import { useState, useEffect } from 'react';
import { Button } from './common/Button';
import './OnboardingTutorial.css';

interface OnboardingTutorialProps {
    onComplete: () => void;
    onOpenSettings: () => void;
}

const steps = [
    {
        icon: '👋',
        title: 'Ethics Review Helperへようこそ',
        description: '研究倫理審査書類を自動生成するアプリです。\nこのチュートリアルで初期設定を行いましょう。',
        action: null,
    },
    {
        icon: '🔑',
        title: 'Step 1: APIキーの設定',
        description: 'AI機能を使用するには、Google GeminiまたはOpenAIのAPIキーが必要です。\n設定画面から入力してください。',
        action: 'openSettings',
        actionLabel: '設定を開く',
    },
    {
        icon: '🏢',
        title: 'Step 2: 研究室情報の設定',
        description: '設定画面の「研究室情報」タブで、\n研究責任者の氏名・所属・連絡先を設定してください。',
        action: 'openSettings',
        actionLabel: '設定を開く',
    },
    {
        icon: '📁',
        title: 'Step 3: lab_defaults.json（任意）',
        description: 'より詳細な設定は「設定フォルダを開く」から\nlab_defaults.jsonを直接編集できます。',
        action: null,
        tip: 'lab_defaults.json.example をコピーして編集してください',
    },
    {
        icon: '🚀',
        title: '準備完了！',
        description: '研究計画を入力して、AIに書類を生成させましょう。\n左側のフォームから始めてください。',
        action: null,
    },
];

export const OnboardingTutorial = ({ onComplete, onOpenSettings }: OnboardingTutorialProps) => {
    const [currentStep, setCurrentStep] = useState(0);
    const [isVisible, setIsVisible] = useState(true);

    const handleNext = () => {
        if (currentStep < steps.length - 1) {
            setCurrentStep(currentStep + 1);
        } else {
            handleComplete();
        }
    };

    const handlePrev = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
        }
    };

    const handleComplete = () => {
        setIsVisible(false);
        localStorage.setItem('onboarding_completed', 'true');
        onComplete();
    };

    const handleAction = () => {
        const step = steps[currentStep];
        if (step.action === 'openSettings') {
            onOpenSettings();
        }
    };

    const handleSkip = () => {
        handleComplete();
    };

    if (!isVisible) return null;

    const step = steps[currentStep];
    const isLastStep = currentStep === steps.length - 1;

    return (
        <div className="onboarding-overlay">
            <div className="onboarding-modal">
                <button className="onboarding-skip" onClick={handleSkip}>
                    スキップ
                </button>

                <div className="onboarding-content">
                    <div className="onboarding-icon">{step.icon}</div>
                    <h2>{step.title}</h2>
                    <p>{step.description}</p>

                    {step.tip && (
                        <div className="onboarding-tip">
                            💡 {step.tip}
                        </div>
                    )}

                    {step.action && (
                        <Button
                            variant="secondary"
                            onClick={handleAction}
                            style={{ marginTop: '1rem' }}
                        >
                            {step.actionLabel}
                        </Button>
                    )}
                </div>

                <div className="onboarding-progress">
                    {steps.map((_, index) => (
                        <div
                            key={index}
                            className={`progress-dot ${index === currentStep ? 'active' : ''} ${index < currentStep ? 'completed' : ''}`}
                        />
                    ))}
                </div>

                <div className="onboarding-actions">
                    <Button
                        variant="secondary"
                        onClick={handlePrev}
                        disabled={currentStep === 0}
                    >
                        ← 戻る
                    </Button>
                    <Button variant="primary" onClick={handleNext}>
                        {isLastStep ? '始める 🚀' : '次へ →'}
                    </Button>
                </div>
            </div>
        </div>
    );
};

// 初回起動かどうかを確認するフック
export const useOnboarding = () => {
    const [showOnboarding, setShowOnboarding] = useState(false);

    useEffect(() => {
        const completed = localStorage.getItem('onboarding_completed');
        if (!completed) {
            setShowOnboarding(true);
        }
    }, []);

    const resetOnboarding = () => {
        localStorage.removeItem('onboarding_completed');
        setShowOnboarding(true);
    };

    return { showOnboarding, setShowOnboarding, resetOnboarding };
};
