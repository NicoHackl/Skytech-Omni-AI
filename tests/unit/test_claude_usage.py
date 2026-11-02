"""Direkte Claude-Verbrauchsabfrage: Netzattrappe, Pausen und Geheimhaltung."""

import json
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from io import BytesIO

import pytest

import limits
from providers import claude_usage

ORIGINAL_FETCH = claude_usage._fetch_usage
NOW = 1_800_000_000.0
TOKEN = "test-abo-zugang"
PAYLOAD = {
    "five_hour": {"utilization": 12.5, "resets_at": limits.iso(NOW + 3600)},
    "seven_day": {"utilization": 42, "resets_at": limits.iso(NOW + 86400)},
    "seven_day_opus": None,
    "extra_usage": {"is_enabled": True, "used_credits": 123},
}


@pytest.fixture(autouse=True)
def usage_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN)
    monkeypatch.setattr(claude_usage, "_memory", {})
    # Jeder Test muss einen Netzaufruf ausdrücklich ersetzen.
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: pytest.fail("Kein echtes Netz"))


def test_percent_below_warning_without_model_call(monkeypatch):
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: PAYLOAD)
    entry = limits.claude_entry(True, NOW)
    assert entry["state"] == "ok"
    assert entry["observedAt"] == limits.iso(NOW)
    first, second = entry["windows"]
    assert (first["usedPercent"], second["usedPercent"]) == (12.5, 42)
    assert first["source"] == "measured"
    assert first["durationMinutes"] == 300
    assert "extra_usage" not in json.dumps(entry)


def test_cache_and_pause_survive_process_restart(monkeypatch):
    calls = []
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: calls.append(token) or PAYLOAD)
    limits.claude_entry(True, NOW)
    monkeypatch.setattr(claude_usage, "_memory", {})
    cached = limits.claude_entry(True, NOW + 299)
    assert cached["observedAt"] == limits.iso(NOW)
    assert len(calls) == 1
    limits.claude_entry(True, NOW + 300)
    assert len(calls) == 2


def test_rate_limit_zero_retry_after_waits_and_keeps_observation(monkeypatch, caplog):
    limits.record_claude({"status": "allowed", "rateLimitType": "five_hour"}, now=NOW - 1)
    calls = []

    def denied(token):
        calls.append(token)
        raise urllib.error.HTTPError(
            "https://example.invalid", 429, TOKEN, {"Retry-After": "0"}, BytesIO(TOKEN.encode())
        )

    monkeypatch.setattr(claude_usage, "_fetch_usage", denied)
    assert limits.claude_entry(True, NOW)["windows"][0]["usedPercent"] is None
    monkeypatch.setattr(claude_usage, "_memory", {})
    limits.claude_entry(True, NOW + 299)
    assert len(calls) == 1
    limits.claude_entry(True, NOW + 300)
    limits.claude_entry(True, NOW + 899)
    assert len(calls) == 2
    limits.claude_entry(True, NOW + 900)
    assert len(calls) == 3
    assert TOKEN not in caplog.text
    assert TOKEN not in "".join(p.read_text() for p in limits.limits_dir().glob("*.json"))


@pytest.mark.parametrize("header", ["1800", formatdate(NOW + 1800, usegmt=True)])
def test_retry_after_is_respected(monkeypatch, header):
    calls = []

    def denied(token):
        calls.append(token)
        raise urllib.error.HTTPError(
            "https://example.invalid", 429, "", {"Retry-After": header}, None
        )

    monkeypatch.setattr(claude_usage, "_fetch_usage", denied)
    limits.claude_entry(True, NOW)
    limits.claude_entry(True, NOW + 1799)
    assert len(calls) == 1
    limits.claude_entry(True, NOW + 1800)
    assert len(calls) == 2


@pytest.mark.parametrize("code", [401, 403])
def test_missing_read_permission_does_not_break_model_access(monkeypatch, code):
    calls = []

    def denied(token):
        calls.append(token)
        raise urllib.error.HTTPError("https://example.invalid", code, "", {}, None)

    monkeypatch.setattr(claude_usage, "_fetch_usage", denied)
    assert limits.claude_entry(True, NOW)["state"] == "unknown"
    limits.claude_entry(True, NOW + 3599)
    assert len(calls) == 1


def test_failure_retains_measured_value_and_timestamp(monkeypatch):
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: PAYLOAD)
    limits.claude_entry(True, NOW)

    def failed(token):
        raise TimeoutError(TOKEN)

    monkeypatch.setattr(claude_usage, "_fetch_usage", failed)
    entry = limits.claude_entry(True, NOW + 300)
    assert entry["observedAt"] == limits.iso(NOW)
    assert entry["windows"][0]["usedPercent"] == 12.5
    assert limits.claude_entry(True, NOW + 3601)["windows"][0]["usedPercent"] is None


def test_newer_observation_wins_without_losing_other_measured_windows(monkeypatch):
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: PAYLOAD)
    limits.claude_entry(True, NOW)
    limits.record_claude(
        {"status": "rejected", "rateLimitType": "five_hour", "resetsAt": NOW + 3600}, now=NOW + 1
    )
    entry = limits.claude_entry(True, NOW + 2)
    assert entry["state"] == "exhausted"
    windows = {w["id"]: w for w in entry["windows"]}
    assert windows["five_hour"]["source"] == "observed"
    assert windows["five_hour"]["usedPercent"] == 100
    assert windows["seven_day"]["source"] == "measured"
    assert entry["retryAt"] == limits.iso(NOW + 3600)


def test_new_measurement_replaces_older_rejection(monkeypatch):
    limits.record_claude(
        {"status": "rejected", "rateLimitType": "five_hour", "resetsAt": NOW + 3600}, now=NOW - 1
    )
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: PAYLOAD)
    assert limits.claude_entry(True, NOW)["state"] == "ok"


