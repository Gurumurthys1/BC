'use client';

import React, { useState, useEffect } from 'react';
import {
  Activity, Plus, Server, Cpu, Clock, CheckCircle2,
  AlertCircle, ArrowRight, Wallet, LayoutDashboard,
  Search, ExternalLink, Shield, Database, Brain, RefreshCcw, Power,
  Download, Zap, Users, TrendingUp, Globe, FileCode, Play, Box, Menu, X
} from 'lucide-react';
import { ethers } from 'ethers';
import { supabase } from './lib/supabase';
import contractAbi from './lib/abi.json';
import NetworkVisualization from './components/NetworkVisualization';
import { JobCard } from './components/JobCard';
import WorkerStatus from './components/WorkerStatus';
import WorkerDistribution from './components/WorkerDistribution';
import { BrowserWorker } from './lib/browserWorker';

const CONTRACT_ADDRESS = "0x2681849aB3d8E470Dedc08b1a4CED92493886501";
const RPC_URL = "https://polygon-amoy-bor-rpc.publicnode.com";

interface Job {
  id: string | number;
  job_type: 'training' | 'inference';
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'slashed';
  reward: string;
  created_at: string;
  data_hash: string;
  model_hash: string;
  requester_address?: string;
  on_chain_id?: number | null;
  result_url?: string;
  inference_result?: string;
  input_data?: string;
  model_url?: string;
}

interface Node {
  id: number;
  hardware_id: string;
  status: 'active' | 'offline';
  wallet_address?: string;
  last_seen: string;
}

