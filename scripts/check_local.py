"""Read-only environment check. Does not download or load model weights."""
import os
import platform

print("Python:", platform.python_version())
print("CUDA_VISIBLE_DEVICES:", os.environ.get("CUDA_VISIBLE_DEVICES", "not set"))
print("HF_HOME:", os.environ.get("HF_HOME", "Hugging Face default cache"))
try:
    import torch
    import transformers
except ImportError as exc:
    raise SystemExit(f"Missing local runtime dependency: {exc.name}. Install .[local].")
print("torch:", torch.__version__, "transformers:", transformers.__version__)
print("CUDA available:", torch.cuda.is_available())
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    free,total = torch.cuda.mem_get_info(i)
    print(f"Visible GPU {i}: {p.name}; compute {p.major}.{p.minor}; free {free/2**30:.1f}/{total/2**30:.1f} GiB")
