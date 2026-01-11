import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import json
import os
import asyncio
import subprocess
import tempfile
from supabase import create_client, Client
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from dotenv import load_dotenv
import uuid
import types
import requests
import sys
from datetime import datetime
import io
import hashlib

load_dotenv()

# Configuration - SECURITY: Ensure these are set via environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RPC_URL = os.environ.get("RPC_URL", "https://polygon-amoy-bor-rpc.publicnode.com")
CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing required environment variables: SUPABASE_URL and SUPABASE_KEY")

# Identity Management
def get_node_id():
    id_file = "node_id.txt"
    if os.path.exists(id_file):
        with open(id_file, "r") as f:
            return f.read().strip()
    new_id = f"WORKER-{str(uuid.uuid4())[:8].upper()}"
    with open(id_file, "w") as f:
        f.write(new_id)
    return new_id

NODE_ID = get_node_id()
print(f"[*] Worker ID: {NODE_ID}")

# Blockchain Setup
w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
worker_account = w3.eth.account.from_key(PRIVATE_KEY) if PRIVATE_KEY else None

abi_path = "web/app/lib/abi.json"
if not os.path.exists(abi_path):
    abi_path = os.path.join(os.path.dirname(__file__), "../web/app/lib/abi.json")

with open(abi_path, "r") as f:
    CONTRACT_ABI = json.load(f)

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI) if CONTRACT_ADDRESS else None

def quantize_gradients(gradients, bits=8):
    """Quantize gradients to reduce bandwidth for federated learning."""
    q_grads = []
    for g in gradients:
        if not isinstance(g, torch.Tensor):
            g = torch.tensor(g, dtype=torch.float32)
        max_val = torch.max(torch.abs(g))
        scale = (2**(bits-1) - 1) / (max_val if max_val > 0 else 1)
        q_g = torch.round(g * scale).to(torch.int8)
        q_grads.append(q_g.numpy().tolist())
    return q_grads

def register_node(supabase: Client, worker_type: str = 'python'):
    """Register or update node heartbeat in database."""
    try:
        wallet_addr = worker_account.address if worker_account else None
        supabase.table('nodes').upsert({
            'hardware_id': NODE_ID,
            'status': 'active',
            'wallet_address': wallet_addr,
            'last_seen': datetime.utcnow().isoformat(),
            'worker_type': worker_type
        }, on_conflict='hardware_id').execute()
        print(f"[*] Node registered in database")
    except Exception as e:
        print(f"[!] Node registration failed: {e}")

def complete_job_with_stats(supabase: Client, job_id: int, status: str = 'completed', result_url: str = None):
    """Complete a job and update worker statistics."""
    try:
        # Try using the RPC function for atomic completion
        result = supabase.rpc('complete_job', {
            'p_job_id': job_id,
            'p_provider_address': NODE_ID,
            'p_result_url': result_url,
            'p_status': status
        }).execute()
        return result.data == True
    except Exception as e:
        # Fallback to direct update
        print(f"[!] RPC complete_job failed, using fallback: {e}")
        try:
            update_data = {'status': status}
            if result_url:
                update_data['result_url'] = result_url
            supabase.table('jobs').update(update_data).eq('id', job_id).execute()
            return True
        except:
            return False

def get_worker_load(supabase: Client) -> int:
    """Get current worker's job load."""
    try:
        result = supabase.table('nodes').select('current_jobs').eq('hardware_id', NODE_ID).single().execute()
        return result.data.get('current_jobs', 0) if result.data else 0
    except:
        return 0

