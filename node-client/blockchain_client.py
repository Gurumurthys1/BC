"""
Blockchain Client for OBLIVION Workers
Handles all on-chain operations - replaces Supabase for job coordination
Uses OblivionManagerSimple contract
"""
import os
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import IntEnum
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()


class JobStatus(IntEnum):
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    CANCELLED = 3
    SLASHED = 4


@dataclass
class Job:
    """On-chain job data structure"""
    id: int
    requester: str
    worker: str
    reward: int  # in wei
    status: JobStatus
    script_hash: str
    data_hash: str
    model_hash: str
    created_at: int
    
    @property
    def reward_eth(self) -> float:
        return self.reward / 10**18
    
    @property
    def is_pending(self) -> bool:
        return self.status == JobStatus.PENDING
    
    @property
    def is_processing(self) -> bool:
        return self.status == JobStatus.PROCESSING
    
    @property
    def is_completed(self) -> bool:
        return self.status == JobStatus.COMPLETED


@dataclass
class Worker:
    """On-chain worker data structure"""
    addr: str
    stake: int
    completed_jobs: int
    reputation: int
    is_active: bool
    node_id: str
    
    @property
    def stake_eth(self) -> float:
        return self.stake / 10**18


# Contract ABI for OblivionManagerSimple
OBLIVION_ABI = [
    # Worker Registration
    {
        "inputs": [{"name": "_nodeId", "type": "string"}],
        "name": "registerWorker",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "depositStake",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "withdrawStake",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Job Functions
    {
        "inputs": [
            {"name": "_scriptHash", "type": "string"},
            {"name": "_dataHash", "type": "string"}
        ],
        "name": "createJob",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "_jobId", "type": "uint256"}],
        "name": "claimJob",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "_jobId", "type": "uint256"},
            {"name": "_modelHash", "type": "string"}
        ],
        "name": "submitResult",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "_jobId", "type": "uint256"}],
        "name": "cancelJob",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # View Functions
    {
        "inputs": [],
        "name": "getJobCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "_jobId", "type": "uint256"}],
        "name": "getJob",
        "outputs": [
            {"name": "requester", "type": "address"},
            {"name": "worker", "type": "address"},
            {"name": "reward", "type": "uint256"},
            {"name": "status", "type": "uint256"},
            {"name": "scriptHash", "type": "string"},
            {"name": "dataHash", "type": "string"},
            {"name": "modelHash", "type": "string"},
            {"name": "createdAt", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "_addr", "type": "address"}],
        "name": "getWorker",
        "outputs": [
            {"name": "stake", "type": "uint256"},
            {"name": "completedJobs", "type": "uint256"},
            {"name": "reputation", "type": "uint256"},
            {"name": "isActive", "type": "bool"},
            {"name": "nodeId", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getWorkerCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getStats",
        "outputs": [
            {"name": "totalJobs", "type": "uint256"},
            {"name": "pendingJobs", "type": "uint256"},
            {"name": "completedJobs", "type": "uint256"},
            {"name": "activeWorkers", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "MIN_STAKE",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "jobId", "type": "uint256"},
            {"indexed": True, "name": "requester", "type": "address"},
            {"indexed": False, "name": "reward", "type": "uint256"},
            {"indexed": False, "name": "scriptHash", "type": "string"},
            {"indexed": False, "name": "dataHash", "type": "string"}
        ],
        "name": "JobCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "jobId", "type": "uint256"},
            {"indexed": True, "name": "worker", "type": "address"}
        ],
        "name": "JobClaimed",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "jobId", "type": "uint256"},
            {"indexed": True, "name": "worker", "type": "address"},
            {"indexed": False, "name": "modelHash", "type": "string"}
        ],
        "name": "JobCompleted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "worker", "type": "address"},
            {"indexed": False, "name": "nodeId", "type": "string"},
            {"indexed": False, "name": "stake", "type": "uint256"}
        ],
        "name": "WorkerRegistered",
        "type": "event"
    }
]


