// frontend/src/components/common/Button.tsx

import React from 'react';
import './Button.css';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    isLoading?: boolean;
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
    children,
    variant = 'primary',
    size = 'md',
    isLoading = false,
    leftIcon,
    rightIcon,
    disabled,
    className = '',
    ...props
}) => {
    return (
        <button
            className={`button button-${variant} button-${size} ${className}`}
            disabled={disabled || isLoading}
            {...props}
        >
            {isLoading ? (
                <span className="button-spinner" />
            ) : (
                <>
                    {leftIcon && <span className="button-icon">{leftIcon}</span>}
                    {children}
                    {rightIcon && <span className="button-icon">{rightIcon}</span>}
                </>
            )}
        </button>
    );
};
