// Network Configuration for Shardeum + INCO Integration
// OBLIVION: Decentralized ML Compute Marketplace
// 
// Architecture:
// - PRIMARY: Shardeum for job settlement (scalable, low-fee)
// - CONFIDENTIAL: INCO for encrypted bids (FHE-based privacy)
// - FALLBACK: Polygon Amoy for development/testing

export const NETWORKS = {
  // ═══════════════════════════════════════════════════════════════════════════
  // SHARDEUM EVM TESTNET - Primary Settlement Layer
  // ═══════════════════════════════════════════════════════════════════════════
  shardeum: {
    chainId: 8119,
    chainIdHex: '0x1fb7',
    chainName: 'Shardeum EVM Testnet',
    nativeCurrency: {
      name: 'Shardeum',
      symbol: 'SHM',
      decimals: 18
    },
    rpcUrl: 'https://api-mezame.shardeum.org',
    explorerUrl: 'https://explorer-mezame.shardeum.org',
    faucetUrl: 'https://docs.shardeum.org/docs/developer/faucet',
    // Contract addresses - UPDATE AFTER DEPLOYMENT
    contracts: {
      oblivionManager: process.env.NEXT_PUBLIC_SHARDEUM_CONTRACT || '0x0000000000000000000000000000000000000000',
    },
    // Network characteristics
    blockTime: 2, // seconds
    gasMultiplier: 1.2,
    confirmations: 1
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // INCO NETWORK - Confidential Computing Layer (FHE)
  // ═══════════════════════════════════════════════════════════════════════════
  inco: {
    chainId: 21097, // INCO Rivest testnet
    chainIdHex: '0x5269',
    chainName: 'INCO Rivest Testnet',
    nativeCurrency: {
      name: 'INCO',
      symbol: 'INCO',
      decimals: 18
    },
    rpcUrl: 'https://validator.rivest.inco.org',
    explorerUrl: 'https://explorer.rivest.inco.org',
    gatewayUrl: 'https://gateway.rivest.inco.org',
    contracts: {
      confidentialBids: process.env.NEXT_PUBLIC_INCO_CONTRACT || '0x0000000000000000000000000000000000000000',
    },
    // FHE-specific settings
    fheEnabled: true,
    encryptionTypes: ['euint256', 'ebool', 'eaddress']
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // POLYGON AMOY - Fallback/Development Network
  // ═══════════════════════════════════════════════════════════════════════════
  polygonAmoy: {
    chainId: 80002,
    chainIdHex: '0x13882',
    chainName: 'Polygon Amoy Testnet',
    nativeCurrency: {
      name: 'MATIC',
      symbol: 'MATIC',
      decimals: 18
    },
    rpcUrl: 'https://polygon-amoy-bor-rpc.publicnode.com',
    explorerUrl: 'https://amoy.polygonscan.com',
    contracts: {
      // New decentralized contract (no Supabase needed)
      oblivionManager: '0x9EE623E30Ad75C156099d9309924bd989b8f37c4',
      // Legacy contract (uses Supabase)
      legacyManager: '0x2681849aB3d8E470Dedc08b1a4CED92493886501',
    },
    blockTime: 2,
    gasMultiplier: 1.5,
    confirmations: 2
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// NETWORK SELECTION - Change this to switch networks
// Options: 'shardeum' | 'polygonAmoy'
// Set to 'polygonAmoy' until Shardeum wallet is funded
// ═══════════════════════════════════════════════════════════════════════════
export const ACTIVE_NETWORK: 'shardeum' | 'polygonAmoy' = 
  (process.env.NEXT_PUBLIC_ACTIVE_NETWORK as 'shardeum' | 'polygonAmoy') || 'polygonAmoy';

// INCO is always available for confidential features (cross-chain)
export const INCO_ENABLED = process.env.NEXT_PUBLIC_INCO_ENABLED !== 'false';

// ═══════════════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

// Get current network config
export function getNetworkConfig() {
  return NETWORKS[ACTIVE_NETWORK];
}

// Get INCO network config
export function getIncoConfig() {
  return NETWORKS.inco;
}

// Get contract address for current network
export function getContractAddress(contractName: 'oblivionManager'): string {
  const network = getNetworkConfig();
  return network.contracts[contractName] || '';
}

// Get INCO contract address
export function getIncoContractAddress(): string {
  return NETWORKS.inco.contracts.confidentialBids || '';
}

// Get RPC URL for current network
export function getRpcUrl(): string {
  return getNetworkConfig().rpcUrl;
}

// Explorer URL builders
export function getTxUrl(txHash: string, network: 'shardeum' | 'inco' | 'polygonAmoy' = ACTIVE_NETWORK): string {
  const config = NETWORKS[network];
  return `${config.explorerUrl}/tx/${txHash}`;
}

export function getAddressUrl(address: string, network: 'shardeum' | 'inco' | 'polygonAmoy' = ACTIVE_NETWORK): string {
  const config = NETWORKS[network];
  return `${config.explorerUrl}/address/${address}`;
}

// Wallet chain parameters for MetaMask
export function getChainParams() {
  const config = getNetworkConfig();
  return {
    chainId: config.chainIdHex,
    chainName: config.chainName,
    nativeCurrency: config.nativeCurrency,
    rpcUrls: [config.rpcUrl],
    blockExplorerUrls: [config.explorerUrl]
  };
}

// Check if on correct network
export function isCorrectNetwork(chainId: number): boolean {
  return chainId === getNetworkConfig().chainId;
}

// Format native currency
export function getNativeCurrencySymbol(): string {
  return getNetworkConfig().nativeCurrency.symbol;
}

// Get gas multiplier for current network
export function getGasMultiplier(): number {
  return (getNetworkConfig() as any).gasMultiplier || 1.5;
}

// Get required confirmations
export function getConfirmations(): number {
  return (getNetworkConfig() as any).confirmations || 1;
}

// Export constants for direct import
export const CONTRACT_ADDRESS = getContractAddress('oblivionManager');
export const RPC_URL = getRpcUrl();
export const CHAIN_ID = getNetworkConfig().chainId;
export const EXPLORER_URL = getNetworkConfig().explorerUrl;
export const CURRENCY_SYMBOL = getNativeCurrencySymbol();

