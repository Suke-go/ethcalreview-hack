// frontend/src/api/client.ts
// APIクライアント

import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type {
    Settings,
    AnalysisResult,
    FormData as ResearchFormData,
    GenerateResponse,
    ReviewResult,
    SessionSummary,
    SessionDetail,
    RebuttalSuggestions,
    SessionStatus,
    PresetBundle,
} from '../types';

// APIのベースURL
//   優先順位:
//   1. Tauri ランタイム内なら sidecar の固定ポート (src-tauri/src/lib.rs の BACKEND_PORT と一致させる)
//   2. VITE_API_URL 環境変数 (開発時 frontend/.env.development や CI で上書き)
//   3. 同一オリジン("") — FastAPI 静的配信 / Web ホスティング時のフォールバック
function resolveApiBaseUrl(): string {
    if (typeof window !== 'undefined') {
        // Tauri 2.x は __TAURI_INTERNALS__、Tauri 1.x は __TAURI__ を window に注入
        const w = window as unknown as Record<string, unknown>;
        if ('__TAURI_INTERNALS__' in w || '__TAURI__' in w) {
            return 'http://127.0.0.1:17500';
        }
    }
    return (import.meta.env.VITE_API_URL as string | undefined) ?? '';
}

export const API_BASE_URL = resolveApiBaseUrl();

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

export const getPresets = async (): Promise<PresetBundle> => {
    const response = await fastClient.get<PresetBundle>('/api/settings/presets');
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
    formData: ResearchFormData
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

export interface IngestedDocument {
    filename: string;
    content_type: string;
    text: string;
    warnings: string[];
}

export interface IngestResponse {
    documents: IngestedDocument[];
    combined_text: string;
    warnings: string[];
}

export const ingestStudyDocuments = async (
    files: File[]
): Promise<IngestResponse> => {
    const payload = new globalThis.FormData();
    files.forEach((file) => payload.append('files', file));
    const response = await defaultClient.post<IngestResponse>('/api/ingest/documents', payload, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
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

// Tauri ランタイムかどうかを判定 (resolveApiBaseUrl と同じ判定方法)
const isTauriRuntime = (): boolean => {
    if (typeof window === 'undefined') return false;
    const w = window as unknown as Record<string, unknown>;
    return '__TAURI_INTERNALS__' in w || '__TAURI__' in w;
};

/**
 * ZIP ファイルをダウンロードする (環境ごとに動作が異なる):
 *
 *  - **ブラウザ**: Blob として取得し `<a download>` で保存ダイアログを発火。
 *  - **Tauri**: WebView2 / WKWebView がプログラム的な `<a download>` クリックを
 *    silent に drop するため、まずバックエンドの download エンドポイントを叩いて
 *    `{app_data}/output/{session_id}/ethics_documents.zip` をディスクに作らせ、
 *    Rust 側コマンド `save_zip_to_downloads` で Downloads フォルダにコピーして
 *    Explorer / Finder で reveal する。
 *
 * 戻り値: Tauri モード時のみ保存先パス。ブラウザモードでは undefined。
 */
export const downloadDocumentsZip = async (
    sessionId: string,
    filename: string = 'ethics_documents.zip'
): Promise<string | undefined> => {
    if (isTauriRuntime()) {
        // バックエンドに ZIP を生成・ディスク書き込みさせる。
        // レスポンス本体は破棄して構わない (Rust が disk から読む)。
        const response = await defaultClient.get(
            `/api/generate/download/${sessionId}`,
            { responseType: 'blob' }
        );
        if (response.status !== 200) {
            throw new Error(`backend returned status ${response.status}`);
        }
        const { invoke } = await import('@tauri-apps/api/core');
        const savedPath = await invoke<string>('save_zip_to_downloads', {
            sessionId,
            suggestedFilename: filename,
        });
        return savedPath;
    }

    // ブラウザ: Blob → <a download> で保存ダイアログ
    const response = await defaultClient.get<Blob>(
        `/api/generate/download/${sessionId}`,
        { responseType: 'blob' }
    );
    const blobUrl = URL.createObjectURL(response.data);
    try {
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        a.rel = 'noopener';
        document.body.appendChild(a);
        a.click();
        a.remove();
    } finally {
        setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
    }
    return undefined;
};

// 再フォーマット適用API（保存済みコンテキストから公式書類のみ再レンダリング）

export interface ReformatResult {
    sessionId: string;
    status: string;
    regenerated: string[];
    errors: string[];
    issues: Array<Record<string, unknown>>;
    assumptions: Array<Record<string, unknown>>;
}

interface ReformatResponseRaw {
    session_id: string;
    status: string;
    regenerated: string[];
    errors: string[];
    issues: Array<Record<string, unknown>>;
    assumptions: Array<Record<string, unknown>>;
}

export const reformatDocuments = async (
    sessionId: string
): Promise<ReformatResult> => {
    const response = await defaultClient.post<ReformatResponseRaw>(
        `/api/generate/reformat/${sessionId}`
    );
    const d = response.data;
    return {
        sessionId: d.session_id,
        status: d.status,
        regenerated: d.regenerated ?? [],
        errors: d.errors ?? [],
        issues: d.issues ?? [],
        assumptions: d.assumptions ?? [],
    };
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

