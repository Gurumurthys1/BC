-- Create the atomic claim_job function for secure job claiming
-- This prevents race conditions when multiple workers try to claim the same job

CREATE OR REPLACE FUNCTION public.claim_job(p_job_id BIGINT, p_provider_address TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_current_status TEXT;
    v_updated_count INT;
BEGIN
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
        provider_address = p_provider_address
    WHERE id = p_job_id
      AND status = 'pending';
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    
    RETURN v_updated_count > 0;
END;
$$;

-- Grant execute permission to authenticated and anon users
GRANT EXECUTE ON FUNCTION public.claim_job(BIGINT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.claim_job(BIGINT, TEXT) TO anon;

-- Notify that function was created
SELECT 'claim_job function created successfully' as result;
