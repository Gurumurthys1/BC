import torch
import torch.nn as nn
import json
import os
import asyncio
import requests
import io
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Configuration - SECURITY: Ensure these are set via environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing required environment variables: SUPABASE_URL and SUPABASE_KEY")

async def aggregate_updates(supabase: Client, job_id: int) -> dict:
    """
    Perform Federated Averaging (FedAvg) on worker updates.
    Downloads model weights from all workers and averages them.
    Returns the aggregated model state dict.
    """
    print(f"[*] Aggregating updates for Job {job_id}...")
    
    # 1. Fetch all updates for this job
    updates_res = supabase.table('worker_updates').select("*").eq('job_id', job_id).execute()
    updates = updates_res.data
    
    if not updates:
        print("    - No updates found.")
        return None

    print(f"    - Found {len(updates)} worker updates. Running FedAvg...")
    
    # 2. Download and aggregate model weights
    aggregated_state = None
    successful_updates = 0
    
    for update in updates:
        update_url = update.get('update_url')
        if not update_url:
            continue
            
        try:
            # Download model weights
            response = requests.get(update_url, timeout=30)
            response.raise_for_status()
            
            weights_buffer = io.BytesIO(response.content)
            state_dict = torch.load(weights_buffer, map_location='cpu', weights_only=True)
            
            if aggregated_state is None:
                # Initialize with first model's structure
                aggregated_state = {k: v.clone().float() for k, v in state_dict.items()}
            else:
                # Add weights to running sum
                for key in aggregated_state:
                    if key in state_dict:
                        aggregated_state[key] += state_dict[key].float()
            
            successful_updates += 1
            print(f"    - Processed update from {update.get('worker_address', 'unknown')}")
            
        except Exception as e:
            print(f"    [!] Failed to process update {update.get('id')}: {e}")
            continue
    
    if successful_updates == 0:
        print("    - No valid updates to aggregate")
        return None
    
    # 3. Average the weights (FedAvg)
    for key in aggregated_state:
        aggregated_state[key] /= successful_updates
    
    print(f"[+] Global Model Updated. Aggregated {successful_updates} updates.")
    return aggregated_state

async def save_global_model(supabase: Client, job_id: int, state_dict: dict) -> str:
    """Save the aggregated global model to storage."""
    try:
        buffer = io.BytesIO()
        torch.save(state_dict, buffer)
        buffer.seek(0)
        
        bucket_name = 'global-models'
        file_name = f"global_model_job_{job_id}_{int(datetime.now().timestamp())}.pt"
        
        try:
            supabase.storage.from_(bucket_name).upload(
                path=file_name,
                file=buffer.getvalue(),
                file_options={"content-type": "application/octet-stream"}
            )
        except:
            # Create bucket if it doesn't exist
            supabase.storage.create_bucket(bucket_name, options={"public": True})
            supabase.storage.from_(bucket_name).upload(
                path=file_name,
                file=buffer.getvalue(),
                file_options={"content-type": "application/octet-stream"}
            )
        
        model_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        print(f"    - Global model saved: {model_url}")
        return model_url
        
    except Exception as e:
        print(f"    [!] Failed to save global model: {e}")
        return None

async def main():
    print("--- OBLIVION: FEDERATED AGGREGATOR ---")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    while True:
        try:
            # Poll for training jobs that are completed but not yet aggregated
            # We look for jobs with multiple worker updates that haven't been processed
            response = supabase.table('jobs').select("id, status, job_type").eq('status', 'completed').eq('job_type', 'training').execute()
            jobs = response.data

            if jobs:
                for job in jobs:
                    job_id = job['id']
                    
                    # Check if we have multiple updates for this job
                    updates_count = supabase.table('worker_updates').select("id", count='exact').eq('job_id', job_id).execute()
                    
                    if updates_count.count and updates_count.count > 1:
                        # Aggregate the updates
                        aggregated_state = await aggregate_updates(supabase, job_id)
                        
                        if aggregated_state:
                            # Save the global model
                            model_url = await save_global_model(supabase, job_id, aggregated_state)
                            
                            if model_url:
                                # Update the job with the aggregated model URL
                                supabase.table('jobs').update({
                                    'result_url': model_url
                                }).eq('id', job_id).execute()
                                
                                print(f"[+] Job {job_id} aggregation complete: {model_url}")
            else:
                print(".", end="", flush=True)
            
        except Exception as e:
            print(f"\n[!] Aggregator Error: {e}")
            
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
