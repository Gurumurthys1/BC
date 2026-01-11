import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

RPC_URL = os.environ.get("RPC_URL")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    print("Error: RPC_URL or PRIVATE_KEY not found")
    exit()

w3 = Web3(Web3.HTTPProvider(RPC_URL))
try:
    account = w3.eth.account.from_key(PRIVATE_KEY)
    balance = w3.eth.get_balance(account.address)
    print(f"Address: {account.address}")
    print(f"Balance: {w3.from_wei(balance, 'ether')} MATIC")
except Exception as e:
    print(f"Error: {e}")
