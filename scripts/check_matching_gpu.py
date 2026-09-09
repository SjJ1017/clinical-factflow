"""Fail closed unless an explicitly selected physical GPU is idle and large enough."""

import argparse
import json
import os
import subprocess


def query(fields, kind="gpu"):
    return subprocess.check_output(
        ["nvidia-smi", f"--query-{kind}={fields}", "--format=csv,noheader,nounits"],
        text=True,
    )


def select_idle_gpu(gpus, apps, selected):
    rows = [
        list(map(str.strip, line.split(",")))
        for line in gpus.splitlines()
        if line.strip()
    ]
    matches = [r for r in rows if selected in (r[0], r[1])]
    if len(matches) != 1:
        raise RuntimeError("GPU selector must identify exactly one physical GPU")
    index, uuid, name, total, used, util = matches[0]
    if int(total) < 38000:
        raise RuntimeError(
            f"GPU {index} ({name}) has insufficient memory for default BF16 Qwen14B"
        )
    if any(line.split(",")[0].strip() == uuid for line in apps.splitlines()):
        raise RuntimeError(
            f"GPU {index} has an existing compute process; refusing to share it"
        )
    if int(used) > 256 or int(util) > 0:
        raise RuntimeError(
            f"GPU {index} is not idle: {used} MiB used, {util}% utilization"
        )
    return {"index": index, "uuid": uuid, "name": name, "total_mib": int(total)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gpu", required=True)
    p.add_argument("--verify-torch", action="store_true")
    args = p.parse_args()
    selected = select_idle_gpu(
        query("index,uuid,name,memory.total,memory.used,utilization.gpu"),
        query("gpu_uuid,pid", "compute-apps"),
        args.gpu,
    )
    if not args.verify_torch:
        print(selected["uuid"])
        return
    if os.environ.get("CUDA_VISIBLE_DEVICES") != selected["uuid"]:
        raise RuntimeError(
            "CUDA_VISIBLE_DEVICES must be the selected physical GPU UUID"
        )
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID":
        raise RuntimeError("CUDA_DEVICE_ORDER must be PCI_BUS_ID")
    import torch

    if torch.cuda.device_count() != 1:
        raise RuntimeError("Expected exactly one CUDA-visible GPU")
    props = torch.cuda.get_device_properties(0)
    actual = str(props.uuid)
    if (
        actual.removeprefix("GPU-").lower()
        != selected["uuid"].removeprefix("GPU-").lower()
    ):
        raise RuntimeError(f"Physical GPU UUID mismatch: {actual}")
    torch.zeros(8, device="cuda:0").sum().item()
    print(
        json.dumps(
            {
                **selected,
                "logical_device": "cuda:0",
                "torch_uuid": actual,
                "torch_version": torch.__version__,
                "kernel_check": "passed",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
