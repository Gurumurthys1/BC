/**
 * React Hooks for OBLIVION Blockchain Integration
 * Provides easy access to on-chain data with auto-refresh
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { 
  BlockchainClient, 
  getBlockchainClient, 
  Job, 
  Worker, 
  NetworkStats,
  JobStatus
} from './blockchain';
import { getNetworkConfig, isCorrectNetwork } from './config';
import { ethers } from 'ethers';

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
// WALLET HOOK
// ═══════════════════════════════════════════════════════════════════════════

interface WalletState {
  address: string | null;
  balance: string;
  isConnected: boolean;
  isCorrectNetwork: boolean;
  isConnecting: boolean;
  error: string | null;
}

export function useWallet() {
  const [state, setState] = useState<WalletState>({
    address: null,
    balance: '0',
    isConnected: false,
    isCorrectNetwork: false,
    isConnecting: false,
    error: null
  });
  
  const checkConnection = useCallback(async () => {
    if (typeof window === 'undefined' || !window.ethereum) return;
    
    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const accounts = await provider.listAccounts();
      
      if (accounts.length > 0) {
        const address = accounts[0].address;
        const balance = await provider.getBalance(address);
        const network = await provider.getNetwork();
        
        setState({
          address,
          balance: ethers.formatEther(balance),
          isConnected: true,
          isCorrectNetwork: isCorrectNetwork(Number(network.chainId)),
          isConnecting: false,
          error: null
        });
      }
    } catch (err) {
      console.error('Connection check failed:', err);
    }
  }, []);
  
  const connect = useCallback(async () => {
    if (typeof window === 'undefined' || !window.ethereum) {
      setState(s => ({ ...s, error: 'MetaMask not found' }));
      return;
    }
    
    setState(s => ({ ...s, isConnecting: true, error: null }));
    
    try {
      const accounts = await window.ethereum.request({ 
        method: 'eth_requestAccounts' 
      }) as string[];
      
      const provider = new ethers.BrowserProvider(window.ethereum as ethers.Eip1193Provider);
      const network = await provider.getNetwork();
      const config = getNetworkConfig();
      
      // Switch network if needed
      if (!isCorrectNetwork(Number(network.chainId))) {
        try {
          await window.ethereum.request({
            method: 'wallet_switchEthereumChain',
            params: [{ chainId: config.chainIdHex }]
          });
        } catch (switchError: unknown) {
          if ((switchError as { code?: number })?.code === 4902) {
            await window.ethereum.request({
              method: 'wallet_addEthereumChain',
              params: [{
                chainId: config.chainIdHex,
                chainName: config.chainName,
                nativeCurrency: config.nativeCurrency,
                rpcUrls: [config.rpcUrl],
                blockExplorerUrls: [config.explorerUrl]
              }]
            });
          }
        }
      }
      
      const balance = await provider.getBalance(accounts[0]);
      
      setState({
        address: accounts[0],
        balance: ethers.formatEther(balance),
        isConnected: true,
        isCorrectNetwork: true,
        isConnecting: false,
        error: null
      });
      
      // Connect blockchain client
      const client = getBlockchainClient();
      await client.connect();
      
    } catch (err: unknown) {
      setState(s => ({
        ...s, 
        isConnecting: false, 
        error: (err as Error).message || 'Connection failed' 
      }));
    }
  }, []);
  
  const disconnect = useCallback(() => {
    setState({
      address: null,
      balance: '0',
      isConnected: false,
      isCorrectNetwork: false,
      isConnecting: false,
      error: null
    });
  }, []);
  
  // Check connection on mount
  useEffect(() => {
    checkConnection();
    
    // Listen for account changes
    if (window.ethereum) {
      window.ethereum.on('accountsChanged', checkConnection);
      window.ethereum.on('chainChanged', checkConnection);
    }
    
    return () => {
      if (window.ethereum) {
        window.ethereum.removeListener('accountsChanged', checkConnection);
        window.ethereum.removeListener('chainChanged', checkConnection);
      }
    };
  }, [checkConnection]);
  
  return {
    ...state,
    connect,
    disconnect,
    refresh: checkConnection
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// JOBS HOOK
// ═══════════════════════════════════════════════════════════════════════════

interface JobsState {
  jobs: Job[];
  isLoading: boolean;
  error: string | null;
}

export function useJobs(refreshInterval: number = 10000) {
  const [state, setState] = useState<JobsState>({
    jobs: [],
    isLoading: true,
    error: null
  });
  
  const fetchJobs = useCallback(async () => {
    try {
      const client = getBlockchainClient();
      const jobs = await client.getAllJobs();
      
      // Sort by creation date (newest first)
      jobs.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
      
      setState({
        jobs,
        isLoading: false,
        error: null
      });
    } catch (err: any) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: err.message || 'Failed to fetch jobs'
      }));
    }
  }, []);
  
  useEffect(() => {
    fetchJobs();
    
    const interval = setInterval(fetchJobs, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchJobs, refreshInterval]);
  
  return {
    ...state,
    refresh: fetchJobs,
    pendingJobs: state.jobs.filter(j => j.status === JobStatus.PENDING),
    processingJobs: state.jobs.filter(j => j.status === JobStatus.PROCESSING),
    completedJobs: state.jobs.filter(j => j.status === JobStatus.COMPLETED)
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// WORKERS HOOK
// ═══════════════════════════════════════════════════════════════════════════

interface WorkersState {
  workers: Worker[];
  isLoading: boolean;
  error: string | null;
}

export function useWorkers(refreshInterval: number = 15000) {
  const [state, setState] = useState<WorkersState>({
    workers: [],
    isLoading: true,
    error: null
  });
  
  const fetchWorkers = useCallback(async () => {
    try {
      const client = getBlockchainClient();
      const workers = await client.getActiveWorkers();
      
      setState({
        workers,
        isLoading: false,
        error: null
      });
    } catch (err: any) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: err.message || 'Failed to fetch workers'
      }));
    }
  }, []);
  
  useEffect(() => {
    fetchWorkers();
    
    const interval = setInterval(fetchWorkers, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchWorkers, refreshInterval]);
  
  return {
    ...state,
    refresh: fetchWorkers,
    totalStake: state.workers.reduce((sum, w) => sum + parseFloat(w.stake), 0),
    totalCompleted: state.workers.reduce((sum, w) => sum + w.completedJobs, 0)
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// NETWORK STATS HOOK
// ═══════════════════════════════════════════════════════════════════════════

interface StatsState {
  stats: NetworkStats | null;
  isLoading: boolean;
  error: string | null;
}

export function useNetworkStats(refreshInterval: number = 10000) {
  const [state, setState] = useState<StatsState>({
    stats: null,
    isLoading: true,
    error: null
  });
  
  const fetchStats = useCallback(async () => {
    try {
      const client = getBlockchainClient();
      const stats = await client.getStats();
      
      setState({
        stats,
        isLoading: false,
        error: null
      });
    } catch (err: any) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: err.message || 'Failed to fetch stats'
      }));
    }
  }, []);
  
  useEffect(() => {
    fetchStats();
    
    const interval = setInterval(fetchStats, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchStats, refreshInterval]);
  
  return {
    ...state,
    refresh: fetchStats
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// JOB CREATION HOOK
// ═══════════════════════════════════════════════════════════════════════════

export function useCreateJob() {
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const createJob = useCallback(async (
    scriptHash: string,
    dataHash: string,
    rewardEth: string
  ): Promise<{ txHash: string; jobId: number } | null> => {
    setIsCreating(true);
    setError(null);
    
    try {
      const client = getBlockchainClient();
      
      if (!client.isConnected()) {
        await client.connect();
      }
      
      const result = await client.createJob(scriptHash, dataHash, rewardEth);
      
      setIsCreating(false);
      return result;
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to create job');
      setIsCreating(false);
      return null;
    }
  }, []);
  
  return {
    createJob,
    isCreating,
    error,
    clearError: () => setError(null)
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// COMBINED DATA HOOK
// ═══════════════════════════════════════════════════════════════════════════

export function useOblivionData() {
  const wallet = useWallet();
  const jobs = useJobs();
  const workers = useWorkers();
  const stats = useNetworkStats();
  
  const refreshAll = useCallback(() => {
    wallet.refresh();
    jobs.refresh();
    workers.refresh();
    stats.refresh();
  }, [wallet, jobs, workers, stats]);
  
  return {
    wallet,
    jobs,
    workers,
    stats,
    refreshAll,
    isLoading: jobs.isLoading || workers.isLoading || stats.isLoading
  };
}
