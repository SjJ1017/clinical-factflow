# Resumable study extraction

The user authorized starting M3 extraction on 2026-09-09 for approximately half an hour, stopping by 17:00 Europe/Zurich. The first queue invocation starts at 16:32 and stops by 17:00 (the earlier of 30 minutes and the absolute deadline). It does not run diagnostic judging or NLI matching.

## Run or resume

From the repository root:

```sh
.venv/bin/python -m clinical_factflow.resumable_extraction --study runs/medcase24-approved-20260909 --config configs/extraction/minimax-m3-speed-v4.yaml --out runs/medcase24-m3-extraction-20260909 --minutes 30
```

The same command starts a new queue if absent and resumes it if present. `--minutes 30` limits this session; it does not reset or discard previous progress. For the first session only, add `--stop-at 2026-09-09T17:00:00+02:00`. Do not reuse an expired absolute deadline. A private `runs/medcase24-m3-extraction-20260909/resume.sh` is ready to run another 30-minute session. The `.env` is read locally, selecting only the key named by the saved extraction YAML. There is no API 1 fallback.

The initial inventory contains 1,487 extraction tasks: 1,080 output turns, 383 unique evidence segments and 24 unique common-metadata texts, across 120 generation runs. It maps to 3,355 original per-run records. Shared evidence is reused only within the same case and source identity/text; common metadata is reused within the same case and identical text. Output identities include the generation run and turn, so independent agent/run occurrences do not collide. Every alias retains its original run, record ID and provenance in the task bindings.

## Durable boundaries

- `manifest.json` freezes the extraction YAML, source hashes, parent manifests/artifacts, task texts and all original record bindings. Resume refuses mismatched config, code, source inputs or parent artifacts.
- `tasks/<task-id>/checkpoints/*.json` saves successful extraction and atomization requests independently, keyed by model settings, exact prompt, schema and sample identity. A pause after initial extraction reuses its parents and performs only missing atomization batches.
- `tasks/<task-id>/calls/*.json` retains every attempt, including failures. If the process was interrupted after a successful raw response was saved but before its checkpoint, resume recovers and validates that response instead of making another call. Each raw transport attempt uses the existing client's attempt counter of one; retries are represented by multiple distinct raw calls for that sample, not by a globally incremented `attempt` field.
- `results/<task-id>.json` contains a sealed completed extraction result. Resume checks its integrity and original record hash and skips it. These files, not a potentially stale status counter, are authoritative.
- JSON writes use a per-writer temporary file, fsync and atomic replacement. No failed or partial response is promoted into a completed result. Corrupt checkpoints fail closed rather than silently rerunning or being accepted.
- An exclusive OS lock prevents a second queue process from consuming the same task set concurrently. At most six record workers are active, each making at most one request at a time.

This is an extraction-stage deterministic work cache, never a generation cache. Cached analysis is safe only for the exact saved model/prompt/schema and text. It does not make independent agent generations interchangeable.

## Stopping

The dispatcher stops issuing work five seconds before its deadline. Each request timeout is capped by the remaining session budget, and retries re-check the deadline. SIGINT/SIGTERM ask the dispatcher to pause and save completed work. At the absolute deadline a watchdog forces process exit if a socket or other operation is still hung, writing `hard-stop.json`. A forcibly interrupted in-flight request may have unknown provider usage; its previous successful stages remain resumable. No process should continue running beyond the requested cutoff.

Three consecutive record failures pause dispatch to avoid spending through a systemic outage. Failed records remain pending for an explicit later resume. `status.json` and `sessions/*.json` expose completion/error counts; `pending` includes every task without a finished result, including failed or in-flight ones. After a hard stop, recompute exact completion from `results/` before reporting it.

## Output use

Task results remain under this independent extraction stage and do not mutate historical generation run configs or artifacts. Read the task's `bindings` to project reused source/metadata facts back onto an original run. Original source facts and actually delivered self/peer output facts can then form each input profile under the saved delivery rules. Matching and downstream export are separate stages and have not been run by this queue.

Preserve the saved source snapshot if the implementation is changed later. Resume refuses source drift; restore the recorded extraction implementation rather than mixing measurement versions. Do not delete a queue directory or its checkpoints to restart a stalled record.

## Validation

61 offline tests pass, including pause after initial extraction and resume without re-extraction, completed-record reuse with zero additional calls, corrupt-checkpoint rejection, sample/prompt separation, recovery from successful raw responses, and a real subprocess hard-deadline test with a deliberately hung fake model (no network). The full 120-run inventory was dry-checked before any production request; parent raw config hashes are checked without reserializing through a newer schema that may introduce default fields.
