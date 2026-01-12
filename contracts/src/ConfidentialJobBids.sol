// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {euint256, ebool, e} from "@inco/lightning/Lib.sol";

/**
 * @title ConfidentialJobBids
 * @notice Stores encrypted job bids for the Oblivion ML marketplace
 * @dev Uses INCO's FHE to keep bid amounts confidential until reveal
 * 
 * Integration with Shardeum:
 * - Job creator creates job on Shardeum (OblivionManager)
 * - Then sets encrypted bid here using the Shardeum job ID
 * - After job completion, bid can be revealed via attested decrypt
 */
contract ConfidentialJobBids {
    using e for *;
    
    // ============ State Variables ============
    
    /// @notice Encrypted bid amount per Shardeum job ID
    mapping(uint256 => euint256) public encryptedBids;
    
    /// @notice Job creator address per job
    mapping(uint256 => address) public jobCreators;
    
    /// @notice Whether bid has been revealed
    mapping(uint256 => bool) public revealed;
    
    /// @notice Revealed bid values (only set after reveal)
    mapping(uint256 => uint256) public revealedBids;
    
    /// @notice Whether job is marked as completed (for access control)
    mapping(uint256 => bool) public jobCompleted;
    
    /// @notice Assigned worker per job (can decrypt after completion)
    mapping(uint256 => address) public assignedWorkers;
    
    // ============ Events ============
    
    event BidSet(uint256 indexed shardeumJobId, address indexed creator);
    event BidRevealed(uint256 indexed shardeumJobId, uint256 bid);
    event JobMarkedComplete(uint256 indexed shardeumJobId, address indexed worker);
    event WorkerAssigned(uint256 indexed shardeumJobId, address indexed worker);
    
    // ============ Errors ============
    
    error BidAlreadySet();
    error NotJobCreator();
    error AlreadyRevealed();
    error JobNotCompleted();
    error InvalidCiphertext();
    
    // ============ External Functions ============
    
    /**
     * @notice Store encrypted bid for a Shardeum job
     * @param shardeumJobId The job ID from Shardeum OblivionManager contract
     * @param bidCiphertext Encrypted bid amount from INCO JS SDK
     * @dev Call this right after creating job on Shardeum
     */
    function setBid(uint256 shardeumJobId, bytes calldata bidCiphertext) external {
        if (jobCreators[shardeumJobId] != address(0)) {
            revert BidAlreadySet();
        }
        
        // Convert ciphertext to encrypted uint256
        euint256 encryptedBid = bidCiphertext.newEuint256(msg.sender);
        
        // Store encrypted bid
        encryptedBids[shardeumJobId] = encryptedBid;
        jobCreators[shardeumJobId] = msg.sender;
        
        // Set access control
        // - Creator can always view
        encryptedBid.allow(msg.sender);
        // - Contract can operate on it
        encryptedBid.allowThis();
        
        emit BidSet(shardeumJobId, msg.sender);
    }
    
    /**
     * @notice Assign a worker to a job (for future decrypt access)
     * @param shardeumJobId The Shardeum job ID
     * @param worker The worker address
     * @dev Call this when job is claimed on Shardeum
     */
    function assignWorker(uint256 shardeumJobId, address worker) external {
        if (msg.sender != jobCreators[shardeumJobId]) {
            revert NotJobCreator();
        }
        
        assignedWorkers[shardeumJobId] = worker;
        
        emit WorkerAssigned(shardeumJobId, worker);
    }
    
    /**
     * @notice Mark job as completed (enables reveal)
     * @param shardeumJobId The Shardeum job ID
     * @dev In production, this would verify completion on Shardeum via cross-chain message
     */
    function markJobCompleted(uint256 shardeumJobId) external {
        // For hackathon: creator can mark complete
        // Production: would verify via Shardeum state or oracle
        if (msg.sender != jobCreators[shardeumJobId]) {
            revert NotJobCreator();
        }
        
        jobCompleted[shardeumJobId] = true;
        
        // Grant decrypt access to assigned worker
        address worker = assignedWorkers[shardeumJobId];
        if (worker != address(0)) {
            encryptedBids[shardeumJobId].allow(worker);
        }
        
        emit JobMarkedComplete(shardeumJobId, worker);
    }
    
    /**
     * @notice Reveal bid (make it publicly accessible)
     * @param shardeumJobId The Shardeum job ID
     * @dev Call e.reveal() to make value accessible via attested decrypt
     */
    function revealBid(uint256 shardeumJobId) external {
        if (msg.sender != jobCreators[shardeumJobId]) {
            revert NotJobCreator();
        }
        if (revealed[shardeumJobId]) {
            revert AlreadyRevealed();
        }
        if (!jobCompleted[shardeumJobId]) {
            revert JobNotCompleted();
        }
        
        // Mark for public reveal
        encryptedBids[shardeumJobId].reveal();
        revealed[shardeumJobId] = true;
        
        emit BidRevealed(shardeumJobId, 0); // Actual value retrieved via attestation
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Check if a bid exists for a job
     * @param shardeumJobId The Shardeum job ID
     * @return True if bid was set
     */
    function hasBid(uint256 shardeumJobId) external view returns (bool) {
        return jobCreators[shardeumJobId] != address(0);
    }
    
    /**
     * @notice Get bid handle for attested decrypt
     * @param shardeumJobId The Shardeum job ID
     * @return The encrypted bid handle
     * @dev Use this with INCO JS SDK attestedDecrypt()
     */
    function getBidHandle(uint256 shardeumJobId) external view returns (euint256) {
        return encryptedBids[shardeumJobId];
    }
    
    /**
     * @notice Check if caller can decrypt the bid
     * @param shardeumJobId The Shardeum job ID
     * @param account The account to check
     * @return True if account has decrypt access
     */
    function canDecrypt(uint256 shardeumJobId, address account) external view returns (bool) {
        euint256 bid = encryptedBids[shardeumJobId];
        return account.isAllowed(bid);
    }
    
    /**
     * @notice Get job info
     * @param shardeumJobId The Shardeum job ID
     */
    function getJobInfo(uint256 shardeumJobId) external view returns (
        address creator,
        address worker,
        bool isCompleted,
        bool isRevealed
    ) {
        return (
            jobCreators[shardeumJobId],
            assignedWorkers[shardeumJobId],
            jobCompleted[shardeumJobId],
            revealed[shardeumJobId]
        );
    }
}
