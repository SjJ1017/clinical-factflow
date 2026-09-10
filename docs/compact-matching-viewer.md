# Compact matching results and offline trace inspection

Matching still writes resumable SQLite ledgers on the server. A completed study can
be exported into two portable stores without repeating text in pair rows:

- `atoms.json.gz`: case-scoped atoms, integer IDs, original node hashes, qualifiers,
  occurrence annotations, quote spans and trace/source bindings.
- `relations.npz`: aligned numeric columns for **every unordered within-case pair**,
  plus sparse full NLI judgment records and policy/runtime/attempt metadata.

No model is called by export or viewing. The original server ledgers remain the
checkpoint and historical source. This export is a completed-study snapshot.

## Export

```sh
python scripts/export_compact_matching.py \
  /scratch/users/jiajun/clinical-factflow \
  /scratch/users/jiajun/clinical-factflow/compact-20260910
```

The current exporter targets the two completed `medcase24-pairs-gpu0` and
`medcase24-pairs-gpu1` shards and the `initial` policy. It is deliberately a small
study utility, not a replacement for the resumable matcher. It verifies all pair
counts, completed annotations and the stored 5.28 classification before exporting.
Do not run it against an active writer or use it for a different policy layout.

`checksums.json` records the SHA-256 of the two finished files. Copy both stores
and this small transfer manifest, then verify the hashes locally.

## Array format

Read with NumPy (`allow_pickle=False`). Each case has a prefix such as `case_00/`;
columns at that prefix have identical row order. `metadata_json` is a UTF-8 JSON
byte array containing the case inventory, global integer-ID offsets and code maps.
Each pair is stored once with `a < b`. Rows are ordered by local `(a, b)`.

| Column | Meaning |
|---|---|
| `a`, `b` | Global unsigned 32-bit atom IDs |
| `relation` | 0 unrelated; 1 a entails b; 2 b entails a; 3 equivalent |
| `stage` | 0 blocker; 1 NLI |
| `cosine`, `lexical`, `combined` | Original float64 blocker values, without downcasting |
| `rank_a`, `rank_b` | Original candidate-ranking positions |
| `token_intersection`, `a_token_count`, `b_token_count` | Original lexical counts |
| `ab_margin`, `ba_margin` | Original float64 directional scores; NaN means no NLI call for this blocker-negative pair |
| `reason`, `judgment_id`, `forced` | Decision provenance; reason codes are in metadata |
| `judgments_json` | Sparse complete judgment payloads, token logits, log masses, probabilities and historical identifiers |
| `audit_json` | Policies, runtime identities and attempts, including historical failures |

All blocker negatives retain an explicit relation code 0. NaN margins do **not**
make their labels unknown. Text/configuration is not repeated in numeric pair rows.
The two-store design reduces representation overhead; storing all blocker values
still has quadratic worst-case space. Compression does not change float precision.

```python
import json
import numpy as np

with np.load("relations.npz", allow_pickle=False) as store:
    metadata = json.loads(store["metadata_json"].tobytes())
    case = metadata["cases"][0]
    prefix = case["prefix"] + "/"
    candidates = store[prefix + "stage"] == 1
    ab = store[prefix + "ab_margin"][candidates]
    ba = store[prefix + "ba_margin"][candidates]
    threshold = 5.28
    # Mutually exclusive: 0, 1, 2, 3 as documented above.
    labels = (ab >= threshold).astype("uint8") + 2 * (ba >= threshold)
```

## Viewer and summary

Place the two files in `runs/server-matching-20260910/compact/`. The builder uses
the original local generation snapshots and sealed atom bundle to validate IDs,
attach source/output spans and honor actual delivery records.

```sh
.venv/bin/python scripts/build_matching_viewer.py
node scripts/check_matching_viewer.cjs findings/medcase24-trace-viewer.html
```

Outputs are an English, self-contained HTML viewer, `matching-summary.json` and
`per-trace-metrics.json`, all under ignored `findings/`. No browser/CDN/API request
is needed to use the viewer. Initial evidence, role prompts and original outputs
are included; reference diagnosis is separate and was never agent input.

The JavaScript check is an offline logic/text test using a minimal DOM harness;
it does not measure browser layout. It checks all 120 selections, all threshold
options, visible-edge eligibility, no synchronous within-round edges, exact text
preservation, direct-only equivalence and the inclusive threshold boundary.

Counts use distinct exact text + qualifier nodes, before semantic clustering.
Report output-only and outputs-plus-initial-materials scopes separately. A pair
is counted once per trace; case-pooled pairs that never coexist in a trace are
excluded. One-way entailment and equivalence are disjoint counts. The optional
complete-link group count is conservative, order-dependent and not a gold fact
count. Viewer connections use direct equivalence, without transitive closure.
