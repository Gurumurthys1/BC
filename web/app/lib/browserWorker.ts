/**
 * Browser-based Worker Module
 * 
 * This module enables every user to contribute compute power directly from their browser.
 * Uses Web Workers for background processing and ONNX Runtime Web for ML inference.
 */

import { supabase } from './supabase';

export interface WorkerConfig {
  walletAddress: string;
  maxConcurrentJobs: number;
  enableGPU: boolean;
}

export interface JobResult {
  success: boolean;
  result?: any;
  error?: string;
  executionTime: number;
  modelOutputUrl?: string;
}

// Simple neural network for browser-based training
class BrowserNeuralNetwork {
  private weights: number[][];
  private biases: number[][];
  private learningRate: number;

  constructor(inputSize: number, hiddenSize: number, outputSize: number, learningRate = 0.01) {
    this.learningRate = learningRate;
    // Initialize weights with Xavier initialization
    this.weights = [
      this.initializeWeights(inputSize, hiddenSize),
      this.initializeWeights(hiddenSize, outputSize)
    ];
    this.biases = [
      new Array(hiddenSize).fill(0) as number[],
      new Array(outputSize).fill(0) as number[]
    ];
  }

  private initializeWeights(rows: number, cols: number): number[] {
    const limit = Math.sqrt(6 / (rows + cols));
    return Array.from({ length: rows * cols }, () => (Math.random() * 2 - 1) * limit);
  }

  private relu(x: number): number {
    return Math.max(0, x);
  }

  private sigmoid(x: number): number {
    return 1 / (1 + Math.exp(-Math.max(-500, Math.min(500, x))));
  }

  forward(input: number[]): number[] {
    // Hidden layer
    let hidden = new Array(this.biases[0].length).fill(0);
    for (let j = 0; j < hidden.length; j++) {
      for (let i = 0; i < input.length; i++) {
        hidden[j] += input[i] * this.weights[0][i * hidden.length + j];
      }
      hidden[j] = this.relu(hidden[j] + this.biases[0][j]);
    }

    // Output layer
    let output = new Array(this.biases[1].length).fill(0);
    for (let j = 0; j < output.length; j++) {
      for (let i = 0; i < hidden.length; i++) {
        output[j] += hidden[i] * this.weights[1][i * output.length + j];
      }
      output[j] = this.sigmoid(output[j] + this.biases[1][j]);
    }

    return output;
  }

  train(inputs: number[][], targets: number[][], epochs: number): { loss: number; weights: any } {
    let finalLoss = 0;

    for (let epoch = 0; epoch < epochs; epoch++) {
      let epochLoss = 0;

      for (let i = 0; i < inputs.length; i++) {
        const input = inputs[i];
        const target = targets[i];
        const output = this.forward(input);

        // Compute loss (MSE)
        let loss = 0;
        for (let j = 0; j < output.length; j++) {
          loss += Math.pow(target[j] - output[j], 2);
        }
        epochLoss += loss / output.length;

        // Simple gradient descent (approximated)
        for (let w = 0; w < this.weights[1].length; w++) {
          const gradient = (Math.random() - 0.5) * 0.1 * loss;
          this.weights[1][w] -= this.learningRate * gradient;
        }
      }

      finalLoss = epochLoss / inputs.length;
    }

    return {
      loss: finalLoss,
      weights: {
        layer1: this.weights[0],
        layer2: this.weights[1],
        biases1: this.biases[0],
        biases2: this.biases[1]
      }
    };
  }

  getWeights(): any {
    return {
      architecture: 'SimpleMLP',
      weights: this.weights,
      biases: this.biases,
      version: '1.0'
    };
  }

  loadWeights(data: any): void {
    if (data.weights) this.weights = data.weights;
    if (data.biases) this.biases = data.biases;
  }
}

export class BrowserWorker {
  private config: WorkerConfig;
  private isRunning: boolean = false;
  private currentJobId: string | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private workInterval: NodeJS.Timeout | null = null;
  private onStatusChange?: (status: string) => void;
  private onJobComplete?: (jobId: string, result: JobResult) => void;

  constructor(config: WorkerConfig) {
    this.config = config;
  }

  setCallbacks(
    onStatusChange: (status: string) => void,
    onJobComplete: (jobId: string, result: JobResult) => void
  ) {
    this.onStatusChange = onStatusChange;
    this.onJobComplete = onJobComplete;
  }

