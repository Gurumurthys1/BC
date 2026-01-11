-- Fix for missing columns in 'jobs' table

-- Add script_url if it doesn't exist
alter table public.jobs 
add column if not exists script_url text;

-- Add dataset_url if it doesn't exist
alter table public.jobs 
add column if not exists dataset_url text;

-- Add model_hash if it doesn't exist
alter table public.jobs 
add column if not exists model_hash text;

-- Add on_chain_id if it doesn't exist
alter table public.jobs 
add column if not exists on_chain_id numeric;

-- Add result_url if it doesn't exist
alter table public.jobs 
add column if not exists result_url text;

-- Ensure RLS policies cover updates to these columns (optional generally, but good practice)
-- Existing policies usually cover 'all', but we can verify.
-- The error was specifically about the column missing in the schema cache/definition.
