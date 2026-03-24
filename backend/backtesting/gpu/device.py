"""
GPU device initialization and availability detection.

Extracted from gpu_optimizer.py (lines 1–142).
Handles lazy CuPy import, CUDA path setup, and GPU availability state.
"""

import os

from loguru import logger

# GPU state — initialized lazily on first use
GPU_AVAILABLE = None  # None = not checked yet, True/False after check
cp = None  # CuPy module reference (None when GPU unavailable)
GPU_NAME = "Not initialized"
_gpu_init_done = False


def _setup_cuda_path() -> str | None:
    """Add CUDA bin directory to PATH so NVRTC DLLs can be found."""
    cuda_paths = [
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
    ]

    current_path = os.environ.get("PATH", "")
    for cuda_bin in cuda_paths:
        if os.path.exists(cuda_bin) and cuda_bin not in current_path:
            os.environ["PATH"] = cuda_bin + os.pathsep + current_path
            logger.debug(f"Added CUDA to PATH: {cuda_bin}")
            return cuda_bin
    return None


def _init_gpu() -> bool:
    """
    Initialize GPU/CuPy on first use (lazy loading).

    Returns:
        True if GPU is available and functional, False otherwise.
    """
    global GPU_AVAILABLE, cp, GPU_NAME, _gpu_init_done

    if _gpu_init_done:
        return GPU_AVAILABLE  # type: ignore[return-value]

    _gpu_init_done = True
    _setup_cuda_path()

    try:
        import cupy as _cp

        # Perform a real operation to verify GPU is functional
        _test = _cp.array([1.0, 2.0, 3.0], dtype=_cp.float64)
        _result = _cp.diff(_test)
        _cp.cuda.Stream.null.synchronize()
        del _test, _result

        cp = _cp
        GPU_AVAILABLE = True

        try:
            device = _cp.cuda.Device()
            mem_info = device.mem_info
            GPU_NAME = f"GPU {device.id} ({mem_info[1] / 1024**3:.1f}GB)"
        except Exception:
            GPU_NAME = "NVIDIA GPU"

        logger.info(f"🚀 GPU acceleration enabled: {GPU_NAME}")
        return True

    except Exception as e:
        cp = None
        GPU_AVAILABLE = False
        GPU_NAME = "None"
        logger.info(f"GPU not available (using CPU): {e}")
        return False


def is_gpu_available() -> bool:
    """Check if GPU is available, initializing lazily on first call."""
    if GPU_AVAILABLE is None:
        _init_gpu()
    return bool(GPU_AVAILABLE)
