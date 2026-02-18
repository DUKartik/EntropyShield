
import React from 'react';
import { cn } from '@/lib/utils';

interface HeaderProps {
    currentView: string;
}

const viewLabels: Record<string, string> = {
    dashboard: 'Overview',
    uploader: 'Policy Engine',
    data: 'Forensics',
};

export const Header: React.FC<HeaderProps> = ({ currentView }) => {
    return (
        <header className="h-16 min-h-[64px] shrink-0 border-b border-white/10 flex items-center px-6 bg-slate-950/80 backdrop-blur-md sticky top-0 z-20 w-full">
            <span className="text-sm text-muted-foreground">
                EntropyShield / <span className="text-white font-medium">{viewLabels[currentView] ?? currentView}</span>
            </span>
        </header>
    );
};
