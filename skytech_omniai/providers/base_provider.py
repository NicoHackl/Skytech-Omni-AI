import json
import re
from abc import ABC, abstractmethod

# Matches a fenced code block, optionally tagged (```json ... ```), capturing
# the inner body so we can unwrap it before parsing.
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\s*\n?(.*?)\n?```$", re.DOTALL)
# Matches the first balanced-looking JSON object or array embedded in prose.
_EMBEDDED_JSON_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


class BaseProvider(ABC):
    """Interface every AI provider (Claude, OpenAI, Gemini, ...) must implement."""

    @abstractmethod
    def execute(self, prompt: str, model: str = None) -> dict:
        """Run the prompt against the provider and return a parsed JSON dict.

        ``model`` optionally selects a specific model within the provider; when
        ``None`` the provider falls back to its own default (or the add-on-wide
        default configured via the ``OMNIAI_MODEL`` environment variable).
        """
        raise NotImplementedError

    @staticmethod
    def parse_json(raw_output: str) -> dict:
        """Parse the model output into a dict, tolerating common LLM wrappers.

        Models frequently wrap valid JSON in Markdown code fences or surround it
        with explanatory prose despite instructions. We therefore try, in order:
        the raw string, the string with code fences stripped, and finally the
        first embedded JSON object/array found in the text.
        """
        text = (raw_output or "").strip()

        candidates = [text]

        fence_match = _FENCE_RE.match(text)
        if fence_match:
            candidates.append(fence_match.group(1).strip())

        embedded_match = _EMBEDDED_JSON_RE.search(text)
        if embedded_match:
            candidates.append(embedded_match.group(1).strip())

        for candidate in candidates:
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        raise ValueError(f"Provider returned invalid JSON.\nRaw output: {raw_output}")
