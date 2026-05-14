// frontend/src/components/SessionList.tsx
// セッション一覧・選択コンポーネント

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-toastify';
import type { SessionSummary, SessionStatus } from '../types';
import { getSessions, deleteSession, resumeSession } from '../api/client';
import { Button } from './common/Button';
import './SessionList.css';

interface SessionListProps {
    onSelectSession: (sessionId: string) => void;
    onCreateNew: () => void;
}

const STATUS_LABELS: Record<SessionStatus, string> = {
    in_progress: '作成中',
    submitted: '提出済み',
    rebuttal: '修正対応中',
    completed: '完了',
};

const STEP_LABELS: Record<string, string> = {
    analyze: '解析',
    confirm: '確認',
    generate: '生成',
    review: 'レビュー',
    submit: '提出',
    rebuttal: '修正対応',
    completed: '完了',
};

export function SessionList({ onSelectSession, onCreateNew }: SessionListProps) {
    const [sessions, setSessions] = useState<SessionSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filter, setFilter] = useState<SessionStatus | 'all'>('all');

    const loadSessions = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getSessions(filter === 'all' ? undefined : filter);
            setSessions(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'セッションの読み込みに失敗しました');
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        loadSessions();
    }, [loadSessions]);

    const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('このセッションを削除しますか？')) return;

        try {
            await deleteSession(sessionId);
            setSessions(sessions.filter(s => s.sessionId !== sessionId));
            toast.success('セッションを削除しました');
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '削除に失敗しました');
        }
    };

    const handleResume = async (sessionId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            const result = await resumeSession(sessionId);
            toast.success(`セッションを再開しました（現在のステップ: ${STEP_LABELS[result.currentStep] || result.currentStep}）`);
            onSelectSession(sessionId);
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '再開に失敗しました');
        }
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('ja-JP', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <div className="session-list">
            <div className="session-list-header">
            <h2>📋 セッション一覧</h2>
            <Button variant="primary" size="md" onClick={onCreateNew}>
                ＋ 新規作成
            </Button>
            </div>

            <div className="session-list-filters">
                <button
                    className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
                    onClick={() => setFilter('all')}
                >
                    すべて
                </button>
                <button
                    className={`filter-btn ${filter === 'in_progress' ? 'active' : ''}`}
                    onClick={() => setFilter('in_progress')}
                >
                    作成中
                </button>
                <button
                    className={`filter-btn ${filter === 'rebuttal' ? 'active' : ''}`}
                    onClick={() => setFilter('rebuttal')}
                >
                    修正対応中
                </button>
                <button
                    className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
                    onClick={() => setFilter('completed')}
                >
                    完了
                </button>
            </div>

            {loading && (
                <div className="session-list-loading">
                    <div className="spinner"></div>
                    <span>読み込み中...</span>
                </div>
            )}

            {error && (
                <div className="session-list-error">
                    <span>⚠️ {error}</span>
                    <button onClick={loadSessions}>再読み込み</button>
                </div>
            )}

            {!loading && !error && sessions.length === 0 && (
                <div className="session-list-empty">
                    <p>セッションがありません</p>
                    <Button variant="primary" size="md" onClick={onCreateNew}>
                        新しい申請を始める
                    </Button>
                </div>
            )}

            {!loading && !error && sessions.length > 0 && (
                <div className="session-list-items">
                    {sessions.map((session) => (
                        <div
                            key={session.sessionId}
                            className="session-item"
                            onClick={() => onSelectSession(session.sessionId)}
                        >
                            <div className="session-item-main">
                                <div className="session-item-title">
                                    {session.title || '（タイトル未設定）'}
                                </div>
                                <div className="session-item-meta">
                                    <div className="session-status-stack">
                                        <span
                                            className={`session-status status-${session.status}`}
                                        >
                                            {STATUS_LABELS[session.status]}
                                        </span>
                                        <span className="session-status-detail">
                                            📍 {STEP_LABELS[session.currentStep] || session.currentStep}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div className="session-item-side">
                                <div className="session-item-date">
                                    {formatDate(session.updatedAt)}
                                </div>
                                <div className="session-item-actions">
                                    {session.status === 'in_progress' && (
                                        <button
                                            className="btn-icon"
                                            onClick={(e) => handleResume(session.sessionId, e)}
                                            title="再開"
                                        >
                                            ▶️
                                        </button>
                                    )}
                                    <button
                                        className="btn-icon btn-danger"
                                        onClick={(e) => handleDelete(session.sessionId, e)}
                                        title="削除"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default SessionList;
