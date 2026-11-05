# EXPORT_MANIFEST — das-scenario-pilot public snapshot

Snapshot date: 2026-11-05 (UTC). Source workspace:
`/mnt/d/daas ,ml/sih 26` at git HEAD `9f9c19ec9ca615e35c742ac5ab58e8ca373a917e`
(branch `main`, ~452 modified/untracked entries — source workspace left
completely untouched; no staging/committing/cleaning performed there).

This export was assembled by an explicit allowlist copy, then scanned for
secrets/personal data before publication. `.git/` of the source workspace
was NOT copied; the public repository has a fresh history.

## Included (and why)

| Path | Why |
|---|---|
| `src/daas_impl/` | deterministic simulation core; needed by experiments/tests |
| `experiments/` | reproducible seeded runners + ablations + vertical slices |
| `muse/` | scenario schema, adapters, reporting, vertical slice, muse tests |
| `tests/run_unit_tests.py` | core unit test suite (33 tests) |
| `scripts/` | analysis/figure/manifest helpers used by experiments |
| `firmware/common/`, `firmware/vehicle-node/`, `firmware/vehicle-node-2/` | production firmware + shared protocol headers |
| `firmware/diagnostics/` | H4 bench diagnostic sketches + manual flash guide (paths sanitized) |
| `firmware/vs1_ack_rtt/` | VS1 host-check reference sketch |
| `firmware/tests/` | host C++ test suites + runners (prebuilt `.exe` binaries excluded) |
| `docs/architecture|protocol|experiments|validation|project|research|problem-statement/` | public-safe engineering documentation |
| `results/derived/`, `results/metadata/` | seeded summary/metadata JSONs (verified reproducible inputs/outputs) |
| `results/reports/` (subset) | ABL2X2, D2 continuity, MUSE vertical-slice reports only |
| `README.md`, `LICENSE`, `NOTICE`, `CITATION.cff`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.gitignore`, `.env.example` | repository front matter (license switched MIT→Apache-2.0 in this public release; source workspace file untouched) |
| `docs/VALIDATION_STATUS.md`, `docs/SAFETY_AND_LIMITATIONS.md`, `docs/LICENSING.md`, `docs/THIRD_PARTY_LICENSES.md` | newly authored concise status/licensing docs for this snapshot |

## Excluded (and why)

| Excluded | Reason |
|---|---|
| `.git/` of source workspace | never publish old history/secrets |
| `firmware/legacy/daas_v1,daas_v2` | contained real device MAC addresses; historical value only |
| `ml/` (11 MB) | separate FastAPI/XGBoost pipeline; dependency/model/data licensing not fully audited under deadline — excluded pending Phase C review |
| `results/raw/` (65 MB), `results/logs/`, `results/hardware/`, `results/plots/` | raw private logs/captures; `results/hardware/` contains real MAC addresses in boot banners |
| `results/reports/H2_*/H3_*/RELEASE_READINESS*` | hardware-evidence reports tied to private device identifiers; superseded by `docs/VALIDATION_STATUS.md` |
| `media/`, `hardware/`, `presentation/` (29 MB pptx), `paper/`, `SIH26007_CONTEXT/`, `research/` drafts | photographs (redistribution rights not established), externally authored PDFs, decks |
| `tools/tectonic/tectonic.exe` (50 MB) + other binaries | binaries excluded on principle |
| `archive/`, `scratch/`, `final/`, `neon_siem/`, `projects/`, `opencode.json`, `.opencode/`, `AGENTS.md` | internal agent/planning material, unrelated subprojects, local config |
| `docs/implementation/`, `docs/evidence/photographs.md`, `docs/hardware/`, `verification/` | internal runbooks/audit trails referencing private paths/evidence |
| `__pycache__/`, `*.exe`, `*.log`, `.env*` (except authored `.env.example`) | caches/binaries/logs/secrets |

## Sanitization performed inside the export

1. `src/daas_impl/simio.py`: personal fallback path removed from
   `REPO_CANDIDATES` (package-root detection already preferred; behaviour
   preserved).
2. `firmware/diagnostics/README_MANUAL_FLASH.md`: user-specific Windows
   paths (`C:\Users\...`, `D:\daas ,ml\...`) replaced with
   `<arduino-cli>` / `<repo>` / `<Arduino sketchbook>` placeholders.
3. Removed entire `firmware/legacy/` (real MAC addresses found inside).
4. Verified by scan: **zero occurrences** of the real MACs
   (`88:57:21:**:**:**`, `14:08:08:**:**:**`), zero secret/token patterns
   (`sk-`, `ghp_`, `Authorization: Bearer`, private-key PEM markers,
   assigned `MUSE_MODEL_API_KEY=` values), zero user-specific absolute
   paths (`/mnt/...`, `C:\Users\...`, usernames), no `.env` files.
   Owner's own public contact e-mail intentionally retained in
   README/SECURITY/CODE_OF_CONDUCT as authorship attribution.
5. Secret scanning method: documented manual grep-based scan (pattern list
   above). Gitleaks was not available in this environment; automated
   scanning is NOT claimed.

## Tests executed in this export before publication

- `python3 tests/run_unit_tests.py` → Ran 33 tests — OK
- `python3 muse/tests/run_tests.py` → PASS (41 run, 0 failed/errored/skipped)
- `python3 -m muse.vertical_slice muse/scenarios/vertical_slice_base.json --sandbox` → PASS (scratch writer)
- `python3 firmware/tests/vs1_hostcheck.py` → PASS (1 compiler warning)
- `g++ -std=c++17` compile + run of `test_wire_protocol.cpp` and
  `test_safety_isolation.cpp` → ALL TESTS PASSED
