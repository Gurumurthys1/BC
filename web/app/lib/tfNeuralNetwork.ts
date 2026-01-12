/**
 * TensorFlow.js Neural Network Module for Oblivion Browser Workers
 * Provides real neural network training with actual backpropagation.
 */

// @ts-ignore - TensorFlow.js types will be available after npm install
import * as tf from '@tensorflow/tfjs';

export interface TrainingConfig {
  epochs: number;
  batchSize: number;
  learningRate: number;
  validationSplit: number;
  earlyStoppingPatience?: number;
  privacyEpsilon?: number;
}

export interface TrainingResult {
  finalLoss: number;
  finalAccuracy?: number;
  validationLoss?: number;
  epochHistory: { loss: number; val_loss?: number }[];
  trainingTime: number;
  modelWeights: ArrayBuffer;
  privacyBudgetUsed?: number;
}

export interface ModelArchitecture {
  inputShape: number[];
  layers: LayerConfig[];
  outputActivation: 'sigmoid' | 'softmax' | 'linear' | 'relu';
}

export interface LayerConfig {
  type: 'dense' | 'dropout' | 'batchNorm';
  units?: number;
  activation?: string;
  rate?: number;
}

/**
 * TensorFlow.js based neural network for browser training
 */
export class TFNeuralNetwork {
  private model: tf.Sequential | null = null;
  private architecture: ModelArchitecture;
  private isCompiled: boolean = false;

  constructor(architecture?: ModelArchitecture) {
    this.architecture = architecture || {
      inputShape: [10],
      layers: [
        { type: 'dense', units: 64, activation: 'relu' },
        { type: 'dropout', rate: 0.2 },
        { type: 'dense', units: 32, activation: 'relu' },
        { type: 'dense', units: 1, activation: 'sigmoid' }
      ],
      outputActivation: 'sigmoid'
    };
  }

  /**
   * Build the neural network model
   */
  build(): tf.Sequential {
    this.model = tf.sequential();

    // Add input layer
    let isFirstLayer = true;

    for (const layerConfig of this.architecture.layers) {
      if (layerConfig.type === 'dense') {
        const config: any = {
          units: layerConfig.units || 32,
          activation: layerConfig.activation || 'relu'
        };

        if (isFirstLayer) {
          config.inputShape = this.architecture.inputShape;
          isFirstLayer = false;
        }

        this.model.add(tf.layers.dense(config));
      } else if (layerConfig.type === 'dropout') {
        this.model.add(tf.layers.dropout({ rate: layerConfig.rate || 0.2 }));
      } else if (layerConfig.type === 'batchNorm') {
        this.model.add(tf.layers.batchNormalization());
      }
    }

    return this.model;
  }

  /**
   * Compile the model with optimizer and loss function
   */
  compile(learningRate: number = 0.01, loss: string = 'binaryCrossentropy'): void {
    if (!this.model) {
      this.build();
    }

    this.model!.compile({
      optimizer: tf.train.adam(learningRate),
      loss: loss,
      metrics: ['accuracy']
    });

    this.isCompiled = true;
  }

  /**
   * Train the model with real backpropagation
   */
  async train(
    inputs: number[][],
    targets: number[][],
    config: TrainingConfig
  ): Promise<TrainingResult> {
    if (!this.isCompiled) {
      this.compile(config.learningRate);
    }

    const startTime = Date.now();
    const epochHistory: { loss: number; val_loss?: number }[] = [];

    // Convert data to tensors
    const xs = tf.tensor2d(inputs);
    const ys = tf.tensor2d(targets);

    // Normalize inputs
    const xsMean = xs.mean();
    const xsStd = tf.moments(xs).variance.sqrt();
    const xsNorm = xs.sub(xsMean).div(xsStd.add(1e-7));

    // Setup callbacks for tracking progress
    let bestValLoss = Infinity;
    let patienceCounter = 0;
    let stoppedEarly = false;

    const callbacks: tf.CustomCallbackArgs = {
      onEpochEnd: (epoch: number, logs: tf.Logs | undefined) => {
        const loss = logs?.loss as number || 0;
        const valLoss = logs?.val_loss as number | undefined;
        
        epochHistory.push({ loss, val_loss: valLoss });

        // Early stopping
        if (config.earlyStoppingPatience && valLoss !== undefined) {
          if (valLoss < bestValLoss) {
            bestValLoss = valLoss;
            patienceCounter = 0;
          } else {
            patienceCounter++;
            if (patienceCounter >= config.earlyStoppingPatience) {
              stoppedEarly = true;
              this.model!.stopTraining = true;
            }
          }
        }
      }
    };

    // Train the model
    const history = await this.model!.fit(xsNorm, ys, {
      epochs: config.epochs,
      batchSize: config.batchSize,
      validationSplit: config.validationSplit,
      shuffle: true,
      callbacks: [callbacks]
    });

    // Get final metrics
    const finalLoss = epochHistory[epochHistory.length - 1]?.loss || 0;
    const finalValLoss = epochHistory[epochHistory.length - 1]?.val_loss;

    // Export model weights
    const weightsBuffer = await this.exportWeights();

    // Cleanup tensors
    xs.dispose();
    ys.dispose();
    xsNorm.dispose();

    return {
      finalLoss,
      validationLoss: finalValLoss,
      epochHistory,
      trainingTime: Date.now() - startTime,
      modelWeights: weightsBuffer
    };
  }

