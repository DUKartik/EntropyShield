import React, { useState, useEffect } from 'react';
import { X, AlertTriangle, CheckCircle, XCircle, FileText, ChevronRight, Clock } from 'lucide-react';
import { ViolationDetail, ViolatingRecord } from '../types';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

// --- Audit log stored in localStorage ---
const AUDIT_KEY = 'entropyshield_audit_log';

export interface AuditEntry {
    id: string;
    rule_id: string;
    description: string;
    action: 'APPROVED' | 'REJECTED';
    reviewer: string;
    timestamp: string;
    record_preview: string;
}

export function loadAuditLog(): AuditEntry[] {
    try { return JSON.parse(localStorage.getItem(AUDIT_KEY) || '[]'); }
    catch { return []; }
}

function saveAuditEntry(entry: AuditEntry) {
    const log = loadAuditLog();
    localStorage.setItem(AUDIT_KEY, JSON.stringify([entry, ...log].slice(0, 100)));
}

function getReviewStatus(ruleId: string): 'APPROVED' | 'REJECTED' | null {
    const log = loadAuditLog();
    const entry = log.find(e => e.rule_id === ruleId);
    return entry?.action ?? null;
}

// --- Format cell values nicely ---
function formatValue(val: any): string {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'number') {
        if (val > 1000) return val.toLocaleString('en-US', { maximumFractionDigits: 2 });
        return String(val);
    }
    if (typeof val === 'string' && val.length > 40) return val.slice(0, 40) + '…';
    return String(val);
}