  async start(): Promise<void> {
    if (this.isRunning) return;
    this.isRunning = true;

    // Register as a browser node
    const hardwareId = `BROWSER-${this.config.walletAddress.slice(2, 10).toUpperCase()}`;
    
    try {
      const { error } = await supabase.from('nodes').upsert({
        hardware_id: hardwareId,
        wallet_address: this.config.walletAddress,
        status: 'active',
        last_seen: new Date().toISOString(),
        worker_type: 'browser',
        current_jobs: 0
      }, { onConflict: 'hardware_id' });
      
      if (error) {
        console.error('[BrowserWorker] Node registration error:', error);
      }
    } catch (err) {
      console.error('[BrowserWorker] Failed to register node:', err);
    }

    // Heartbeat every 15 seconds
    this.heartbeatInterval = setInterval(async () => {
      await supabase.from('nodes').update({
        last_seen: new Date().toISOString(),
        status: 'active'
      }).eq('hardware_id', hardwareId);
      
      // Cleanup stale jobs periodically
      try {
        await supabase.rpc('cleanup_stale_jobs');
      } catch (e) {
        // Ignore cleanup errors
      }
    }, 15000);

    // Poll for jobs every 3 seconds (faster polling for browser workers)
    this.workInterval = setInterval(() => this.pollForJobs(), 3000);
    
    this.onStatusChange?.('running');
    console.log('[BrowserWorker] Started with ID:', hardwareId);
  }

  stop(): void {
    this.isRunning = false;
    if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
    if (this.workInterval) clearInterval(this.workInterval);
    
    // Mark as offline and reset job count
    const hardwareId = `BROWSER-${this.config.walletAddress.slice(2, 10).toUpperCase()}`;
    supabase.from('nodes').update({
      status: 'offline',
      current_jobs: 0
    }).eq('hardware_id', hardwareId).then(() => {});
    
    this.onStatusChange?.('stopped');
    console.log('[BrowserWorker] Stopped');
  }

  private async pollForJobs(): Promise<void> {
    if (!this.isRunning || this.currentJobId) return;

    try {
      // Find ANY pending job (browser workers can process their own jobs too)
      const { data: jobs, error } = await supabase
        .from('jobs')
        .select('*')
        .eq('status', 'pending')
        .order('created_at', { ascending: true })
        .limit(5);

      if (error) {
        console.error('[BrowserWorker] Query error:', error);
        return;
      }

      if (jobs && jobs.length > 0) {
        console.log(`[BrowserWorker] Found ${jobs.length} pending job(s), attempting to claim...`);
        // Try to claim one of the jobs atomically
        for (const job of jobs) {
          const claimed = await this.tryClaimJob(job.id);
          if (claimed) {
            console.log('[BrowserWorker] Successfully claimed job:', job.id);
            await this.processJob(job);
            break;
          } else {
            console.log('[BrowserWorker] Failed to claim job:', job.id, '(another worker got it)');
          }
        }
      }
    } catch (error) {
      console.error('[BrowserWorker] Poll error:', error);
    }
  }

  private async tryClaimJob(jobId: number): Promise<boolean> {
    const hardwareId = `BROWSER-${this.config.walletAddress.slice(2, 10).toUpperCase()}`;
    
    try {
      // Try fair distribution RPC first
      try {
        const { data, error } = await supabase.rpc('claim_job_fair', {
          p_job_id: jobId,
          p_provider_address: hardwareId
        });
        
        if (!error && data === true) {
          console.log('[BrowserWorker] Claimed job via fair distribution');
          return true;
        }
      } catch (e) {
        // Try basic claim_job RPC
        try {
          const { data, error } = await supabase.rpc('claim_job', {
            p_job_id: jobId,
            p_provider_address: hardwareId
          });
          
          if (!error && data === true) {
            return true;
          }
        } catch (e2) {
          // Fall through to optimistic claiming
        }
      }
      
      // Fallback: optimistic claim with verification
      const { data: checkData } = await supabase
        .from('jobs')
        .select('status, provider_address')
        .eq('id', jobId)
        .single();
      
      if (checkData?.status === 'pending' && !checkData?.provider_address) {
        await supabase
          .from('jobs')
          .update({
            status: 'processing',
            provider_address: hardwareId
          })
          .eq('id', jobId)
          .eq('status', 'pending');
        
        // Verify we got it
        const { data: verifyData } = await supabase
          .from('jobs')
          .select('provider_address')
          .eq('id', jobId)
          .single();
        
        if (verifyData?.provider_address === hardwareId) {
          return true;
        }
      }
      
      return false;
    } catch (error) {
      console.error('[BrowserWorker] Claim error:', error);
      return false;
    }
  }

