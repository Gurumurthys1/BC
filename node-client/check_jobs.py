#!/usr/bin/env python3
"""Check job distribution across workers."""

from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

# Get recent jobs
print("\n=== Recent Jobs ===")
jobs = supabase.table('jobs').select('id, status, provider_address, created_at').order('id', desc=True).limit(15).execute()
for j in jobs.data:
    provider = j.get('provider_address', 'None')[:20] if j.get('provider_address') else 'None'
    print(f"Job {j['id']:3d}: {j['status']:12s} | Worker: {provider}")

# Count jobs per worker
print("\n=== Jobs Per Worker ===")
all_jobs = supabase.table('jobs').select('provider_address, status').execute()
worker_counts = {}
status_counts = {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}

for j in all_jobs.data:
    status = j.get('status', 'unknown')
    status_counts[status] = status_counts.get(status, 0) + 1
    
    provider = j.get('provider_address')
    if provider:
        if provider not in worker_counts:
            worker_counts[provider] = {'processing': 0, 'completed': 0, 'failed': 0}
        if status in worker_counts[provider]:
            worker_counts[provider][status] += 1

print(f"\nJob Status Summary: {status_counts}")
print(f"\nWorker Distribution:")
for worker, counts in sorted(worker_counts.items()):
    total = sum(counts.values())
    print(f"  {worker[-15:]}: {counts} (total: {total})")

# Active nodes
print("\n=== Active Nodes ===")
nodes = supabase.table('nodes').select('hardware_id, status, last_seen').eq('status', 'active').execute()
for n in nodes.data:
    print(f"  {n['hardware_id']}: {n['status']} (seen: {n['last_seen'][:19]})")
