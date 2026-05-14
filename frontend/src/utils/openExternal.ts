// frontend/src/utils/openExternal.ts
//
// 外部 URL を「OS のデフォルトブラウザ」で開くユーティリティ。
//
//   - Tauri WebView: `window.open` は無視される / WebView 内に遷移してしまうため、
//     Rust 側の `open_external` カスタムコマンド経由で `shell().open()` を呼ぶ。
//   - ブラウザ (Web ホスト時): 通常の `window.open(url, '_blank')` で新規タブを開く。
//
// Tauri ランタイム検出は client.ts と同じく `window.__TAURI_INTERNALS__` で行う。

const isTauri = (): boolean => {
    if (typeof window === 'undefined') return false;
    const w = window as unknown as Record<string, unknown>;
    return '__TAURI_INTERNALS__' in w || '__TAURI__' in w;
};

export const openExternal = async (url: string): Promise<void> => {
    if (isTauri()) {
        // @tauri-apps/api/core からの動的 import — ブラウザビルドでも実行時に
        // 不要な依存を読み込まない (webpack/vite は dynamic import を分割する)。
        const { invoke } = await import('@tauri-apps/api/core');
        await invoke('open_external', { url });
        return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
};
