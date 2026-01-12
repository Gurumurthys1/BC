/**
 * IPFS Client for OBLIVION Frontend
 * Handles file uploads to Pinata IPFS
 */

const PINATA_API_URL = 'https://api.pinata.cloud';
const PINATA_GATEWAY = process.env.NEXT_PUBLIC_PINATA_GATEWAY || 'https://gateway.pinata.cloud';

interface PinataConfig {
  jwt?: string;
  apiKey?: string;
  secretKey?: string;
}

function getConfig(): PinataConfig {
  return {
    jwt: process.env.NEXT_PUBLIC_PINATA_JWT,
    apiKey: process.env.NEXT_PUBLIC_PINATA_API_KEY,
    secretKey: process.env.NEXT_PUBLIC_PINATA_SECRET_KEY
  };
}

function getHeaders(): Record<string, string> {
  const config = getConfig();
  
  if (config.jwt) {
    return { 'Authorization': `Bearer ${config.jwt}` };
  }
  
  if (config.apiKey && config.secretKey) {
    return {
      'pinata_api_key': config.apiKey,
      'pinata_secret_api_key': config.secretKey
    };
  }
  
  throw new Error('Pinata credentials not configured');
}

/**
 * Upload a file to IPFS via Pinata
 */
export async function uploadFile(file: File, name?: string): Promise<string> {
  const formData = new FormData();
  formData.append('file', file);
  
  const metadata = JSON.stringify({
    name: name || file.name
  });
  formData.append('pinataMetadata', metadata);
  
  const response = await fetch(`${PINATA_API_URL}/pinning/pinFileToIPFS`, {
    method: 'POST',
    headers: getHeaders(),
    body: formData
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Upload failed: ${error}`);
  }
  
  const result = await response.json();
  return result.IpfsHash;
}

/**
 * Upload JSON data to IPFS via Pinata
 */
export async function uploadJSON(data: any, name: string = 'data.json'): Promise<string> {
  const response = await fetch(`${PINATA_API_URL}/pinning/pinJSONToIPFS`, {
    method: 'POST',
    headers: {
      ...getHeaders(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      pinataContent: data,
      pinataMetadata: { name }
    })
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`JSON upload failed: ${error}`);
  }
  
  const result = await response.json();
  return result.IpfsHash;
}

/**
 * Get the gateway URL for a CID
 */
export function getGatewayUrl(cid: string): string {
  const cleanCid = cid.replace('ipfs://', '');
  return `${PINATA_GATEWAY}/ipfs/${cleanCid}`;
}

/**
 * Download content from IPFS
 */
export async function downloadFromIPFS(cid: string): Promise<Response> {
  const url = getGatewayUrl(cid);
  return fetch(url);
}

/**
 * Download JSON from IPFS
 */
export async function downloadJSON(cid: string): Promise<any> {
  const response = await downloadFromIPFS(cid);
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Download file as blob from IPFS
 */
export async function downloadBlob(cid: string): Promise<Blob> {
  const response = await downloadFromIPFS(cid);
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }
  return response.blob();
}

/**
 * Check if Pinata is configured
 */
export function isPinataConfigured(): boolean {
  const config = getConfig();
  return !!(config.jwt || (config.apiKey && config.secretKey));
}

/**
 * Test Pinata connection
 */
export async function testConnection(): Promise<boolean> {
  try {
    const response = await fetch(`${PINATA_API_URL}/data/testAuthentication`, {
      headers: getHeaders()
    });
    return response.ok;
  } catch {
    return false;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// TRAINING DATA HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Parse CSV file to training data format
 */
export function parseCSVToTrainingData(csvContent: string): { X: number[][]; y: number[] } {
  const lines = csvContent.trim().split('\n');
  const headers = lines[0].split(',');
  
  const X: number[][] = [];
  const y: number[] = [];
  
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => parseFloat(v.trim()));
    
    if (values.length >= 2) {
      // Last column is target, rest are features
      y.push(values[values.length - 1]);
      X.push(values.slice(0, -1));
    }
  }
  
  return { X, y };
}

/**
 * Upload training data from CSV file
 */
export async function uploadTrainingData(csvFile: File): Promise<string> {
  const content = await csvFile.text();
  const data = parseCSVToTrainingData(content);
  
  return uploadJSON(data, `training_data_${Date.now()}.json`);
}

/**
 * Upload training script
 */
export async function uploadTrainingScript(script: string, name?: string): Promise<string> {
  const blob = new Blob([script], { type: 'text/plain' });
  const file = new File([blob], name || 'training_script.py');
  
  return uploadFile(file, name);
}
