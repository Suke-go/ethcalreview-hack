// frontend/src/components/SettingsPage.tsx

import React, { useState } from 'react';
import { Button } from './common/Button';
import { Input, Select } from './common/Input';
import type { Settings } from '../types';
import './SettingsPage.css';

interface SettingsPageProps {
    settings: Settings;
    onSave: (settings: Partial<Settings>) => Promise<void>;
    onClose: () => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
    settings,
    onSave,
    onClose,
}) => {
    const [formData, setFormData] = useState(settings);
    const [isSaving, setIsSaving] = useState(false);
    const [activeTab, setActiveTab] = useState<'lab' | 'budget' | 'api'>('lab');

    const handleChange = (path: string, value: string | number) => {
        const keys = path.split('.');
        setFormData(prev => {
            const newData = { ...prev };
            let current: Record<string, unknown> = newData;

            for (let i = 0; i < keys.length - 1; i++) {
                current[keys[i]] = { ...(current[keys[i]] as Record<string, unknown>) };
                current = current[keys[i]] as Record<string, unknown>;
            }

            current[keys[keys.length - 1]] = value;
            return newData as Settings;
        });
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(formData);
            onClose();
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="settings-page">
            <div className="settings-header">
                <h2>⚙️ 設定</h2>
                <button className="close-btn" onClick={onClose}>×</button>
            </div>

            <div className="settings-tabs">
                <button
                    className={`tab ${activeTab === 'lab' ? 'active' : ''}`}
                    onClick={() => setActiveTab('lab')}
                >
                    🏢 研究室情報
                </button>
                <button
                    className={`tab ${activeTab === 'budget' ? 'active' : ''}`}
                    onClick={() => setActiveTab('budget')}
                >
                    💰 予算・謝礼
                </button>
                <button
                    className={`tab ${activeTab === 'api' ? 'active' : ''}`}
                    onClick={() => setActiveTab('api')}
                >
                    🔑 API設定
                </button>
            </div>

            <div className="settings-content">
                {activeTab === 'lab' && (
                    <div className="settings-section">
                        <h3>研究室基本情報</h3>
                        <Input
                            label="研究室名"
                            value={formData.labName}
                            onChange={(e) => handleChange('labName', e.target.value)}
                        />

                        <div className="section-divider" />

                        <h3>研究責任者</h3>
                        <div className="form-grid">
                            <Input
                                label="氏名"
                                value={formData.principalInvestigator?.name || ''}
                                onChange={(e) => handleChange('principalInvestigator.name', e.target.value)}
                            />
                            <Input
                                label="所属"
                                value={formData.principalInvestigator?.affiliation || ''}
                                onChange={(e) => handleChange('principalInvestigator.affiliation', e.target.value)}
                            />
                            <Input
                                label="職名"
                                value={formData.principalInvestigator?.position || ''}
                                onChange={(e) => handleChange('principalInvestigator.position', e.target.value)}
                            />
                            <Input
                                label="メールアドレス"
                                type="email"
                                value={formData.principalInvestigator?.email || ''}
                                onChange={(e) => handleChange('principalInvestigator.email', e.target.value)}
                            />
                            <Input
                                label="電話番号"
                                value={formData.principalInvestigator?.phone || ''}
                                onChange={(e) => handleChange('principalInvestigator.phone', e.target.value)}
                            />
                        </div>

                        <div className="section-divider" />

                        <h3>倫理委員会</h3>
                        <Input
                            label="委員会名"
                            value={formData.ethicsCommittee}
                            onChange={(e) => handleChange('ethicsCommittee', e.target.value)}
                        />
                    </div>
                )}

                {activeTab === 'budget' && (
                    <div className="settings-section">
                        <h3>予算設定</h3>
                        <Select
                            label="予算種別"
                            value={formData.budget.source}
                            onChange={(e) => handleChange('budget.source', e.target.value)}
                            options={[
                                { value: '運営費交付金', label: '運営費交付金' },
                                { value: '科研費', label: '科研費' },
                                { value: '受託研究費', label: '受託研究費' },
                                { value: '共同研究費', label: '共同研究費' },
                                { value: 'その他', label: 'その他' },
                            ]}
                        />
                        <Input
                            label="プロジェクト名"
                            value={formData.budget.project_name || ''}
                            onChange={(e) => handleChange('budget.project_name', e.target.value)}
                        />

                        <div className="section-divider" />

                        <h3>謝礼計算設定</h3>
                        <div className="form-grid">
                            <Input
                                label="60分あたり基本金額（円）"
                                type="number"
                                value={formData.reward?.baseAmountPer60Min || 1000}
                                onChange={(e) => handleChange('reward.baseAmountPer60Min', parseInt(e.target.value))}
                            />
                            <Input
                                label="丸め単位（円）"
                                type="number"
                                value={formData.reward?.roundingUnit || 100}
                                onChange={(e) => handleChange('reward.roundingUnit', parseInt(e.target.value))}
                            />
                        </div>

                        <div className="reward-info">
                            <p>💡 謝礼は「大学規定による」と記載され、60分1,000円を基準に100円単位で自動計算されます。</p>
                            <table className="reward-example">
                                <thead>
                                    <tr>
                                        <th>所要時間</th>
                                        <th>推奨謝礼額</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td>30分</td><td>¥500</td></tr>
                                    <tr><td>45分</td><td>¥800</td></tr>
                                    <tr><td>60分</td><td>¥1,000</td></tr>
                                    <tr><td>90分</td><td>¥1,500</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'api' && (
                    <div className="settings-section">
                        <h3>LLMプロバイダー設定</h3>
                        <Select
                            label="プロバイダー"
                            value={formData.llm?.provider || 'openai'}
                            onChange={(e) => handleChange('llm.provider', e.target.value)}
                            options={[
                                { value: 'openai', label: 'OpenAI (推奨)' },
                                { value: 'gemini', label: 'Google Gemini' },
                            ]}
                        />

                        <div className="section-divider" />

                        <h3>APIキー設定</h3>
                        <Input
                            label={formData.llm?.provider === 'gemini' ? 'Gemini APIキー' : 'OpenAI APIキー'}
                            type="password"
                            value={formData.llm?.apiKey || ''}
                            placeholder={formData.llm?.provider === 'gemini' ? 'AIza...' : 'sk-...'}
                            onChange={(e) => handleChange('llm.apiKey', e.target.value)}
                            helpText={formData.llm?.provider === 'gemini'
                                ? 'Google AI StudioでAPIキーを取得してください'
                                : 'OpenAI PlatformでAPIキーを取得してください'}
                        />

                        {formData.llm?.provider === 'openai' ? (
                            <a
                                href="https://platform.openai.com/api-keys"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="api-link"
                            >
                                🔗 OpenAI Platformでキーを取得
                            </a>
                        ) : (
                            <a
                                href="https://aistudio.google.com/app/apikey"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="api-link"
                            >
                                🔗 Google AI Studioでキーを取得
                            </a>
                        )}

                        <div className="section-divider" />

                        <h3>モデル設定</h3>
                        {formData.llm?.provider === 'gemini' ? (
                            <Select
                                label="Geminiモデル"
                                value={formData.llm?.model || 'gemini-2.5-flash'}
                                onChange={(e) => handleChange('llm.model', e.target.value)}
                                options={[
                                    { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview (最新・高速)' },
                                    { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro Preview (最新・高精度)' },
                                    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (推奨・安定)' },
                                    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
                                ]}
                            />
                        ) : (
                            <Select
                                label="OpenAIモデル"
                                value={formData.llm?.model || 'gpt-5-mini'}
                                onChange={(e) => handleChange('llm.model', e.target.value)}
                                options={[
                                    { value: 'gpt-5.2', label: 'GPT-5.2 (最新・高精度)' },
                                    { value: 'gpt-5-mini', label: 'GPT-5 Mini (推奨・コスパ◎)' },
                                    { value: 'gpt-4o', label: 'GPT-4o' },
                                    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
                                ]}
                            />
                        )}

                        <div className="provider-info">
                            <p>💡 <strong>推奨設定</strong>: GPT-5 Mini または Gemini 2.5 Flash</p>
                            <p>📝 書類生成は複数回LLMを呼び出すため、高速モデルがおすすめです</p>
                        </div>
                    </div>
                )}
            </div>

            <div className="settings-footer">
                {/* Electron環境でのみ設定フォルダを開くボタンを表示 */}
                {typeof window !== 'undefined' && (window as any).electronAPI && (
                    <Button
                        variant="secondary"
                        onClick={() => (window as any).electronAPI.openUserDataFolder()}
                        style={{ marginRight: 'auto' }}
                    >
                        📁 設定フォルダを開く
                    </Button>
                )}
                <Button variant="secondary" onClick={onClose}>
                    キャンセル
                </Button>
                <Button variant="primary" onClick={handleSave} isLoading={isSaving}>
                    保存
                </Button>
            </div>
        </div>
    );
};
