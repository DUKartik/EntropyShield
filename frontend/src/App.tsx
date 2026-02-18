
import React, { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import ComplianceDashboard from './components/ComplianceDashboard';
import DataViewer from './components/DataViewer';
import PolicyUploader from './components/PolicyUploader';
import { ThemeProvider } from './components/ThemeProvider';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';

// Background shell with subtle gradient or noise if desired
const AppShell = ({ children }: { children: React.ReactNode }) => (
  <div className="min-h-screen bg-slate-950 text-foreground font-sans antialiased selection:bg-primary/20 selection:text-white">
    {children}
  </div>
);

const App: React.FC = () => {
  const [view, setView] = useState<'dashboard' | 'uploader' | 'data'>('dashboard');

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <AppShell>
          <div className="flex h-screen">
            <Sidebar currentView={view} onViewChange={setView} />

            <main className="flex-1 flex flex-col min-h-0 relative">
              <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent opacity-50 z-0"></div>

              {/* Header is OUTSIDE the scroll container — always fixed height */}
              <Header currentView={view} />

              {/* Scrollable content below header */}
              <div className="flex-1 overflow-y-auto">
                <div className="p-6 md:p-8 max-w-[1600px] mx-auto space-y-8 w-full relative z-10">
                  {view === 'dashboard' && <ComplianceDashboard />}
                  {view === 'uploader' && <PolicyUploader onUploadSuccess={() => { }} />}
                  {view === 'data' && <DataViewer />}
                </div>
              </div>
            </main>
          </div>
        </AppShell>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;


