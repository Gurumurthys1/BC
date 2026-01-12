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
 * @dev Fully Decentralized ML Training Marketplace - No External Database Required
 * @notice All job coordination happens on-chain with IPFS for file storage
 * 
 * Architecture:
 * - Job lifecycle managed entirely on-chain
 * - Worker registry with reputation tracking
 * - Fair distribution algorithm (fewer jobs = higher priority)
 * - Events for real-time frontend updates
 * - IPFS hashes stored for models, datasets, results
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
    uint256 public constant MIN_STAKE = 0.001 ether;

    enum JobType { Inference, Training }
    enum JobStatus { Pending, Processing, Completed, Cancelled, Slashed, Expired }

    struct Job {
        uint256 id;
        address requester;
        uint256 reward;
        JobType jobType;
        JobStatus status;
        string scriptHash;      // IPFS hash of training script
        string dataHash;        // IPFS hash of dataset
        string modelHash;       // IPFS hash of trained model (set on completion)
        string proofHash;       // IPFS hash of ZK proof
        address worker;
        uint256 stake;
        uint256 createdAt;
        uint256 claimedAt;
        uint256 completedAt;
    }

    struct Worker {
        address addr;
        uint256 stake;
        uint256 reputation;
        uint256 completedJobs;
        uint256 failedJobs;
        uint256 totalEarnings;
        bool isActive;
        uint256 registeredAt;
        string nodeId;          // Unique node identifier
    }

    // Storage
    Job[] public jobs;
    mapping(address => Worker) public workers;
    address[] public workerAddresses;
    mapping(address => uint256[]) public workerJobHistory;
    
    // ============ Events ============
    
    event JobCreated(
        uint256 indexed jobId, 
        address indexed requester, 
        JobType jobType, 
        uint256 reward,
        string scriptHash,
        string dataHash
    );
    
    event JobClaimed(
        uint256 indexed jobId, 
        address indexed worker,
        uint256 claimedAt
    );
    
    event JobCompleted(
        uint256 indexed jobId, 
        address indexed worker, 
        string modelHash,
        string proofHash,
        uint256 completedAt
    );
    
    event JobCancelled(uint256 indexed jobId, address indexed requester);
    event JobExpired(uint256 indexed jobId, address indexed worker);
    event JobSlashed(uint256 indexed jobId, address indexed worker, uint256 slashedAmount);
    
    event WorkerRegistered(address indexed worker, string nodeId, uint256 stake);
    event WorkerDeactivated(address indexed worker);
    event StakeDeposited(address indexed worker, uint256 amount, uint256 totalStake);
    event StakeWithdrawn(address indexed worker, uint256 amount, uint256 remainingStake);
    event RewardPaid(address indexed worker, uint256 indexed jobId, uint256 amount);

    // ============ Constructor ============

    constructor(address _verifier) {
        require(_verifier != address(0), "Invalid verifier address");
        verifier = IVerifier(_verifier);
        owner = msg.sender;
        _status = NOT_ENTERED;
    }

    // ============ Modifiers ============

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

    modifier onlyActiveWorker() {
        require(workers[msg.sender].isActive, "Worker not registered or inactive");
        _;
    }

    // ============ Worker Registration ============

    function registerWorker(string memory _nodeId) external payable nonReentrant {
        require(msg.value >= MIN_STAKE, "Minimum stake required");
        require(!workers[msg.sender].isActive, "Already registered");
        require(bytes(_nodeId).length > 0, "Node ID required");
        
        workers[msg.sender] = Worker({
            addr: msg.sender,
            stake: msg.value,
            reputation: 100,  // Start with base reputation
            completedJobs: 0,
            failedJobs: 0,
            totalEarnings: 0,
            isActive: true,
            registeredAt: block.timestamp,
            nodeId: _nodeId
        });
        
        workerAddresses.push(msg.sender);
        
        emit WorkerRegistered(msg.sender, _nodeId, msg.value);
        emit StakeDeposited(msg.sender, msg.value, msg.value);
    }

    function depositStake() external payable nonReentrant onlyActiveWorker {
        require(msg.value > 0, "Must deposit non-zero amount");
        workers[msg.sender].stake += msg.value;
        emit StakeDeposited(msg.sender, msg.value, workers[msg.sender].stake);
    }

    function withdrawStake(uint256 amount) external nonReentrant onlyActiveWorker {
        require(amount > 0, "Must withdraw non-zero amount");
        Worker storage worker = workers[msg.sender];
        require(worker.stake >= amount, "Insufficient stake balance");
        require(worker.stake - amount >= MIN_STAKE, "Must maintain minimum stake");
        
        worker.stake -= amount;
        
        (bool success, ) = payable(msg.sender).call{value: amount}("");
        require(success, "Transfer failed");
        
        emit StakeWithdrawn(msg.sender, amount, worker.stake);
    }

    function deactivateWorker() external nonReentrant onlyActiveWorker {
        Worker storage worker = workers[msg.sender];
        
        // Check no active jobs
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].worker == msg.sender && jobs[i].status == JobStatus.Processing) {
                revert("Cannot deactivate with active jobs");
            }
        }
        
        uint256 refundAmount = worker.stake;
        worker.stake = 0;
        worker.isActive = false;
        
        (bool success, ) = payable(msg.sender).call{value: refundAmount}("");
        require(success, "Refund failed");
        
        emit WorkerDeactivated(msg.sender);
        emit StakeWithdrawn(msg.sender, refundAmount, 0);
    }

    // ============ Job Management ============

    function createJob(
        JobType _type, 
        string memory _scriptHash, 
        string memory _dataHash
    ) external payable nonReentrant {
        require(msg.value > 0, "Reward required");
        require(bytes(_scriptHash).length > 0, "Script hash required");
        require(bytes(_dataHash).length > 0, "Data hash required");
        
        uint256 jobId = jobs.length;
        
        jobs.push(Job({
            id: jobId,
            requester: msg.sender,
            reward: msg.value,
            jobType: _type,
            status: JobStatus.Pending,
            scriptHash: _scriptHash,
            dataHash: _dataHash,
            modelHash: "",
            proofHash: "",
            worker: address(0),
            stake: 0,
            createdAt: block.timestamp,
            claimedAt: 0,
            completedAt: 0
        }));
        
        emit JobCreated(jobId, msg.sender, _type, msg.value, _scriptHash, _dataHash);
    }

    function cancelJob(uint256 _jobId) external nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(msg.sender == job.requester, "Not requester");
        require(job.status == JobStatus.Pending, "Not cancellable");

        job.status = JobStatus.Cancelled;
        uint256 refundAmount = job.reward;
        
        (bool success, ) = payable(msg.sender).call{value: refundAmount}("");
        require(success, "Refund failed");
        
        emit JobCancelled(_jobId, msg.sender);
    }

    function claimJob(uint256 _jobId) external nonReentrant validJobId(_jobId) onlyActiveWorker {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Pending, "Job not available");
        require(msg.sender != job.requester, "Cannot claim own job");
        
        Worker storage worker = workers[msg.sender];
        uint256 requiredStake = job.reward / 2;
        require(worker.stake >= requiredStake, "Insufficient stake (50% of reward required)");

        // Lock stake
        worker.stake -= requiredStake;
        
        // Update job
        job.worker = msg.sender;
        job.status = JobStatus.Processing;
        job.stake = requiredStake;
        job.claimedAt = block.timestamp;

        emit JobClaimed(_jobId, msg.sender, block.timestamp);
    }

    function submitResult(
        uint256 _jobId,
        string memory _modelHash,
        string memory _proofHash,
        uint256[] calldata _pubInputs,
        bytes calldata _proof
    ) external nonReentrant validJobId(_jobId) onlyActiveWorker {
        Job storage job = jobs[_jobId];
        require(job.worker == msg.sender, "Not assigned worker");
        require(job.status == JobStatus.Processing, "Job not in processing");
        require(!_isJobExpired(job), "Job has expired");
        require(bytes(_modelHash).length > 0, "Model hash required");

        // Verify ZK proof
        bool proofValid = verifier.verify(_pubInputs, _proof);
        require(proofValid, "Invalid ZK proof");

        // Update job
        job.status = JobStatus.Completed;
        job.modelHash = _modelHash;
        job.proofHash = _proofHash;
        job.completedAt = block.timestamp;

        // Update worker stats
        Worker storage worker = workers[msg.sender];
        worker.completedJobs += 1;
        worker.reputation += 10;  // Reputation boost
        
        // Calculate payout (reward + returned stake)
        uint256 totalPayout = job.reward + job.stake;
        worker.totalEarnings += job.reward;
        
        // Record in history
        workerJobHistory[msg.sender].push(_jobId);
        
        // Pay worker
        (bool success, ) = payable(msg.sender).call{value: totalPayout}("");
        require(success, "Payout failed");
        
        emit JobCompleted(_jobId, msg.sender, _modelHash, _proofHash, block.timestamp);
        emit RewardPaid(msg.sender, _jobId, job.reward);
    }

    // Simplified submit for testing (no ZK proof required)
    function submitResultSimple(
        uint256 _jobId,
        string memory _modelHash
    ) external nonReentrant validJobId(_jobId) onlyActiveWorker {
        Job storage job = jobs[_jobId];
        require(job.worker == msg.sender, "Not assigned worker");
        require(job.status == JobStatus.Processing, "Job not in processing");
        require(!_isJobExpired(job), "Job has expired");
        require(bytes(_modelHash).length > 0, "Model hash required");

        // Update job
        job.status = JobStatus.Completed;
        job.modelHash = _modelHash;
        job.completedAt = block.timestamp;

        // Update worker stats
        Worker storage worker = workers[msg.sender];
        worker.completedJobs += 1;
        worker.reputation += 10;
        
        uint256 totalPayout = job.reward + job.stake;
        worker.totalEarnings += job.reward;
        
        workerJobHistory[msg.sender].push(_jobId);
        
        (bool success, ) = payable(msg.sender).call{value: totalPayout}("");
        require(success, "Payout failed");
        
        emit JobCompleted(_jobId, msg.sender, _modelHash, "", block.timestamp);
        emit RewardPaid(msg.sender, _jobId, job.reward);
    }

    // ============ Timeout & Slashing ============

    function expireJob(uint256 _jobId) external nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Processing, "Job not processing");
        require(_isJobExpired(job), "Job not yet expired");
        
        address expiredWorker = job.worker;
        uint256 slashedStake = job.stake;
        
        // Update job
        job.status = JobStatus.Expired;
        
        // Update worker stats
        Worker storage worker = workers[expiredWorker];
        worker.failedJobs += 1;
        if (worker.reputation > 20) {
            worker.reputation -= 20;
        }
        
        // Refund requester
        (bool success, ) = payable(job.requester).call{value: job.reward}("");
        require(success, "Refund failed");
        
        emit JobExpired(_jobId, expiredWorker);
        emit JobSlashed(_jobId, expiredWorker, slashedStake);
    }

    function slashWorker(uint256 _jobId) external onlyOwner nonReentrant validJobId(_jobId) {
        Job storage job = jobs[_jobId];
        require(job.status == JobStatus.Processing, "Can only slash processing jobs");
        
        address badWorker = job.worker;
        uint256 slashedAmount = job.stake;
        
        job.status = JobStatus.Slashed;
        
        Worker storage worker = workers[badWorker];
        worker.failedJobs += 1;
        if (worker.reputation > 30) {
            worker.reputation -= 30;
        }
        
        (bool success, ) = payable(job.requester).call{value: job.reward}("");
        require(success, "Refund failed");
        
        emit JobSlashed(_jobId, badWorker, slashedAmount);
    }

    // ============ View Functions - Job Queries ============

    function getJob(uint256 _jobId) external view validJobId(_jobId) returns (Job memory) {
        return jobs[_jobId];
    }

    function getJobCount() external view returns (uint256) {
        return jobs.length;
    }

    function getPendingJobs() external view returns (Job[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == JobStatus.Pending) {
                count++;
            }
        }
        
        Job[] memory pendingJobs = new Job[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == JobStatus.Pending) {
                pendingJobs[index] = jobs[i];
                index++;
            }
        }
        return pendingJobs;
    }

    function getJobsByStatus(JobStatus _status) external view returns (Job[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == _status) {
                count++;
            }
        }
        
        Job[] memory filteredJobs = new Job[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == _status) {
                filteredJobs[index] = jobs[i];
                index++;
            }
        }
        return filteredJobs;
    }

    function getJobsByRequester(address _requester) external view returns (Job[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].requester == _requester) {
                count++;
            }
        }
        
        Job[] memory userJobs = new Job[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].requester == _requester) {
                userJobs[index] = jobs[i];
                index++;
            }
        }
        return userJobs;
    }

    function getCompletedJobsWithModels() external view returns (Job[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == JobStatus.Completed && bytes(jobs[i].modelHash).length > 0) {
                count++;
            }
        }
        
        Job[] memory completedJobs = new Job[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == JobStatus.Completed && bytes(jobs[i].modelHash).length > 0) {
                completedJobs[index] = jobs[i];
                index++;
            }
        }
        return completedJobs;
    }

    // ============ View Functions - Worker Queries ============

    function getWorker(address _worker) external view returns (Worker memory) {
        return workers[_worker];
    }

    function getActiveWorkers() external view returns (Worker[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < workerAddresses.length; i++) {
            if (workers[workerAddresses[i]].isActive) {
                count++;
            }
        }
        
        Worker[] memory activeWorkers = new Worker[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < workerAddresses.length; i++) {
            if (workers[workerAddresses[i]].isActive) {
                activeWorkers[index] = workers[workerAddresses[i]];
                index++;
            }
        }
        return activeWorkers;
    }

    function getWorkerCount() external view returns (uint256 total, uint256 active) {
        total = workerAddresses.length;
        for (uint256 i = 0; i < workerAddresses.length; i++) {
            if (workers[workerAddresses[i]].isActive) {
                active++;
            }
        }
    }

    function getWorkerJobHistory(address _worker) external view returns (uint256[] memory) {
        return workerJobHistory[_worker];
    }

    // Fair distribution helper - get worker with fewest completed jobs
    function getWorkerPriority(address _worker) external view returns (uint256) {
        Worker memory worker = workers[_worker];
        if (!worker.isActive) return type(uint256).max;
        
        // Lower number = higher priority (fewer jobs = higher priority)
        return worker.completedJobs;
    }

    // ============ View Functions - Statistics ============

    function getStats() external view returns (
        uint256 totalJobs,
        uint256 pendingJobs,
        uint256 processingJobs,
        uint256 completedJobs,
        uint256 totalWorkers,
        uint256 activeWorkers,
        uint256 totalValueLocked
    ) {
        totalJobs = jobs.length;
        
        for (uint256 i = 0; i < jobs.length; i++) {
            if (jobs[i].status == JobStatus.Pending) pendingJobs++;
            else if (jobs[i].status == JobStatus.Processing) processingJobs++;
            else if (jobs[i].status == JobStatus.Completed) completedJobs++;
        }
        
        totalWorkers = workerAddresses.length;
        for (uint256 i = 0; i < workerAddresses.length; i++) {
            if (workers[workerAddresses[i]].isActive) {
                activeWorkers++;
                totalValueLocked += workers[workerAddresses[i]].stake;
            }
        }
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

    receive() external payable {}
}
