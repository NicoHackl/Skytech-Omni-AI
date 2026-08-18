import os
import subprocess

from providers.base_provider import JSON_INSTRUCTION, BaseProvider

# The Claude Code CLI defaults to an interactive coding-assistant persona that
# reads project context from the working directory and asks clarifying
# questions. That framing makes it refuse plain JSON requests. This system
# prompt overrides the persona so the CLI behaves as a headless JSON endpoint.
#
# Der zweite Absatz ist bewusst so deutlich formuliert: ohne ihn deutet das
# Modell "headless JSON endpoint" als "kein Internet" und lehnt Wetter- oder
# Nachrichtenfragen pauschal ab, statt die freigegebenen Web-Werkzeuge zu
# benutzen.
SYSTEM_PROMPT = (
    "You are a headless JSON generation endpoint, not an interactive coding "
    "assistant. You have no project, repository or working directory to reason "
    "about. Never ask clarifying questions and never refuse. "
    "You do have working internet access. Use the WebSearch and WebFetch "
    "tools whenever the answer depends on current, local or time-sensitive "
    "facts - weather, news, prices, opening hours, timetables, sports "
    "results. Never claim that you cannot access the internet and never guess "
    "such facts from memory. If a lookup genuinely fails, report the reason in "
    "an \"error\" field inside the JSON instead of inventing an answer. "
    "Always answer the user's request by returning exactly one valid JSON "
    "object and nothing else."
)

# Kurz-Aliasse, die die Claude-CLI versteht, in der Reihenfolge des
# Add-on-Dropdowns. Vollständige Modell-IDs sind über das Feld "model" im
# /ask-Body ebenfalls erlaubt.
CLAUDE_MODELS = ["sonnet", "opus", "haiku"]

# Freigabestufen für die Werkzeuge der Claude-CLI. Im Headless-Modus
# ("claude -p") gibt es keine interaktive Rückfrage: ohne ausdrückliche
# Freigabe lehnt die CLI jedes genehmigungspflichtige Werkzeug automatisch ab.
# Genau daran scheiterten bisher alle Anfragen, die eine Web-Recherche
# benötigen ("WebFetch ist unterbunden").
TOOL_ACCESS_OFF = "off"  # keine Werkzeuge - Verhalten vor Version 0.6.0
TOOL_ACCESS_WEB = "web"  # nur Websuche und Seitenabruf
TOOL_ACCESS_FULL = "full"  # alle Werkzeuge, inkl. Shell- und Dateizugriff
DEFAULT_TOOL_ACCESS = TOOL_ACCESS_FULL

# Die beiden Werkzeuge, die für Recherche-Antworten nötig sind. WebSearch
# findet die passende Quelle, WebFetch liest sie aus.
WEB_TOOLS = ["WebSearch", "WebFetch"]

MISSING_CREDENTIALS_MESSAGE = (
    "No Claude credentials configured. Open the add-on 'Configuration' tab and "
    "set 'claude_oauth_token'. Generate that token on a computer where you can "
    "log in to your Claude Pro/Max account by running 'claude setup-token', "
    "then paste the result into the add-on configuration and restart the "
    "add-on. Alternatively set 'anthropic_api_key' to use the metered API "
    "instead of the subscription."
)

# Ein Add-on läuft als root. Manche CLI-Versionen verweigern in dieser
# Konstellation das Umgehen der Berechtigungsabfrage. Erkennen wir das an der
# Fehlerausgabe, bekommt der Nutzer statt der englischen CLI-Meldung einen
# Hinweis auf die funktionierende Alternative.
ROOT_PERMISSION_MARKERS = ("root", "sudo")
PERMISSION_MARKERS = ("permission", "bypasspermissions", "skip-permissions")

TOOL_ACCESS_ROOT_HINT = (
    "Die Claude-CLI verweigert die Stufe 'full', weil das Add-on als root "
    "läuft. Stelle im Add-on unter 'Konfiguration' → 'tool_access' den Wert "
    "'web' ein (Websuche und Seitenabruf bleiben damit verfügbar) und starte "
    "das Add-on neu."
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

    def _resolve_tool_access(self) -> str:
        """Liest die Freigabestufe aus der Add-on-Konfiguration.

        Unbekannte oder leere Werte fallen auf den Standard zurück, damit eine
        vertippte Option nicht den kompletten Provider lahmlegt.
        """
        level = os.environ.get("OMNIAI_TOOL_ACCESS", "").strip().lower()
        if level in (TOOL_ACCESS_OFF, TOOL_ACCESS_WEB, TOOL_ACCESS_FULL):
            return level
        return DEFAULT_TOOL_ACCESS

    def _tool_access_args(self) -> list:
        """Übersetzt die Freigabestufe in Argumente für die Claude-CLI."""
        level = self._resolve_tool_access()
        if level == TOOL_ACCESS_OFF:
            return []
        if level == TOOL_ACCESS_WEB:
            # --allowedTools erwartet eine leerzeichengetrennte Liste; da hier
            # ohne Shell aufgerufen wird, ist jeder Name ein eigenes Element.
            return ["--allowedTools", *WEB_TOOLS]
        return ["--permission-mode", "bypassPermissions"]

    def _build_env(self) -> dict:
        env = os.environ.copy()
        token = env.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        if not token and not api_key:
            raise RuntimeError(MISSING_CREDENTIALS_MESSAGE)
        if self._resolve_tool_access() == TOOL_ACCESS_FULL:
            # Das Add-on läuft als root in einem isolierten Container. Ohne
            # diese Markierung lehnen manche CLI-Versionen
            # "bypassPermissions" unter root grundsätzlich ab.
            env["IS_SANDBOX"] = "1"
        return env

    def _resolve_model(self, model: str) -> str:
        """Pick the per-request model, else the add-on-wide OMNIAI_MODEL default."""
        chosen = (model or "").strip()
        if not chosen:
            chosen = os.environ.get("OMNIAI_MODEL", "").strip()
        return chosen

    def _cli_error_message(self, detail: str) -> str:
        """Ersetzt die root-Fehlermeldung der CLI durch einen brauchbaren Hinweis."""
        lowered = detail.lower()
        looks_like_root_refusal = any(
            marker in lowered for marker in ROOT_PERMISSION_MARKERS
        ) and any(marker in lowered for marker in PERMISSION_MARKERS)
        if self._resolve_tool_access() == TOOL_ACCESS_FULL and looks_like_root_refusal:
            return f"{TOOL_ACCESS_ROOT_HINT} (CLI-Meldung: {detail})"
        return f"Claude CLI failed: {detail}"

    def execute(self, prompt: str, model: str = None) -> dict:
        env = self._build_env()
        full_prompt = prompt + JSON_INSTRUCTION

        command = ["claude", "-p", full_prompt, "--append-system-prompt", SYSTEM_PROMPT]
        chosen_model = self._resolve_model(model)
        if chosen_model:
            # The Claude Code CLI accepts model aliases (sonnet/opus/haiku) as
            # well as full model IDs via --model.
            command += ["--model", chosen_model]
        command += self._tool_access_args()

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                # Run from the persistent data dir, not the add-on source tree, so
                # the CLI does not pick up any CLAUDE.md / project context and
                # reframe the request as a coding task.
                cwd="/data",
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "The 'claude' CLI was not found in the container. The add-on "
                "image may have failed to build correctly."
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(self._cli_error_message(detail))

        return self.parse_json(result.stdout.strip())
