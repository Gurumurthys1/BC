import React from 'react';
import { Database, Brain, Activity, CheckCircle2, Plus, Clock, AlertCircle, ExternalLink, ScrollText } from 'lucide-react';
import ModelDownload from './ModelDownload';

interface Job {
    id: string | number;
    job_type: 'training' | 'inference';
    status: 'pending' | 'processing' | 'completed' | 'failed' | 'slashed';
    reward: string;
    created_at: string;
    data_hash: string;
    model_hash: string;
    requester_address?: string;
    on_chain_id?: number | null;
    result_url?: string;
    inference_result?: string;
    logs_url?: string;
}

interface JobCardProps {
    job: Job;
    account: string | null;
    onCancel: (id: string, onChainId: number) => void;
    onTest: (job: Job) => void;
    isWorkerMode?: boolean;
    onWork?: (job: Job) => void;
}

export const JobCard: React.FC<JobCardProps> = ({ job, account, onCancel, onTest, isWorkerMode, onWork }) => {
    const [mounted, setMounted] = React.useState(false);

    React.useEffect(() => {
        setMounted(true);
    }, []);

    const getStatusTheme = (status: string) => {
        switch (status) {
            case 'completed': return { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', icon: CheckCircle2 };
            case 'processing': return { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20', icon: Activity };
            case 'failed': return { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/20', icon: AlertCircle };
            case 'slashed': return { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/20', icon: AlertCircle };
            case 'challenged': return { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', icon: AlertCircle };
            default: return { bg: 'bg-zinc-500/10', text: 'text-zinc-500', border: 'border-zinc-500/20', icon: Clock };
        }
    };

    const theme = getStatusTheme(job.status);

    return (
        <div className="relative group p-[1px] bg-gradient-to-br from-white/10 to-transparent rounded-[2.5rem] hover:from-emerald-500/30 transition-all duration-700">
            {job.status === 'processing' && <div className="scanline" />}
            <div className="p-10 bg-[#0a0a0a] rounded-[2.4rem] flex flex-col gap-8 h-full relative">
                {/* Background ambient glow */}
                <div className={`absolute top-0 right-0 w-32 h-32 ${theme.bg} blur-[60px] opacity-20 transition-all duration-700 group-hover:opacity-40`} />

                <div className="flex flex-col sm:flex-row justify-between items-start gap-6">
                    <div className="flex items-center gap-6">
                        <div className={`w-16 h-16 rounded-[1.5rem] border flex items-center justify-center transition-all duration-500 ${theme.bg} ${theme.border} shadow-inner`}>
                            <theme.icon className={`w-8 h-8 ${theme.text} ${job.status === 'processing' ? 'animate-pulse' : ''}`} />
                        </div>
                        <div>
                            <div className="flex items-center gap-3 mb-2">
                                <span className="px-3 py-1 bg-white/5 rounded-lg text-[10px] font-mono font-black text-zinc-500 uppercase tracking-widest border border-white/5">0x-{String(job.id).slice(0, 8)}</span>
                                <span className="text-[10px] font-black text-zinc-700 uppercase tracking-[0.2em]">
                                    {mounted ? new Date(job.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'}
                                </span>
                            </div>
                            <h3 className="text-2xl font-black text-white tracking-tighter group-hover:text-emerald-400 transition-colors uppercase italic">
                                {job.job_type === 'inference' ? 'Neuro-Inference' : 'Mesh Training'}
                            </h3>
                        </div>
                    </div>

                    <div className="text-right flex flex-col items-end">
                        <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-white font-mono tracking-tighter">{job.reward}</span>
                            <span className="text-xs font-black text-emerald-500 uppercase tracking-widest italic">MATIC</span>
                        </div>
                        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-zinc-600 mt-2">Protocol Yield</p>
                    </div>
                </div>

                {job.status === 'processing' && (
                    <div className="space-y-3">
                        <div className="flex justify-between items-center px-1">
                            <span className="text-[9px] font-black text-emerald-500 uppercase tracking-[0.2em] animate-pulse">Syncing Neural Weights...</span>
                            <span className="text-[9px] font-mono text-zinc-500">
                                {Math.min(95, Math.floor((Date.now() - new Date(job.created_at).getTime()) / 1000 / 60 * 10))}%
                            </span>
                        </div>
                        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden border border-white/5">
                            <div 
                                className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 animate-[shimmer_2s_infinite] transition-all duration-1000" 
                                style={{ width: `${Math.min(95, Math.floor((Date.now() - new Date(job.created_at).getTime()) / 1000 / 60 * 10))}%` }}
                            />
                        </div>
                    </div>
                )}

                {job.job_type === 'inference' && job.inference_result && (
                    <div className="p-6 bg-cyan-500/5 border border-cyan-500/20 rounded-[1.8rem] relative group/result overflow-hidden">
                        <div className="absolute top-0 left-0 w-1 h-full bg-cyan-500/40" />
                        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-cyan-400 mb-3 opacity-60">Sequence Result</p>
                        <p className="font-mono text-cyan-50 text-base leading-relaxed break-all">{job.inference_result}</p>
                    </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-4 p-4 bg-white/[0.02] rounded-2xl border border-white/5">
                        <div className="p-2 bg-zinc-900 rounded-xl"><Database className="w-4 h-4 text-zinc-600" /></div>
                        <div className="flex flex-col min-w-0">
                            <span className="text-[9px] font-black text-zinc-700 uppercase tracking-widest">Model Shard</span>
                            <span className="text-[11px] font-mono text-zinc-400 truncate mt-0.5">{job.model_hash || 'Global Architecture'}</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-4 p-4 bg-white/[0.02] rounded-2xl border border-white/5">
                        <div className="p-2 bg-zinc-900 rounded-xl"><Activity className="w-4 h-4 text-zinc-600" /></div>
                        <div className="flex flex-col min-w-0">
                            <span className="text-[9px] font-black text-zinc-700 uppercase tracking-widest">Data Shard</span>
                            <span className="text-[11px] font-mono text-zinc-400 truncate mt-0.5">{job.data_hash || 'Synthetic Shard'}</span>
                        </div>
                    </div>
                </div>

                    <div className="flex flex-wrap items-center justify-between gap-6 pt-4 border-t border-white/5">
                    <div className="flex flex-wrap gap-4 items-center">
                        {job.status === 'completed' ? (
                            <div className="flex items-center gap-4">
                                {job.job_type === 'training' && job.result_url && (
                                    <>
                                        <ModelDownload 
                                            jobId={String(job.id)} 
                                            modelUrl={job.result_url} 
                                        />
                                        <button
                                            onClick={() => onTest(job)}
                                            className="flex items-center gap-2.5 px-5 py-2.5 bg-cyan-500/5 border border-cyan-500/20 rounded-xl text-[11px] font-black uppercase tracking-widest text-cyan-400 hover:bg-cyan-500 hover:text-black transition-all"
                                        >
                                            <Brain className="w-4 h-4" /> Infer
                                        </button>
                                    </>
                                )}
                                {job.logs_url && (
                                    <a
                                        href={job.logs_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-2.5 px-5 py-2.5 bg-amber-500/5 border border-amber-500/20 rounded-xl text-[11px] font-black uppercase tracking-widest text-amber-400 hover:bg-amber-500 hover:text-black transition-all"
                                    >
                                        <ScrollText className="w-4 h-4" /> Logs
                                    </a>
                                )}
                            </div>
                        ) : (
                            <div className={`flex items-center gap-3 px-5 py-2.5 rounded-xl border ${theme.bg} ${theme.border} text-[11px] font-black uppercase tracking-widest ${theme.text}`}>
                                <Clock className={`w-4 h-4 ${job.status === 'processing' ? 'animate-spin' : ''}`} />
                                {job.status}
                            </div>
                        )}

                        {job.status === 'pending' && job.requester_address?.toLowerCase() === account?.toLowerCase() && (
                            <button
                                onClick={() => {
                                    if (job.on_chain_id !== undefined && job.on_chain_id !== null) {
                                        onCancel(String(job.id), job.on_chain_id);
                                    } else {
                                        alert("On-chain ID missing. Please refresh or contact support.");
                                    }
                                }}
                                className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-rose-500 hover:text-rose-400 transition-colors"
                            >
                                <AlertCircle className="w-4 h-4" /> Cancel
                            </button>
                        )}

                        {job.status === 'pending' && isWorkerMode && (
                            <button
                                onClick={() => onWork?.(job)}
                                className="flex items-center gap-2.5 px-6 py-2.5 bg-amber-500 text-black rounded-xl text-[11px] font-black uppercase tracking-widest hover:scale-105 transition-all shadow-lg shadow-amber-500/20 animate-[pulse_3s_infinite]"
                            >
                                <Plus className="w-4 h-4" /> Fulfill Shard
                            </button>
                        )}
                    </div>

                    <button className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-zinc-700 hover:text-white transition-colors">
                        Protocol Detail <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>
        </div>
    );
};
