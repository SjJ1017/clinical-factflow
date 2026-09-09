# Server annotation validation — 2026-09-09

The portable server path is implemented and tested. **Real Qwen3-14B GPU inference and clinical matching accuracy have not been measured.** The tests use random logits, with either random embeddings or the actual cached BGE model. Instructions: [server workflow](server-matching.md).

## Executed checks

| Check | Result |
|---|---|
| Full offline suite before GPU-launcher additions | 80 passed |
| Fresh Git clone, independent Python 3.12.14, installed package | 78 passed, 1 skipped (PyTorch-dependent adapter test; PyTorch absent in this minimal environment) |
| Fresh-clone smoke with API-key environment variables removed | Completed; imports resolve to the new environment's installed package |
| Synthetic atoms + random embeddings + random logits | 2 cases, 48 nodes, 552/552 pair rows; 120 pairs initially sent to the mock scorer |
| Synthetic atoms + real BGE + random logits | 2 cases, 48 nodes, 552/552 pair rows; 342 pairs initially sent to the mock scorer |
| Actual extracted atoms + real BGE + random logits | 775 nodes, 299,925/299,925 pair rows and JSONL records; SQLite integrity check `ok` |
| Completed-run resume | Zero additional judgments |
| Threshold change | Existing raw scores reused; newly promoted blocker negatives become pending until scored |
| Selective second judgment | Original observations remain intact; unselected pairs inherit the specified parent policy |
| Failure injection | Missing/duplicate results, NaN, inconsistent margins and exceptions retain null/pending labels |

The scale test used an explicitly partial input snapshot, with `input_complete: false` and `test_data: true` retained in every exported row. The actual BGE/blocker labeled 293,593 pairs UNRELATED and passed 6,332 pairs to the random scorer. Those random labels are solely interface test data. No random result is an experimental finding.

The scale test's initial SQLite ledger was about 147.5 MiB. It stores all 299,925 pairs, not just candidates; an additional complete threshold policy increased it to about 222 MiB. Full-pair storage grows quadratically with each case's distinct-node count, while the costly model stage is limited to the escalated subset.

Local artifacts are ignored by Git:

- `runs/pair-bge-release-20260909/`
- `runs/pair-one-case-release-20260909/`
- The independent clone and Python 3.12 environment were under `/tmp/`; they are verification workspaces, not dependencies.

## Completed production extraction and workload

All **1,487 / 1,487** records and **120 / 120** trace extractions are complete: 1,080 outputs, 383 unique sources and 24 shared metadata records. All result/task/record hashes and the six frozen extraction source hashes verified; the queue lock is free.

There are 38,229 atomic mentions, of which 37,720 have located quotations (98.67%). Location is not semantic accuracy or recall. Eight failed stages used audited schema-only retries with distinct request keys; successful stages were reused. No atom attributes were added, no facts were hand-edited, and no returned thinking blocks were observed.

The user authorized API 2 Go balance after the subscription quota pause. The remaining extraction completed with **$1.88299488 in provider-reported balance charges**, summed from `response.cost`, including charged validation failures. This is separate from historical subscription allowance. The earlier quota and timed-session summaries remain preserved; the final private audit is `runs/medcase24-m3-extraction-20260909/sessions/2026-09-09-final-summary.json`.

The complete archive is `exports/medcase24-atoms.tar.gz` (about 6.8 MiB), transferred separately by SCP. Its manifest hash is `96ab2cff041d161e2c1c6b0371a532f7298c12472608e97d9c0ea7f0af952ee3`. It contains 24 cases, 30,945 distinct nodes and **20,196,086 possible same-case pairs**, preserving all occurrence bindings. The earlier partial archive is diagnostic history only.

The complete real-BGE workload profile (`runs/blocker-workload-full-20260909/`) saved every pair's similarity, lexical components and endpoint ranks:

| Blocker threshold | Top-K | Unique candidate pairs | GPU hours at 7.25 bidirectional pairs/s |
|---|---|---|---|
| **0.62** | **12** | **256,811** | **9.84** |
| 0.70 | 12 | 253,187 | 9.70 |
| 0.62 | 8 | 172,606 | 6.61 |
| 0.62 | 20 | 423,549 | 16.23 |

Keep the approved defaults, 0.62/top12/batch16/NLI margin5.28. Top-K controls most of the workload; increasing the threshold to 0.70 saves little. The estimate covers model work, excluding initialization, geometry and file export; it is not a new GPU benchmark. Of the default shared-case candidates, 148,660 never co-occur within one trace. Per-trace candidate counts average 1,030.36 and overlap; the shared-case total above is the actual execution pool.

## Chewie preparation; GPU run deliberately not started

The server repository and complete atom archive are installed. The existing `/scratch/users/jiajun/venv-matcher` and cached Qwen/BGE weights are reused; no old project code is required at runtime. A CPU random-interface smoke passed on Chewie (552/552 pairs, completed resume adds zero judgments). The startup guard has offline tests for physical index/UUID selection, busy processes, high utilization, insufficient memory and unavailable telemetry.

User requested stopping after available CPU tests and waiting for a later instruction. **No GPU matching process or automatic idle-GPU waiter was started.** Physical GPU 3 is an 11 GiB RTX 2080 Ti and cannot hold default BF16 Qwen14B. Other GPUs were occupied, including GPU 1 despite its large remaining memory.

`scripts/run_server_matching.sh` starts a detached tmux session only for an explicitly selected idle, sufficiently large GPU. It resolves the physical index to its UUID, sets both `CUDA_DEVICE_ORDER=PCI_BUS_ID` and UUID-valued `CUDA_VISIBLE_DEVICES`, rechecks inside tmux and verifies PyTorch's device UUID/kernel before model loading. It never falls back to another GPU. The real CUDA verification remains deferred until an eligible card is available.
