import os
import subprocess

from providers.base_provider import BaseProvider

JSON_INSTRUCTION = (
    "\n\nIMPORTANT: Respond with raw JSON only. Do not wrap the response in "
    "markdown code fences, do not add any explanation before or after the "
    "JSON, and do not include any text that is not valid JSON."
)

MISSING_CREDENTIALS_MESSAGE = (
    "No Claude credentials configured. Open the add-on 'Configuration' tab and "
    "set 'claude_oauth_token'. Generate that token on a computer where you can "
    "log in to your Claude Pro/Max account by running 'claude setup-token', "
    "then paste the result into the add-on configuration and restart the "
    "add-on. Alternatively set 'anthropic_api_key' to use the metered API "
    "instead of the subscription."
)


class ClaudeSubProvider(BaseProvider):
    """Executes prompts through the Claude Code CLI using the user's Claude subscription
    instead of a metered API key, so requests draw on the existing Pro/Max plan."""

    def __init__(self):
        # Claude Code stores its config and credentials under $HOME/.claude.
        # Point HOME at the add-on's persistent /data volume so any CLI state
        # survives add-on restarts. (The previous XDG_CONFIG_HOME approach did
        # not work because the CLI keys its state off HOME, not XDG.)
        os.environ.setdefault("HOME", "/data")

    def _build_env(self) -> dict:
        env = os.environ.copy()
        token = env.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        if not token and not api_key:
            raise RuntimeError(MISSING_CREDENTIALS_MESSAGE)
        return env

    def execute(self, prompt: str) -> dict:
        env = self._build_env()
        full_prompt = prompt + JSON_INSTRUCTION

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "The 'claude' CLI was not found in the container. The add-on "
                "image may have failed to build correctly."
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Claude CLI failed: {detail}")

        return self.parse_json(result.stdout.strip())
