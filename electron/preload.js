/**
 * Electron Preload Script
 * セキュアなIPC通信とファイル操作APIの公開
 */
const { contextBridge, ipcRenderer, shell } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // 設定関連
    getSettings: () => ipcRenderer.invoke('config:getSettings'),
    saveSettings: (settings) => ipcRenderer.invoke('config:saveSettings', settings),

    // Lab defaults関連
    getLabDefaults: () => ipcRenderer.invoke('config:getLabDefaults'),
    saveLabDefaults: (labDefaults) => ipcRenderer.invoke('config:saveLabDefaults', labDefaults),
    importLabDefaults: (filePath) => ipcRenderer.invoke('config:importLabDefaults', filePath),

    // ファイル操作
    openUserDataFolder: () => ipcRenderer.invoke('shell:openUserDataFolder'),
    selectFile: (options) => ipcRenderer.invoke('dialog:selectFile', options),

    // バックエンド状態
    getBackendStatus: () => ipcRenderer.invoke('backend:getStatus'),
    restartBackend: () => ipcRenderer.invoke('backend:restart'),

    // パス情報
    getUserDataPath: () => ipcRenderer.invoke('path:getUserData'),

    // アプリ情報
    getAppVersion: () => ipcRenderer.invoke('app:getVersion'),

    // イベントリスナー
    onBackendReady: (callback) => ipcRenderer.on('backend:ready', callback),
    onBackendError: (callback) => ipcRenderer.on('backend:error', callback),
});
