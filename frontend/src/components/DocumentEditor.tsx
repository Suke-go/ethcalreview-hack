import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'react-toastify';
import { Button } from './common/Button';
import {
  getEditableContext,
  applyEditableContext,
  type EditableField,
} from '../api/client';

interface DocumentEditorProps {
  sessionId: string;
  onClose: () => void;
  /** 反映成功後に呼ばれる（ダウンロード対象が更新されたことを親へ通知） */
  onApplied?: () => void;
}

/**
 * 対話的な書類編集パネル（崩れない設計）。
 *
 * docx を直接編集せず、構造化データ（context）の項目を編集する。保存すると
 * バックエンドがアンカーベースの公式様式レンダラで再描画するため、テンプレートの
 * 段組み・チェック欄・項番は崩れない。LLM生成物（実施計画書等）は保持される。
 */
export const DocumentEditor: React.FC<DocumentEditorProps> = ({ sessionId, onClose, onApplied }) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState('');
  const [fields, setFields] = useState<EditableField[]>([]);
  // key -> 編集後テキスト（list/textarea/text/number すべて文字列で保持）
  const [draft, setDraft] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getEditableContext(sessionId);
        if (!active) return;
        setTitle(data.title);
        setFields(data.fields);
        const init: Record<string, string> = {};
        for (const f of data.fields) init[f.key] = f.text ?? '';
        setDraft(init);
      } catch (err) {
        toast.error(`編集データの取得に失敗しました: ${err instanceof Error ? err.message : '不明なエラー'}`);
        onClose();
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [sessionId, onClose]);

  // group ごとにまとめる（定義順を保つ）
  const grouped = useMemo(() => {
    const order: string[] = [];
    const map: Record<string, EditableField[]> = {};
    for (const f of fields) {
      if (!map[f.group]) {
        map[f.group] = [];
        order.push(f.group);
      }
      map[f.group].push(f);
    }
    return order.map((g) => ({ group: g, items: map[g] }));
  }, [fields]);

  const dirtyKeys = useMemo(
    () => fields.filter((f) => (draft[f.key] ?? '') !== (f.text ?? '')).map((f) => f.key),
    [fields, draft]
  );

  const handleSave = async () => {
    if (dirtyKeys.length === 0) {
      toast.info('変更がありません。');
      return;
    }
    setSaving(true);
    try {
      // 変更したフィールドだけ送る（list 型は改行区切り文字列のまま送ってサーバ側で配列化）
      const edits: Record<string, string> = {};
      for (const k of dirtyKeys) edits[k] = draft[k] ?? '';
      const res = await applyEditableContext(sessionId, edits);

      const counts = (res.reviewNotes?.counts ?? {}) as Record<string, number>;
      if (res.errors.length > 0) {
        toast.warning(`再描画しました（${res.regenerated.length}件）。一部失敗: ${res.errors.join(', ')}`);
      } else {
        toast.success(`編集を公式様式へ反映しました（${res.regenerated.length}件を再生成）`);
      }
      if ((counts.errors ?? 0) > 0 || (counts.missing_items ?? 0) > 0) {
        toast.info(
          `要確認: 不足 ${counts.errors ?? 0} / 確認質問 ${counts.missing_items ?? 0} 件。レビュー指摘リストをご確認ください。`,
          { autoClose: 8000 }
        );
      }
      // 反映後の最新値でフォームを更新（textを基準値に同期）
      setFields(res.fields);
      const next: Record<string, string> = {};
      for (const f of res.fields) next[f.key] = f.text ?? '';
      setDraft(next);
      onApplied?.();
    } catch (err) {
      toast.error(`反映に失敗しました: ${err instanceof Error ? err.message : '不明なエラー'}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>📝 書類の内容を編集</h2>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: '#666' }}>
              {title || '（無題）'} ／ 編集すると公式様式に当てはめ直します（様式は崩れません）
            </p>
          </div>
          <button onClick={onClose} style={closeBtnStyle} aria-label="閉じる">
            ×
          </button>
        </div>

        <div style={bodyStyle}>
          {loading ? (
            <p style={{ textAlign: 'center', color: '#888' }}>読み込み中…</p>
          ) : (
            grouped.map(({ group, items }) => (
              <fieldset key={group} style={fieldsetStyle}>
                <legend style={legendStyle}>{group}</legend>
                {items.map((f) => {
                  const changed = (draft[f.key] ?? '') !== (f.text ?? '');
                  return (
                    <div key={f.key} style={{ marginBottom: '0.75rem' }}>
                      <label style={labelStyle}>
                        {f.label}
                        {changed && <span style={changedBadge}>変更あり</span>}
                      </label>
                      {f.type === 'textarea' || f.type === 'list' ? (
                        <textarea
                          value={draft[f.key] ?? ''}
                          onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                          rows={f.type === 'list' ? 4 : 3}
                          style={inputStyle}
                          placeholder={f.type === 'list' ? '1行に1項目' : ''}
                        />
                      ) : (
                        <input
                          type={f.type === 'number' ? 'number' : 'text'}
                          value={draft[f.key] ?? ''}
                          onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                          style={inputStyle}
                        />
                      )}
                    </div>
                  );
                })}
              </fieldset>
            ))
          )}
        </div>

        <div style={footerStyle}>
          <span style={{ fontSize: '0.8rem', color: '#666' }}>
            {dirtyKeys.length > 0 ? `${dirtyKeys.length} 項目を変更中` : '変更なし'}
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="secondary" onClick={onClose} disabled={saving}>
              閉じる
            </Button>
            <Button variant="primary" isLoading={saving} onClick={handleSave} disabled={dirtyKeys.length === 0}>
              保存して様式に反映
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.45)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: '1rem',
};

const panelStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: 12,
  width: 'min(760px, 100%)',
  maxHeight: '90vh',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  padding: '1rem 1.25rem',
  borderBottom: '1px solid #eee',
};

const closeBtnStyle: React.CSSProperties = {
  border: 'none',
  background: 'transparent',
  fontSize: '1.5rem',
  cursor: 'pointer',
  color: '#888',
  lineHeight: 1,
};

const bodyStyle: React.CSSProperties = {
  padding: '1rem 1.25rem',
  overflowY: 'auto',
};

const footerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '0.85rem 1.25rem',
  borderTop: '1px solid #eee',
};

const fieldsetStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: '0.75rem 1rem 1rem',
  marginBottom: '1rem',
};

const legendStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: '0.9rem',
  padding: '0 0.4rem',
  color: '#374151',
};

const labelStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  fontSize: '0.82rem',
  color: '#374151',
  marginBottom: '0.25rem',
};

const changedBadge: React.CSSProperties = {
  fontSize: '0.7rem',
  color: '#b45309',
  background: '#fef3c7',
  borderRadius: 4,
  padding: '0 0.35rem',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '0.5rem 0.6rem',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: '0.9rem',
  fontFamily: 'inherit',
};
