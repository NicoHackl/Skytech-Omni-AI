"""Diagnosejournal des Add-ons für Skytech X (D-039, Vertrag omniai-api-v1 1.5.0).

Gleiches Ereignisformat wie das Journal des Backends (Version 1): Maschinenkennungen, Ausgang,
Dauer, stabile Fehlercodes und Ursachen nur als Typ plus Codestellen. **Nie** Prompts, Antworten,
Werkzeugargumente, Tokens, Exception-Meldungen oder Fremdtexte. Das Backend holt die Ereignisse über
``GET /v1/diagnostics/events`` ab und legt sie mit ``source: omniai`` in sein eigenes Journal.

Korrelation: ``X-Correlation-Id`` des Backends (nur UUID) wird zur ``traceId`` aller Ereignisse
der Anfrage und des daraus gestarteten Laufs. Jedes Ereignis hat eine fortlaufende ``seq``, die
über Neustarts erhalten bleibt; das Backend merkt sich die zuletzt abgeholte.

Ablage als JSONL-Segmente unter ``OMNIAI_DIAGNOSTICS_DIR`` (Vorgabe ``/data/diagnostics``),
Rechte 0600, höchstens ``MAX_BYTES`` insgesamt und ``RETENTION_DAYS`` Tage.
"""

import contextlib
import contextvars
import json
import logging
import os
import re
import threading
import time
import traceback
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

log = logging.getLogger("omniai.diagnostics")

SCHEMA_VERSION = 1
SEGMENT_BYTES = 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
RETENTION_DAYS = 30
MAX_PAGE = 500

KINDS = {
    "HTTP_START": "HTTP-Anfrage begonnen",
    "HTTP_END": "HTTP-Anfrage abgeschlossen",
    "OPERATION_START": "Arbeitsschritt begonnen",
    "OPERATION_END": "Arbeitsschritt abgeschlossen",
    "FAILURE": "Fehler erfasst",
    "LIFECYCLE": "Diagnosejournal gestartet",
}
OUTCOMES = {"STARTED", "SUCCESS", "REJECTED", "ERROR", "SLOW"}

_UUID = re.compile(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
_IDENTIFIER = re.compile(r"[^A-Za-z0-9_.$#<>:/{}* -]")
_CODE = re.compile(r"[A-Z0-9_]{1,64}")

trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)


def identifier(value: str | None) -> str | None:
    """Maschinenkennung ohne Freitext: erlaubte Zeichen, höchstens 240."""
    if value is None:
        return None
    return _IDENTIFIER.sub("_", str(value))[:240]


def uuid_or_none(value: str | None) -> str | None:
    return value if isinstance(value, str) and _UUID.fullmatch(value) else None


def code_or_none(value: str | None) -> str | None:
    return value if isinstance(value, str) and _CODE.fullmatch(value) else None


def failures_of(error: BaseException | None) -> list[dict]:
    """Bis zu vier Ursachen mit je höchstens zwölf Codestellen, ohne Meldung und Dateipfad."""
    result = []
    cause = error
    while cause is not None and len(result) < 4:
        frames = [
            identifier(f"{Path(frame.filename).stem}.{frame.name}:{frame.lineno}")
            for frame in traceback.extract_tb(cause.__traceback__)[-12:]
        ]
        result.append({"type": identifier(type(cause).__qualname__), "frames": frames})
        cause = cause.__cause__ or cause.__context__
    return result


