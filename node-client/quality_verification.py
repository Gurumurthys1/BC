"""
Model Quality Verification Module for Oblivion
Ensures trained models meet quality standards before payment.
"""

import torch
import torch.nn as nn
import numpy as np
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class QualityThresholds:
    """Quality thresholds for model verification."""
    max_loss: float = 10.0           # Maximum acceptable loss
    min_loss_improvement: float = 0.0  # Minimum required improvement
    max_gradient_norm: float = 100.0   # Maximum gradient norm
    min_gradient_norm: float = 1e-8    # Minimum gradient norm (detect dead gradients)
    max_weight_magnitude: float = 1000.0  # Maximum weight magnitude
    nan_tolerance: float = 0.0         # Fraction of NaN values allowed


class ModelQualityVerifier:
    """
    Verifies that trained models meet quality standards.
    Prevents workers from submitting garbage results.
    """
    
    def __init__(self, thresholds: Optional[QualityThresholds] = None):
        """
        Initialize verifier with thresholds.
        
        Args:
            thresholds: Quality thresholds (uses defaults if None)
        """
        self.thresholds = thresholds or QualityThresholds()
        
    def verify_loss(
        self,
        initial_loss: float,
        final_loss: float
    ) -> Tuple[bool, str]:
        """
        Verify that training achieved acceptable loss.
        
        Args:
            initial_loss: Loss before training
            final_loss: Loss after training
            
        Returns:
            Tuple of (passed, reason)
        """
        # Check for NaN/Inf
        if np.isnan(final_loss) or np.isinf(final_loss):
            return False, f"Invalid loss value: {final_loss}"
            
        # Check maximum loss
        if final_loss > self.thresholds.max_loss:
            return False, f"Loss {final_loss:.4f} exceeds maximum {self.thresholds.max_loss}"
            
        # Check improvement
        if self.thresholds.min_loss_improvement > 0:
            improvement = initial_loss - final_loss
            if improvement < self.thresholds.min_loss_improvement:
                return False, f"Loss improvement {improvement:.4f} below threshold {self.thresholds.min_loss_improvement}"
                
        return True, f"Loss {final_loss:.4f} is acceptable"
        
    def verify_gradients(
        self,
        gradients: List[torch.Tensor]
    ) -> Tuple[bool, str]:
        """
        Verify gradient quality.
        
        Args:
            gradients: List of gradient tensors
            
        Returns:
            Tuple of (passed, reason)
        """
        if not gradients:
            return False, "No gradients provided"
            
        total_norm = 0.0
        nan_count = 0
        total_elements = 0
        
        for g in gradients:
            if g is None:
                continue
                
            # Check for NaN/Inf
            nan_mask = torch.isnan(g) | torch.isinf(g)
            nan_count += nan_mask.sum().item()
            total_elements += g.numel()
            
            # Compute norm
            total_norm += g.pow(2).sum().item()
            
        total_norm = np.sqrt(total_norm)
        nan_fraction = nan_count / max(total_elements, 1)
        
        # Check NaN tolerance
        if nan_fraction > self.thresholds.nan_tolerance:
            return False, f"NaN fraction {nan_fraction:.2%} exceeds tolerance {self.thresholds.nan_tolerance:.2%}"
            
        # Check gradient magnitude
        if total_norm > self.thresholds.max_gradient_norm:
            return False, f"Gradient norm {total_norm:.4f} exceeds maximum {self.thresholds.max_gradient_norm}"
            
        if total_norm < self.thresholds.min_gradient_norm:
            return False, f"Gradient norm {total_norm:.4e} below minimum (dead gradients)"
            
        return True, f"Gradient norm {total_norm:.4f} is acceptable"
        
    def verify_weights(
        self,
        state_dict: Dict[str, torch.Tensor]
    ) -> Tuple[bool, str]:
        """
        Verify model weight quality.
        
        Args:
            state_dict: Model state dictionary
            
        Returns:
            Tuple of (passed, reason)
        """
        if not state_dict:
            return False, "Empty state dictionary"
            
        max_magnitude = 0.0
        nan_count = 0
        total_elements = 0
        
        for name, tensor in state_dict.items():
            if not isinstance(tensor, torch.Tensor):
                continue
                
            # Check for NaN/Inf
            nan_mask = torch.isnan(tensor) | torch.isinf(tensor)
            nan_count += nan_mask.sum().item()
            total_elements += tensor.numel()
            
            # Track max magnitude
            current_max = tensor.abs().max().item()
            if not np.isnan(current_max):
                max_magnitude = max(max_magnitude, current_max)
                
        nan_fraction = nan_count / max(total_elements, 1)
        
        # Check NaN tolerance
        if nan_fraction > self.thresholds.nan_tolerance:
            return False, f"Weight NaN fraction {nan_fraction:.2%} exceeds tolerance"
            
        # Check magnitude
        if max_magnitude > self.thresholds.max_weight_magnitude:
            return False, f"Weight magnitude {max_magnitude:.4f} exceeds maximum {self.thresholds.max_weight_magnitude}"
            
        return True, f"Weight magnitude {max_magnitude:.4f} is acceptable"
        
    def verify_model_output(
        self,
        model: nn.Module,
        test_input: torch.Tensor,
        expected_output_shape: Tuple[int, ...]
    ) -> Tuple[bool, str]:
        """
        Verify model produces valid outputs.
        
        Args:
            model: PyTorch model
            test_input: Test input tensor
            expected_output_shape: Expected output shape
            
        Returns:
            Tuple of (passed, reason)
        """
        try:
            model.eval()
            with torch.no_grad():
                output = model(test_input)
                
            # Check shape
            if output.shape != expected_output_shape:
                return False, f"Output shape {output.shape} doesn't match expected {expected_output_shape}"
                
            # Check for NaN/Inf
            if torch.isnan(output).any() or torch.isinf(output).any():
                return False, "Model output contains NaN or Inf values"
                
            return True, "Model output is valid"
            
        except Exception as e:
            return False, f"Model forward pass failed: {str(e)}"
            
    def verify_training_result(
        self,
        result: Dict[str, Any],
        initial_loss: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive verification of training result.
        
        Args:
            result: Training result dictionary
            initial_loss: Initial loss before training
            
        Returns:
            Verification report
        """
        report = {
            'passed': True,
            'checks': [],
            'warnings': [],
            'errors': []
        }
        
        # Check if result indicates success
        if not result.get('success', False):
            report['passed'] = False
            report['errors'].append(f"Training failed: {result.get('error', 'Unknown error')}")
            return report
            
        # Verify loss
        final_loss = result.get('loss', result.get('final_loss'))
        if final_loss is not None:
            initial = initial_loss or float('inf')
            passed, reason = self.verify_loss(initial, final_loss)
            report['checks'].append({
                'name': 'loss_verification',
                'passed': passed,
                'reason': reason
            })
            if not passed:
                report['passed'] = False
                report['errors'].append(reason)
        else:
            report['warnings'].append("No loss value provided")
            
        # Verify gradients if available
        gradients = result.get('gradients')
        if gradients:
            passed, reason = self.verify_gradients(gradients)
            report['checks'].append({
                'name': 'gradient_verification',
                'passed': passed,
                'reason': reason
            })
            if not passed:
                report['passed'] = False
                report['errors'].append(reason)
                
        # Verify weights if available
        weights = result.get('weights') or result.get('state_dict')
        if weights:
            passed, reason = self.verify_weights(weights)
            report['checks'].append({
                'name': 'weight_verification',
                'passed': passed,
                'reason': reason
            })
            if not passed:
                report['passed'] = False
                report['errors'].append(reason)
                
        return report


class ConsensusVerifier:
    """
    Multi-worker consensus verification.
    Compares results from multiple workers to detect outliers.
    """
    
    def __init__(
        self,
        min_workers: int = 2,
        agreement_threshold: float = 0.8,
        loss_tolerance: float = 0.1
    ):
        """
        Initialize consensus verifier.
        
        Args:
            min_workers: Minimum workers needed for consensus
            agreement_threshold: Fraction of workers that must agree
            loss_tolerance: Relative tolerance for loss comparison
        """
        self.min_workers = min_workers
        self.agreement_threshold = agreement_threshold
        self.loss_tolerance = loss_tolerance
        
    def verify_consensus(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Verify consensus among multiple worker results.
        
        Args:
            results: List of training results from different workers
            
        Returns:
            Consensus verification report
        """
        if len(results) < self.min_workers:
            return {
                'consensus_reached': False,
                'reason': f"Need at least {self.min_workers} workers, got {len(results)}"
            }
            
        # Extract losses
        losses = []
        for r in results:
            loss = r.get('loss') or r.get('final_loss')
            if loss is not None and not np.isnan(loss):
                losses.append(loss)
                
        if len(losses) < self.min_workers:
            return {
                'consensus_reached': False,
                'reason': "Not enough valid loss values"
            }
            
        # Calculate median and check agreement
        median_loss = np.median(losses)
        agreements = sum(
            1 for l in losses 
            if abs(l - median_loss) / max(abs(median_loss), 1e-8) <= self.loss_tolerance
        )
        
        agreement_ratio = agreements / len(losses)
        consensus_reached = agreement_ratio >= self.agreement_threshold
        
        return {
            'consensus_reached': consensus_reached,
            'agreement_ratio': agreement_ratio,
            'median_loss': float(median_loss),
            'num_workers': len(losses),
            'agreeing_workers': agreements,
            'all_losses': losses
        }
        
    def identify_outliers(
        self,
        results: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Identify outlier results that deviate significantly.
        
        Args:
            results: List of training results
            
        Returns:
            Indices of outlier results
        """
        losses = []
        for r in results:
            loss = r.get('loss') or r.get('final_loss', float('inf'))
            losses.append(loss if not np.isnan(loss) else float('inf'))
            
        if len(losses) < 3:
            return []
            
        # Use IQR method for outlier detection
        q1 = np.percentile(losses, 25)
        q3 = np.percentile(losses, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = [
            i for i, l in enumerate(losses)
            if l < lower_bound or l > upper_bound
        ]
        
        return outliers


def create_verification_hash(
    input_hash: str,
    output_hash: str,
    loss: float,
    model_architecture: str
) -> str:
    """
    Create a verification hash for training result.
    
    Args:
        input_hash: Hash of input data
        output_hash: Hash of output weights
        loss: Final training loss
        model_architecture: String description of model
        
    Returns:
        Verification hash
    """
    data = {
        'input': input_hash,
        'output': output_hash,
        'loss': round(loss, 6),
        'architecture': model_architecture
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()


# Convenience function
def verify_training_quality(
    result: Dict[str, Any],
    max_loss: float = 10.0,
    initial_loss: Optional[float] = None,
    max_gradient_norm: float = 100.0
) -> Dict[str, Any]:
    """
    Quick verification of training result quality.
    
    Args:
        result: Training result dictionary
        max_loss: Maximum acceptable loss
        initial_loss: Initial loss before training
        max_gradient_norm: Maximum acceptable gradient norm
        
    Returns:
        Verification report
    """
    thresholds = QualityThresholds(max_loss=max_loss, max_gradient_norm=max_gradient_norm)
    verifier = ModelQualityVerifier(thresholds)
    return verifier.verify_training_result(result, initial_loss)


__all__ = [
    'ModelQualityVerifier',
    'QualityThresholds',
    'ConsensusVerifier',
    'verify_training_quality',
    'create_verification_hash'
]
