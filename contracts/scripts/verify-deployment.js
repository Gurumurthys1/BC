const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

/**
 * Verify contract deployments and test basic functionality
 */
async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║         OBLIVION Contract Verification Suite               ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const network = hre.network.name;
  console.log(`Network: ${network}\n`);

  // Load deployed addresses
  let addresses = {};
  const addressFiles = [
    "deployed_addresses_shardeum.json",
    "deployed_addresses_inco.json",
    "deployed_addresses_polygon.json",
    "deployed_addresses.json"
  ];

  for (const file of addressFiles) {
    const filePath = path.join(__dirname, "..", file);
    if (fs.existsSync(filePath)) {
      const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
      addresses = { ...addresses, ...data };
      console.log(`📄 Loaded ${file}`);
    }
  }

  console.log("\n" + "─".repeat(60));
  console.log("1. CONTRACT VERIFICATION");
  console.log("─".repeat(60));

  // Verify contracts based on network
  if (network === "shardeum" || network === "localhost" || network === "hardhat") {
    await verifyShardeum(addresses);
  }

  if (network === "inco") {
    await verifyInco(addresses);
  }

  if (network === "polygonAmoy") {
    await verifyPolygon(addresses);
  }

  console.log("\n" + "─".repeat(60));
  console.log("2. FUNCTIONALITY TEST");
  console.log("─".repeat(60));

  if (network === "hardhat" || network === "localhost") {
    await testFunctionality();
  } else {
    console.log("   ⚠️  Skipping functionality tests on live network");
    console.log("   Run on hardhat network: npx hardhat run scripts/verify-deployment.js");
  }

  console.log("\n" + "═".repeat(60));
  console.log("✅ Verification Complete");
  console.log("═".repeat(60));
}

async function verifyShardeum(addresses) {
  const shardeumAddresses = addresses.shardeum || addresses.contracts || {};
  
  console.log("\n📍 Shardeum Contracts:");
  
  if (shardeumAddresses.MockVerifier) {
    const code = await hre.ethers.provider.getCode(shardeumAddresses.MockVerifier);
    const deployed = code.length > 2;
    console.log(`   MockVerifier: ${shardeumAddresses.MockVerifier}`);
    console.log(`   Status: ${deployed ? "✅ Deployed" : "❌ Not Found"}`);
  } else {
    console.log("   MockVerifier: ⚠️  Not configured");
  }

  if (shardeumAddresses.OblivionManager) {
    const code = await hre.ethers.provider.getCode(shardeumAddresses.OblivionManager);
    const deployed = code.length > 2;
    console.log(`   OblivionManager: ${shardeumAddresses.OblivionManager}`);
    console.log(`   Status: ${deployed ? "✅ Deployed" : "❌ Not Found"}`);
  } else {
    console.log("   OblivionManager: ⚠️  Not configured");
  }
}

async function verifyInco(addresses) {
  const incoAddresses = addresses.inco || {};
  
  console.log("\n📍 INCO Contracts:");
  
  if (incoAddresses.ConfidentialJobBids) {
    const code = await hre.ethers.provider.getCode(incoAddresses.ConfidentialJobBids);
    const deployed = code.length > 2;
    console.log(`   ConfidentialJobBids: ${incoAddresses.ConfidentialJobBids}`);
    console.log(`   Status: ${deployed ? "✅ Deployed" : "❌ Not Found"}`);
  } else {
    console.log("   ConfidentialJobBids: ⚠️  Not configured");
  }
}

async function verifyPolygon(addresses) {
  const polygonAddresses = addresses.polygon || {};
  
  console.log("\n📍 Polygon Amoy Contracts:");
  
  const defaultManager = "0x2681849aB3d8E470Dedc08b1a4CED92493886501";
  const managerAddress = polygonAddresses.OblivionManager || defaultManager;
  
  const code = await hre.ethers.provider.getCode(managerAddress);
  const deployed = code.length > 2;
  console.log(`   OblivionManager: ${managerAddress}`);
  console.log(`   Status: ${deployed ? "✅ Deployed" : "❌ Not Found"}`);
}

async function testFunctionality() {
  const [deployer, user] = await hre.ethers.getSigners();
  
  console.log("\n🧪 Running Functionality Tests...\n");
  
  // Deploy fresh contracts for testing
  console.log("   Deploying test contracts...");
  
  const MockVerifier = await hre.ethers.getContractFactory("MockVerifier");
  const mockVerifier = await MockVerifier.deploy();
  await mockVerifier.waitForDeployment();
  console.log(`   ✅ MockVerifier: ${await mockVerifier.getAddress()}`);

  const OblivionManager = await hre.ethers.getContractFactory("OblivionManager");
  const manager = await OblivionManager.deploy(await mockVerifier.getAddress());
  await manager.waitForDeployment();
  console.log(`   ✅ OblivionManager: ${await manager.getAddress()}`);

  // Test job creation
  console.log("\n   Testing job creation...");
  const tx = await manager.createJob(
    0, // JobType.Inference
    "QmModelHash123",
    "QmDataHash456",
    { value: hre.ethers.parseEther("0.1") }
  );
  await tx.wait();
  console.log("   ✅ Job created successfully");

  // Test job count
  const jobCount = await manager.getJobCount();
  console.log(`   ✅ Job count: ${jobCount}`);

  // Test stake deposit
  console.log("\n   Testing stake management...");
  const stakeTx = await manager.connect(user).depositStake({
    value: hre.ethers.parseEther("0.1")
  });
  await stakeTx.wait();
  const userStake = await manager.workerStakes(user.address);
  console.log(`   ✅ Stake deposited: ${hre.ethers.formatEther(userStake)} ETH`);

  // Test job claim
  console.log("\n   Testing job claim...");
  const claimTx = await manager.connect(user).claimJob(0);
  await claimTx.wait();
  const job = await manager.getJob(0);
  console.log(`   ✅ Job claimed by: ${job.provider}`);
  console.log(`   ✅ Job status: ${["Pending", "Processing", "Completed", "Cancelled", "Slashed", "Expired"][job.status]}`);

  console.log("\n   All functionality tests passed! ✅");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Verification failed:", error);
    process.exit(1);
  });
