#!/usr/bin/env bash
# Explicit physical-GPU selection, detached tmux, and resumable local-only matching.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export SCRATCH_ROOT="${SCRATCH_ROOT:-/scratch/users/jiajun}"
PY="${PYTHON:-$SCRATCH_ROOT/venv-matcher/bin/python}"
CONFIG="${MATCH_CONFIG:-outputs/matching-chewie.yaml}"
BUNDLE="${MATCH_BUNDLE:-exports/medcase24-atoms}"
OUT="${MATCH_OUT:-$SCRATCH_ROOT/clinical-factflow/medcase24-pairs}"
SESSION="${MATCH_SESSION:-clinical-matching}"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${1:-}" != "--inside-tmux" ]]; then
    : "${GPU:?Set GPU to the physical nvidia-smi index; GPU 3 is too small}"
    [[ -x "$PY" && -f "$CONFIG" && -f "$BUNDLE/manifest.json" ]] || {
        echo "Missing Python, resolved configuration or atom bundle" >&2; exit 1;
    }
    UUID="$("$PY" scripts/check_matching_gpu.py --gpu "$GPU")"
    tmux has-session -t "=$SESSION" 2>/dev/null && {
        echo "tmux session $SESSION already exists; inspect it before resuming" >&2; exit 1;
    }
    printf -v COMMAND '%q ' env "GPU=$GPU" "EXPECTED_GPU_UUID=$UUID" \
        "SCRATCH_ROOT=$SCRATCH_ROOT" "PYTHON=$PY" "MATCH_CONFIG=$CONFIG" \
        "MATCH_BUNDLE=$BUNDLE" "MATCH_OUT=$OUT" "MATCH_SESSION=$SESSION" \
        bash "$ROOT/scripts/run_server_matching.sh" --inside-tmux
    tmux new-session -d -s "$SESSION" "$COMMAND"
    echo "Started tmux session: $SESSION; physical GPU $GPU ($UUID)"
    echo "Attach: tmux attach -t $SESSION"
    echo "Log: $OUT/launcher.log"
    exit 0
fi

[[ -n "${TMUX:-}" && -n "${EXPECTED_GPU_UUID:-}" ]] || exit 1
mkdir -p "$OUT"
exec > >(tee -a "$OUT/launcher.log") 2>&1
trap 'status=$?; date -u; echo "Matching command exited with status $status"; exit "$status"' EXIT
date -u
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES="$EXPECTED_GPU_UUID"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 TORCHINDUCTOR_DISABLE=1
export DISABLE_KERNEL_MAPPING=1 FF_ATTN=eager TOKENIZERS_PARALLELISM=false
export HF_HOME="$SCRATCH_ROOT/hf-datasets"
export HF_HUB_CACHE="$HF_HOME/hub" TRANSFORMERS_CACHE="$HF_HOME/hub"
export HF_DATASETS_CACHE="$HF_HOME/datasets" SENTENCE_TRANSFORMERS_HOME="$HF_HOME/sentence-transformers"
export TORCH_HOME="$SCRATCH_ROOT/torch" XDG_CACHE_HOME="$SCRATCH_ROOT/xdg"
export TRITON_CACHE_DIR="$SCRATCH_ROOT/triton" TMPDIR="$SCRATCH_ROOT/tmp"
export PIP_CACHE_DIR="$SCRATCH_ROOT/pip-cache" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" MKL_NUM_THREADS="${MKL_NUM_THREADS:-4}"
mkdir -p "$TMPDIR" "$TORCH_HOME" "$XDG_CACHE_HOME" "$TRITON_CACHE_DIR"
# Resolve again inside tmux before any CUDA allocation. Never fall back to another GPU.
"$PY" scripts/check_matching_gpu.py --gpu "$EXPECTED_GPU_UUID" --verify-torch
"$PY" scripts/server_match.py --bundle "$BUNDLE" --out "$OUT" --config "$CONFIG"
