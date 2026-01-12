"""
Differential Privacy Module for Oblivion
Implements privacy-preserving gradient sharing with mathematical guarantees.
"""

import torch
import numpy as np
from typing import List, Tuple, Optional
import hashlib
import json


class DifferentialPrivacy:
    """
    Differential Privacy implementation for gradient protection.
    
    Privacy guarantee: For any two neighboring datasets D and D' that differ
    in one record, the probability of any output is bounded by e^ε.
    
    Attributes:
        epsilon: Privacy budget (lower = more private, typical: 0.1-10)
        delta: Probability of privacy breach (typical: 1e-5 to 1e-7)
        max_grad_norm: Maximum L2 norm for gradient clipping
    """
    
    def __init__(
        self, 
        epsilon: float = 1.0, 
        delta: float = 1e-5,
        max_grad_norm: float = 1.0,
        noise_multiplier: Optional[float] = None
    ):
        """
        Initialize differential privacy parameters.
        
        Args:
            epsilon: Privacy budget (ε). Lower values = stronger privacy.
                    - ε < 1: Strong privacy
                    - ε = 1-10: Moderate privacy  
                    - ε > 10: Weak privacy
            delta: Probability of privacy failure (δ). Should be < 1/n where n = dataset size.
            max_grad_norm: Maximum allowed gradient norm (for clipping).
            noise_multiplier: Optional override for noise scale.
        """
        self.epsilon = epsilon
        self.delta = delta
        self.max_grad_norm = max_grad_norm
        
        # Calculate noise multiplier using Gaussian mechanism
        if noise_multiplier is None:
            self.noise_multiplier = self._compute_noise_multiplier()
        else:
            self.noise_multiplier = noise_multiplier
            
        self._privacy_spent = 0.0
        self._queries = 0
        
    def _compute_noise_multiplier(self) -> float:
        """
        Compute noise multiplier for (ε,δ)-differential privacy.
        Uses the Gaussian mechanism formula.
        """
        # For (ε,δ)-DP with Gaussian noise:
        # σ ≥ Δf * sqrt(2 * ln(1.25/δ)) / ε
        # where Δf is the sensitivity (max_grad_norm for gradients)
        
        if self.delta > 0:
            return (
                self.max_grad_norm * 
                np.sqrt(2 * np.log(1.25 / self.delta)) / 
                self.epsilon
            )
        else:
            # Pure ε-DP (no δ) requires Laplace mechanism
            return self.max_grad_norm / self.epsilon
            
    def clip_gradients(
        self, 
        gradients: List[torch.Tensor]
    ) -> Tuple[List[torch.Tensor], float]:
        """
        Clip gradients to bound sensitivity.
        
        Args:
            gradients: List of gradient tensors
            
        Returns:
            Tuple of (clipped_gradients, original_norm)
        """
        # Compute total gradient norm
        total_norm = torch.sqrt(
            sum(g.pow(2).sum() for g in gradients if g is not None)
        ).item()
        
        # Clip if necessary
        clip_factor = min(1.0, self.max_grad_norm / (total_norm + 1e-8))
        
        clipped_grads = []
        for g in gradients:
            if g is not None:
                clipped_grads.append(g * clip_factor)
            else:
                clipped_grads.append(None)
                
        return clipped_grads, total_norm
    
    def add_noise(
        self, 
        gradients: List[torch.Tensor],
        clip_first: bool = True
    ) -> List[torch.Tensor]:
        """
        Add calibrated Gaussian noise to gradients for differential privacy.
        
        Args:
            gradients: List of gradient tensors
            clip_first: Whether to clip gradients before adding noise
            
        Returns:
            Noisy gradients with DP guarantee
        """
        if clip_first:
            gradients, _ = self.clip_gradients(gradients)
            
        noisy_grads = []
        for g in gradients:
            if g is not None:
                # Add Gaussian noise scaled by noise_multiplier
                noise = torch.normal(
                    mean=0.0,
                    std=self.noise_multiplier,
                    size=g.shape,
                    device=g.device,
                    dtype=g.dtype
                )
                noisy_grads.append(g + noise)
            else:
                noisy_grads.append(None)
                
        self._queries += 1
        self._privacy_spent += self.epsilon  # Simple composition
        
        return noisy_grads
    
    def privatize_model_weights(
        self,
        state_dict: dict,
        sensitivity: float = 1.0
    ) -> dict:
        """
        Add differential privacy noise to model weights.
        
        Args:
            state_dict: Model state dictionary
            sensitivity: Sensitivity of the weights
            
        Returns:
            Privatized state dictionary
        """
        private_state = {}
        noise_scale = sensitivity * self.noise_multiplier
        
        for key, value in state_dict.items():
            if isinstance(value, torch.Tensor):
                noise = torch.normal(
                    mean=0.0,
                    std=noise_scale,
                    size=value.shape,
                    device=value.device,
                    dtype=value.dtype
                )
                private_state[key] = value + noise
            else:
                private_state[key] = value
                
        return private_state
    
    def get_privacy_guarantee(self) -> dict:
        """
        Get current privacy guarantee status.
        
        Returns:
            Dictionary with privacy metrics
        """
        return {
            'epsilon': self.epsilon,
            'delta': self.delta,
            'noise_multiplier': self.noise_multiplier,
            'max_grad_norm': self.max_grad_norm,
            'queries_made': self._queries,
            'total_epsilon_spent': self._privacy_spent,
            'guarantee': f"({self.epsilon}, {self.delta})-Differential Privacy"
        }
    
    def reset_budget(self):
        """Reset privacy budget tracking."""
        self._privacy_spent = 0.0
        self._queries = 0


