"""Unit tests for the Meta Model API adapter — fully mocked transport.

The suite never requires a live API key and never performs network I/O.
Run via: python3 muse/tests/run_tests.py
"""

import hashlib
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from muse.scenario import validate_scenario
from muse.spark_adapter import (DEFAULT_MODEL, review_scenario)
from muse.tests.test_scenario import base_scenario


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self.payload = payload
        self.status = status

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RecordingTransport:
    """Yields one canned response and records the request for assertions."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.error is not None:
            raise self.error
        return self.response


def make_api_body(content: str) -> bytes:
    return json.dumps({
        "id": "x", "model": DEFAULT_MODEL,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"total_tokens": 1},
    }).encode("utf-8")


def env(**over):
    e = {"MUSE_MODEL_API_URL": "https://api.example-meta/v1",
         "MUSE_MODEL_API_KEY": "test-key-123"}
    e.update(over)
    return e


class TestOfflineMode(unittest.TestCase):
    def test_no_url_is_offline_and_never_calls_network(self):
        boom = RecordingTransport(error=RuntimeError("network touched"))
        r = review_scenario(validate_scenario(base_scenario()),
                            env={"MUSE_MODEL_API_URL": ""}, urlopen_fn=boom)
        self.assertEqual(r.status, "DISABLED_NO_URL")
        self.assertEqual(len(boom.requests), 0)
        self.assertEqual(r.model, DEFAULT_MODEL)

    def test_url_without_key_rejected_by_env(self):
        boom = RecordingTransport(error=RuntimeError("network touched"))
        r = review_scenario(validate_scenario(base_scenario()),
                            env={"MUSE_MODEL_API_URL": "https://x/v1",
                                 "MUSE_MODEL_API_KEY": ""},
                            urlopen_fn=boom)
        self.assertEqual(r.status, "REJECTED_BY_ENV")
        self.assertEqual(len(boom.requests), 0)


class TestMockedSuccess(unittest.TestCase):
    def test_ok_review_parses_verdict_and_hashes_content(self):
        content = json.dumps({"verdict": "ok", "summary": "plausible"})
        t = RecordingTransport(response=FakeResponse(make_api_body(content)))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.verdict, "ok")
        self.assertEqual(r.summary, "plausible")
        self.assertEqual(r.content_sha256,
                         hashlib.sha256(content.encode()).hexdigest())

    def test_request_carries_credentials_and_model(self):
        t = RecordingTransport(response=FakeResponse(make_api_body('{}')))
        review_scenario(validate_scenario(base_scenario()), env(),
                        urlopen_fn=t)
        self.assertEqual(len(t.requests), 1)
        req = t.requests[0]
        self.assertIn("Bearer test-key-123",
                      req.headers.get("Authorization", ""))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertTrue(req.get_full_url().endswith("/chat/completions"))
        self.assertEqual(body["temperature"], 0.0)

    def test_max_tokens_default_and_env_override(self):
        # Live evidence D1.1: 256 truncated before content (finish_reason=
        # length). Default is now 2048; MUSE_MODEL_MAX_TOKENS overrides,
        # clamped to [64, 8192].
        from muse.spark_adapter import build_review_payload, _config_from_env
        spec = validate_scenario(base_scenario())
        self.assertEqual(build_review_payload(spec)["max_tokens"], 2048)
        _, _, _, _, mt = _config_from_env(env(**{"MUSE_MODEL_MAX_TOKENS": "512"}))
        self.assertEqual(mt, 512)
        _, _, _, _, mt = _config_from_env(env(**{"MUSE_MODEL_MAX_TOKENS": "99999"}))
        self.assertEqual(mt, 8192)
        _, _, _, _, mt = _config_from_env(env(**{"MUSE_MODEL_MAX_TOKENS": "junk"}))
        self.assertEqual(mt, 2048)
        t = RecordingTransport(response=FakeResponse(make_api_body('{}')))
        review_scenario(spec, env(**{"MUSE_MODEL_MAX_TOKENS": "512"}),
                        urlopen_fn=t)
        self.assertEqual(json.loads(t.requests[0].data)["max_tokens"], 512)

    def test_non_json_content_kept_as_summary_without_verdict(self):
        t = RecordingTransport(response=FakeResponse(
            make_api_body("looks reasonable to me")))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.verdict, "")
        self.assertEqual(r.summary, "looks reasonable to me")

    def test_unexpected_verdict_word_is_never_trusted(self):
        content = json.dumps({"verdict": "ENABLE_ALL", "summary": "?"})
        t = RecordingTransport(response=FakeResponse(make_api_body(content)))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.verdict, "")


class TestMockedFailures(unittest.TestCase):
    def test_http_401_maps_to_api_error(self):
        t = RecordingTransport(error=urllib.error.HTTPError(
            "https://x/v1/chat/completions", 401, "Unauthorized", {}, None))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.status, "API_ERROR")
        self.assertIn("401", r.error)
        self.assertEqual(r.verdict, "")

    def test_network_exception_maps_to_unavailable(self):
        t = RecordingTransport(error=TimeoutError("timed out"))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.status, "UNAVAILABLE")

    def test_bad_payload_shape_maps_to_bad_response(self):
        t = RecordingTransport(response=FakeResponse(b'{"nope": true}'))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.status, "BAD_RESPONSE")

    def test_review_is_bounded_exactly_one_call_no_retry(self):
        # Transport that ALWAYS fails: the adapter must attempt exactly one
        # call — no retry loop, no tool-call cascade.
        t = RecordingTransport(error=TimeoutError("down"))
        review_scenario(validate_scenario(base_scenario()), env(),
                        urlopen_fn=t)
        self.assertEqual(len(t.requests), 1)

    def test_review_never_contains_numbers_that_affect_runs(self):
        # A model attempting to emit metrics must not influence the run:
        # the review record carries only status/verdict/summary/hashes.
        content = json.dumps({"verdict": "ok", "summary": "ok",
                              "pdr_percent": 99.999})
        t = RecordingTransport(response=FakeResponse(make_api_body(content)))
        r = review_scenario(validate_scenario(base_scenario()), env(),
                            urlopen_fn=t)
        self.assertEqual(r.status, "OK")
        self.assertNotIn("99.999", str(r.to_dict()))


class TestMissingContentHandling(unittest.TestCase):
    """D1.1 — the live API returned message.content=None; the adapter must
    return a controlled status, never raise, and record safe diagnostics."""

    def resp_with_message(self, message, finish_reason="stop", top=None):
        body = {"id": "req-1", "model": DEFAULT_MODEL,
                "choices": [{"index": 0, "finish_reason": finish_reason,
                             "message": message}]}
        body.update(top or {})
        return FakeResponse(json.dumps(body).encode("utf-8"))

    def review(self, response):
        return review_scenario(validate_scenario(base_scenario()), env(),
                               urlopen_fn=RecordingTransport(response=response))

    def test_content_none_is_controlled_bad_response_never_crashes(self):
        r = self.review(self.resp_with_message({"role": "assistant",
                                                "content": None}))
        self.assertEqual(r.status, "BAD_RESPONSE")
        self.assertEqual(r.diagnostics["content_type"], "NoneType")
        self.assertIn("empty", r.error.lower())

    def test_empty_and_whitespace_content_rejected(self):
        for c in ("", "   "):
            with self.subTest(content=repr(c)):
                r = self.review(self.resp_with_message(
                    {"role": "assistant", "content": c}))
                self.assertEqual(r.status, "BAD_RESPONSE")
                self.assertEqual(r.diagnostics["content_len"],
                                 len(c))

    def test_refusal_maps_to_refusal_status(self):
        r = self.review(self.resp_with_message(
            {"role": "assistant", "content": None,
             "refusal": "cannot help with that"},
            finish_reason="stop"))
        self.assertEqual(r.status, "REFUSAL")
        self.assertTrue(r.diagnostics["refusal_present"])
        self.assertEqual(r.verdict, "")

    def test_unexpected_tool_calls_map_to_bad_response(self):
        r = self.review(self.resp_with_message(
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "t1", "type": "function",
                             "function": {"name": "f", "arguments": "{}"}}]},
            finish_reason="tool_calls"))
        self.assertEqual(r.status, "BAD_RESPONSE")
        self.assertEqual(r.diagnostics["tool_calls_count"], 1)
        self.assertIn("tool_calls", r.error)

    def test_valid_json_content_still_parses_with_diagnostics(self):
        content = json.dumps({"verdict": "concern", "summary": "dense net"})
        r = self.review(self.resp_with_message(
            {"role": "assistant", "content": content}, finish_reason="stop"))
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.verdict, "concern")
        self.assertEqual(r.diagnostics["finish_reason"], "stop")
        self.assertTrue(r.diagnostics["request_id_present"])
        self.assertEqual(r.diagnostics["response_model"], DEFAULT_MODEL)

    def test_malformed_json_content_is_ok_with_empty_verdict(self):
        r = self.review(self.resp_with_message(
            {"role": "assistant", "content": "not json {{{"}))
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.verdict, "")

    def test_diagnostics_never_leak_secrets_and_summary_is_capped(self):
        long_text = "advisory prose " * 40   # 560 chars
        r = self.review(self.resp_with_message(
            {"role": "assistant", "content": long_text}))
        blob = json.dumps(r.to_dict())
        # credential material must never appear
        self.assertNotIn("Bearer", blob)
        self.assertNotIn("test-key-123", blob)
        self.assertNotIn("MUSE_MODEL_API_KEY", blob)
        # advisory summary is intentionally capped at 200 chars
        self.assertLessEqual(len(r.summary), 200)
        self.assertEqual(r.diagnostics["content_len"], len(long_text))

    def test_reasoning_style_finish_with_content_still_ok(self):
        r = self.review(self.resp_with_message(
            {"role": "assistant",
             "content": json.dumps({"verdict": "ok", "summary": "fine"})},
            finish_reason="length"))
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.diagnostics["finish_reason"], "length")


if __name__ == "__main__":
    unittest.main(verbosity=2)
