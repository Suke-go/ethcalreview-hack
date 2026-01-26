// frontend/src/components/ReviewVisualization.tsx
// マルチエージェント レビューやり取りの可視化コンポーネント

import React, { useState, useEffect, useRef } from 'react';
import { getRebuttalRounds } from '../api/client';
import type { RebuttalSuggestions } from '../types';
import './ReviewVisualization.css';

export interface RebuttalRound {
    roundNumber: number;
    feedbackText: string;
    status: string;
    createdAt: string;
    hasSuggestions: boolean;
    suggestions?: RebuttalSuggestions['suggestions'];
    responseDraft?: string;
}

interface ReviewVisualizationProps {
    sessionId: string;
    onClose?: () => void;
}

export const ReviewVisualization: React.FC<ReviewVisualizationProps> = ({
    sessionId,
    onClose
}) => {
    const [rounds, setRounds] = useState<RebuttalRound[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    // ラウンド情報の取得
    useEffect(() => {
        const fetchRounds = async () => {
            try {
                setLoading(true);
                const data = await getRebuttalRounds(sessionId);
                setRounds(data as RebuttalRound[]);
                setError(null);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load review data');
            } finally {
                setLoading(false);
            }
        };

        fetchRounds();

        // 定期的に更新（リアルタイム対応）
        const interval = setInterval(fetchRounds, 3000);
        return () => clearInterval(interval);
    }, [sessionId]);

    // 最新のラウンドまで自動スクロール
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [rounds]);

    if (loading && rounds.length === 0) {
        return (
            <div className="review-visualization loading">
                <div className="spinner"></div>
                <p>レビューデータを読み込んでいます...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="review-visualization error">
                <p>エラー: {error}</p>
                {onClose && <button onClick={onClose}>閉じる</button>}
            </div>
        );
    }

    return (
        <div className="review-visualization">
            <div className="review-header">
                <h2>📝 査読やり取り履歴</h2>
                {onClose && (
                    <button className="close-button" onClick={onClose}>
                        ✕
                    </button>
                )}
            </div>

            <div className="review-timeline" ref={scrollRef}>
                {rounds.length === 0 ? (
                    <div className="empty-state">
                        <p>まだ査読コメントはありません</p>
                    </div>
                ) : (
                    rounds.map((round) => (
                        <ReviewRoundDisplay key={round.roundNumber} round={round} />
                    ))
                )}
            </div>

            <div className="review-footer">
                <span className="rounds-count">
                    {rounds.length > 0 ? `${rounds.length}ラウンド` : '0ラウンド'}
                </span>
            </div>
        </div>
    );
};

// 個別ラウンドの表示コンポーネント
const ReviewRoundDisplay: React.FC<{ round: RebuttalRound }> = ({ round }) => {
    const [expanded, setExpanded] = useState(false);

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleString('ja-JP', {
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div className="review-round">
            <div className="round-header">
                <span className="round-number">ラウンド {round.roundNumber}</span>
                <span className="round-date">{formatDate(round.createdAt)}</span>
                <span className={`round-status status-${round.status}`}>
                    {round.status === 'completed' ? '完了' : '進行中'}
                </span>
            </div>

            {/* 査読者コメント */}
            <div className="message reviewer-message">
                <div className="message-header">
                    <span className="agent-icon">👨‍🔬</span>
                    <span className="agent-name">査読者</span>
                </div>
                <div className="message-content">
                    <p className="feedback-text">{round.feedbackText}</p>
                </div>
            </div>

            {/* AI提案 */}
            {round.hasSuggestions && round.suggestions && (
                <div className="message ai-message">
                    <div className="message-header">
                        <span className="agent-icon">🤖</span>
                        <span className="agent-name">AI アシスタント</span>
                        <button
                            className="expand-button"
                            onClick={() => setExpanded(!expanded)}
                        >
                            {expanded ? '▼ 折りたたむ' : '▶ 展開'}
                        </button>
                    </div>

                    <div className="message-content">
                        <p className="suggestion-summary">
                            {round.suggestions.length}件の改善提案を生成しました
                        </p>

                        {expanded && (
                            <div className="suggestions-list">
                                {round.suggestions.map((suggestion, index) => (
                                    <div
                                        key={index}
                                        className="suggestion-item"
                                    >
                                        <div className="suggestion-header">
                                            <span className="suggestion-type">
                                                📍 {suggestion.field}
                                            </span>
                                        </div>
                                        <div className="suggestion-diff">
                                            <div className="diff-before">
                                                <span className="diff-label">現在:</span>
                                                <span>{suggestion.originalValue || '（未記載）'}</span>
                                            </div>
                                            <div className="diff-after">
                                                <span className="diff-label">提案:</span>
                                                <span>{suggestion.suggestedValue}</span>
                                            </div>
                                        </div>
                                        {suggestion.reason && (
                                            <p className="suggestion-rationale">
                                                <em>💬 {suggestion.reason}</em>
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 研究者の返答 */}
            {round.responseDraft && (
                <div className="message researcher-message">
                    <div className="message-header">
                        <span className="agent-icon">👨‍💼</span>
                        <span className="agent-name">研究者</span>
                    </div>
                    <div className="message-content">
                        <p className="response-text">{round.responseDraft}</p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ReviewVisualization;
