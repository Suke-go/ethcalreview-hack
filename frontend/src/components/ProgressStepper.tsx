import type { ProgressEvent } from '../hooks/useSSE';
import './ProgressStepper.css';

interface ProgressStepperProps {
    events: ProgressEvent[];
    status: 'idle' | 'connecting' | 'streaming' | 'done' | 'error';
    error?: string | null;
}

const statusIcons: Record<string, string> = {
    running: '🔄',
    completed: '✅',
    error: '❌',
};

const stepLabels: Record<string, string> = {
    receive: '📝 リクエスト受信',
    init_client: '🔧 クライアント初期化',
    analyze: '🧠 AI解析',
    init: '📋 レビュー初期化',
    round_1: '🔍 ラウンド 1',
    round_1_agent_b: '   👨‍⚖️ Agent B (審査委員)',
    round_1_agent_a: '   ✍️ Agent A (起案者)',
    round_2: '🔍 ラウンド 2',
    round_2_agent_b: '   👨‍⚖️ Agent B (審査委員)',
    round_2_agent_a: '   ✍️ Agent A (起案者)',
    complete: '🎉 完了',
};

export function ProgressStepper({ events, status, error }: ProgressStepperProps) {
    if (status === 'idle') {
        return null;
    }

    return (
        <div className="progress-stepper">
            <div className="progress-header">
                {status === 'connecting' && (
                    <span className="status-badge connecting">接続中...</span>
                )}
                {status === 'streaming' && (
                    <span className="status-badge streaming">処理中</span>
                )}
                {status === 'done' && (
                    <span className="status-badge done">完了</span>
                )}
                {status === 'error' && (
                    <span className="status-badge error">エラー</span>
                )}
            </div>

            <div className="progress-events">
                {events.map((event, index) => (
                    <div
                        key={`${event.step}-${index}`}
                        className={`progress-event ${event.status}`}
                    >
                        <span className="event-icon">
                            {event.status === 'running' ? (
                                <span className="spinner" />
                            ) : (
                                statusIcons[event.status] || '•'
                            )}
                        </span>
                        <span className="event-label">
                            {stepLabels[event.step] || event.step}
                        </span>
                        <span className="event-message">
                            {event.message}
                        </span>
                        {event.detail && Object.keys(event.detail).length > 0 && (
                            <span className="event-detail">
                                {event.detail.issues_count !== undefined && (
                                    <span className="badge">{event.detail.issues_count as number}件の指摘</span>
                                )}
                                {event.detail.chars !== undefined && (
                                    <span className="badge">{event.detail.chars as number}文字</span>
                                )}
                            </span>
                        )}
                    </div>
                ))}
            </div>

            {error && (
                <div className="progress-error">
                    <span className="error-icon">⚠️</span>
                    <span className="error-message">{error}</span>
                </div>
            )}
        </div>
    );
}
