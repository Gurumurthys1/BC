#!/usr/bin/env python3
"""
Shardeum + INCO Network Configuration for Oblivion Worker

OBLIVION: Decentralized ML Compute Marketplace
- PRIMARY: Shardeum for job settlement (scalable, low-fee)
- CONFIDENTIAL: INCO for encrypted bids (FHE-based privacy)
- FALLBACK: Polygon Amoy for development/testing

Update contract addresses after deployment.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# NETWORK SELECTION
# =============================================================================

# Set to 'shardeum' for hackathon, 'polygon' for fallback
# Using 'polygon' until Shardeum wallet is funded with SHM tokens
ACTIVE_NETWORK = os.getenv('ACTIVE_NETWORK', 'polygon')

# =============================================================================
# SHARDEUM EVM TESTNET - Primary Settlement Layer
# =============================================================================

SHARDEUM_CONFIG = {
    'name': 'Shardeum EVM Testnet',
    'chain_id': 8119,
    'rpc_url': 'https://api-mezame.shardeum.org',
    'explorer_url': 'https://explorer-mezame.shardeum.org',
    'native_currency': 'SHM',
    'block_time': 2,  # seconds
    'gas_multiplier': 1.2,
    'confirmations': 1,
    # Contract addresses - UPDATE AFTER DEPLOYMENT
    'oblivion_manager': os.getenv('SHARDEUM_CONTRACT_ADDRESS', ''),
}

# =============================================================================
# INCO RIVEST TESTNET - Confidential Computing Layer (FHE)
# =============================================================================

INCO_CONFIG = {
    'name': 'INCO Rivest Testnet',
    'chain_id': 21097,
    'rpc_url': 'https://validator.rivest.inco.org',
    'explorer_url': 'https://explorer.rivest.inco.org',
    'gateway_url': 'https://gateway.rivest.inco.org',
    'native_currency': 'INCO',
    # FHE-specific settings
    'fhe_enabled': True,
    'encryption_types': ['euint256', 'ebool', 'eaddress'],
    # Contract addresses - UPDATE AFTER DEPLOYMENT
    'confidential_bids': os.getenv('INCO_CONTRACT_ADDRESS', ''),
}

# =============================================================================
# POLYGON AMOY TESTNET - Fallback/Development
# =============================================================================

POLYGON_CONFIG = {
    'name': 'Polygon Amoy Testnet',
    'chain_id': 80002,
    'rpc_url': 'https://polygon-amoy-bor-rpc.publicnode.com',
    'explorer_url': 'https://amoy.polygonscan.com',
    'native_currency': 'MATIC',
    'block_time': 2,
    'gas_multiplier': 1.5,
    'confirmations': 2,
    # New decentralized contract (no Supabase needed)
    'oblivion_manager': '0x9EE623E30Ad75C156099d9309924bd989b8f37c4',
    # Legacy contract (uses Supabase)  
    'legacy_manager': '0x2681849aB3d8E470Dedc08b1a4CED92493886501',
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_network_config():
    """Get the active network configuration."""
    if ACTIVE_NETWORK == 'shardeum':
        return SHARDEUM_CONFIG
    elif ACTIVE_NETWORK == 'inco':
        return INCO_CONFIG
    else:
        return POLYGON_CONFIG

def get_rpc_url():
    """Get RPC URL for the active network."""
    return get_network_config()['rpc_url']

def get_contract_address():
    """Get OblivionManager contract address for active network."""
    config = get_network_config()
    return config.get('oblivion_manager', '')

def get_chain_id():
    """Get chain ID for active network."""
    return get_network_config()['chain_id']

def get_native_currency():
    """Get native currency symbol."""
    return get_network_config()['native_currency']

def get_explorer_tx_url(tx_hash: str) -> str:
    """Get explorer URL for a transaction."""
    config = get_network_config()
    return f"{config['explorer_url']}/tx/{tx_hash}"

def get_explorer_address_url(address: str) -> str:
    """Get explorer URL for an address."""
    config = get_network_config()
    return f"{config['explorer_url']}/address/{address}"

def get_gas_multiplier():
    """Get gas price multiplier for the network."""
    return get_network_config().get('gas_multiplier', 1.5)

def get_confirmations():
    """Get required confirmations for the network."""
    return get_network_config().get('confirmations', 1)

# INCO-specific helpers
def get_inco_rpc():
    """Get INCO RPC URL."""
    return INCO_CONFIG['rpc_url']

def get_inco_gateway():
    """Get INCO gateway URL for FHE operations."""
    return INCO_CONFIG['gateway_url']

def get_inco_contract_address():
    """Get ConfidentialJobBids contract address on INCO."""
    return INCO_CONFIG.get('confidential_bids', '')

def is_inco_enabled():
    """Check if INCO integration is configured."""
    return bool(INCO_CONFIG.get('confidential_bids'))

# =============================================================================
# PRINT CONFIG (for debugging)
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("OBLIVION Network Configuration")
    print("=" * 60)
    print(f"\nActive Network: {ACTIVE_NETWORK.upper()}")
    config = get_network_config()
    print(f"Network Name:   {config['name']}")
    print(f"Chain ID:       {config['chain_id']}")
    print(f"RPC URL:        {config['rpc_url']}")
    print(f"Explorer:       {config['explorer_url']}")
    print(f"Currency:       {config['native_currency']}")
    print(f"Contract:       {get_contract_address() or 'NOT DEPLOYED'}")
    
    print(f"\nINCO Integration:")
    print(f"Enabled:        {is_inco_enabled()}")
    print(f"RPC:            {get_inco_rpc()}")
    print(f"Gateway:        {get_inco_gateway()}")
    print(f"Contract:       {get_inco_contract_address() or 'NOT DEPLOYED'}")
    print("=" * 60)
