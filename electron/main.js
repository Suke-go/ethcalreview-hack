/**
 * Electron Main Process
 * ウィンドウ管理、Pythonバックエンド起動、IPC処理
 */
const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const ConfigManager = require('./config-manager');

// 開発モード判定
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

let mainWindow = null;
let backendProcess = null;
let configManager = null;

/**
 * メインウィンドウを作成
 */
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
        icon: path.join(__dirname, '../frontend/public/icon.png'),
        title: 'Ethics Review Helper',
    });

    // 開発モード: Vite dev server
    // 本番: ビルド済みファイル
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(path.join(__dirname, '../frontend/dist/index.html'));
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

/**
 * Pythonバックエンドを起動
 */
function startBackend() {
    const backendDir = path.join(__dirname, '../backend');

    // 環境変数でユーザーデータディレクトリを渡す
    const env = {
        ...process.env,
        ETHICS_DATA_DIR: configManager.getUserDataPath(),
    };

    if (isDev) {
        // 開発モード: uvicorn直接実行
        backendProcess = spawn('uvicorn', ['app.main:app', '--reload', '--port', '8000'], {
            cwd: backendDir,
            env,
            shell: true,
        });
    } else {
        // 本番モード: PyInstallerでビルドしたexe
        const exePath = path.join(__dirname, '../backend-dist/backend.exe');
        if (fs.existsSync(exePath)) {
            backendProcess = spawn(exePath, [], { env });
        } else {
            console.error('Backend executable not found:', exePath);
            mainWindow?.webContents.send('backend:error', 'Backend executable not found');
            return;
        }
    }

    backendProcess.stdout?.on('data', (data) => {
        console.log(`[Backend] ${data}`);
        if (data.toString().includes('Application startup complete')) {
            mainWindow?.webContents.send('backend:ready');
        }
    });

    backendProcess.stderr?.on('data', (data) => {
        console.error(`[Backend Error] ${data}`);
    });

    backendProcess.on('close', (code) => {
        console.log(`Backend process exited with code ${code}`);
        backendProcess = null;
    });
}

/**
 * バックエンドを停止
 */
function stopBackend() {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
}

/**
 * IPC ハンドラの登録
 */
function setupIpcHandlers() {
    // 設定関連
    ipcMain.handle('config:getSettings', () => {
        return configManager.loadSettings();
    });

    ipcMain.handle('config:saveSettings', (_, settings) => {
        configManager.saveSettings(settings);
        return true;
    });

    ipcMain.handle('config:getLabDefaults', () => {
        return configManager.loadLabDefaults();
    });

    ipcMain.handle('config:saveLabDefaults', (_, labDefaults) => {
        configManager.saveLabDefaults(labDefaults);
        return true;
    });

    ipcMain.handle('config:importLabDefaults', async (_, filePath) => {
        try {
            const content = fs.readFileSync(filePath, 'utf8');
            const labDefaults = JSON.parse(content);
            configManager.saveLabDefaults(labDefaults);
            return { success: true };
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    // シェル操作
    ipcMain.handle('shell:openUserDataFolder', () => {
        shell.openPath(configManager.getUserDataPath());
        return true;
    });

    // ダイアログ
    ipcMain.handle('dialog:selectFile', async (_, options) => {
        const result = await dialog.showOpenDialog(mainWindow, {
            properties: ['openFile'],
            filters: [{ name: 'JSON', extensions: ['json'] }],
            ...options,
        });
        return result;
    });

    // バックエンド制御
    ipcMain.handle('backend:getStatus', () => {
        return backendProcess ? 'running' : 'stopped';
    });

    ipcMain.handle('backend:restart', () => {
        stopBackend();
        startBackend();
        return true;
    });

    // パス情報
    ipcMain.handle('path:getUserData', () => {
        return configManager.getUserDataPath();
    });

    // アプリ情報
    ipcMain.handle('app:getVersion', () => {
        return app.getVersion();
    });
}

// アプリ起動
app.whenReady().then(() => {
    configManager = new ConfigManager();
    setupIpcHandlers();
    createWindow();

    // 開発モードではバックエンドは別途起動されている前提
    // 本番モードではここで起動
    if (!isDev) {
        startBackend();
    }

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// 全ウィンドウ閉じたら終了
app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// アプリ終了時にバックエンドも停止
app.on('before-quit', () => {
    stopBackend();
});
