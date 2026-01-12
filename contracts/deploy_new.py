"""
Deploy OblivionManager to multiple networks
Supports: Polygon Amoy, Shardeum, INCO
"""
import os
import json
import solcx
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# Network configurations
NETWORKS = {
    'polygon': {
        'rpc': 'https://polygon-amoy-bor-rpc.publicnode.com',
        'chain_id': 80002,
        'symbol': 'MATIC',
        'explorer': 'https://amoy.polygonscan.com'
    },
    'shardeum': {
        'rpc': 'https://api-mezame.shardeum.org',
        'chain_id': 8119,
        'symbol': 'SHM',
        'explorer': 'https://explorer-mezame.shardeum.org'
    }
}

def compile_contract():
    """Compile the OblivionManager contract"""
    print("📝 Compiling contracts...")
    
    # Install solc if needed
    try:
        solcx.get_installed_solc_versions()
    except:
        print("  Installing solc 0.8.17...")
        solcx.install_solc('0.8.17')
    
    solcx.set_solc_version('0.8.17')
    
    # Read contract source - use simplified version to avoid stack depth issues
    contract_path = os.path.join(os.path.dirname(__file__), 'src', 'OblivionManagerSimple.sol')
    with open(contract_path, 'r') as f:
        source = f.read()
    
    # Compile with optimizer to help with stack depth
    compiled = solcx.compile_source(
        source,
        output_values=['abi', 'bin'],
        solc_version='0.8.17',
        optimize=True,
        optimize_runs=200
    )
    
    # Get OblivionManager contract
    contract_id = '<stdin>:OblivionManager'
    contract_data = compiled[contract_id]
    
    print("  ✅ Compilation successful")
    
    return contract_data['abi'], contract_data['bin']

def compile_mock_verifier():
    """Compile MockVerifier contract"""
    verifier_path = os.path.join(os.path.dirname(__file__), 'src', 'MockVerifier.sol')
    with open(verifier_path, 'r') as f:
        source = f.read()
    
    compiled = solcx.compile_source(
        source,
        output_values=['abi', 'bin'],
        solc_version='0.8.17'
    )
    
    contract_id = '<stdin>:MockVerifier'
    contract_data = compiled[contract_id]
    
    return contract_data['abi'], contract_data['bin']

def deploy_contract(network: str, abi, bytecode, constructor_args=None):
    """Deploy contract to specified network"""
    if network not in NETWORKS:
        raise ValueError(f"Unknown network: {network}")
    
    config = NETWORKS[network]
    print(f"\n🚀 Deploying to {network.upper()}...")
    print(f"   RPC: {config['rpc']}")
    print(f"   Chain ID: {config['chain_id']}")
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(config['rpc']))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    # Check connection
    if not w3.is_connected():
        raise Exception(f"Cannot connect to {network}")
    
    print(f"   Connected! Block: {w3.eth.block_number}")
    
    # Set up account
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        raise Exception("PRIVATE_KEY not set in environment")
    
    account = Account.from_key(private_key)
    address = account.address
    
    balance = w3.eth.get_balance(address)
    print(f"   Deployer: {address}")
    print(f"   Balance: {w3.from_wei(balance, 'ether')} {config['symbol']}")
    
    if balance == 0:
        raise Exception(f"No {config['symbol']} balance! Get tokens from faucet.")
    
    # Create contract instance
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Build constructor transaction
    if constructor_args:
        construct_txn = Contract.constructor(*constructor_args).build_transaction({
            'from': address,
            'gas': 5000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(address)
        })
    else:
        construct_txn = Contract.constructor().build_transaction({
            'from': address,
            'gas': 5000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(address)
        })
    
    # Sign and send
    print("   📤 Sending deployment transaction...")
    signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    
    print(f"   Transaction: {tx_hash.hex()}")
    print("   ⏳ Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    if receipt['status'] != 1:
        raise Exception("Deployment failed!")
    
    contract_address = receipt['contractAddress']
    print(f"   ✅ Contract deployed at: {contract_address}")
    print(f"   Explorer: {config['explorer']}/address/{contract_address}")
    
    return contract_address

def save_deployment(network: str, addresses: dict):
    """Save deployed addresses to file"""
    addresses_file = os.path.join(os.path.dirname(__file__), 'deployed_addresses.json')
    
    # Load existing
    existing = {}
    if os.path.exists(addresses_file):
        with open(addresses_file, 'r') as f:
            existing = json.load(f)
    
    # Update
    existing[network] = addresses
    
    # Save
    with open(addresses_file, 'w') as f:
        json.dump(existing, f, indent=2)
    
    print(f"\n📄 Addresses saved to deployed_addresses.json")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy OblivionManager contracts')
    parser.add_argument('network', choices=['polygon', 'shardeum', 'all'],
                       help='Network to deploy to')
    parser.add_argument('--skip-verifier', action='store_true',
                       help='Skip deploying MockVerifier (use existing)')
    parser.add_argument('--verifier', type=str,
                       help='Existing verifier address to use')
    
    args = parser.parse_args()
    
    networks = ['polygon', 'shardeum'] if args.network == 'all' else [args.network]
    
    # Compile contracts
    oblivion_abi, oblivion_bytecode = compile_contract()
    
    for network in networks:
        try:
            # Deploy MockVerifier first (or use existing)
            if args.verifier:
                verifier_address = args.verifier
                print(f"\n📌 Using existing verifier: {verifier_address}")
            elif not args.skip_verifier:
                verifier_abi, verifier_bytecode = compile_mock_verifier()
                verifier_address = deploy_contract(network, verifier_abi, verifier_bytecode)
            else:
                verifier_address = "0x0000000000000000000000000000000000000001"  # Dummy
            
            # Deploy OblivionManager
            manager_address = deploy_contract(
                network, 
                oblivion_abi, 
                oblivion_bytecode,
                constructor_args=[verifier_address]
            )
            
            # Save addresses
            save_deployment(network, {
                'verifier': verifier_address,
                'oblivionManager': manager_address
            })
            
            # Save ABI
            abi_path = os.path.join(os.path.dirname(__file__), '..', 'web', 'app', 'lib', 'abi.json')
            with open(abi_path, 'w') as f:
                json.dump(oblivion_abi, f, indent=2)
            print(f"📄 ABI saved to web/app/lib/abi.json")
            
        except Exception as e:
            print(f"\n❌ Deployment to {network} failed: {e}")
            continue
    
    print("\n🎉 Deployment complete!")

if __name__ == "__main__":
    main()
