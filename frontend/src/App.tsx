
import React, { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { ShieldCheck, Database, LayoutDashboard } from 'lucide-react';
import ComplianceDashboard from './components/ComplianceDashboard';
import DataViewer from './components/DataViewer';
import PolicyUploader from './components/PolicyUploader';
import { ThemeProvider } from './components/ThemeProvider';
import { ModeToggle } from './components/ModeToggle';

// Placeholder for now, we will move these components later
const AppShell = ({ children }: { children: React.ReactNode }) => (
  <div className="min-h-screen bg-background text-foreground font-sans antialiased transition-colors duration-300">
    {children}
  </div>
);

const SidebarItem = ({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) => (
  <button
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${active
      ? 'bg-primary/10 text-primary'
      : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
      }`}
  >
    {icon}
    {label}
  </button>
);

const App: React.FC = () => {
  const [view, setView] = useState<'dashboard' | 'uploader' | 'data'>('dashboard');

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <AppShell>
          <div className="flex h-screen overflow-hidden">
            {/* Sidebar */}
            <aside className="w-64 border-r border-border bg-card hidden md:flex flex-col">
              <div className="p-6 border-b border-border">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-6 h-6 text-primary" />
                  <span className="font-bold text-lg tracking-tight">VeriDoc</span>
                </div>
              </div>
              <nav className="flex-1 p-4 space-y-1">
                <SidebarItem
                  icon={<LayoutDashboard className="w-4 h-4" />}
                  label="Dashboard"
                  active={view === 'dashboard'}
                  onClick={() => setView('dashboard')}
                />
                <SidebarItem
                  icon={<ShieldCheck className="w-4 h-4" />}
                  label="Policy Engine"
                  active={view === 'uploader'}
                  onClick={() => setView('uploader')}
                />
                <SidebarItem
                  icon={<Database className="w-4 h-4" />}
                  label="Forensic Data"
                  active={view === 'data'}
                  onClick={() => setView('data')}
                />
              </nav>
              <div className="p-4 border-t border-border">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-medium text-muted-foreground">System Online</span>
                </div>
              </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-background/50 backdrop-blur-sm">
              {/* Header */}
              <header className="h-14 border-b border-border flex items-center justify-between px-6 bg-background/80 backdrop-blur-md sticky top-0 z-10">
                <span className="text-sm text-muted-foreground">
                  VeriDoc / <span className="text-foreground font-medium capitalize">{view.replace('_', ' ')}</span>
                </span>
                <div className="flex items-center gap-4">
                  <ModeToggle />
                </div>
              </header>

              <div className="p-6 max-w-7xl mx-auto space-y-6">
                {view === 'dashboard' && <ComplianceDashboard />}
                {view === 'uploader' && <PolicyUploader onUploadSuccess={() => { }} />}
                {view === 'data' && <DataViewer />}
              </div>
            </main>
          </div>
        </AppShell>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;

