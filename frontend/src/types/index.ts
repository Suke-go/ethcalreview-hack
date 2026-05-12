// frontend/src/types/index.ts
// 型定義

// 研究責任者情報 (Backend: InvestigatorSettings)
export interface Investigator {
    name: string;        // 氏名
    affiliation: string; // 所属
    position: string;    // 職名
    email: string;       // メールアドレス
    phone: string;       // 電話番号
}

// 研究室情報 (Backend: LaboratorySettings)
export interface LaboratorySettings {
    name: string;        // 研究室名
    building: string;    // 建物
    room: string;        // 部屋番号
}

// 予算設定 (Backend: BudgetSettings) - 構造をバックエンドに合わせる
export interface BudgetSettings {
    source: string;           // 予算種別
    project_name: string;     // プロジェクト名 (snake_case for backend)
    reward_per_person: number; // 一人あたり謝礼
    reward_type: string;      // 謝礼の種類
    hourly_rate: number;      // 時給換算 (60分あたり)
}

// 倫理委員会設定 (Backend: EthicsCommitteeSettings)
export interface EthicsCommitteeSettings {
    name: string;        // 委員会名
    office: string;      // 事務局
    phone: string;       // 電話番号
}

// LLM設定 (フロントエンド専用)
export interface LLMSettings {
    provider: 'openai' | 'gemini';
    apiKey: string;
    model?: string;
}

// アプリケーション設定 (Backend: UserSettings と整合性を保つ)
export interface Settings {
    laboratory: LaboratorySettings;
    submission_destination: string;
    principal_investigator: Investigator;
    ethics_committee: EthicsCommitteeSettings;
    budget: BudgetSettings;
    // フロントエンド専用フィールド
    subInvestigators?: Investigator[];
    llm?: LLMSettings;
    // 互換性のためのエイリアス
    labName?: string;              // laboratory.name のエイリアス
    principalInvestigator?: Investigator;  // principal_investigator のエイリアス
    ethicsCommittee?: string;      // ethics_committee.name のエイリアス
    reward?: {                     // budget から算出
        baseAmountPer60Min: number;
        roundingUnit: number;
        minimumWage?: number;
        prefecture?: string;
    };
}


// 研究計画解析リクエスト
export interface InvestigatorPreset {
    id: string;
    label: string;
    name: string;
    affiliation: string;
    position: string;
    email: string;
    tel: string;
    default_rooms: string[];
    default_budget_ids: string[];
    default_submission_preset_id: string;
    enabled: boolean;
}

export interface BudgetPreset {
    id: string;
    label: string;
    source: string;
    project_name: string;
    reward_per_person: number;
    reward_type: string;
    hourly_rate: number;
    enabled: boolean;
}

export interface RoomPreset {
    id: string;
    label: string;
    rooms: string[];
    enabled: boolean;
}

export interface SubmissionPreset {
    id: string;
    label: string;
    recipient: string;
    committee_name: string;
    office_name: string;
    office_tel: string;
    default_affiliation_label: string;
    domain_head_candidates?: { name: string; title?: string }[];
    enabled: boolean;
}

export interface PresetBundle {
    investigator_presets: InvestigatorPreset[];
    budget_presets: BudgetPreset[];
    room_presets: RoomPreset[];
    submission_presets: SubmissionPreset[];
}

export interface ValidationIssue {
    field: string;
    message: string;
    severity: 'error' | 'warning';
}

export interface AnalyzeRequest {
    researchPlan: string;        // 研究計画テキスト
}

// 研究計画解析結果（バックエンドのレスポンス形式に合わせる）
export interface AnalysisResult {
    research_title: string;
    research_purpose: string;
    research_method: string;
    target_participants: string;
    participant_count: number;
    participant_count_reason: string;
    age_range: string;
    selection_criteria: string;
    exclusion_criteria: string;
    risks: string[];
    risk_countermeasures: string[];
    duration_minutes: number;
    devices: string[];
    clarification_needed: boolean;
    clarification_questions: string[];
}

// フォーム入力データ
export interface FormData {
    research_plan?: string;
    followupAnswers?: Record<string, string>;

    // 基本情報
    title: string;
    principalInvestigator: Investigator;
    subInvestigators: Investigator[];

    // 研究内容
    purpose: string;
    background: string;
    methodology: string;

    // 対象者
    targetDescription: string;
    inclusionCriteria: string[];
    exclusionCriteria: string[];
    expectedParticipants: number;
    participantsJustification: string;
    recruitmentMethod: string;

    // 実験詳細
    procedures: string[];
    duration: number;
    location: string;
    devices: string[];