class Journal:
    """Schreibt Ereignisse threadsicher; Lesen per ``seq`` für das Backend."""

    def __init__(self, directory: str | None = None):
        self.directory = Path(
            directory or os.environ.get("OMNIAI_DIAGNOSTICS_DIR", "/data/diagnostics")
        )
        self.instance_id = str(uuid.uuid4())
        self.version = identifier(_addon_version())
        self.lock = threading.Lock()
        self.dropped = 0
        self.enabled = True
        self._seq = None
        self._segment: Path | None = None
        self._last_maintenance = 0.0

    # --- Schreiben ------------------------------------------------------

    def record(
        self,
        kind: str,
        operation: str,
        outcome: str,
        duration_micros: int = 0,
        http_status: int | None = None,
        error_code: str | None = None,
        error: BaseException | None = None,
        run: str | None = None,
    ) -> None:
        if not self.enabled or kind not in KINDS or outcome not in OUTCOMES:
            return
        try:
            with self.lock:
                self._ensure_ready()
                self._seq += 1
                event = {
                    "schemaVersion": SCHEMA_VERSION,
                    "seq": self._seq,
                    "id": str(uuid.uuid4()),
                    "instanceId": self.instance_id,
                    "serviceVersion": self.version,
                    "timestamp": datetime.now(UTC)
                    .isoformat(timespec="microseconds")
                    .replace("+00:00", "Z"),
                    "kind": kind,
                    "message": KINDS[kind],
                    "traceId": uuid_or_none(trace_id.get()),
                    "runId": run or run_id.get(),
                    "operation": identifier(operation),
                    "outcome": outcome,
                    "durationMicros": max(0, int(duration_micros)),
                    "httpStatus": http_status,
                    "errorCode": code_or_none(error_code),
                    "failures": failures_of(error),
                }
                line = json.dumps(event, ensure_ascii=False) + "\n"
                segment = self._current_segment(len(line.encode()))
                fd = os.open(segment, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a", encoding="utf-8") as stream:
                    stream.write(line)
                if time.monotonic() - self._last_maintenance > 300:
                    self._maintenance()
        except OSError:
            self.dropped += 1
            log.warning("Diagnoseereignis konnte nicht gespeichert werden")

    @contextlib.contextmanager
    def operation(self, name: str, error_codes=None):
        """Misst einen Arbeitsschritt; Ausnahmen werden mit Code erfasst und weitergereicht."""
        self.record("OPERATION_START", name, "STARTED")
        started = time.perf_counter_ns()
        try:
            yield
        except BaseException as error:
            code = (error_codes or {}).get(type(error).__name__) or code_for(error)
            self.record(
                "OPERATION_END",
                name,
                "ERROR",
                (time.perf_counter_ns() - started) // 1000,
                error_code=code,
                error=error,
            )
            raise
        self.record("OPERATION_END", name, "SUCCESS", (time.perf_counter_ns() - started) // 1000)

    # --- Lesen ------------------------------------------------------------

    def read(self, after: int, limit: int) -> dict:
        """Ereignisse mit ``seq`` > ``after``, aufsteigend; ``head`` ist die jüngste ``seq``."""
        limit = max(1, min(limit, MAX_PAGE))
        events: list[dict] = []
        with self.lock:
            self._ensure_ready()
            head = self._seq
            segments = self._segments()
        for segment in segments:
            try:
                with open(segment, encoding="utf-8") as stream:
                    for line in stream:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(event, dict) and event.get("seq", 0) > after:
                            events.append(event)
                            if len(events) >= limit:
                                break
            except OSError:
                continue
            if len(events) >= limit:
                break
        oldest = None
        if segments:
            oldest = self._first_seq(segments[0])
        return {
            "instanceId": self.instance_id,
            "events": events,
            "next": events[-1]["seq"] if events else after,
            "head": head,
            "oldest": oldest,
            "dropped": self.dropped,
        }

    # --- Ablage -----------------------------------------------------------

    def _ensure_ready(self) -> None:
        if self._seq is not None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self.directory, 0o700)
        self._seq = 0
        for segment in reversed(self._segments()):
            last = self._last_seq(segment)
            if last is not None:
                self._seq = last
                break

    def _segments(self) -> list[Path]:
        return sorted(self.directory.glob("events-*.jsonl"))

    def _current_segment(self, size: int) -> Path:
        if self._segment is None or not self._segment.exists():
            existing = self._segments()
            self._segment = existing[-1] if existing else None
        if self._segment is None or self._segment.stat().st_size + size > SEGMENT_BYTES:
            self._segment = self.directory / f"events-{time.time_ns():020d}.jsonl"
        return self._segment

    def _maintenance(self) -> None:
        self._last_maintenance = time.monotonic()
        segments = self._segments()
        limit = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        total = sum(s.stat().st_size for s in segments)
        for segment in segments[:-1]:
            old = datetime.fromtimestamp(segment.stat().st_mtime, UTC) < limit
            if old or total > MAX_BYTES:
                total -= segment.stat().st_size
                segment.unlink(missing_ok=True)

    @staticmethod
    def _last_seq(segment: Path) -> int | None:
        last = None
        with contextlib.suppress(OSError), open(segment, encoding="utf-8") as stream:
            for line in stream:
                with contextlib.suppress(ValueError, AttributeError):
                    last = json.loads(line).get("seq", last)
        return last

    @staticmethod
    def _first_seq(segment: Path) -> int | None:
        with contextlib.suppress(OSError), open(segment, encoding="utf-8") as stream:
            for line in stream:
                with contextlib.suppress(ValueError, AttributeError):
                    return json.loads(line).get("seq")
        return None


def _addon_version() -> str:
    """Version aus config.yaml des Add-ons; im Test oder ohne Datei „dev"."""
    try:
        from config_loader import read_addon_version

        return read_addon_version() or "dev"
    except Exception:  # Version ist nur Beiwerk, darf das Journal nie aufhalten
        return "dev"


def code_for(error: BaseException) -> str:
    """Stabiler Code aus dem Ausnahmetyp der Anbieter (keine Meldung)."""
    name = type(error).__name__
    return {
        "ProviderTimeout": "TIMEOUT",
        "UnknownModel": "UNKNOWN_MODEL",
        "NotJson": "NOT_JSON",
        "UnsupportedEffort": "UNSUPPORTED_EFFORT",
        "RuntimeError": "PROVIDER_UNAVAILABLE",
    }.get(name, "INTERNAL")


journal = Journal()
