import { useState, useEffect, useCallback } from 'react';
import type { Settings } from '../types';
import { getSettings, updateSettings as apiUpdateSettings, setApiKey as setClientApiKey } from '../api/client';

const SETTINGS_KEY = 'ethicalReviewSettings';
const API_KEY_STORAGE = 'geminiApiKey';

const defaultSettings: Settings = {
    laboratory: {
        name: '善甫研究室',
        building: '総合研究棟B',
        room: '3M211',
    },
    submission_destination: 'システム情報系',
    principal_investigator: {
        name: '善甫 啓一',
        affiliation: '筑波大学 システム情報系',
        position: '准教授',
        email: 'zempo@iit.tsukuba.ac.jp',
        phone: '029-853-5338',
    },
    ethics_committee: {
        name: '筑波大学 システム情報系 研究倫理委員会',
        office: 'システム情報エリア支援室',
        phone: '029-853-4989',
    },
    budget: {
        source: '運営費交付金',
        project_name: '',
        reward_per_person: 800,
        reward_type: 'Amazonギフトカード（メールタイプ）',
        hourly_rate: 1000,
    },
    subInvestigators: [],
    llm: {
        provider: 'openai',
        apiKey: '',
    },
    labName: '善甫研究室',
    principalInvestigator: {
        name: '善甫 啓一',
        affiliation: '筑波大学 システム情報系',
        position: '准教授',
        email: 'zempo@iit.tsukuba.ac.jp',
        phone: '029-853-5338',
    },
    ethicsCommittee: '筑波大学 システム情報系 研究倫理委員会',
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
    apiKey: string;
    setApiKey: (key: string) => void;
    isApiKeySet: boolean;
}

export const useSettings = (): UseSettingsReturn => {
    const [settings, setSettings] = useState<Settings>(defaultSettings);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [apiKey, setApiKeyState] = useState('');

    useEffect(() => {
        const loadSettings = async () => {
            try {
                setIsLoading(true);

                const savedSettings = localStorage.getItem(SETTINGS_KEY);
                if (savedSettings) {
                    const parsed = JSON.parse(savedSettings);
                    setSettings((prev) => ({ ...prev, ...parsed }));
                }

                const savedApiKey = localStorage.getItem(API_KEY_STORAGE);
                if (savedApiKey) {
                    setApiKeyState(savedApiKey);
                }

                try {
                    const serverSettings = await getSettings();
                    setSettings((current) => ({ ...current, ...serverSettings }));
                } catch {
                    // The local web app can still open before the backend is ready.
                }

                setError(null);
            } catch (err) {
                setError('設定の読み込みに失敗しました');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        };

        loadSettings();
    }, []);

    const updateSettings = useCallback(async (updates: Partial<Settings>) => {
        try {
            const newSettings = { ...settings, ...updates };
            setSettings(newSettings);
            localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings));

            if (updates.llm) {
                const nextApiKey = updates.llm.apiKey || settings.llm?.apiKey || '';
                const provider = updates.llm.provider || settings.llm?.provider || 'openai';
                if (nextApiKey) {
                    setClientApiKey(nextApiKey, provider);
                    setApiKeyState(nextApiKey);
                    localStorage.setItem(API_KEY_STORAGE, nextApiKey);
                }
            }

            apiUpdateSettings(updates).catch(() => {
                console.log('Server settings update was skipped because the backend is unavailable.');
            });

            setError(null);
        } catch (err) {
            setError('設定の更新に失敗しました');
            throw err;
        }
    }, [settings]);

    const resetToDefaults = useCallback(() => {
        setSettings(defaultSettings);
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(defaultSettings));
    }, []);

    const setApiKey = useCallback((key: string) => {
        setApiKeyState(key);
        localStorage.setItem(API_KEY_STORAGE, key);
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
