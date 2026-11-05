"""Run I/O — CSV/metadata writers, run registry, checkpointing.

Contract: docs/implementation/CURRENT_INTERFACE_CONTRACT.md section 4.
Raw CSVs are append-only during a run and never edited afterwards.
Every run writes a sidecar metadata JSON in results/metadata/.
"""

import csv
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

SOFTWARE_VERSION = "daas-impl 1.0.0"

# Personal-machine fallback paths intentionally removed from the public export.
# repo_root() resolves the project root from this package's own location first.
REPO_CANDIDATES: list = []


def repo_root() -> str:
    # Prefer the package's own project root first: this resolves correctly in
    # clean copies / worktrees without .git (reconstruction isolation).
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.isdir(os.path.join(pkg_root, "src", "daas_impl")):
        return pkg_root
    for cand in REPO_CANDIDATES:
        if os.path.isdir(os.path.join(cand, ".git")):
            return cand
    return pkg_root


def git_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root(), capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RunContext:
    experiment_id: str
    run_id: str
    seed: int
    run_number: int
    configuration: dict
    modality: str = "SIMULATION"     # SIMULATION | HARDWARE_BENCH — never mislabeled
    raw_csv: str = ""
    metadata_csv: str | None = None
    git_hash: str = field(default_factory=git_hash)
    software_version: str = SOFTWARE_VERSION
    started_utc: str = field(default_factory=utc_now_iso)
    finished_utc: str | None = None
    row_count: int = 0
    status: str = "RUNNING"
    notes: str = ""
    _file_initialized: bool = field(default=False, repr=False)

    def ensure_header(self, header: list[str]) -> None:
        path = os.path.join(repo_root(), self.raw_csv)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not self._file_initialized:
            # A new RunContext replaces its own run file (same run_id rerun
            # truncates; different run_ids are separate paths, preserved).
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(header)
            self._file_initialized = True

    def append_rows(self, header: list[str], rows: list[list]) -> None:
        if not rows:
            return
        self.ensure_header(header)
        path = os.path.join(repo_root(), self.raw_csv)
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            for row in rows:
                w.writerow(row)
                self.row_count += 1

    def finalize(self, status: str = "COMPLETE", notes: str = "") -> str:
        self.finished_utc = utc_now_iso()
        self.status = status
        if notes:
            self.notes = notes
        meta = {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "seed": self.seed,
            "run_number": self.run_number,
            "configuration": self.configuration,
            "software_version": self.software_version,
            "git_hash": self.git_hash,
            "modality": self.modality,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "raw_csv": self.raw_csv,
            "row_count": self.row_count,
            "status": self.status,
            "notes": self.notes,
        }
        mdir = os.path.join(repo_root(), "results", "metadata")
        os.makedirs(mdir, exist_ok=True)
        mpath = os.path.join(mdir, f"{self.run_id}.metadata.json")
        with open(mpath, "w") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
        return mpath

    def checkpoint(self) -> None:
        """Periodic checkpoint: persists metadata with current status."""
        self.finalize(status=self.status, notes=self.notes or "checkpoint")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksum_manifest(raw_dir: str | None = None) -> str:
    """REQ-06: SHA-256 manifest over results/raw/ (immutability guarantee)."""
    root = repo_root()
    raw = os.path.join(root, raw_dir) if raw_dir else os.path.join(root, "results", "raw")
    lines = []
    for name in sorted(os.listdir(raw)):
        p = os.path.join(raw, name)
        if os.path.isfile(p) and name != "CHECKSUMS.sha256":
            lines.append(f"{sha256_file(p)}  {name}")
    manifest = os.path.join(raw, "CHECKSUMS.sha256")
    with open(manifest, "w") as f:
        f.write("\n".join(lines) + "\n")
    return manifest


def verify_checksum_manifest(raw_dir: str | None = None) -> tuple[int, list[str]]:
    """Returns (n_ok, mismatched_names)."""
    root = repo_root()
    raw = os.path.join(root, raw_dir) if raw_dir else os.path.join(root, "results", "raw")
    manifest = os.path.join(raw, "CHECKSUMS.sha256")
    ok, bad = 0, []
    with open(manifest) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            digest, name = line.split("  ", 1)
            p = os.path.join(raw, name)
            if not os.path.isfile(p) or sha256_file(p) != digest:
                bad.append(name)
            else:
                ok += 1
    return ok, bad
