# MUSE Live Smoke Verification Record — LIVE_SMOKE_VERIFIED

**Status: LIVE_SMOKE_VERIFIED** (user-run `muse/live_smoke.py` output, reported 2026-10-31)

| Field | Value |
| :--- | :--- |
| Tool | `muse/live_smoke.py` |
| Model ID | `muse-spark-1.3` (`MUSE_MODEL_NAME`, default confirmed in output) |
| Endpoint | `MUSE_MODEL_API_URL` = `https://api.meta.ai/v1` (+ `/chat/completions`) |
| Auth | Bearer, read from `MUSE_MODEL_API_KEY` (value NEVER printed/stored; presence-only check) |
| Result | `status=OK`, `verdict=ok` |
| Observed latency | 7514 ms (one request) |
| Model-independence proof | baseline metrics identical with/without review: **True**; DAAS-V2V metrics identical: **True** |
| Test outcome | **SMOKE PASS** (live review + sandboxed E2E ×2 with identical metrics) |

## Integration contract (exact scope)

- **One advisory request per run** — bounded by construction (single call
  site, no retry loop, no tool-call layer). NOT multi-turn autonomous tool
  execution; nothing in the docs or code implies otherwise.
- The review is advisory provenance only: it does not gate, alter, or
  compute any experiment value. Local strict schema validation
  (`muse/scenario.py`) is the only gate; all metrics come from the existing
  `WorldMetrics` implementations. The identical-metrics proof above is the
  enforced demonstration.

## Provenance (code hashes at verification)

- `muse/spark_adapter.py` sha256 `a677f15eecf3e33950cd8315d7ab5a7041a60e0308c44f0fcb9ea3a8f13c351f`
- `muse/live_smoke.py` sha256 `5ca552859b8180ba3f7c383eab8941c64ad1ca6793692b901c321b829ad04f65`
- `muse/adapter.py` sha256 `760c16761db607ce9e7c512d58652ce14b1df279aa1fa52f15903bb60f987847`

Prior failed attempts (both resolved, logged in CHANGES.md #16/#17):
content=None TypeError at L135 → controlled statuses + diagnostics;
`finish_reason=length` at max_tokens=256 → 2048 default (+`MUSE_MODEL_MAX_TOKENS`).

## Credential hygiene (verified)

- No key values in source, logs, reports, metadata or Git diffs (greps:
  0 hits). RUNBOOK documents `export` in the USER's shell only.
- Sandbox artifacts from the smoke ran in temp dirs; nothing sensitive
  written under `results/`.
