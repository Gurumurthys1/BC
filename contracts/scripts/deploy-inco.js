const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║       OBLIVION Deployment to INCO Rivest Testnet           ║");
  console.log("║          Chain ID: 21097 (Confidential Computing)          ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const network = hre.network.name;
  const [deployer] = await hre.ethers.getSigners();
  
  console.log("📋 Deployment Configuration:");
  console.log(`   Network: ${network}`);
  console.log(`   Deployer: ${deployer.address}`);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`   Balance: ${hre.ethers.formatEther(balance)} INCO\n`);

  if (balance === 0n) {
    console.log("❌ ERROR: Deployer has no INCO testnet tokens. Get tokens from faucet:");
    console.log("   https://faucet.rivest.inco.org/");
    process.exit(1);
  }

  // Deploy ConfidentialJobBids contract
  console.log("🔧 Deploying ConfidentialJobBids...");
  console.log("   This contract enables encrypted bidding using FHE\n");
  
  const ConfidentialJobBids = await hre.ethers.getContractFactory("ConfidentialJobBids");
  const confidentialBids = await ConfidentialJobBids.deploy({
    gasLimit: 3000000
  });
  await confidentialBids.waitForDeployment();
  const bidsAddress = await confidentialBids.getAddress();
  console.log(`   ✅ ConfidentialJobBids deployed: ${bidsAddress}`);

  // Save addresses
  const addresses = {
    network: "inco-rivest",
    chainId: 21097,
    deployedAt: new Date().toISOString(),
    contracts: {
      ConfidentialJobBids: bidsAddress
    },
    gateway: "https://gateway.rivest.inco.org",
    explorer: {
      bids: `https://explorer.rivest.inco.org/address/${bidsAddress}`
    }
  };

  const outputPath = path.join(__dirname, "..", "deployed_addresses_inco.json");
  fs.writeFileSync(outputPath, JSON.stringify(addresses, null, 2));
  
  console.log("\n" + "═".repeat(60));
  console.log("🎉 DEPLOYMENT SUCCESSFUL!");
  console.log("═".repeat(60));
  console.log(`\n📄 Contract Address:`);
  console.log(`   ConfidentialJobBids: ${bidsAddress}`);
  console.log(`\n🔗 Explorer Link:`);
  console.log(`   ${addresses.explorer.bids}`);
  console.log(`\n🌐 INCO Gateway:`);
  console.log(`   ${addresses.gateway}`);
  console.log(`\n💾 Addresses saved to: ${outputPath}`);
  console.log("═".repeat(60));

  // Update main config file
  console.log("\n📝 Updating configuration files...");
  await updateConfigFiles(bidsAddress);
}

async function updateConfigFiles(bidsAddress) {
  const mainAddressPath = path.join(__dirname, "..", "deployed_addresses.json");
  let existingAddresses = {};
  
  try {
    if (fs.existsSync(mainAddressPath)) {
      existingAddresses = JSON.parse(fs.readFileSync(mainAddressPath, "utf8"));
    }
  } catch (e) {
    // File doesn't exist or is invalid
  }

  existingAddresses.inco = {
    ConfidentialJobBids: bidsAddress,
    chainId: 21097,
    network: "inco-rivest",
    gateway: "https://gateway.rivest.inco.org"
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
