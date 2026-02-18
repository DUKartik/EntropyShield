import random
import numpy as np
import torch
import hashlib
import os
import logging

logger = logging.getLogger("determinism")

def set_global_seed(seed: int = 42):
    """
    Sets the random seed for Python, NumPy, PyTorch, and CUDA to ensure reproducible results.
    Call this before every major stochastic operation (e.g., model inference).
    """
    # 1. Python random
    random.seed(seed)
    
    # 2. NumPy
    np.random.seed(seed)
    
    # 3. PyTorch
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)  # if you are using multi-GPU.
    
    # 4. CuDNN Determinism
    # Benchmarking causes the cudnn backend to search for the fastest convolution algorithm
    # which can result in non-deterministic behavior.
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    
    # 5. Deterministic Algorithms (Strict Mode)
    # WARNING: Some operations (like Resize with bicubic on GPU) might not support this.
    # Use with caution. For now, we rely on cudnn.deterministic=True.
    # os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    # torch.use_deterministic_algorithms(True)
    
    # logger.info(f"Global seed set to {seed}. Determinism enforced.")

def get_tensor_fingerprint(tensor, name: str = "tensor") -> str:
    """
    Returns a short hash + stats of a tensor to track data consistency.
    Useful for debugging where data changes between runs.
    """
    try:
        if isinstance(tensor, torch.Tensor):
             # Move to CPU for analysis
             t_cpu = tensor.detach().cpu().float()
             min_v = t_cpu.min().item()
             max_v = t_cpu.max().item()
             mean_v = t_cpu.mean().item()
             # Create simple hash from the raw bytes of first 1000 elements (speed)
             # or purely stats if data is massive
             
             # Robust Hash: Convert to numpy, ensure consistent endianness
             data_bytes = t_cpu.numpy().tobytes()
             sha = hashlib.sha256(data_bytes).hexdigest()[:8]
             
             return f"[{name}] Shape: {list(tensor.shape)} | Range: [{min_v:.4f}, {max_v:.4f}] | Mean: {mean_v:.4f} | Hash: {sha}"
             
        elif isinstance(tensor, np.ndarray):
             min_v = tensor.min()
             max_v = tensor.max()
             mean_v = tensor.mean()
             data_bytes = tensor.tobytes()
             sha = hashlib.sha256(data_bytes).hexdigest()[:8]
             
             return f"[{name}] Shape: {tensor.shape} | Range: [{min_v:.4f}, {max_v:.4f}] | Mean: {mean_v:.4f} | Hash: {sha}"
             
    except Exception as e:
        return f"[{name}] Fingerprint Failed: {str(e)}"
    
    return f"[{name}] Unknown Type"
