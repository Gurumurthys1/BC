// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

/**
 * @title OblivionManager - Simplified
 * @dev Decentralized ML Training Marketplace - Fully On-Chain
 * @notice All job coordination on-chain, IPFS for file storage
 */
contract OblivionManager {
    address public owner;
    address public verifier;
    
    // Reentrancy guard
    uint256 private constant NOT_ENTERED = 1;
    uint256 private constant ENTERED = 2;
    uint256 private _status;

    uint256 public constant TRAINING_TIMEOUT = 24 hours;
    uint256 public constant MIN_STAKE = 0.001 ether;

    enum JobStatus { Pending, Processing, Completed, Cancelled, Slashed }

    struct Job {
        address requester;
        address worker;
        uint256 reward;
        uint256 stake;
        uint256 createdAt;
        uint256 claimedAt;
        JobStatus status;
        string scriptHash;
        string dataHash;
        string modelHash;
    }

    struct Worker {
        uint256 stake;
        uint256 completedJobs;
        uint256 reputation;
        bool isActive;
        string nodeId;
    }

    Job[] public jobs;
    mapping(address => Worker) public workers;
    address[] public workerList;
    
    event JobCreated(uint256 indexed jobId, address indexed requester, uint256 reward, string scriptHash, string dataHash);
    event JobClaimed(uint256 indexed jobId, address indexed worker);
    event JobCompleted(uint256 indexed jobId, address indexed worker, string modelHash);
    event JobCancelled(uint256 indexed jobId);
    event WorkerRegistered(address indexed worker, string nodeId, uint256 stake);
    event StakeChanged(address indexed worker, uint256 newStake);

    constructor(address _verifier) {
        owner = msg.sender;
        verifier = _verifier;
        _status = NOT_ENTERED;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier nonReentrant() {
        require(_status != ENTERED, "Reentrant");
        _status = ENTERED;
        _;
        _status = NOT_ENTERED;
    }

    modifier onlyActiveWorker() {
        require(workers[msg.sender].isActive, "Not active worker");
        _;
    }

    // ============ Worker Functions ============

    function registerWorker(string calldata _nodeId) external payable nonReentrant {
        require(msg.value >= MIN_STAKE, "Min stake required");
        require(!workers[msg.sender].isActive, "Already registered");
        
        workers[msg.sender] = Worker({
            stake: msg.value,
            completedJobs: 0,
            reputation: 100,
            isActive: true,
            nodeId: _nodeId
        });
        workerList.push(msg.sender);
        
        emit WorkerRegistered(msg.sender, _nodeId, msg.value);
    }

    function depositStake() external payable nonReentrant onlyActiveWorker {
        require(msg.value > 0, "Zero deposit");
        workers[msg.sender].stake += msg.value;
        emit StakeChanged(msg.sender, workers[msg.sender].stake);
    }

    function withdrawStake(uint256 amount) external nonReentrant onlyActiveWorker {
        Worker storage w = workers[msg.sender];
        require(w.stake >= amount, "Insufficient stake");
        require(w.stake - amount >= MIN_STAKE, "Below min stake");
        
        w.stake -= amount;
        payable(msg.sender).transfer(amount);
        emit StakeChanged(msg.sender, w.stake);
    }

    // ============ Job Functions ============

    function createJob(string calldata _scriptHash, string calldata _dataHash) external payable nonReentrant {
        require(msg.value > 0, "Reward required");
        
        jobs.push(Job({
            requester: msg.sender,
            worker: address(0),
            reward: msg.value,
            stake: 0,
            createdAt: block.timestamp,
            claimedAt: 0,
            status: JobStatus.Pending,
            scriptHash: _scriptHash,
            dataHash: _dataHash,
            modelHash: ""
        }));
        
        emit JobCreated(jobs.length - 1, msg.sender, msg.value, _scriptHash, _dataHash);
    }

    function claimJob(uint256 _jobId) external nonReentrant onlyActiveWorker {
        require(_jobId < jobs.length, "Invalid job");
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Pending, "Not pending");
        require(msg.sender != job.requester, "Own job");
        
        uint256 requiredStake = job.reward / 2;
        Worker storage w = workers[msg.sender];
        require(w.stake >= requiredStake, "Insufficient stake");
        
        w.stake -= requiredStake;
        job.worker = msg.sender;
        job.stake = requiredStake;
        job.status = JobStatus.Processing;
        job.claimedAt = block.timestamp;
        
        emit JobClaimed(_jobId, msg.sender);
    }

    function submitResult(uint256 _jobId, string calldata _modelHash) external nonReentrant onlyActiveWorker {
        require(_jobId < jobs.length, "Invalid job");
        Job storage job = jobs[_jobId];
        require(job.worker == msg.sender, "Not your job");
        require(job.status == JobStatus.Processing, "Not processing");
        
        job.status = JobStatus.Completed;
        job.modelHash = _modelHash;
        
        Worker storage w = workers[msg.sender];
        w.completedJobs += 1;
        w.reputation += 10;
        
        // Pay worker (reward + returned stake)
        uint256 payout = job.reward + job.stake;
        payable(msg.sender).transfer(payout);
        
        emit JobCompleted(_jobId, msg.sender, _modelHash);
    }

    function cancelJob(uint256 _jobId) external nonReentrant {
        require(_jobId < jobs.length, "Invalid job");
        Job storage job = jobs[_jobId];
        require(msg.sender == job.requester, "Not requester");
        require(job.status == JobStatus.Pending, "Not pending");
        
        job.status = JobStatus.Cancelled;
        payable(msg.sender).transfer(job.reward);
        
        emit JobCancelled(_jobId);
    }

    // ============ View Functions ============

    function getJobCount() external view returns (uint256) {
        return jobs.length;
    }

    function getJob(uint256 _jobId) external view returns (
        address requester,
        address worker,
        uint256 reward,
        uint256 status,
        string memory scriptHash,
        string memory dataHash,
        string memory modelHash,
        uint256 createdAt
    ) {
        require(_jobId < jobs.length, "Invalid job");
        Job storage j = jobs[_jobId];
        return (j.requester, j.worker, j.reward, uint256(j.status), j.scriptHash, j.dataHash, j.modelHash, j.createdAt);
    }

    function getWorker(address _addr) external view returns (
        uint256 stake,
        uint256 completedJobs,
        uint256 reputation,
        bool isActive,
        string memory nodeId
    ) {
        Worker storage w = workers[_addr];
        return (w.stake, w.completedJobs, w.reputation, w.isActive, w.nodeId);
    }

    function getWorkerCount() external view returns (uint256) {
        return workerList.length;
    }

    function getStats() external view returns (
        uint256 totalJobs,
        uint256 pendingJobs,
        uint256 completedJobs,
        uint256 activeWorkers
    ) {
        totalJobs = jobs.length;
        for (uint i = 0; i < jobs.length; i++) {
            if (jobs[i].status == JobStatus.Pending) pendingJobs++;
            else if (jobs[i].status == JobStatus.Completed) completedJobs++;
        }
        for (uint i = 0; i < workerList.length; i++) {
            if (workers[workerList[i]].isActive) activeWorkers++;
        }
    }

    // ============ Admin ============

    function updateVerifier(address _newVerifier) external onlyOwner {
        verifier = _newVerifier;
    }

    receive() external payable {}
}
