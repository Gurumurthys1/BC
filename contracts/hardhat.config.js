require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    compilers: [
      {
        version: "0.8.20",
        settings: {
          optimizer: {
            enabled: true,
            runs: 200
          },
          viaIR: true
        }
      },
      {
        version: "0.8.17",
        settings: {
          optimizer: {
            enabled: true,
            runs: 200
          }
        }
      }
    ]
  },
  
  networks: {
    // ═══════════════════════════════════════════════════════════════════════
    // SHARDEUM EVM TESTNET - Primary Settlement Layer
    // Faucet: https://faucet.shardeum.org/
    // ═══════════════════════════════════════════════════════════════════════
    shardeum: {
      url: process.env.SHARDEUM_RPC_URL || "https://api-mezame.shardeum.org",
      chainId: 8119,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: "auto",
      timeout: 60000,
      confirmations: 2
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // INCO RIVEST TESTNET - Confidential Computing with FHE
    // Faucet: https://faucet.rivest.inco.org/
    // Gateway: https://gateway.rivest.inco.org
    // ═══════════════════════════════════════════════════════════════════════
    inco: {
      url: process.env.INCO_RPC_URL || "https://validator.rivest.inco.org",
      chainId: 21097,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: "auto",
      timeout: 120000 // FHE operations need longer timeout
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // POLYGON AMOY TESTNET - Fallback/Development
    // Faucet: https://faucet.polygon.technology/
    // ═══════════════════════════════════════════════════════════════════════
    polygonAmoy: {
      url: process.env.POLYGON_RPC_URL || "https://polygon-amoy-bor-rpc.publicnode.com",
      chainId: 80002,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: "auto",
      timeout: 60000
    },
    
    // Local development
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337
    },
    
    hardhat: {
      chainId: 31337,
      mining: {
        auto: true,
        interval: 0
      }
    }
  },
  
  // Etherscan verification
  etherscan: {
    apiKey: {
      polygonAmoy: process.env.POLYGONSCAN_API_KEY || "",
    },
    customChains: [
      {
        network: "polygonAmoy",
        chainId: 80002,
        urls: {
          apiURL: "https://api-amoy.polygonscan.com/api",
          browserURL: "https://amoy.polygonscan.com"
        }
      },
      {
        network: "shardeum",
        chainId: 8119,
        urls: {
          apiURL: "https://explorer-mezame.shardeum.org/api",
          browserURL: "https://explorer-mezame.shardeum.org"
        }
      },
      {
        network: "inco",
        chainId: 21097,
        urls: {
          apiURL: "https://explorer.rivest.inco.org/api",
          browserURL: "https://explorer.rivest.inco.org"
        }
      }
    ]
  },
  
  paths: {
    sources: "./src",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  }
};
