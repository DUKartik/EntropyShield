
import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    UploadCloud,
    FileText,
    CheckCircle,
    AlertTriangle,
    ShieldAlert,
    ScanLine,
    Trash2,
    Clock,
    Shield,
    ChevronDown,
    ChevronUp,
    X,
} from 'lucide-react';
import { api } from '../lib/api';
import { Policy, Rule } from '../types';
import { Switch } from './ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { cn } from '../lib/utils';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

/* ───────────────────── Types ───────────────────── */
interface UploadResponse {
    status: string;
    policy_id: string;
    data: Policy;
}

interface PolicyListItem {
    policy_id: string;
    name: string;
    rules: Rule[];
    rule_count: number;
    created_at: string | null;
}

/* ───────────────────── Policy Card ───────────────────── */
const PolicyCard: React.FC<{
    policy: PolicyListItem;
    onDelete: (id: string) => void;
    isDeleting: boolean;
    onRuleClick: (rule: Rule) => void;
}> = ({ policy, onDelete, isDeleting, onRuleClick }) => {
    const [expanded, setExpanded] = useState(false);

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -5 }}
            transition={{ duration: 0.25 }}
        >
            <Card className="group relative overflow-hidden bg-white/5 backdrop-blur-lg border-white/10 shadow-2xl hover:border-sky-400/30 transition-all duration-300">
                {/* Subtle glow line on top */}
                <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-sky-400/40 to-transparent" />

                <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                            <div className="p-2 bg-sky-400/10 rounded-lg flex-shrink-0">
                                <FileText className="w-5 h-5 text-sky-400" />
                            </div>
                            <div className="min-w-0">
                                <CardTitle className="text-sm font-semibold text-white truncate">
                                    {policy.name}
                                </CardTitle>
                                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                        <Shield className="w-3 h-3" />
                                        {policy.rule_count} rule{policy.rule_count !== 1 ? 's' : ''}
                                    </span>
                                    {policy.created_at && (
                                        <span className="flex items-center gap-1">
                                            <Clock className="w-3 h-3" />
                                            {new Date(policy.created_at).toLocaleDateString()}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-1 flex-shrink-0">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setExpanded(e => !e)}
                                className="h-8 w-8 p-0 text-muted-foreground hover:text-white hover:bg-white/10"
                                title={expanded ? 'Collapse rules' : 'Expand rules'}
                            >
                                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => onDelete(policy.policy_id)}
                                disabled={isDeleting}
                                className="h-8 w-8 p-0 text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                                title="Delete policy"
                            >
                                {isDeleting ? (
                                    <div className="w-4 h-4 border-2 border-rose-400 border-t-transparent rounded-full animate-spin" />
                                ) : (
                                    <Trash2 className="w-4 h-4" />
                                )}
                            </Button>
                        </div>
                    </div>
                </CardHeader>

                {/* Expandable Rules Section */}
                <AnimatePresence>
                    {expanded && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                        >
                            <CardContent className="pt-0 space-y-2">
                                <div className="border-t border-white/5 pt-3 space-y-2">
                                    {policy.rules.map((rule, i) => (
                                        <div
                                            key={i}
                                            onClick={() => onRuleClick(rule)}
                                            className="p-3 bg-white/[0.03] rounded-lg border border-white/5 cursor-pointer hover:bg-white/10 transition-colors"
                                        >
                                            <div className="flex items-start justify-between gap-2 mb-1">
                                                <span className="font-mono text-[10px] px-1.5 py-0.5 bg-secondary/50 rounded text-secondary-foreground">
                                                    {rule.rule_id}
                                                </span>
                                                <span className={cn(
                                                    "text-[10px] px-1.5 py-0.5 rounded font-medium",
                                                    rule.severity === 'HIGH' ? 'bg-destructive/20 text-destructive' : 'bg-primary/20 text-primary'
                                                )}>
                                                    {rule.severity}
                                                </span>
                                            </div>
                                            <p className="text-xs text-foreground/80 leading-relaxed mt-1">
                                                {rule.description}
                                            </p>
                                            {rule.sql_query && (
                                                <div className="mt-2 p-1.5 bg-muted/50 rounded text-[10px] font-mono text-muted-foreground truncate">
                                                    {rule.sql_query}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </motion.div>
                    )}
                </AnimatePresence>
            </Card>
        </motion.div>
    );
};

/* ───────────────────── Main Component ───────────────────── */
const PolicyManager: React.FC = () => {
    const queryClient = useQueryClient();
    const [isDragging, setIsDragging] = useState(false);
    const [checkTampering, setCheckTampering] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [uploadSuccess, setUploadSuccess] = useState<UploadResponse | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
    const [selectedRule, setSelectedRule] = useState<Rule | null>(null);

    /* ── Fetch policies ── */
    const { data: policies, isLoading: policiesLoading } = useQuery({
        queryKey: ['policy-list'],
        queryFn: () => api.get<PolicyListItem[]>('/policy/list'),
    });

    /* ── Upload mutation ── */
    const uploadMutation = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('check_tampering', checkTampering.toString());
            if (checkTampering) await new Promise(r => setTimeout(r, 2000));
            return api.post<UploadResponse>('/policy/upload', formData, true);
        },
        onSuccess: (data) => {
            setUploadSuccess(data);
            setUploadError(null);
            queryClient.invalidateQueries({ queryKey: ['policy-list'] });
            setTimeout(() => setUploadSuccess(null), 4000);
        },
        onError: (error: any) => {
            setUploadError(error.message || 'Upload failed');
        },
    });

    /* ── Delete mutation ── */
    const deleteMutation = useMutation({
        mutationFn: async (policyId: string) => {
            setDeletingId(policyId);
            return api.delete<{ status: string }>(`/policy/${policyId}`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['policy-list'] });
            setDeletingId(null);
            setConfirmDeleteId(null);
        },
        onError: () => {
            setDeletingId(null);
            setConfirmDeleteId(null);
        },
    });

    const handleFileUpload = useCallback(
        (file: File) => {
            if (file.type !== 'application/pdf') {
                setUploadError('Only PDF files are accepted.');
                return;
            }
            setUploadError(null);
            setUploadSuccess(null);
            uploadMutation.mutate(file);
        },
        [uploadMutation]
    );

    const onDrag = useCallback((e: React.DragEvent, active: boolean) => {
        e.preventDefault();
        setIsDragging(active);
    }, []);

    const onDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files?.length) handleFileUpload(e.dataTransfer.files[0]);
        },
        [handleFileUpload]
    );

    const handleDelete = (policyId: string) => {
        if (confirmDeleteId === policyId) {
            deleteMutation.mutate(policyId);
        } else {
            setConfirmDeleteId(policyId);
            setTimeout(() => setConfirmDeleteId(prev => (prev === policyId ? null : prev)), 3000);
        }
    };

    return (
        <div className="space-y-8">
            {/* ── HERO SECTION ── */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Policy Manager</h2>
                    <p className="text-muted-foreground">Upload, review, and manage compliance policies.</p>
                </div>

                {/* TAMPER TOGGLE */}
                <div className="flex items-center gap-3 bg-white/5 border border-white/10 p-3 rounded-full backdrop-blur-md shadow-lg">
                    <Switch id="tamper-mode" checked={checkTampering} onCheckedChange={setCheckTampering} />
                    <label
                        htmlFor="tamper-mode"
                        className="text-sm font-medium cursor-pointer select-none flex items-center gap-2"
                    >
                        {checkTampering ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                                <ShieldAlert className="w-4 h-4" /> Integrity Check Active
                            </span>
                        ) : (
                            <span className="text-muted-foreground">Integrity Check Off</span>
                        )}
                    </label>
                </div>
            </div>

            {/* ── UPLOAD ZONE ── */}
            <label
                onDragOver={(e) => onDrag(e, true)}
                onDragLeave={(e) => onDrag(e, false)}
                onDrop={onDrop}
                className={cn(
                    'relative group flex flex-col items-center justify-center w-full h-56 rounded-xl border-2 border-dashed transition-all cursor-pointer overflow-hidden',
                    isDragging
                        ? 'border-sky-400 bg-sky-400/5 scale-[1.01] shadow-2xl shadow-sky-400/20'
                        : 'border-white/10 bg-white/5 hover:border-sky-400/50 hover:bg-white/10',
                    uploadMutation.isPending && 'pointer-events-none opacity-80'
                )}
            >
                <input
                    type="file"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                    accept=".pdf"
                />

                {/* SCANNING ANIMATION */}
                {uploadMutation.isPending && checkTampering && (
                    <div className="absolute inset-0 z-10 bg-black/80 flex flex-col items-center justify-center">
                        <motion.div
                            className="w-full h-1 bg-emerald-500/50 absolute top-0 shadow-[0_0_20px_rgba(16,185,129,0.5)]"
                            animate={{ top: ['0%', '100%', '0%'] }}
                            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                        />
                        <ScanLine className="w-14 h-14 text-emerald-500 animate-pulse mb-3" />
                        <p className="text-emerald-400 font-mono text-base animate-pulse">
                            VERIFYING INTEGRITY...
                        </p>
                    </div>
                )}

                {/* STANDARD LOADING */}
                {uploadMutation.isPending && !checkTampering && (
                    <div className="absolute inset-0 z-10 bg-background/80 flex flex-col items-center justify-center backdrop-blur-sm">
                        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mb-3" />
                        <p className="text-foreground font-medium animate-pulse">Extracting Rules...</p>
                    </div>
                )}

                <div className="flex flex-col items-center space-y-3 p-6 text-center z-0">
                    <div
                        className={cn(
                            'p-3 rounded-full transition-all duration-500',
                            isDragging
                                ? 'bg-sky-400/20 text-sky-400'
                                : 'bg-white/10 text-slate-400 group-hover:bg-sky-400/10 group-hover:text-sky-400'
                        )}
                    >
                        <UploadCloud className="w-8 h-8" />
                    </div>
                    <div className="space-y-1">
                        <p className="text-base font-semibold text-foreground">
                            {isDragging ? 'Drop to Upload' : 'Drag & drop PDF Policy'}
                        </p>
                        <p className="text-sm text-muted-foreground">or click to browse filesystem</p>
                    </div>
                </div>
            </label>

            {/* ── UPLOAD FEEDBACK ── */}
            <AnimatePresence>
                {uploadMutation.isError && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="p-4 bg-destructive/10 border border-destructive/20 text-destructive rounded-lg flex items-center gap-3"
                    >
                        <AlertTriangle className="w-5 h-5 flex-shrink-0" />
                        <p className="font-medium text-sm">{uploadError}</p>
                    </motion.div>
                )}

                {uploadSuccess && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-3"
                    >
                        <div className="p-1.5 bg-emerald-500/20 rounded-full flex-shrink-0">
                            <CheckCircle className="w-5 h-5 text-emerald-500" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-emerald-500 text-sm">
                                Policy Active: {uploadSuccess.data.name}
                            </h3>
                            <p className="text-xs text-emerald-500/80">
                                Successfully extracted {uploadSuccess.data.rules.length} compliance rules.
                            </p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── ACTIVE POLICIES ── */}
            <div>
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 bg-primary/10 rounded-lg">
                        <Shield className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold tracking-tight">Active Policies</h3>
                        <p className="text-sm text-muted-foreground">
                            {policiesLoading
                                ? 'Loading...'
                                : `${policies?.length ?? 0} polic${(policies?.length ?? 0) === 1 ? 'y' : 'ies'} active`}
                        </p>
                    </div>
                </div>

                {/* Skeleton loading */}
                {policiesLoading && (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 animate-pulse">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="h-28 bg-white/5 rounded-xl border border-white/10" />
                        ))}
                    </div>
                )}

                {/* Empty state */}
                {!policiesLoading && (!policies || policies.length === 0) && (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="p-4 bg-white/5 rounded-full mb-4">
                            <FileText className="w-10 h-10 text-slate-500" />
                        </div>
                        <h4 className="text-lg font-medium text-slate-400">No active policies</h4>
                        <p className="text-sm text-muted-foreground mt-1">
                            Upload a PDF above to create your first compliance policy.
                        </p>
                    </div>
                )}

                {/* Policy grid */}
                {policies && policies.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                        <AnimatePresence mode="popLayout">
                            {policies.map((policy) => (
                                <PolicyCard
                                    key={policy.policy_id}
                                    policy={policy}
                                    onDelete={handleDelete}
                                    isDeleting={deletingId === policy.policy_id}
                                    onRuleClick={setSelectedRule}
                                />
                            ))}
                        </AnimatePresence>
                    </div>
                )}

                {/* Delete confirmation toast */}
                <AnimatePresence>
                    {confirmDeleteId && !deletingId && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 20 }}
                            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-900 border border-rose-500/30 rounded-xl px-5 py-3 shadow-2xl shadow-rose-500/10 flex items-center gap-4"
                        >
                            <p className="text-sm text-white">
                                Click <span className="text-rose-400 font-semibold">delete</span> again to confirm
                            </p>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setConfirmDeleteId(null)}
                                className="text-xs text-muted-foreground hover:text-white"
                            >
                                Cancel
                            </Button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* ── RULE DETAILS MODAL ── */}
            <AnimatePresence>
                {selectedRule && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm"
                        onClick={() => setSelectedRule(null)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-card w-full max-w-lg rounded-xl border border-border shadow-2xl overflow-hidden"
                        >
                            <div className="flex items-center justify-between p-4 border-b border-border">
                                <div className="flex items-center gap-3">
                                    <span className="font-mono text-xs px-2 py-1 bg-secondary/50 rounded text-secondary-foreground">
                                        {selectedRule.rule_id}
                                    </span>
                                    <span className={cn(
                                        "text-xs px-2 py-1 rounded font-medium",
                                        selectedRule.severity === 'HIGH' ? 'bg-destructive/20 text-destructive' : 'bg-primary/20 text-primary'
                                    )}>
                                        {selectedRule.severity}
                                    </span>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => setSelectedRule(null)} className="h-8 w-8 p-0">
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                            <div className="p-4 space-y-4">
                                <div>
                                    <h4 className="text-sm font-semibold text-muted-foreground mb-1">Description</h4>
                                    <p className="text-sm text-foreground/90 leading-relaxed">
                                        {selectedRule.description}
                                    </p>
                                </div>
                                {selectedRule.quote && (
                                    <div>
                                        <h4 className="text-sm font-semibold text-muted-foreground mb-1">Policy Quote</h4>
                                        <p className="text-sm text-foreground/70 italic border-l-2 border-primary/50 pl-2">
                                            "{selectedRule.quote}"
                                        </p>
                                    </div>
                                )}
                                {selectedRule.sql_query && (
                                    <div>
                                        <h4 className="text-sm font-semibold text-muted-foreground mb-1">SQL Query</h4>
                                        <div className="p-3 bg-muted/50 rounded-lg overflow-x-auto">
                                            <pre className="text-xs font-mono text-muted-foreground">
                                                {selectedRule.sql_query}
                                            </pre>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default PolicyManager;
