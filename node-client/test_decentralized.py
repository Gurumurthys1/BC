"""
Test the fully decentralized OBLIVION system
Tests blockchain-only job coordination (no Supabase)
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# New contract address
CONTRACT_ADDRESS = "0x9EE623E30Ad75C156099d9309924bd989b8f37c4"

# ABI for simplified contract
CONTRACT_ABI = [
    {"inputs": [{"name": "_verifier", "type": "address"}], "stateMutability": "nonpayable", "type": "constructor"},
    {"anonymous": False, "inputs": [{"indexed": True, "name": "jobId", "type": "uint256"}, {"indexed": True, "name": "requester", "type": "address"}, {"indexed": False, "name": "reward", "type": "uint256"}, {"indexed": False, "name": "scriptHash", "type": "string"}, {"indexed": False, "name": "dataHash", "type": "string"}], "name": "JobCreated", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "name": "jobId", "type": "uint256"}, {"indexed": True, "name": "worker", "type": "address"}], "name": "JobClaimed", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "name": "jobId", "type": "uint256"}, {"indexed": True, "name": "worker", "type": "address"}, {"indexed": False, "name": "modelHash", "type": "string"}], "name": "JobCompleted", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "name": "worker", "type": "address"}, {"indexed": False, "name": "nodeId", "type": "string"}, {"indexed": False, "name": "stake", "type": "uint256"}], "name": "WorkerRegistered", "type": "event"},
    {"inputs": [{"name": "_nodeId", "type": "string"}], "name": "registerWorker", "outputs": [], "stateMutability": "payable", "type": "function"},
    {"inputs": [], "name": "depositStake", "outputs": [], "stateMutability": "payable", "type": "function"},
    {"inputs": [{"name": "_scriptHash", "type": "string"}, {"name": "_dataHash", "type": "string"}], "name": "createJob", "outputs": [], "stateMutability": "payable", "type": "function"},
    {"inputs": [{"name": "_jobId", "type": "uint256"}], "name": "claimJob", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "_jobId", "type": "uint256"}, {"name": "_modelHash", "type": "string"}], "name": "submitResult", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "_jobId", "type": "uint256"}], "name": "cancelJob", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "getJobCount", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "_jobId", "type": "uint256"}], "name": "getJob", "outputs": [{"name": "requester", "type": "address"}, {"name": "worker", "type": "address"}, {"name": "reward", "type": "uint256"}, {"name": "status", "type": "uint256"}, {"name": "scriptHash", "type": "string"}, {"name": "dataHash", "type": "string"}, {"name": "modelHash", "type": "string"}, {"name": "createdAt", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "_addr", "type": "address"}], "name": "getWorker", "outputs": [{"name": "stake", "type": "uint256"}, {"name": "completedJobs", "type": "uint256"}, {"name": "reputation", "type": "uint256"}, {"name": "isActive", "type": "bool"}, {"name": "nodeId", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getWorkerCount", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getStats", "outputs": [{"name": "totalJobs", "type": "uint256"}, {"name": "pendingJobs", "type": "uint256"}, {"name": "completedJobs", "type": "uint256"}, {"name": "activeWorkers", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "MIN_STAKE", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]

def test_blockchain_connection():
    """Test connection to blockchain and contract"""
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    
    print("=" * 60)
    print("   TESTING DECENTRALIZED OBLIVION SYSTEM")
    print("=" * 60)
    print()
    
    # Connect to Polygon Amoy
    rpc_url = "https://polygon-amoy-bor-rpc.publicnode.com"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    if not w3.is_connected():
        print("❌ Failed to connect to Polygon Amoy")
        return False
    
    print(f"✅ Connected to Polygon Amoy")
    print(f"   Block: {w3.eth.block_number}")
    
    # Load contract
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI
    )
    
    print(f"✅ Contract loaded: {CONTRACT_ADDRESS}")
    
    # Get contract stats
    try:
        stats = contract.functions.getStats().call()
        print()
        print("📊 CONTRACT STATISTICS:")
        print(f"   Total Jobs:    {stats[0]}")
        print(f"   Pending Jobs:  {stats[1]}")
        print(f"   Completed:     {stats[2]}")
        print(f"   Active Workers: {stats[3]}")
        
        min_stake = contract.functions.MIN_STAKE().call()
        print(f"   Min Stake:     {w3.from_wei(min_stake, 'ether')} MATIC")
    except Exception as e:
        print(f"❌ Error reading contract: {e}")
        return False
    
    # Check wallet
    private_key = os.getenv('PRIVATE_KEY')
    if private_key:
        from eth_account import Account
        account = Account.from_key(private_key)
        balance = w3.eth.get_balance(account.address)
        
        print()
        print("💰 WALLET:")
        print(f"   Address: {account.address}")
        print(f"   Balance: {w3.from_wei(balance, 'ether'):.4f} MATIC")
        
        # Check if registered as worker
        worker_info = contract.functions.getWorker(account.address).call()
        if worker_info[3]:  # isActive
            print()
            print("👷 WORKER STATUS:")
            print(f"   Stake: {w3.from_wei(worker_info[0], 'ether')} MATIC")
            print(f"   Completed Jobs: {worker_info[1]}")
            print(f"   Reputation: {worker_info[2]}")
            print(f"   Node ID: {worker_info[4]}")
        else:
            print()
            print("⚠️  Not registered as worker yet")
    
    print()
    print("=" * 60)
    print("✅ All tests passed! System is operational.")
    print("=" * 60)
    
    return True


def register_worker(node_id: str = "TEST-WORKER-001"):
    """Register as a worker on-chain"""
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    from eth_account import Account
    
    rpc_url = "https://polygon-amoy-bor-rpc.publicnode.com"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        print("❌ PRIVATE_KEY not set")
        return
    
    account = Account.from_key(private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI
    )
    
    # Check if already registered
    worker_info = contract.functions.getWorker(account.address).call()
    if worker_info[3]:
        print(f"✅ Already registered as worker: {worker_info[4]}")
        return
    
    # Register with min stake
    min_stake = contract.functions.MIN_STAKE().call()
    
    print(f"📝 Registering worker: {node_id}")
    print(f"   Stake: {w3.from_wei(min_stake, 'ether')} MATIC")
    
    tx = contract.functions.registerWorker(node_id).build_transaction({
        'from': account.address,
        'value': min_stake,
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address)
    })
    
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"   Transaction: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        print("✅ Worker registered successfully!")
    else:
        print("❌ Registration failed")


def create_test_job(reward_matic: float = 0.001):
    """Create a test job on-chain"""
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    from eth_account import Account
    
    rpc_url = "https://polygon-amoy-bor-rpc.publicnode.com"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        print("❌ PRIVATE_KEY not set")
        return
    
    account = Account.from_key(private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI
    )
    
    reward_wei = w3.to_wei(reward_matic, 'ether')
    script_hash = "ipfs://QmTestScript123"
    data_hash = "ipfs://QmTestData456"
    
    print(f"📝 Creating test job")
    print(f"   Reward: {reward_matic} MATIC")
    print(f"   Script: {script_hash}")
    print(f"   Data: {data_hash}")
    
    tx = contract.functions.createJob(script_hash, data_hash).build_transaction({
        'from': account.address,
        'value': reward_wei,
        'gas': 300000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address)
    })
    
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"   Transaction: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        job_count = contract.functions.getJobCount().call()
        print(f"✅ Job created! ID: {job_count - 1}")
    else:
        print("❌ Job creation failed")


def list_jobs():
    """List all jobs on-chain"""
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    
    rpc_url = "https://polygon-amoy-bor-rpc.publicnode.com"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI
    )
    
    job_count = contract.functions.getJobCount().call()
    
    print(f"\n📋 JOBS ON-CHAIN ({job_count} total)")
    print("-" * 60)
    
    status_names = ['Pending', 'Processing', 'Completed', 'Cancelled', 'Slashed']
    
    for i in range(job_count):
        job = contract.functions.getJob(i).call()
        status = status_names[job[3]] if job[3] < len(status_names) else 'Unknown'
        reward = w3.from_wei(job[2], 'ether')
        
        print(f"  Job {i}: {status}")
        print(f"    Reward: {reward} MATIC")
        print(f"    Requester: {job[0][:10]}...")
        if job[1] != "0x0000000000000000000000000000000000000000":
            print(f"    Worker: {job[1][:10]}...")
        if job[6]:
            print(f"    Model: {job[6][:30]}...")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test decentralized OBLIVION system')
    parser.add_argument('command', nargs='?', default='test',
                       choices=['test', 'register', 'create', 'list'],
                       help='Command to run')
    
    args = parser.parse_args()
    
    if args.command == 'test':
        test_blockchain_connection()
    elif args.command == 'register':
        register_worker()
    elif args.command == 'create':
        create_test_job()
    elif args.command == 'list':
        list_jobs()
