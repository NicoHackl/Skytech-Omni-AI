import json
import os

# Home Assistant's Supervisor writes the add-on options (everything the user
# enters in the add-on "Configuration" tab) to this file inside the container.
OPTIONS_PATH = "/data/options.json"


def load_options() -> dict:
    """Read the Home Assistant add-on options from /data/options.json.

    Returns an empty dict when the file is missing so the app can still be run
    locally (outside Home Assistant) for development and testing.
    """
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Failed to read add-on options at {OPTIONS_PATH}: {exc}"
        ) from exc


def apply_options_to_env(options: dict) -> None:
    """Map the add-on options onto the environment variables the providers and
    the Claude CLI expect, so the whole add-on is configured from the HA UI.
    """
    provider = (options.get("provider") or "").strip()
    if provider:
        os.environ["AI_PROVIDER"] = provider

    # Add-on-wide default model. A per-request "model" in the /ask payload wins;
    # this only applies when the request does not specify one.
    model = (options.get("model") or "").strip()
    if model:
        os.environ["OMNIAI_MODEL"] = model

    # Long-lived Claude Pro/Max subscription token. Generate it once on a
    # machine where you can log in with a browser via `claude setup-token`,
    # then paste the result into the add-on configuration.
    token = (options.get("claude_oauth_token") or "").strip()
    if token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token

    # Optional fallback: metered Anthropic API key (not the subscription).
    api_key = (options.get("anthropic_api_key") or "").strip()
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
