import React, { useState, useEffect } from 'react';
import { X, AlertTriangle, CheckCircle, XCircle, FileText, ChevronRight, Clock } from 'lucide-react';
import { ViolationDetail, ViolatingRecord } from '../types';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { cn } from '../lib/utils';
import { api } from '../lib/api';

export interface AuditEntry {
    id: string;
    rule_id: string;
    description: string;
    action: 'APPROVED' | 'REJECTED' | 'UNDO';
    reviewer: string;
    timestamp: string;
    record_preview: string;
    record_ids?: string[];
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
const RecordTable: React.FC<{
    records: ViolatingRecord[],
    selectedIds: Set<string>,
    onToggleSelection: (id: string) => void,
    onToggleAll: (allIds: string[], forceState?: boolean) => void
}> = ({ records, selectedIds, onToggleSelection, onToggleAll }) => {
    const [isExpanded, setIsExpanded] = React.useState(false);

    if (!records || records.length === 0) {
        return <p className="text-sm text-muted-foreground text-center py-4">No records available.</p>;
    }

    // Ensure we don't display massive amounts in frontend gracefully
    const displayLimit = isExpanded ? 500 : 5;
    const displayRecords = records.slice(0, displayLimit);
    const columns = Object.keys(displayRecords[0]).filter(col => col !== 'id');

    // We assume every record has an "id", but fallback to the first column if missing
    const allIds = displayRecords.map(r => String(r.id || r[Object.keys(r)[0]]));
    const isAllSelected = allIds.length > 0 && allIds.every(id => selectedIds.has(id));

    return (
        <div className="overflow-x-auto rounded-lg border border-white/10 max-h-[400px]">
            <table className="w-full text-xs">
                <thead className="sticky top-0 z-10 bg-slate-800">
                    <tr className="bg-white/5 border-b border-white/10">
                        <th className="px-3 py-2 text-left w-8">
                            <input
                                type="checkbox"
                                className="rounded border-white/20 bg-white/5 cursor-pointer"
                                checked={isAllSelected}
                                onChange={(e) => onToggleAll(allIds, e.target.checked)}
                            />
                        </th>
                        {columns.map(col => (
                            <th key={col} className="px-3 py-2 text-left text-muted-foreground font-medium whitespace-nowrap">
                                {col.replace(/_/g, ' ').toUpperCase()}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {displayRecords.map((row, i) => {
                        const rowId = String(row.id || row[Object.keys(row)[0]]);
                        const isSelected = selectedIds.has(rowId);
                        return (
                            <tr key={i} className={cn("border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer",
                                isSelected ? 'bg-indigo-500/10 hover:bg-indigo-500/20' : (i % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.02]')
                            )} onClick={() => onToggleSelection(rowId)}>
                                <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                                    <input
                                        type="checkbox"
                                        className="rounded border-white/20 bg-white/5 cursor-pointer pointer-events-auto"
                                        checked={isSelected}
                                        onChange={() => onToggleSelection(rowId)}
                                    />
                                </td>
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
                        );
                    })}
                </tbody>
            </table>
            {!isExpanded && records.length > 5 && (
                <div className="p-3 text-center border-t border-white/10 bg-white/[0.01]">
                    <Button variant="ghost" size="sm" onClick={() => setIsExpanded(true)} className="text-xs w-full text-indigo-400 hover:text-indigo-300 hover:bg-indigo-400/10">
                        Expand All Records ({records.length})
                    </Button>
                </div>
            )}
            {isExpanded && records.length > 5 && (
                <div className="p-3 text-center border-t border-white/10 bg-white/[0.01] flex flex-col items-center gap-1">
                    {records.length > 500 && (
                        <p className="text-xs text-muted-foreground">Showing top 500 of {records.length} records.</p>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => {
                        setIsExpanded(false);
                        // Optional: Scroll back to the top of the table if it was long
                        document.querySelector('.max-h-\\[400px\\]')?.scrollTo({ top: 0, behavior: 'smooth' });
                    }} className="text-xs text-muted-foreground hover:text-white hover:bg-white/10">
                        Minimize Records
                    </Button>
                </div>
            )}
        </div>
    );
};

// --- Main Modal ---
interface ViolationDrillDownProps {
    violation: ViolationDetail | null;
    onClose: () => void;
    onStatusChange?: () => void;
}

const ViolationDrillDown: React.FC<ViolationDrillDownProps> = ({ violation, onClose, onStatusChange }) => {
    const [reviewStatus, setReviewStatus] = useState<'APPROVED' | 'REJECTED' | null>(null);
    const [justification, setJustification] = useState('');
    const [showJustification, setShowJustification] = useState(false);
    const [pendingAction, setPendingAction] = useState<'APPROVED' | 'REJECTED' | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [allRecords, setAllRecords] = useState<ViolatingRecord[]>([]);
    const [selectedRecordIds, setSelectedRecordIds] = useState<Set<string>>(new Set());
    const [isLoadingRecords, setIsLoadingRecords] = useState(false);

    useEffect(() => {
        if (violation) {
            setReviewStatus(violation.review_status as any ?? null);
            setJustification('');
            setShowJustification(false);
            setPendingAction(null);
            setSelectedRecordIds(new Set());

            // Fetch all records
            setIsLoadingRecords(true);
            api.get<{ records: ViolatingRecord[] }>(`/compliance/rule/${violation.policy_id}/${violation.rule_id}/records`)
                .then(res => {
                    setAllRecords(res.records || []);
                })
                .catch(err => {
                    console.error("Failed to load full records:", err);
                    setAllRecords(violation.violating_records || []); // Fallback to sample
                })
                .finally(() => {
                    setIsLoadingRecords(false);
                });
        }
    }, [violation]);

    const handleToggleSelection = (id: string) => {
        setSelectedRecordIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const handleToggleAll = (allIds: string[], forceState?: boolean) => {
        setSelectedRecordIds(prev => {
            const next = new Set(prev);
            const isAllCurrentlySelected = allIds.length > 0 && allIds.every(id => next.has(id));
            const shouldSelect = forceState !== undefined ? forceState : !isAllCurrentlySelected;

            allIds.forEach(id => {
                if (shouldSelect) next.add(id);
                else next.delete(id);
            });
            return next;
        });
    };

    if (!violation) return null;

    const handleActionClick = (action: 'APPROVED' | 'REJECTED') => {
        setPendingAction(action);
        setShowJustification(true);
    };

    const handleConfirm = async () => {
        if (!pendingAction) return;
        setIsSubmitting(true);

        const isPartialReview = selectedRecordIds.size > 0 && selectedRecordIds.size < allRecords.length;
        const entry: AuditEntry = {
            id: `${violation.rule_id}-${Date.now()}`,
            rule_id: violation.rule_id,
            description: violation.description,
            action: pendingAction,
            reviewer: 'Compliance Officer',
            timestamp: new Date().toISOString(),
            record_preview: justification || `${isPartialReview ? selectedRecordIds.size : (violation.total_matches ?? '?')} records reviewed`,
            record_ids: isPartialReview ? Array.from(selectedRecordIds) : undefined
        };
        try {
            await api.post('/audit/log', entry);
            // If partial, we don't necessarily mark the rule as fully triaged
            if (!isPartialReview) {
                setReviewStatus(pendingAction);
            } else {
                setSelectedRecordIds(new Set()); // Clear selection on success
            }
            setShowJustification(false);
            if (onStatusChange) onStatusChange();
        } catch (err) {
            console.error(err);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleUndo = async () => {
        setIsSubmitting(true);
        const entry: AuditEntry = {
            id: `undo-${Date.now()}`,
            rule_id: violation.rule_id,
            description: violation.description,
            action: 'UNDO',
            reviewer: 'Compliance Officer',
            timestamp: new Date().toISOString(),
            record_preview: '',
        };
        try {
            await api.post('/audit/log', entry);
            setReviewStatus(null);
            setShowJustification(false);
            if (onStatusChange) onStatusChange();
        } catch (err) {
            console.error(err);
        } finally {
            setIsSubmitting(false);
        }
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
                                Violating Records
                                {isLoadingRecords ? (
                                    <span className="text-xs text-muted-foreground font-normal animate-pulse">(Loading all {violation.total_matches} records...)</span>
                                ) : (
                                    <span className="text-xs text-muted-foreground font-normal">(Select specific rows to approve/reject individually)</span>
                                )}
                            </h3>
                            {selectedRecordIds.size > 0 && (
                                <Badge variant="secondary" className="bg-primary/20 text-primary border-primary/30">
                                    {selectedRecordIds.size} selected
                                </Badge>
                            )}
                        </div>
                        <RecordTable
                            records={allRecords.length > 0 ? allRecords : (violation.violating_records ?? [])}
                            selectedIds={selectedRecordIds}
                            onToggleSelection={handleToggleSelection}
                            onToggleAll={handleToggleAll}
                        />
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
                                    <Button variant="ghost" size="sm" className="ml-auto text-xs" onClick={handleUndo} disabled={isSubmitting}>
                                        {isSubmitting ? '...' : 'Undo'}
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
                                        disabled={isSubmitting}
                                        className="w-full h-20 px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none disabled:opacity-50"
                                    />
                                    <div className="flex gap-2">
                                        <Button size="sm" onClick={handleConfirm} disabled={isSubmitting}
                                            className={pendingAction === 'APPROVED' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'}>
                                            {isSubmitting ? 'Saving...' : `Confirm ${pendingAction === 'APPROVED' ? 'Approval' : 'Rejection'}`}
                                        </Button>
                                        <Button size="sm" variant="ghost" onClick={() => setShowJustification(false)} disabled={isSubmitting}>Cancel</Button>
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
                                            Confirm Violation {selectedRecordIds.size > 0 && selectedRecordIds.size < allRecords.length ? `(${selectedRecordIds.size})` : ''}
                                        </Button>
                                        <Button size="sm" variant="outline" onClick={() => handleActionClick('REJECTED')}
                                            className="border-white/20 hover:bg-white/10 flex items-center gap-2">
                                            <XCircle className="w-3.5 h-3.5" />
                                            False Positive {selectedRecordIds.size > 0 && selectedRecordIds.size < allRecords.length ? `(${selectedRecordIds.size})` : ''}
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
