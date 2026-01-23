# -*- coding: utf-8 -*-
"""
DEPRECATED MODULE.

The logic from this module has been moved to:
backend.core.metrics_calculator.py

This file is kept temporarily to avoid import errors but should be removed.
Please use MetricsCalculator from backend.core.metrics_calculator instead.
"""

# Re-export key functions from the new centralized calculator if needed for compatibility,
# or just raise a warning. For now, it's a stub.
import warnings


def __getattr__(name):
    warnings.warn(
        "backend.backtesting.tv_metrics is deprecated. Use backend.core.metrics_calculator instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Optionally try to import from new location if completely necessary
    # from backend.core import metrics_calculator
    # return getattr(metrics_calculator, name)
    raise AttributeError(f"Module {__name__} is deprecated and has no attribute {name}")