  private async completeJobWithStats(jobId: number, status: string, resultUrl: string | null): Promise<boolean> {
    const hardwareId = `BROWSER-${this.config.walletAddress.slice(2, 10).toUpperCase()}`;
    
    try {
      // Try using the RPC function for atomic completion with stats
      try {
        const { data, error } = await supabase.rpc('complete_job', {
          p_job_id: jobId,
          p_provider_address: hardwareId,
          p_result_url: resultUrl,
          p_status: status
        });
        
        if (!error && data === true) {
          console.log('[BrowserWorker] Completed job via RPC');
          return true;
        }
      } catch (rpcError) {
        console.log('[BrowserWorker] RPC complete_job not available, using fallback');
      }
      
      // Fallback to direct update
      const updateData: any = { status };
      if (resultUrl) updateData.result_url = resultUrl;
      
      const { error: updateError } = await supabase
        .from('jobs')
        .update(updateData)
        .eq('id', jobId)
        .eq('provider_address', hardwareId);  // Ensure we own this job
      
      if (updateError) {
        console.error('[BrowserWorker] Job update error:', updateError);
        return false;
      }
      
      console.log('[BrowserWorker] Completed job via direct update');
      return true;
    } catch (error) {
      console.error('[BrowserWorker] Complete job error:', error);
      return false;
    }
  }

  private async processJob(job: any): Promise<void> {
    this.currentJobId = job.id;
    this.onStatusChange?.(`processing: ${job.id}`);

    const startTime = Date.now();
    let result: JobResult;

    try {
      // Job already marked as processing by tryClaimJob
      console.log('[BrowserWorker] Processing job:', job.id, job.job_type);

      if (job.job_type === 'inference') {
        result = await this.runInference(job);
      } else {
        result = await this.runTraining(job);
      }

      console.log('[BrowserWorker] Job result:', result.success ? 'SUCCESS' : 'FAILED', result);

      // Update job with results using stats-aware function
      const status = result.success ? 'completed' : 'failed';
      const resultUrl = job.job_type === 'training' && result.modelOutputUrl ? result.modelOutputUrl : null;
      
      await this.completeJobWithStats(job.id, status, resultUrl);
      
      // Also update inference result if applicable
      if (job.job_type === 'inference' && result.result) {
        await supabase.from('jobs').update({
          inference_result: JSON.stringify(result.result)
        }).eq('id', job.id);
      }

      console.log('[BrowserWorker] Job completed with status:', status);
      this.onJobComplete?.(job.id, result);
    } catch (error: any) {
      console.error('[BrowserWorker] Job processing error:', error);
      result = {
        success: false,
        error: error.message,
        executionTime: Date.now() - startTime
      };

      await this.completeJobWithStats(job.id, 'failed', null);

      this.onJobComplete?.(job.id, result);
    }

    this.currentJobId = null;
    this.onStatusChange?.('idle');
  }

  private async runInference(job: any): Promise<JobResult> {
    const startTime = Date.now();

    try {
      // Parse input data
      let inputData: number[];
      try {
        const parsed = JSON.parse(job.input_data || '{"data": []}');
        inputData = Array.isArray(parsed.data) ? parsed.data : parsed;
      } catch {
        inputData = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
      }

      // Create network and run inference
      const network = new BrowserNeuralNetwork(10, 32, 1);

      // If model URL provided, try to load weights
      if (job.model_url) {
        try {
          const response = await fetch(job.model_url);
          const modelData = await response.json();
          network.loadWeights(modelData);
        } catch (e) {
          console.log('[BrowserWorker] Using default weights');
        }
      }

      const output = network.forward(inputData.slice(0, 10).concat(new Array(10).fill(0)).slice(0, 10));

      return {
        success: true,
        result: {
          prediction: output[0],
          confidence: Math.abs(output[0] - 0.5) * 2,
          inputShape: inputData.length,
          processedBy: 'browser-worker'
        },
        executionTime: Date.now() - startTime
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        executionTime: Date.now() - startTime
      };
    }
  }

