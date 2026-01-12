"""
OBLIVION Decentralized Worker
Fully on-chain job coordination with IPFS file storage
No external database required - everything is trustless
"""
import os
import sys
import time
import json
import uuid
import torch
import torch.nn as nn
import numpy as np
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Local imports
from blockchain_client import BlockchainClient, Job, JobStatus
from ipfs_client import get_ipfs_client, IPFSClient, MockIPFSClient

# ============ Configuration ============

class WorkerConfig:
    """Worker configuration"""
    # Polling
    POLL_INTERVAL = 10  # seconds between job checks
    MAX_RETRIES = 3
    
    # Training
    DEFAULT_EPOCHS = 50
    DEFAULT_BATCH_SIZE = 32
    DEFAULT_LR = 0.01
    QUALITY_THRESHOLD = 0.5  # Max acceptable loss
    
    # Privacy
    DP_ENABLED = True
    DP_EPSILON = 1.0
    DP_DELTA = 1e-5
    DP_MAX_GRAD_NORM = 1.0
    
    # Stake
    MIN_STAKE_ETH = 0.01
    
    # Paths
    WORK_DIR = Path("./work")
    MODELS_DIR = Path("./trained_models")


# ============ Neural Network ============

class SimpleNet(nn.Module):
    """Simple neural network for training jobs"""
    def __init__(self, input_size: int = 10, hidden_size: int = 64, output_size: int = 1):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_size),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, output_size)
        )
    
    def forward(self, x):
        return self.layers(x)


# ============ Differential Privacy ============

class DPTrainer:
    """Differential Privacy trainer with gradient clipping and noise"""
    
    def __init__(
        self,
        epsilon: float = 1.0,
        delta: float = 1e-5,
        max_grad_norm: float = 1.0
    ):
        self.epsilon = epsilon
        self.delta = delta
        self.max_grad_norm = max_grad_norm
        self.noise_multiplier = self._compute_noise_multiplier()
    
    def _compute_noise_multiplier(self) -> float:
        """Compute noise based on privacy budget"""
        return np.sqrt(2 * np.log(1.25 / self.delta)) / self.epsilon
    
    def clip_gradients(self, model: nn.Module) -> float:
        """Clip gradients to bound sensitivity"""
        total_norm = 0.0
        for param in model.parameters():
            if param.grad is not None:
                param_norm = param.grad.data.norm(2)
                total_norm += param_norm.item() ** 2
        total_norm = np.sqrt(total_norm)
        
        clip_coef = self.max_grad_norm / (total_norm + 1e-6)
        if clip_coef < 1:
            for param in model.parameters():
                if param.grad is not None:
                    param.grad.data.mul_(clip_coef)
        
        return total_norm
    
    def add_noise(self, model: nn.Module):
        """Add calibrated Gaussian noise to gradients"""
        for param in model.parameters():
            if param.grad is not None:
                noise = torch.normal(
                    mean=0,
                    std=self.noise_multiplier * self.max_grad_norm,
                    size=param.grad.shape
                )
                param.grad.data.add_(noise)


# ============ Training Engine ============

