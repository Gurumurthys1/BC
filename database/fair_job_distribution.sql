-- ============================================
-- Fair Job Distribution System
-- Ensures work is distributed evenly across all active workers
-- ============================================

-- Add columns for tracking worker load and job assignment
ALTER TABLE public.nodes ADD COLUMN IF NOT EXISTS current_jobs INTEGER DEFAULT 0;
ALTER TABLE public.nodes ADD COLUMN IF NOT EXISTS total_jobs_completed INTEGER DEFAULT 0;
ALTER TABLE public.nodes ADD COLUMN IF NOT EXISTS last_job_assigned TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.nodes ADD COLUMN IF NOT EXISTS worker_type TEXT DEFAULT 'browser' CHECK (worker_type IN ('browser', 'python', 'server'));

-- Add column to jobs for tracking assignment attempts
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS assignment_attempts INTEGER DEFAULT 0;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS preferred_worker TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP WITH TIME ZONE;

-- Create index for efficient worker selection
CREATE INDEX IF NOT EXISTS idx_nodes_load ON public.nodes(current_jobs, last_job_assigned);
CREATE INDEX IF NOT EXISTS idx_jobs_claimed ON public.jobs(claimed_at);

-- ============================================
-- Fair Job Claiming Function with Load Balancing
-- ============================================
CREATE OR REPLACE FUNCTION public.claim_job_fair(
    p_job_id BIGINT,
    p_provider_address TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_current_status TEXT;
    v_updated_count INT;
    v_worker_jobs INT;
    v_total_active_workers INT;
    v_avg_jobs NUMERIC;
BEGIN
    -- Get worker's current load
    SELECT COALESCE(current_jobs, 0) INTO v_worker_jobs
    FROM public.nodes
    WHERE hardware_id = p_provider_address;
    
    -- Get total active workers and average load
    SELECT COUNT(*), COALESCE(AVG(current_jobs), 0)
    INTO v_total_active_workers, v_avg_jobs
    FROM public.nodes
    WHERE status = 'active' 
    AND last_seen > NOW() - INTERVAL '60 seconds';
    
    -- Allow claim if worker has below average load OR if they're the only worker
    -- Or if they have fewer than 2 concurrent jobs (prevent starvation)
    IF v_worker_jobs >= 2 AND v_worker_jobs > v_avg_jobs + 1 AND v_total_active_workers > 1 THEN
        -- Worker is overloaded, let others take this job
        RETURN FALSE;
    END IF;
    
    -- Lock the row and get current status
    SELECT status INTO v_current_status
    FROM public.jobs
    WHERE id = p_job_id
    FOR UPDATE SKIP LOCKED;
    
    -- If job not found or already locked by another transaction
    IF v_current_status IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Only claim if status is 'pending'
    IF v_current_status != 'pending' THEN
        RETURN FALSE;
    END IF;
    
    -- Update the job
    UPDATE public.jobs
    SET status = 'processing',
        provider_address = p_provider_address,
        claimed_at = NOW()
    WHERE id = p_job_id
      AND status = 'pending';
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    
    -- If claimed successfully, update worker's job count
    IF v_updated_count > 0 THEN
        UPDATE public.nodes
        SET current_jobs = COALESCE(current_jobs, 0) + 1,
            last_job_assigned = NOW()
        WHERE hardware_id = p_provider_address;
    END IF;
    
    RETURN v_updated_count > 0;
END;
$$;

-- ============================================
-- Function to complete a job and update worker stats
-- ============================================
CREATE OR REPLACE FUNCTION public.complete_job(
    p_job_id BIGINT,
    p_provider_address TEXT,
    p_result_url TEXT DEFAULT NULL,
    p_status TEXT DEFAULT 'completed'
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_updated_count INT;
BEGIN
    -- Update the job
    UPDATE public.jobs
    SET status = p_status,
        result_url = COALESCE(p_result_url, result_url)
    WHERE id = p_job_id
      AND provider_address = p_provider_address
      AND status = 'processing';
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    
    -- Update worker stats
    IF v_updated_count > 0 THEN
        UPDATE public.nodes
        SET current_jobs = GREATEST(0, COALESCE(current_jobs, 0) - 1),
            total_jobs_completed = COALESCE(total_jobs_completed, 0) + CASE WHEN p_status = 'completed' THEN 1 ELSE 0 END,
            reputation = reputation + CASE WHEN p_status = 'completed' THEN 1 ELSE -1 END
        WHERE hardware_id = p_provider_address;
    END IF;
    
    RETURN v_updated_count > 0;
END;
$$;

-- ============================================
-- Function to get next job for a specific worker (fair assignment)
-- ============================================
CREATE OR REPLACE FUNCTION public.get_next_job_for_worker(
    p_provider_address TEXT
)
RETURNS TABLE(
    job_id BIGINT,
    job_type TEXT,
    model_hash TEXT,
    dataset_url TEXT,
    script_url TEXT,
    reward NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_worker_jobs INT;
    v_total_pending INT;
    v_total_workers INT;
BEGIN
    -- Get worker's current load
    SELECT COALESCE(current_jobs, 0) INTO v_worker_jobs
    FROM public.nodes
    WHERE hardware_id = p_provider_address;
    
    -- If worker already has 2+ jobs, don't assign more unless no other workers
    SELECT COUNT(*) INTO v_total_workers
    FROM public.nodes
    WHERE status = 'active' 
    AND last_seen > NOW() - INTERVAL '60 seconds'
    AND COALESCE(current_jobs, 0) < 2;
    
    IF v_worker_jobs >= 2 AND v_total_workers > 0 THEN
        RETURN; -- Return empty, let less loaded workers take jobs
    END IF;
    
    -- Return the oldest pending job
    RETURN QUERY
    SELECT j.id, j.job_type, j.model_hash, j.dataset_url, j.script_url, j.reward
    FROM public.jobs j
    WHERE j.status = 'pending'
    ORDER BY j.created_at ASC
    LIMIT 1;
END;
$$;

-- ============================================
-- Function to get worker statistics
-- ============================================
CREATE OR REPLACE FUNCTION public.get_worker_stats()
RETURNS TABLE(
    hardware_id TEXT,
    status TEXT,
    current_jobs INT,
    total_completed INT,
    reputation INT,
    worker_type TEXT,
    is_online BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        n.hardware_id,
        n.status,
        COALESCE(n.current_jobs, 0),
        COALESCE(n.total_jobs_completed, 0),
        COALESCE(n.reputation, 0),
        COALESCE(n.worker_type, 'browser'),
        n.last_seen > NOW() - INTERVAL '60 seconds' AS is_online
    FROM public.nodes n
    ORDER BY n.last_seen DESC;
END;
$$;

-- ============================================
-- Cleanup function for stale jobs
-- ============================================
CREATE OR REPLACE FUNCTION public.cleanup_stale_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_cleaned INT;
BEGIN
    -- Reset jobs that have been processing for more than 10 minutes
    -- and their worker is offline
    UPDATE public.jobs j
    SET status = 'pending',
        provider_address = NULL,
        claimed_at = NULL,
        assignment_attempts = COALESCE(assignment_attempts, 0) + 1
    WHERE j.status = 'processing'
      AND j.claimed_at < NOW() - INTERVAL '10 minutes'
      AND NOT EXISTS (
          SELECT 1 FROM public.nodes n 
          WHERE n.hardware_id = j.provider_address 
          AND n.last_seen > NOW() - INTERVAL '60 seconds'
      );
    
    GET DIAGNOSTICS v_cleaned = ROW_COUNT;
    
    -- Also decrement the job count for offline workers
    UPDATE public.nodes
    SET current_jobs = 0
    WHERE status = 'active'
      AND last_seen < NOW() - INTERVAL '60 seconds';
    
    RETURN v_cleaned;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.claim_job_fair(BIGINT, TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_job(BIGINT, TEXT, TEXT, TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_next_job_for_worker(TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_worker_stats() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.cleanup_stale_jobs() TO anon, authenticated;

-- Backward compatibility: Update original claim_job to use fair distribution
CREATE OR REPLACE FUNCTION public.claim_job(
    p_job_id BIGINT,
    p_provider_address TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Delegate to fair claiming function
    RETURN public.claim_job_fair(p_job_id, p_provider_address);
END;
$$;

GRANT EXECUTE ON FUNCTION public.claim_job(BIGINT, TEXT) TO anon, authenticated;

SELECT 'Fair job distribution functions created successfully' as result;
