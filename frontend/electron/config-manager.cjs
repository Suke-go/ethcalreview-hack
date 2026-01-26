/**
 * Electron Config Manager
 * ユーザーデータディレクトリでの設定ファイル管理
 */
const { app } = require('electron');
const path = require('path');
const fs = require('fs');

class ConfigManager {
    constructor() {
        // ユーザーデータディレクトリ: %APPDATA%/EthicalReviewHacker (Windows)
        this.userDataPath = app.getPath('userData');
        this.ensureDirectories();
    }

    /**
     * 必要なディレクトリを作成
     */
    ensureDirectories() {
        const dirs = [
            this.userDataPath,
            path.join(this.userDataPath, 'sessions'),
            path.join(this.userDataPath, 'output'),
        ];

        dirs.forEach(dir => {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        });
    }

    /**
     * 設定ファイルのパスを取得
     */
    getConfigPath(filename) {
        return path.join(this.userDataPath, filename);
    }

    /**
     * settings.json を読み込み
     */
    loadSettings() {
        const settingsPath = this.getConfigPath('settings.json');

        if (fs.existsSync(settingsPath)) {
            try {
                const content = fs.readFileSync(settingsPath, 'utf8');
                return JSON.parse(content);
            } catch (e) {
                console.error('Failed to load settings:', e);
                return this.getDefaultSettings();
            }
        }

        // デフォルト設定を作成
        const defaults = this.getDefaultSettings();
        this.saveSettings(defaults);
        return defaults;
    }

    /**
     * settings.json を保存
     */
    saveSettings(settings) {
        const settingsPath = this.getConfigPath('settings.json');
        fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf8');
    }

    /**
     * lab_defaults.json を読み込み
     */
    loadLabDefaults() {
        const labDefaultsPath = this.getConfigPath('lab_defaults.json');

        if (fs.existsSync(labDefaultsPath)) {
            try {
                const content = fs.readFileSync(labDefaultsPath, 'utf8');
                return JSON.parse(content);
            } catch (e) {
                console.error('Failed to load lab_defaults:', e);
                return null;
            }
        }

        // ユーザーデータにない場合はnull（アプリ同梱のデフォルトを使用）
        return null;
    }

    /**
     * lab_defaults.json を保存（外部ファイルインポート時）
     */
    saveLabDefaults(labDefaults) {
        const labDefaultsPath = this.getConfigPath('lab_defaults.json');
        fs.writeFileSync(labDefaultsPath, JSON.stringify(labDefaults, null, 2), 'utf8');
    }

    /**
     * デフォルト設定
     */
    getDefaultSettings() {
        return {
            api_key: '',
            llm: {
                provider: 'gemini',
                model: 'gemini-2.5-flash'
            },
            principal_investigator: {
                name: '',
                affiliation: '',
                position: '',
                email: '',
                phone: ''
            }
        };
    }

    /**
     * ユーザーデータディレクトリのパスを取得
     */
    getUserDataPath() {
        return this.userDataPath;
    }
}

module.exports = ConfigManager;