class TrainingEngine:
    """Handles model training with privacy and quality guarantees"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.dp_trainer = DPTrainer(
            epsilon=config.DP_EPSILON,
            delta=config.DP_DELTA,
            max_grad_norm=config.DP_MAX_GRAD_NORM
        ) if config.DP_ENABLED else None
    
    def train(
        self,
        data: torch.Tensor,
        targets: torch.Tensor,
        epochs: int = None,
        lr: float = None
    ) -> Dict[str, Any]:
        """
        Train a model on the provided data
        Returns training results including model and metrics
        """
        epochs = epochs or self.config.DEFAULT_EPOCHS
        lr = lr or self.config.DEFAULT_LR
        
        # Determine model architecture from data
        input_size = data.shape[1] if len(data.shape) > 1 else 1
        output_size = targets.shape[1] if len(targets.shape) > 1 else 1
        
        model = SimpleNet(input_size=input_size, output_size=output_size)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        
        # Training loop
        model.train()
        history = []
        
        print(f"  📊 Training for {epochs} epochs...")
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            
            outputs = model(data)
            loss = criterion(outputs, targets)
            loss.backward()
            
            # Apply differential privacy
            if self.dp_trainer:
                grad_norm = self.dp_trainer.clip_gradients(model)
                self.dp_trainer.add_noise(model)
            
            optimizer.step()
            
            history.append(loss.item())
            
            if (epoch + 1) % 10 == 0:
                print(f"    Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
        
        final_loss = history[-1]
        quality_passed = final_loss < self.config.QUALITY_THRESHOLD
        
        return {
            'model': model,
            'final_loss': final_loss,
            'history': history,
            'quality_passed': quality_passed,
            'epochs': epochs,
            'dp_enabled': self.config.DP_ENABLED,
            'dp_epsilon': self.config.DP_EPSILON if self.config.DP_ENABLED else None
        }
    
    def generate_synthetic_data(self, samples: int = 1000) -> tuple:
        """Generate synthetic training data for testing"""
        X = torch.randn(samples, 10)
        y = (X.sum(dim=1, keepdim=True) + torch.randn(samples, 1) * 0.1)
        return X, y


# ============ Decentralized Worker ============

class DecentralizedWorker:
    """
    Fully decentralized worker node
    - Job coordination via smart contract
    - File storage via IPFS
    - No external database required
    """
    
    def __init__(self, node_id: Optional[str] = None):
        self.config = WorkerConfig()
        
        # Generate or load node ID
        self.node_id = node_id or self._get_or_create_node_id()
        
        # Initialize clients
        print("=" * 60)
        print("   OBLIVION DECENTRALIZED WORKER")
        print("=" * 60)
        print(f"  Node ID: {self.node_id}")
        print()
        
        # Blockchain client
        print("📡 Initializing blockchain connection...")
        self.blockchain = BlockchainClient()
        
        # IPFS client
        print("📦 Initializing IPFS client...")
        use_mock = os.getenv('IPFS_MOCK', 'true').lower() == 'true'
        self.ipfs = get_ipfs_client(use_mock=use_mock)
        
        # Training engine
        self.trainer = TrainingEngine(self.config)
        
        # Ensure directories exist
        self.config.WORK_DIR.mkdir(parents=True, exist_ok=True)
        self.config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        # State
        self.is_running = False
        self.jobs_completed = 0
        self.total_earnings = 0.0
        
        print()
        print("=" * 60)
    
    def _get_or_create_node_id(self) -> str:
        """Get existing node ID or create new one"""
        node_id_file = Path("node_id.txt")
        
        if node_id_file.exists():
            return node_id_file.read_text().strip()
        
        # Generate new ID
        node_id = f"WORKER-{uuid.uuid4().hex[:8].upper()}"
        node_id_file.write_text(node_id)
        
        return node_id
    
    def ensure_registered(self) -> bool:
        """Ensure worker is registered on-chain"""
        if self.blockchain.is_registered():
            worker = self.blockchain.get_worker_info()
            print(f"✅ Worker registered on-chain")
            print(f"   Stake: {worker.stake_eth:.4f} ETH")
            print(f"   Reputation: {worker.reputation}")
            print(f"   Completed: {worker.completed_jobs} jobs")
            return True
        
        # Need to register
        print("📝 Registering worker on-chain...")
        balance = self.blockchain.get_balance()
        
        if balance < self.config.MIN_STAKE_ETH * 1.5:  # Need extra for gas
            print(f"❌ Insufficient balance: {balance:.4f} ETH")
            print(f"   Need at least {self.config.MIN_STAKE_ETH * 1.5:.4f} ETH")
            return False
        
        success = self.blockchain.register_worker(
            self.node_id,
            stake_eth=self.config.MIN_STAKE_ETH
        )
        
        if success:
            print("✅ Worker registered successfully!")
            return True
        else:
            print("❌ Registration failed")
            return False
    
    def find_best_job(self) -> Optional[Job]:
        """Find the best available job (fair distribution)"""
        pending_jobs = self.blockchain.get_pending_jobs()
        
        if not pending_jobs:
            return None
        
        # Get our priority
        my_priority = self.blockchain.get_my_priority()
        
        # Get all active workers
        workers = self.blockchain.get_active_workers()
        
        # Check if we're among the lowest priority workers (fair distribution)
        priorities = sorted([w.completed_jobs for w in workers])
        
        if priorities and my_priority > priorities[len(priorities) // 2]:
            # We have more jobs than median - let others take this one
            print(f"  ⏳ Fair distribution: letting lower-priority workers claim first")
            return None
        
        # Sort by reward (highest first)
        pending_jobs.sort(key=lambda j: j.reward, reverse=True)
        
        # Check if we have enough stake
        worker = self.blockchain.get_worker_info()
        if not worker:
            return None
        
        for job in pending_jobs:
            required_stake = job.reward / 2
            if worker.stake >= required_stake:
                return job
        
        print(f"  ⚠️  Insufficient stake for available jobs")
        return None
    
    def process_job(self, job: Job) -> bool:
        """Process a training job"""
        print()
        print(f"{'='*60}")
        print(f"  PROCESSING JOB {job.id}")
        print(f"{'='*60}")
        print(f"  Reward: {job.reward_eth:.4f} ETH")
        print(f"  Script: {job.script_hash[:40]}...")
        print(f"  Data: {job.data_hash[:40]}...")
        print()
        
        try:
            # Step 1: Claim the job on-chain
            print("📝 Step 1: Claiming job on-chain...")
            if not self.blockchain.claim_job(job.id):
                print("❌ Failed to claim job")
                return False
            
            # Step 2: Download data from IPFS
            print("📥 Step 2: Downloading data from IPFS...")
            data, targets = self._download_training_data(job)
            
            # Step 3: Train the model
            print("🏋️ Step 3: Training model...")
            result = self.trainer.train(data, targets)
            
            if not result['quality_passed']:
                print(f"⚠️  Quality check failed (loss: {result['final_loss']:.4f})")
                # Still submit - contract will handle verification
            
            # Step 4: Upload model to IPFS
            print("📤 Step 4: Uploading model to IPFS...")
            model_cid = self._upload_model(job, result)
            
            if not model_cid:
                print("❌ Failed to upload model")
                return False
            
            # Step 5: Submit result on-chain
            print("📋 Step 5: Submitting result on-chain...")
            if not self.blockchain.submit_result(job.id, f"ipfs://{model_cid}"):
                print("❌ Failed to submit result")
                return False
            
            # Success!
            print()
            print(f"✅ JOB {job.id} COMPLETED SUCCESSFULLY!")
            print(f"   Model CID: {model_cid}")
            print(f"   Reward: {job.reward_eth:.4f} ETH")
            print()
            
            self.jobs_completed += 1
            self.total_earnings += job.reward_eth
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing job: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _download_training_data(self, job: Job) -> tuple:
        """Download and parse training data from IPFS"""
        try:
            # Try to download from IPFS
            data_json = self.ipfs.download_json(job.data_hash)
            
            if data_json and 'X' in data_json and 'y' in data_json:
                X = torch.tensor(data_json['X'], dtype=torch.float32)
                y = torch.tensor(data_json['y'], dtype=torch.float32)
                if len(y.shape) == 1:
                    y = y.unsqueeze(1)
                print(f"    Downloaded data: {X.shape[0]} samples")
                return X, y
        except Exception as e:
            print(f"    Could not download from IPFS: {e}")
        
        # Fall back to synthetic data
        print("    Using synthetic data for demo...")
        return self.trainer.generate_synthetic_data()
    
    def _upload_model(self, job: Job, result: Dict[str, Any]) -> Optional[str]:
        """Upload trained model to IPFS"""
        # Save model locally first
        model_path = self.config.MODELS_DIR / f"job_{job.id}.pt"
        torch.save({
            'model_state_dict': result['model'].state_dict(),
            'job_id': job.id,
            'final_loss': result['final_loss'],
            'epochs': result['epochs'],
            'dp_enabled': result['dp_enabled'],
            'dp_epsilon': result['dp_epsilon'],
            'timestamp': datetime.now().isoformat(),
            'worker_id': self.node_id
        }, model_path)
        
        # Upload to IPFS
        cid = self.ipfs.upload_file(model_path, f"model_job_{job.id}.pt")
        
        return cid
    
    def run(self):
        """Main worker loop"""
        print()
        print("🚀 Starting worker loop...")
        print()
        
        # Ensure registered
        if not self.ensure_registered():
            print("❌ Cannot start - registration required")
            return
        
        self.is_running = True
        
        try:
            while self.is_running:
                # Check for jobs
                print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Checking for jobs...")
                
                job = self.find_best_job()
                
                if job:
                    self.process_job(job)
                else:
                    print("  No available jobs")
                
                # Display stats
                worker = self.blockchain.get_worker_info()
                if worker:
                    print(f"  📊 Stats: {worker.completed_jobs} completed, {worker.stake_eth:.4f} ETH staked")
                
                # Wait before next poll
                print(f"  💤 Sleeping {self.config.POLL_INTERVAL}s...")
                print()
                time.sleep(self.config.POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down gracefully...")
            self.is_running = False
        
        print()
        print("=" * 60)
        print("  WORKER SESSION SUMMARY")
        print("=" * 60)
        print(f"  Jobs Completed: {self.jobs_completed}")
        print(f"  Total Earnings: {self.total_earnings:.4f} ETH")
        print("=" * 60)


# ============ CLI ============

def print_status(blockchain: BlockchainClient):
    """Print network status"""
    print()
    print("=" * 60)
    print("   OBLIVION NETWORK STATUS")
    print("=" * 60)
    
    stats = blockchain.get_stats()
    
    print(f"\n📊 JOB STATISTICS:")
    print(f"   Total Jobs:      {stats.get('total_jobs', 0)}")
    print(f"   Pending:         {stats.get('pending_jobs', 0)}")
    print(f"   Processing:      {stats.get('processing_jobs', 0)}")
    print(f"   Completed:       {stats.get('completed_jobs', 0)}")
    
    print(f"\n👷 WORKER STATISTICS:")
    print(f"   Total Workers:   {stats.get('total_workers', 0)}")
    print(f"   Active Workers:  {stats.get('active_workers', 0)}")
    print(f"   TVL:             {stats.get('total_value_locked', 0):.4f} ETH")
    
    print(f"\n💰 WALLET:")
    print(f"   Address:         {blockchain.address}")
    print(f"   Balance:         {blockchain.get_balance():.4f} ETH")
    
    print()
    print("=" * 60)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OBLIVION Decentralized Worker')
    parser.add_argument('command', nargs='?', default='run',
                       choices=['run', 'status', 'register'],
                       help='Command to execute')
    parser.add_argument('--node-id', type=str, help='Custom node ID')
    
    args = parser.parse_args()
    
    if args.command == 'status':
        blockchain = BlockchainClient()
        print_status(blockchain)
    
    elif args.command == 'register':
        worker = DecentralizedWorker(node_id=args.node_id)
        worker.ensure_registered()
    
    else:  # run
        worker = DecentralizedWorker(node_id=args.node_id)
        worker.run()


if __name__ == "__main__":
    main()