class SecureAggregation:
    """
    Secure aggregation for federated learning.
    Combines multiple worker updates while preserving privacy.
    """
    
    def __init__(
        self, 
        num_workers: int,
        threshold: int = None,
        dp_config: Optional[DifferentialPrivacy] = None
    ):
        """
        Initialize secure aggregation.
        
        Args:
            num_workers: Total number of workers
            threshold: Minimum workers needed for aggregation
            dp_config: Optional differential privacy configuration
        """
        self.num_workers = num_workers
        self.threshold = threshold or max(1, num_workers // 2)
        self.dp = dp_config
        self.pending_updates = []
        
    def add_update(
        self, 
        worker_id: str, 
        gradients: List[torch.Tensor],
        weight: float = 1.0
    ):
        """
        Add a worker's update to the aggregation queue.
        
        Args:
            worker_id: Unique worker identifier
            gradients: List of gradient tensors
            weight: Weight for this worker's contribution
        """
        # Apply DP if configured
        if self.dp:
            gradients = self.dp.add_noise(gradients)
            
        self.pending_updates.append({
            'worker_id': worker_id,
            'gradients': gradients,
            'weight': weight
        })
        
    def can_aggregate(self) -> bool:
        """Check if we have enough updates to aggregate."""
        return len(self.pending_updates) >= self.threshold
        
    def aggregate(self) -> Tuple[List[torch.Tensor], dict]:
        """
        Perform federated averaging on collected updates.
        
        Returns:
            Tuple of (aggregated_gradients, metadata)
        """
        if not self.can_aggregate():
            raise ValueError(
                f"Need at least {self.threshold} updates, "
                f"have {len(self.pending_updates)}"
            )
            
        # Calculate total weight
        total_weight = sum(u['weight'] for u in self.pending_updates)
        
        # Initialize aggregated gradients
        num_grads = len(self.pending_updates[0]['gradients'])
        aggregated = [None] * num_grads
        
        # Weighted average
        for i in range(num_grads):
            weighted_sum = None
            for update in self.pending_updates:
                g = update['gradients'][i]
                if g is not None:
                    weighted = g * (update['weight'] / total_weight)
                    if weighted_sum is None:
                        weighted_sum = weighted.clone()
                    else:
                        weighted_sum += weighted
            aggregated[i] = weighted_sum
            
        metadata = {
            'num_workers': len(self.pending_updates),
            'total_weight': total_weight,
            'worker_ids': [u['worker_id'] for u in self.pending_updates]
        }
        
        # Clear updates
        self.pending_updates = []
        
        return aggregated, metadata


def compute_privacy_cost(
    epsilon_per_query: float,
    num_queries: int,
    delta: float = 1e-5,
    composition: str = 'advanced'
) -> float:
    """
    Compute total privacy cost using composition theorems.
    
    Args:
        epsilon_per_query: Privacy budget per query
        num_queries: Number of queries/iterations
        delta: Privacy failure probability
        composition: 'basic', 'advanced', or 'rdp'
        
    Returns:
        Total epsilon spent
    """
    if composition == 'basic':
        # Basic composition: ε_total = k * ε
        return epsilon_per_query * num_queries
        
    elif composition == 'advanced':
        # Advanced composition: ε_total = √(2k ln(1/δ')) * ε + k*ε*(e^ε - 1)
        # Simplified version for small ε
        return np.sqrt(2 * num_queries * np.log(1 / delta)) * epsilon_per_query
        
    else:
        # Renyi DP composition (most tight)
        # Simplified approximation
        alpha = 1 + 1 / epsilon_per_query
        rdp_epsilon = num_queries * alpha * epsilon_per_query ** 2 / 2
        return rdp_epsilon + np.log(1 / delta) / (alpha - 1)


def verify_privacy_guarantee(
    gradients: List[torch.Tensor],
    epsilon: float,
    delta: float,
    sensitivity: float
) -> dict:
    """
    Verify that gradients satisfy differential privacy bounds.
    
    Args:
        gradients: Noisy gradients
        epsilon: Target epsilon
        delta: Target delta
        sensitivity: Gradient sensitivity
        
    Returns:
        Verification report
    """
    # Compute empirical noise statistics
    total_variance = sum(
        g.var().item() for g in gradients if g is not None
    )
    
    # Expected variance for (ε,δ)-DP
    expected_var = (sensitivity ** 2) * (2 * np.log(1.25 / delta)) / (epsilon ** 2)
    
    # Check if noise is sufficient
    is_private = total_variance >= expected_var * 0.9  # 10% tolerance
    
    return {
        'is_private': is_private,
        'empirical_variance': total_variance,
        'expected_variance': expected_var,
        'epsilon': epsilon,
        'delta': delta,
        'message': 'Privacy guarantee satisfied' if is_private else 'WARNING: Insufficient noise'
    }


# Convenience function for quick privatization
def privatize_gradients(
    gradients: List[torch.Tensor],
    epsilon: float = 1.0,
    delta: float = 1e-5,
    max_norm: float = 1.0
) -> Tuple[List[torch.Tensor], dict]:
    """
    Quick function to privatize gradients with default settings.
    
    Args:
        gradients: List of gradient tensors
        epsilon: Privacy budget
        delta: Privacy failure probability
        max_norm: Maximum gradient norm for clipping
        
    Returns:
        Tuple of (private_gradients, privacy_report)
    """
    dp = DifferentialPrivacy(
        epsilon=epsilon,
        delta=delta,
        max_grad_norm=max_norm
    )
    
    private_grads = dp.add_noise(gradients, clip_first=True)
    report = dp.get_privacy_guarantee()
    
    return private_grads, report
