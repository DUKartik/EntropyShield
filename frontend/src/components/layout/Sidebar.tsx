
import React from 'react';
import { ShieldCheck, LayoutDashboard, Database } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  currentView: 'dashboard' | 'uploader' | 'data';
  onViewChange: (view: 'dashboard' | 'uploader' | 'data') => void;
}

const SidebarItem = ({
  icon,
  label,
  active,
  onClick
}: {
  icon: React.ReactNode,
  label: string,
  active: boolean,
  onClick: () => void
}) => (
  <button
    onClick={onClick}
    className={cn(
      "w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-300",
      active
        ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_15px_rgba(56,189,248,0.1)]"
        : "text-muted-foreground hover:bg-white/5 hover:text-foreground hover:border-white/10 border border-transparent"
    )}
  >
    {icon}
    {label}
  </button>
);

export const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange }) => {
  return (
    <aside className="w-64 border-r border-white/10 bg-slate-950/50 backdrop-blur-xl hidden md:flex flex-col h-full sticky top-0 z-30">
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="relative">
            <ShieldCheck className="w-7 h-7 text-primary" />
            <div className="absolute inset-0 bg-primary/20 blur-md rounded-full animate-pulse" />
          </div>
          <span className="font-bold text-xl tracking-tight text-white">
            Entropy
            <span className="text-primary">Shield</span>
          </span>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Platform
        </div>
        <SidebarItem
          icon={<LayoutDashboard className="w-4 h-4" />}
          label="Overview"
          active={currentView === 'dashboard'}
          onClick={() => onViewChange('dashboard')}
        />
        <SidebarItem
          icon={<ShieldCheck className="w-4 h-4" />}
          label="Policy Engine"
          active={currentView === 'uploader'}
          onClick={() => onViewChange('uploader')}
        />
        <SidebarItem
          icon={<Database className="w-4 h-4" />}
          label="Forensics"
          active={currentView === 'data'}
          onClick={() => onViewChange('data')}
        />
      </nav>

      <div className="p-4 border-t border-white/10 bg-white/5">
        <div className="flex items-center gap-3">
          <div className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-white">System Online</span>
            <span className="text-[10px] text-muted-foreground font-mono">v2.4.0-stable</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