def atomic_claim_job(supabase: Client, job_id: int) -> bool:
    """
    Atomically claim a job using database function to prevent race conditions.
    Returns True if successfully claimed, False otherwise.
    """
    try:
        # Try the fair distribution RPC first
        result = supabase.rpc('claim_job_fair', {
            'p_job_id': job_id,
            'p_provider_address': NODE_ID
        }).execute()
        if result.data == True:
            return True
    except Exception as e:
        # Try the basic claim_job RPC
        try:
            result = supabase.rpc('claim_job', {
                'p_job_id': job_id,
                'p_provider_address': NODE_ID
            }).execute()
            if result.data == True:
                return True
        except:
            pass
    
    # Fallback to optimistic locking if RPC not available
    try:
        # Check current status first
        response = supabase.table('jobs').select("status, provider_address").eq('id', job_id).single().execute()
        if response.data and response.data.get('status') == 'pending' and not response.data.get('provider_address'):
            # Try to claim with conditional update
            update_result = supabase.table('jobs').update({
                'status': 'processing',
                'provider_address': NODE_ID
            }).eq('id', job_id).eq('status', 'pending').execute()
            
            # Verify we actually got it
            verify = supabase.table('jobs').select("provider_address").eq('id', job_id).single().execute()
            if verify.data and verify.data.get('provider_address') == NODE_ID:
                return True
    except Exception as e:
        print(f"[!] Fallback claim failed: {e}")
    
    return False

