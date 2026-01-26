// frontend/src/components/layout/Stepper.tsx

import React from 'react';
import './Stepper.css';

export interface Step {
    id: string;
    label: string;
    description?: string;
}

interface StepperProps {
    steps: Step[];
    currentStep: number;
    onStepClick?: (stepIndex: number) => void;
}

export const Stepper: React.FC<StepperProps> = ({ steps, currentStep, onStepClick }) => {
    return (
        <div className="stepper">
            {steps.map((step, index) => {
                const isCompleted = index < currentStep;
                const isCurrent = index === currentStep;
                const isClickable = onStepClick && index <= currentStep;

                return (
                    <React.Fragment key={step.id}>
                        <div
                            className={`stepper-item ${isCompleted ? 'completed' : ''} ${isCurrent ? 'current' : ''} ${isClickable ? 'clickable' : ''}`}
                            onClick={() => isClickable && onStepClick?.(index)}
                        >
                            <div className="stepper-indicator">
                                {isCompleted ? (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                                        <polyline points="20 6 9 17 4 12"></polyline>
                                    </svg>
                                ) : (
                                    <span>{index + 1}</span>
                                )}
                            </div>
                            <div className="stepper-content">
                                <span className="stepper-label">{step.label}</span>
                                {step.description && (
                                    <span className="stepper-description">{step.description}</span>
                                )}
                            </div>
                        </div>

                        {index < steps.length - 1 && (
                            <div className={`stepper-connector ${isCompleted ? 'completed' : ''}`} />
                        )}
                    </React.Fragment>
                );
            })}
        </div>
    );
};
