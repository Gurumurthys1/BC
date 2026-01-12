const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║        OBLIVION Deployment to Shardeum EVM Testnet         ║");
  console.log("║              Chain ID: 8119 (Mezame Testnet)               ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const network = hre.network.name;
  const [deployer] = await hre.ethers.getSigners();
  
  console.log("📋 Deployment Configuration:");
  console.log(`   Network: ${network}`);
  console.log(`   Deployer: ${deployer.address}`);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`   Balance: ${hre.ethers.formatEther(balance)} SHM\n`);

  if (balance === 0n) {
    console.log("❌ ERROR: Deployer has no SHM. Get testnet SHM from faucet:");
    console.log("   https://faucet.shardeum.org/");
    process.exit(1);
  }

  // Step 1: Deploy MockVerifier
  console.log("🔧 Step 1/2: Deploying MockVerifier...");
  const MockVerifier = await hre.ethers.getContractFactory("MockVerifier");
  const mockVerifier = await MockVerifier.deploy({
    gasLimit: 2000000
  });
  await mockVerifier.waitForDeployment();
  const verifierAddress = await mockVerifier.getAddress();
  console.log(`   ✅ MockVerifier deployed: ${verifierAddress}`);

  // Step 2: Deploy OblivionManager
  console.log("\n🔧 Step 2/2: Deploying OblivionManager...");
  const OblivionManager = await hre.ethers.getContractFactory("OblivionManager");
  const oblivionManager = await OblivionManager.deploy(verifierAddress, {
    gasLimit: 5000000
  });
  await oblivionManager.waitForDeployment();
  const managerAddress = await oblivionManager.getAddress();
  console.log(`   ✅ OblivionManager deployed: ${managerAddress}`);

  // Save addresses
  const addresses = {
    network: "shardeum",
    chainId: 8119,
    deployedAt: new Date().toISOString(),
    contracts: {
      MockVerifier: verifierAddress,
      OblivionManager: managerAddress
    },
    explorer: {
      verifier: `https://explorer-mezame.shardeum.org/address/${verifierAddress}`,
      manager: `https://explorer-mezame.shardeum.org/address/${managerAddress}`
    }
  };

  const outputPath = path.join(__dirname, "..", "deployed_addresses_shardeum.json");
  fs.writeFileSync(outputPath, JSON.stringify(addresses, null, 2));
  
  console.log("\n" + "═".repeat(60));
  console.log("🎉 DEPLOYMENT SUCCESSFUL!");
  console.log("═".repeat(60));
  console.log(`\n📄 Contract Addresses:`);
  console.log(`   MockVerifier:    ${verifierAddress}`);
  console.log(`   OblivionManager: ${managerAddress}`);
  console.log(`\n🔗 Explorer Links:`);
  console.log(`   ${addresses.explorer.verifier}`);
  console.log(`   ${addresses.explorer.manager}`);
  console.log(`\n💾 Addresses saved to: ${outputPath}`);
  console.log("═".repeat(60));

  // Update main config file with new address
  console.log("\n📝 Updating configuration files...");
  await updateConfigFiles(managerAddress, verifierAddress);
}

async function updateConfigFiles(managerAddress, verifierAddress) {
  // Update deployed_addresses.json
  const mainAddressPath = path.join(__dirname, "..", "deployed_addresses.json");
  let existingAddresses = {};
  
  try {
    if (fs.existsSync(mainAddressPath)) {
      existingAddresses = JSON.parse(fs.readFileSync(mainAddressPath, "utf8"));
    }
  } catch (e) {
    // File doesn't exist or is invalid
  }

  existingAddresses.shardeum = {
    MockVerifier: verifierAddress,
    OblivionManager: managerAddress,
    chainId: 8119,
    network: "shardeum"
  };

  fs.writeFileSync(mainAddressPath, JSON.stringify(existingAddresses, null, 2));
  console.log("   ✅ Updated deployed_addresses.json");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });
