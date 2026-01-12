/**
 * INCO Integration Module for OBLIVION
 * 
 * Handles encrypted bid creation and reveal for confidential job bidding.
 * Uses INCO's FHE (Fully Homomorphic Encryption) to keep bids private.
 * 
 * Network: INCO Rivest Testnet
 * Features: euint256 encrypted bids, ACL-based access control, attested decrypt
 */

import { ethers } from 'ethers';
import { NETWORKS, INCO_ENABLED } from './config';

// INCO Contract ABI (only the functions we need)
const INCO_CONTRACT_ABI = [
  // Write functions
  "function setBid(uint256 shardeumJobId, bytes calldata bidCiphertext) external",
  "function assignWorker(uint256 shardeumJobId, address worker) external",
  "function markJobCompleted(uint256 shardeumJobId) external",
  "function revealBid(uint256 shardeumJobId) external",
  
  // Read functions
  "function hasBid(uint256 shardeumJobId) external view returns (bool)",
  "function getBidHandle(uint256 shardeumJobId) external view returns (uint256)",
  "function canDecrypt(uint256 shardeumJobId, address account) external view returns (bool)",
  "function getJobInfo(uint256 shardeumJobId) external view returns (address creator, address worker, bool isCompleted, bool isRevealed)",
  "function jobCreators(uint256) external view returns (address)",
  "function revealed(uint256) external view returns (bool)",
  
  // Events
  "event BidSet(uint256 indexed shardeumJobId, address indexed creator)",
  "event BidRevealed(uint256 indexed shardeumJobId, uint256 bid)",
  "event JobMarkedComplete(uint256 indexed shardeumJobId, address indexed worker)",
  "event WorkerAssigned(uint256 indexed shardeumJobId, address indexed worker)"
];

// Get INCO network configuration
const INCO_CONFIG = NETWORKS.inco;

/**
 * Check if INCO integration is available
 */
export function isIncoAvailable(): boolean {
  return INCO_ENABLED && !!INCO_CONFIG.contracts.confidentialBids;
}

/**
 * Get INCO provider (read-only)
 */
export function getIncoProvider(): ethers.JsonRpcProvider {
  return new ethers.JsonRpcProvider(INCO_CONFIG.rpcUrl);
}

/**
 * Initialize INCO contract with signer
 */
export function getIncoContract(signer: ethers.Signer): ethers.Contract {
  if (!INCO_CONFIG.contracts.confidentialBids) {
    throw new Error('INCO contract address not configured');
  }
  return new ethers.Contract(
    INCO_CONFIG.contracts.confidentialBids,
    INCO_CONTRACT_ABI,
    signer
  );
}

/**
 * Get read-only INCO contract
 */
export function getIncoContractReadOnly(): ethers.Contract {
  if (!INCO_CONFIG.contracts.confidentialBids) {
    throw new Error('INCO contract address not configured');
  }
  return new ethers.Contract(
    INCO_CONFIG.contracts.confidentialBids,
    INCO_CONTRACT_ABI,
    getIncoProvider()
  );
}

// Type declaration for dynamic import (SDK may not be installed)
interface LightningSDK {
  connect: () => Promise<void>;
  encrypt: (value: bigint, options: { type: string; userAddress: string; contractAddress: string }) => Promise<Uint8Array>;
  decrypt: (handle: bigint, options: { contractAddress: string; userAddress: string }) => Promise<bigint>;
}

/**
 * Encrypt a bid amount using INCO's FHE
 * 
 * @param amount - The bid amount in wei
 * @param userAddress - The user's wallet address
 * @returns Encrypted ciphertext bytes
 */
