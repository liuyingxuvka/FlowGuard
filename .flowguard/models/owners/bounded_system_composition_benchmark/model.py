"""Executable evidence owner for the Emergent Integration Benchmark."""

from examples.bounded_system_composition.benchmark import run_bounded_system_benchmark


def validate_benchmark() -> bool:
    return run_bounded_system_benchmark().ok


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
