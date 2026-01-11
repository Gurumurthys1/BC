'use client';

import React, { useState, useEffect } from 'react';
import { Activity, Cpu, Power, PowerOff, Zap, Server, CheckCircle2 } from 'lucide-react';
import { BrowserWorker } from '../lib/browserWorker';

interface WorkerStatusProps {
  walletAddress: string | null;
  onJobComplete?: (jobId: string, success: boolean) => void;
}

export const WorkerStatus: React.FC<WorkerStatusProps> = ({ walletAddress, onJobComplete }) => {
  const [worker, setWorker] = useState<BrowserWorker | null>(null);
  const [status, setStatus] = useState<'stopped' | 'running' | 'processing'>('stopped');
  const [currentJob, setCurrentJob] = useState<string | null>(null);
  const [jobsCompleted, setJobsCompleted] = useState(0);
  const [enableGPU, setEnableGPU] = useState(false);

  useEffect(() => {
    if (walletAddress && !worker) {
      const newWorker = new BrowserWorker({
        walletAddress,
        maxConcurrentJobs: 1,
        enableGPU
      });

      newWorker.setCallbacks(
        (newStatus: string) => {
          if (newStatus.startsWith('processing:')) {
            setStatus('processing');
            setCurrentJob(newStatus.split(':')[1].trim());
          } else if (newStatus === 'running' || newStatus === 'idle') {
            setStatus('running');
            setCurrentJob(null);
          } else {
            setStatus('stopped');
            setCurrentJob(null);
          }
        },
        (jobId: string, result) => {
          if (result.success) {
            setJobsCompleted(prev => prev + 1);
          }
          onJobComplete?.(jobId, result.success);
        }
      );

      setWorker(newWorker);
    }

    return () => {
      if (worker) {
        worker.stop();
      }
    };
  }, [walletAddress]);

  const toggleWorker = async () => {
    if (!worker) return;

    if (status === 'stopped') {
      await worker.start();
    } else {
      worker.stop();
    }
  };

  if (!walletAddress) return null;

  return (
    <div className="relative group">
      <div className={`p-6 rounded-[2rem] border transition-all duration-500 ${
        status === 'running' 
          ? 'bg-emerald-500/5 border-emerald-500/20' 
          : status === 'processing'
          ? 'bg-cyan-500/5 border-cyan-500/20'
          : 'bg-zinc-900/50 border-white/5'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl ${
              status === 'running' ? 'bg-emerald-500/20' : 
              status === 'processing' ? 'bg-cyan-500/20' : 'bg-white/5'
            }`}>
              <Cpu className={`w-5 h-5 ${
                status === 'running' ? 'text-emerald-400' : 
                status === 'processing' ? 'text-cyan-400 animate-pulse' : 'text-zinc-500'
              }`} />
            </div>
            <div>
              <h3 className="text-sm font-black text-white uppercase tracking-tight">Browser Worker</h3>
              <p className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest">
                {status === 'stopped' ? 'Offline' : status === 'processing' ? 'Computing...' : 'Active'}
              </p>
            </div>
          </div>

          <button
            onClick={toggleWorker}
            disabled={status === 'processing'}
            className={`p-3 rounded-xl transition-all ${
              status === 'stopped'
                ? 'bg-emerald-500 hover:bg-emerald-400 text-black'
                : 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-400'
            } disabled:opacity-50`}
          >
            {status === 'stopped' ? (
              <Power className="w-4 h-4" />
            ) : (
              <PowerOff className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Status Bar */}
        {status !== 'stopped' && (
          <div className="space-y-3">
            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
              <div className={`h-full ${
                status === 'processing' 
                  ? 'bg-cyan-500 animate-[pulse_1s_infinite]' 
                  : 'bg-emerald-500'
              } transition-all`} style={{ width: status === 'processing' ? '60%' : '100%' }} />
            </div>

            <div className="flex justify-between items-center text-[10px]">
              <span className="text-zinc-500 uppercase tracking-wider font-bold">
                {status === 'processing' && currentJob ? (
                  <>Processing Job: <span className="text-cyan-400 font-mono">{currentJob.slice(0, 8)}...</span></>
                ) : (
                  'Waiting for jobs...'
                )}
              </span>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                <span className="text-emerald-400 font-mono">{jobsCompleted}</span>
              </div>
            </div>
          </div>
        )}

        {/* GPU Toggle */}
        <div className="mt-4 flex items-center justify-between pt-4 border-t border-white/5">
          <div className="flex items-center gap-2">
            <Zap className={`w-3 h-3 ${enableGPU ? 'text-amber-400' : 'text-zinc-600'}`} />
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">GPU Acceleration</span>
          </div>
          <button
            onClick={() => setEnableGPU(!enableGPU)}
            disabled={status !== 'stopped'}
            className={`w-10 h-5 rounded-full transition-all ${
              enableGPU ? 'bg-amber-500' : 'bg-white/10'
            } disabled:opacity-50`}
          >
            <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${
              enableGPU ? 'translate-x-5' : 'translate-x-0.5'
            }`} />
          </button>
        </div>

        {/* Info */}
        <p className="mt-4 text-[9px] text-zinc-600 leading-relaxed">
          {status === 'stopped' 
            ? 'Start the worker to contribute your compute power and earn rewards.'
            : 'Your browser is now processing ML jobs from the network. Keep this tab open.'
          }
        </p>
      </div>
    </div>
  );
};

export default WorkerStatus;
