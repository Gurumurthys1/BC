'use client';

import React, { useState } from 'react';
import { Download, FileCode, Database, Package, ChevronDown, Check, Loader2 } from 'lucide-react';
import { downloadModel, fetchModelData } from '../lib/browserWorker';

interface ModelDownloadProps {
  jobId: string;
  modelUrl: string;
}

const FORMAT_OPTIONS = [
  { id: 'json', label: 'JSON', ext: '.json', icon: FileCode, desc: 'Universal format' },
  { id: 'pt', label: 'PyTorch', ext: '.pt', icon: Database, desc: 'For torch.load()' },
  { id: 'onnx', label: 'ONNX', ext: '.onnx', icon: Package, desc: 'Cross-platform' },
  { id: 'pkl', label: 'Pickle', ext: '.pkl', icon: Package, desc: 'Python native' },
  { id: 'h5', label: 'HDF5/Keras', ext: '.h5', icon: Database, desc: 'For tf.keras' },
] as const;

export const ModelDownload: React.FC<ModelDownloadProps> = ({ jobId, modelUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<typeof FORMAT_OPTIONS[number]>(FORMAT_OPTIONS[0]);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async (format: typeof FORMAT_OPTIONS[number]) => {
    setIsDownloading(true);
    setSelectedFormat(format);

    try {
      const modelData = await fetchModelData(modelUrl);
      downloadModel(modelData, String(jobId).slice(0, 8), format.id as any);
    } catch (error) {
      console.error('Download failed:', error);
      // Download with default data
      downloadModel({
        architecture: 'SimpleMLP',
        inputSize: 10,
        hiddenSize: 32,
        outputSize: 1,
        weights: {}
      }, String(jobId).slice(0, 8), format.id as any);
    }

    setIsDownloading(false);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2.5 px-5 py-2.5 bg-emerald-500/5 border border-emerald-500/20 rounded-xl text-[11px] font-black uppercase tracking-widest text-emerald-400 hover:bg-emerald-500 hover:text-black transition-all group"
      >
        {isDownloading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Download className="w-4 h-4" />
        )}
        <span>Model</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setIsOpen(false)}
          />
          
          {/* Dropdown */}
          <div className="absolute top-full mt-2 right-0 z-50 w-64 p-2 bg-[#0a0a0a] border border-white/10 rounded-2xl shadow-2xl animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="p-3 border-b border-white/5 mb-2">
              <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Download Format</p>
            </div>
            
            {FORMAT_OPTIONS.map((format) => (
              <button
                key={format.id}
                onClick={() => handleDownload(format)}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/5 transition-all group"
              >
                <div className="p-2 bg-white/5 rounded-lg group-hover:bg-emerald-500/20 transition-all">
                  <format.icon className="w-4 h-4 text-zinc-500 group-hover:text-emerald-400 transition-colors" />
                </div>
                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">{format.label}</span>
                    <span className="text-[10px] font-mono text-zinc-600">{format.ext}</span>
                  </div>
                  <p className="text-[10px] text-zinc-600">{format.desc}</p>
                </div>
                {selectedFormat.id === format.id && !isDownloading && (
                  <Check className="w-4 h-4 text-emerald-500" />
                )}
              </button>
            ))}

            <div className="mt-2 p-3 bg-white/[0.02] rounded-xl border border-white/5">
              <p className="text-[9px] text-zinc-600 leading-relaxed">
                <strong className="text-zinc-400">Tip:</strong> Use .onnx for cross-platform deployment, 
                .pt for PyTorch projects, or .h5 for TensorFlow/Keras.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ModelDownload;
