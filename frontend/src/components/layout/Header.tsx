// frontend/src/components/layout/Header.tsx

import React from 'react';
import './Header.css';

interface HeaderProps {
    apiKey: string;
    onSettingsClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ apiKey, onSettingsClick }) => {
    return (
        <header className="header">
            <div className="header-content">
                <div className="header-brand">
                    <div className="header-logo">📋</div>
                    <div className="header-title-group">
                        <h1 className="header-title">EthicalReviewHacker</h1>
                        <span className="header-subtitle">倫理審査書類作成支援システム</span>
                    </div>
                </div>

                <div className="header-actions">
                    <div className="header-status">
                        {apiKey ? (
                            <span className="status-badge status-connected">
                                <span className="status-dot"></span>
                                API接続済み
                            </span>
                        ) : (
                            <span className="status-badge status-disconnected">
                                <span className="status-dot"></span>
                                API未設定
                            </span>
                        )}
                    </div>

                    <button className="header-btn" onClick={onSettingsClick}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="3"></circle>
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                        </svg>
                        設定
                    </button>
                </div>
            </div>
        </header>
    );
};
