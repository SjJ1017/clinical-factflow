import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "gpu_guard", Path(__file__).parents[1] / "scripts/check_matching_gpu.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

GPUS = "0, GPU-busy, Ada, 46068, 22000, 94\n3, GPU-small, 2080 Ti, 11264, 2, 0\n4, GPU-free, Ada, 46068, 2, 0\n"


def test_selects_physical_uuid_and_rejects_busy_or_small_cards():
    assert guard.select_idle_gpu(GPUS, "GPU-busy, 42", "4")["uuid"] == "GPU-free"
    assert guard.select_idle_gpu(GPUS, "", "GPU-free")["index"] == "4"
    for selector in ["0", "3", "5"]:
        with pytest.raises(RuntimeError):
            guard.select_idle_gpu(GPUS, "GPU-busy, 42", selector)
    with pytest.raises(RuntimeError, match="existing compute process"):
        guard.select_idle_gpu(GPUS, "GPU-free, 21", "4")
    with pytest.raises(RuntimeError, match="not idle"):
        guard.select_idle_gpu(GPUS.replace("46068, 2, 0", "46068, 2, 94"), "", "4")


def test_unknown_telemetry_fails_closed():
    with pytest.raises((RuntimeError, ValueError)):
        guard.select_idle_gpu(GPUS.replace("46068, 2, 0", "46068, 2, N/A"), "", "4")
