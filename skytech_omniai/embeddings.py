"""Embeddings für Skytech X (Vertrag v1 1.2.0, ``POST /v1/embeddings``, D-023).

Das Backend von Skytech X sucht im gemeinsamen Wissen nach Bedeutung. Dafür braucht
es Zahlenvektoren je Text. Vorgabe des Users: ausschließlich das günstige Modell
``gemini-embedding-001`` über den hinterlegten Gemini-Schlüssel — kein anderes
Modell, keine Auswahl. Die Texte gehen dafür an Google.

Wie der Gemini-Provider spricht dieses Modul die API über ``urllib`` an.
"""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("omniai.embeddings")

MODEL = "gemini-embedding-001"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":batchEmbedContents"
DIMENSIONS = (768, 1536, 3072)
DEFAULT_DIMENSIONS = 768
TASK_TYPES = ("RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY")
MAX_INPUTS = 100
MAX_INPUT_LENGTH = 8000
TIMEOUT_SEKUNDEN = 60

FEHLER_KEIN_SCHLUESSEL = "Für Embeddings ist kein Gemini-Schlüssel hinterlegt."
FEHLER_GOOGLE = "Google hat die Embeddings nicht geliefert. Bitte später erneut versuchen."
FEHLER_ZEIT = "Google hat zu lange für die Embeddings gebraucht."


class EmbeddingTimeout(RuntimeError):
    """Google hat nicht rechtzeitig geantwortet."""


def api_key() -> str:
    """Gemini-Schlüssel aus der Umgebung, wie beim Gemini-Provider; leer = keiner."""
    return (os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")).strip()


def available() -> bool:
    return bool(api_key())


def embed(
    texts: list[str], task_type: str, dimensions: int
) -> tuple[list[list[float]], int | None]:
    """Vektoren in der Reihenfolge der Texte und die gezählten Eingabe-Tokens.

    :raises RuntimeError: ohne Schlüssel oder bei Fehlern von Google (Satz für den Aufrufer)
    :raises EmbeddingTimeout: bei Zeitüberschreitung
    """
    key = api_key()
    if not key:
        raise RuntimeError(FEHLER_KEIN_SCHLUESSEL)
    body = {
        "requests": [
            {
                "model": "models/" + MODEL,
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": dimensions,
            }
            for text in texts
        ]
    }
    request = urllib.request.Request(
        os.environ.get("OMNIAI_EMBEDDINGS_URL", API_URL),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEKUNDEN) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        try:
            detail = (
                json.loads(fehler.read().decode("utf-8", errors="replace"))
                .get("error", {})
                .get("message", "")
            )
        except (ValueError, AttributeError, OSError):
            detail = ""
        log.error(
            "Embeddings: Google antwortete mit Code %s: %s", fehler.code, detail or "keine Meldung"
        )
        raise RuntimeError(FEHLER_GOOGLE) from fehler
    except TimeoutError as fehler:
        raise EmbeddingTimeout(FEHLER_ZEIT) from fehler
    except urllib.error.URLError as fehler:
        if isinstance(fehler.reason, TimeoutError):
            raise EmbeddingTimeout(FEHLER_ZEIT) from fehler
        log.error("Embeddings: Google nicht erreichbar: %s", fehler.reason)
        raise RuntimeError(FEHLER_GOOGLE) from fehler

    vectors = [e.get("values") for e in payload.get("embeddings") or []]
    if len(vectors) != len(texts) or not all(isinstance(v, list) and v for v in vectors):
        log.error(
            "Embeddings: unerwartete Antwort von Google (%s Vektoren für %s Texte)",
            len(vectors),
            len(texts),
        )
        raise RuntimeError(FEHLER_GOOGLE)
    tokens = (payload.get("usageMetadata") or {}).get("promptTokenCount")
    return vectors, tokens if isinstance(tokens, int) else None
