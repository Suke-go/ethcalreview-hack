// frontend/src/components/ResearchPlanInput.tsx

import React, { useState, useCallback } from 'react';
import { Button } from './common/Button';
import { Textarea } from './common/Input';
import { ingestStudyDocuments } from '../api/client';
import './ResearchPlanInput.css';

interface ResearchPlanInputProps {
    onAnalyze: (plan: string) => Promise<void>;
    isAnalyzing: boolean;
    error?: string;
}

export const ResearchPlanInput: React.FC<ResearchPlanInputProps> = ({
    onAnalyze,
    isAnalyzing,
    error,
}) => {
    const [planText, setPlanText] = useState('');
    const [isDragging, setIsDragging] = useState(false);
    const [isExtracting, setIsExtracting] = useState(false);
    const [ingestedFiles, setIngestedFiles] = useState<string[]>([]);
    const [ingestWarnings, setIngestWarnings] = useState<string[]>([]);

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (planText.trim()) {
            await onAnalyze(planText);
        }
    }, [planText, onAnalyze]);

    const handleFileUpload = useCallback(async (files: FileList | File[]) => {
        const fileArray = Array.from(files);
        if (fileArray.length === 0) return;

        setIsExtracting(true);
        setIngestWarnings([]);
        try {
            const result = await ingestStudyDocuments(fileArray);
            const extracted = result.combined_text.trim();
            if (extracted) {
                setPlanText((prev) => {
                    const separator = prev.trim() ? '\n\n' : '';
                    return `${prev}${separator}${extracted}`;
                });
            }
            setIngestedFiles((prev) => [
                ...prev,
                ...result.documents.map((doc) => doc.filename),
            ]);
            setIngestWarnings(result.warnings);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'ファイルの読み取りに失敗しました';
            setIngestWarnings([message]);
        } finally {
            setIsExtracting(false);
        }
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files);
        }
    }, [handleFileUpload]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setIsDragging(false);
    }, []);

    return (
        <div className="research-plan-input">
            <div className="input-header">
                <h2 className="input-title">📝 研究計画を入力</h2>
                <p className="input-description">
                    研究計画、論文メモ、実装メモ、既存docx/xlsxを貼り付けるか、ファイルとして追加してください。
                    AIが内容を解析し、不足項目を確認しながら申請書とアンケート用紙に使う情報へ整理します。
                </p>
            </div>

            <form onSubmit={handleSubmit}>
                <div
                    className={`drop-zone ${isDragging ? 'dragging' : ''}`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                >
                    <Textarea
                        value={planText}
                        onChange={(e) => setPlanText(e.target.value)}
                        placeholder="ここに研究計画を貼り付けてください...

例:
論文や実装メモを入れました。資料から研究目的と実験条件を推論して、実験計画とアンケート案を作ってください。
不明な点は確認事項として出してください。"
                        className="plan-textarea"
                        rows={12}
                    />

                    <div className="drop-overlay">
                        <div className="drop-icon">📄</div>
                        <span>ファイルをここにドロップ</span>
                    </div>
                </div>

                {(isExtracting || ingestedFiles.length > 0 || ingestWarnings.length > 0) && (
                    <div className="ingest-status">
                        {isExtracting && <p>資料テキストを抽出しています...</p>}
                        {ingestedFiles.length > 0 && (
                            <p>取り込み済み: {ingestedFiles.join(', ')}</p>
                        )}
                        {ingestWarnings.map((warning, index) => (
                            <p key={index} className="ingest-warning">{warning}</p>
                        ))}
                    </div>
                )}

                {error && (
                    <div className="input-error-alert">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="8" x2="12" y2="12"></line>
                            <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        <span>{error}</span>
                    </div>
                )}

                <div className="input-actions">
                    <div className="upload-section">
                        <label className="upload-btn">
                            <input
                                type="file"
                                accept=".txt,.md,.docx,.xlsx,.pdf"
                                multiple
                                onChange={(e) => e.target.files && handleFileUpload(e.target.files)}
                                hidden
                            />
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="17 8 12 3 7 8"></polyline>
                                <line x1="12" y1="3" x2="12" y2="15"></line>
                            </svg>
                            資料ファイルを追加
                        </label>
                        <span className="upload-hint">対応形式: .txt, .md, .docx, .xlsx, .pdf</span>
                    </div>

                    <Button
                        type="submit"
                        variant="primary"
                        size="lg"
                        isLoading={isAnalyzing}
                        disabled={!planText.trim() || isExtracting}
                    >
                        {isAnalyzing ? 'AI解析中...' : '🔍 AIで研究計画を解析'}
                    </Button>
                </div>
            </form>

            <div className="input-tips">
                <h3>💡 ヒント</h3>
                <ul>
                    <li>研究の目的、対象者、実験方法を含めると、より正確に解析できます</li>
                    <li>想定されるリスクや対策についても記載があれば、自動で抽出します</li>
                    <li>不足している情報は、次のステップで質問形式で補完します</li>
                </ul>
            </div>
        </div>
    );
};