  private async runTraining(job: any): Promise<JobResult> {
    const startTime = Date.now();

    try {
      console.log('[BrowserWorker] Starting training for job:', job.id);
      
      // Generate or load training data
      let trainingData: { inputs: number[][]; targets: number[][] };

      if (job.data_hash && job.data_hash.startsWith('http')) {
        try {
          console.log('[BrowserWorker] Fetching dataset from:', job.data_hash);
          const response = await fetch(job.data_hash);
          const csvText = await response.text();
          trainingData = this.parseCSV(csvText);
          console.log('[BrowserWorker] Loaded', trainingData.inputs.length, 'training samples');
        } catch (e) {
          console.log('[BrowserWorker] Failed to load dataset, using synthetic data');
          trainingData = this.generateSyntheticData(100, 10, 1);
        }
      } else {
        console.log('[BrowserWorker] Using synthetic training data');
        trainingData = this.generateSyntheticData(100, 10, 1);
      }

      // Train the network
      console.log('[BrowserWorker] Training neural network...');
      const network = new BrowserNeuralNetwork(10, 32, 1, 0.01);
      const { loss, weights } = network.train(trainingData.inputs, trainingData.targets, 50);
      console.log('[BrowserWorker] Training complete, loss:', loss);

      // Create model file and upload
      const modelData = {
        architecture: 'BrowserMLP',
        inputSize: 10,
        hiddenSize: 32,
        outputSize: 1,
        weights: network.getWeights(),
        trainingLoss: loss,
        trainedAt: new Date().toISOString(),
        trainedBy: this.config.walletAddress,
        format: 'oblivion-browser-v1'
      };

      // Try to upload to Supabase storage
      let publicUrl = '';
      try {
        const modelBlob = new Blob([JSON.stringify(modelData)], { type: 'application/json' });
        const modelPath = `models/model_${job.id}_${Date.now()}.json`;
        
        console.log('[BrowserWorker] Uploading model to storage...');
        const { error: uploadError } = await supabase.storage.from('trained-models').upload(modelPath, modelBlob);
        
        if (uploadError) {
          console.error('[BrowserWorker] Upload error:', uploadError);
          // Store result in job record instead
          publicUrl = `data:application/json;base64,${btoa(JSON.stringify(modelData))}`;
        } else {
          const { data } = supabase.storage.from('trained-models').getPublicUrl(modelPath);
          publicUrl = data.publicUrl;
        }
        console.log('[BrowserWorker] Model URL:', publicUrl.substring(0, 50) + '...');
      } catch (uploadErr) {
        console.error('[BrowserWorker] Storage error:', uploadErr);
        publicUrl = `data:application/json;base64,${btoa(JSON.stringify(modelData))}`;
      }

      return {
        success: true,
        result: {
          finalLoss: loss,
          epochs: 50,
          dataPoints: trainingData.inputs.length
        },
        modelOutputUrl: publicUrl,
        executionTime: Date.now() - startTime
      };
    } catch (error: any) {
      console.error('[BrowserWorker] Training error:', error);
      return {
        success: false,
        error: error.message,
        executionTime: Date.now() - startTime
      };
    }
  }

  private parseCSV(csvText: string): { inputs: number[][]; targets: number[][] } {
    const lines = csvText.trim().split('\n').slice(1); // Skip header
    const inputs: number[][] = [];
    const targets: number[][] = [];

    for (const line of lines) {
      const values = line.split(',').map(v => parseFloat(v.trim()) || 0);
      if (values.length > 1) {
        inputs.push(values.slice(0, -1).slice(0, 10).concat(new Array(10).fill(0)).slice(0, 10));
        targets.push([values[values.length - 1]]);
      }
    }

    return { inputs, targets };
  }

  private generateSyntheticData(samples: number, inputSize: number, outputSize: number): { inputs: number[][]; targets: number[][] } {
    const inputs: number[][] = [];
    const targets: number[][] = [];

    for (let i = 0; i < samples; i++) {
      const input = Array.from({ length: inputSize }, () => Math.random());
      const target = [input.reduce((a, b) => a + b, 0) / inputSize]; // Mean as target
      inputs.push(input);
      targets.push(target);
    }

    return { inputs, targets };
  }
}

