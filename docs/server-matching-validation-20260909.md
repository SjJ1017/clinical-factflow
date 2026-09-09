# Server annotation validation — 2026-09-09

The portable server path is implemented and tested. **Real Qwen3-14B GPU inference and clinical matching accuracy have not been measured.** The tests use random logits, with either random embeddings or the actual cached BGE model. Instructions: [server workflow](server-matching.md).

## Executed checks

| Check | Result |
|---|---|
| Full offline suite in the development environment | 79 passed |
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

## Production extraction continuation

The previous 616-record queue was resumed using M3, thinking disabled, six workers and API 2. **541 additional records completed**, bringing the total to **1,157 / 1,487**, with **330 remaining**.

- Completed: 755 output records, 378 unique source records, 24 shared-metadata records.
- 27,296 atomic mentions; 390 have no exact located quote. This is a location audit, not a semantic accuracy estimate.
- All records and the six frozen extraction source hashes verified; the queue lock is free.
- 67 / 120 traces have every required extraction record completed.
- Known cumulative Go allowance from returned usage is about $4.700, including the earlier session. This is not a cash invoice; requests without returned usage are separate in the audit.

The provider returned HTTP 429 with `GoUsageLimitError`, `limitName: weekly`, and an approximately four-day reset. The queue stopped after consecutive failures. A single diagnostic retry confirmed the weekly limit. No paid-balance fallback was enabled. Successful initial-extraction and atomization checkpoints remain reusable.

A separate, tested `scripts/recover_extraction_schema.py` prepares schema-only retries for failed stages, with different request keys and explicit audit metadata. It has **not been executed on production records**, because API 2's quota is exhausted. It neither changes the atom schema nor hand-maps invalid values.

The current transfer snapshot is `exports/medcase24-atoms-partial-20260909.tar.gz` (4.85 MiB): 24 cases, 22,587 distinct nodes, 11,929,499 possible same-case pairs. It is explicitly incomplete. The main server wrapper refuses to publish a complete-study export from it. For interface diagnostics, the lower-level `run --allow-partial` command is available; a completed extraction must produce a new complete bundle and matching output because the ranking pool changes when nodes are added.

The current user decision is whether to use API 1's Go allowance or retain the checkpoint until API 2 resets. The full extraction has not been reported as complete.
