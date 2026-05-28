// frontend/src/App.tsx

import { useState, useCallback, useEffect } from 'react';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './styles/global.css';
import './App.css';

import { Header } from './components/layout/Header';
import { Stepper, type Step } from './components/layout/Stepper';
import { ResearchPlanInput } from './components/ResearchPlanInput';
import { SettingsPage } from './components/SettingsPage';
import { SessionList } from './components/SessionList';
import { RebuttalForm } from './components/RebuttalForm';
import { Button } from './components/common/Button';
import { Input, Textarea } from './components/common/Input';
import { ProgressStepper } from './components/ProgressStepper';
import { OnboardingTutorial } from './components/OnboardingTutorial';
import { useOnboarding } from './hooks/useOnboarding';
import { useSettings } from './hooks/useSettings';
import { useSSE } from './hooks/useSSE';
import { setApiKey, getSession, downloadDocumentsZip, reformatDocuments, getPresets, API_BASE_URL } from './api/client';
import type { AnalysisResult, FormData, SessionDetail, PresetBundle, ValidationIssue } from './types';


// ビュータイプ
type ViewType = 'sessions' | 'new' | 'rebuttal';

// 申請書設定（生成前にユーザーが入力する項目）
interface ApplicationFormConfig {
  principalInvestigatorPresetId?: string;
  submissionPresetId?: string;
  budgetPresetId?: string;
  roomPresetId?: string;
  domainName?: string;
  domainHeadName?: string;
  researchPeriodStartText?: string;
  researchPeriodEndText?: string;
  rewardUnit?: string;
  // 2. 申請種別・類似申請
  applicationType: 'new' | 'change';
  previousApprovalNumber?: string;
  similarApplicationExists: boolean;
  similarApplicationDetails?: string;
  // 3. 実施分担者
  subInvestigators: { affiliation: string; position: string; name: string; tel?: string }[];
  // 5. 実施施設
  facilityType: 'a' | 'b' | 'c';
  facilityName: string;
  externalFacilityName?: string;
  externalOrgLeader?: string;
  tsukubaRole?: string;
  // 7. 費用の出所
  fundingSource: string;
  fundingPI: string;
  fundingProjectName: string;
  // 9. 倫理的配慮
  genomeRelated: boolean;
  conflictOfInterest: boolean;
  conflictOfInterestPartner?: string;
  videoRecording: boolean;
  recordingTypes?: string;
  recordingPublicRelease: boolean;
  invasiveness: boolean;
  invasivenessDetails?: string;
  // 10. データ保存
  dataTypes?: string;  // AI推察
  retentionPeriod: '10years' | 'less';
  retentionReason?: string;
  hasAnonymization: boolean;
  hasCorrespondenceTable: boolean;
  storageLocation: string;
  dataManager: string;
  managementMethod: string;
  disposalMethod: string;
}

const defaultAppConfig: ApplicationFormConfig = {
  applicationType: 'new',
  domainName: 'システム情報系',
  domainHeadName: '矢野 博明',
  researchPeriodStartText: '研究倫理委員会承認後',
  researchPeriodEndText: '',
  rewardUnit: '回',
  similarApplicationExists: false,
  subInvestigators: [],
  facilityType: 'a',
  facilityName: '3M211',
  fundingSource: '(教研)教研-重点-人材養成機能強化経費',  // lab_defaults.json から
  fundingPI: '善甫 啓一',  // lab_defaults.json から
  fundingProjectName: '',
  genomeRelated: false,
  conflictOfInterest: false,
  videoRecording: false,
  recordingPublicRelease: false,
  invasiveness: false,
  dataTypes: '',
  retentionPeriod: '10years',
  hasAnonymization: true,
  hasCorrespondenceTable: true,
  storageLocation: '研究室(3M211)にて管理されたノートパソコン',  // lab_defaults.json から
  dataManager: '善甫 啓一',  // lab_defaults.json から
  managementMethod: 'ノートパソコンの使用を関係者のみとし、結果の解析はネットに接続されない状態で行う。また、暗号化およびパスワード保護を用いることによりデータを保護する。同意書等の紙媒体については研究室(3M211)の鍵付き棚に保管し、鍵は管理責任者が管理する。',
  disposalMethod: '研究対象者からの実験に関するデータの破棄が申請された場合は直ちに研究対象者のデータを破棄する。また、研究成果発表から10年が経過した場合、データの保存しているSSDを初期化し、データの復元をできないようにして処分する。同意書等の紙媒体についてはシュレッダーにかけた上で破棄し、復元できないように処分する',
};

const DEFAULT_ZEMPO_LAB_CONDUCTOR_TEL = '029-853-6185';

const extractValidationIssues = (detail: unknown): ValidationIssue[] => {
  if (!detail || typeof detail !== 'object') {
    return [];
  }
  const payload = detail as { issues?: ValidationIssue[]; detail?: { issues?: ValidationIssue[] } };
  if (Array.isArray(payload.issues)) {
    return payload.issues;
  }
  if (payload.detail && Array.isArray(payload.detail.issues)) {
    return payload.detail.issues;
  }
  return [];
};

// ステップ定義
const steps: Step[] = [
  { id: 'input', label: '研究計画入力', description: 'テキストまたはファイルで入力' },
  { id: 'review', label: '内容確認', description: 'AI解析結果を確認・編集' },
  { id: 'generate', label: '書類生成', description: '倫理審査書類を自動生成' },
  { id: 'download', label: 'ダウンロード', description: 'ZIPでまとめてダウンロード' },
];

