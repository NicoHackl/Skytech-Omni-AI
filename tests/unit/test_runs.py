"""Tests der Agent-Läufe (``/v1/runs``, D-021).

Die Claude-CLI wird durch ein kleines Skript ersetzt, das eine aufgezeichnete
Ausgabe der echten CLI (``stream-json``) abspielt und seine Aufrufparameter
mitschreibt. Geprüft wird, was das Add-on daraus macht — nicht das Modell.
"""

import json
import os
import stat
import sys
import time
from typing import ClassVar

import pytest

import api_v1 as api_module
from app import app as flask_app
from runs import (
    FEHLER_ERGEBNIS,
    FEHLER_NEUSTART,
    FEHLER_ZEIT,
    ClaudeRunner,
    RunManager,
    SingleShotRunner,
    build_task,
    clean_handover,
    cli_tool_name,
)

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}
RUN_TOKEN = "lauf-token-geheim"

# Gekürzte Aufzeichnung eines echten Laufs der Claude-CLI 2.1.234.
RECORDED = [
    {
        "type": "system",
        "subtype": "init",
        "tools": ["StructuredOutput", "mcp__skytech__skytech_test_data_list"],
        "mcp_servers": [{"name": "skytech", "status": "connected"}],
    },
    {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Ich lese die Testdaten."}]},
    },
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "mcp__skytech__skytech_test_data_list",
                    "input": {"limit": 1},
                }
            ]
        },
    },
    {
        "type": "user",
        "message": {
            "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "{}"}]
        },
    },
    {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": "toolu_2", "name": "StructuredOutput"}]},
    },
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": 0.02,
        "usage": {
            "input_tokens": 10,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 1000,
            "output_tokens": 50,
        },
        "structured_output": {
            "output": {"value": 4.2},
            "handover": {
                "summary": "PV liegt bei 4,2.",
                "decisions": ["Nur den letzten Wert gelesen"],
                "openPoints": [],
                "artifacts": [{"kind": "url", "ref": "https://example.test/x", "title": "Quelle"}],
            },
        },
    },
]

