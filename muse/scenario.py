"""Strict scenario schema for ScenarioPilot.

One schema, version "1.0". All mapped simulation fields are REQUIRED (no
silent defaults): a scenario that omits or mis-types anything is rejected
before any experiment starts. Unknown top-level keys are rejected (strict).

Validation is local and deterministic — the model API never approves params.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"

NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-]{0,127}$")


class ScenarioError(ValueError):
    """Raised when a scenario violates the strict schema."""


@dataclass
class ScenarioSpec:
    name: str
    seed: int
    num_vehicles: int
    duration_s: float
    dt_ms: float
    emergency_intensity: float
    emergency_duration_ms: float
    speed_mean_mps: float
    speed_jitter_mps: float
    loss_prob: float
    comm_range_m: float
    road_length_m: float
    trust_gate_enabled: bool
    description: str = ""
    raw: dict = field(default_factory=dict)


def _fail(name: str, msg: str) -> None:
    raise ScenarioError(f"{name}: {msg}")


def _check_number(name: str, value: Any, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(name, f"expected number, got {type(value).__name__}")
    v = float(value)
    if v != v or v in (float("inf"), float("-inf")):
        _fail(name, "value must be finite")
    if not (lo <= v <= hi):
        _fail(name, f"value {v} outside allowed range [{lo}, {hi}]")
    return v


def _check_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        _fail(name, f"expected boolean, got {type(value).__name__}")
    return value


def validate_scenario(data: Any) -> ScenarioSpec:
    """Validate a raw dict against the strict schema; raise ScenarioError."""
    if not isinstance(data, dict):
        raise ScenarioError("scenario must be a JSON object")

    if data.get("schema_version") != SCHEMA_VERSION:
        _fail("schema_version",
              f"must be exactly '{SCHEMA_VERSION}' "
              f"(got {data.get('schema_version')!r})")

    allowed = {
        "schema_version", "name", "seed", "num_vehicles", "duration_s",
        "dt_ms", "emergency_intensity", "emergency_duration_ms",
        "speed_mean_mps", "speed_jitter_mps", "loss_prob", "comm_range_m",
        "road_length_m", "trust_gate_enabled", "description",
    }
    unknown = set(data.keys()) - allowed
    if unknown:
        _fail("scenario", f"unknown field(s): {sorted(unknown)}")

    required = [
        "name", "seed", "num_vehicles", "duration_s", "dt_ms",
        "emergency_intensity", "emergency_duration_ms", "speed_mean_mps",
        "speed_jitter_mps", "loss_prob", "comm_range_m", "road_length_m",
        "trust_gate_enabled",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise ScenarioError(f"missing required field(s): {missing}")

    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        _fail("name", "must match ^[a-zA-Z][a-zA-Z0-9_-]{0,127}$")

    seed = data.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        _fail("seed", "must be an integer")
    if not (0 <= seed <= 2**31 - 1):
        _fail("seed", "outside allowed range [0, 2147483647]")

    for key, lo, hi in [
        ("num_vehicles", 2, 50),
        ("duration_s", 1.0, 1800.0),
        ("dt_ms", 1.0, 100.0),
        ("emergency_intensity", 0.0, 1.0),
        ("emergency_duration_ms", 100.0, 10000.0),
        ("speed_mean_mps", 0.5, 30.0),
        ("speed_jitter_mps", 0.0, 20.0),
        ("loss_prob", 0.0, 0.9),
        ("comm_range_m", 10.0, 500.0),
        ("road_length_m", 10.0, 2000.0),
    ]:
        _check_number(key, data[key], lo, hi)

    if not 0.0 <= data["speed_jitter_mps"] <= data["speed_mean_mps"]:
        _fail("speed_jitter_mps", "must not exceed speed_mean_mps")

    desc = data.get("description", "")
    if not isinstance(desc, str) or len(desc) > 2000:
        _fail("description", "must be a string of at most 2000 chars")

    trust = _check_bool("trust_gate_enabled", data["trust_gate_enabled"])

    return ScenarioSpec(
        name=name,
        seed=seed,
        num_vehicles=int(data["num_vehicles"]),
        duration_s=float(data["duration_s"]),
        dt_ms=float(data["dt_ms"]),
        emergency_intensity=float(data["emergency_intensity"]),
        emergency_duration_ms=float(data["emergency_duration_ms"]),
        speed_mean_mps=float(data["speed_mean_mps"]),
        speed_jitter_mps=float(data["speed_jitter_mps"]),
        loss_prob=float(data["loss_prob"]),
        comm_range_m=float(data["comm_range_m"]),
        road_length_m=float(data["road_length_m"]),
        trust_gate_enabled=trust,
        description=desc,
        raw=dict(data),
    )


def load_scenario(path: str) -> ScenarioSpec:
    with open(path, encoding="utf-8") as f:
        return validate_scenario(json.load(f))


def scenario_hash(spec: ScenarioSpec) -> str:
    blob = json.dumps(spec.raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