// --- Record Table ---
const RecordTable: React.FC<{ records: ViolatingRecord[] }> = ({ records }) => {
    if (!records || records.length === 0) {
        return <p className="text-sm text-muted-foreground text-center py-4">No sample records available.</p>;
    }
    const columns = Object.keys(records[0]);
    return (
        <div className="overflow-x-auto rounded-lg border border-white/10">
            <table className="w-full text-xs">
                <thead>
                    <tr className="bg-white/5 border-b border-white/10">
                        {columns.map(col => (
                            <th key={col} className="px-3 py-2 text-left text-muted-foreground font-medium whitespace-nowrap">
                                {col.replace(/_/g, ' ').toUpperCase()}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {records.map((row, i) => (
                        <tr key={i} className={cn("border-b border-white/5 hover:bg-white/5 transition-colors",
                            i % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.02]')}>
                            {columns.map(col => (
                                <td key={col} className={cn("px-3 py-2 whitespace-nowrap font-mono",
                                    col === 'is_laundering' && row[col] === 1 ? 'text-rose-400 font-bold' :
                                        col.includes('amount') || col.includes('paid') ? 'text-emerald-400' :
                                            'text-foreground/80'
                                )}>
                                    {col === 'is_laundering' ? (row[col] === 1 ? '🚨 YES' : '✅ NO') : formatValue(row[col])}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

// --- Main Modal ---
interface ViolationDrillDownProps {
    violation: ViolationDetail | null;
    onClose: () => void;
}

const ViolationDrillDown: React.FC<ViolationDrillDownProps> = ({ violation, onClose }) => {
    const [reviewStatus, setReviewStatus] = useState<'APPROVED' | 'REJECTED' | null>(null);
    const [justification, setJustification] = useState('');
    const [showJustification, setShowJustification] = useState(false);
    const [pendingAction, setPendingAction] = useState<'APPROVED' | 'REJECTED' | null>(null);

    useEffect(() => {
        if (violation) {
            setReviewStatus(getReviewStatus(violation.rule_id));
            setJustification('');
            setShowJustification(false);
            setPendingAction(null);
        }
    }, [violation]);

    if (!violation) return null;

    const handleActionClick = (action: 'APPROVED' | 'REJECTED') => {
        setPendingAction(action);
        setShowJustification(true);
    };

    const handleConfirm = () => {
        if (!pendingAction) return;
        const entry: AuditEntry = {
            id: `${violation.rule_id}-${Date.now()}`,
            rule_id: violation.rule_id,
            description: violation.description,
            action: pendingAction,
            reviewer: 'Compliance Officer',
            timestamp: new Date().toISOString(),
            record_preview: justification || `${violation.total_matches ?? '?'} records reviewed`,
        };
        saveAuditEntry(entry);
        setReviewStatus(pendingAction);
        setShowJustification(false);
    };

    const severityColor = violation.severity === 'HIGH'
        ? 'text-rose-400 bg-rose-500/10 border-rose-500/20'
        : violation.severity === 'MEDIUM'
            ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
            : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';

    return (
        // Backdrop — starts below the 64px header so nothing is hidden
        <div
            className="fixed top-16 inset-x-0 bottom-0 z-50 flex items-start justify-center p-4 pt-6 bg-black/60 backdrop-blur-sm overflow-y-auto"
            onClick={onClose}
        >
            {/* Modal */}
            <div
                className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-white/10 rounded-2xl shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur-md border-b border-white/10 px-6 py-4 flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 min-w-0">
                        <div className={cn("p-2 rounded-lg flex-shrink-0 mt-0.5", severityColor)}>
                            <AlertTriangle className="w-5 h-5" />
                        </div>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-xs text-muted-foreground">{violation.rule_id}</span>
                                <Badge variant={violation.severity === 'HIGH' ? 'destructive' : 'secondary'} className="text-[10px]">
                                    {violation.severity}
                                </Badge>
                                {reviewStatus && (
                                    <Badge className={cn("text-[10px]",
                                        reviewStatus === 'APPROVED' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/20 text-rose-400 border-rose-500/20'
                                    )}>
                                        {reviewStatus === 'APPROVED' ? '✓ Approved' : '✗ Rejected'}
                                    </Badge>
                                )}
                            </div>
                            <h2 className="text-base font-semibold text-white mt-1">{violation.description}</h2>
                        </div>
                    </div>
                    <button onClick={onClose} className="flex-shrink-0 p-1.5 rounded-lg hover:bg-white/10 transition-colors text-muted-foreground hover:text-white">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 space-y-6">
                    {/* Policy Quote */}
                    <div className="flex gap-3 p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
                        <FileText className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="text-xs text-indigo-400 font-medium mb-1">Policy Basis</p>
                            <p className="text-sm text-foreground/80 italic">"{violation.quote}"</p>
                        </div>
                    </div>

                    {/* Stats row */}
                    <div className="grid grid-cols-3 gap-3">
                        <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-center">
                            <p className="text-2xl font-bold text-rose-400">{(violation.total_matches ?? 0).toLocaleString()}</p>
                            <p className="text-xs text-muted-foreground mt-1">Total Records Affected</p>
                        </div>
                        <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-center">
                            <p className="text-2xl font-bold text-amber-400">{violation.violating_records?.length ?? 0}</p>
                            <p className="text-xs text-muted-foreground mt-1">Sample Records Shown</p>
                        </div>
                        <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-center">
                            <p className="text-2xl font-bold text-indigo-400">{violation.policy_name?.split(' ')[0] ?? '—'}</p>
                            <p className="text-xs text-muted-foreground mt-1">Policy</p>
                        </div>
                    </div>

                    {/* Sample Records Table */}
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                                <ChevronRight className="w-4 h-4 text-muted-foreground" />
                                Sample Violating Records
                                <span className="text-xs text-muted-foreground font-normal">(showing up to 5 of {(violation.total_matches ?? 0).toLocaleString()})</span>
                            </h3>
                        </div>
                        <RecordTable records={violation.violating_records ?? []} />
                    </div>

                    {/* Human Review Section */}
                    <div className="border border-white/10 rounded-xl overflow-hidden">
                        <div className="px-4 py-3 bg-white/5 border-b border-white/10 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Human Review</span>
                            <span className="text-xs text-muted-foreground ml-auto">Required for audit trail</span>
                        </div>
                        <div className="p-4">
                            {reviewStatus ? (
                                <div className={cn("flex items-center gap-3 p-3 rounded-lg",
                                    reviewStatus === 'APPROVED' ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-rose-500/10 border border-rose-500/20'
                                )}>
                                    {reviewStatus === 'APPROVED'
                                        ? <CheckCircle className="w-5 h-5 text-emerald-400" />
                                        : <XCircle className="w-5 h-5 text-rose-400" />}
                                    <div>
                                        <p className={cn("text-sm font-medium", reviewStatus === 'APPROVED' ? 'text-emerald-400' : 'text-rose-400')}>
                                            {reviewStatus === 'APPROVED' ? 'Violation Approved — Escalated for remediation' : 'Violation Rejected — Marked as false positive'}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-0.5">Reviewed by Compliance Officer · Logged to audit trail</p>
                                    </div>
                                    <Button variant="ghost" size="sm" className="ml-auto text-xs" onClick={() => setReviewStatus(null)}>
                                        Undo
                                    </Button>
                                </div>
                            ) : showJustification ? (
                                <div className="space-y-3">
                                    <p className="text-sm text-muted-foreground">
                                        {pendingAction === 'APPROVED' ? '✅ Approving violation — add notes (optional):' : '❌ Rejecting as false positive — add reason (optional):'}
                                    </p>
                                    <textarea
                                        value={justification}
                                        onChange={e => setJustification(e.target.value)}
                                        placeholder="Add reviewer notes..."
                                        className="w-full h-20 px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                                    />
                                    <div className="flex gap-2">
                                        <Button size="sm" onClick={handleConfirm}
                                            className={pendingAction === 'APPROVED' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'}>
                                            Confirm {pendingAction === 'APPROVED' ? 'Approval' : 'Rejection'}
                                        </Button>
                                        <Button size="sm" variant="ghost" onClick={() => setShowJustification(false)}>Cancel</Button>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <p className="text-sm text-muted-foreground">
                                        Review this violation and take action. Your decision will be logged to the audit trail.
                                    </p>
                                    <div className="flex gap-3">
                                        <Button size="sm" onClick={() => handleActionClick('APPROVED')}
                                            className="bg-rose-600 hover:bg-rose-700 flex items-center gap-2">
                                            <AlertTriangle className="w-3.5 h-3.5" />
                                            Confirm Violation
                                        </Button>
                                        <Button size="sm" variant="outline" onClick={() => handleActionClick('REJECTED')}
                                            className="border-white/20 hover:bg-white/10 flex items-center gap-2">
                                            <XCircle className="w-3.5 h-3.5" />
                                            False Positive
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ViolationDrillDown;
