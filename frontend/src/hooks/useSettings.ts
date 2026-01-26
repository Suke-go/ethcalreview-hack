// frontend/src/hooks/useSettings.ts
// 設定管理用カスタムフック

import { useState, useEffect, useCallback } from 'react';
import type { Settings } from '../types';
import { getSettings, updateSettings as apiUpdateSettings, setApiKey as setClientApiKey } from '../api/client';

// Electron API 型定義
interface ElectronAPI {
    getSettings: () => Promise<Settings>;
    saveSettings: (settings: Settings) => Promise<boolean>;
    getLabDefaults: () => Promise<unknown>;
    saveLabDefaults: (labDefaults: unknown) => Promise<boolean>;
    openUserDataFolder: () => Promise<boolean>;
    selectFile: (options: unknown) => Promise<{ canceled: boolean; filePaths: string[] }>;
    getBackendStatus: () => Promise<string>;
    restartBackend: () => Promise<boolean>;
    getUserDataPath: () => Promise<string>;
    getAppVersion: () => Promise<string>;
}

declare global {
    interface Window {
        electronAPI?: ElectronAPI;
    }
}

// Electron環境かどうかを判定
const isElectron = (): boolean => {
    return typeof window !== 'undefined' && !!window.electronAPI;
};

// ローカルストレージキー
const SETTINGS_KEY = 'ethicalReviewSettings';
const API_KEY_STORAGE = 'geminiApiKey';

// デフォルト設定（バックエンドUserSettingsに準拠）
const defaultSettings: Settings = {
    laboratory: {
        name: '善甫研究室',
        building: '総合研究棟B',
        room: '0911',
    },
    submission_destination: 'システム情報系',
    principal_investigator: {
        name: '善甫 啓一',
        affiliation: '筑波大学システム情報系',
        position: '准教授',
        email: '',
        phone: '',
    },
    ethics_committee: {
        name: '筑波大学人を対象とする倫理委員会',
        office: 'システム情報エリア支援室',
        phone: '029-853-4989',
    },
    budget: {
        source: '運営費交付金',
        project_name: '',
        reward_per_person: 800,
        reward_type: 'Amazonギフトカード（Eメールタイプ）',
        hourly_rate: 1000,
    },
    subInvestigators: [],
    llm: {
        provider: 'openai',
        apiKey: '',
    },
    // 互換性エイリアス
    labName: '善甫研究室',
    principalInvestigator: {
        name: '善甫 啓一',
        affiliation: '筑波大学システム情報系',
        position: '准教授',
        email: '',
        phone: '',
    },
    ethicsCommittee: '筑波大学人を対象とする倫理委員会',
    reward: {
        baseAmountPer60Min: 1000,
        roundingUnit: 100,
        minimumWage: 1074,
        prefecture: '茨城県',
    },
};

export interface UseSettingsReturn {
    settings: Settings;
    isLoading: boolean;
    error: string | null;
    updateSettings: (updates: Partial<Settings>) => Promise<void>;
    resetToDefaults: () => void;
    // APIキー管理
    apiKey: string;
    setApiKey: (key: string) => void;
    isApiKeySet: boolean;
}

export const useSettings = (): UseSettingsReturn => {
    const [settings, setSettings] = useState<Settings>(defaultSettings);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [apiKey, setApiKeyState] = useState('');

    // 設定の読み込み
    useEffect(() => {
        const loadSettings = async () => {
            try {
                setIsLoading(true);

                // Electron環境の場合はElectron APIから読み込み
                if (isElectron()) {
                    try {
                        const electronSettings = await window.electronAPI!.getSettings();
                        if (electronSettings) {
                            setSettings({ ...defaultSettings, ...electronSettings });
                            // APIキーも設定
                            if (electronSettings.llm?.apiKey) {
                                setApiKeyState(electronSettings.llm.apiKey);
                                setClientApiKey(electronSettings.llm.apiKey, electronSettings.llm.provider || 'openai');
                            }
                            console.log('Electron: 設定をファイルから読み込みました');
                        }
                    } catch (e) {
                        console.error('Electron: 設定の読み込みに失敗しました', e);
                    }
                }

                // ローカルストレージから読み込み（同期的、即座）
                const savedSettings = localStorage.getItem(SETTINGS_KEY);
                if (savedSettings) {
                    const parsed = JSON.parse(savedSettings);
                    setSettings(prev => ({ ...prev, ...parsed }));
                }

                // APIキーも読み込み
                const savedApiKey = localStorage.getItem(API_KEY_STORAGE);
                if (savedApiKey) {
                    setApiKeyState(savedApiKey);
                }

                setError(null);
            } catch (err) {
                setError('設定の読み込みに失敗しました');
                console.error(err);
            } finally {
                setIsLoading(false);
            }

            // サーバーから最新設定を取得（バックグラウンド、UI表示後に実行）
            getSettings()
                .then((serverSettings) => {
                    setSettings((current) => ({ ...current, ...serverSettings }));
                    console.log('サーバーから設定を取得しました');
                })
                .catch(() => {
                    console.log('サーバーに接続できません。ローカル設定を使用します。');
                });
        };

        loadSettings();
    }, []);

    // 設定の更新
    const updateSettings = useCallback(async (updates: Partial<Settings>) => {
        try {
            const newSettings = { ...settings, ...updates };
            setSettings(newSettings);

            // ローカルストレージに保存（同期的、即座に完了）
            localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings));

            // LLM設定が含まれていればAPIクライアントも更新
            if (updates.llm) {
                const apiKey = updates.llm.apiKey || settings.llm?.apiKey || '';
                const provider = updates.llm.provider || settings.llm?.provider || 'openai';
                if (apiKey) {
                    setClientApiKey(apiKey, provider);
                    setApiKeyState(apiKey);
                    localStorage.setItem(API_KEY_STORAGE, apiKey);
                }
            }

            // Electron環境の場合はElectron APIで保存（非ブロッキング）
            if (isElectron()) {
                window.electronAPI!.saveSettings(newSettings)
                    .then(() => console.log('Electron: 設定をファイルに保存しました'))
                    .catch((e) => console.error('Electron: 設定の保存に失敗しました', e));
            }

            // サーバーにも保存（非ブロッキング - 待たない）
            apiUpdateSettings(updates)
                .then(() => console.log('サーバーに設定を保存しました'))
                .catch(() => console.log('サーバーへの設定保存をスキップしました'));

            setError(null);
        } catch (err) {
            setError('設定の更新に失敗しました');
            throw err;
        }
    }, [settings]);

    // デフォルトにリセット
    const resetToDefaults = useCallback(() => {
        setSettings(defaultSettings);
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(defaultSettings));
    }, []);

    // APIキー設定
    const setApiKey = useCallback((key: string) => {
        setApiKeyState(key);
        localStorage.setItem(API_KEY_STORAGE, key);
        // APIクライアントにも設定
        const provider = settings.llm?.provider || 'openai';
        setClientApiKey(key, provider);
    }, [settings.llm?.provider]);

    return {
        settings,
        isLoading,
        error,
        updateSettings,
        resetToDefaults,
        apiKey,
        setApiKey,
        isApiKeySet: !!apiKey,
    };
};
