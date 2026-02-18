
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { ShieldAlert, CheckCircle, TrendingUp, AlertTriangle, ArrowUpRight } from 'lucide-react';
import { api } from '../lib/api';
import { ComplianceReport, ViolationDetail } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';

// --- MOCK CHART DATA ---
const chartData = [
  { time: '09:00', violations: 2, safe: 140 },
  { time: '10:00', violations: 5, safe: 120 },
  { time: '11:00', violations: 1, safe: 180 },
  { time: '12:00', violations: 8, safe: 150 },
  { time: '13:00', violations: 3, safe: 200 },
  { time: '14:00', violations: 0, safe: 170 },
  { time: '15:00', violations: 4, safe: 190 },
];

// --- COMPONENTS ---

const KpiCard = ({ title, value, icon, trend, color }: { title: string, value: string | number, icon: React.ReactNode, trend?: string, color: string }) => (
  <Card className="bg-card/40 backdrop-blur-sm border-border overflow-hidden relative">
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium text-muted-foreground">
        {title}
      </CardTitle>
      <div className={cn("p-2 rounded-full", color)}>
        {icon}
      </div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
      {trend && (
        <p className="text-xs text-emerald-500 flex items-center mt-1">
          <TrendingUp className="w-3 h-3 mr-1" />
          {trend} from last hour
        </p>
      )}
      {/* Background Decor */}
      <div className={cn("absolute -right-6 -bottom-6 w-24 h-24 rounded-full opacity-10 blur-xl", color.replace('text-', 'bg-').replace('/10', ''))} />
    </CardContent>
  </Card>
);

const ViolationItem: React.FC<{ violation: ViolationDetail }> = ({ violation }) => (
  <motion.div
    initial={{ opacity: 0, x: -20 }}
    animate={{ opacity: 1, x: 0 }}
    className="flex items-center justify-between p-4 rounded-lg bg-card/60 border border-border/50 hover:bg-card/80 transition-colors group"
  >
    <div className="flex items-center gap-4">
      <div className={cn("p-2 rounded-full", violation.severity === 'HIGH' ? 'bg-rose-500/10 text-rose-500' : 'bg-amber-500/10 text-amber-500')}>
        <AlertTriangle className="w-4 h-4" />
      </div>
      <div>
        <p className="font-medium text-sm text-foreground group-hover:text-primary transition-colors">
          {violation.rule_id}
        </p>
        <p className="text-xs text-muted-foreground truncate w-64">
          {violation.violation_reason}
        </p>
      </div>
    </div>
    <div className="text-right">
      <Badge variant={violation.severity === 'HIGH' ? 'destructive' : 'secondary'} className="mb-1">
        {violation.severity}
      </Badge>
      <p className="text-[10px] text-muted-foreground font-mono">
        Running
      </p>
    </div>
  </motion.div>
);

// --- MAIN DASHBOARD ---

const ComplianceDashboard: React.FC = () => {
  // Polling simulation for "Live" feel
  const { data: report, isLoading } = useQuery({
    queryKey: ['compliance-report'],
    queryFn: async () => {
      // In a real app we might just run check or get stats.
      // Here we re-use the run endpoint as a stats generator for demo.
      return api.get<ComplianceReport>('/compliance/run');
    },
    refetchInterval: 5000
  });

  const stats = {
    totalViolations: report?.details.length || 0,
    highRisk: report?.details.filter(v => v.severity === 'HIGH').length || 0,
    activePolicies: 12 // Mock
  };

  return (
    <div className="space-y-6 pb-8">
      {/* HERO STATS - BENTO GRID TOP */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Risk Score"
          value="Low"
          icon={<ShieldAlert className="w-4 h-4" />}
          color="bg-emerald-500/10 text-emerald-500"
        />
        <KpiCard
          title="Total Violations"
          value={stats.totalViolations}
          icon={<AlertTriangle className="w-4 h-4" />}
          trend="+2.5%"
          color="bg-rose-500/10 text-rose-500"
        />
        <KpiCard
          title="Active Policies"
          value={stats.activePolicies}
          icon={<CheckCircle className="w-4 h-4" />}
          color="bg-indigo-500/10 text-indigo-500"
        />
        <KpiCard
          title="Real-time Events"
          value="142"
          icon={<ArrowUpRight className="w-4 h-4" />}
          trend="+12%"
          color="bg-amber-500/10 text-amber-500"
        />
      </div>

      {/* MAIN CONTENT GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[500px]">

        {/* LEFT: CHART AREA */}
        <Card className="lg:col-span-2 bg-card/40 backdrop-blur-sm border-border">
          <CardHeader>
            <CardTitle>Compliance Velocity</CardTitle>
          </CardHeader>
          <CardContent className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorViolations" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorSafe" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#525252" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#525252" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1c1917', border: '1px solid #262626' }}
                  itemStyle={{ color: '#d4d4d4' }}
                />
                <Area type="monotone" dataKey="violations" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorViolations)" />
                <Area type="monotone" dataKey="safe" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorSafe)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* RIGHT: VIOLATION FEED */}
        <Card className="bg-card/40 backdrop-blur-sm border-border flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Live Violations
              <Badge variant="outline" className="animate-pulse text-rose-500 border-rose-500/20 bg-rose-500/10">LIVE</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => <div key={i} className="h-16 bg-muted/50 rounded-lg animate-pulse" />)}
              </div>
            ) : report?.details.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-center">
                <CheckCircle className="w-10 h-10 mb-2 opacity-20" />
                <p>System Clean</p>
              </div>
            ) : (
              report?.details.map((v, i) => (
                <ViolationItem key={i} violation={v} />
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ComplianceDashboard;