class BlockchainClient:
    """
    Client for interacting with OblivionManagerSimple smart contract
    Replaces Supabase for all job coordination
    """
    
    def __init__(
        self,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        private_key: Optional[str] = None
    ):
        # Load from env if not provided
        self.rpc_url = rpc_url or os.getenv('RPC_URL') or os.getenv('POLYGON_RPC_URL')
        self.contract_address = contract_address or os.getenv('CONTRACT_ADDRESS') or os.getenv('POLYGON_CONTRACT')
        self.private_key = private_key or os.getenv('PRIVATE_KEY')
        
        if not self.rpc_url:
            raise ValueError("RPC_URL not configured")
        if not self.contract_address:
            raise ValueError("CONTRACT_ADDRESS not configured")
        if not self.private_key:
            raise ValueError("PRIVATE_KEY not configured")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Add POA middleware for sidechains
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        # Set up account
        self.account = Account.from_key(self.private_key)
        self.address = self.account.address
        
        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=OBLIVION_ABI
        )
        
        print(f"✅ Blockchain client initialized")
        print(f"   RPC: {self.rpc_url[:40]}...")
        print(f"   Contract: {self.contract_address}")
        print(f"   Worker: {self.address}")
    
    def _parse_job(self, job_id: int, job_data: tuple) -> Job:
        """Parse raw job tuple from contract into Job dataclass"""
        # job_data: (requester, worker, reward, status, scriptHash, dataHash, modelHash, createdAt)
        return Job(
            id=job_id,
            requester=job_data[0],
            worker=job_data[1],
            reward=job_data[2],
            status=JobStatus(job_data[3]),
            script_hash=job_data[4],
            data_hash=job_data[5],
            model_hash=job_data[6],
            created_at=job_data[7]
        )
    
    def _parse_worker(self, addr: str, worker_data: tuple) -> Worker:
        """Parse raw worker tuple from contract into Worker dataclass"""
        # worker_data: (stake, completedJobs, reputation, isActive, nodeId)
        return Worker(
            addr=addr,
            stake=worker_data[0],
            completed_jobs=worker_data[1],
            reputation=worker_data[2],
            is_active=worker_data[3],
            node_id=worker_data[4]
        )
    
    def _send_transaction(self, func, value: int = 0) -> str:
        """Send a transaction and wait for receipt"""
        try:
            # Build transaction
            tx = func.build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': 500000,
                'gasPrice': int(self.w3.eth.gas_price * 1.2),
                'value': value
            })
            
            # Sign and send
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"📤 Transaction sent: {tx_hash.hex()[:20]}...")
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                print(f"✅ Transaction confirmed in block {receipt['blockNumber']}")
                return tx_hash.hex()
            else:
                print(f"❌ Transaction failed")
                return None
                
        except Exception as e:
            print(f"❌ Transaction error: {e}")
            return None
    
    # ========== Worker Functions ==========
    
    def register_worker(self, node_id: str, stake_wei: int) -> bool:
        """Register as a worker with initial stake"""
        print(f"📝 Registering worker with node_id: {node_id}, stake: {stake_wei / 10**18} ETH")
        
        func = self.contract.functions.registerWorker(node_id)
        result = self._send_transaction(func, value=stake_wei)
        return result is not None
    
    def deposit_stake(self, amount_wei: int) -> bool:
        """Add more stake to worker account"""
        print(f"💰 Depositing {amount_wei / 10**18} ETH stake")
        
        func = self.contract.functions.depositStake()
        result = self._send_transaction(func, value=amount_wei)
        return result is not None
    
    def withdraw_stake(self, amount_wei: int) -> bool:
        """Withdraw stake from worker account"""
        print(f"💸 Withdrawing {amount_wei / 10**18} ETH stake")
        
        func = self.contract.functions.withdrawStake(amount_wei)
        result = self._send_transaction(func)
        return result is not None
    
    def get_worker_info(self, address: Optional[str] = None) -> Optional[Worker]:
        """Get worker information"""
        addr = address or self.address
        try:
            data = self.contract.functions.getWorker(addr).call()
            return self._parse_worker(addr, data)
        except Exception as e:
            print(f"❌ Error getting worker info: {e}")
            return None
    
    def is_registered(self) -> bool:
        """Check if current address is a registered worker"""
        worker = self.get_worker_info()
        return worker is not None and worker.is_active
    
    # ========== Job Functions ==========
    
    def create_job(self, script_hash: str, data_hash: str, reward_wei: int) -> Optional[int]:
        """Create a new job with reward"""
        print(f"📋 Creating job with reward: {reward_wei / 10**18} ETH")
        
        func = self.contract.functions.createJob(script_hash, data_hash)
        result = self._send_transaction(func, value=reward_wei)
        
        if result:
            # Get the job count to determine new job ID
            job_count = self.get_job_count()
            return job_count - 1  # Jobs are 0-indexed
        return None
    
    def claim_job(self, job_id: int) -> bool:
        """Claim a pending job for processing"""
        print(f"🎯 Claiming job #{job_id}")
        
        func = self.contract.functions.claimJob(job_id)
        result = self._send_transaction(func)
        return result is not None
    
    def submit_result(self, job_id: int, model_hash: str) -> bool:
        """Submit training result for a job"""
        print(f"📤 Submitting result for job #{job_id}")
        print(f"   Model hash: {model_hash[:50]}...")
        
        func = self.contract.functions.submitResult(job_id, model_hash)
        result = self._send_transaction(func)
        return result is not None
    
    def cancel_job(self, job_id: int) -> bool:
        """Cancel a pending job (only requester can call)"""
        print(f"❌ Cancelling job #{job_id}")
        
        func = self.contract.functions.cancelJob(job_id)
        result = self._send_transaction(func)
        return result is not None
    
    # ========== View Functions ==========
    
    def get_job(self, job_id: int) -> Optional[Job]:
        """Get job by ID"""
        try:
            data = self.contract.functions.getJob(job_id).call()
            return self._parse_job(job_id, data)
        except Exception as e:
            print(f"❌ Error getting job {job_id}: {e}")
            return None
    
    def get_job_count(self) -> int:
        """Get total number of jobs"""
        try:
            return self.contract.functions.getJobCount().call()
        except Exception as e:
            print(f"❌ Error getting job count: {e}")
            return 0
    
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs from contract"""
        jobs = []
        job_count = self.get_job_count()
        
        for i in range(job_count):
            job = self.get_job(i)
            if job:
                jobs.append(job)
        
        return jobs
    
    def get_pending_jobs(self) -> List[Job]:
        """Get all pending jobs"""
        all_jobs = self.get_all_jobs()
        return [j for j in all_jobs if j.is_pending]
    
    def get_my_jobs(self) -> List[Job]:
        """Get jobs assigned to this worker"""
        all_jobs = self.get_all_jobs()
        return [j for j in all_jobs if j.worker.lower() == self.address.lower()]
    
    def get_stats(self) -> Dict[str, int]:
        """Get network statistics"""
        try:
            data = self.contract.functions.getStats().call()
            return {
                'total_jobs': data[0],
                'pending_jobs': data[1],
                'completed_jobs': data[2],
                'active_workers': data[3]
            }
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {
                'total_jobs': 0,
                'pending_jobs': 0,
                'completed_jobs': 0,
                'active_workers': 0
            }
    
    def get_min_stake(self) -> int:
        """Get minimum stake required"""
        try:
            return self.contract.functions.MIN_STAKE().call()
        except Exception as e:
            print(f"❌ Error getting min stake: {e}")
            return 10**15  # Default 0.001 ETH
    
    def get_balance(self) -> int:
        """Get wallet balance in wei"""
        return self.w3.eth.get_balance(self.address)
    
    def get_balance_eth(self) -> float:
        """Get wallet balance in ETH"""
        return self.get_balance() / 10**18
    
    def get_my_priority(self) -> int:
        """Get current worker's priority (completed jobs count)"""
        worker = self.get_worker_info()
        if worker:
            return worker.completed_jobs
        return 0
    
    def get_active_workers(self) -> List[Worker]:
        """Get list of all active workers"""
        workers = []
        try:
            worker_count = self.contract.functions.getWorkerCount().call()
            # Note: The simple contract doesn't have a workerList getter
            # So we return our own worker info for now
            my_worker = self.get_worker_info()
            if my_worker and my_worker.is_active:
                workers.append(my_worker)
        except Exception as e:
            print(f"❌ Error getting workers: {e}")
        return workers


