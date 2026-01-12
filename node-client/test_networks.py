#!/usr/bin/env python3
"""
OBLIVION Network Configuration Test
Verifies connectivity to all configured networks

Run: python test_networks.py
"""

import os
import sys
import asyncio
from web3 import Web3

# Load configuration
from network_config import (
    SHARDEUM_CONFIG, INCO_CONFIG, POLYGON_CONFIG,
    ACTIVE_NETWORK, get_network_config, get_rpc_url, 
    get_contract_address, is_inco_enabled
)

def test_rpc_connection(name: str, config: dict) -> tuple[bool, dict]:
    """Test RPC connection and get network info."""
    try:
        w3 = Web3(Web3.HTTPProvider(config['rpc_url'], request_kwargs={'timeout': 10}))
        
        if not w3.is_connected():
            return False, {'error': 'Connection failed'}
        
        chain_id = w3.eth.chain_id
        block_number = w3.eth.block_number
        
        # Verify chain ID matches
        expected_chain_id = config['chain_id']
        chain_match = chain_id == expected_chain_id
        
        return True, {
            'chain_id': chain_id,
            'expected_chain_id': expected_chain_id,
            'chain_match': chain_match,
            'block_number': block_number,
            'synced': block_number > 0
        }
    except Exception as e:
        return False, {'error': str(e)}

def test_contract_deployment(name: str, rpc_url: str, contract_address: str) -> tuple[bool, dict]:
    """Check if contract is deployed at address."""
    if not contract_address or contract_address == '0x0000000000000000000000000000000000000000':
        return False, {'error': 'Contract address not configured'}
    
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
        code = w3.eth.get_code(contract_address)
        
        if len(code) > 2:  # '0x' is empty code
            return True, {'deployed': True, 'code_size': len(code)}
        else:
            return False, {'deployed': False, 'error': 'No code at address'}
    except Exception as e:
        return False, {'error': str(e)}

def test_wallet_balance(rpc_url: str, address: str) -> tuple[bool, dict]:
    """Check wallet balance."""
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
        balance_wei = w3.eth.get_balance(address)
        balance = w3.from_wei(balance_wei, 'ether')
        
        return True, {
            'balance': float(balance),
            'has_funds': balance_wei > 0
        }
    except Exception as e:
        return False, {'error': str(e)}

def print_result(name: str, success: bool, info: dict):
    """Print formatted test result."""
    status = "✅" if success else "❌"
    print(f"  {status} {name}")
    for key, value in info.items():
        print(f"     {key}: {value}")

def main():
    print("=" * 70)
    print("              OBLIVION NETWORK CONFIGURATION TEST")
    print("=" * 70)
    print(f"\nActive Network: {ACTIVE_NETWORK.upper()}")
    print(f"INCO Enabled:   {is_inco_enabled()}")
    
    # Test all networks
    networks = [
        ('Shardeum EVM Testnet', SHARDEUM_CONFIG),
        ('INCO Rivest Testnet', INCO_CONFIG),
        ('Polygon Amoy Testnet', POLYGON_CONFIG),
    ]
    
    all_passed = True
    
    print("\n" + "-" * 70)
    print("1. RPC CONNECTIVITY")
    print("-" * 70)
    
    for name, config in networks:
        success, info = test_rpc_connection(name, config)
        print_result(name, success, info)
        if name == 'Shardeum EVM Testnet' and not success:
            all_passed = False
    
    print("\n" + "-" * 70)
    print("2. CONTRACT DEPLOYMENT")
    print("-" * 70)
    
    # Check Shardeum contract
    shardeum_contract = SHARDEUM_CONFIG.get('oblivion_manager', '')
    success, info = test_contract_deployment(
        'Shardeum OblivionManager',
        SHARDEUM_CONFIG['rpc_url'],
        shardeum_contract
    )
    print_result(f"Shardeum OblivionManager ({shardeum_contract[:10]}...)" if shardeum_contract else "Shardeum OblivionManager", success, info)
    
    # Check INCO contract
    inco_contract = INCO_CONFIG.get('confidential_bids', '')
    success, info = test_contract_deployment(
        'INCO ConfidentialBids',
        INCO_CONFIG['rpc_url'],
        inco_contract
    )
    print_result(f"INCO ConfidentialBids ({inco_contract[:10]}...)" if inco_contract else "INCO ConfidentialBids", success, info)
    
    # Check Polygon contract (existing)
    polygon_contract = POLYGON_CONFIG.get('oblivion_manager', '')
    success, info = test_contract_deployment(
        'Polygon OblivionManager',
        POLYGON_CONFIG['rpc_url'],
        polygon_contract
    )
    print_result(f"Polygon OblivionManager ({polygon_contract[:10]}...)", success, info)
    
    print("\n" + "-" * 70)
    print("3. WALLET CONFIGURATION")
    print("-" * 70)
    
    private_key = os.getenv('PRIVATE_KEY')
    if private_key:
        try:
            w3 = Web3()
            account = w3.eth.account.from_key(private_key)
            print(f"  ✅ Wallet configured: {account.address}")
            
            # Check balances on each network
            for name, config in networks:
                success, info = test_wallet_balance(config['rpc_url'], account.address)
                symbol = config['native_currency']
                if success:
                    print(f"     {name}: {info['balance']:.4f} {symbol}")
                else:
                    print(f"     {name}: Error - {info['error']}")
        except Exception as e:
            print(f"  ❌ Wallet error: {e}")
            all_passed = False
    else:
        print("  ⚠️  No PRIVATE_KEY configured (set in .env)")
    
    print("\n" + "-" * 70)
    print("4. CONFIGURATION SUMMARY")
    print("-" * 70)
    
    active_config = get_network_config()
    print(f"  Active Network:    {active_config['name']}")
    print(f"  RPC URL:           {get_rpc_url()}")
    print(f"  Contract Address:  {get_contract_address() or 'NOT DEPLOYED'}")
    print(f"  Chain ID:          {active_config['chain_id']}")
    print(f"  Currency:          {active_config['native_currency']}")
    
    if is_inco_enabled():
        print(f"\n  INCO Gateway:      {INCO_CONFIG['gateway_url']}")
        print(f"  INCO Contract:     {INCO_CONFIG.get('confidential_bids', 'NOT DEPLOYED')}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All critical tests passed!")
    else:
        print("⚠️  Some tests failed - check configuration")
    print("=" * 70)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
