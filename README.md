# 🧠 OBLIVION - Decentralized Machine Learning Marketplace

<div align="center">

**Fully Decentralized ML Training on Blockchain + IPFS**

[![Polygon](https://img.shields.io/badge/Polygon-Amoy-8247E5?style=flat-square&logo=polygon)](https://polygon.technology/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)](https://python.org/)

</div>

---

## 🌟 Overview

OBLIVION is a **fully decentralized** machine learning marketplace that connects:
- **Requesters** who need ML models trained
- **Workers** who provide computing power

**No centralized database required** - all coordination happens on-chain with IPFS for file storage.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              POLYGON AMOY BLOCKCHAIN                             │
│     Contract: 0x9EE623E30Ad75C156099d9309924bd989b8f37c4        │
│                                                                  │
│  • Job creation with ETH rewards                                │
│  • Worker registration with staking                             │
│  • Job claiming and completion                                  │
│  • On-chain statistics                                          │
└─────────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌──────────────────────┐      ┌─────────────────────────────┐
│        IPFS          │      │     WORKER NODES            │
│   (File Storage)     │      │  decentralized_worker.py    │
│                      │      │                             │
│  • Training scripts  │      │  • Polls blockchain         │
│  • Datasets          │      │  • Trains models (PyTorch)  │
│  • Trained models    │      │  • Differential privacy     │
│  • ZK proofs         │      │  • Submits results on-chain │
└──────────────────────┘      └─────────────────────────────┘
```

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| **Fully Decentralized** | No centralized database - blockchain + IPFS only |
| **Staking System** | Workers stake collateral, lose it if they cheat |
| **Fair Distribution** | Workers with fewer jobs get priority |
| **Differential Privacy** | Mathematical privacy guarantees (ε=1.0) |
| **Quality Verification** | Automatic rejection of undertrained models |
| **On-Chain Rewards** | Workers paid in MATIC upon completion |

## 📁 Project Structure

```
BC/
├── contracts/                 # Smart contracts
│   ├── src/
│   │   ├── OblivionManagerSimple.sol  # Main contract (deployed)
│   │   └── MockVerifier.sol           # ZK proof verifier
│   └── deploy_new.py          # Deployment script
│
├── node-client/               # Python worker node
│   ├── blockchain_client.py   # Contract interaction
│   ├── ipfs_client.py         # IPFS file storage
│   ├── decentralized_worker.py # Main worker process
│   ├── privacy.py             # Differential privacy
│   ├── quality_verification.py # Model quality checks
│   ├── zk_proofs.py           # ZK proof generation
│   ├── network_config.py      # Network configuration
│   └── verify_system.py       # System verification
│
├── web/                       # Next.js frontend
│   └── app/
│       ├── page.tsx           # Main dashboard
│       ├── components/        # React components
│       └── lib/
│           ├── blockchain.ts  # Contract client
│           ├── config.ts      # Network config
│           └── hooks.ts       # React hooks
│
├── visualizer_app/            # Streamlit dashboard (alternative)
│   └── app.py
│
└── sample_job/                # Example training job
    ├── training_script.py
    └── dataset.csv
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- MetaMask wallet with Polygon Amoy MATIC

### 1. Setup Environment

```bash
# Clone and setup
cd BC
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r node-client/requirements.txt

# Setup frontend
cd web
npm install
```

### 2. Configure Environment

Create `.env` files:

**node-client/.env:**
```
RPC_URL=https://polygon-amoy-bor-rpc.publicnode.com
CONTRACT_ADDRESS=0x9EE623E30Ad75C156099d9309924bd989b8f37c4
PRIVATE_KEY=your_private_key
```

**web/.env:**
```
NEXT_PUBLIC_CONTRACT_ADDRESS=0x9EE623E30Ad75C156099d9309924bd989b8f37c4
```

### 3. Run the System

**Start Frontend:**
```bash
cd web
npm run dev
# Open http://localhost:3000
```

**Start Worker:**
```bash
cd node-client
python decentralized_worker.py
```

**Verify System:**
```bash
cd node-client
python verify_system.py
```

## 📊 Current Status

| Component | Status |
|-----------|--------|
| Smart Contract | ✅ Deployed on Polygon Amoy |
| Blockchain Client | ✅ Working |
| IPFS Client | ✅ Working |
| Worker Node | ✅ Working |
| Frontend | ✅ Working |
| Differential Privacy | ✅ Enabled (ε=1.0) |

## 🔗 Contract Details

- **Network:** Polygon Amoy Testnet (Chain ID: 80002)
- **Contract:** `0x9EE623E30Ad75C156099d9309924bd989b8f37c4`
- **Minimum Stake:** 0.001 MATIC
- **Explorer:** [View on PolygonScan](https://amoy.polygonscan.com/address/0x9EE623E30Ad75C156099d9309924bd989b8f37c4)

## 📝 How It Works

1. **Requester** creates a job on-chain with reward
2. **Worker** claims job (stakes 50% of reward)
3. **Worker** downloads script/data from IPFS
4. **Worker** trains model with differential privacy
5. **Worker** uploads model to IPFS
6. **Worker** submits result on-chain
7. **Smart contract** pays worker (reward + returned stake)

## 🛠️ Development

**Run Tests:**
```bash
cd node-client
python verify_system.py      # System verification
python blockchain_client.py  # Blockchain test
python test_networks.py      # Network connectivity
```

**TypeScript Check:**
```bash
cd web
npx tsc --noEmit
```

---

<div align="center">
Built for decentralized ML computation 🧠⛓️
</div>