export async function encryptBid(
  amount: bigint,
  userAddress: string
): Promise<Uint8Array> {
  // Dynamic import of INCO JS SDK
  // Install with: npm install @inco-fhevm/sdk
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const incoSDK = await import('@inco-fhevm/sdk' as any).catch(() => null);
    
    if (!incoSDK?.Lightning) {
      // SDK not installed - return mock encrypted data for development
      console.warn('INCO SDK not installed, using mock encryption');
      const mockCiphertext = new TextEncoder().encode(
        JSON.stringify({ mock: true, amount: amount.toString(), timestamp: Date.now() })
      );
      return mockCiphertext;
    }
    
    const lightning: LightningSDK = new incoSDK.Lightning({
      network: 'rivest', // INCO Rivest testnet
      gatewayUrl: INCO_CONFIG.gatewayUrl
    });
    
    await lightning.connect();
    
    // Encrypt the bid amount as euint256
    const ciphertext = await lightning.encrypt(amount, {
      type: 'euint256',
      userAddress: userAddress,
      contractAddress: INCO_CONFIG.contracts.confidentialBids
    });
    
    return ciphertext;
  } catch (error) {
    console.error('INCO encryption error:', error);
    throw new Error(`Failed to encrypt bid: ${error}`);
  }
}

/**
 * Store encrypted bid on INCO contract
 * 
 * @param signer - Ethers signer (must be connected to INCO network)
 * @param shardeumJobId - Job ID from Shardeum contract
 * @param encryptedBid - Encrypted bid bytes from encryptBid()
 */
export async function storeBid(
  signer: ethers.Signer,
  shardeumJobId: number,
  encryptedBid: Uint8Array
): Promise<ethers.TransactionReceipt> {
  const contract = getIncoContract(signer);
  
  const tx = await contract.setBid(shardeumJobId, encryptedBid);
  const receipt = await tx.wait();
  
  console.log(`[INCO] Bid stored for job ${shardeumJobId}: ${receipt.hash}`);
  return receipt;
}

/**
 * Reveal bid after job completion using attested decrypt
 * 
 * @param shardeumJobId - Job ID from Shardeum contract
 * @returns Revealed bid amount
 */
export async function decryptBid(shardeumJobId: number): Promise<bigint> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const incoSDK = await import('@inco-fhevm/sdk' as any).catch(() => null);
    
    if (!incoSDK?.Lightning) {
      // SDK not installed - return mock value for development
      console.warn('INCO SDK not installed, returning mock decryption');
      return BigInt(0);
    }
    
    const lightning: LightningSDK = new incoSDK.Lightning({
      network: 'rivest',
      gatewayUrl: INCO_CONFIG.gatewayUrl
    });
    
    await lightning.connect();
    
    // Get the bid handle from the contract
    const contract = getIncoContractReadOnly();
    const handle = await contract.getBidHandle(shardeumJobId);
    
    // Attested decrypt - proves the decryption is valid
    const result = await lightning.decrypt(handle, {
      contractAddress: INCO_CONFIG.contracts.confidentialBids,
      userAddress: '' // Will be filled by SDK
    });
    
    return result;
  } catch (error) {
    console.error('INCO decryption error:', error);
    throw new Error(`Failed to decrypt bid: ${error}`);
  }
}

/**
 * Check if a bid exists for a job
 */
export async function checkBidExists(shardeumJobId: number): Promise<boolean> {
  try {
    const contract = getIncoContractReadOnly();
    return await contract.hasBid(shardeumJobId);
  } catch (error) {
    console.error('Error checking bid:', error);
    return false;
  }
}

/**
 * Get job info from INCO contract
 */
export async function getIncoJobInfo(shardeumJobId: number): Promise<{
  creator: string;
  worker: string;
  isCompleted: boolean;
  isRevealed: boolean;
} | null> {
  try {
    const contract = getIncoContractReadOnly();
    const [creator, worker, isCompleted, isRevealed] = await contract.getJobInfo(shardeumJobId);
    return { creator, worker, isCompleted, isRevealed };
  } catch (error) {
    console.error('Error getting INCO job info:', error);
    return null;
  }
}

/**
 * Mark job as completed on INCO (enables reveal)
 */
export async function markJobCompletedOnInco(
  signer: ethers.Signer,
  shardeumJobId: number
): Promise<ethers.TransactionReceipt> {
  const contract = getIncoContract(signer);
  
  const tx = await contract.markJobCompleted(shardeumJobId);
  const receipt = await tx.wait();
  
  console.log(`[INCO] Job ${shardeumJobId} marked complete: ${receipt.hash}`);
  return receipt;
}