FAKE_CLI = """#!{python}
import json, os, sys, time
with open(os.environ["FAKE_CLAUDE_ARGS"], "w") as f:
    json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(),
               "mcp": open(sys.argv[sys.argv.index("--mcp-config") + 1]).read()
               if "--mcp-config" in sys.argv else None,
               "mode": oct(os.stat(sys.argv[sys.argv.index("--mcp-config") + 1]).st_mode & 0o777)
               if "--mcp-config" in sys.argv else None}}, f)
time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "0")))
for line in open(os.environ["FAKE_CLAUDE_OUTPUT"]):
    print(line, end="", flush=True)
sys.exit(int(os.environ.get("FAKE_CLAUDE_EXIT", "0")))
"""


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    """Legt eine nachgebaute ``claude`` in den Suchpfad; liefert Helfer."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(FAKE_CLI.format(python=sys.executable))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    output = tmp_path / "output.jsonl"
    args_file = tmp_path / "args.json"
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_OUTPUT", str(output))
    monkeypatch.setenv("FAKE_CLAUDE_ARGS", str(args_file))
    monkeypatch.setenv("OMNIAI_RUN_WORKDIR", str(work))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "abo-token")

    class Helper:
        def play(self, lines):
            output.write_text("".join(json.dumps(line) + "\n" for line in lines))

        def args(self):
            return json.loads(args_file.read_text())

        def leftovers(self):
            return list(work.iterdir())

    helper = Helper()
    helper.play(RECORDED)
    return helper


def wait_until_done(run, seconds=10):
    deadline = time.monotonic() + seconds
    while not run.terminal and time.monotonic() < deadline:
        time.sleep(0.02)
    assert run.terminal, f"Lauf nicht beendet, Status {run.status}"


def claude_request(**overrides):
    request = {
        "runId": "run-1",
        "provider": "claude_sub",
        "model": "sonnet",
        "instructions": "Antworte knapp.",
        "context": "Gestern lag PV bei 3,9.",
        "prompt": "Lies die Testdaten.",
        "outputSchema": {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "number"}},
        },
        "tools": {
            "mcpServers": [
                {
                    "name": "skytech",
                    "url": "http://192.168.10.18:8090/mcp",
                    "headers": {"Authorization": f"Bearer {RUN_TOKEN}"},
                }
            ],
            "allowedTools": ["skytech.test_data_list"],
        },
        "limits": {"maxMinutes": 5, "maxToolCalls": 10},
        "metadata": {"workItemId": "w-1"},
    }
    request.update(overrides)
    return request


# --- Claude-Läufe -------------------------------------------------------------


def test_claude_run_turns_cli_output_into_contract_events(tmp_path, fake_cli):
    manager = RunManager(str(tmp_path / "runs"))
    run, created = manager.start("run-1", claude_request())
    wait_until_done(run)

    assert created
    assert run.status == "SUCCEEDED"
    types = [e["type"] for e in run.events]
    assert types == [
        "status",
        "log",
        "tool_call",
        "tool_call",
        "usage",
        "handover",
        "result",
        "status",
    ]
    started, finished = run.events[2]["data"], run.events[3]["data"]
    assert started == {
        "callId": "toolu_1",
        "server": "skytech",
        "tool": "skytech.test_data_list",
        "phase": "started",
    }
    assert finished["phase"] == "finished" and finished["tool"] == "skytech.test_data_list"
    assert run.events[4]["data"] == {"inputTokens": 1110, "outputTokens": 50}
    assert run.output == {"value": 4.2}
    assert run.handover["summary"] == "PV liegt bei 4,2."
    assert run.summary == "PV liegt bei 4,2."
    # Beim Abo gibt es keinen Preis.
    assert run.cost_usd is None


def test_claude_command_allows_only_backend_tools(tmp_path, fake_cli):
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    wait_until_done(run)

    called = fake_cli.args()
    argv = called["argv"]
    assert argv[argv.index("--tools") + 1] == "WebSearch,WebFetch"
    allowed = argv[argv.index("--allowedTools") + 1].split(",")
    assert "mcp__skytech__skytech_test_data_list" in allowed
    assert not any(t in allowed for t in ("Bash", "Read", "Write", "Edit"))
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert argv[argv.index("--model") + 1] == "sonnet"
    # Hintergrund steht abgesetzt vor der Aufgabe, nicht in den Anweisungen.
    task = argv[argv.index("-p") + 1]
    assert task.index("Gestern lag PV") < task.index("Lies die Testdaten.")
    assert "Antworte knapp." in argv[argv.index("--append-system-prompt") + 1]
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["required"] == ["output", "handover"]
    # Das Lauf-Token steht nur in der Konfigurationsdatei, nur für den Besitzer lesbar.
    assert RUN_TOKEN not in json.dumps(argv)
    assert RUN_TOKEN in called["mcp"]
    assert called["mode"] == "0o600"


def test_without_web_access_no_builtin_tools_at_all(tmp_path, fake_cli, monkeypatch):
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "off")
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    wait_until_done(run)

    argv = fake_cli.args()["argv"]
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--allowedTools") + 1] == "mcp__skytech__skytech_test_data_list"


def test_token_and_work_files_are_gone_after_the_run(tmp_path, fake_cli):
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    wait_until_done(run)
    time.sleep(0.1)

    assert fake_cli.leftovers() == []
    assert "headers" not in run.request["tools"]["mcpServers"][0]
    stored = "".join(p.read_text() for p in (tmp_path / "runs").iterdir())
    assert RUN_TOKEN not in stored


def test_output_not_matching_schema_fails_but_keeps_handover(tmp_path, fake_cli):
    recorded = json.loads(json.dumps(RECORDED))
    recorded[-1]["structured_output"]["output"] = {"value": "viel"}
    fake_cli.play(recorded)
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    wait_until_done(run)

    assert run.status == "FAILED"
    assert run.error == FEHLER_ERGEBNIS
    assert run.handover is not None


def test_cli_without_result_fails_with_german_sentence(tmp_path, fake_cli, monkeypatch):
    fake_cli.play(RECORDED[:2])
    monkeypatch.setenv("FAKE_CLAUDE_EXIT", "1")
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    wait_until_done(run)

    assert run.status == "FAILED"
    assert run.error == "Das Modell hat den Lauf nicht abgeschlossen."


def test_time_limit_ends_the_run(tmp_path, fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_SLEEP", "5")
    monkeypatch.setattr("runs.limits_of", lambda request: (0.01, 10))
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    wait_until_done(run, seconds=15)

    assert run.status == "FAILED"
    assert run.error == FEHLER_ZEIT


def test_cancel_stops_the_cli(tmp_path, fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_SLEEP", "5")
    manager = RunManager(str(tmp_path / "runs"))
    run, _ = manager.start("run-1", claude_request())
    deadline = time.monotonic() + 5
    while run.process is None and time.monotonic() < deadline:
        time.sleep(0.02)
    manager.cancel("run-1")
    wait_until_done(run)

    assert run.status == "CANCELLED"


def test_tool_names_are_mapped_like_the_cli():
    assert cli_tool_name("skytech", "github.issue_list") == "mcp__skytech__github_issue_list"
    runner = ClaudeRunner(claude_request())
    assert runner._tool("mcp__skytech__skytech_test_data_list") == (
        "skytech",
        "skytech.test_data_list",
    )
    assert runner._tool("mcp__other__x_y") == ("other", "x_y")
    assert runner._tool("WebSearch") == (None, "WebSearch")


# --- Übergabe und Aufgabe -----------------------------------------------------


def test_handover_is_trimmed_to_contract_limits():
    handover = clean_handover(
        {
            "summary": "x" * 5000,
            "decisions": ["a"] * 30 + [5],
            "artifacts": [{"kind": "pr"}, {"kind": "pr", "ref": "1"}],
        }
    )
    assert len(handover["summary"]) == 4000
    assert len(handover["decisions"]) == 20
    assert handover["artifacts"] == [{"kind": "pr", "title": None, "ref": "1"}]
    assert clean_handover({"decisions": []}) is None


def test_task_without_context_is_the_prompt():
    assert build_task(" Tu es. ", None) == "Tu es."
    assert build_task("Tu es.", "Vorher").startswith("## Background")


# --- Läufe ohne Werkzeuge -----------------------------------------------------


class FakeProvider:
    answers: ClassVar[list] = []
    prompts: ClassVar[list] = []

    def execute(self, prompt, model=None, timeout=None):
        FakeProvider.prompts.append(prompt)
        answer = FakeProvider.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def effective_model(self, model=None):
        return model or "auto"


@pytest.fixture
def fake_provider(monkeypatch):
    FakeProvider.answers = []
    FakeProvider.prompts = []
    monkeypatch.setattr(
        "providers.factory.ProviderFactory.create", staticmethod(lambda name=None: FakeProvider())
    )
    return FakeProvider


def test_single_shot_run_with_other_provider(tmp_path, fake_provider):
    fake_provider.answers = [{"output": None, "handover": {"summary": "Erledigt."}}]
    manager = RunManager(str(tmp_path / "runs"), runner_factory=SingleShotRunner)
    run, _ = manager.start("run-2", claude_request(provider="gemini", tools={}, outputSchema=None))
    wait_until_done(run)

    assert run.status == "SUCCEEDED"
    assert run.handover["summary"] == "Erledigt."
    assert "handover" in fake_provider.prompts[0]
    assert fake_provider.prompts[0].index("Gestern lag PV") < fake_provider.prompts[0].index("Lies")


def test_single_shot_provider_error_is_passed_on(tmp_path, fake_provider):
    fake_provider.answers = [RuntimeError("Für Gemini ist kein Zugang hinterlegt.")]
    manager = RunManager(str(tmp_path / "runs"), runner_factory=SingleShotRunner)
    run, _ = manager.start("run-2", claude_request(provider="gemini", tools={}))
    wait_until_done(run)

    assert run.status == "FAILED"
    assert run.error == "Für Gemini ist kein Zugang hinterlegt."


# --- Verwaltung ---------------------------------------------------------------


class BlockingRunner:
    """Bleibt aktiv, bis der Test ihn freigibt."""

    release = False

    def __init__(self, request):
        pass

    def run(self, manager, run):
        manager.set_running(run)
        while not BlockingRunner.release and not run.cancel_requested:
            time.sleep(0.01)
        manager.finish(run, "SUCCEEDED", handover={"summary": "ok"})


@pytest.fixture
def blocking(tmp_path):
    BlockingRunner.release = False
    manager = RunManager(str(tmp_path / "runs"), runner_factory=BlockingRunner)
    yield manager
    BlockingRunner.release = True


def test_same_run_id_is_idempotent_and_different_input_conflicts(blocking):
    from runs import RunConflict

    first, created = blocking.start("a", claude_request())
    again, created_again = blocking.start("a", claude_request())
    assert created and not created_again and first is again
    with pytest.raises(RunConflict) as konflikt:
        blocking.start("a", claude_request(prompt="Etwas anderes"))
    assert konflikt.value.code == "RUN_ID_REUSED"


def test_only_two_runs_at_a_time(blocking):
    from runs import RunConflict

    blocking.start("a", claude_request())
    blocking.start("b", claude_request(runId="b"))
    with pytest.raises(RunConflict) as konflikt:
        blocking.start("c", claude_request(runId="c"))
    assert konflikt.value.code == "BUSY"


def test_runs_of_a_previous_process_fail_after_restart(tmp_path, blocking):
    run, _ = blocking.start("a", claude_request())
    deadline = time.monotonic() + 5
    while run.status != "RUNNING" and time.monotonic() < deadline:
        time.sleep(0.01)

    restarted = RunManager(blocking.directory, runner_factory=BlockingRunner)
    old = restarted.get("a")

    assert old.status == "FAILED"
    assert old.error == FEHLER_NEUSTART
    assert [e["type"] for e in old.events][-1] == "status"


# --- Schnittstelle ------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNIAI_API_TOKEN", TOKEN)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "abo-token")
    BlockingRunner.release = False
    monkeypatch.setattr(
        api_module, "runs", RunManager(str(tmp_path / "runs"), runner_factory=BlockingRunner)
    )
    flask_app.config["TESTING"] = True
    yield flask_app.test_client()
    BlockingRunner.release = True


@pytest.mark.parametrize(
    "change",
    [
        {"runId": "mit leerzeichen"},
        {"prompt": ""},
        {"context": "x" * 40_001},
        {"outputSchema": {"type": "kein-typ"}},
        {"tools": {"mcpServers": [{"name": "Skytech", "url": "http://x"}]}},
        {"tools": {"mcpServers": [{"name": "s", "url": "ftp://x"}]}},
        {"tools": {"mcpServers": [{"name": "s", "url": "http://x", "headers": {"a": 1}}]}},
        {"limits": {"maxMinutes": "30"}},
    ],
)
def test_malformed_runs_are_rejected(client, change):
    antwort = client.post("/v1/runs", headers=AUTH, json=claude_request(**change))

    assert antwort.status_code == 400
    assert antwort.get_json()["code"] == "VALIDATION_ERROR"


def test_start_state_cancel_over_http(client):
    gestartet = client.post("/v1/runs", headers=AUTH, json=claude_request())
    nochmal = client.post("/v1/runs", headers=AUTH, json=claude_request())
    anders = client.post("/v1/runs", headers=AUTH, json=claude_request(prompt="anders"))
    zustand = client.get("/v1/runs/run-1", headers=AUTH)
    abbruch = client.post("/v1/runs/run-1/cancel", headers=AUTH)

    assert gestartet.status_code == 202 and gestartet.get_json()["runId"] == "run-1"
    assert nochmal.status_code == 202
    assert anders.status_code == 409 and anders.get_json()["code"] == "RUN_ID_REUSED"
    assert zustand.status_code == 200
    assert abbruch.status_code == 202
    assert RUN_TOKEN not in json.dumps(zustand.get_json())


def test_tools_only_for_claude_and_credentials_required(client, monkeypatch):
    gemini = client.post("/v1/runs", headers=AUTH, json=claude_request(provider="gemini"))
    unbekannt = client.post("/v1/runs", headers=AUTH, json=claude_request(provider="mistral"))
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN")
    ohne_zugang = client.post("/v1/runs", headers=AUTH, json=claude_request())

    assert gemini.status_code == 422 and gemini.get_json()["code"] == "TOOLS_NOT_SUPPORTED"
    assert unbekannt.status_code == 422 and unbekannt.get_json()["code"] == "UNKNOWN_PROVIDER"
    assert (
        ohne_zugang.status_code == 503 and ohne_zugang.get_json()["code"] == "PROVIDER_UNAVAILABLE"
    )


def test_unknown_run_is_404(client):
    for antwort in (
        client.get("/v1/runs/gibt-es-nicht", headers=AUTH),
        client.get("/v1/runs/gibt-es-nicht/events", headers=AUTH),
        client.post("/v1/runs/gibt-es-nicht/cancel", headers=AUTH),
    ):
        assert antwort.status_code == 404
        assert antwort.get_json()["code"] == "NOT_FOUND"


def test_events_stream_resumes_after_last_event_id(client):
    client.post("/v1/runs", headers=AUTH, json=claude_request())
    BlockingRunner.release = True
    run = api_module.runs.get("run-1")
    wait_until_done(run)

    alles = client.get("/v1/runs/run-1/events", headers=AUTH).get_data(as_text=True)
    ab_zwei = client.get("/v1/runs/run-1/events", headers={**AUTH, "Last-Event-ID": "2"}).get_data(
        as_text=True
    )

    assert alles.startswith("id: 1\nevent: status\n")
    assert "event: handover" in alles
    assert "id: 1\n" not in ab_zwei and "id: 3\n" in ab_zwei


def test_runs_need_the_api_token(client):
    assert client.post("/v1/runs", json=claude_request()).status_code == 401
