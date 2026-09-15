"""
AgentArora Privacy Engine - Benchmark Test Suite Package.

Contains evaluation benchmark datasets and audit scripts for validating
privacy detection rules across all taxonomy categories.
"""

from .test_privacy_engine import BENCHMARK_DATASET, run_benchmark_audit

__all__ = [
    "BENCHMARK_DATASET",
    "run_benchmark_audit",
]