# ============ CLI Functions ============

def main():
    """Test the blockchain client"""
    print("=" * 60)
    print("   BLOCKCHAIN CLIENT TEST")
    print("=" * 60)
    
    try:
        client = BlockchainClient()
        
        print(f"\n💰 Balance: {client.get_balance_eth():.4f} ETH")
        
        # Get stats
        stats = client.get_stats()
        print(f"\n📊 Network Stats:")
        print(f"   Total Jobs: {stats['total_jobs']}")
        print(f"   Pending: {stats['pending_jobs']}")
        print(f"   Completed: {stats['completed_jobs']}")
        print(f"   Workers: {stats['active_workers']}")
        
        # Check worker status
        worker = client.get_worker_info()
        if worker and worker.is_active:
            print(f"\n👷 Worker Status:")
            print(f"   Node ID: {worker.node_id}")
            print(f"   Stake: {worker.stake_eth:.4f} ETH")
            print(f"   Completed: {worker.completed_jobs}")
            print(f"   Reputation: {worker.reputation}")
        else:
            print(f"\n⚠️ Not registered as worker")
        
        # List pending jobs
        pending = client.get_pending_jobs()
        print(f"\n📋 Pending Jobs: {len(pending)}")
        for job in pending[:5]:
            print(f"   Job #{job.id}: {job.reward_eth:.4f} ETH")
        
        print("\n" + "=" * 60)
        print("✅ Client test complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
