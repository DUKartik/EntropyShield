
import React from 'react';
import { ShieldCheck, LayoutDashboard, FileText, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  currentView: 'dashboard' | 'data';
  onViewChange: (view: 'dashboard' | 'data') => void;
  collapsed: boolean;
  onToggle: () => void;
}

const SidebarItem = ({
  icon,
  label,
  active,
  onClick,
  collapsed,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  collapsed: boolean;
}) => (
  <button
    onClick={onClick}
    title={collapsed ? label : undefined}
    className={cn(
      "w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-300",
      collapsed ? "justify-center" : "",
      active
        ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_15px_rgba(56,189,248,0.1)]"
        : "text-muted-foreground hover:bg-white/5 hover:text-foreground hover:border-white/10 border border-transparent"
    )}
  >
    {icon}
    {!collapsed && <span className="truncate">{label}</span>}
  </button>
);

export const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange, collapsed, onToggle }) => {
  return (
    <aside className={cn(
      "border-r border-white/10 bg-slate-950/50 backdrop-blur-xl hidden md:flex flex-col h-full sticky top-0 z-30 transition-all duration-300",
      collapsed ? "w-16" : "w-64"
    )}>
      {/* Logo */}
      <div className={cn("p-4 border-b border-white/10 flex items-center", collapsed ? "justify-center" : "gap-3")}>
        <div className="relative flex-shrink-0">
          <ShieldCheck className="w-7 h-7 text-primary" />
          <div className="absolute inset-0 bg-primary/20 blur-md rounded-full animate-pulse" />
        </div>
        {!collapsed && (
          <span className="font-bold text-xl tracking-tight text-white">
            Entropy<span className="text-primary">Shield</span>
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-2">
        {!collapsed && (
          <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Platform
          </div>
        )}
        <SidebarItem
          icon={<LayoutDashboard className="w-4 h-4 flex-shrink-0" />}
          label="Overview"
          active={currentView === 'dashboard'}
          onClick={() => onViewChange('dashboard')}
          collapsed={collapsed}
        />
        <SidebarItem
          icon={<FileText className="w-4 h-4 flex-shrink-0" />}
          label="Policies"
          active={currentView === 'data'}
          onClick={() => onViewChange('data')}
          collapsed={collapsed}
        />
      </nav>

      {/* Footer */}
      <div className={cn("p-4 border-t border-white/10 bg-white/5 space-y-3")}>
        {!collapsed && (
          <div className="flex items-center gap-3">
            <div className="relative flex h-2.5 w-2.5 flex-shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-semibold text-white">System Online</span>
              <span className="text-[10px] text-muted-foreground font-mono">v2.4.0-stable</span>
            </div>
          </div>
        )}

        {/* Collapse toggle button */}
        <button
          onClick={onToggle}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs text-muted-foreground hover:bg-white/10 hover:text-white transition-colors border border-transparent hover:border-white/10",
            collapsed ? "justify-center" : ""
          )}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed
            ? <ChevronRight className="w-4 h-4" />
            : <><ChevronLeft className="w-4 h-4" /><span>Collapse</span></>
          }
        </button>
      </div>
    </aside>
  );
};
