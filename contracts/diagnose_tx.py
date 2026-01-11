"""
OBLIVION Deep Transaction Diagnostic Tool - File Output Version
"""
import os
import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configuration
RPC_URL = os.environ.get("RPC_URL", "https://polygon-amoy-bor-rpc.publicnode.com")
CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

output = []

def log(msg):
    print(msg)
    output.append(msg)

log("=" * 60)
log("OBLIVION DEEP TRANSACTION DIAGNOSTIC")
log("=" * 60)

# 1. Connect to Network
log("\n[1] Connecting to Polygon Amoy...")
w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

if w3.is_connected():
    log(f"    OK: Connected to chain ID: {w3.eth.chain_id}")
else:
    log("    FAIL: Could not connect!")
    with open("diagnostic_result.txt", "w") as f:
        f.write("\n".join(output))
    exit(1)

# 2. Check Account
log("\n[2] Checking Account...")
account = w3.eth.account.from_key(PRIVATE_KEY)
balance = w3.eth.get_balance(account.address)
log(f"    Address: {account.address}")
log(f"    Balance: {w3.from_wei(balance, 'ether')} MATIC")

if balance < w3.to_wei(0.15, 'ether'):
    log("    WARNING: Balance is LOW!")

# 3. Check Contract
log("\n[3] Checking Contract...")
log(f"    Target: {CONTRACT_ADDRESS}")
code = w3.eth.get_code(CONTRACT_ADDRESS)
if code == b'' or code.hex() == '0x':
    log("    FAIL: NO CONTRACT AT THIS ADDRESS!")
    with open("diagnostic_result.txt", "w") as f:
        f.write("\n".join(output))
    exit(1)
else:
    log(f"    OK: Contract exists ({len(code)} bytes)")

# 4. Load ABI
log("\n[4] Loading ABI...")
try:
    with open("web/app/lib/abi.json", "r") as f:
        abi = json.load(f)
    log(f"    OK: ABI loaded ({len(abi)} items)")
except Exception as e:
    log(f"    FAIL: {e}")
    with open("diagnostic_result.txt", "w") as f:
        f.write("\n".join(output))
    exit(1)

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

# 5. Test Read
log("\n[5] Testing Contract Read...")
try:
    owner = contract.functions.owner().call()
    log(f"    OK: Contract owner = {owner}")
except Exception as e:
    log(f"    INFO: owner() not accessible: {e}")

# 6. Simulate Transaction
log("\n[6] Simulating createJob Transaction...")
test_model = "ipfs://test"
test_data = "ipfs://test"
reward = w3.to_wei(0.01, 'ether')

try:
    tx = contract.functions.createJob(1, test_model, test_data).build_transaction({
        'from': account.address,
        'value': reward,
        'gas': 300000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address)
    })
    log("    OK: Transaction built")
    
    # Gas estimation reveals reverts
    log("\n[7] Estimating Gas...")
    try:
        gas = w3.eth.estimate_gas({
            'from': account.address,
            'to': CONTRACT_ADDRESS,
            'data': tx['data'],
            'value': reward
        })
        log(f"    OK: Gas estimate = {gas}")
        log("\n    >>> TRANSACTION WILL SUCCEED <<<")
        log("    The issue is MetaMask. Reset it: Settings > Advanced > Clear Activity Tab Data")
        
    except Exception as gas_err:
        log(f"    FAIL: Gas estimation failed!")
        log(f"    ERROR: {gas_err}")
        log("\n    >>> THIS IS THE REAL BLOCKCHAIN ERROR <<<")
        
except Exception as e:
    log(f"    FAIL: {e}")

# Write results
with open("diagnostic_result.txt", "w") as f:
    f.write("\n".join(output))

log("\n" + "=" * 60)
log("Results saved to: diagnostic_result.txt")
log("=" * 60)
