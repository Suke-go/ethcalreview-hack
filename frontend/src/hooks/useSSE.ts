import { useState, useEffect, useCallback, useRef } from 'react';

export interface ProgressEvent {
    step: string;
    status: 'running' | 'completed' | 'error';
    message: string;
    detail?: Record<string, unknown>;
}

export interface SSEOptions {
    headers?: Record<string, string>;
    body?: unknown;
    onProgress?: (event: ProgressEvent) => void;
    onResult?: (result: unknown) => void;
    onError?: (error: string, detail?: unknown) => void;
}

export type SSEStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

export function useSSE<T = unknown>() {
    const [data, setData] = useState<T | null>(null);
    const [progress, setProgress] = useState<ProgressEvent[]>([]);
    const [status, setStatus] = useState<SSEStatus>('idle');
    const [error, setError] = useState<string | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    const statusRef = useRef<SSEStatus>('idle');

    // statusが変更されたらrefも更新
    useEffect(() => {
        statusRef.current = status;
    }, [status]);

    const reset = useCallback(() => {
        setData(null);
        setProgress([]);
        setStatus('idle');
        setError(null);
        statusRef.current = 'idle';
    }, []);

    const start = useCallback(async (url: string, options: SSEOptions) => {
        // 既存の接続をキャンセル
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        reset();
        setStatus('connecting');
        statusRef.current = 'connecting';

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                body: JSON.stringify(options.body),
                signal: abortController.signal,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            if (!response.body) {
                throw new Error('Response body is null');
            }

            setStatus('streaming');
            statusRef.current = 'streaming';

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let resultReceived = false;

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                // SSEイベントをパース
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // 未完了の行を保持

                let currentEventType = '';
                let currentData = '';

                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        currentEventType = line.slice(7).trim();
                    } else if (line.startsWith('data: ')) {
                        currentData = line.slice(6);

                        if (currentEventType && currentData) {
                            try {
                                const parsedData = JSON.parse(currentData);

                                if (currentEventType === 'progress') {
                                    const progressEvent = parsedData as ProgressEvent;
                                    setProgress(prev => [...prev, progressEvent]);
                                    options.onProgress?.(progressEvent);
                                } else if (currentEventType === 'result') {
                                    console.log('[SSE] Result received:', parsedData);
                                    setData(parsedData as T);
                                    setStatus('done');
                                    statusRef.current = 'done';
                                    resultReceived = true;
                                    // コールバックを呼び出し
                                    if (options.onResult) {
                                        console.log('[SSE] Calling onResult callback');
                                        options.onResult(parsedData);
                                    }
                                } else if (currentEventType === 'error') {
                                    const errorMessage = parsedData.message || 'Unknown error';
                                    setError(errorMessage);
                                    setStatus('error');
                                    statusRef.current = 'error';
                                    options.onError?.(errorMessage, parsedData.detail);
                                }
                            } catch (e) {
                                console.error('Failed to parse SSE data:', e, currentData);
                            }

                            currentEventType = '';
                            currentData = '';
                        }
                    }
                }
            }

            // ストリーム完了後、まだdoneになっていなければ完了とする
            if (!resultReceived && statusRef.current !== 'done' && statusRef.current !== 'error') {
                console.log('[SSE] Stream ended without result event');
                setStatus('done');
                statusRef.current = 'done';
            }

        } catch (err) {
            if (err instanceof Error && err.name === 'AbortError') {
                // キャンセルされた場合は無視
                return;
            }

            const errorMessage = err instanceof Error ? err.message : 'Unknown error';
            console.error('[SSE] Error:', errorMessage);
            setError(errorMessage);
            setStatus('error');
            statusRef.current = 'error';
            options.onError?.(errorMessage);
        }
    }, [reset]);

    const cancel = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setStatus('idle');
        statusRef.current = 'idle';
    }, []);

    // クリーンアップ
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    return {
        data,
        progress,
        status,
        error,
        start,
        cancel,
        reset,
    };
}
