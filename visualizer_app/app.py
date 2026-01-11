import streamlit as st
import time
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
if not load_dotenv(os.path.join(os.path.dirname(__file__), '.env')):
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

st.set_page_config(page_title="OBLIVION Visualizer", layout="wide", page_icon="⚡")

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }
    .node-card {
        border-radius: 15px;
        padding: 25px;
        color: white;
        text-align: center;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        border: 2px solid #333;
        margin-bottom: 10px;
    }
    .status-computing {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.5);
        animation: pulse 1.5s infinite;
    }
    .status-ready {
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
        box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
    }
    .status-completed {
        background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
    }
    .status-idle {
        background: linear-gradient(135deg, #374151 0%, #1F2937 100%);
    }
    .status-failed {
        background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
        opacity: 0.7;
    }
    @keyframes pulse {
        0% { transform: scale(1); box-shadow: 0 0 30px rgba(16, 185, 129, 0.5); }
        50% { transform: scale(1.02); box-shadow: 0 0 50px rgba(16, 185, 129, 0.7); }
        100% { transform: scale(1); box-shadow: 0 0 30px rgba(16, 185, 129, 0.5); }
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 2px;
        opacity: 0.8;
    }
    .job-card {
        background: #1a1a2e;
        border-radius: 10px;
        padding: 15px;
        margin: 5px 0;
        border-left: 4px solid #10B981;
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

def get_jobs():
    if not supabase: return []
    res = supabase.table('jobs').select('*').order('created_at', desc=True).limit(20).execute()
    return res.data

def get_job_stats():
    if not supabase: return {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}
    stats = {}
    for status in ['pending', 'processing', 'completed', 'failed']:
        res = supabase.table('jobs').select('*', count='exact').eq('status', status).execute()
        stats[status] = res.count or 0
    return stats

def get_active_workers():
    """Get unique workers that have processed jobs recently."""
    if not supabase: return []
    # Get workers from recent job assignments
    res = supabase.table('jobs').select('provider_address').not_.is_('provider_address', 'null').execute()
    workers = list(set([j['provider_address'] for j in res.data if j['provider_address']]))
    return workers

st.title("⚡ OBLIVION Compute Mesh Visualizer")

if not supabase:
    st.error("Supabase credentials not found. Please check .env file.")
else:
    # Stats Row
    stats = get_job_stats()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🟡 Pending", stats['pending'])
    with col2:
        st.metric("🔵 Processing", stats['processing'])
    with col3:
        st.metric("🟢 Completed", stats['completed'])
    with col4:
        st.metric("🔴 Failed", stats['failed'])

    st.markdown("---")

    # Two Column Layout
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.markdown("### 📋 Recent Jobs")
        jobs = get_jobs()
        
        if not jobs:
            st.info("No jobs found. Create a job in the Web Dashboard!")
        else:
            for job in jobs[:10]:
                status = job['status']
                status_emoji = {"pending": "🟡", "processing": "🔵", "completed": "🟢", "failed": "🔴"}.get(status, "⚪")
                reward = job.get('reward', 'N/A')
                created = job.get('created_at', '')[:16].replace('T', ' ')
                provider = (job.get('provider_address') or 'Waiting...')[:15]
                
                st.markdown(f"""
                <div class="job-card" style="border-left-color: {'#10B981' if status=='completed' else '#3B82F6' if status=='processing' else '#EAB308' if status=='pending' else '#EF4444'}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #9CA3AF; font-size: 0.8em;">ID: {str(job['id'])[:8]}...</span>
                        <span style="color: white; font-weight: bold;">{status_emoji} {status.upper()}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                        <span style="color: #10B981; font-weight: bold;">{reward} MATIC</span>
                        <span style="color: #6B7280; font-size: 0.8em;">{created}</span>
                    </div>
                    <div style="color: #6B7280; font-size: 0.75em; margin-top: 5px;">Worker: {provider}</div>
                </div>
                """, unsafe_allow_html=True)

    with right_col:
        st.markdown("### 🖥️ Active Workers")
        workers = get_active_workers()
        
        if not workers:
            st.markdown("""
            <div class="node-card status-idle">
                <div class="metric-value">👁️</div>
                <div class="metric-label">Waiting for Workers</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for worker in workers[:4]:
                is_processing = any(j['status'] == 'processing' and j.get('provider_address') == worker for j in jobs)
                status_class = "status-computing" if is_processing else "status-ready"
                status_text = "COMPUTING" if is_processing else "READY"
                
                st.markdown(f"""
                <div class="node-card {status_class}">
                    <div class="metric-value">{worker[-4:]}</div>
                    <div class="metric-label">{status_text}</div>
                    <small style="opacity: 0.6; margin-top: 10px;">{worker}</small>
                </div>
                """, unsafe_allow_html=True)

    # Auto-refresh
    time.sleep(3)
    st.rerun()