/**
 * Trigger bid reveal on INCO contract
 */
export async function triggerBidReveal(
  signer: ethers.Signer,
  shardeumJobId: number
): Promise<ethers.TransactionReceipt> {
  const contract = getIncoContract(signer);
  
  const tx = await contract.revealBid(shardeumJobId);
  const receipt = await tx.wait();
  
  console.log(`[INCO] Bid revealed for job ${shardeumJobId}: ${receipt.hash}`);
  return receipt;
}

// ═══════════════════════════════════════════════════════════════════════════
// HIGH-LEVEL WORKFLOW FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Full workflow: Create job with confidential bid
 * 
 * Steps:
 * 1. Create job on Shardeum (public deposit)
 * 2. Encrypt actual bid with INCO
 * 3. Store encrypted bid on INCO contract
 */
export async function createJobWithConfidentialBid(
  shardeumSigner: ethers.Signer,
  incoSigner: ethers.Signer,
  shardeumContract: ethers.Contract,
  params: {
    jobType: 0 | 1; // 0 = Training, 1 = Inference
    modelHash: string;
    dataHash: string;
    visibleDeposit: bigint;  // Amount deposited on Shardeum (public)
    actualBid: bigint;       // Actual reward (encrypted on INCO)
  }
): Promise<{
  shardeumJobId: number;
  shardeumTxHash: string;
  incoTxHash: string;
}> {
  const userAddress = await shardeumSigner.getAddress();
  
  // Step 1: Create job on Shardeum
  console.log('[Shardeum] Creating job...');
  const shardeumTx = await shardeumContract.createJob(
    params.jobType,
    params.modelHash,
    params.dataHash,
    { value: params.visibleDeposit }
  );
  const shardeumReceipt = await shardeumTx.wait();
  
  // Extract job ID from event
  const iface = shardeumContract.interface;
  const jobCreatedTopic = iface.getEvent('JobCreated')?.topicHash;
  const jobCreatedLog = shardeumReceipt.logs.find(
    (log: any) => log.topics[0] === jobCreatedTopic
  );
  
  if (!jobCreatedLog) {
    throw new Error('JobCreated event not found');
  }
  
  const decodedLog = iface.parseLog({
    topics: jobCreatedLog.topics,
    data: jobCreatedLog.data
  });
  const shardeumJobId = Number(decodedLog?.args[0] || 0);
  
  console.log(`[Shardeum] Job created: ${shardeumJobId}`);
  
  // Step 2: Encrypt bid using INCO
  console.log('[INCO] Encrypting bid...');
  const encryptedBid = await encryptBid(params.actualBid, userAddress);
  
  // Step 3: Store encrypted bid on INCO
  console.log('[INCO] Storing encrypted bid...');
  const incoReceipt = await storeBid(incoSigner, shardeumJobId, encryptedBid);
  
  return {
    shardeumJobId,
    shardeumTxHash: shardeumReceipt.hash,
    incoTxHash: incoReceipt.hash
  };
}

/**
 * Full workflow: Complete job and reveal bid
 */
export async function completeJobAndRevealBid(
  incoSigner: ethers.Signer,
  shardeumJobId: number
): Promise<{
  revealedBid: bigint;
  incoTxHash: string;
}> {
  // Mark job completed on INCO
  console.log('[INCO] Marking job completed...');
  await markJobCompletedOnInco(incoSigner, shardeumJobId);
  
  // Trigger reveal
  console.log('[INCO] Revealing bid...');
  const revealReceipt = await triggerBidReveal(incoSigner, shardeumJobId);
  
  // Get revealed value via attested decrypt
  console.log('[INCO] Decrypting bid...');
  const revealedBid = await decryptBid(shardeumJobId);
  
  return {
    revealedBid,
    incoTxHash: revealReceipt.hash
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPLORER URL HELPERS
// ═══════════════════════════════════════════════════════════════════════════

export function getIncoTxUrl(txHash: string): string {
  return `${INCO_CONFIG.explorerUrl}/tx/${txHash}`;
}

export function getIncoAddressUrl(address: string): string {
  return `${INCO_CONFIG.explorerUrl}/address/${address}`;
}