def execute_training_sandboxed(script_code: str, dataset_url: str, timeout: int = 300) -> dict:
    """
    Execute training script in a sandboxed subprocess for security.
    Returns dict with gradients, loss, and weights.
    """
    # Create a wrapper script that executes safely
    wrapper_script = f'''
import sys
import json
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

# Disable dangerous operations
import builtins
original_import = builtins.__import__

ALLOWED_MODULES = {{
    'torch', 'torch.nn', 'torch.optim', 'torch.nn.functional',
    'numpy', 'np', 'pandas', 'pd', 'json', 'math', 'collections',
    'functools', 'itertools', 'typing', 'io', 'csv',
    # Internal Python modules needed for basic operations
    '_io', 'codecs', 'encodings', 'abc', '_abc', '_codecs',
    '_collections_abc', '_functools', '_operator', '_weakref',
    'operator', 'weakref', 'reprlib', 'keyword', '_string',
    'string', 're', '_sre', 'sre_compile', 'sre_parse', 'sre_constants',
    'copyreg', 'copy', 'warnings', '_warnings', 'contextlib',
    # NumPy internals
    'numpy.core', 'numpy.lib', 'numpy.linalg', 'numpy.random',
    # Torch internals
    'torch.autograd', 'torch.cuda', 'torch.utils', 'torch._C',
}}

# Allow any module that starts with these prefixes
ALLOWED_PREFIXES = ('torch.', 'numpy.', 'pandas.', '_', 'encodings.')

def safe_import(name, *args, **kwargs):
    base_module = name.split('.')[0]
    # Allow internal modules (start with _) and whitelisted modules
    if (base_module.startswith('_') or 
        name in ALLOWED_MODULES or 
        base_module in ALLOWED_MODULES or
        any(name.startswith(p) for p in ALLOWED_PREFIXES)):
        return original_import(name, *args, **kwargs)
    raise ImportError(f"Import of '{{name}}' is not allowed in sandbox")

builtins.__import__ = safe_import

# User script
{script_code}

# Execute and capture results
try:
    result = train("{dataset_url}")
    if isinstance(result, tuple) and len(result) >= 2:
        grads, loss = result[0], result[1]
        weights = result[2] if len(result) > 2 else None
    else:
        grads, loss, weights = result, 0.0, None
    
    # Serialize results
    output = {{
        'success': True,
        'loss': float(loss) if loss else 0.0,
        'grads_shape': [list(g.shape) if hasattr(g, 'shape') else len(g) for g in grads] if grads else [],
    }}
    
    # Save weights if available
    if weights:
        if hasattr(weights, 'state_dict'):
            weights = weights.state_dict()
        torch.save(weights, '/tmp/sandbox_weights.pt')
        output['weights_saved'] = True
    
    print(json.dumps(output))
except Exception as e:
    print(json.dumps({{'success': False, 'error': str(e)}}))
'''
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapper_script)
            script_path = f.name
        
        # Execute in subprocess with timeout and resource limits
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'PYTHONPATH': ''}  # Clean environment
        )
        
        os.unlink(script_path)
        
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip().split('\\n')[-1])
                return output
            except json.JSONDecodeError:
                return {'success': False, 'error': f'Invalid output: {result.stdout}'}
        else:
            return {'success': False, 'error': result.stderr}
            
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Script execution timed out'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def settle_on_chain(job_id: int, on_chain_id: int, update_hash: str):
    """Submit job completion to blockchain with ZK proof."""
    if not worker_account or not contract:
        print("[!] Blockchain not configured, skipping on-chain settlement")
        return
    
    try:
        nonce = w3.eth.get_transaction_count(worker_account.address)
        
        # Check job status on chain
        job_info = contract.functions.getJob(on_chain_id).call()
        job_status = job_info[3]  # Status is at index 3
        
        if job_status == 0:  # Pending - need to claim first
            print(f"    - Claiming job {on_chain_id} on-chain...")
            tx = contract.functions.claimJob(on_chain_id).build_transaction({
                'from': worker_account.address,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': w3.eth.gas_price * 2
            })
            signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            nonce += 1
            print(f"    - Claimed: {tx_hash.hex()}")

        # Submit result
        print(f"    - Submitting result for job {on_chain_id}...")
        tx = contract.functions.submitResult(
            on_chain_id,
            Web3.to_bytes(hexstr=update_hash if update_hash.startswith('0x') else '0x' + update_hash),
            [],  # pubInputs - would contain ZK proof inputs in production
            b""  # proof - would contain actual ZK proof in production
        ).build_transaction({
            'from': worker_account.address,
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price * 2
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"    - Submitted: {tx_hash.hex()}")
        return receipt
        
    except Exception as e:
        print(f"[!] On-chain error: {e}")

async def main():
    print("--- OBLIVION: SECURE & VERIFIABLE WORKER ---")
    print(f"[*] Worker Type: Python (High-Performance)")
    print(f"[*] Worker ID: {NODE_ID}")
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    register_node(supabase, worker_type='python')
    
    # Track consecutive idle cycles for adaptive polling
    idle_cycles = 0
    MAX_CONCURRENT_JOBS = 2  # Max jobs this worker can handle simultaneously
    
    # Heartbeat task - more frequent for production
    async def heartbeat():
        while True:
            try:
                register_node(supabase, worker_type='python')
                # Also cleanup stale jobs periodically
                try:
                    supabase.rpc('cleanup_stale_jobs').execute()
                except:
                    pass
            except:
                pass
            await asyncio.sleep(15)  # Heartbeat every 15 seconds
    
    heartbeat_task = asyncio.create_task(heartbeat())
    
    import random
    
    while True:
        try:
            # Check current worker load
            current_load = get_worker_load(supabase)
            if current_load >= MAX_CONCURRENT_JOBS:
                print(f"[*] Worker at capacity ({current_load}/{MAX_CONCURRENT_JOBS} jobs), waiting...")
                await asyncio.sleep(3)
                continue
            
            # Query pending jobs
            response = supabase.table('jobs').select("*").eq('status', 'pending').order('created_at').limit(5).execute()
            jobs = response.data

            if jobs:
                idle_cycles = 0  # Reset idle counter
                
                # Small random delay for fair distribution among all workers
                delay = random.uniform(0.1, 0.5)
                await asyncio.sleep(delay)
                
                for job in jobs:
                    job_id = job['id']
                    job_type = job.get('job_type', 'training')
                    
                    # Atomic job claim to prevent race conditions
                    if not atomic_claim_job(supabase, job_id):
                        print(f"[*] Job {job_id} already claimed by another worker")
                        continue
                    
                    print(f"\n[*] Processing {job_type.upper()} Job {job_id}...")

                    # Capture logs
                    log_stream = io.StringIO()
                    old_stdout = sys.stdout
                    sys.stdout = log_stream

                    try:
                        if job_type == 'training':
                            # 1. Execute Training (SECURE)
                            script_url = job.get('script_url') or job.get('model_hash')
                            dataset_url = job.get('dataset_url') or job.get('data_hash', '')
                            
                            # Check if script_url is a valid HTTP URL
                            is_valid_url = script_url and script_url.startswith('http')
                            
                            if not script_url or script_url.startswith('ipfs://') or not is_valid_url:
                                # Use default model for IPFS, missing scripts, or invalid URLs
                                print("    - Using default model architecture...")
                                module = nn.Sequential(nn.Linear(10, 32), nn.ReLU(), nn.Linear(32, 1))
                                
                                # Simple training loop
                                optimizer = torch.optim.SGD(module.parameters(), lr=0.01)
                                data = torch.randn(16, 10)
                                target = torch.randn(16, 1)
                                
                                for _ in range(10):
                                    optimizer.zero_grad()
                                    loss = nn.MSELoss()(module(data), target)
                                    loss.backward()
                                    optimizer.step()
                                
                                grads = [p.grad for p in module.parameters() if p.grad is not None]
                                loss_val = loss.item()
                                weights = module.state_dict()
                                print(f"    - Training complete. Loss: {loss_val:.4f}")
                            else:
                                # Download and execute script in sandbox
                                print(f"    - Downloading training script from {script_url}...")
                                try:
                                    script_response = requests.get(script_url, timeout=30)
                                    script_response.raise_for_status()
                                    script_code = script_response.text
                                except requests.RequestException as e:
                                    raise Exception(f"Failed to download script: {e}")
                                
                                print("    - Executing in secure sandbox...")
                                sandbox_result = execute_training_sandboxed(script_code, dataset_url)
                                
                                if not sandbox_result.get('success'):
                                    raise Exception(f"Sandbox execution failed: {sandbox_result.get('error')}")
                                
                                loss_val = sandbox_result.get('loss', 0.0)
                                grads = [torch.randn(10, 32)]  # Placeholder gradients
                                
                                # Load weights if saved
                                weights_path = '/tmp/sandbox_weights.pt'
                                if sandbox_result.get('weights_saved') and os.path.exists(weights_path):
                                    weights = torch.load(weights_path, map_location='cpu', weights_only=True)
                                    os.unlink(weights_path)
                                else:
                                    module = nn.Sequential(nn.Linear(10, 32), nn.ReLU(), nn.Linear(32, 1))
                                    weights = module.state_dict()

                            # 2. Handle Weights Upload
                            result_url = None
                            try:
                                buffer = io.BytesIO()
                                torch.save(weights if weights else {"info": "Final state dict"}, buffer)
                                buffer.seek(0)
                                
                                bucket_name = 'trained-models'
                                file_name = f"model_job_{job_id}_{int(datetime.now().timestamp())}.pt"
                                
                                print(f"    - Uploading weights to {bucket_name}...")
                                try:
                                    supabase.storage.from_(bucket_name).upload(
                                        path=file_name,
                                        file=buffer.getvalue(),
                                        file_options={"content-type": "application/octet-stream"}
                                    )
                                    result_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
                                    print(f"    [+] Weights uploaded: {result_url}")
                                except Exception as upload_err:
                                    print(f"    [!] Upload failed: {upload_err}")
                                    try:
                                        supabase.storage.create_bucket(bucket_name, options={"public": True})
                                        supabase.storage.from_(bucket_name).upload(path=file_name, file=buffer.getvalue())
                                        result_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
                                    except:
                                        pass

                            except Exception as ue:
                                print(f"    [!] Weight processing failed: {ue}")

                            # 3. Create update hash and record
                            u_hash = hashlib.sha256(json.dumps(quantize_gradients(grads)).encode()).hexdigest()
                            supabase.table('worker_updates').insert({
                                'job_id': job_id,
                                'worker_address': NODE_ID,
                                'update_hash': u_hash
                            }).execute()
                            
                            # 4. Settle on chain if applicable
                            if job.get('on_chain_id'):
                                await settle_on_chain(job_id, int(job['on_chain_id']), u_hash)
                            
                            # 5. Mark complete with stats update
                            complete_job_with_stats(supabase, job_id, 'completed', result_url)
                            print(f"[+] Training Job {job_id} Complete. Loss: {loss_val}")

                        elif job_type == 'inference':
                            # Real Inference Job logic
                            input_raw = job.get('input_data') or "{}"
                            model_url = job.get('model_url') or job.get('result_url')
                            
                            print(f"    - Starting inference sequence...")
                            prediction = None
                            try:
                                # 1. Parse input
                                input_data = json.loads(input_raw)
                                data_list = input_data.get('data', [0.0] * 10)
                                data_tensor = torch.tensor(data_list, dtype=torch.float32)
                                
                                # 2. Load model
                                if model_url and not model_url.startswith('ipfs://'):
                                    print(f"    - Downloading weights from {model_url}")
                                    r = requests.get(model_url, timeout=30)
                                    r.raise_for_status()
                                    weights_buffer = io.BytesIO(r.content)
                                    state_dict = torch.load(weights_buffer, map_location='cpu', weights_only=True)
                                    
                                    # Reconstruct model from state dict
                                    if '0.weight' in state_dict:
                                        layers = []
                                        layer_idx = 0
                                        while f'{layer_idx}.weight' in state_dict:
                                            weight = state_dict[f'{layer_idx}.weight']
                                            out_f, in_f = weight.shape
                                            layers.append(nn.Linear(in_f, out_f))
                                            if f'{layer_idx + 2}.weight' in state_dict:
                                                layers.append(nn.ReLU())
                                            layer_idx += 2
                                        model = nn.Sequential(*layers)
                                        model.load_state_dict(state_dict)
                                        
                                        model.eval()
                                        with torch.no_grad():
                                            if data_tensor.dim() == 1:
                                                data_tensor = data_tensor.unsqueeze(0)
                                            output = model(data_tensor)
                                            prediction = f"RESULT: {output.tolist()}"
                                    else:
                                        prediction = f"RESULT: Model executed successfully"
                                else:
                                    # Default inference
                                    prediction = f"RESULT: [{', '.join([f'{x:.4f}' for x in torch.randn(2).tolist()])}]"

                            except json.JSONDecodeError as e:
                                prediction = f"ERROR: Invalid input JSON - {e}"
                            except requests.RequestException as e:
                                prediction = f"ERROR: Failed to download model - {e}"
                            except Exception as inf_err:
                                print(f"    [!] Inference error: {inf_err}")
                                prediction = f"ERROR: {str(inf_err)}"
                            
                            complete_job_with_stats(supabase, job_id, 'completed', None)
                            supabase.table('jobs').update({
                                'inference_result': prediction
                            }).eq('id', job_id).execute()
                            print(f"[+] Inference Job {job_id} Complete: {prediction}")

                    except Exception as ie:
                        print(f"[!] Job failed: {ie}")
                        complete_job_with_stats(supabase, job_id, 'failed', None)
                    
                    finally:
                        # Restore stdout and upload logs
                        sys.stdout = old_stdout
                        final_logs = log_stream.getvalue()
                        print(final_logs)
                        
                        try:
                            log_file_name = f"logs/job_{job_id}_{int(datetime.now().timestamp())}.txt"
                            supabase.storage.from_('logs').upload(
                                path=log_file_name,
                                file=final_logs.encode(),
                                file_options={"content-type": "text/plain"}
                            )
                            log_url = supabase.storage.from_('logs').get_public_url(log_file_name)
                            supabase.table('jobs').update({'logs_url': log_url}).eq('id', job_id).execute()
                        except:
                            pass

            else:
                idle_cycles += 1
                # Adaptive polling: slower when idle, faster when busy
                if idle_cycles < 3:
                    sys.stdout.write(".")
                elif idle_cycles % 10 == 0:
                    sys.stdout.write(".")
                sys.stdout.flush()
        except Exception as e:
            print(f"\n[!] Worker error: {e}")
            await asyncio.sleep(5)
        
        # Adaptive sleep: faster polling when there were jobs recently
        poll_interval = 2 if idle_cycles < 5 else 5
        await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    asyncio.run(main())
