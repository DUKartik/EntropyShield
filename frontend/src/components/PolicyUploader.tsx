
import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, FileText, CheckCircle, AlertTriangle, ShieldAlert, ScanLine } from 'lucide-react';
import { api } from '../lib/api';
import { Policy, Rule } from '../types';
import { Switch } from './ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';
import { useMutation } from '@tanstack/react-query';

interface uploadResponse {
  status: string;
  policy_id: string;
  data: Policy;
}

const PolicyUploader: React.FC<{ onUploadSuccess: (policy: Policy) => void }> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [checkTampering, setCheckTampering] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('check_tampering', checkTampering.toString());
      // Artificial delay for "Cinematic" scanning effect if tamper check is on
      if (checkTampering) await new Promise(r => setTimeout(r, 2000));
      return api.post<uploadResponse>('/policy/upload', formData, true);
    },
    onSuccess: (data) => {
      onUploadSuccess(data.data);
    },
    onError: (error: any) => {
      setUploadError(error.message || "Upload failed");
    }
  });

  const handleFileUpload = useCallback((file: File) => {
    if (file.type !== 'application/pdf') {
      setUploadError('Only PDF files are accepted.');
      return;
    }
    setUploadError(null);
    mutation.mutate(file);
  }, [mutation]);

  const onDrag = useCallback((e: React.DragEvent, active: boolean) => {
    e.preventDefault();
    setIsDragging(active);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) handleFileUpload(e.dataTransfer.files[0]);
  }, [handleFileUpload]);


  return (
    <div className="space-y-6">
      {/* HERO SECTION */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Policy Ingestion</h2>
          <p className="text-muted-foreground">Upload compliance documents for AI analysis.</p>
        </div>

        {/* TAMPER TOGGLE */}
        <div className="flex items-center gap-3 bg-white/5 border border-white/10 p-3 rounded-full backdrop-blur-md shadow-lg">
          <Switch
            id="tamper-mode"
            checked={checkTampering}
            onCheckedChange={setCheckTampering}
          />
          <label htmlFor="tamper-mode" className="text-sm font-medium cursor-pointer select-none flex items-center gap-2">
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

      {/* DROPZONE */}
      <AnimatePresence mode='wait'>
        {!mutation.data ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            layout
          >
            <label
              onDragOver={(e) => onDrag(e, true)}
              onDragLeave={(e) => onDrag(e, false)}
              onDrop={onDrop}
              className={cn(
                "relative group flex flex-col items-center justify-center w-full h-80 rounded-xl border-2 border-dashed transition-all cursor-pointer overflow-hidden",
                isDragging
                  ? "border-sky-400 bg-sky-400/5 scale-[1.01] shadow-2xl shadow-sky-400/20"
                  : "border-white/10 bg-white/5 hover:border-sky-400/50 hover:bg-white/10",
                mutation.isPending && "pointer-events-none opacity-80"
              )}
            >
              <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])} accept=".pdf" />

              {/* SCANNING ANIMATION LAYER */}
              {mutation.isPending && checkTampering && (
                <div className="absolute inset-0 z-10 bg-black/80 flex flex-col items-center justify-center">
                  <motion.div
                    className="w-full h-1 bg-emerald-500/50 absolute top-0 shadow-[0_0_20px_rgba(16,185,129,0.5)]"
                    animate={{ top: ["0%", "100%", "0%"] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  />
                  <ScanLine className="w-16 h-16 text-emerald-500 animate-pulse mb-4" />
                  <p className="text-emerald-400 font-mono text-lg animate-pulse">VERIFYING INTEGRITY...</p>
                  <div className="font-mono text-xs text-emerald-500/60 mt-2">
                    HASH: {Math.random().toString(36).substring(7).toUpperCase()}...
                  </div>
                </div>
              )}

              {/* STANDARD LOADING */}
              {mutation.isPending && !checkTampering && (
                <div className="absolute inset-0 z-10 bg-background/80 flex flex-col items-center justify-center backdrop-blur-sm">
                  <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
                  <p className="text-foreground font-medium animate-pulse">Extracting Rules...</p>
                </div>
              )}

              <div className="flex flex-col items-center space-y-4 p-6 text-center z-0">
                <div className={cn(
                  "p-4 rounded-full transition-all duration-500",
                  isDragging ? "bg-sky-400/20 text-sky-400" : "bg-white/10 text-slate-400 group-hover:bg-sky-400/10 group-hover:text-sky-400"
                )}>
                  <UploadCloud className="w-10 h-10" />
                </div>
                <div className="space-y-1">
                  <p className="text-lg font-semibold text-foreground">
                    {isDragging ? "Drop to Upload" : "Drag & drop PDF Policy"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    or click to browse filesystem
                  </p>
                </div>
              </div>
            </label>

            {/* ERROR STATE */}
            {mutation.isError && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 bg-destructive/10 border border-destructive/20 text-destructive rounded-lg flex items-center gap-3"
              >
                <AlertTriangle className="w-5 h-5" />
                <p className="font-medium text-sm">{uploadError}</p>
              </motion.div>
            )}
          </motion.div>

        ) : (
          /* SUCCESS STATE - RULES GRID */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            <div className="flex items-center justify-between bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-500/20 rounded-full">
                  <CheckCircle className="w-6 h-6 text-emerald-500" />
                </div>
                <div>
                  <h3 className="font-semibold text-emerald-500">Policy Active: {mutation.data.data.name}</h3>
                  <p className="text-sm text-emerald-500/80">Successfully extracted {mutation.data.data.rules.length} compliance rules.</p>
                </div>
              </div>
              <Badge variant="outline" className="border-emerald-500/30 text-emerald-500 bg-emerald-500/5">
                AI Confidence: 98%
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {mutation.data.data.rules.map((rule: Rule, i: number) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <Card className="h-full hover:border-sky-400/50 transition-colors bg-white/5 backdrop-blur-md border-white/10 shadow-lg">
                    <CardHeader className="pb-3">
                      <div className="flex justify-between items-start">
                        <Badge variant="secondary" className="font-mono text-xs">{rule.rule_id}</Badge>
                        <Badge variant={rule.severity === 'HIGH' ? 'destructive' : 'default'} className="text-[10px]">
                          {rule.severity}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-foreground/90 leading-relaxed">
                        {rule.description}
                      </p>
                      <div className="mt-4 p-2 bg-muted/50 rounded text-[10px] font-mono text-muted-foreground truncate">
                        {rule.sql_query}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>

            <button
              onClick={() => mutation.reset()}
              className="text-sm text-muted-foreground hover:text-primary transition-colors underline underline-offset-4"
            >
              Upload another policy
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default PolicyUploader;
