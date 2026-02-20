
import React, { useMemo, useCallback, useState } from 'react';
import ViolationDrillDown from './ViolationDrillDown';
import { useQuery } from '@tanstack/react-query';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { ShieldAlert, CheckCircle, XCircle, TrendingUp, AlertTriangle, ArrowUpRight, History } from 'lucide-react';
import { api } from '../lib/api';
import { ComplianceReport, ViolationDetail, SystemStats } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

// --- SCAN HISTORY (localStorage) ---
const HISTORY_KEY = 'entropyshield_scan_history';
const MAX_HISTORY = 12; // Keep last 12 scans

interface ScanSnapshot {
  time: string;   // e.g. "10:32"
  date: string;   // e.g. "Feb 18"
  HIGH: number;
  MEDIUM: number;
  LOW: number;
  total: number;
}

function loadHistory(): ScanSnapshot[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveSnapshot(report: ComplianceReport) {
  const history = loadHistory();
  const now = new Date();
  const snapshot: ScanSnapshot = {
    time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    date: now.toLocaleDateString([], { month: 'short', day: 'numeric' }),
    HIGH: report.details.filter(v => v.severity === 'HIGH').length,
    MEDIUM: report.details.filter(v => v.severity === 'MEDIUM').length,
    LOW: report.details.filter(v => v.severity === 'LOW').length,
    total: report.total_violations,
  };
  const updated = [...history, snapshot].slice(-MAX_HISTORY);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
  return updated;
}

// --- COMPONENTS ---

const KpiCard = ({ title, value, icon, trend, color }: {
  title: string, value: string | number, icon: React.ReactNode, trend?: string, color: string
}) => (
  <Card className="bg-white/5 backdrop-blur-lg border-white/10 shadow-2xl overflow-hidden relative">
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      <div className={cn("p-2 rounded-full flex-shrink-0", color)}>{icon}</div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold truncate">{value}</div>
      {trend && (
        <p className="text-xs text-emerald-500 flex items-center mt-1">
          <TrendingUp className="w-3 h-3 mr-1 flex-shrink-0" />
          {trend} from last scan
        </p>
      )}
    </CardContent>
  </Card>
);

const ViolationItem: React.FC<{ violation: ViolationDetail; onClick: () => void }> = ({ violation, onClick }) => (
  <div
    className={cn(
      "p-3 rounded-lg border transition-colors cursor-pointer group",
      violation.review_status
        ? "bg-card/20 border-white/5 hover:bg-card/40 opacity-70"
        : "bg-card/60 border-border/50 hover:bg-card/80 hover:border-white/20"
    )}
    onClick={onClick}
  >
    <div className="flex items-start justify-between gap-2">
      <div className="flex items-start gap-3 min-w-0">
        <div className={cn("p-1.5 rounded-full flex-shrink-0 mt-0.5",
          violation.review_status === 'APPROVED' ? 'bg-emerald-500/10 text-emerald-500' :
            violation.review_status === 'REJECTED' ? 'bg-rose-500/10 text-rose-500' :
              violation.severity === 'HIGH' ? 'bg-rose-500/10 text-rose-500' : 'bg-amber-500/10 text-amber-500')}>
          {violation.review_status === 'APPROVED' ? <CheckCircle className="w-3.5 h-3.5" /> :
            violation.review_status === 'REJECTED' ? <XCircle className="w-3.5 h-3.5" /> :
              <AlertTriangle className="w-3.5 h-3.5" />}
        </div>
        <div className="min-w-0">
          <p className="font-medium text-sm text-foreground flex items-center gap-2">
            {violation.rule_id}
            {violation.review_status && (
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground bg-white/10 px-1.5 py-0.5 rounded">
                Triaged
              </span>
            )}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5 break-words">{violation.violation_reason}</p>
          {violation.total_matches != null && (
            <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono">
              {violation.total_matches.toLocaleString()} records affected
              {violation.review_status && " (excluded from total)"}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-col items-end gap-1 flex-shrink-0">
        <Badge
          variant={violation.severity === 'HIGH' ? 'destructive' : 'secondary'}
          className={cn("text-[10px]", violation.review_status && "opacity-50")}
        >
          {violation.severity}
        </Badge>
        <span className="text-[10px] text-muted-foreground/50 group-hover:text-muted-foreground transition-colors">View →</span>
      </div>
    </div>
  </div>
);

// --- MAIN DASHBOARD ---

const ComplianceDashboard: React.FC = () => {
  // Scan history state — stored in localStorage, updated after each scan
  const [history, setHistory] = React.useState<ScanSnapshot[]>(loadHistory);
  const [selectedViolation, setSelectedViolation] = useState<ViolationDetail | null>(null);

  const { data: report, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['compliance-report'],
    queryFn: async () => {
      const result = await api.get<ComplianceReport>('/compliance/run');
      // Save snapshot to history after each successful scan
      const updated = saveSnapshot(result);
      setHistory(updated);
      return result;
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const handleRunCheck = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleClearHistory = useCallback(() => {
    localStorage.removeItem(HISTORY_KEY);
    setHistory([]);
  }, []);

  const { data: statsData } = useQuery({
    queryKey: ['system-stats'],
    queryFn: () => api.get<SystemStats>('/system/stats'),
    refetchInterval: 30000,
    refetchOnWindowFocus: false,
  });

  const stats = {
    totalViolations: statsData?.total_violations ?? (report?.total_violations || 0),
    highRisk: report?.details.filter(v => v.severity === 'HIGH').length || 0,
    activePolicies: statsData?.active_policies ?? 0,
    riskScore: statsData?.risk_score ?? "—",
    events: statsData?.real_time_events ?? 0
  };

  // Chart data: time-series from scan history
  // Each point = one scan run, X axis = time, Y axis = violation counts by severity
  const chartData = useMemo(() => {
    if (history.length === 0) {
      return [{ time: 'No scans yet', HIGH: 0, MEDIUM: 0, LOW: 0 }];
    }
    return history.map(s => ({
      time: s.time,
      HIGH: s.HIGH,
      MEDIUM: s.MEDIUM,
      LOW: s.LOW,
    }));
  }, [history]);

  return (
    <div className="space-y-6 pb-8 w-full min-w-0">
      {/* KPI CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard title="Risk Score" value={stats.riskScore}
          icon={<ShieldAlert className="w-4 h-4" />} color="bg-emerald-500/10 text-emerald-500" />
        <KpiCard title="Total Violations" value={stats.totalViolations}
          icon={<AlertTriangle className="w-4 h-4" />} color="bg-rose-500/10 text-rose-500" />
        <KpiCard title="Active Policies" value={stats.activePolicies}
          icon={<CheckCircle className="w-4 h-4" />} color="bg-indigo-500/10 text-indigo-500" />
        <KpiCard title="Scans Run" value={history.length}
          icon={<ArrowUpRight className="w-4 h-4" />} color="bg-amber-500/10 text-amber-500" />
      </div>

      {/* MAIN CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* CHART */}
        <Card className="lg:col-span-2 bg-white/5 backdrop-blur-lg border-white/10 shadow-2xl min-w-0">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base">Compliance Velocity</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {history.length > 0
                    ? `${history.length} scan${history.length > 1 ? 's' : ''} recorded — each dot = one scan run`
                    : 'Run a scan to start recording history'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {history.length > 0 && (
                  <Button variant="ghost" size="sm" onClick={handleClearHistory}
                    className="text-muted-foreground hover:text-foreground text-xs h-8 px-2">
                    <History className="w-3 h-3 mr-1" /> Clear
                  </Button>
                )}
                <Button
                  variant="outline" size="sm"
                  onClick={handleRunCheck} disabled={isFetching}
                  className="bg-sky-500/10 text-sky-500 border-sky-500/20 hover:bg-sky-500/20 flex-shrink-0"
                >
                  <div className={cn("mr-2 h-4 w-4", isFetching && "animate-spin")}>
                    {isFetching
                      ? <div className="border-2 border-current border-t-transparent rounded-full w-full h-full" />
                      : <ShieldAlert className="w-full h-full" />}
                  </div>
                  {isFetching ? "Scanning..." : "Run System Scan"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div style={{ width: '100%', height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <defs>
                    <linearGradient id="gHigh" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gMedium" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gLow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" stroke="#525252" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#525252" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '12px' }}
                    itemStyle={{ color: '#d4d4d4' }}
                    labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                  <Area type="monotone" dataKey="HIGH" name="High Risk" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#gHigh)" dot={{ r: 4, fill: '#f43f5e' }} />
                  <Area type="monotone" dataKey="MEDIUM" name="Medium Risk" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#gMedium)" dot={{ r: 4, fill: '#f59e0b' }} />
                  <Area type="monotone" dataKey="LOW" name="Low Risk" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#gLow)" dot={{ r: 4, fill: '#10b981' }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* VIOLATION FEED */}
        <Card className="bg-white/5 backdrop-blur-lg border-white/10 shadow-2xl flex flex-col min-w-0">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Live Violations</CardTitle>
              <Badge variant="outline" className="animate-pulse text-rose-500 border-rose-500/20 bg-rose-500/10 text-[10px]">LIVE</Badge>
            </div>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto space-y-2 pr-1">
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => <div key={i} className="h-16 bg-muted/50 rounded-lg animate-pulse" />)}
              </div>
            ) : !report || report.details.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-muted-foreground text-center">
                <CheckCircle className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-sm">Run a scan to see violations</p>
              </div>
            ) : (
              report.details.slice(0, 20).map((v, i) => (
                <ViolationItem key={i} violation={v} onClick={() => setSelectedViolation(v)} />
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Drill-down modal */}
      <ViolationDrillDown
        violation={selectedViolation}
        onClose={() => setSelectedViolation(null)}
        onStatusChange={() => {
          refetch(); // Refetch the compliance data to update the KPIs and feed
          // also refetch system stats
        }}
      />
    </div>
  );
};

export default ComplianceDashboard;
