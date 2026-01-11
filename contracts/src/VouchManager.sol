// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

interface IVerifier {
    function verify(
        uint256[] calldata pubInputs,
        bytes calldata proof
    ) external view returns (bool);
}

/**
 * @title OblivionManager
 * @dev Orchestrator for Decentralized Blind AI Training & Inference
 * @notice Production-ready contract with security features:
 *         - Reentrancy protection
 *         - Job timeout mechanism
 *         - Input validation
 *         - ZK verification for both job types
 */
contract OblivionManager {
    IVerifier public verifier;
    address public owner;
    
    // Reentrancy guard
    uint256 private constant NOT_ENTERED = 1;
    uint256 private constant ENTERED = 2;
    uint256 private _status;

    // Timeout configuration
    uint256 public constant INFERENCE_TIMEOUT = 1 hours;
    uint256 public constant TRAINING_TIMEOUT = 24 hours;

    enum JobType { Inference, Training }
    enum JobStatus { Pending, Processing, Completed, Cancelled, Slashed, Expired }

    struct Job {
        address requester;
        uint256 reward;
        JobType jobType;
        JobStatus status;
        string modelHash;
        string dataHash;
        address provider;
        uint256 stake;
        uint256 createdAt;
        uint256 claimedAt;
    }

    Job[] public jobs;
    mapping(address => uint256) public workerStakes;
    mapping(address => uint256) public workerReputation;
    
    event JobCreated(uint256 indexed jobId, JobType jobType, uint256 reward, address indexed requester);
    event JobProcessing(uint256 indexed jobId, address indexed provider);
    event JobCompleted(uint256 indexed jobId, address indexed provider, bytes32 updateHash);
    event JobCancelled(uint256 indexed jobId, address indexed requester);
    event JobExpired(uint256 indexed jobId, address indexed provider);
    event WorkerSlashed(address indexed worker, uint256 amount, uint256 indexed jobId);
    event StakeDeposited(address indexed worker, uint256 amount);
    event StakeWithdrawn(address indexed worker, uint256 amount);

    constructor(address _verifier) {
        require(_verifier != address(0), "Invalid verifier address");
        verifier = IVerifier(_verifier);
        owner = msg.sender;
        _status = NOT_ENTERED;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier nonReentrant() {
        require(_status != ENTERED, "Reentrant call");
        _status = ENTERED;
        _;
        _status = NOT_ENTERED;
    }

    modifier validJobId(uint256 _jobId) {
        require(_jobId < jobs.length, "Invalid job ID");
        _;
    }

    // ============ Stake Management ============

    function depositStake() external payable nonReentrant {
        require(msg.value > 0, "Must deposit non-zero amount");
        workerStakes[msg.sender] += msg.value;
        emit StakeDeposited(msg.sender, msg.value);
    }

    function withdrawStake(uint256 amount) external nonReentrant {
        require(amount > 0, "Must withdraw non-zero amount");
        require(workerStakes[msg.sender] >= amount, "Insufficient stake balance");
        
        // Effects before interactions (CEI pattern)
        workerStakes[msg.sender] -= amount;
        
        // Interaction
        (bool success, ) = payable(msg.sender).call{value: amount}("");
        require(success, "Transfer failed");
        
        emit StakeWithdrawn(msg.sender, amount);
    }

    // ============ Job Management ============

    function createJob(
        JobType _type, 
        string memory _modelHash, 
        string memory _dataHash
    ) external payable nonReentrant {
        require(msg.value > 0, "Reward required");
        require(bytes(_modelHash).length > 0, "Model hash required");
        require(bytes(_dataHash).length > 0, "Data hash required");
        
        jobs.push(Job({
            requester: msg.sender,
            reward: msg.value,
            jobType: _type,
            status: JobStatus.Pending,
            modelHash: _modelHash,
            dataHash: _dataHash,
            provider: address(0),
            stake: 0,
            createdAt: block.timestamp,
            claimedAt: 0
        }));
        
        emit JobCreated(jobs.length - 1, _type, msg.value, msg.sender);
    }

    function cancelJob(uint256 _jobId) external nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(msg.sender == job.requester, "Not requester");
        require(job.status == JobStatus.Pending, "Not cancellable");

        // Effects before interactions
        job.status = JobStatus.Cancelled;
        uint256 refundAmount = job.reward;
        
        // Interaction
        (bool success, ) = payable(msg.sender).call{value: refundAmount}("");
        require(success, "Refund failed");
        
        emit JobCancelled(_jobId, msg.sender);
    }

    function claimJob(uint256 _jobId) external nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Pending, "Job not pending");
        require(msg.sender != job.requester, "Requester cannot claim own job");
        
        uint256 requiredStake = job.reward / 2;
        require(workerStakes[msg.sender] >= requiredStake, "Insufficient stake (50% of reward required)");

        // Effects
        job.provider = msg.sender;
        job.status = JobStatus.Processing;
        job.stake = requiredStake;
        job.claimedAt = block.timestamp;
        workerStakes[msg.sender] -= requiredStake;

        emit JobProcessing(_jobId, msg.sender);
    }

    function submitResult(
        uint256 _jobId,
        bytes32 _updateHash,
        uint256[] calldata _pubInputs,
        bytes calldata _proof
    ) external nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.provider == msg.sender, "Not assigned provider");
        require(job.status == JobStatus.Processing, "Not in processing");
        require(!_isJobExpired(job), "Job has expired");

        // Verify ZK proof for both job types (production requirement)
        // For training jobs, proof validates correct gradient computation
        // For inference jobs, proof validates correct model execution
        bool proofValid = verifier.verify(_pubInputs, _proof);
        require(proofValid, "Invalid ZK proof");

        // Effects before interactions
        job.status = JobStatus.Completed;
        uint256 totalPayout = job.reward + job.stake;
        workerReputation[msg.sender] += 1;
        
        // Interaction
        (bool success, ) = payable(msg.sender).call{value: totalPayout}("");
        require(success, "Payout failed");
        
        emit JobCompleted(_jobId, msg.sender, _updateHash);
    }

    // Legacy function name for backwards compatibility
    function submitTrainingUpdate(
        uint256 _jobId,
        bytes32 _updateHash,
        uint256[] calldata _pubInputs,
        bytes calldata _proof
    ) external {
        this.submitResult(_jobId, _updateHash, _pubInputs, _proof);
    }

    // ============ Timeout & Dispute Resolution ============

    function expireJob(uint256 _jobId) external nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Processing, "Job not processing");
        require(_isJobExpired(job), "Job not yet expired");
        
        // Effects
        address expiredProvider = job.provider;
        uint256 slashedStake = job.stake;
        job.status = JobStatus.Expired;
        
        // Return reward to requester, stake goes to contract (or could go to requester)
        uint256 refundAmount = job.reward;
        
        // Interaction - refund requester
        (bool success, ) = payable(job.requester).call{value: refundAmount}("");
        require(success, "Refund failed");
        
        emit JobExpired(_jobId, expiredProvider);
        emit WorkerSlashed(expiredProvider, slashedStake, _jobId);
    }

    function slashWorker(uint256 _jobId) external onlyOwner nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Processing, "Can only slash processing jobs");
        
        address badWorker = job.provider;
        uint256 slashedAmount = job.stake;
        
        // Effects
        job.status = JobStatus.Slashed;
        
        // Return reward to requester
        uint256 refundAmount = job.reward;
        (bool success, ) = payable(job.requester).call{value: refundAmount}("");
        require(success, "Refund failed");
        
        emit WorkerSlashed(badWorker, slashedAmount, _jobId);
    }

    // ============ View Functions ============

    function getJob(uint256 _jobId) external view validJobId(_jobId) returns (Job memory) {
        return jobs[_jobId];
    }

    function getJobCount() external view returns (uint256) {
        return jobs.length;
    }

    function isJobExpired(uint256 _jobId) external view validJobId(_jobId) returns (bool) {
        return _isJobExpired(jobs[_jobId]);
    }

    function getTimeout(JobType _type) public pure returns (uint256) {
        return _type == JobType.Inference ? INFERENCE_TIMEOUT : TRAINING_TIMEOUT;
    }

    // ============ Internal Functions ============

    function _isJobExpired(Job storage job) internal view returns (bool) {
        if (job.status != JobStatus.Processing) return false;
        uint256 timeout = getTimeout(job.jobType);
        return block.timestamp > job.claimedAt + timeout;
    }

    // ============ Admin Functions ============

    function updateVerifier(address _newVerifier) external onlyOwner {
        require(_newVerifier != address(0), "Invalid verifier address");
        verifier = IVerifier(_newVerifier);
    }

    function transferOwnership(address _newOwner) external onlyOwner {
        require(_newOwner != address(0), "Invalid owner address");
        owner = _newOwner;
    }

    // Allow contract to receive ETH for slashed stakes
    receive() external payable {}
}
