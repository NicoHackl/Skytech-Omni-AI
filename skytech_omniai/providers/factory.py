import os

from providers.claude_sub_provider import ClaudeSubProvider

DEFAULT_PROVIDER = "claude_sub"

_PROVIDERS = {
    "claude_sub": ClaudeSubProvider,
}


class ProviderFactory:
    """Instantiates the configured AI provider by name, defaulting to the
    Claude Subscription provider so new providers can be plugged in later
    without touching app.py."""

    @staticmethod
    def create(name: str = None):
        provider_name = name or os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER)
        provider_cls = _PROVIDERS.get(provider_name)
        if provider_cls is None:
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available: {list(_PROVIDERS.keys())}"
            )
        return provider_cls()
