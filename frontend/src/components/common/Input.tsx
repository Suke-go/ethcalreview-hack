// frontend/src/components/common/Input.tsx

import React, { forwardRef } from 'react';
import './Input.css';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
    helpText?: string;
    leftAddon?: React.ReactNode;
    rightAddon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
    ({ label, error, helpText, leftAddon, rightAddon, className = '', id, ...props }, ref) => {
        const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;

        return (
            <div className={`input-wrapper ${className}`}>
                {label && (
                    <label htmlFor={inputId} className="input-label">
                        {label}
                        {props.required && <span className="input-required">*</span>}
                    </label>
                )}
                <div className={`input-container ${error ? 'input-error' : ''}`}>
                    {leftAddon && <span className="input-addon input-addon-left">{leftAddon}</span>}
                    <input
                        ref={ref}
                        id={inputId}
                        className="input-field"
                        {...props}
                    />
                    {rightAddon && <span className="input-addon input-addon-right">{rightAddon}</span>}
                </div>
                {error && <p className="input-error-text">{error}</p>}
                {helpText && !error && <p className="input-help-text">{helpText}</p>}
            </div>
        );
    }
);

Input.displayName = 'Input';

// テキストエリアコンポーネント
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    label?: string;
    error?: string;
    helpText?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
    ({ label, error, helpText, className = '', id, ...props }, ref) => {
        const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`;

        return (
            <div className={`input-wrapper ${className}`}>
                {label && (
                    <label htmlFor={textareaId} className="input-label">
                        {label}
                        {props.required && <span className="input-required">*</span>}
                    </label>
                )}
                <textarea
                    ref={ref}
                    id={textareaId}
                    className={`textarea-field ${error ? 'input-error' : ''}`}
                    {...props}
                />
                {error && <p className="input-error-text">{error}</p>}
                {helpText && !error && <p className="input-help-text">{helpText}</p>}
            </div>
        );
    }
);

Textarea.displayName = 'Textarea';

// セレクトコンポーネント
export interface SelectOption {
    value: string;
    label: string;
    disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    label?: string;
    error?: string;
    helpText?: string;
    options: SelectOption[];
    placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
    ({ label, error, helpText, options, placeholder, className = '', id, ...props }, ref) => {
        const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`;

        return (
            <div className={`input-wrapper ${className}`}>
                {label && (
                    <label htmlFor={selectId} className="input-label">
                        {label}
                        {props.required && <span className="input-required">*</span>}
                    </label>
                )}
                <select
                    ref={ref}
                    id={selectId}
                    className={`select-field ${error ? 'input-error' : ''}`}
                    {...props}
                >
                    {placeholder && (
                        <option value="" disabled>
                            {placeholder}
                        </option>
                    )}
                    {options.map((option) => (
                        <option key={option.value} value={option.value} disabled={option.disabled}>
                            {option.label}
                        </option>
                    ))}
                </select>
                {error && <p className="input-error-text">{error}</p>}
                {helpText && !error && <p className="input-help-text">{helpText}</p>}
            </div>
        );
    }
);

Select.displayName = 'Select';
