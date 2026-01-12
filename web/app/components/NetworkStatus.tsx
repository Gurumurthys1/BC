'use client';

import React from 'react';
import { Shield, Lock, ExternalLink, CheckCircle, XCircle, Globe } from 'lucide-react';
import { ACTIVE_NETWORK, getNetworkConfig } from '../lib/config';

interface NetworkStatusProps {
  shardeumConnected: boolean;
  incoReady: boolean;
  shardeumChainId?: number;
  account?: string;
}

export default function NetworkStatus({ 
  shardeumConnected, 
  incoReady,
  shardeumChainId,
  account 
}: NetworkStatusProps) {
  const networkConfig = getNetworkConfig();
  const isCorrectNetwork = shardeumChainId === networkConfig.chainId;
  const isPrimaryShardeum = ACTIVE_NETWORK === 'shardeum';

  return (
    <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 p-4">
      <h3 className="text-sm font-medium text-white/70 mb-3 flex items-center gap-2">
        <Shield className="w-4 h-4" />
        Network Status
      </h3>
      
      <div className="grid grid-cols-2 gap-4">
        {/* Primary Network Status */}
        <div className="bg-white/5 rounded-xl p-3 border border-white/5">
          <div className="flex items-center gap-2 mb-2">
            <Globe className="w-5 h-5 text-emerald-400" />
            <span className="text-white font-medium text-sm">
              {isPrimaryShardeum ? 'Shardeum' : 'Polygon'}
            </span>
          </div>
          
          <div className="flex items-center gap-1.5 text-xs">
            {shardeumConnected && isCorrectNetwork ? (
              <>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Connected</span>
              </>
            ) : shardeumConnected ? (
              <>
                <XCircle className="w-3.5 h-3.5 text-yellow-400" />
                <span className="text-yellow-400">Wrong Network</span>
              </>
            ) : (
              <>
                <XCircle className="w-3.5 h-3.5 text-red-400" />
                <span className="text-red-400">Disconnected</span>
              </>
            )}
          </div>
          
          <div className="mt-2 text-xs text-white/40">
            {isCorrectNetwork ? `${networkConfig.chainName} (${networkConfig.chainId})` : `Chain: ${shardeumChainId || 'N/A'}`}
          </div>
          
          <a 
            href={networkConfig.explorerUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="mt-2 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
          >
            <ExternalLink className="w-3 h-3" />
            Explorer
          </a>
        </div>

        {/* INCO Status */}
        <div className="bg-white/5 rounded-xl p-3 border border-white/5">
          <div className="flex items-center gap-2 mb-2">
            <Lock className="w-5 h-5 text-purple-400" />
            <span className="text-white font-medium text-sm">INCO</span>
          </div>
          
          <div className="flex items-center gap-1.5 text-xs">
            {incoReady ? (
              <>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">FHE Ready</span>
              </>
            ) : (
              <>
                <XCircle className="w-3.5 h-3.5 text-yellow-400" />
                <span className="text-yellow-400">Not Configured</span>
              </>
            )}
          </div>
          
          <div className="mt-2 text-xs text-white/40">
            Confidential Computing
          </div>
          
          <a 
            href="https://docs.inco.org" 
            target="_blank" 
            rel="noopener noreferrer"
            className="mt-2 flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300"
          >
            <ExternalLink className="w-3 h-3" />
            Docs
          </a>
        </div>
      </div>

      {/* Features */}
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-white/60">
          <Shield className="w-3.5 h-3.5 text-cyan-400" />
          <span>Job Settlement</span>
        </div>
        <div className="flex items-center gap-1.5 text-white/60">
          <Lock className="w-3.5 h-3.5 text-purple-400" />
          <span>Encrypted Bids</span>
        </div>
      </div>
    </div>
  );
}