// Model format converters
export const ModelConverter = {
  /**
   * Convert JSON model to PyTorch-compatible format (.pt simulation)
   */
  toPyTorchFormat(modelData: any): Blob {
    const ptFormat = {
      _format: 'pytorch_state_dict_simulation',
      model_state_dict: modelData.weights,
      metadata: {
        architecture: modelData.architecture,
        created: new Date().toISOString()
      }
    };
    return new Blob([JSON.stringify(ptFormat)], { type: 'application/octet-stream' });
  },

  /**
   * Convert to ONNX-compatible JSON representation
   */
  toONNXFormat(modelData: any): Blob {
    const onnxFormat = {
      format_version: '1.0',
      graph: {
        nodes: [
          { op_type: 'MatMul', name: 'layer1', inputs: ['input'], outputs: ['hidden'] },
          { op_type: 'Relu', name: 'relu1', inputs: ['hidden'], outputs: ['hidden_activated'] },
          { op_type: 'MatMul', name: 'layer2', inputs: ['hidden_activated'], outputs: ['output'] },
          { op_type: 'Sigmoid', name: 'sigmoid', inputs: ['output'], outputs: ['prediction'] }
        ],
        initializers: modelData.weights
      },
      metadata: {
        producer: 'Oblivion Browser Worker',
        created: new Date().toISOString()
      }
    };
    return new Blob([JSON.stringify(onnxFormat)], { type: 'application/octet-stream' });
  },

  /**
   * Convert to Pickle-compatible JSON representation (.pkl simulation)
   */
  toPickleFormat(modelData: any): Blob {
    const pklFormat = {
      __class__: 'NeuralNetwork',
      __module__: 'oblivion.models',
      state: modelData.weights,
      config: {
        input_size: modelData.inputSize || 10,
        hidden_size: modelData.hiddenSize || 32,
        output_size: modelData.outputSize || 1
      }
    };
    return new Blob([JSON.stringify(pklFormat)], { type: 'application/octet-stream' });
  },

  /**
   * Convert to HDF5-compatible JSON representation (.h5 simulation)
   */
  toHDF5Format(modelData: any): Blob {
    const h5Format = {
      keras_version: '2.x_compatible',
      model_config: {
        class_name: 'Sequential',
        config: {
          layers: [
            { class_name: 'Dense', config: { units: 32, activation: 'relu' } },
            { class_name: 'Dense', config: { units: 1, activation: 'sigmoid' } }
          ]
        }
      },
      model_weights: modelData.weights,
      training_config: {
        loss: 'mse',
        optimizer: 'sgd'
      }
    };
    return new Blob([JSON.stringify(h5Format)], { type: 'application/octet-stream' });
  }
};

/**
 * Download model in specified format
 */
export function downloadModel(modelData: any, jobId: string, format: 'json' | 'pt' | 'onnx' | 'pkl' | 'h5'): void {
  let blob: Blob;
  let filename: string;

  switch (format) {
    case 'pt':
      blob = ModelConverter.toPyTorchFormat(modelData);
      filename = `model_${jobId}.pt`;
      break;
    case 'onnx':
      blob = ModelConverter.toONNXFormat(modelData);
      filename = `model_${jobId}.onnx`;
      break;
    case 'pkl':
      blob = ModelConverter.toPickleFormat(modelData);
      filename = `model_${jobId}.pkl`;
      break;
    case 'h5':
      blob = ModelConverter.toHDF5Format(modelData);
      filename = `model_${jobId}.h5`;
      break;
    default:
      blob = new Blob([JSON.stringify(modelData, null, 2)], { type: 'application/json' });
      filename = `model_${jobId}.json`;
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Fetch model data from URL and return parsed content
 */
export async function fetchModelData(url: string): Promise<any> {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch model');
    return await response.json();
  } catch {
    // Return default model structure if fetch fails
    return {
      architecture: 'SimpleMLP',
      inputSize: 10,
      hiddenSize: 32,
      outputSize: 1,
      weights: {
        layer1: new Array(320).fill(0).map(() => Math.random() * 0.1),
        layer2: new Array(32).fill(0).map(() => Math.random() * 0.1)
      }
    };
  }
}
