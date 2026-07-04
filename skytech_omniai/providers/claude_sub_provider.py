import os
import subprocess

from providers.base_provider import BaseProvider

JSON_INSTRUCTION = (
    "\n\nIMPORTANT: Respond with raw JSON only. Do not wrap the response in "
    "markdown code fences, do not add any explanation before or after the "
    "JSON, and do not include any text that is not valid JSON."
)


class ClaudeSubProvider(BaseProvider):
    """Executes prompts through the Claude Code CLI using the user's Claude subscription
    instead of a metered API key, so requests draw on the existing Pro/Max plan."""

    def __init__(self):
        # Persist the CLI's login/session data on the add-on's protected /data volume
        # so it survives add-on restarts.
        os.environ["XDG_CONFIG_HOME"] = "/data"

    def execute(self, prompt: str) -> dict:
        full_prompt = prompt + JSON_INSTRUCTION

        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")

        return self.parse_json(result.stdout.strip())
