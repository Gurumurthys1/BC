'use client';

import React, { useEffect, useState } from 'react';
import { Users, Cpu, Activity, CheckCircle, Clock, AlertTriangle } from 'lucide-react';
import { supabase } from '../lib/supabase';

interface WorkerStats {
  hardware_id: string;
  status: string;
  current_jobs: number;
  total_jobs_completed: number;
  reputation: number;
  worker_type: string;
  last_seen: string;
  is_online: boolean;
}

export const WorkerDistribution: React.FC = () => {
  const [workers, setWorkers] = useState<WorkerStats[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchWorkerStats = async () => {
    try {
      // Try RPC function first
      const { data: rpcData, error: rpcError } = await supabase.rpc('get_worker_stats');
      
      if (!rpcError && rpcData) {
        setWorkers(rpcData);
      } else {
        // Fallback to direct query
        const { data } = await supabase
          .from('nodes')
          .select('*')
          .order('last_seen', { ascending: false });
        
        if (data) {
          const now = new Date();
          setWorkers(data.map(n => ({
            hardware_id: n.hardware_id,
            status: n.status,
            current_jobs: n.current_jobs || 0,
            total_jobs_completed: n.total_jobs_completed || 0,
            reputation: n.reputation || 0,
            worker_type: n.worker_type || 'browser',
            last_seen: n.last_seen,
            is_online: new Date(n.last_seen) > new Date(now.getTime() - 60000)
          })));
        }
      }
    } catch (error) {
      console.error('Failed to fetch worker stats:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkerStats();
    const interval = setInterval(fetchWorkerStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const onlineWorkers = workers.filter(w => w.is_online);
  const totalJobsCompleted = workers.reduce((sum, w) => sum + (w.total_jobs_completed || 0), 0);
  const totalCurrentJobs = workers.reduce((sum, w) => sum + (w.current_jobs || 0), 0);

  const getWorkerTypeIcon = (type: string) => {
    switch (type) {
      case 'python': return <Cpu className="w-4 h-4" />;
      case 'server': return <Activity className="w-4 h-4" />;
      default: return <Users className="w-4 h-4" />;
    }
  };

  const getWorkerTypeBadge = (type: string) => {
    switch (type) {
      case 'python': return { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20' };
      case 'server': return { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20' };
      default: return { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' };
    }
  };

  if (loading) {
    return (
      <div className="p-8 bg-[#0a0a0a] border border-white/5 rounded-[2.5rem] animate-pulse">
        <div className="h-8 bg-white/5 rounded w-48 mb-4" />
        <div className="space-y-3">
          <div className="h-16 bg-white/5 rounded-2xl" />
          <div className="h-16 bg-white/5 rounded-2xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-6 bg-[#0a0a0a] border border-white/5 rounded-2xl">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-emerald-500/10 rounded-xl">
              <Users className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Online</span>
          </div>
          <p className="text-3xl font-black text-white">{onlineWorkers.length}</p>
          <p className="text-[10px] text-zinc-600 mt-1">of {workers.length} total workers</p>
        </div>

        <div className="p-6 bg-[#0a0a0a] border border-white/5 rounded-2xl">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-cyan-500/10 rounded-xl">
              <Activity className="w-5 h-5 text-cyan-400" />
            </div>
            <span className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Active Jobs</span>
          </div>
          <p className="text-3xl font-black text-white">{totalCurrentJobs}</p>
          <p className="text-[10px] text-zinc-600 mt-1">across all workers</p>
        </div>

        <div className="p-6 bg-[#0a0a0a] border border-white/5 rounded-2xl">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-amber-500/10 rounded-xl">
              <CheckCircle className="w-5 h-5 text-amber-400" />
            </div>
            <span className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Completed</span>
          </div>
          <p className="text-3xl font-black text-white">{totalJobsCompleted}</p>
          <p className="text-[10px] text-zinc-600 mt-1">total jobs</p>
        </div>

        <div className="p-6 bg-[#0a0a0a] border border-white/5 rounded-2xl">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-purple-500/10 rounded-xl">
              <Cpu className="w-5 h-5 text-purple-400" />
            </div>
            <span className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">Worker Types</span>
          </div>
          <p className="text-3xl font-black text-white">
            {new Set(workers.map(w => w.worker_type)).size}
          </p>
          <p className="text-[10px] text-zinc-600 mt-1">browser, python, server</p>
        </div>
      </div>

      {/* Worker List */}
      <div className="p-8 bg-[#0a0a0a] border border-white/5 rounded-[2.5rem]">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-black text-white uppercase tracking-tight">Worker Distribution</h3>
          <span className="text-[10px] font-black text-zinc-600 uppercase tracking-widest">
            Live • Auto-refresh
          </span>
        </div>

        <div className="space-y-3">
          {workers.length === 0 ? (
            <div className="text-center py-12 text-zinc-600">
              <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-sm">No workers connected yet</p>
              <p className="text-[10px] mt-1">Start a worker to contribute compute</p>
            </div>
          ) : (
            workers.map((worker) => {
              const typeBadge = getWorkerTypeBadge(worker.worker_type);
              return (
                <div
                  key={worker.hardware_id}
                  className={`p-5 rounded-2xl border transition-all ${
                    worker.is_online
                      ? 'bg-white/[0.02] border-white/10 hover:border-emerald-500/30'
                      : 'bg-white/[0.01] border-white/5 opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Status indicator */}
                      <div className={`w-3 h-3 rounded-full ${worker.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-600'}`} />
                      
                      {/* Worker type badge */}
                      <div className={`p-2 rounded-xl border ${typeBadge.bg} ${typeBadge.border}`}>
                        {getWorkerTypeIcon(worker.worker_type)}
                      </div>
                      
                      {/* Worker info */}
                      <div>
                        <div className="flex items-center gap-3">
                          <span className="font-mono font-bold text-white text-sm">{worker.hardware_id}</span>
                          <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${typeBadge.bg} ${typeBadge.text} ${typeBadge.border} border`}>
                            {worker.worker_type}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-1">
                          <span className="text-[10px] text-zinc-600">
                            Last seen: {new Date(worker.last_seen).toLocaleTimeString()}
                          </span>
                          <span className="text-[10px] text-zinc-600">
                            Rep: {worker.reputation}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <p className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Current</p>
                        <p className={`text-lg font-black ${worker.current_jobs > 0 ? 'text-cyan-400' : 'text-zinc-500'}`}>
                          {worker.current_jobs}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Completed</p>
                        <p className="text-lg font-black text-emerald-400">{worker.total_jobs_completed}</p>
                      </div>
                      
                      {/* Load indicator */}
                      <div className="w-24 h-2 bg-white/5 rounded-full overflow-hidden">
                        <div 
                          className={`h-full transition-all ${
                            worker.current_jobs >= 2 ? 'bg-rose-500' : 
                            worker.current_jobs === 1 ? 'bg-amber-500' : 
                            'bg-emerald-500'
                          }`}
                          style={{ width: `${Math.min(100, worker.current_jobs * 50)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Fair distribution notice */}
        <div className="mt-6 p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-[11px] font-bold text-emerald-400">Fair Distribution Active</p>
              <p className="text-[10px] text-zinc-500 mt-1">
                Jobs are automatically distributed across all online workers based on their current load. 
                Workers with fewer jobs get priority for new assignments.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkerDistribution;