function App() {
  const { settings, updateSettings, apiKey, isApiKeySet } = useSettings();
  const [currentStep, setCurrentStep] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [generatedSessionId, setGeneratedSessionId] = useState<string | null>(null);
  const [reformatting, setReformatting] = useState(false);
  const [presets, setPresets] = useState<PresetBundle | null>(null);
  const [generationIssues, setGenerationIssues] = useState<ValidationIssue[]>([]);
  const [rawResearchInput, setRawResearchInput] = useState('');
  const [followupAnswers, setFollowupAnswers] = useState<Record<string, string>>({});

  // 申請書設定（生成前にユーザーが入力）
  const [appConfig, setAppConfig] = useState<ApplicationFormConfig>(defaultAppConfig);

  // ビュー管理
  const [currentView, setCurrentView] = useState<ViewType>('sessions');
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [, setSelectedSession] = useState<SessionDetail | null>(null);


  // SSE for research plan analysis
  const analyzeSSE = useSSE<AnalysisResult>();

  // 解析結果の個別フィールド更新
  const updateAnalysisField = useCallback(<K extends keyof AnalysisResult>(
    field: K,
    value: AnalysisResult[K]
  ) => {
    setAnalysisResult(prev => prev ? { ...prev, [field]: value } : null);
  }, []);

  // SSE for document generation
  const generateSSE = useSSE<{ sessionId: string }>();

  // Onboarding
  const { showOnboarding, setShowOnboarding } = useOnboarding();

  // 書類生成（非SSE版は削除、SSEを使用）

  // 研究計画解析ハンドラ (SSE版)
  useEffect(() => {
    getPresets()
      .then(setPresets)
      .catch((error) => {
        console.warn('Failed to load presets', error);
      });
  }, []);

  const fieldIssues = useCallback((field: string) => (
    generationIssues.filter((issue) => issue.field === field)
  ), [generationIssues]);

  const renderFieldIssues = useCallback((field: string) => {
    const issues = fieldIssues(field);
    if (issues.length === 0) {
      return null;
    }
    return (
      <div className="field-issues">
        {issues.map((issue, index) => (
          <p key={`${field}-${index}`} className={`field-issue field-issue-${issue.severity}`}>
            {issue.message}
          </p>
        ))}
      </div>
    );
  }, [fieldIssues]);

  const applyInvestigatorPreset = useCallback((presetId: string) => {
    const preset = presets?.investigator_presets.find((item) => item.id === presetId);
    if (!preset) return;
    const roomPreset = presets?.room_presets.find((item) => (
      item.rooms.join('|') === (preset.default_rooms ?? []).join('|')
    ));
    const budgetPreset = presets?.budget_presets.find((item) => item.id === preset.default_budget_ids?.[0]);
    const submissionPreset = presets?.submission_presets.find((item) => item.id === preset.default_submission_preset_id);
    const domainHead = submissionPreset?.domain_head_candidates?.[0]?.name;
    const rooms = roomPreset?.rooms ?? preset.default_rooms ?? [];
    setAppConfig((prev) => ({
      ...prev,
      principalInvestigatorPresetId: preset.id,
      submissionPresetId: submissionPreset?.id ?? prev.submissionPresetId,
      budgetPresetId: budgetPreset?.id ?? prev.budgetPresetId,
      roomPresetId: roomPreset?.id ?? prev.roomPresetId,
      facilityName: rooms.length ? rooms.join(', ') : prev.facilityName,
      fundingSource: budgetPreset?.source || prev.fundingSource,
      fundingPI: preset.name || prev.fundingPI,
      fundingProjectName: budgetPreset?.project_name || prev.fundingProjectName,
      storageLocation: rooms[0] ? `研究室(${rooms[0]})` : prev.storageLocation,
      dataManager: preset.name || prev.dataManager,
      domainName: submissionPreset?.label || prev.domainName,
      domainHeadName: domainHead || prev.domainHeadName,
      subInvestigators: prev.subInvestigators.map((inv) => ({
        ...inv,
        tel: inv.tel || DEFAULT_ZEMPO_LAB_CONDUCTOR_TEL,
      })),
    }));
  }, [presets]);

  const applyBudgetPreset = useCallback((presetId: string) => {
    const preset = presets?.budget_presets.find((item) => item.id === presetId);
    if (!preset) return;
    setAppConfig((prev) => ({
      ...prev,
      budgetPresetId: preset.id,
      fundingSource: preset.source || prev.fundingSource,
      fundingProjectName: preset.project_name || prev.fundingProjectName,
    }));
  }, [presets]);

  const applyRoomPreset = useCallback((presetId: string) => {
    const preset = presets?.room_presets.find((item) => item.id === presetId);
    if (!preset) return;
    setAppConfig((prev) => ({
      ...prev,
      roomPresetId: preset.id,
      facilityName: preset.rooms.join(', '),
      storageLocation: preset.rooms[0] ? `研究室(${preset.rooms[0]})` : prev.storageLocation,
    }));
  }, [presets]);

  const handleAnalyze = useCallback(async (plan: string) => {
    if (!apiKey) {
      toast.error('APIキーを設定してください');
      return;
    }

    setIsAnalyzing(true);
    setAnalyzeError(null);
    setRawResearchInput(plan);
    setFollowupAnswers({});
    analyzeSSE.reset();

    const provider = settings.llm?.provider || 'gemini';
    const model = settings.llm?.model || (provider === 'gemini' ? 'gemini-2.5-flash' : 'gpt-5-mini');

    await analyzeSSE.start(`${API_BASE_URL}/api/analyze/stream`, {
      headers: {
        'X-API-Key': apiKey,
        'X-LLM-Provider': provider,
        'X-LLM-Model': model,
      },
      body: { research_plan: plan },
      onResult: (result) => {
        setAnalysisResult(result as AnalysisResult);
        setCurrentStep(1);
        setIsAnalyzing(false);
        toast.success('研究計画の解析が完了しました！');
      },
      onError: (error) => {
        setAnalyzeError(error);
        setIsAnalyzing(false);
        toast.error(`解析エラー: ${error}`);
      },
    });
  }, [apiKey, settings.llm?.provider, settings.llm?.model, analyzeSSE]);

  // 書類生成ハンドラ
  const handleGenerate = useCallback(async () => {
    if (!analysisResult) return;

    // 謝礼計算: 設定の単価 × 所要時間 (budget.hourly_rate または reward.baseAmountPer60Min)
    const hourlyRate = settings.budget?.hourly_rate ?? settings.reward?.baseAmountPer60Min ?? 1000;
    const rewardAmount = Math.round(hourlyRate * (analysisResult.duration_minutes / 60));

    const formData: FormData = {
      research_plan: rawResearchInput,
      followupAnswers,
      title: analysisResult.research_title,
      principalInvestigator: settings.principal_investigator ?? settings.principalInvestigator!,
      subInvestigators: settings.subInvestigators ?? [],
      purpose: analysisResult.research_purpose,
      background: '',
      methodology: analysisResult.research_method,
      targetDescription: analysisResult.target_participants,
      inclusionCriteria: [analysisResult.selection_criteria],
      exclusionCriteria: [analysisResult.exclusion_criteria],
      expectedParticipants: analysisResult.participant_count,
      participantsJustification: analysisResult.participant_count_reason,
      recruitmentMethod: '',
      procedures: [analysisResult.research_method],
      duration: analysisResult.duration_minutes,
      location: '',
      devices: analysisResult.devices,
      risks: analysisResult.risks,
      riskCountermeasures: analysisResult.risk_countermeasures,
      dataProtection: '',
      emergencyProcedures: '',
      rewardAmount: rewardAmount,
      rewardRationale: `所要時間${analysisResult.duration_minutes}分に基づく計算`,
      consentWithdrawalProcedure: '',
      dataHandlingOnWithdrawal: '',
    };

    setCurrentStep(2);
    setGenerationIssues([]);
    toast.info('書類生成を開始しました。しばらくお待ちください...');
    generateSSE.reset();

    const provider = settings.llm?.provider || 'gemini';
    const model = settings.llm?.model || (provider === 'gemini' ? 'gemini-2.5-flash' : 'gpt-5-mini');

    await generateSSE.start(`${API_BASE_URL}/api/generate/stream`, {
      headers: {
        'X-API-Key': apiKey,
        'X-LLM-Provider': provider,
        'X-LLM-Model': model,
      },
      body: {
        form_data: formData,
        app_config: appConfig,  // 申請書設定を追加
      },
      onResult: (result) => {
        const res = result as { sessionId?: string; session_id?: string };
        const sessionId = res.sessionId || res.session_id;
        if (!sessionId) {
          toast.error('生成は完了しましたが、セッションIDを取得できませんでした。セッション一覧から開き直してください。');
          setCurrentStep(1);
          return;
        }
        setGeneratedSessionId(sessionId);
        setCurrentStep(3);
        toast.success('書類生成が完了しました！');
      },
      onError: (error, detail) => {
        setGenerationIssues(extractValidationIssues(detail));
        toast.error(`書類生成エラー: ${error}`);
        setCurrentStep(1); // 確認画面に戻る
      },
    });
  }, [analysisResult, settings, apiKey, appConfig, generateSSE, rawResearchInput, followupAnswers]);

  // セッション選択ハンドラ
  const handleSelectSession = useCallback(async (sessionId: string) => {
    try {
      const session = await getSession(sessionId);
      setSelectedSessionId(sessionId);
      setSelectedSession(session);

      // セッションの状態に応じてビューを切り替え
      if (session.status === 'rebuttal') {
        setCurrentView('rebuttal');
      } else {
        setCurrentView('new');

        // ステップの完了状態に基づいて適切なステップに復元
        if (session.steps.generate.status === 'completed') {
          // 書類生成完了 → ダウンロード画面
          if (session.steps.analyze.result) {
            setAnalysisResult(session.steps.analyze.result as AnalysisResult);
          }
          setGeneratedSessionId(sessionId);
          setCurrentStep(3);
          toast.success('書類は既に生成済みです。ダウンロード可能です。');
        } else if (session.steps.analyze.result) {
          // 解析完了 → 確認画面
          setAnalysisResult(session.steps.analyze.result as AnalysisResult);
          setCurrentStep(1);
        } else {
          // 未解析 → 入力画面
          setCurrentStep(0);
        }
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'セッションの読み込みに失敗しました');
    }
  }, []);


  // 新規作成ハンドラ
  const handleCreateNew = useCallback(() => {
    setCurrentView('new');
    setSelectedSessionId(null);
    setSelectedSession(null);
    setAnalysisResult(null);
    setRawResearchInput('');
    setFollowupAnswers({});
    setCurrentStep(0);
  }, []);

  // セッション一覧に戻る
  const handleBackToSessions = useCallback(() => {
    setCurrentView('sessions');
    setSelectedSessionId(null);
    setSelectedSession(null);
  }, []);

  return (
    <div className="app">
      <Header
        apiKey={apiKey}
        onSettingsClick={() => setShowSettings(true)}
      />

      <main className="app-main">
        <div className="container">
          {/* セッション一覧ビュー */}
          {currentView === 'sessions' && (
            <SessionList
              onSelectSession={handleSelectSession}
              onCreateNew={handleCreateNew}
            />
          )}

          {/* Rebuttalビュー */}
          {currentView === 'rebuttal' && selectedSessionId && (
            <div>
              <button className="back-button" onClick={handleBackToSessions}>
                ← セッション一覧に戻る
              </button>
              <RebuttalForm
                sessionId={selectedSessionId}
                onComplete={handleBackToSessions}
              />
            </div>
          )}

          {/* 新規作成 / 既存セッション編集ビュー */}
          {currentView === 'new' && (
            <>
              <button className="back-button" onClick={handleBackToSessions}>
                ← セッション一覧に戻る
              </button>

              <Stepper
                steps={steps}
                currentStep={currentStep}
                onStepClick={(step) => step < currentStep && setCurrentStep(step)}
              />

              {/* 初期画面: APIキー未設定時の警告 */}
              {!isApiKeySet && currentStep === 0 && (
                <div className="api-key-warning">
                  <div className="warning-content">
                    <div className="warning-icon">🔑</div>
                    <div className="warning-text">
                      <h3>APIキーが設定されていません</h3>
                      <p>Gemini APIキーを設定してください。研究計画の解析と書類生成に必要です。</p>
                    </div>
                    <Button
                      variant="primary"
                      onClick={() => setShowSettings(true)}
                    >
                      APIキーを設定
                    </Button>
                  </div>
                </div>
              )}

              {/* ステップ1: 研究計画入力 */}
              {currentStep === 0 && (
                <>
                  <ResearchPlanInput
                    onAnalyze={handleAnalyze}
                    isAnalyzing={isAnalyzing}
                    error={analyzeError || undefined}
                  />

                  {/* SSE進捗表示 */}
                  {(analyzeSSE.status !== 'idle') && (
                    <ProgressStepper
                      events={analyzeSSE.progress}
                      status={analyzeSSE.status}
                      error={analyzeSSE.error}
                    />
                  )}
                </>
              )}

              {/* ステップ2: 内容確認・編集 */}
              {currentStep === 1 && analysisResult && (
                <div className="review-section">
                  <div className="review-header">
                    <h2>🔍 AI解析結果の確認</h2>
                    <p>以下の内容を確認・編集してください。「書類生成」をクリックすると、マルチエージェントによるレビューと書類生成が開始されます。</p>
                  </div>

                  {generationIssues.length > 0 && (
                    <div className="validation-summary">
                      <h3>生成前に修正が必要な項目があります</h3>
                      {generationIssues.map((issue, index) => (
                        <p key={`${issue.field}-${index}`} className={`validation-item validation-item-${issue.severity}`}>
                          <strong>{issue.field}</strong>: {issue.message}
                        </p>
                      ))}
                    </div>
                  )}

                  {analysisResult.clarification_questions.length > 0 && (
                    <div className="followup-panel">
                      <h3>AIが確認したい項目</h3>
                      <p>
                        不明な項目はここで補足できます。空欄のままでも生成は試せますが、研究期間・責任者・所属長・謝金財源などの必須項目は別途入力が必要です。
                      </p>
                      {analysisResult.clarification_questions.map((question, index) => {
                        const key = `q_${index + 1}`;
                        return (
                          <div className="followup-question" key={key}>
                            <label>{question}</label>
                            <Textarea
                              value={followupAnswers[key] || ''}
                              onChange={(e) => setFollowupAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                              rows={2}
                              placeholder="回答・補足を入力"
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="review-grid">
                    {presets && (
                      <div className="review-card preset-card">
                        <h3>プリセット</h3>
                        <div className="review-field">
                          <label>研究責任者</label>
                          <select
                            className="input"
                            value={appConfig.principalInvestigatorPresetId || ''}
                            onChange={(e) => applyInvestigatorPreset(e.target.value)}
                          >
                            <option value="">選択してください</option>
                            {presets.investigator_presets.filter((preset) => preset.enabled).map((preset) => (
                              <option key={preset.id} value={preset.id}>{preset.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="review-field">
                          <label>提出先</label>
                          <select
                            className="input"
                            value={appConfig.submissionPresetId || ''}
                            onChange={(e) => {
                              const preset = presets.submission_presets.find((item) => item.id === e.target.value);
                              setAppConfig(prev => ({
                                ...prev,
                                submissionPresetId: e.target.value,
                                domainName: preset?.label || prev.domainName,
                                domainHeadName: preset?.domain_head_candidates?.[0]?.name || prev.domainHeadName,
                              }));
                            }}
                          >
                            <option value="">選択してください</option>
                            {presets.submission_presets.filter((preset) => preset.enabled).map((preset) => (
                              <option key={preset.id} value={preset.id}>{preset.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="review-field">
                          <label>予算</label>
                          <select
                            className="input"
                            value={appConfig.budgetPresetId || ''}
                            onChange={(e) => applyBudgetPreset(e.target.value)}
                          >
                            <option value="">選択してください</option>
                            {presets.budget_presets.filter((preset) => preset.enabled).map((preset) => (
                              <option key={preset.id} value={preset.id}>{preset.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="review-field">
                          <label>部屋・実施場所</label>
                          <select
                            className="input"
                            value={appConfig.roomPresetId || ''}
                            onChange={(e) => applyRoomPreset(e.target.value)}
                          >
                            <option value="">選択してください</option>
                            {presets.room_presets.filter((preset) => preset.enabled).map((preset) => (
                              <option key={preset.id} value={preset.id}>{preset.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )}

                    <div className="review-card">
                      <h3>申請種別・類似申請（申請書 2項）</h3>
                      <div className="review-field">
                        <label>研究等を行う期間</label>
                        <div className="period-row">
                          <Input
                            value={appConfig.researchPeriodStartText || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, researchPeriodStartText: e.target.value }))}
                            placeholder="研究倫理委員会承認後"
                          />
                          <span>～</span>
                          <Input
                            value={appConfig.researchPeriodEndText || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, researchPeriodEndText: e.target.value }))}
                            placeholder="例: 2027年3月31日"
                          />
                        </div>
                        {renderFieldIssues('research.period_end_text')}
                      </div>
                      <div className="review-field">
                        <label>関係組織の長</label>
                        <div className="period-row">
                          <Input
                            value={appConfig.domainName || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, domainName: e.target.value }))}
                            placeholder="例: システム情報系"
                          />
                          <Input
                            value={appConfig.domainHeadName || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, domainHeadName: e.target.value }))}
                            placeholder="例: 矢野 博明"
                          />
                        </div>
                        {renderFieldIssues('domain_head.name')}
                      </div>
                      <div className="review-field">
                        <label>申請種別</label>
                        <select
                          className="input"
                          value={appConfig.applicationType}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, applicationType: e.target.value as 'new' | 'change' }))}
                        >
                          <option value="new">新規申請</option>
                          <option value="change">変更申請</option>
                        </select>
                      </div>
                      {appConfig.applicationType === 'change' && (
                        <div className="review-field">
                          <label>審査承認番号</label>
                          <Input
                            value={appConfig.previousApprovalNumber || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, previousApprovalNumber: e.target.value }))}
                          />
                          {renderFieldIssues('application.approval_number')}
                        </div>
                      )}
                      <div className="review-field">
                        <label>
                          <input
                            type="checkbox"
                            checked={appConfig.similarApplicationExists}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, similarApplicationExists: e.target.checked }))}
                          /> 類似申請あり
                        </label>
                      </div>
                      {appConfig.similarApplicationExists && (
                        <div className="review-field">
                          <label>申請者・機関名・申請課題・研究期間</label>
                          <Textarea
                            value={appConfig.similarApplicationDetails || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, similarApplicationDetails: e.target.value }))}
                            rows={2}
                          />
                          {renderFieldIssues('application.similar_details')}
                        </div>
                      )}
                    </div>

                    <div className="review-card">
                      <h3>📋 基本情報</h3>
                      <div className="review-field">
                        <label>研究タイトル</label>
                        <Input
                          value={analysisResult.research_title}
                          onChange={(e) => updateAnalysisField('research_title', e.target.value)}
                        />
                      </div>
                      <div className="review-field">
                        <label>研究目的</label>
                        <Textarea
                          value={analysisResult.research_purpose}
                          onChange={(e) => updateAnalysisField('research_purpose', e.target.value)}
                          rows={3}
                        />
                      </div>
                      <div className="review-field">
                        <label>研究方法</label>
                        <Textarea
                          value={analysisResult.research_method}
                          onChange={(e) => updateAnalysisField('research_method', e.target.value)}
                          rows={3}
                        />
                      </div>
                    </div>

                    <div className="review-card">
                      <h3>👥 対象者</h3>
                      <div className="review-field">
                        <label>対象者の説明</label>
                        <Textarea
                          value={analysisResult.target_participants}
                          onChange={(e) => updateAnalysisField('target_participants', e.target.value)}
                          rows={2}
                        />
                      </div>
                      <div className="review-field">
                        <label>予定参加者数</label>
                        <Input
                          type="number"
                          value={analysisResult.participant_count}
                          onChange={(e) => updateAnalysisField('participant_count', parseInt(e.target.value) || 0)}
                        />
                      </div>
                      <div className="review-field">
                        <label>年齢範囲</label>
                        <Input
                          value={analysisResult.age_range}
                          onChange={(e) => updateAnalysisField('age_range', e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="review-card">
                      <h3>⚠️ リスクと対策</h3>
                      {analysisResult.risks.length > 0 ? (
                        analysisResult.risks.map((risk, i) => (
                          <div key={i} className="risk-item">
                            <p>• {risk}</p>
                            {analysisResult.risk_countermeasures[i] && (
                              <p className="risk-mitigation">対策: {analysisResult.risk_countermeasures[i]}</p>
                            )}
                          </div>
                        ))
                      ) : (
                        <p className="no-risks">特定されたリスクはありません</p>
                      )}
                    </div>

                    <div className="review-card">
                      <h3>⏱️ 実験時間・使用機器</h3>
                      <div className="review-field">
                        <label>所要時間（分）</label>
                        <Input
                          type="number"
                          value={analysisResult.duration_minutes}
                          onChange={(e) => updateAnalysisField('duration_minutes', parseInt(e.target.value) || 0)}
                        />
                      </div>
                      <div className="review-field">
                        <label>使用機器</label>
                        <span>{analysisResult.devices.join(', ') || 'なし'}</span>
                      </div>
                    </div>

                    {/* 3. 実施分担者 */}
                    <div className="review-card">
                      <h3>👥 実施分担者（申請書 3項）</h3>
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                        研究に参加する共同研究者を追加してください（任意）
                      </p>
                      {appConfig.subInvestigators.map((inv, index) => (
                        <div key={index} className="sub-investigator-row" style={{
                          display: 'grid',
                          gridTemplateColumns: '1fr 1fr 1fr 1fr auto',
                          gap: '0.5rem',
                          marginBottom: '0.5rem',
                          alignItems: 'center'
                        }}>
                          <Input
                            placeholder="所属"
                            value={inv.affiliation}
                            onChange={(e) => {
                              const updated = [...appConfig.subInvestigators];
                              updated[index] = { ...updated[index], affiliation: e.target.value };
                              setAppConfig(prev => ({ ...prev, subInvestigators: updated }));
                            }}
                          />
                          <Input
                            placeholder="職名等"
                            value={inv.position}
                            onChange={(e) => {
                              const updated = [...appConfig.subInvestigators];
                              updated[index] = { ...updated[index], position: e.target.value };
                              setAppConfig(prev => ({ ...prev, subInvestigators: updated }));
                            }}
                          />
                          <Input
                            placeholder="氏名"
                            value={inv.name}
                            onChange={(e) => {
                              const updated = [...appConfig.subInvestigators];
                              updated[index] = { ...updated[index], name: e.target.value };
                              setAppConfig(prev => ({ ...prev, subInvestigators: updated }));
                            }}
                          />
                          <Input
                            placeholder="TEL"
                            value={inv.tel || ''}
                            onChange={(e) => {
                              const updated = [...appConfig.subInvestigators];
                              updated[index] = { ...updated[index], tel: e.target.value };
                              setAppConfig(prev => ({ ...prev, subInvestigators: updated }));
                            }}
                          />
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              const updated = appConfig.subInvestigators.filter((_, i) => i !== index);
                              setAppConfig(prev => ({ ...prev, subInvestigators: updated }));
                            }}
                          >
                            ✕
                          </Button>
                        </div>
                      ))}
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setAppConfig(prev => ({
                            ...prev,
                            subInvestigators: [...prev.subInvestigators, { affiliation: '', position: '', name: '', tel: DEFAULT_ZEMPO_LAB_CONDUCTOR_TEL }]
                          }));
                        }}
                        style={{ marginTop: '0.5rem' }}
                      >
                        ＋ 分担者を追加
                      </Button>
                    </div>

                    {/* 5. 実施施設 */}
                    <div className="review-card">
                      <h3>🏢 実施施設（申請書 5項）</h3>
                      <div className="review-field">
                        <label>施設タイプ</label>
                        <select
                          className="input"
                          value={appConfig.facilityType}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, facilityType: e.target.value as 'a' | 'b' | 'c' }))}
                        >
                          <option value="a">a. 筑波大学単独施設での研究</option>
                          <option value="b">b. 筑波大学を代表施設とする多施設共同研究</option>
                          <option value="c">c. 他施設を代表施設とする多施設共同研究</option>
                        </select>
                      </div>
                      <div className="review-field">
                        <label>実施施設名</label>
                        <Input
                          value={appConfig.facilityName}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, facilityName: e.target.value }))}
                          placeholder="例: 総合研究棟B"
                        />
                        {renderFieldIssues('facility.rooms')}
                      </div>
                      {appConfig.facilityType === 'c' && (
                        <>
                          <div className="review-field">
                            <label>代表施設名</label>
                            <Input
                              value={appConfig.externalFacilityName || ''}
                              onChange={(e) => setAppConfig(prev => ({ ...prev, externalFacilityName: e.target.value }))}
                            />
                            {renderFieldIssues('facility.external_facility')}
                          </div>
                          <div className="review-field">
                            <label>研究組織代表者氏名</label>
                            <Input
                              value={appConfig.externalOrgLeader || ''}
                              onChange={(e) => setAppConfig(prev => ({ ...prev, externalOrgLeader: e.target.value }))}
                            />
                            {renderFieldIssues('facility.external_org_leader')}
                          </div>
                        </>
                      )}
                      {(appConfig.facilityType === 'b' || appConfig.facilityType === 'c') && (
                        <div className="review-field">
                          <label>筑波大学の役割</label>
                          <Textarea
                            value={appConfig.tsukubaRole || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, tsukubaRole: e.target.value }))}
                            rows={2}
                          />
                          {renderFieldIssues('facility.tsukuba_role')}
                        </div>
                      )}
                    </div>

                    {/* 7. 費用の出所 */}
                    <div className="review-card">
                      <h3>💰 費用の出所（申請書 7項）</h3>
                      <div className="review-field">
                        <label>資金の種類</label>
                        <select
                          className="input"
                          value={appConfig.fundingSource}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, fundingSource: e.target.value }))}
                        >
                          <option value="運営費交付金">運営費交付金</option>
                          <option value="教育研究基盤経費">教育研究基盤経費</option>
                          <option value="科学研究費補助金">科学研究費補助金</option>
                          <option value="厚生労働科学研究費補助金">厚生労働科学研究費補助金</option>
                          <option value="共同研究">共同研究</option>
                          <option value="受託研究">受託研究</option>
                          <option value="奨学寄附金">奨学寄附金</option>
                        </select>
                      </div>
                      <div className="review-field">
                        <label>研究代表者</label>
                        <Input
                          value={appConfig.fundingPI}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, fundingPI: e.target.value }))}
                          placeholder="例: 山田太郎"
                        />
                      </div>
                      <div className="review-field">
                        <label>研究課題名</label>
                        <Input
                          value={appConfig.fundingProjectName}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, fundingProjectName: e.target.value }))}
                          placeholder="（任意）"
                        />
                      </div>
                    </div>

                    {/* 9. 倫理的配慮 */}
                    <div className="review-card">
                      <h3>倫理的配慮（申請書 9項）</h3>
                      <div className="review-field">
                        <label>
                          <input
                            type="checkbox"
                            checked={appConfig.genomeRelated}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, genomeRelated: e.target.checked }))}
                          /> ヒトゲノム・遺伝子解析研究に該当
                        </label>
                      </div>
                      <div className="review-field">
                        <label>
                          <input
                            type="checkbox"
                            checked={appConfig.conflictOfInterest}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, conflictOfInterest: e.target.checked }))}
                          /> 利益相反あり
                        </label>
                      </div>
                      {appConfig.conflictOfInterest && (
                        <div className="review-field">
                          <label>相手先企業名</label>
                          <Input
                            value={appConfig.conflictOfInterestPartner || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, conflictOfInterestPartner: e.target.value }))}
                          />
                          {renderFieldIssues('ethics.conflict_of_interest_partner')}
                        </div>
                      )}
                      <div className="review-field">
                        <label>
                          <input
                            type="checkbox"
                            checked={appConfig.videoRecording}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, videoRecording: e.target.checked }))}
                          /> ビデオ撮影あり
                        </label>
                      </div>
                      {appConfig.videoRecording && (
                        <>
                          <div className="review-field">
                            <label>記録種別</label>
                            <Input
                              value={appConfig.recordingTypes || ''}
                              onChange={(e) => setAppConfig(prev => ({ ...prev, recordingTypes: e.target.value }))}
                              placeholder="例: 実験中の姿勢・動作映像"
                            />
                            {renderFieldIssues('recording.types')}
                          </div>
                          <div className="review-field">
                            <label>
                              <input
                                type="checkbox"
                                checked={appConfig.recordingPublicRelease}
                                onChange={(e) => setAppConfig(prev => ({ ...prev, recordingPublicRelease: e.target.checked }))}
                              /> ビデオ画像公開についての承諾書を取得
                            </label>
                          </div>
                        </>
                      )}
                      <div className="review-field">
                        <label>
                          <input
                            type="checkbox"
                            checked={appConfig.invasiveness}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, invasiveness: e.target.checked }))}
                          /> 侵襲性あり
                        </label>
                      </div>
                      {appConfig.invasiveness && (
                        <div className="review-field">
                          <label>具体的な内容</label>
                          <Textarea
                            value={appConfig.invasivenessDetails || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, invasivenessDetails: e.target.value }))}
                            rows={2}
                          />
                          {renderFieldIssues('ethics.invasiveness_details')}
                        </div>
                      )}
                    </div>

                    {/* 10. データ保存 */}
                    <div className="review-card">
                      <h3>💾 データ保存設定（申請書 10項）</h3>
                      <div className="review-field">
                        <label>取得する研究データ</label>
                        <Textarea
                          value={appConfig.dataTypes || ''}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, dataTypes: e.target.value }))}
                          rows={2}
                          placeholder="例: 実験課題中の反応時間、正答率、質問紙回答"
                        />
                        {renderFieldIssues('data.types')}
                      </div>
                      <div className="review-field">
                        <label>保存期間</label>
                        <select
                          className="input"
                          value={appConfig.retentionPeriod}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, retentionPeriod: e.target.value as '10years' | 'less' }))}
                        >
                          <option value="10years">論文等発表後10年間（ガイドライン基準）</option>
                          <option value="less">10年以下（理由を記載）</option>
                        </select>
                      </div>
                      {appConfig.retentionPeriod === 'less' && (
                        <div className="review-field">
                          <label>10年以下の理由</label>
                          <Textarea
                            value={appConfig.retentionReason || ''}
                            onChange={(e) => setAppConfig(prev => ({ ...prev, retentionReason: e.target.value }))}
                            rows={2}
                          />
                          {renderFieldIssues('data.retention_period')}
                        </div>
                      )}
                      <div className="review-field">
                        <label>匿名化</label>
                        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                          <label>
                            <input
                              type="checkbox"
                              checked={appConfig.hasAnonymization}
                              onChange={(e) => setAppConfig(prev => ({ ...prev, hasAnonymization: e.target.checked }))}
                            /> 有
                          </label>
                          {appConfig.hasAnonymization && (
                            <label>
                              <input
                                type="checkbox"
                                checked={appConfig.hasCorrespondenceTable}
                                onChange={(e) => setAppConfig(prev => ({ ...prev, hasCorrespondenceTable: e.target.checked }))}
                              /> 対応表を作成
                            </label>
                          )}
                        </div>
                      </div>
                      <div className="review-field">
                        <label>管理場所</label>
                        <Input
                          value={appConfig.storageLocation}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, storageLocation: e.target.value }))}
                        />
                        {renderFieldIssues('data.storage_location')}
                      </div>
                      <div className="review-field">
                        <label>管理責任者</label>
                        <Input
                          value={appConfig.dataManager}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, dataManager: e.target.value }))}
                          placeholder="例: 善甫 啓一"
                        />
                        {renderFieldIssues('data.manager')}
                      </div>
                      <div className="review-field">
                        <label>管理方法</label>
                        <Textarea
                          value={appConfig.managementMethod}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, managementMethod: e.target.value }))}
                          rows={3}
                        />
                        {renderFieldIssues('data.management_method')}
                      </div>
                      <div className="review-field">
                        <label>処分方法</label>
                        <Textarea
                          value={appConfig.disposalMethod}
                          onChange={(e) => setAppConfig(prev => ({ ...prev, disposalMethod: e.target.value }))}
                          rows={3}
                        />
                        {renderFieldIssues('data.disposal_method')}
                      </div>
                    </div>
                  </div>


                  <div className="review-actions">
                    <Button variant="secondary" onClick={() => setCurrentStep(0)}>
                      戻る
                    </Button>
                    <Button
                      variant="primary"
                      size="lg"
                      onClick={handleGenerate}
                      isLoading={generateSSE.status === 'streaming' || generateSSE.status === 'connecting'}
                    >
                      📝 書類を生成（マルチエージェントレビュー付き）
                    </Button>
                  </div>
                </div>
              )}

              {/* ステップ3: 生成中 / ステップ4: ダウンロード */}
              {currentStep >= 2 && (
                <div className="generation-section">
                  <div className="generation-status">
                    <div className="status-icon">
                      {currentStep === 2 ? (
                        <div className="spinner-large" />
                      ) : (
                        <span>✅</span>
                      )}
                    </div>
                    <h2>{currentStep === 2 ? 'マルチエージェントレビュー中...' : '書類生成完了！'}</h2>
                    <p>
                      {currentStep === 2
                        ? 'Agent A（書類生成）とAgent B（倫理審査シミュレート）が書類をチェックしています'
                        : 'すべての書類が正常に生成されました'}
                    </p>

                    {/* SSE進捗表示 */}
                    {currentStep === 2 && generateSSE.status !== 'idle' && (
                      <ProgressStepper
                        events={generateSSE.progress}
                        status={generateSSE.status}
                        error={generateSSE.error}
                      />
                    )}

                    {currentStep === 3 && (
                      <>
                        {generatedSessionId ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
                            <Button
                              variant="success"
                              size="lg"
                              onClick={async () => {
                                try {
                                  const savedPath = await downloadDocumentsZip(generatedSessionId);
                                  if (savedPath) {
                                    // Tauri モード: 保存先パスを表示
                                    toast.success(`保存しました: ${savedPath}`, { autoClose: 8000 });
                                  } else {
                                    // ブラウザモード: ブラウザ側のダウンロードが発火
                                    toast.success('ダウンロードを開始しました');
                                  }
                                } catch (err) {
                                  console.error('ZIP download failed:', err);
                                  toast.error(
                                    `ダウンロードに失敗しました: ${err instanceof Error ? err.message : '不明なエラー'}`
                                  );
                                }
                              }}
                            >
                              📥 ZIPファイルをダウンロード
                            </Button>
                            <Button
                              variant="primary"
                              isLoading={reformatting}
                              onClick={async () => {
                                if (!generatedSessionId) return;
                                setReformatting(true);
                                try {
                                  const res = await reformatDocuments(generatedSessionId);
                                  const n = res.regenerated.length;
                                  if (res.errors.length > 0) {
                                    toast.warning(
                                      `公式書類を再生成しました（${n}件）。一部失敗: ${res.errors.join(', ')}`
                                    );
                                  } else {
                                    toast.success(`公式フォーマットへ再適用しました（${n}件を再生成）`);
                                  }
                                  if (res.assumptions.length > 0) {
                                    toast.info(
                                      `入力から ${res.assumptions.length} 件を自動推定して補完しました。内容をご確認ください。`,
                                      { autoClose: 8000 }
                                    );
                                  }
                                  if (res.issues.length > 0) {
                                    toast.info(
                                      `未入力・要確認の項目が ${res.issues.length} 件あります。内容をご確認ください。`,
                                      { autoClose: 8000 }
                                    );
                                  }
                                } catch (err) {
                                  console.error('reformat failed:', err);
                                  toast.error(
                                    `再フォーマットに失敗しました: ${err instanceof Error ? err.message : '不明なエラー'}`
                                  );
                                } finally {
                                  setReformatting(false);
                                }
                              }}
                            >
                              🔄 再度フォーマットに当てはめる
                            </Button>
                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                              <Button
                                variant="secondary"
                                onClick={() => {
                                  setSelectedSessionId(generatedSessionId);
                                  setCurrentView('rebuttal');
                                }}
                              >
                                📝 審査コメントへの対応
                              </Button>
                              <Button
                                variant="secondary"
                                onClick={handleBackToSessions}
                              >
                                セッション一覧へ
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <p style={{ color: 'orange' }}>セッションIDを取得中...</p>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* 設定モーダル */}
      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
            <SettingsPage
              settings={settings}
              onSave={async (updates) => {
                await updateSettings(updates);
                // LLM設定が更新された場合、APIクライアントも更新
                if (updates.llm?.apiKey) {
                  setApiKey(updates.llm.apiKey, updates.llm?.provider || settings.llm?.provider || 'openai');
                }
                toast.success('設定を保存しました');
              }}
              onClose={() => setShowSettings(false)}
            />
          </div>
        </div>
      )}

      <ToastContainer
        position="top-right"
        autoClose={3000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        pauseOnHover
        theme="light"
      />

      {/* Onboarding Tutorial */}
      {showOnboarding && (
        <OnboardingTutorial
          onComplete={() => setShowOnboarding(false)}
          onOpenSettings={() => setShowSettings(true)}
        />
      )}
    </div>
  );
}

export default App;
