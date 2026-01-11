import os
from web3 import Web3
from dotenv import load_dotenv

from web3.middleware import ExtraDataToPOAMiddleware

load_dotenv(dotenv_path="contracts/src/.env")
RPC_URL = os.environ.get("RPC_URL")
w3 = Web3(Web3.HTTPProvider(RPC_URL))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

base_fee = w3.eth.get_block('latest')['baseFeePerGas']
priority_fee = w3.eth.max_priority_fee

print(f"Base Fee: {base_fee // 10**9} Gwei")
print(f"Priority Fee: {priority_fee // 10**9} Gwei")
print(f"Total Recommended Max Fee: {(int(base_fee * 1.5) + priority_fee) // 10**9} Gwei")