  /**
   * Run inference on input data
   */
  async predict(input: number[]): Promise<number[]> {
    if (!this.model) {
      throw new Error('Model not built');
    }

    const inputTensor = tf.tensor2d([input]);
    const prediction = this.model.predict(inputTensor) as tf.Tensor;
    const result = await prediction.array() as number[][];

    inputTensor.dispose();
    prediction.dispose();

    return result[0];
  }

  /**
   * Export model weights as ArrayBuffer
   */
  async exportWeights(): Promise<ArrayBuffer> {
    if (!this.model) {
      throw new Error('Model not built');
    }

    const weights: { [key: string]: number[] } = {};
    
    for (const layer of this.model.layers) {
      const layerWeights = layer.getWeights();
      for (let i = 0; i < layerWeights.length; i++) {
        const weightData = await layerWeights[i].data();
        weights[`${layer.name}_${i}`] = Array.from(weightData);
      }
    }

    const jsonString = JSON.stringify(weights);
    const encoder = new TextEncoder();
    return encoder.encode(jsonString).buffer;
  }

  /**
   * Import weights from ArrayBuffer
   */
  async importWeights(buffer: ArrayBuffer): Promise<void> {
    if (!this.model) {
      this.build();
    }

    const decoder = new TextDecoder();
    const jsonString = decoder.decode(buffer);
    const weights = JSON.parse(jsonString);

    for (const layer of this.model!.layers) {
      const layerWeights: tf.Tensor[] = [];
      let i = 0;
      
      while (weights[`${layer.name}_${i}`] !== undefined) {
        const weightData = weights[`${layer.name}_${i}`];
        const originalWeight = layer.getWeights()[i];
        const shape = originalWeight.shape;
        layerWeights.push(tf.tensor(weightData, shape));
        i++;
      }

      if (layerWeights.length > 0) {
        layer.setWeights(layerWeights);
      }
    }
  }

  /**
   * Get model summary
   */
  getSummary(): string {
    if (!this.model) {
      return 'Model not built';
    }

    let summary = 'TF.js Neural Network Summary:\n';
    summary += '================================\n';
    
    for (const layer of this.model.layers) {
      const config = layer.getConfig();
      summary += `${layer.name}: ${(config as any).units || 'N/A'} units\n`;
    }

    const totalParams = this.model.countParams();
    summary += `================================\n`;
    summary += `Total parameters: ${totalParams}\n`;

    return summary;
  }

  /**
   * Dispose of model and free memory
   */
  dispose(): void {
    if (this.model) {
      this.model.dispose();
      this.model = null;
    }
    this.isCompiled = false;
  }
}

/**
 * Add differential privacy noise to gradients/weights
 */
export function addDifferentialPrivacyNoise(
  weights: number[],
  epsilon: number,
  sensitivity: number = 1.0
): { noisyWeights: number[]; noiseScale: number } {
  // Laplace noise for pure epsilon-DP
  const noiseScale = sensitivity / epsilon;
  
  const noisyWeights = weights.map(w => {
    // Generate Laplace noise using inverse CDF method
    const u = Math.random() - 0.5;
    const noise = -noiseScale * Math.sign(u) * Math.log(1 - 2 * Math.abs(u));
    return w + noise;
  });

  return { noisyWeights, noiseScale };
}

/**
 * Create a model hash for verification
 */
export function createModelHash(weights: ArrayBuffer): string {
  const data = new Uint8Array(weights);
  let hash = 0;
  for (let i = 0; i < data.length; i++) {
    const char = data[i];
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16).padStart(16, '0');
}

/**
 * Default export for easy importing
 */
export default TFNeuralNetwork;
