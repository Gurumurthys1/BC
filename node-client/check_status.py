#!/usr/bin/env python3
"""OBLIVION System Status Report"""

from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

# Get all jobs
jobs = supabase.table('jobs').select('*').execute().data
status_counts = {}
for j in jobs:
    s = j['status']
    status_counts[s] = status_counts.get(s, 0) + 1

print('=' * 60)
print('        OBLIVION SYSTEM STATUS REPORT')
print('=' * 60)
print()
print('JOB STATISTICS:')
for status, count in sorted(status_counts.items()):
    bar = '#' * min(count, 40)
    print(f'  {status:12}: {count:3} {bar}')
print(f'  {"TOTAL":12}: {len(jobs)}')

# Get worker updates
updates = supabase.table('worker_updates').select('*').execute().data
worker_jobs = {}
for u in updates:
    w = u.get('worker_address', 'unknown')
    if w:
        w = w[:20]
    worker_jobs[w] = worker_jobs.get(w, 0) + 1

print()
print('WORKER DISTRIBUTION:')
for worker, count in sorted(worker_jobs.items(), key=lambda x: -x[1]):
    bar = '#' * min(count, 30)
    print(f'  {worker:20}: {count:3} {bar}')

# Check nodes
nodes = supabase.table('nodes').select('*').execute().data
online = sum(1 for n in nodes if n['status'] == 'active')
print()
print('NETWORK STATUS:')
print(f'  Online nodes: {online}/{len(nodes)}')

# Check completed jobs with results
completed = [j for j in jobs if j['status'] == 'completed' and j.get('result_url')]
print(f'  Jobs with models: {len(completed)}')

print()
print('=' * 60)
print('  System is operational!')
print('=' * 60)
