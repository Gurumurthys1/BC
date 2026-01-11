'use client';

import React, { useEffect, useState, useRef } from 'react';
import { supabase } from '../lib/supabase';
import { Server, Activity, Globe } from 'lucide-react';

interface Node {
    id: number;
    hardware_id: string;
    status: 'active' | 'offline';
    wallet_address?: string;
    last_seen: string;
}

interface Job {
    id: string;
    status: string;
    provider_address?: string;
}

export default function NetworkVisualization() {
    const [nodes, setNodes] = useState<Node[]>([]);
    const [jobs, setJobs] = useState<Job[]>([]);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        fetchNodes();
        fetchJobs();

        const channel = supabase
            .channel('network-viz')
            .on('postgres_changes', { event: '*', schema: 'public', table: 'nodes' }, () => fetchNodes())
            .on('postgres_changes', { event: '*', schema: 'public', table: 'jobs' }, () => fetchJobs())
            .subscribe();

        return () => { supabase.removeChannel(channel); };
    }, []);

    async function fetchNodes() {
        const { data } = await supabase.from('nodes').select('*');
        if (data) setNodes(data);
    }

    async function fetchJobs() {
        const { data } = await supabase.from('jobs').select('id, status, provider_address').in('status', ['processing', 'completed']);
        if (data) setJobs(data);
    }

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let iframeId: number;

        const draw = () => {
            if (!canvas) return;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;

            // Grid Lines
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
            ctx.lineWidth = 1;
            for (let i = 0; i < canvas.width; i += 50) {
                ctx.moveTo(i, 0); ctx.lineTo(i, canvas.height);
            }
            for (let i = 0; i < canvas.height; i += 50) {
                ctx.moveTo(0, i); ctx.lineTo(canvas.width, i);
            }
            ctx.stroke();

            // Hub
            ctx.beginPath();
            ctx.arc(centerX, centerY, 30, 0, Math.PI * 2);
            ctx.fillStyle = '#10B981';
            ctx.shadowBlur = 40;
            ctx.shadowColor = '#10B981';
            ctx.fill();
            ctx.closePath();
            ctx.shadowBlur = 0;

            const radius = Math.min(centerX, centerY) * 0.75;
            const recentNodes = nodes.filter(n => new Date().getTime() - new Date(n.last_seen).getTime() < 3600000); // Only seen in last hour

            recentNodes.forEach((node, i) => {
                const angle = (i / Math.max(recentNodes.length, 1)) * Math.PI * 2;
                const x = centerX + Math.cos(angle) * radius;
                const y = centerY + Math.sin(angle) * radius;

                // Real-time Online Check (45s window)
                const isOnline = new Date().getTime() - new Date(node.last_seen).getTime() < 45000;

                // Curved Connection
                ctx.beginPath();
                const cp1x = centerX + (x - centerX) * 0.5;
                const cp1y = centerY;
                const cp2x = centerX;
                const cp2y = centerY + (y - centerY) * 0.5;
                ctx.moveTo(centerX, centerY);
                ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x, y);
                ctx.strokeStyle = isOnline ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.03)';
                ctx.setLineDash(isOnline ? [] : [2, 4]);
                ctx.lineWidth = 1.5;
                ctx.stroke();
                ctx.setLineDash([]);

                // Animated Packet
                const isActive = jobs.some(j =>
                    (j.provider_address?.toLowerCase() === node.wallet_address?.toLowerCase() ||
                        j.provider_address?.toLowerCase() === node.hardware_id?.toLowerCase()) &&
                    j.status === 'processing'
                );

                if (isActive && isOnline) {
                    const progress = (Date.now() / 1500) % 1;
                    const t = progress;
                    const px = (1 - t) ** 3 * centerX + 3 * (1 - t) ** 2 * t * cp1x + 3 * (1 - t) * t ** 2 * cp2x + t ** 3 * x;
                    const py = (1 - t) ** 3 * centerY + 3 * (1 - t) ** 2 * t * cp1y + 3 * (1 - t) * t ** 2 * cp2y + t ** 3 * y;

                    ctx.beginPath();
                    ctx.arc(px, py, 6, 0, Math.PI * 2);
                    ctx.fillStyle = '#fff';
                    ctx.shadowBlur = 15;
                    ctx.shadowColor = '#10B981';
                    ctx.fill();
                    ctx.shadowBlur = 0;
                }

                // Node
                ctx.beginPath();
                ctx.arc(x, y, 10, 0, Math.PI * 2);
                ctx.fillStyle = isOnline ? '#10B981' : '#27272a';
                ctx.shadowBlur = isOnline ? 25 : 0;
                ctx.shadowColor = '#10B981';
                ctx.fill();
                ctx.shadowBlur = 0;

                // Label
                ctx.font = 'bold 9px monospace';
                ctx.fillStyle = isOnline ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.2)';
                ctx.textAlign = 'center';
                ctx.fillText(node.hardware_id.split('-')[1] || node.hardware_id, x, y + 25);

                if (isOnline) {
                    ctx.beginPath();
                    ctx.arc(x, y, 14, 0, Math.PI * 2);
                    ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
                    ctx.setLineDash([2, 4]);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }
            });

            iframeId = requestAnimationFrame(draw);
        };

        const resize = () => {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
        };
        window.addEventListener('resize', resize);
        resize();
        draw();
        return () => {
            cancelAnimationFrame(iframeId);
            window.removeEventListener('resize', resize);
        };
    }, [nodes, jobs]);

    return (
        <div className="flex flex-col h-full gap-8">
            <div className="relative flex-1 bg-black/60 rounded-[2.5rem] border border-white/5 overflow-hidden">
                <canvas ref={canvasRef} className="w-full h-full relative z-10" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-6">
                {nodes
                    .filter(n => new Date().getTime() - new Date(n.last_seen).getTime() < 3600000) // Seen in last hour
                    .sort((a, b) => new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime()) // Most recent first
                    .slice(0, 12)
                    .map(node => {
                        const isOnline = new Date().getTime() - new Date(node.last_seen).getTime() < 45000;
                        return (
                            <div key={node.id} className="p-4 bg-white/5 rounded-2xl border border-white/5 flex flex-col gap-2 group hover:border-emerald-500/30 transition-all">
                                <div className="flex items-center justify-between">
                                    <Server className={`w-4 h-4 ${isOnline ? 'text-emerald-500' : 'text-zinc-700'}`} />
                                    <div className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-800'}`} />
                                </div>
                                <p className="text-[10px] font-black text-white font-mono truncate">{node.hardware_id}</p>
                            </div>
                        );
                    })}
            </div>
        </div>
    );
}
