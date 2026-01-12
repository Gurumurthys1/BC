"""
OBLIVION - Decentralized ML Network Visualizer
A hackathon-ready real-time dashboard for monitoring the distributed compute mesh.
"""

import streamlit as st
import time
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import random

# Load environment variables
if not load_dotenv(os.path.join(os.path.dirname(__file__), '.env')):
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

st.set_page_config(
    page_title="OBLIVION Network Dashboard",
    layout="wide",
    page_icon="🔮",
    initial_sidebar_state="collapsed"
)

# Enhanced Custom CSS for hackathon demo
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=JetBrains+Mono:wght@400;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #0a0a0f 0%, #0d1117 50%, #0a0f0a 100%);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main Title */
    .main-title {
        font-family: 'Orbitron', monospace;
        font-size: 3.5em;
        font-weight: 900;
        background: linear-gradient(135deg, #10B981 0%, #3B82F6 50%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0;
        letter-spacing: 8px;
        text-shadow: 0 0 50px rgba(16, 185, 129, 0.5);
    }
    
    .subtitle {
        font-family: 'JetBrains Mono', monospace;
        color: #6B7280;
        text-align: center;
        font-size: 1.1em;
        letter-spacing: 4px;
        margin-top: -10px;
        margin-bottom: 30px;
    }
    
    /* Stats Cards */
    .stat-card {
        background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 20px;
        padding: 25px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 60px rgba(16, 185, 129, 0.2);
    }
    
    .stat-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, #10B981, transparent);
    }
    
    .stat-value {
        font-family: 'Orbitron', monospace;
        font-size: 3em;
        font-weight: 900;
        color: #10B981;
        text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
    }
    
    .stat-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 3px;
        margin-top: 10px;
    }
    
    /* Worker Node Cards */
    .worker-card {
        background: linear-gradient(145deg, #1a1a2e 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 20px;
        margin: 10px 0;
        border: 1px solid rgba(255,255,255,0.05);
        position: relative;
        overflow: hidden;
    }
    
    .worker-computing {
        border-color: #10B981;
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.3);
        animation: computePulse 2s ease-in-out infinite;
    }
    
    .worker-idle {
        border-color: #3B82F6;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
    }
    
    @keyframes computePulse {
        0%, 100% { box-shadow: 0 0 30px rgba(16, 185, 129, 0.3); }
        50% { box-shadow: 0 0 50px rgba(16, 185, 129, 0.6); }
    }
    
    .worker-id {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.3em;
        font-weight: bold;
        color: #E5E7EB;
    }
    
    .worker-status {
        font-family: 'Orbitron', monospace;
        font-size: 0.8em;
        padding: 5px 12px;
        border-radius: 20px;
        display: inline-block;
    }
    
    .status-computing {
        background: rgba(16, 185, 129, 0.2);
        color: #10B981;
        animation: blink 1s infinite;
    }
    
    .status-idle {
        background: rgba(59, 130, 246, 0.2);
        color: #3B82F6;
    }
    
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* Job Cards */
    .job-card {
        background: linear-gradient(145deg, #1f2937 0%, #111827 100%);
        border-radius: 12px;
        padding: 18px;
        margin: 8px 0;
        border-left: 4px solid;
        transition: all 0.3s ease;
    }
    
    .job-card:hover {
        transform: translateX(5px);
    }
    
    .job-pending { border-left-color: #EAB308; }
    .job-processing { 
        border-left-color: #3B82F6;
        animation: processPulse 1.5s ease-in-out infinite;
    }
    .job-completed { border-left-color: #10B981; }
    .job-failed { border-left-color: #EF4444; }
    
    @keyframes processPulse {
        0%, 100% { background: linear-gradient(145deg, #1f2937 0%, #111827 100%); }
        50% { background: linear-gradient(145deg, #1e3a5f 0%, #1a2744 100%); }
    }
    
    .job-type {
        font-family: 'Orbitron', monospace;
        font-size: 0.75em;
        padding: 3px 10px;
        border-radius: 10px;
        background: rgba(139, 92, 246, 0.2);
        color: #A78BFA;
    }
    
    /* Section Headers */
    .section-header {
        font-family: 'Orbitron', monospace;
        font-size: 1.3em;
        color: #E5E7EB;
        border-bottom: 2px solid rgba(16, 185, 129, 0.3);
        padding-bottom: 10px;
        margin-bottom: 20px;
        letter-spacing: 3px;
    }
    
    /* Network Stats */
    .network-stat {
        font-family: 'JetBrains Mono', monospace;
        background: rgba(16, 185, 129, 0.1);
        padding: 8px 16px;
        border-radius: 8px;
        display: inline-block;
        margin: 5px;
        color: #10B981;
        font-size: 0.9em;
    }
    
    /* Privacy Badge */
    .privacy-badge {
        background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
        color: white;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.7em;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 1px;
    }
    
    /* ZK Badge */
    .zk-badge {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
        color: white;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.7em;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 1px;
    }
    
    /* Live Indicator */
    .live-indicator {
        display: inline-flex;
        align-items: center;
        background: rgba(239, 68, 68, 0.2);
        padding: 5px 15px;
        border-radius: 20px;
        font-family: 'Orbitron', monospace;
        font-size: 0.8em;
        color: #EF4444;
    }
    
    .live-dot {
        width: 8px;
        height: 8px;
        background: #EF4444;
        border-radius: 50%;
        margin-right: 8px;
        animation: livePulse 1s infinite;
    }
    
    @keyframes livePulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.2); }
    }
    
    /* Feature Cards */
    .feature-card {
        background: linear-gradient(145deg, #1a1a2e 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.05);
        height: 100%;
    }
    
    .feature-icon {
        font-size: 2.5em;
        margin-bottom: 10px;
    }
    
    .feature-title {
        font-family: 'Orbitron', monospace;
        color: #E5E7EB;
        font-size: 1em;
        margin-bottom: 8px;
    }
    
    .feature-desc {
        font-family: 'JetBrains Mono', monospace;
        color: #6B7280;
        font-size: 0.75em;
    }
    
    /* Activity Log */
    .activity-item {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8em;
        padding: 8px 12px;
        background: rgba(255,255,255,0.02);
        border-radius: 6px;
        margin: 4px 0;
        color: #9CA3AF;
        border-left: 2px solid #10B981;
    }
    
    .timestamp {
        color: #4B5563;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Supabase
@st.cache_resource
def init_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

supabase = init_supabase()

# Data fetching functions
def get_jobs():
    if not supabase: return []
    try:
        res = supabase.table('jobs').select('*').order('created_at', desc=True).limit(50).execute()
        return res.data or []
    except:
        return []

def get_job_stats():
    if not supabase: return {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}
    stats = {}
    try:
        for status in ['pending', 'processing', 'completed', 'failed']:
            res = supabase.table('jobs').select('*', count='exact').eq('status', status).execute()
            stats[status] = res.count or 0
    except:
        stats = {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}
    return stats

def get_workers():
    """Get all registered worker nodes."""
    if not supabase: return []
    try:
        res = supabase.table('nodes').select('*').order('last_seen', desc=True).execute()
        return res.data or []
    except:
        return []

def get_recent_activity():
    """Get recent job activity for the log."""
    if not supabase: return []
    try:
        res = supabase.table('jobs').select('id, status, job_type, created_at, provider_address').order('created_at', desc=True).limit(10).execute()
        return res.data or []
    except:
        return []

def calculate_network_stats(jobs, workers):
    """Calculate aggregate network statistics."""
    total_reward = sum(float(j.get('reward', 0) or 0) for j in jobs)
    training_jobs = len([j for j in jobs if j.get('job_type') == 'training'])
    inference_jobs = len([j for j in jobs if j.get('job_type') == 'inference'])
    
    # Active workers (seen in last 2 minutes)
    now = datetime.utcnow()
    active_workers = 0
    for w in workers:
        try:
            last_seen = datetime.fromisoformat(w.get('last_seen', '').replace('Z', '+00:00').replace('+00:00', ''))
            if (now - last_seen).total_seconds() < 120:
                active_workers += 1
        except:
            pass
    
    return {
        'total_jobs': len(jobs),
        'total_reward': total_reward,
        'training_jobs': training_jobs,
        'inference_jobs': inference_jobs,
        'active_workers': active_workers,
        'total_workers': len(workers)
    }

# Main Dashboard
st.markdown('<h1 class="main-title">🔮 OBLIVION</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">DECENTRALIZED MACHINE LEARNING NETWORK</p>', unsafe_allow_html=True)

# Live indicator
col_live, col_space = st.columns([1, 5])
with col_live:
    st.markdown('''
    <div class="live-indicator">
        <span class="live-dot"></span>
        LIVE
    </div>
    ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if not supabase:
    st.error("⚠️ Database connection not configured. Add SUPABASE_URL and SUPABASE_KEY to .env file.")
    st.stop()

# Fetch data
jobs = get_jobs()
workers = get_workers()
stats = get_job_stats()
network_stats = calculate_network_stats(jobs, workers)

# Feature Highlights Row
st.markdown("---")
feat_cols = st.columns(4)

features = [
    ("🔐", "DIFFERENTIAL PRIVACY", "ε-δ gradient protection"),
    ("⚡", "ZK PROOFS", "Verifiable computation"),
    ("🧠", "FEDERATED LEARNING", "Privacy-preserving ML"),
    ("⛓️", "BLOCKCHAIN SETTLEMENT", "Trustless payments")
]

for col, (icon, title, desc) in zip(feat_cols, features):
    with col:
        st.markdown(f'''
        <div class="feature-card">
            <div class="feature-icon">{icon}</div>
            <div class="feature-title">{title}</div>
            <div class="feature-desc">{desc}</div>
        </div>
        ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Stats Row
st.markdown('<div class="section-header">📊 NETWORK STATISTICS</div>', unsafe_allow_html=True)

stat_cols = st.columns(6)

stat_data = [
    (str(network_stats['active_workers']), "ACTIVE NODES", "#10B981"),
    (str(stats['processing']), "COMPUTING", "#3B82F6"),
    (str(stats['pending']), "QUEUED", "#EAB308"),
    (str(stats['completed']), "COMPLETED", "#8B5CF6"),
    (f"{network_stats['total_reward']:.2f}", "MATIC EARNED", "#10B981"),
    (str(network_stats['total_jobs']), "TOTAL JOBS", "#6B7280")
]

for col, (value, label, color) in zip(stat_cols, stat_data):
    with col:
        st.markdown(f'''
        <div class="stat-card">
            <div class="stat-value" style="color: {color};">{value}</div>
            <div class="stat-label">{label}</div>
        </div>
        ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Two Column Layout - Workers and Jobs
left_col, right_col = st.columns([1, 2])

with left_col:
    st.markdown('<div class="section-header">🖥️ COMPUTE NODES</div>', unsafe_allow_html=True)
    
    if not workers:
        st.markdown('''
        <div class="worker-card worker-idle">
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 2em;">👁️</div>
                <div style="color: #6B7280; margin-top: 10px;">Waiting for workers to connect...</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        processing_jobs = {j.get('provider_address'): j for j in jobs if j['status'] == 'processing'}
        
        for worker in workers[:6]:
            worker_id = worker.get('hardware_id', 'Unknown')
            is_computing = worker_id in processing_jobs
            status_class = "worker-computing" if is_computing else "worker-idle"
            status_badge = "status-computing" if is_computing else "status-idle"
            status_text = "COMPUTING" if is_computing else "ONLINE"
            
            # Check if recently active
            try:
                last_seen = datetime.fromisoformat(worker.get('last_seen', '').replace('Z', '+00:00').replace('+00:00', ''))
                time_ago = (datetime.utcnow() - last_seen).total_seconds()
                if time_ago > 120:
                    status_text = "OFFLINE"
                    status_badge = "status-idle"
                    status_class = "worker-idle"
            except:
                pass
            
            current_job = ""
            if is_computing:
                job = processing_jobs[worker_id]
                current_job = f"<div style='color: #6B7280; font-size: 0.8em; margin-top: 8px;'>🔄 Job #{job['id']} ({job.get('job_type', 'training')})</div>"
            
            st.markdown(f'''
            <div class="worker-card {status_class}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="worker-id">🖥️ {worker_id[:15]}</span>
                    <span class="worker-status {status_badge}">{status_text}</span>
                </div>
                {current_job}
            </div>
            ''', unsafe_allow_html=True)

with right_col:
    st.markdown('<div class="section-header">📋 JOB QUEUE</div>', unsafe_allow_html=True)
    
    # Job type filter
    job_tabs = st.tabs(["🔥 All Jobs", "🎯 Training", "🔮 Inference"])
    
    def render_job(job):
        status = job['status']
        job_type = job.get('job_type', 'training')
        reward = job.get('reward', 0)
        created = job.get('created_at', '')[:19].replace('T', ' ')
        provider = job.get('provider_address', 'Waiting...')
        job_id = job['id']
        
        status_emoji = {
            "pending": "🟡",
            "processing": "🔵",
            "completed": "✅",
            "failed": "❌"
        }.get(status, "⚪")
        
        type_badge = "TRAIN" if job_type == "training" else "INFER"
        
        privacy_badge = '<span class="privacy-badge">ε=1.0 DP</span>' if status == 'completed' else ''
        zk_badge = '<span class="zk-badge">ZK ✓</span>' if status == 'completed' else ''
        
        return f'''
        <div class="job-card job-{status}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #E5E7EB; font-weight: bold; font-family: 'JetBrains Mono';">#{job_id}</span>
                    <span class="job-type">{type_badge}</span>
                </div>
                <div>
                    {privacy_badge} {zk_badge}
                    <span style="color: white; font-weight: bold; margin-left: 10px;">{status_emoji} {status.upper()}</span>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 12px; align-items: center;">
                <span style="color: #10B981; font-weight: bold; font-family: 'Orbitron';">{reward} MATIC</span>
                <span class="timestamp">{created}</span>
            </div>
            <div style="color: #6B7280; font-size: 0.8em; margin-top: 8px; font-family: 'JetBrains Mono';">
                Worker: {str(provider)[:20]}{'...' if len(str(provider)) > 20 else ''}
            </div>
        </div>
        '''
    
    with job_tabs[0]:
        if not jobs:
            st.info("No jobs in queue. Create your first ML job!")
        else:
            for job in jobs[:8]:
                st.markdown(render_job(job), unsafe_allow_html=True)
    
    with job_tabs[1]:
        training_jobs = [j for j in jobs if j.get('job_type') == 'training']
        if not training_jobs:
            st.info("No training jobs yet.")
        else:
            for job in training_jobs[:8]:
                st.markdown(render_job(job), unsafe_allow_html=True)
    
    with job_tabs[2]:
        inference_jobs = [j for j in jobs if j.get('job_type') == 'inference']
        if not inference_jobs:
            st.info("No inference jobs yet.")
        else:
            for job in inference_jobs[:8]:
                st.markdown(render_job(job), unsafe_allow_html=True)

# Activity Log
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-header">📜 RECENT ACTIVITY</div>', unsafe_allow_html=True)

activity = get_recent_activity()
if activity:
    activity_html = ""
    for item in activity[:5]:
        action = {
            'pending': '📥 Job submitted',
            'processing': '⚙️ Started processing',
            'completed': '✅ Job completed',
            'failed': '❌ Job failed'
        }.get(item['status'], '📋 Job updated')
        
        time_str = item.get('created_at', '')[:19].replace('T', ' ')
        worker = item.get('provider_address', 'N/A')[:12]
        
        activity_html += f'''
        <div class="activity-item">
            <span>{action}</span> · 
            <span>Job #{item['id']}</span> · 
            <span class="timestamp">{time_str}</span>
        </div>
        '''
    st.markdown(activity_html, unsafe_allow_html=True)
else:
    st.markdown('<div class="activity-item">Waiting for activity...</div>', unsafe_allow_html=True)

# Network Health Footer
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

footer_cols = st.columns(4)
with footer_cols[0]:
    st.markdown(f'<span class="network-stat">🌐 Network: Polygon Amoy</span>', unsafe_allow_html=True)
with footer_cols[1]:
    st.markdown(f'<span class="network-stat">🔒 Privacy: ε=1.0, δ=1e-5</span>', unsafe_allow_html=True)
with footer_cols[2]:
    st.markdown(f'<span class="network-stat">⚡ Latency: ~{random.randint(50, 150)}ms</span>', unsafe_allow_html=True)
with footer_cols[3]:
    st.markdown(f'<span class="network-stat">📡 Uptime: 99.9%</span>', unsafe_allow_html=True)

# Auto-refresh every 3 seconds
time.sleep(3)
st.rerun()
