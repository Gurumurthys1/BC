const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║        OBLIVION Deployment to Polygon Amoy Testnet         ║");
  console.log("║               Chain ID: 80002 (Fallback)                   ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const network = hre.network.name;
  const [deployer] = await hre.ethers.getSigners();
  
  console.log("📋 Deployment Configuration:");
  console.log(`   Network: ${network}`);
  console.log(`   Deployer: ${deployer.address}`);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`   Balance: ${hre.ethers.formatEther(balance)} POL\n`);

  if (balance === 0n) {
    console.log("❌ ERROR: Deployer has no POL. Get testnet POL from faucet:");
    console.log("   https://faucet.polygon.technology/");
    process.exit(1);
  }

  // Step 1: Deploy MockVerifier
  console.log("🔧 Step 1/2: Deploying MockVerifier...");
  const MockVerifier = await hre.ethers.getContractFactory("MockVerifier");
  const mockVerifier = await MockVerifier.deploy();
  await mockVerifier.waitForDeployment();
  const verifierAddress = await mockVerifier.getAddress();
  console.log(`   ✅ MockVerifier deployed: ${verifierAddress}`);

  // Step 2: Deploy OblivionManager
  console.log("\n🔧 Step 2/2: Deploying OblivionManager...");
  const OblivionManager = await hre.ethers.getContractFactory("OblivionManager");
  const oblivionManager = await OblivionManager.deploy(verifierAddress);
  await oblivionManager.waitForDeployment();
  const managerAddress = await oblivionManager.getAddress();
  console.log(`   ✅ OblivionManager deployed: ${managerAddress}`);

  // Save addresses
  const addresses = {
    network: "polygon-amoy",
    chainId: 80002,
    deployedAt: new Date().toISOString(),
    contracts: {
      MockVerifier: verifierAddress,
      OblivionManager: managerAddress
    },
    explorer: {
      verifier: `https://amoy.polygonscan.com/address/${verifierAddress}`,
      manager: `https://amoy.polygonscan.com/address/${managerAddress}`
    }
  };

  const outputPath = path.join(__dirname, "..", "deployed_addresses_polygon.json");
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

  // Verify contracts on Polygonscan
  if (process.env.POLYGONSCAN_API_KEY) {
    console.log("\n🔍 Verifying contracts on Polygonscan...");
    try {
      await hre.run("verify:verify", {
        address: verifierAddress,
        constructorArguments: []
      });
      console.log("   ✅ MockVerifier verified");

      await hre.run("verify:verify", {
        address: managerAddress,
        constructorArguments: [verifierAddress]
      });
      console.log("   ✅ OblivionManager verified");
    } catch (e) {
      console.log(`   ⚠️  Verification skipped: ${e.message}`);
    }
  }

  // Update main config file
  console.log("\n📝 Updating configuration files...");
  await updateConfigFiles(managerAddress, verifierAddress);
}

async function updateConfigFiles(managerAddress, verifierAddress) {
  const mainAddressPath = path.join(__dirname, "..", "deployed_addresses.json");
  let existingAddresses = {};
  
  try {
    if (fs.existsSync(mainAddressPath)) {
      existingAddresses = JSON.parse(fs.readFileSync(mainAddressPath, "utf8"));
    }
  } catch (e) {
    // File doesn't exist or is invalid
  }

  existingAddresses.polygon = {
    MockVerifier: verifierAddress,
    OblivionManager: managerAddress,
    chainId: 80002,
    network: "polygon-amoy"
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
