"""Meta Model API client for Muse Spark 1.3 (advisory scenario review).

Credentials and endpoint come from environment variables only:

  MUSE_MODEL_API_URL     base URL of the Meta Model API (offline if unset)
  MUSE_MODEL_API_KEY     bearer credential (required when URL is set)
  MUSE_MODEL_NAME        model id (default: muse-spark-1.3)
  MUSE_MODEL_TIMEOUT_S   request timeout in seconds (default: 30)

The client performs one bounded request per run and never computes numeric
metrics — its output is advisory provenance attached to the evidence. The
strict local scenario validator (scenario.py) remains the only gate that can
reject parameters. The transport is injectable so unit tests run fully
mocked, with no live API key requirement.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_TIMEOUT_S = 30.0
# Live evidence (Task D1.1): with max_tokens=256 the model spent the whole
# budget on reasoning and returned finish_reason=length with EMPTY content.
# 2048 gives room for reasoning + the tiny JSON verdict. Optional override:
# MUSE_MODEL_MAX_TOKENS.
DEFAULT_MAX_TOKENS = 2048


class SparkReview:
    __slots__ = ("status", "model", "verdict", "summary", "content_sha256",
                 "latency_ms", "error", "diagnostics")

    def __init__(self, status, model="", verdict="", summary="",
                 content_sha256="", latency_ms=0, error="", diagnostics=None):
        self.status = status          # OK | DISABLED_NO_URL | REJECTED_BY_ENV |
                                      # UNAVAILABLE | API_ERROR | BAD_RESPONSE |
                                      # REFUSAL
        self.model = model
        self.verdict = verdict        # ok | concern | reject | ""
        self.summary = summary
        self.content_sha256 = content_sha256
        self.latency_ms = latency_ms
        self.error = error
        self.diagnostics = diagnostics or {}

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def _config_from_env(env=None):
    env = dict(os.environ if env is None else env)
    url = env.get("MUSE_MODEL_API_URL", "").strip()
    key = env.get("MUSE_MODEL_API_KEY", "").strip()
    model = env.get("MUSE_MODEL_NAME", "").strip() or DEFAULT_MODEL
    try:
        timeout = float(env.get("MUSE_MODEL_TIMEOUT_S", "") or DEFAULT_TIMEOUT_S)
    except ValueError:
        timeout = DEFAULT_TIMEOUT_S
    try:
        max_tokens = int(float(env.get("MUSE_MODEL_MAX_TOKENS", "")
                               or DEFAULT_MAX_TOKENS))
    except ValueError:
        max_tokens = DEFAULT_MAX_TOKENS
    max_tokens = max(64, min(max_tokens, 8192))
    return url, key, model, timeout, max_tokens


REVIEW_SYSTEM_PROMPT = (
    "You are an experiment design reviewer. Given a JSON scenario descriptor "
    "for a vehicle-to-vehicle broadcast simulation, reply with ONLY a JSON "
    'object: {"verdict": "ok" | "concern" | "reject", "summary": "<=200 chars"}. '
    "Judge internal consistency and realism only (parameter plausibility). "
    "Do not recompute or estimate any numerical result."
)


def build_review_payload(spec, max_tokens=None) -> dict:
    """Constructor of the request body for the chat-completions-style API."""
    return {
        "model": None,  # filled by review_scenario from config
        "messages": [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user",
             "content": json.dumps(spec.raw, sort_keys=True)},
        ],
        "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        "temperature": 0.0,
    }


def review_scenario(spec, env=None, urlopen_fn=None):
    """Run one advisory review of a validated scenario. Never raises."""
    url, key, model, timeout, max_tokens = _config_from_env(env)
    urlopen_fn = urlopen_fn or urllib.request.urlopen

    if not url:
        return SparkReview(status="DISABLED_NO_URL", model=model)
    if not key:
        return SparkReview(status="REJECTED_BY_ENV", model=model,
                           error="MUSE_MODEL_API_KEY not set")

    payload = build_review_payload(spec, max_tokens=max_tokens)
    payload["model"] = model
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urlopen_fn(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            code = getattr(resp, "status", 200)
    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}"
        try:
            err += f": {e.read().decode('utf-8', 'replace')[:200]}"
        except Exception:
            pass
        return SparkReview(status=f"API_ERROR", model=model, error=err,
                           latency_ms=int((time.monotonic() - t0) * 1000))
    except Exception as e:  # network/timeout/mocked transport failures
        return SparkReview(status="UNAVAILABLE", model=model, error=str(e),
                           latency_ms=int((time.monotonic() - t0) * 1000))
    latency = int((time.monotonic() - t0) * 1000)

    if code != 200:
        return SparkReview(status="API_ERROR", model=model,
                           error=f"HTTP {code}", latency_ms=latency)
    # --- response inspection (safe metadata only; never raw content/auth) ---
    try:
        data = json.loads(raw)
        choice0 = data["choices"][0]
        msg = choice0["message"]
        content = msg.get("content")
        diagnostics = {
            "finish_reason": str(choice0.get("finish_reason", "")),
            "refusal_present": msg.get("refusal") is not None,
            "tool_calls_count": len(msg["tool_calls"])
            if isinstance(msg.get("tool_calls"), list) else 0,
            "response_model": str(data.get("model", "")),
            "request_id_present": bool(data.get("id")),
            "content_type": type(content).__name__,
            "content_len": len(content) if isinstance(content, str) else None,
        }
    except (KeyError, IndexError, ValueError, TypeError) as e:
        return SparkReview(status="BAD_RESPONSE", model=model,
                           error=f"response shape: {e}", latency_ms=latency)

    # --- explicit missing/empty-content handling (never json.loads(None)) ---
    if diagnostics["refusal_present"]:
        return SparkReview(status="REFUSAL", model=model,
                           error="model set refusal; no advisory content",
                           diagnostics=diagnostics, latency_ms=latency)
    if diagnostics["tool_calls_count"]:
        return SparkReview(status="BAD_RESPONSE", model=model,
                           error="unexpected tool_calls in advisory review",
                           diagnostics=diagnostics, latency_ms=latency)
    if not isinstance(content, str) or not content.strip():
        return SparkReview(status="BAD_RESPONSE", model=model,
                           error="missing or empty message content "
                                 f"(finish_reason="
                                 f"{diagnostics['finish_reason'] or 'none'})",
                           diagnostics=diagnostics, latency_ms=latency)

    # --- content is a non-empty string: parse defensively ---
    verdict, summary = "", ""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            v = str(parsed.get("verdict", "")).lower()
            verdict = v if v in ("ok", "concern", "reject") else ""
            summary = str(parsed.get("summary", ""))[:200]
    except (ValueError, TypeError):
        summary = content[:200]   # non-JSON text: kept as advisory summary
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return SparkReview(status="OK", model=model, verdict=verdict,
                       summary=summary, content_sha256=digest,
                       diagnostics=diagnostics, latency_ms=latency)
