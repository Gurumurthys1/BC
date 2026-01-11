import asyncio
import time
import os
import json
from supabase import create_client, Client
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# Configuration - SECURITY: Ensure these are set via environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RPC_URL = os.environ.get("RPC_URL", "https://polygon-amoy-bor-rpc.publicnode.com")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing required environment variables: SUPABASE_URL and SUPABASE_KEY")

async def main():
    print("Starting Oblivion Node Client...")
    
    # 1. Connect to Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Connected to Supabase.")
    
    # 2. Connect to Blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    print(f"Connected to Blockchain: {RPC_URL}")
    
    # 3. Hardware Handshake
    hardware_id = "GPU-RTX-4090-OBLIVION-01"
    print(f"Hardware Identity Verified: {hardware_id}")
    
    # 4. Main Loop
    while True:
        try:
            print("Polling for pending jobs...")
            response = supabase.table('jobs').select("*").eq('status', 'pending').execute()
            jobs = response.data

            if jobs:
                for job in jobs:
                    job_type = job.get('job_type', 'inference')
                    print(f"Processing job {job['id']}: Type={job_type}")
                    
                    # Update status to processing
                    supabase.table('jobs').update({
                        'status': 'processing', 
                        'provider_address': hardware_id
                    }).eq('id', job['id']).execute()
                    
                    # Mock Inference & Proof Generation
                    print("Running ZK-Inference...")
                    time.sleep(3) 
                    
                    # Submitting proof (Placeholder for actual contract call)
                    print(f"Submitting proof for job {job['id']} to chain...")
                    tx_hash = "0x" + "f" * 64  # Mock hash
                    
                    # Mark as completed with correct column names
                    update_data = {
                        'status': 'completed', 
                        'tx_hash': tx_hash,
                    }
                    if job_type == 'inference':
                        update_data['inference_result'] = 'Inference Result: [1.2, -0.5]'
                    else:
                        update_data['result_url'] = f'https://storage.example.com/model_{job["id"]}.pt'
                    
                    supabase.table('jobs').update(update_data).eq('id', job['id']).execute()
                    
                    print(f"Job {job['id']} completed successfully.")
            else:
                print("No pending jobs. Waiting...")
        
        except Exception as e:
            print(f"Error in node loop: {e}")
        
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down node.")