def test_changed_token_does_not_reuse_cached_measurement(monkeypatch):
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: PAYLOAD)
    limits.claude_entry(True, NOW)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "anderer-test-zugang")
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: {})
    assert limits.claude_entry(True, NOW + 1)["windows"] == []


def test_no_token_or_unavailable_does_not_query(monkeypatch):
    assert limits.claude_entry(False, NOW)["state"] == "unavailable"
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN")
    assert limits.claude_entry(True, NOW)["state"] == "unknown"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"five_hour": {"utilization": True}},
        {"five_hour": {"utilization": float("nan")}},
        {"five_hour": {"utilization": 101}},
        {"five_hour": {"utilization": 10, "resets_at": "falsch"}},
    ],
)
def test_invalid_response_does_not_invent_usage(monkeypatch, payload):
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: payload)
    assert limits.claude_entry(True, NOW)["windows"] == []


def test_concurrent_refresh_queries_once(monkeypatch):
    calls = []
    barrier = threading.Barrier(4)
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: calls.append(token) or PAYLOAD)

    def refresh(_):
        barrier.wait(timeout=5)
        return limits.claude_entry(True, NOW)

    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(refresh, range(4)))
    assert len(calls) == 1
    assert all(e["windows"][0]["usedPercent"] == 12.5 for e in entries)


def test_transport_uses_fixed_url_headers_timeout_and_bounded_read(monkeypatch):
    captured = {}

    class Response(BytesIO):
        def read(self, size=-1):
            assert size == claude_usage.MAX_RESPONSE_BYTES + 1
            return super().read(size)

    class Opener:
        def open(self, request, timeout):
            captured.update(
                url=request.full_url, headers=dict(request.header_items()), timeout=timeout
            )
            return Response(json.dumps(PAYLOAD).encode())

    def build(*handlers):
        assert any(isinstance(h, claude_usage._NoRedirect) for h in handlers)
        return Opener()

    monkeypatch.setattr(claude_usage.urllib.request, "build_opener", build)
    # Die Autouse-Attrappe hier gezielt durch die ursprüngliche Funktion ersetzen.
    result = ORIGINAL_FETCH(TOKEN)
    assert result == PAYLOAD
    assert captured["url"] == "https://api.anthropic.com/api/oauth/usage"
    assert captured["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert captured["headers"]["Anthropic-beta"] == "oauth-2025-04-20"
    assert captured["timeout"] == 8


def test_redirect_does_not_forward_credentials():
    assert (
        claude_usage._NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://example.invalid"
        )
        is None
    )


def test_corrupt_cache_falls_back_without_crashing(monkeypatch):
    import hashlib

    path = limits.limits_dir() / "claude_usage.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "fingerprint": hashlib.sha256(TOKEN.encode()).hexdigest(),
                "nextAttempt": NOW + 300,
                "measurement": {"at": NOW, "windows": [None]},
            }
        )
    )
    assert limits.claude_entry(True, NOW)["state"] == "unknown"


def test_exhausted_measurement_keeps_latest_reset(monkeypatch):
    payload = {
        key: {**value, "utilization": 100}
        for key, value in PAYLOAD.items()
        if key in ("five_hour", "seven_day")
    }
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: payload)
    entry = limits.claude_entry(True, NOW)
    assert entry["state"] == "exhausted"
    assert entry["retryAt"] == limits.iso(NOW + 86400)


def test_unwritable_cache_still_throttles_in_memory(monkeypatch):
    calls = []

    def unwritable(*args):
        raise OSError(TOKEN)

    monkeypatch.setattr(claude_usage, "write_json", unwritable)
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: calls.append(token) or PAYLOAD)
    limits.claude_entry(True, NOW)
    limits.claude_entry(True, NOW + 1)
    assert len(calls) == 1


@pytest.mark.parametrize("used, state", [(0, "ok"), (100, "exhausted")])
def test_known_usage_without_reset_time_is_preserved(monkeypatch, used, state):
    monkeypatch.setattr(
        claude_usage,
        "_fetch_usage",
        lambda token: {"five_hour": {"utilization": used, "resets_at": None}},
    )
    entry = limits.claude_entry(True, NOW)
    assert entry["state"] == state
    assert entry["windows"][0]["usedPercent"] == used
    assert entry["windows"][0]["resetsAt"] is None
    assert entry["retryAt"] is None


def test_repeated_failures_back_off_to_one_hour(monkeypatch):
    calls = []

    def failed(token):
        calls.append(token)
        raise TimeoutError()

    monkeypatch.setattr(claude_usage, "_fetch_usage", failed)
    at = NOW
    for count, delay in enumerate((300, 600, 1200, 2400, 3600, 3600), start=1):
        limits.claude_entry(True, at)
        monkeypatch.setattr(claude_usage, "_memory", {})
        limits.claude_entry(True, at + delay - 1)
        assert len(calls) == count
        at += delay


@pytest.mark.parametrize("route", ["/limits", "/v1/limits"])
def test_both_endpoints_query_the_same_cache(monkeypatch, route):
    from app import app

    calls = []
    monkeypatch.setenv("OMNIAI_API_TOKEN", "t" * 40)
    monkeypatch.setattr(claude_usage, "_fetch_usage", lambda token: calls.append(token) or PAYLOAD)
    with app.test_client() as client:
        for _ in range(2):
            answer = client.get(route, headers={"Authorization": "Bearer " + "t" * 40})
            assert answer.status_code == 200
            assert answer.json["accounts"][0]["windows"][0]["usedPercent"] == 12.5
    assert len(calls) == 1
