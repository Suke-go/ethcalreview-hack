// frontend/src/api/client.ts
// APIクライアント

import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type {
    Settings,
    AnalysisResult,
    FormData,
    GenerateResponse,
    ReviewResult,
    SessionSummary,
    SessionDetail,
    RebuttalSuggestions,
    SessionStatus,
} from '../types';

// APIのベースURL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// タイムアウト設定
const API_TIMEOUT_LONG = 600000;  // 10分（書類生成などLLM処理用）
const API_TIMEOUT_SHORT = 5000;   // 5秒（設定取得・保存など軽量操作用）

// Axiosインスタンスの作成
const createApiClient = (apiKey?: string, provider: string = 'openai', timeout: number = API_TIMEOUT_LONG): AxiosInstance => {
    const client = axios.create({
        baseURL: API_BASE_URL,
        timeout: timeout,
        headers: {
            'Content-Type': 'application/json',
        },
    });


    // APIキーとプロバイダーのインターセプター
    client.interceptors.request.use((config) => {
        if (apiKey) {
            config.headers['X-API-Key'] = apiKey;
        }
        config.headers['X-LLM-Provider'] = provider;
        return config;
    });

    // エラーハンドリングインターセプター
    client.interceptors.response.use(
        (response) => response,
        (error: AxiosError) => {
            if (error.response) {
                const status = error.response.status;
                const data = error.response.data as { detail?: string };

                switch (status) {
                    case 401:
                        throw new Error('APIキーが無効です');
                    case 429:
                        throw new Error('レート制限に達しました。しばらく待ってから再試行してください');
                    case 500:
                        throw new Error('サーバーエラーが発生しました');
                    default:
                        throw new Error(data.detail || 'エラーが発生しました');
                }
            } else if (error.request) {
                throw new Error('サーバーに接続できません');
            }
            throw error;
        }
    );

    return client;
};

// デフォルトクライアント（長い処理用）
let defaultClient = createApiClient();

// 軽量操作用クライアント（短いタイムアウト）
const fastClient = createApiClient(undefined, 'openai', API_TIMEOUT_SHORT);

// APIキーとプロバイダー設定
export const setApiKey = (apiKey: string, provider: string = 'openai'): void => {
    defaultClient = createApiClient(apiKey, provider);
};

// 設定API（短いタイムアウトを使用）

export const getSettings = async (): Promise<Settings> => {
    const response = await fastClient.get<Settings>('/api/settings');
    return response.data;
};

export const updateSettings = async (settings: Partial<Settings>): Promise<Settings> => {
    const response = await fastClient.put<Settings>('/api/settings', settings);
    return response.data;
};

export interface RewardCalculationRequest {
    durationMinutes: number;
}

export interface RewardCalculationResponse {
    recommendedAmount: number;
    minimumWage: number;
    isAboveMinimumWage: boolean;
    rationale: string;
}

export const calculateReward = async (
    request: RewardCalculationRequest
): Promise<RewardCalculationResponse> => {
    const response = await defaultClient.post<RewardCalculationResponse>(
        '/api/settings/reward-calculation',
        request
    );
    return response.data;
};

// 研究計画解析API

export interface AnalyzeRequestPayload {
    researchPlan: string;
}

export const analyzeResearchPlan = async (
    researchPlan: string
): Promise<AnalysisResult> => {
    const response = await defaultClient.post<AnalysisResult>('/api/analyze', {
        researchPlan,
    });
    return response.data;
};

// 書類生成API

// バックエンドレスポンス型 (snake_case)
interface GenerateResponseRaw {
    session_id: string;
    status: string;
    documents_generated: string[];
}

export const generateDocuments = async (
    formData: FormData
): Promise<GenerateResponse> => {
    const response = await defaultClient.post<GenerateResponseRaw>('/api/generate', {
        form_data: formData,  // Changed from formData to form_data (snake_case)
    });

    // snake_case → camelCase マッピング
    return {
        sessionId: response.data.session_id,
        status: response.data.status as GenerateResponse['status'],
    };
};

