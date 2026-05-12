import { useState } from 'react';

export const useOnboarding = () => {
    const [showOnboarding, setShowOnboarding] = useState(() => (
        typeof window !== 'undefined' && !localStorage.getItem('onboarding_completed')
    ));

    const resetOnboarding = () => {
        localStorage.removeItem('onboarding_completed');
        setShowOnboarding(true);
    };

    return { showOnboarding, setShowOnboarding, resetOnboarding };
};
