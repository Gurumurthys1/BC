/**
 * Blockchain Client for OBLIVION Frontend
 * Handles all smart contract interactions - replaces Supabase
 */
import { ethers, BrowserProvider, Contract, parseEther, formatEther } from 'ethers';
import { getNetworkConfig, getContractAddress } from './config';

// TypeScript declaration for window.ethereum
declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      on: (event: string, callback: (...args: unknown[]) => void) => void;
      removeListener: (event: string, callback: (...args: unknown[]) => void) => void;
    };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// CONTRACT ABI - OblivionManagerSimple (Deployed)
// ═══════════════════════════════════════════════════════════════════════════
export const OBLIVION_ABI = [
  // Job Management
  "function createJob(string _scriptHash, string _dataHash) payable",
  "function cancelJob(uint256 _jobId)",
  "function claimJob(uint256 _jobId)",
  "function submitResult(uint256 _jobId, string _modelHash)",
  
  // Worker Management
  "function registerWorker(string _nodeId) payable",
  "function depositStake() payable",
  
  // View Functions - Simple returns (no complex tuples to avoid stack depth issues)
  "function getJob(uint256 _jobId) view returns (address requester, address worker, uint256 reward, uint256 status, string scriptHash, string dataHash, string modelHash, uint256 createdAt)",
  "function getJobCount() view returns (uint256)",
  "function getWorker(address _addr) view returns (uint256 stake, uint256 completedJobs, uint256 reputation, bool isActive, string nodeId)",
  "function getWorkerCount() view returns (uint256)",
  "function getStats() view returns (uint256 totalJobs, uint256 pendingJobs, uint256 completedJobs, uint256 activeWorkers)",
  "function MIN_STAKE() view returns (uint256)",
  
  // Events
  "event JobCreated(uint256 indexed jobId, address indexed requester, uint256 reward, string scriptHash, string dataHash)",
  "event JobClaimed(uint256 indexed jobId, address indexed worker)",
  "event JobCompleted(uint256 indexed jobId, address indexed worker, string modelHash)",
  "event WorkerRegistered(address indexed worker, string nodeId, uint256 stake)"
];

// ═══════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════

export enum JobType {
  INFERENCE = 0,
  TRAINING = 1
}

export enum JobStatus {
  PENDING = 0,
  PROCESSING = 1,
  COMPLETED = 2,
  CANCELLED = 3,
  SLASHED = 4,
  EXPIRED = 5
}

export const JOB_STATUS_LABELS = {
  [JobStatus.PENDING]: 'Pending',
  [JobStatus.PROCESSING]: 'Processing',
  [JobStatus.COMPLETED]: 'Completed',
  [JobStatus.CANCELLED]: 'Cancelled',
  [JobStatus.SLASHED]: 'Slashed',
  [JobStatus.EXPIRED]: 'Expired'
};

export interface Job {
  id: number;
  requester: string;
  reward: string; // in ETH
  rewardWei: bigint;
  status: JobStatus;
  statusLabel: string;
  scriptHash: string;
  dataHash: string;
  modelHash: string;
  worker: string;
  createdAt: Date;
}

export interface Worker {
  addr: string;
  stake: string;
  stakeWei: bigint;
  reputation: number;
  completedJobs: number;
  isActive: boolean;
  nodeId: string;
}

