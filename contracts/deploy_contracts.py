import os
import json
from web3 import Web3
from solcx import compile_standard, install_solc
from dotenv import load_dotenv
from web3.middleware import ExtraDataToPOAMiddleware

# Load environment variables
load_dotenv(dotenv_path=".env")

RPC_URL = os.environ.get("RPC_URL")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    print("Error: RPC_URL or PRIVATE_KEY not found in contracts/src/.env")
    exit()

w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

account = w3.eth.account.from_key(PRIVATE_KEY)

def deploy_contract(file_path, contract_name, constructor_args=None):
    print(f"\n[*] Compiling {contract_name}...")
    install_solc("0.8.17")
    
    with open(file_path, "r") as file:
        source_code = file.read()

    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {file_path: {"content": source_code}},
            "settings": {
                "outputSelection": {
                    "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                }
            },
        },
        solc_version="0.8.17",
    )

    bytecode = compiled_sol["contracts"][file_path][contract_name]["evm"]["bytecode"]["object"]
    abi = compiled_sol["contracts"][file_path][contract_name]["abi"]

    print(f"[*] Deploying {contract_name} to {RPC_URL}...")
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    nonce = w3.eth.get_transaction_count(account.address)
    
    # Modern EIP-1559 settings for Polygon
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    priority_fee = w3.eth.max_priority_fee
    
    # Aggressive gas for quick confirmation
    max_fee = int(base_fee * 2) + priority_fee
    
    tx_data = {
        "chainId": w3.eth.chain_id,
        "from": account.address,
        "nonce": nonce,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
    }

    if constructor_args:
        transaction = Contract.constructor(*constructor_args).build_transaction(tx_data)
    else:
        transaction = Contract.constructor().build_transaction(tx_data)

    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"    - Transaction sent: {tx_hash.hex()}")
    
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"[+] {contract_name} deployed to: {tx_receipt.contractAddress}")
    return tx_receipt.contractAddress

if __name__ == "__main__":
    try:
        # 1. Deploy MockVerifier
        verifier_address = deploy_contract("contracts/src/MockVerifier.sol", "MockVerifier")
        
        # 2. Deploy OblivionManager
        manager_address = deploy_contract("contracts/src/VouchManager.sol", "OblivionManager", [verifier_address])
        
        print("\n" + "="*50)
        print(f"DEPLOYMENT SUCCESSFUL")
        print(f"Verifier: {verifier_address}")
        print(f"Manager:  {manager_address}")
        print("="*50)
        
        with open("contracts/deployed_addresses.json", "w") as f:
            json.dump({
                "MockVerifier": verifier_address,
                "OblivionManager": manager_address
            }, f, indent=2)
            
    except Exception as e:
        print(f"\n[!] Deployment Failed: {e}")