export default function Home() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [modelHash, setModelHash] = useState('ipfs://QmGlobalModel...');
  const [dataHash, setDataHash] = useState('ipfs://QmDataShard...');
  const [pythonCode, setPythonCode] = useState(`import torch\nimport torch.nn as nn\nimport torch.optim as optim\n\ndef train(dataset_url):\n    # Custom Model\n    model = nn.Sequential(\n        nn.Linear(10, 32),\n        nn.ReLU(),\n        nn.Linear(32, 1)\n    )\n    \n    # Mock data load\n    data = torch.randn(16, 10)\n    target = torch.randn(16, 1)\n    \n    optimizer = optim.SGD(model.parameters(), lr=0.1)\n    optimizer.zero_grad()\n    loss = nn.MSELoss()(model(data), target)\n    loss.backward()\n    \n    return [p.grad for p in model.parameters()], loss.item(), model.state_dict()`);
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [reward, setReward] = useState('0.1');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isAdvanced, setIsAdvanced] = useState(false);
  const [account, setAccount] = useState<string | null>(null);
  const [balance, setBalance] = useState<string>('0.00');
  const [networkOk, setNetworkOk] = useState(false);
  const [testingJob, setTestingJob] = useState<Job | null>(null);
  const [inferenceInput, setInferenceInput] = useState('{"data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}');
  const [nodes, setNodes] = useState<Node[]>([]);
  const [browserWorker, setBrowserWorker] = useState<BrowserWorker | null>(null);
  const [workerStatus, setWorkerStatus] = useState<'stopped' | 'running' | 'processing'>('stopped');
  const [jobsCompleted, setJobsCompleted] = useState(0);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [jobFilter, setJobFilter] = useState<'all' | 'mine'>('all');

  // Auto-start browser worker when wallet connects
  useEffect(() => {
    if (account && !browserWorker) {
      const worker = new BrowserWorker({
        walletAddress: account,
        maxConcurrentJobs: 1,
        enableGPU: false
      });

      worker.setCallbacks(
        (status: string) => {
          if (status.startsWith('processing')) {
            setWorkerStatus('processing');
          } else if (status === 'running' || status === 'idle') {
            setWorkerStatus('running');
          } else {
            setWorkerStatus('stopped');
          }
        },
        (jobId: string, result) => {
          if (result.success) {
            setJobsCompleted(prev => prev + 1);
          }
          fetchJobs(); // Refresh job list
        }
      );

      worker.start();
      setBrowserWorker(worker);
    }

    return () => {
      if (browserWorker) {
        browserWorker.stop();
      }
    };
  }, [account]);

  useEffect(() => {
    fetchJobs();
    fetchNodes();
    checkConnection();

    const channel = supabase
      .channel('realtime-mesh')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'jobs' }, () => {
        fetchJobs();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'nodes' }, () => {
        fetchNodes();
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, []);

  async function fetchNodes() {
    const { data } = await supabase.from('nodes').select('*');
    if (data) setNodes(data);
  }

  async function checkConnection() {
    if (typeof window !== 'undefined' && (window as any).ethereum) {
      const provider = new ethers.BrowserProvider((window as any).ethereum);
      const accounts = await provider.listAccounts();
      if (accounts.length > 0) {
        setAccount(accounts[0].address);
        const bal = await provider.getBalance(accounts[0].address);
        setBalance(ethers.formatEther(bal));
        const network = await provider.getNetwork();
        setNetworkOk(Number(network.chainId) === 80002);
      }
    }
  }

  async function connectWallet() {
    if (typeof window === 'undefined') return;
    const ethereum = (window as any).ethereum;
    if (!ethereum) {
      alert("MetaMask not found.");
      return;
    }
    try {
      const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
      const provider = new ethers.BrowserProvider(ethereum);
      const network = await provider.getNetwork();

      if (Number(network.chainId) !== 80002) {
        try {
          await ethereum.request({
            method: 'wallet_switchEthereumChain',
            params: [{ chainId: '0x13882' }],
          });
        } catch (switchError: any) {
          if (switchError.code === 4902) {
            await ethereum.request({
              method: 'wallet_addEthereumChain',
              params: [{
                chainId: '0x13882',
                chainName: 'Polygon Amoy Testnet',
                nativeCurrency: { name: 'MATIC', symbol: 'MATIC', decimals: 18 },
                rpcUrls: ['https://rpc-amoy.polygon.technology'],
                blockExplorerUrls: ['https://amoy.polygonscan.com']
              }],
            });
          }
        }
      }

      setAccount(accounts[0]);
      const bal = await provider.getBalance(accounts[0]);
      setBalance(ethers.formatEther(bal));
      setNetworkOk(true);
    } catch (err: any) {
      alert("Connect failed: " + err.message);
    }
  }

  async function fetchJobs() {
    try {
      const { data, error } = await supabase
        .from('jobs')
        .select('*')
        .order('created_at', { ascending: false });
      if (error) throw error;
      setJobs(data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function createOnChainJob(e: React.FormEvent) {
    e.preventDefault();
    if (!account) {
      await connectWallet();
      return;
    }
    if (!networkOk) {
      alert("Please switch to Polygon Amoy Network.");
      return;
    }
    setIsSubmitting(true);
    try {
      let finalScriptUrl = modelHash;
      let finalDataUrl = dataHash;

      if (isAdvanced) {
        const scriptBlob = new Blob([pythonCode], { type: 'text/plain' });
        const scriptPath = `scripts/script_${Date.now()}.py`;
        await supabase.storage.from('training-scripts').upload(scriptPath, scriptBlob);
        const { data: { publicUrl: scriptUrl } } = supabase.storage.from('training-scripts').getPublicUrl(scriptPath);
        finalScriptUrl = scriptUrl;

        if (datasetFile) {
          const dataPath = `datasets/data_${Date.now()}_${datasetFile.name}`;
          await supabase.storage.from('datasets').upload(dataPath, datasetFile);
          const { data: { publicUrl: dataUrl } } = supabase.storage.from('datasets').getPublicUrl(dataPath);
          finalDataUrl = dataUrl;
        }
      }

      const provider = new ethers.BrowserProvider((window as any).ethereum);
      const signer = await provider.getSigner();
      const signerAddress = await signer.getAddress();
      
      // Check balance first
      const balance = await provider.getBalance(signerAddress);
      const rewardWei = ethers.parseEther(reward);
      console.log('Wallet balance:', ethers.formatEther(balance), 'MATIC');
      console.log('Reward amount:', reward, 'MATIC');
      
      if (balance < rewardWei) {
        alert(`Insufficient balance. You have ${ethers.formatEther(balance)} MATIC but need at least ${reward} MATIC plus gas fees.`);
        setIsSubmitting(false);
        return;
      }
      
      const contract = new ethers.Contract(CONTRACT_ADDRESS, contractAbi, signer);

      console.log('Creating job with:', { 
        jobType: 1, // 1 = Training
        scriptUrl: finalScriptUrl, 
        dataUrl: finalDataUrl, 
        reward: ethers.formatEther(rewardWei) + ' MATIC'
      });
      
      // Estimate gas first to catch errors before sending
      let gasEstimate;
      try {
        gasEstimate = await contract.createJob.estimateGas(1, finalScriptUrl, finalDataUrl, { value: rewardWei });
        console.log('Gas estimate:', gasEstimate.toString());
      } catch (estimateErr: any) {
        console.error('Gas estimation failed:', estimateErr);
        // Try to get more info about why it failed
        if (estimateErr.reason) {
          throw new Error(`Contract will revert: ${estimateErr.reason}`);
        }
        throw estimateErr;
      }
      
      // Get gas price using legacy method (more compatible with various RPCs)
      const gasPrice = await provider.send("eth_gasPrice", []);
      console.log('Gas price:', parseInt(gasPrice, 16), 'wei');
      
      // Use 1 for Training job type (enum value)
      // Use legacy transaction with explicit gasPrice (more compatible)
      const tx = await contract.createJob(1, finalScriptUrl, finalDataUrl, { 
        value: rewardWei,
        gasLimit: gasEstimate * 120n / 100n,
        gasPrice: BigInt(gasPrice) // Use legacy gasPrice instead of EIP-1559
      });
      console.log('Transaction sent:', tx.hash);
      
      const receipt = await tx.wait();
      console.log('Transaction confirmed:', receipt);

      let onChainId = null;
      for (const log of receipt.logs) {
        try {
          const parsed = contract.interface.parseLog(log);
          if (parsed && parsed.name === 'JobCreated') {
            onChainId = Number(parsed.args.jobId);
            break;
          }
        } catch (e) { }
      }

      await supabase.from('jobs').insert([{
        job_type: 'training',
        status: 'pending',
        requester_address: account,
        reward: reward,
        model_hash: finalScriptUrl,
        data_hash: finalDataUrl,
        on_chain_id: onChainId
      }]);

      alert("Job Created!");
      fetchJobs();
    } catch (err: any) {
      console.error('Job creation error:', err);
      console.error('Error details:', JSON.stringify(err, Object.getOwnPropertyNames(err), 2));
      
      // Provide more helpful error messages
      let errorMsg = err.message || 'Unknown error';
      
      // Try to extract revert reason
      if (err.data) {
        console.error('Revert data:', err.data);
      }
      if (err.reason) {
        errorMsg = `Contract reverted: ${err.reason}`;
      } else if (err.code === 'ACTION_REJECTED') {
        errorMsg = 'Transaction was rejected by user';
      } else if (err.code === -32603 || errorMsg.includes('Internal JSON-RPC')) {
        // Try to parse the inner error
        const match = errorMsg.match(/reason="([^"]+)"/);
        if (match) {
          errorMsg = `Contract reverted: ${match[1]}`;
        } else {
          errorMsg = 'Contract reverted. Possible causes:\n1) Insufficient MATIC (need reward + gas)\n2) Invalid input data\n3) Network congestion';
        }
      } else if (err.code === 'INSUFFICIENT_FUNDS') {
        errorMsg = 'Insufficient funds - you need MATIC for gas fees and the job reward';
      }
      alert("Error: " + errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function cancelOnChainJob(jobId: string, onChainId: number) {
    if (!account) return;
    try {
      const provider = new ethers.BrowserProvider((window as any).ethereum);
      const signer = await provider.getSigner();
      const contract = new ethers.Contract(CONTRACT_ADDRESS, contractAbi, signer);
      const tx = await contract.cancelJob(onChainId);
      await tx.wait();
      await supabase.from('jobs').update({ status: 'failed' }).eq('id', jobId);
      fetchJobs();
    } catch (err: any) {
      alert("Cancel failed: " + err.message);
    }
  }

  async function runInference() {
    if (!testingJob || !account) return;
    setIsSubmitting(true);
    try {
      // Basic JSON validation
      try {
        JSON.parse(inferenceInput);
      } catch (e) {
        alert("Invalid JSON sequence data.");
        setIsSubmitting(false);
        return;
      }

      await supabase.from('jobs').insert([{
        job_type: 'inference',
        status: 'pending',
        requester_address: account,
        reward: '0',
        model_url: testingJob.result_url || testingJob.model_hash,
        input_data: inferenceInput
      }]);
      alert("Inference Job Submitted!");
      setTestingJob(null);
      fetchJobs();
    } catch (err: any) {
      alert("Inference failed: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleWork(job: Job) {
    if (!account) {
      alert("Please connect your wallet first.");
      return;
    }
    if (!networkOk) {
      alert("Please switch to Polygon Amoy Network.");
      return;
    }
    
    // Jobs are now automatically processed by the BrowserWorker
    // This function is kept for manual triggering if needed
    try {
      setIsSubmitting(true);
      
      // Mark job as processing
      await supabase.from('jobs').update({
        status: 'processing',
        provider_address: account,
        claimed_at: new Date().toISOString()
      }).eq('id', job.id);

      // Simulate browser-based computation
      await new Promise(r => setTimeout(r, 2000));

      // For training jobs, create model output
      if (job.job_type === 'training') {
        const modelData = {
          architecture: 'BrowserMLP',
          inputSize: 10,
          hiddenSize: 32,
          outputSize: 1,
          weights: {
            layer1: Array.from({ length: 320 }, () => Math.random() * 0.1),
            layer2: Array.from({ length: 32 }, () => Math.random() * 0.1)
          },
          trainedAt: new Date().toISOString(),
          trainedBy: account
        };

        const modelBlob = new Blob([JSON.stringify(modelData)], { type: 'application/json' });
        const modelPath = `models/model_${job.id}_${Date.now()}.json`;
        
        await supabase.storage.from('trained-models').upload(modelPath, modelBlob);
        const { data: { publicUrl } } = supabase.storage.from('trained-models').getPublicUrl(modelPath);

        await supabase.from('jobs').update({
          status: 'completed',
          result_url: publicUrl,
          completed_at: new Date().toISOString()
        }).eq('id', job.id);
      } else {
        // Inference job
        const result = {
          prediction: Math.random(),
          confidence: Math.random() * 0.5 + 0.5,
          processedBy: 'browser-worker'
        };

        await supabase.from('jobs').update({
          status: 'completed',
          inference_result: JSON.stringify(result),
          completed_at: new Date().toISOString()
        }).eq('id', job.id);
      }

      alert("Job Completed!");
      fetchJobs();
    } catch (err: any) {
      alert("Work failed: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  // Filter jobs based on selection
  const filteredJobs = jobFilter === 'mine' 
    ? jobs.filter(j => j.requester_address?.toLowerCase() === account?.toLowerCase())
    : jobs;

  return (
    <div className="flex min-h-screen bg-[#050505] text-zinc-400 font-sans selection:bg-emerald-500/30 overflow-hidden">
      {/* Top Status Bar - Always Visible */}
      <div className="fixed top-0 left-0 w-full h-14 z-[200] bg-black/80 backdrop-blur-xl border-b border-white/5 flex items-center justify-between px-4 lg:px-8">
        <div className="flex items-center gap-4">
          {/* Mobile Menu Toggle */}
          <button 
            onClick={() => setShowMobileMenu(!showMobileMenu)}
            className="xl:hidden p-2 rounded-xl bg-white/5 text-white"
          >
            {showMobileMenu ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          
          {/* Logo */}
          <div className="flex items-center gap-2">
            <Brain className="w-6 h-6 text-emerald-500" />
            <span className="font-black text-white text-lg tracking-tight hidden sm:block">OBLIVION</span>
          </div>

          {/* Quick Stats */}
          <div className="hidden md:flex items-center gap-4 ml-6">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
              <Users className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] font-bold text-emerald-400">{nodes.filter(n => new Date().getTime() - new Date(n.last_seen).getTime() < 3600000).length} Nodes</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
              <Activity className="w-3 h-3 text-cyan-400" />
              <span className="text-[10px] font-bold text-cyan-400">{jobs.filter(j => j.status === 'processing').length} Active</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 rounded-lg border border-amber-500/20">
              <CheckCircle2 className="w-3 h-3 text-amber-400" />
              <span className="text-[10px] font-bold text-amber-400">{jobs.filter(j => j.status === 'completed').length} Done</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Worker Status Indicator */}
          {account && (
            <div className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
              workerStatus === 'processing' 
                ? 'bg-cyan-500/10 border-cyan-500/20' 
                : workerStatus === 'running'
                ? 'bg-emerald-500/10 border-emerald-500/20'
                : 'bg-zinc-500/10 border-zinc-500/20'
            }`}>
              <Cpu className={`w-3 h-3 ${
                workerStatus === 'processing' ? 'text-cyan-400 animate-pulse' : 
                workerStatus === 'running' ? 'text-emerald-400' : 'text-zinc-500'
              }`} />
              <span className={`text-[10px] font-bold ${
                workerStatus === 'processing' ? 'text-cyan-400' : 
                workerStatus === 'running' ? 'text-emerald-400' : 'text-zinc-500'
              }`}>
                {workerStatus === 'processing' ? 'Computing' : workerStatus === 'running' ? 'Worker Active' : 'Offline'}
              </span>
              {jobsCompleted > 0 && (
                <span className="text-[9px] bg-emerald-500 text-black px-1.5 rounded font-bold">{jobsCompleted}</span>
              )}
            </div>
          )}

          {/* Connect Wallet Button */}
          <button
            onClick={connectWallet}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs transition-all ${
              account
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-emerald-500 text-black hover:bg-emerald-400'
            }`}
          >
            <Wallet className="w-4 h-4" />
            {account ? `${account.slice(0, 6)}...${account.slice(-4)}` : 'Connect'}
          </button>
        </div>
      </div>

      {/* Mobile Menu Overlay */}
      {showMobileMenu && (
        <div className="fixed inset-0 z-[150] bg-black/90 backdrop-blur-xl xl:hidden pt-14">
          <div className="p-6 space-y-4">
            {[
              { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard', desc: 'Submit & track jobs' },
              { id: 'nodes', icon: Server, label: 'Network', desc: 'View compute nodes' }
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => { setActiveTab(item.id); setShowMobileMenu(false); }}
                className={`w-full flex items-center gap-4 p-4 rounded-2xl transition-all ${
                  activeTab === item.id
                    ? 'bg-emerald-500/10 border border-emerald-500/20'
                    : 'bg-white/5 border border-white/5'
                }`}
              >
                <item.icon className={`w-6 h-6 ${activeTab === item.id ? 'text-emerald-400' : 'text-zinc-400'}`} />
                <div className="text-left">
                  <p className={`font-bold ${activeTab === item.id ? 'text-white' : 'text-zinc-300'}`}>{item.label}</p>
                  <p className="text-xs text-zinc-500">{item.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Sidebar - Precision Glassmorphism */}
      <aside className="w-72 border-r border-white/5 flex flex-col p-6 gap-6 bg-black/60 backdrop-blur-3xl z-20 fixed left-0 top-0 h-screen hidden xl:flex pt-20">
        {/* Logo */}
        <div className="flex items-center gap-3 px-2">
          <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center">
            <Brain className="text-black w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-xl text-white">OBLIVION</span>
            <span className="text-[9px] text-emerald-500 uppercase tracking-wider block">Decentralized ML</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-1">
          {[
            { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard', desc: 'Jobs & Training' },
            { id: 'nodes', icon: Globe, label: 'Network', desc: 'Active Nodes' }
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === item.id
                ? 'bg-emerald-500/10 text-white border border-emerald-500/20'
                : 'hover:bg-white/5 text-zinc-400 border border-transparent'
                }`}
            >
              <item.icon className={`w-5 h-5 ${activeTab === item.id ? 'text-emerald-400' : ''}`} />
              <div className="text-left">
                <span className="font-medium text-sm block">{item.label}</span>
                <span className="text-[10px] text-zinc-500">{item.desc}</span>
              </div>
            </button>
          ))}
        </nav>

        {/* Quick Stats */}
        <div className="p-4 bg-white/[0.02] rounded-xl border border-white/5">
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">Network Stats</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-lg font-bold text-white">{nodes.filter(n => new Date().getTime() - new Date(n.last_seen).getTime() < 3600000).length}</p>
              <p className="text-[10px] text-zinc-500">Online Nodes</p>
            </div>
            <div>
              <p className="text-lg font-bold text-emerald-400">{jobs.length}</p>
              <p className="text-[10px] text-zinc-500">Total Jobs</p>
            </div>
          </div>
        </div>

        <div className="mt-auto space-y-4">
          {/* Browser Worker Status */}
          {account && (
            <div className={`p-4 rounded-xl border transition-all ${
              workerStatus === 'running' 
                ? 'bg-emerald-500/5 border-emerald-500/20' 
                : workerStatus === 'processing'
                ? 'bg-cyan-500/5 border-cyan-500/20'
                : 'bg-zinc-900/50 border-white/5'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Cpu className={`w-4 h-4 ${
                    workerStatus === 'running' ? 'text-emerald-400' : 
                    workerStatus === 'processing' ? 'text-cyan-400' : 'text-zinc-600'
                  }`} />
                  <span className="text-xs font-bold text-white">Worker</span>
                </div>
                <div className={`w-2 h-2 rounded-full ${
                  workerStatus === 'running' ? 'bg-emerald-500 animate-pulse' : 
                  workerStatus === 'processing' ? 'bg-cyan-500 animate-ping' : 'bg-zinc-600'
                }`} />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">
                  {workerStatus === 'processing' ? 'Computing...' : workerStatus === 'running' ? 'Active' : 'Offline'}
                </span>
                <span className="text-emerald-400 font-mono">{jobsCompleted} done</span>
              </div>
            </div>
          )}

          {/* Help Card */}
          <div className="p-4 bg-white/[0.02] rounded-xl border border-white/5">
            <p className="text-xs font-bold text-white mb-2">How it works</p>
            <ul className="text-[10px] text-zinc-500 space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="text-emerald-500">1.</span> Submit a training job
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500">2.</span> Browser workers process it
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500">3.</span> Download your model
              </li>
            </ul>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 pt-14 xl:ml-72">
        {/* Page Header - Simplified */}
        <header className="px-6 lg:px-12 py-6 border-b border-white/5 bg-black/20 backdrop-blur-md">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl lg:text-3xl font-black text-white tracking-tighter uppercase">
                {activeTab === 'dashboard' ? '🚀 Dashboard' : '🌐 Network'}
              </h1>
              <p className="text-xs text-zinc-500 mt-1">
                {activeTab === 'dashboard' ? 'Submit jobs, track progress, download models' : 
                 'View active compute nodes in the network'}
              </p>
            </div>
            
            {/* Quick Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  activeTab === 'dashboard' ? 'bg-emerald-500 text-black' : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                }`}
              >
                <Plus className="w-4 h-4" /> New Job
              </button>
              <button
                onClick={() => setActiveTab('nodes')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  activeTab === 'nodes' ? 'bg-cyan-500 text-black' : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                }`}
              >
                <Globe className="w-4 h-4" /> Network
              </button>
            </div>
          </div>
        </header>

        {/* Dynamic Content Scroll */}
        <div className="flex-1 overflow-y-auto p-4 lg:p-8 custom-scrollbar">
          {activeTab === 'dashboard' && (
            <div className="max-w-[1600px] mx-auto space-y-8">
              
              {/* Feature Cards - Always Visible */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-4 lg:p-6 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 rounded-2xl border border-emerald-500/20 group hover:border-emerald-500/40 transition-all">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-emerald-500/20 rounded-xl">
                      <Brain className="w-5 h-5 text-emerald-400" />
                    </div>
                    <span className="text-xs font-bold text-emerald-400 uppercase">Train Models</span>
                  </div>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">Submit training jobs with your data & code. Browser workers process them.</p>
                </div>
                <div className="p-4 lg:p-6 bg-gradient-to-br from-cyan-500/10 to-cyan-500/5 rounded-2xl border border-cyan-500/20 group hover:border-cyan-500/40 transition-all">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-cyan-500/20 rounded-xl">
                      <Zap className="w-5 h-5 text-cyan-400" />
                    </div>
                    <span className="text-xs font-bold text-cyan-400 uppercase">Inference</span>
                  </div>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">Run predictions on trained models. Fast & verifiable results.</p>
                </div>
                <div className="p-4 lg:p-6 bg-gradient-to-br from-amber-500/10 to-amber-500/5 rounded-2xl border border-amber-500/20 group hover:border-amber-500/40 transition-all">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-amber-500/20 rounded-xl">
                      <Download className="w-5 h-5 text-amber-400" />
                    </div>
                    <span className="text-xs font-bold text-amber-400 uppercase">Download</span>
                  </div>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">Export models in .pt, .onnx, .pkl, .h5 formats for your projects.</p>
                </div>
                <div className="p-4 lg:p-6 bg-gradient-to-br from-purple-500/10 to-purple-500/5 rounded-2xl border border-purple-500/20 group hover:border-purple-500/40 transition-all">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-500/20 rounded-xl">
                      <Users className="w-5 h-5 text-purple-400" />
                    </div>
                    <span className="text-xs font-bold text-purple-400 uppercase">Earn</span>
                  </div>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">Your browser computes jobs & earns rewards. No setup needed.</p>
                </div>
              </div>

              {/* Main Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Submission Zone */}
              <div className="lg:col-span-4 space-y-6">
                <div id="job-form" className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-2xl blur opacity-10 group-hover:opacity-20 transition duration-1000"></div>
                  <div className="relative p-6 lg:p-8 bg-[#0a0a0a] border border-white/5 rounded-2xl flex flex-col gap-6 shadow-2xl">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center border border-emerald-500/20">
                        <Plus className="text-emerald-400 w-6 h-6" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-white">Submit Job</h2>
                        <p className="text-xs text-zinc-500">Train a model on the network</p>
                      </div>
                    </div>

                    <form onSubmit={createOnChainJob} className="flex flex-col gap-5">
                      <div className="flex bg-black/50 p-1 rounded-xl border border-white/5">
                        <button
                          type="button"
                          onClick={() => setIsAdvanced(false)}
                          className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all ${!isAdvanced ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                          Quick Mode
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsAdvanced(true)}
                          className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all ${isAdvanced ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
                        >
                          Custom Code
                        </button>
                      </div>

                      <div className="space-y-4">
                        {!isAdvanced ? (
                          <>
                            <div className="space-y-2">
                              <label className="text-xs font-bold text-zinc-400">Model Hash / IPFS URL</label>
                              <div className="relative">
                                <Database className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                                <input
                                  value={modelHash}
                                  onChange={(e) => setModelHash(e.target.value)}
                                  placeholder="ipfs://Qm... or https://..."
                                  className="w-full bg-black/40 border border-white/10 rounded-xl py-3 pl-11 pr-4 text-zinc-200 text-sm focus:border-emerald-500/40 transition-all font-mono outline-none"
                                />
                              </div>
                            </div>
                            <div className="space-y-2">
                              <label className="text-xs font-bold text-zinc-400">Dataset Hash / URL</label>
                              <div className="relative">
                                <Shield className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                                <input
                                  value={dataHash}
                                  onChange={(e) => setDataHash(e.target.value)}
                                  placeholder="ipfs://Qm... or https://..."
                                  className="w-full bg-black/40 border border-white/10 rounded-xl py-3 pl-11 pr-4 text-zinc-200 text-sm focus:border-emerald-500/40 transition-all font-mono outline-none"
                                />
                              </div>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="space-y-2">
                              <label className="text-xs font-bold text-zinc-400">Python Training Code</label>
                              <textarea
                                value={pythonCode}
                                onChange={(e) => setPythonCode(e.target.value)}
                                className="w-full h-40 bg-black/40 border border-white/10 rounded-xl p-4 text-zinc-300 text-xs focus:border-emerald-500/40 transition-all font-mono resize-none custom-scrollbar outline-none"
                              />
                            </div>
                            <div className="space-y-2">
                              <label className="text-xs font-bold text-zinc-400">Dataset File (CSV)</label>
                              <div className="relative">
                                <input
                                  type="file"
                                  accept=".csv"
                                  onChange={(e) => setDatasetFile(e.target.files?.[0] || null)}
                                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                                />
                                <div className="w-full py-3 px-4 bg-black/40 border border-dashed border-white/10 rounded-xl flex items-center justify-between hover:border-emerald-500/30 transition-all">
                                  <span className="text-xs text-zinc-500 truncate">
                                    {datasetFile ? `📄 ${datasetFile.name}` : 'Drop or click to upload...'}
                                  </span>
                                  <Plus className="w-4 h-4 text-emerald-500" />
                                </div>
                              </div>
                            </div>
                          </>
                        )}
                        <div className="space-y-2 pt-2">
                          <label className="text-xs font-bold text-zinc-400">Reward Amount (MATIC)</label>
                          <div className="relative">
                            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-emerald-500 font-bold">◈</span>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={reward}
                              onChange={(e) => setReward(e.target.value)}
                              className="w-full bg-black/40 border border-white/10 rounded-xl py-3 pl-10 pr-4 text-white text-lg font-bold focus:border-emerald-500/40 transition-all outline-none"
                            />
                          </div>
                        </div>
                      </div>

                      <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full py-4 mt-2 bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-xl disabled:opacity-50 transition-all hover:from-emerald-500 hover:to-emerald-400"
                      >
                        <div className="flex items-center justify-center gap-3 text-black font-bold text-sm">
                          {isSubmitting ? (
                            <RefreshCcw className="w-5 h-5 animate-spin" />
                          ) : (
                            <>
                              {!account ? (
                                <><Wallet className="w-5 h-5" /> Connect Wallet</>
                              ) : !networkOk ? (
                                <><AlertCircle className="w-5 h-5" /> Switch to Polygon Amoy</>
                              ) : (
                                <><Play className="w-5 h-5" /> Submit Training Job</>
                              )}
                            </>
                          )}
                        </div>
                      </button>

                      {/* Help Text */}
                      <p className="text-[10px] text-zinc-600 text-center">
                        Jobs are processed by browser workers across the network
                      </p>
                    </form>
                  </div>
                </div>
              </div>

              {/* Task Hub */}
              <div className="lg:col-span-8 space-y-6 pb-24">
                {/* Compact Stats Bar */}
                <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-[#0a0a0a] rounded-2xl border border-white/5">
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-sm font-bold text-white">Jobs</span>
                    </div>
                    <div className="flex gap-4 text-xs">
                      <span className="text-zinc-500">Total: <span className="text-white font-bold">{jobs.length}</span></span>
                      <span className="text-zinc-500">Active: <span className="text-cyan-400 font-bold">{jobs.filter(j => j.status === 'processing').length}</span></span>
                      <span className="text-zinc-500">Done: <span className="text-emerald-400 font-bold">{jobs.filter(j => j.status === 'completed').length}</span></span>
                    </div>
                  </div>
                  
                  {/* Filter Tabs */}
                  <div className="flex bg-black/50 p-1 rounded-xl border border-white/5">
                    <button 
                      onClick={() => setJobFilter('all')}
                      className={`px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                        jobFilter === 'all' ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-500 hover:text-white'
                      }`}
                    >All Jobs</button>
                    <button 
                      onClick={() => setJobFilter('mine')}
                      className={`px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                        jobFilter === 'mine' ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-500 hover:text-white'
                      }`}
                    >My Jobs</button>
                  </div>
                </div>

                {loading ? (
                  <div className="py-20 flex flex-col items-center gap-6 opacity-40">
                    <div className="w-16 h-16 border-4 border-emerald-500/10 border-t-emerald-500 rounded-full animate-spin" />
                    <span className="text-xs font-bold text-emerald-500">Loading jobs...</span>
                  </div>
                ) : filteredJobs.length === 0 ? (
                  <div className="p-12 bg-white/[0.02] border border-dashed border-white/10 rounded-2xl flex flex-col items-center text-center gap-6">
                    <div className="w-16 h-16 bg-white/5 rounded-2xl flex items-center justify-center border border-white/5">
                      <Brain className="w-8 h-8 text-zinc-600" />
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-white mb-2">
                        {jobFilter === 'mine' ? 'No jobs yet' : 'Network is quiet'}
                      </h3>
                      <p className="text-sm text-zinc-500">
                        {jobFilter === 'mine' ? 'Submit your first training job to get started!' : 'Be the first to submit a job to the network.'}
                      </p>
                    </div>
                    <button 
                      onClick={() => document.getElementById('job-form')?.scrollIntoView({ behavior: 'smooth' })}
                      className="px-6 py-3 bg-emerald-500 text-black font-bold rounded-xl text-sm hover:bg-emerald-400 transition-all"
                    >
                      Create Your First Job
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-6 animate-in fade-in slide-in-from-bottom-5 duration-700">
                    {filteredJobs.map((job) => (
                      <JobCard
                        key={job.id}
                        job={job}
                        account={account}
                        isWorkerMode={!!account}
                        onCancel={(id, onChainId) => cancelOnChainJob(id, onChainId!)}
                        onTest={(j) => setTestingJob(j)}
                        onWork={(j) => handleWork(j)}
                      />
                    ))}
                  </div>
                )}
              </div>
              </div>
            </div>
          )}

          {activeTab === 'nodes' && (
            <div className="max-w-[1600px] mx-auto space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
              {/* Worker Distribution Stats */}
              <WorkerDistribution />
              
              {/* Network Visualization */}
              <div className="p-12 bg-[#0a0a0a] rounded-[3rem] border border-white/5 min-h-[70vh] flex flex-col gap-10 relative shadow-2xl">
                <div className="relative z-10 flex justify-between items-start">
                  <div>
                    <h2 className="text-4xl font-black text-white italic uppercase tracking-tight">Fleet Topology</h2>
                    <p className="text-zinc-500 mt-2 font-medium tracking-wide">Global distribution of sovereign compute clusters.</p>
                  </div>
                  <div className="flex gap-4">
                    <div className="px-6 py-3 bg-white/5 rounded-2xl border border-white/5 flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest">{nodes.length} Active Nodes</span>
                    </div>
                  </div>
                </div>
                <div className="flex-1 w-full relative z-10 min-h-[500px]">
                  <NetworkVisualization />
                </div>
                <div className="absolute inset-0 bg-[radial-gradient(#ffffff03_1px,transparent_1px)] [background-size:40px_40px] opacity-50" />
              </div>
            </div>
          )}


        </div>
      </main>

      {/* Mobile Bottom Navigation - hidden on xl screens since we have sidebar */}
      <div className="xl:hidden fixed bottom-0 left-0 w-full bg-black/90 backdrop-blur-xl z-[100] p-3 flex justify-around items-center border-t border-white/10">
        {[
          { id: 'dashboard', icon: LayoutDashboard, label: 'Jobs' },
          { id: 'nodes', icon: Globe, label: 'Network' }
        ].map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`flex flex-col items-center gap-1 py-2 px-4 rounded-xl transition-all ${activeTab === item.id ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500'}`}
          >
            <item.icon className="w-5 h-5" />
            <span className="text-[10px] font-bold">{item.label}</span>
          </button>
        ))}
      </div>

      {/* Inference Modal - Improved */}
      {testingJob && (
        <div className="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-black/95 backdrop-blur-xl">
          <div className="w-full max-w-lg bg-[#0a0a0a] border border-white/10 rounded-2xl overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-cyan-500 to-blue-500" />
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold text-white">Run Inference</h3>
                <button onClick={() => setTestingJob(null)} className="p-2 bg-white/5 rounded-lg text-zinc-400 hover:text-white transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-bold text-zinc-400 mb-2 block">Input Data (JSON)</label>
                  <textarea
                    value={inferenceInput}
                    onChange={(e) => setInferenceInput(e.target.value)}
                    placeholder='{"data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}'
                    className="w-full h-32 bg-black border border-white/10 rounded-xl p-4 text-cyan-100 font-mono text-sm outline-none focus:border-cyan-500/50"
                  />
                </div>
                <button
                  onClick={runInference}
                  disabled={isSubmitting}
                  className="w-full py-4 bg-gradient-to-r from-cyan-600 to-cyan-500 text-black font-bold rounded-xl flex items-center justify-center gap-3 hover:from-cyan-500 hover:to-cyan-400 transition-all disabled:opacity-50"
                >
                  {isSubmitting ? <RefreshCcw className="w-5 h-5 animate-spin" /> : <><Zap className="w-5 h-5" /> Run Prediction</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Atmospheric FX */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none -z-0 overflow-hidden">
        <div className="absolute top-[-20%] left-[-20%] w-[60%] h-[60%] bg-emerald-500/[0.03] blur-[200px] rounded-full" />
        <div className="absolute bottom-[-20%] right-[-20%] w-[60%] h-[60%] bg-cyan-500/[0.03] blur-[200px] rounded-full" />
      </div>
    </div>
  );
}