    // リスクと対策
    risks: string[];
    riskCountermeasures: string[];
    dataProtection: string;
    emergencyProcedures: string;

    // 謝礼
    rewardAmount: number;
    rewardRationale: string;

    // 同意関連
    consentWithdrawalProcedure: string;
    dataHandlingOnWithdrawal: string;
}

// 書類生成リクエスト
export interface GenerateRequest {
    formData: FormData;
    settings: Settings;
}

// 書類生成レスポンス
export interface GenerateResponse {
    sessionId: string;
    status: 'pending' | 'processing' | 'reviewing' | 'completed' | 'failed';
    documents?: GeneratedDocument[];
    reviewResult?: ReviewResult;
    downloadUrl?: string;
    error?: string;
}

// 生成された書類
export interface GeneratedDocument {
    type: 'application' | 'consent' | 'withdrawal' | 'implementation_plan' |
    'questionnaire' | 'script' | 'budget' | 'participant_list' | 'recruitment';
    name: string;
    previewUrl?: string;
}

// レビュー結果
export interface ReviewResult {
    agentAReview: AgentReview;
    agentBReview: AgentReview;
    finalStatus: 'approved' | 'needs_revision' | 'rejected';
    iterations: number;
}

// エージェントレビュー
export interface AgentReview {
    agent: 'A' | 'B';
    findings: ReviewFinding[];
    corrections?: string[];
    overallAssessment: string;
}

// レビュー指摘
export interface ReviewFinding {
    criteriaId: string;        // SR1, SR2, etc.
    severity: 'critical' | 'major' | 'minor';
    description: string;
    suggestion?: string;
}

// API設定状態
export interface ApiConfigState {
    apiKey: string;
    isValid: boolean;
    isValidating: boolean;
    error?: string;
}

// ステップステータス
export type StepStatus = 'pending' | 'running' | 'completed' | 'error';

// セッションステータス
export type SessionStatus = 'in_progress' | 'submitted' | 'rebuttal' | 'completed';

// セッション概要（一覧表示用）
export interface SessionSummary {
    sessionId: string;
    title: string | null;
    status: SessionStatus;
    currentStep: string;
    createdAt: string;
    updatedAt: string;
}

// Chain of Thoughtエントリ
export interface ChainOfThoughtEntry {
    timestamp: string;
    step: string;
    prompt?: string;
    response?: string;
    error?: string;
}

// ステップ詳細
export interface AnalyzeStepDetail {
    status: StepStatus;
    startedAt: string | null;
    completedAt: string | null;
    result: AnalysisResult | null;
    error: string | null;
    chainOfThought: ChainOfThoughtEntry[];
}

export interface ConfirmStepDetail {
    status: StepStatus;
    userEdits: Record<string, unknown>;
    confirmedAt: string | null;
}

export interface DocumentStatusDetail {
    status: StepStatus;
    path: string | null;
    error: string | null;
}

export interface GenerateStepDetail {
    status: StepStatus;
    startedAt: string | null;
    completedAt: string | null;
    documents: Record<string, DocumentStatusDetail>;
}

export interface ReviewStepDetail {
    status: StepStatus;
    startedAt: string | null;
    completedAt: string | null;
    agents: Record<string, { status: StepStatus; result: unknown }>;
}

export interface SubmitStepDetail {
    status: StepStatus;
    submittedAt: string | null;
    submissionNotes: string | null;
}

// セッションステップ
export interface SessionSteps {
    analyze: AnalyzeStepDetail;
    confirm: ConfirmStepDetail;
    generate: GenerateStepDetail;
    review: ReviewStepDetail;
    submit: SubmitStepDetail;
}

// Rebuttalラウンド
export interface RebuttalRound {
    roundNumber: number;
    createdAt: string;
    feedbackText: string;
    aiSuggestions: RebuttalSuggestions | null;
    userResponse: string | null;
    status: StepStatus;
}

// Rebuttal提案
export interface RebuttalSuggestion {
    field: string;
    originalValue: string;
    suggestedValue: string;
    reason: string;
}

export interface RebuttalSuggestions {
    suggestions: RebuttalSuggestion[];
    responseDraft: string;
}

// Rebuttal情報
export interface RebuttalInfo {
    enabled: boolean;
    rounds: RebuttalRound[];
}

// セッション詳細
export interface SessionDetail {
    sessionId: string;
    title: string | null;
    status: SessionStatus;
    currentStep: string;
    createdAt: string;
    updatedAt: string;
    researchPlan: {
        rawInput: string;
        analyzedAt: string | null;
    };
    steps: SessionSteps;
    rebuttal: RebuttalInfo;
}

