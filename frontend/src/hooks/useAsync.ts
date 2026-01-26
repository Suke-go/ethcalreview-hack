// frontend/src/hooks/useAsync.ts
// 非同期処理管理用カスタムフック

import { useState, useCallback, useRef, useEffect } from 'react';

export interface AsyncState<T> {
    data: T | null;
    isLoading: boolean;
    error: string | null;
}

export interface UseAsyncReturn<T, Args extends unknown[]> extends AsyncState<T> {
    execute: (...args: Args) => Promise<T | null>;
    reset: () => void;
}

export function useAsync<T, Args extends unknown[] = []>(
    asyncFunction: (...args: Args) => Promise<T>,
    immediate = false
): UseAsyncReturn<T, Args> {
    const [state, setState] = useState<AsyncState<T>>({
        data: null,
        isLoading: immediate,
        error: null,
    });

    const isMountedRef = useRef(true);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    const execute = useCallback(
        async (...args: Args): Promise<T | null> => {
            setState({ data: null, isLoading: true, error: null });

            try {
                const result = await asyncFunction(...args);

                if (isMountedRef.current) {
                    setState({ data: result, isLoading: false, error: null });
                }

                return result;
            } catch (err) {
                const errorMessage = err instanceof Error ? err.message : '予期せぬエラーが発生しました';

                if (isMountedRef.current) {
                    setState({ data: null, isLoading: false, error: errorMessage });
                }

                return null;
            }
        },
        [asyncFunction]
    );

    const reset = useCallback(() => {
        setState({ data: null, isLoading: false, error: null });
    }, []);

    return {
        ...state,
        execute,
        reset,
    };
}

// ポーリング用フック
export interface UsePollingOptions {
    interval: number;
    enabled?: boolean;
    onSuccess?: () => void;
    shouldStop?: (data: unknown) => boolean;
}

export function usePolling<T>(
    asyncFunction: () => Promise<T>,
    options: UsePollingOptions
): AsyncState<T> & { start: () => void; stop: () => void } {
    const { interval, enabled = true, onSuccess, shouldStop } = options;
    const [state, setState] = useState<AsyncState<T>>({
        data: null,
        isLoading: false,
        error: null,
    });

    const intervalRef = useRef<number | null>(null);
    const isMountedRef = useRef(true);

    const poll = useCallback(async () => {
        if (!isMountedRef.current) return;

        try {
            setState((prev) => ({ ...prev, isLoading: true }));
            const result = await asyncFunction();

            if (!isMountedRef.current) return;

            setState({ data: result, isLoading: false, error: null });

            if (shouldStop?.(result)) {
                if (intervalRef.current) {
                    clearInterval(intervalRef.current);
                    intervalRef.current = null;
                }
                onSuccess?.();
            }
        } catch (err) {
            if (!isMountedRef.current) return;

            const errorMessage = err instanceof Error ? err.message : 'ポーリング中にエラーが発生しました';
            setState((prev) => ({ ...prev, isLoading: false, error: errorMessage }));
        }
    }, [asyncFunction, shouldStop, onSuccess]);

    const start = useCallback(() => {
        if (intervalRef.current) return;
        poll();
        intervalRef.current = window.setInterval(poll, interval);
    }, [poll, interval]);

    const stop = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
    }, []);

    useEffect(() => {
        isMountedRef.current = true;

        if (enabled) {
            start();
        }

        return () => {
            isMountedRef.current = false;
            stop();
        };
    }, [enabled, start, stop]);

    return {
        ...state,
        start,
        stop,
    };
}