export interface NetworkStats {
  totalJobs: number;
  pendingJobs: number;
  completedJobs: number;
  activeWorkers: number;
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

function parseJobFromContract(id: number, raw: any): Job {
  // raw is array: [requester, worker, reward, status, scriptHash, dataHash, modelHash, createdAt]
  return {
    id: id,
    requester: raw[0],
    reward: formatEther(raw[2]),
    rewardWei: raw[2],
    status: Number(raw[3]) as JobStatus,
    statusLabel: JOB_STATUS_LABELS[Number(raw[3]) as JobStatus] || 'Unknown',
    scriptHash: raw[4],
    dataHash: raw[5],
    modelHash: raw[6],
    worker: raw[1],
    createdAt: new Date(Number(raw[7]) * 1000)
  };
}

function parseWorkerFromContract(addr: string, raw: any): Worker {
  // raw is array: [stake, completedJobs, reputation, isActive, nodeId]
  return {
    addr: addr,
    stake: formatEther(raw[0]),
    stakeWei: raw[0],
    reputation: Number(raw[2]),
    completedJobs: Number(raw[1]),
    isActive: raw[3],
    nodeId: raw[4]
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// BLOCKCHAIN CLIENT CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class BlockchainClient {
  private provider: BrowserProvider | null = null;
  private contract: Contract | null = null;
  private signer: any = null;
  private address: string | null = null;
  
  constructor() {}
  
  /**
   * Connect to MetaMask and initialize contract
   */
  async connect(): Promise<string> {
    if (typeof window === 'undefined' || !window.ethereum) {
      throw new Error('MetaMask not found');
    }
    
    this.provider = new BrowserProvider(window.ethereum as ethers.Eip1193Provider);
    this.signer = await this.provider.getSigner();
    this.address = await this.signer.getAddress();
    
    const contractAddress = getContractAddress('oblivionManager');
    if (!contractAddress || contractAddress === '0x0000000000000000000000000000000000000000') {
      throw new Error('Contract not deployed on this network');
    }
    
    this.contract = new Contract(contractAddress, OBLIVION_ABI, this.signer);
    
    return this.address!;
  }
  
  /**
   * Get connected address
   */
  getAddress(): string | null {
    return this.address;
  }
  
  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.contract !== null && this.address !== null;
  }
  
  /**
   * Get read-only contract (no wallet needed)
   */
  private async getReadOnlyContract(): Promise<Contract> {
    const config = getNetworkConfig();
    const provider = new ethers.JsonRpcProvider(config.rpcUrl);
    const contractAddress = getContractAddress('oblivionManager');
    return new Contract(contractAddress, OBLIVION_ABI, provider);
  }
  
  // ═══════════════════════════════════════════════════════════════════════════
  // READ FUNCTIONS (No wallet needed)
  // ═══════════════════════════════════════════════════════════════════════════
  
  /**
   * Get network statistics
   */
  async getStats(): Promise<NetworkStats> {
    const contract = await this.getReadOnlyContract();
    const stats = await contract.getStats();
    // stats is array: [totalJobs, pendingJobs, completedJobs, activeWorkers]
    
    return {
      totalJobs: Number(stats[0]),
      pendingJobs: Number(stats[1]),
      completedJobs: Number(stats[2]),
      activeWorkers: Number(stats[3])
    };
  }
  
  /**
   * Get all jobs
   */
  async getAllJobs(): Promise<Job[]> {
    const contract = await this.getReadOnlyContract();
    const count = await contract.getJobCount();
    
    const jobs: Job[] = [];
    for (let i = 0; i < Number(count); i++) {
      try {
        const raw = await contract.getJob(i);
        jobs.push(parseJobFromContract(i, raw));
      } catch (e) {
        console.error(`Error getting job ${i}:`, e);
      }
    }
    
    return jobs;
  }
  
  /**
   * Get a single job
   */
  async getJob(jobId: number): Promise<Job> {
    const contract = await this.getReadOnlyContract();
    const raw = await contract.getJob(jobId);
    return parseJobFromContract(jobId, raw);
  }
  
  /**
   * Get active workers (simplified - returns empty for now)
   */
  async getActiveWorkers(): Promise<Worker[]> {
    // Note: The simplified contract doesn't have batch worker fetching
    // We'd need to track worker addresses separately
    return [];
  }
  
  /**
   * Get worker info
   */
  async getWorker(address: string): Promise<Worker | null> {
    const contract = await this.getReadOnlyContract();
    try {
      const raw = await contract.getWorker(address);
      if (!raw[3]) return null; // Not active
      return parseWorkerFromContract(address, raw);
    } catch {
      return null;
    }
  }
  
  /**
   * Get worker count
   */
  async getWorkerCount(): Promise<number> {
    const contract = await this.getReadOnlyContract();
    const result = await contract.getWorkerCount();
    return Number(result);
  }
  
  // ═══════════════════════════════════════════════════════════════════════════
  // WRITE FUNCTIONS (Wallet required)
  // ═══════════════════════════════════════════════════════════════════════════
  
  /**
   * Create a new training job
   */
  async createJob(
    scriptHash: string,
    dataHash: string,
    rewardEth: string
  ): Promise<{ txHash: string; jobId: number }> {
    if (!this.contract) throw new Error('Not connected');
    
    const tx = await this.contract.createJob(
      scriptHash,
      dataHash,
      { value: parseEther(rewardEth) }
    );
    
    const receipt = await tx.wait();
    
    // Get job ID from event
    const event = receipt.logs.find((log: any) => {
      try {
        const parsed = this.contract!.interface.parseLog(log);
        return parsed?.name === 'JobCreated';
      } catch { return false; }
    });
    
    let jobId = -1;
    if (event) {
      const parsed = this.contract.interface.parseLog(event);
      jobId = Number(parsed?.args?.jobId);
    }
    
    return { txHash: receipt.hash, jobId };
  }
  
  /**
   * Cancel a pending job
   */
  async cancelJob(jobId: number): Promise<string> {
    if (!this.contract) throw new Error('Not connected');
    
    const tx = await this.contract.cancelJob(jobId);
    const receipt = await tx.wait();
    return receipt.hash;
  }
  
  /**
   * Register as a worker
   */
  async registerWorker(nodeId: string, stakeEth: string): Promise<string> {
    if (!this.contract) throw new Error('Not connected');
    
    const tx = await this.contract.registerWorker(nodeId, {
      value: parseEther(stakeEth)
    });
    const receipt = await tx.wait();
    return receipt.hash;
  }
  
  /**
   * Add stake
   */
  async depositStake(amountEth: string): Promise<string> {
    if (!this.contract) throw new Error('Not connected');
    
    const tx = await this.contract.depositStake({
      value: parseEther(amountEth)
    });
    const receipt = await tx.wait();
    return receipt.hash;
  }
  
  /**
   * Claim a job as worker
   */
  async claimJob(jobId: number): Promise<string> {
    if (!this.contract) throw new Error('Not connected');
    
    const tx = await this.contract.claimJob(jobId);
    const receipt = await tx.wait();
    return receipt.hash;
  }
  
  /**
   * Submit result for a job
   */
  async submitResult(jobId: number, modelHash: string): Promise<string> {
    if (!this.contract) throw new Error('Not connected');
    
    const tx = await this.contract.submitResult(jobId, modelHash);
    const receipt = await tx.wait();
    return receipt.hash;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// SINGLETON INSTANCE
// ═══════════════════════════════════════════════════════════════════════════

let clientInstance: BlockchainClient | null = null;

export function getBlockchainClient(): BlockchainClient {
  if (!clientInstance) {
    clientInstance = new BlockchainClient();
  }
  return clientInstance;
}

// ═══════════════════════════════════════════════════════════════════════════
// IPFS HELPERS
// ═══════════════════════════════════════════════════════════════════════════

const PINATA_GATEWAY = process.env.NEXT_PUBLIC_PINATA_GATEWAY || 'https://gateway.pinata.cloud';

export function getIPFSUrl(hash: string): string {
  const cid = hash.replace('ipfs://', '');
  return `${PINATA_GATEWAY}/ipfs/${cid}`;
}

export async function downloadFromIPFS(hash: string): Promise<Blob> {
  const url = getIPFSUrl(hash);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download from IPFS: ${response.status}`);
  }
  return response.blob();
}
