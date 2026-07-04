import json
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Interface every AI provider (Claude, OpenAI, Gemini, ...) must implement."""

    @abstractmethod
    def execute(self, prompt: str) -> dict:
        """Run the prompt against the provider and return a parsed JSON dict."""
        raise NotImplementedError

    @staticmethod
    def parse_json(raw_output: str) -> dict:
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Provider returned invalid JSON: {exc}\nRaw output: {raw_output}"
            )
