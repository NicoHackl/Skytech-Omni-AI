import json
from abc import ABC, abstractmethod


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
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Provider returned invalid JSON: {exc}\nRaw output: {raw_output}"
            )
