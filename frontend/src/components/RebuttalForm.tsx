// frontend/src/components/RebuttalForm.tsx
// Rebuttal（修正対応）入力・表示コンポーネント

import { useState } from 'react';
import { toast } from 'react-toastify';
import type { RebuttalSuggestion } from '../types';
import { createRebuttal, applyRebuttal } from '../api/client';
import './RebuttalForm.css';

interface RebuttalFormProps {
    sessionId: string;
    onComplete?: () => void;
}

interface RebuttalResult {
    roundNumber: number;
    feedbackText: string;
    suggestions: RebuttalSuggestion[];
    responseDraft: string;
}

export function RebuttalForm({ sessionId, onComplete }: RebuttalFormProps) {
    const [feedbackText, setFeedbackText] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<RebuttalResult | null>(null);
    const [editedResponse, setEditedResponse] = useState('');
    const [acceptedSuggestions, setAcceptedSuggestions] = useState<Set<number>>(new Set());

    const handleSubmit = async () => {
        if (!feedbackText.trim()) {
            setError('指摘事項を入力してください');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await createRebuttal(sessionId, feedbackText);
            setResult({
                roundNumber: response.roundNumber,
                feedbackText: response.feedbackText,
                suggestions: response.suggestions,
                responseDraft: response.responseDraft,
            });
            setEditedResponse(response.responseDraft);
            // 全提案を初期状態で選択
            setAcceptedSuggestions(new Set(response.suggestions.map((_, i) => i)));
        } catch (e) {
            setError(e instanceof Error ? e.message : '修正提案の生成に失敗しました');
        } finally {
            setLoading(false);
        }
    };

    const toggleSuggestion = (index: number) => {
        const newSet = new Set(acceptedSuggestions);
        if (newSet.has(index)) {
            newSet.delete(index);
        } else {
            newSet.add(index);
        }
        setAcceptedSuggestions(newSet);
    };

    const handleApply = async () => {
        if (!result) return;

        setLoading(true);
        try {
            await applyRebuttal(
                sessionId,
                result.roundNumber,
                editedResponse,
                Array.from(acceptedSuggestions)
            );
            toast.success('修正を適用しました');
            onComplete?.();
        } catch (e) {
            setError(e instanceof Error ? e.message : '修正の適用に失敗しました');
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setResult(null);
        setFeedbackText('');
        setEditedResponse('');
        setAcceptedSuggestions(new Set());
        setError(null);
    };

    // 入力フォーム
    if (!result) {
        return (
            <div className="rebuttal-form">
                <div className="rebuttal-header">
                    <h2>📝 修正対応（Rebuttal）</h2>
                    <p className="rebuttal-description">
                        委員会からの指摘事項を入力すると、AIが修正提案を生成します。
                    </p>
                </div>

                <div className="rebuttal-input-section">
                    <label htmlFor="feedback">指摘事項</label>
                    <textarea
                        id="feedback"
                        value={feedbackText}
                        onChange={(e) => setFeedbackText(e.target.value)}
                        placeholder="例：&#10;・実験手順の詳細が不足しています&#10;・リスク対策について具体的な記載が必要です&#10;・参加者への謝金の根拠を明記してください"
                        rows={8}
                        disabled={loading}
                    />
                </div>

                {error && (
                    <div className="rebuttal-error">
                        ⚠️ {error}
                    </div>
                )}

                <div className="rebuttal-actions">
                    <button
                        className="btn-primary"
                        onClick={handleSubmit}
                        disabled={loading || !feedbackText.trim()}
                    >
                        {loading ? (
                            <>
                                <span className="spinner-small"></span>
                                生成中...
                            </>
                        ) : (
                            '🔍 修正提案を生成'
                        )}
                    </button>
                </div>
            </div>
        );
    }

    // 結果表示
    return (
        <div className="rebuttal-form">
            <div className="rebuttal-header">
                <h2>✨ 修正提案（ラウンド {result.roundNumber}）</h2>
                <button className="btn-secondary" onClick={handleReset}>
                    ← 新しい指摘を入力
                </button>
            </div>

            {/* 元の指摘事項 */}
            <div className="rebuttal-section">
                <h3>📥 入力した指摘事項</h3>
                <div className="feedback-display">
                    {result.feedbackText}
                </div>
            </div>

            {/* 指摘の解釈・対応方針 */}
            <div className="rebuttal-section interpretation-section">
                <h3>🔍 指摘の解釈・対応方針</h3>
                <div className="interpretation-content">
                    {result.suggestions.length > 0 ? (
                        <ul className="interpretation-list">
                            {result.suggestions.map((suggestion, index) => (
                                <li key={index}>
                                    <strong>{suggestion.field}</strong>: {suggestion.reason}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p>指摘事項に対する具体的な修正提案を生成しました。</p>
                    )}
                </div>
            </div>

            {/* 文書修正提案リスト */}
            <div className="rebuttal-section">
                <h3>📝 文書修正提案</h3>
                <p className="section-description">チェックした項目が書類に反映されます</p>
                <div className="suggestions-list">
                    {result.suggestions.map((suggestion, index) => (
                        <div
                            key={index}
                            className={`suggestion-item ${acceptedSuggestions.has(index) ? 'accepted' : 'rejected'}`}
                            onClick={() => toggleSuggestion(index)}
                        >
                            <div className="suggestion-checkbox">
                                {acceptedSuggestions.has(index) ? '✅' : '⬜'}
                            </div>
                            <div className="suggestion-content">
                                <div className="suggestion-field">
                                    <strong>📍 {suggestion.field}</strong>
                                </div>
                                <div className="suggestion-diff">
                                    <div className="diff-before">
                                        <span className="diff-label">現在:</span>
                                        <span className="diff-text">{suggestion.originalValue || '（未記載）'}</span>
                                    </div>
                                    <div className="diff-arrow">→</div>
                                    <div className="diff-after">
                                        <span className="diff-label">提案:</span>
                                        <span className="diff-text">{suggestion.suggestedValue}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* 回答メール文案 */}
            <div className="rebuttal-section email-section">
                <h3>📧 委員会への回答メール文案</h3>
                <p className="section-description">
                    修正完了後、このメールを委員会に送信してください
                </p>
                <textarea
                    value={editedResponse}
                    onChange={(e) => setEditedResponse(e.target.value)}
                    rows={12}
                    className="response-textarea"
                />
                <button
                    className="btn-copy"
                    onClick={async () => {
                        try {
                            // navigator.clipboard はセキュアコンテキスト必須。
                            // Tauri WebView は通常 secure context だが、
                            // 念のため execCommand フォールバックを用意。
                            if (navigator.clipboard && window.isSecureContext) {
                                await navigator.clipboard.writeText(editedResponse);
                            } else {
                                const ta = document.createElement('textarea');
                                ta.value = editedResponse;
                                ta.style.position = 'fixed';
                                ta.style.left = '-9999px';
                                document.body.appendChild(ta);
                                ta.select();
                                const ok = document.execCommand('copy');
                                ta.remove();
                                if (!ok) throw new Error('execCommand("copy") failed');
                            }
                            toast.success('クリップボードにコピーしました');
                        } catch (err) {
                            console.error('clipboard copy failed:', err);
                            toast.error(
                                `コピーに失敗しました: ${err instanceof Error ? err.message : '不明なエラー'}`
                            );
                        }
                    }}
                >
                    📋 コピー
                </button>
            </div>

            {error && (
                <div className="rebuttal-error">
                    ⚠️ {error}
                </div>
            )}

            <div className="rebuttal-actions">
                <button className="btn-secondary" onClick={handleReset}>
                    キャンセル
                </button>
                <button
                    className="btn-primary"
                    onClick={handleApply}
                    disabled={loading}
                >
                    {loading ? '適用中...' : '✓ 修正を適用してDOCXを再生成'}
                </button>
            </div>
        </div>
    );
}

export default RebuttalForm;