// 生成状態確認API

export const getGenerationStatus = async (
    sessionId: string
): Promise<GenerateResponse> => {
    const response = await defaultClient.get<GenerateResponse>(
        `/api/generate/status/${sessionId}`
    );
    return response.data;
};

// ダウンロードURL取得

export const getDownloadUrl = (sessionId: string): string => {
    return `${API_BASE_URL}/api/generate/download/${sessionId}`;
};

// レビューAPI

export const requestReview = async (
    sessionId: string
): Promise<ReviewResult> => {
    const response = await defaultClient.post<ReviewResult>('/api/review', {
        sessionId,
    });
    return response.data;
};

// ヘルスチェック（短いタイムアウト）

export const checkHealth = async (): Promise<{ status: string }> => {
    const response = await fastClient.get<{ status: string }>('/health');
    return response.data;
};

// ========================================
// セッション管理API
// ========================================

// セッション作成
export const createSession = async (researchPlan: string): Promise<SessionDetail> => {
    const response = await defaultClient.post<SessionDetail>('/api/sessions', {
        researchPlan,
    });
    return response.data;
};

// セッション一覧取得（短いタイムアウト）
export const getSessions = async (status?: SessionStatus): Promise<SessionSummary[]> => {
    const params = status ? { status } : {};
    const response = await fastClient.get<SessionSummary[]>('/api/sessions', { params });
    return response.data;
};

// セッション詳細取得（短いタイムアウト）
export const getSession = async (sessionId: string): Promise<SessionDetail> => {
    const response = await fastClient.get<SessionDetail>(`/api/sessions/${sessionId}`);
    return response.data;
};

// セッション更新
export const updateSession = async (
    sessionId: string,
    updates: { title?: string; status?: SessionStatus; userEdits?: Record<string, unknown> }
): Promise<SessionDetail> => {
    const response = await defaultClient.put<SessionDetail>(`/api/sessions/${sessionId}`, updates);
    return response.data;
};

// セッション削除
export const deleteSession = async (sessionId: string): Promise<void> => {
    await defaultClient.delete(`/api/sessions/${sessionId}`);
};

// セッション再開
export const resumeSession = async (sessionId: string): Promise<{
    message: string;
    sessionId: string;
    currentStep: string;
    chainOfThoughtCount: number;
}> => {
    const response = await defaultClient.post(`/api/sessions/${sessionId}/resume`);
    return response.data;
};

// ========================================
// Rebuttal API
// ========================================

// Rebuttal作成（指摘事項入力）
export const createRebuttal = async (
    sessionId: string,
    feedbackText: string
): Promise<{
    roundNumber: number;
    feedbackText: string;
    suggestions: RebuttalSuggestions['suggestions'];
    responseDraft: string;
    status: string;
}> => {
    const response = await defaultClient.post(`/api/rebuttal/${sessionId}`, {
        feedbackText,
    });
    return response.data;
};

// Rebuttalラウンド一覧
export const getRebuttalRounds = async (sessionId: string): Promise<{
    roundNumber: number;
    feedbackText: string;
    status: string;
    createdAt: string;
    hasSuggestions: boolean;
}[]> => {
    const response = await defaultClient.get(`/api/rebuttal/${sessionId}/rounds`);
    return response.data;
};

// Rebuttal適用
export const applyRebuttal = async (
    sessionId: string,
    roundNumber: number,
    userResponse: string,
    acceptedSuggestions: number[] = []
): Promise<{ message: string; roundNumber: number; acceptedCount: number }> => {
    const response = await defaultClient.post(
        `/api/rebuttal/${sessionId}/rounds/${roundNumber}/apply`,
        { userResponse, acceptedSuggestions }
    );
    return response.data;
};

export { createApiClient };

