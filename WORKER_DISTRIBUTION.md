# Fair Job Distribution System - Production Setup

## Overview
The Oblivion platform now supports fair job distribution across all connected worker nodes. This ensures that work is split evenly among all participants, whether they're browser workers or Python workers.

## How It Works

### Worker Types
1. **Browser Workers**: Run directly in users' browsers when they connect their wallet and have the app open
2. **Python Workers**: Dedicated compute nodes running the `sharded_worker.py` script
3. **Server Workers**: (Future) High-performance server nodes

### Fair Distribution Algorithm
- Each worker has a `current_jobs` counter tracking active jobs
- Workers with fewer active jobs get priority for new assignments
- Maximum 2 concurrent jobs per worker (configurable)
- Stale jobs (processing > 10 min with offline worker) are automatically reset

### Job Claiming Process
1. Worker queries for pending jobs
2. Worker attempts atomic claim via `claim_job_fair` RPC function
3. If RPC unavailable, falls back to optimistic locking with verification
4. On success, worker's `current_jobs` is incremented
5. On completion, `current_jobs` is decremented and `total_jobs_completed` is incremented

## Setup Instructions

### 1. Apply Database Migrations
Run the following SQL file in your Supabase SQL Editor:
- `database/fair_job_distribution.sql`

This creates:
- New columns for load tracking (`current_jobs`, `total_jobs_completed`, `worker_type`)
- `claim_job_fair()` - Fair job claiming with load balancing
- `complete_job()` - Job completion with stats update
- `cleanup_stale_jobs()` - Automatic recovery of stuck jobs
- `get_worker_stats()` - Worker statistics for dashboard

### 2. Start Python Worker
```bash
cd node-client
python sharded_worker.py
```

The Python worker will:
- Register itself with `worker_type: 'python'`
- Send heartbeats every 15 seconds
- Poll for jobs every 2-5 seconds (adaptive)
- Respect load balancing (max 2 concurrent jobs)

### 3. Browser Workers
Browser workers automatically start when users:
1. Connect their wallet on the frontend
2. Enable the worker in the dashboard

Browser workers:
- Register with `worker_type: 'browser'`
- Send heartbeats every 15 seconds
- Poll for jobs every 3 seconds
- Process one job at a time

## Production Considerations

### Environment Variables
Ensure these are set for Python workers:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
RPC_URL=https://polygon-amoy-bor-rpc.publicnode.com
CONTRACT_ADDRESS=0x...
PRIVATE_KEY=0x...  # Optional, for on-chain settlement
```

### Scaling
- The system automatically balances across any number of workers
- Add more Python workers by running `sharded_worker.py` on different machines
- Each user running the frontend contributes browser compute
- Workers with high reputation get slightly higher priority (future enhancement)

### Monitoring
- View worker distribution in the "Network" tab
- Real-time stats show:
  - Online workers count
  - Active jobs per worker
  - Total completed jobs
  - Worker types (browser/python/server)

### Error Recovery
- Jobs stuck in "processing" for > 10 minutes with offline workers are auto-reset
- Workers verify claims to prevent race conditions
- Failed jobs don't count against worker reputation

## API Reference

### RPC Functions

#### `claim_job_fair(p_job_id, p_provider_address)`
Atomically claim a job with load balancing.
- Returns: `boolean`

#### `complete_job(p_job_id, p_provider_address, p_result_url, p_status)`
Complete a job and update worker stats.
- Returns: `boolean`

#### `cleanup_stale_jobs()`
Reset stuck jobs from offline workers.
- Returns: `integer` (count of cleaned jobs)

#### `get_worker_stats()`
Get all worker statistics for dashboard.
- Returns: Table of worker stats

## Troubleshooting

### Jobs not being picked up
1. Check worker is online: `nodes.last_seen` should be within 60 seconds
2. Verify worker is registered with correct `hardware_id`
3. Check browser console for errors (browser workers)

### One worker getting all jobs
1. Ensure `claim_job_fair` RPC is deployed
2. Check other workers are sending heartbeats
3. Verify `current_jobs` isn't stuck (cleanup should fix this)

### Jobs stuck in processing
1. Wait for cleanup (runs every 15 seconds via heartbeat)
2. Manually reset: `UPDATE jobs SET status='pending', provider_address=NULL WHERE id=X`
