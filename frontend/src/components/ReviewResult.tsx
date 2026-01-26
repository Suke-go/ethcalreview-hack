// frontend/src/components/ReviewResult.tsx

import React from 'react';
import type { ReviewResult as ReviewResultType, ReviewFinding } from '../types';
import './ReviewResult.css';

interface ReviewResultProps {
    result: ReviewResultType;
    onContinue: () => void;
    onRevise: () => void;
}

// 厳格審査基準の説明
const CRITERIA_LABELS: Record<string, string> = {
    SR1: 'リスク記述の網羅性',
    SR2: '対策の具体性',
    SR3: '緊急時対応',
    SR4: '除外基準の妥当性',
    SR5: '同意撤回手続き',
    SR6: '参加者保護',
};

const getSeverityColor = (severity: string) => {
    switch (severity) {
        case 'critical':
            return 'severity-critical';
        case 'major':
            return 'severity-major';
        case 'minor':
            return 'severity-minor';
        default:
            return '';
    }
};

const FindingCard: React.FC<{ finding: ReviewFinding }> = ({ finding }) => (
    <div className={`finding-card ${getSeverityColor(finding.severity)}`}>
        <div className="finding-header">
            <span className="finding-criteria">
                {CRITERIA_LABELS[finding.criteriaId] || finding.criteriaId}
            </span>
            <span className={`finding-severity ${finding.severity}`}>
                {finding.severity === 'critical' && '🚨 重大'}
                {finding.severity === 'major' && '⚠️ 重要'}
                {finding.severity === 'minor' && '💡 軽微'}
            </span>
        </div>
        <p className="finding-description">{finding.description}</p>
        {finding.suggestion && (
            <div className="finding-suggestion">
                <strong>修正提案:</strong> {finding.suggestion}
            </div>
        )}
    </div>
);

export const ReviewResult: React.FC<ReviewResultProps> = ({
    result,
    onContinue,
    onRevise,
}) => {
    const isApproved = result.finalStatus === 'approved';
    const needsRevision = result.finalStatus === 'needs_revision';

    // 全指摘をまとめる
    const allFindings = [
        ...result.agentBReview.findings,
    ];

    const criticalCount = allFindings.filter(f => f.severity === 'critical').length;
    const majorCount = allFindings.filter(f => f.severity === 'major').length;
    const minorCount = allFindings.filter(f => f.severity === 'minor').length;

    return (
        <div className="review-result">
            <div className={`result-header ${isApproved ? 'approved' : needsRevision ? 'needs-revision' : 'rejected'}`}>
                <div className="result-icon">
                    {isApproved && '✅'}
                    {needsRevision && '⚠️'}
                    {result.finalStatus === 'rejected' && '❌'}
                </div>
                <div className="result-title">
                    <h2>
                        {isApproved && 'マルチエージェントレビュー完了'}
                        {needsRevision && '修正が必要な項目があります'}
                        {result.finalStatus === 'rejected' && '重大な問題があります'}
                    </h2>
                    <p>
                        Agent A（書類生成）とAgent B（倫理審査シミュレート）による
                        {result.iterations}回の応酬が完了しました
                    </p>
                </div>
            </div>

            <div className="result-summary">
                <div className="summary-stats">
                    <div className="stat-item critical">
                        <span className="stat-value">{criticalCount}</span>
                        <span className="stat-label">重大な指摘</span>
                    </div>
                    <div className="stat-item major">
                        <span className="stat-value">{majorCount}</span>
                        <span className="stat-label">重要な指摘</span>
                    </div>
                    <div className="stat-item minor">
                        <span className="stat-value">{minorCount}</span>
                        <span className="stat-label">軽微な指摘</span>
                    </div>
                </div>
            </div>

            <div className="result-agents">
                <div className="agent-section">
                    <h3>
                        <span className="agent-badge agent-a">Agent A</span>
                        書類生成エージェント
                    </h3>
                    <p className="agent-assessment">{result.agentAReview.overallAssessment}</p>

                    {result.agentAReview.corrections && result.agentAReview.corrections.length > 0 && (
                        <div className="corrections-list">
                            <h4>実施した修正:</h4>
                            <ul>
                                {result.agentAReview.corrections.map((correction, i) => (
                                    <li key={i}>{correction}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>

                <div className="agent-section">
                    <h3>
                        <span className="agent-badge agent-b">Agent B</span>
                        倫理審査シミュレート
                    </h3>
                    <p className="agent-assessment">{result.agentBReview.overallAssessment}</p>

                    {allFindings.length > 0 ? (
                        <div className="findings-list">
                            <h4>審査指摘事項:</h4>
                            {allFindings.map((finding, i) => (
                                <FindingCard key={i} finding={finding} />
                            ))}
                        </div>
                    ) : (
                        <p className="no-findings">指摘事項はありません。</p>
                    )}
                </div>
            </div>

            <div className="result-actions">
                {needsRevision && (
                    <button className="action-btn secondary" onClick={onRevise}>
                        🔄 修正して再レビュー
                    </button>
                )}
                <button className="action-btn primary" onClick={onContinue}>
                    {isApproved ? '📥 書類をダウンロード' : '📥 現状の書類をダウンロード'}
                </button>
            </div>
        </div>
    );
};
