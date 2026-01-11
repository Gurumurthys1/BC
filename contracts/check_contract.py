import os
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path="contracts/src/.env")

RPC_URL = os.environ.get("RPC_URL")
CONTRACT_ADDRESS = "0x81347e742b9239e190881BE7cd8C6F3758f10257"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

print(f"Connected to RPC: {w3.is_connected()}")
print(f"Chain ID: {w3.eth.chain_id}")

# Check if contract exists
code = w3.eth.get_code(CONTRACT_ADDRESS)
print(f"\nContract at {CONTRACT_ADDRESS}")
print(f"Code length: {len(code)} bytes")
print(f"Contract exists: {len(code) > 2}")

if len(code) <= 2:
    print("\n⚠️  CONTRACT NOT DEPLOYED! The contract does not exist at this address.")
    print("You need to redeploy the contract.")
else:
    print("\n✅ Contract is deployed!")
    
    # Try to call a read function
    # Load ABI
    with open("web/app/lib/abi.json", "r") as f:
        abi = json.load(f)
    
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)
    
    try:
        job_count = contract.functions.jobCount().call()
        print(f"Job count: {job_count}")
    except Exception as e:
        print(f"Error calling jobCount: {e}")
    
    try:
        min_reward = contract.functions.minReward().call()
        print(f"Min reward: {w3.from_wei(min_reward, 'ether')} MATIC")
    except Exception as e:
        print(f"Error calling minReward: {e}")
        
    try:
        min_stake = contract.functions.minStake().call()
        print(f"Min stake: {w3.from_wei(min_stake, 'ether')} MATIC")
    except Exception as e:
        print(f"Error calling minStake: {e}")
