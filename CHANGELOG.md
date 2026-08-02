# Changelog

All notable changes to the Skytech OmniAI Home Assistant Add-on are documented in this file.

## [0.5.0]

### Added
- **Google Gemini as a second provider.** The add-on is no longer Claude-only; `provider` can now be set to `gemini`, which the `config.yaml` schema previously rejected (`list(claude_sub)`).
  - `providers/gemini_provider.py`: `GeminiProvider` calls Google's **Interactions API** (`POST https://generativelanguage.googleapis.com/v1beta/interactions`), the primary Gemini interface as of 2026, superseding `generateContent`. The API key is sent as an `x-goog-api-key` header rather than a URL parameter so it cannot leak into logs or proxies, and `store: false` keeps Google from retaining the conversation server-side.
  - The HTTP call uses `urllib.request` from the standard library — **no new dependencies**. The image is Alpine/musl and builds for `armv7`/`armhf`/`i386`, where the official SDK would drag in `pydantic-core` and a Rust toolchain. `Dockerfile` is unchanged; `COPY providers ./providers` already picks up the new module.
  - Response text is read from the Interactions step timeline (`steps[].content[].text`, preferring `model_output` steps) with a fallback that scans every step, so a future rename of the step types degrades instead of breaking.
  - Errors are surfaced in plain German instead of a stack trace: missing key (with a link to Google AI Studio), invalid/unauthorized key (401/403), unknown model (404), exhausted quota (429), overloaded API (503), and network/timeout failures.
  - New add-on option `gemini_api_key` (password), mapped by `config_loader.py` onto `GEMINI_API_KEY`. `GOOGLE_API_KEY` is accepted as a fallback.
- **Model registry with the current Gemini models**, selectable per request and add-on-wide: `gemini-flash-latest` (default alias), `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`. Any other `gemini-*` ID is accepted too, so new Google models work without a code change; non-Gemini values (e.g. a leftover `sonnet`) are rejected with a message listing the valid IDs.
- **`GET /models`** returns the active provider plus the selectable models and default model per provider, so Home Assistant scripts can discover valid values instead of hard-coding them.

### Changed
- **`model` is now a dropdown instead of a free-text field** (`config.yaml`), shared by both providers: `auto`, the Claude aliases (`sonnet`/`opus`/`haiku`), and the Gemini IDs. It only constrains the add-on-wide default — the `model` field in the `/ask` payload still accepts any string.
- `JSON_INSTRUCTION` moved from `claude_sub_provider.py` to `base_provider.py`; it is provider-independent and now shared by both providers.
- `providers/factory.py` registers `gemini`. `DEFAULT_PROVIDER` stays `claude_sub`, so existing installations are unaffected.

### Migration
- The `model` option previously defaulted to `""`, which is not a valid member of the new `list(...)` schema. After updating, Home Assistant reports the configuration as invalid once — open the add-on configuration, pick `auto` (or the desired model) and save.

## [0.3.0]

### Added
- **Per-request model selection.** `POST /ask` now accepts an optional `model` field alongside `prompt` and `provider`. When set, `ClaudeSubProvider` passes it to the Claude CLI via `--model` (accepts aliases `sonnet`/`opus`/`haiku` or full model IDs). Omitting it keeps the CLI default.
  - `app.py` reads `model` from the payload and forwards it to `provider.execute(prompt, model=...)`.
  - `BaseProvider.execute` signature extended to `execute(prompt, model=None)`.
  - `ClaudeSubProvider._resolve_model` prefers the per-request model, then falls back to the add-on-wide default.
  - New optional `model` add-on option (`config.yaml`), mapped by `config_loader.py` onto the `OMNIAI_MODEL` environment variable as the fallback default.

## [0.2.0]

### Fixed
- **Authentication is now actually configurable — the add-on could not be logged in before.** A headless HA add-on cannot run the interactive `claude login` browser flow, and there was no field to enter any credential, so every `/ask` call ran an unauthenticated `claude` CLI and failed.
  - Added `claude_oauth_token` (password) and `anthropic_api_key` (password) options to `config.yaml`; both optional.
  - Added `config_loader.py`, which reads the Supervisor-written `/data/options.json` at start-up and maps the options onto `AI_PROVIDER`, `CLAUDE_CODE_OAUTH_TOKEN`, and `ANTHROPIC_API_KEY`. Previously nothing read the add-on options at all, so even the `provider` selection was ignored.
  - `ClaudeSubProvider` now passes those environment variables into the `claude` subprocess and raises a clear, instructive error when no credential is set.
  - Replaced the non-functional `XDG_CONFIG_HOME=/data` persistence with `HOME=/data`; the Claude CLI keys its state off `HOME`, not `XDG_CONFIG_HOME`.
  - Restricted the `provider` schema to the only implemented provider (`list(claude_sub)`); selecting `openai`/`gemini` previously raised "Unknown provider".
  - Documented the `claude setup-token` set-up flow in `info.md`.
  - `Dockerfile` now copies `config_loader.py` into the image.

## [Unreleased]

### Added
- Initial project scaffolding for the Skytech OmniAI Home Assistant Add-on.
- `config.yaml`: Home Assistant add-on configuration exposing port 8000, mapping persistent `/data` storage, and defining the `provider` option (default `claude_sub`).
- `Dockerfile`: Alpine-based image installing Node.js/npm, Python 3, pip, the `@anthropic-ai/claude-code` CLI, and a Python virtualenv with Flask.
- `providers/base_provider.py`: Abstract `BaseProvider` class defining the `execute(prompt) -> dict` interface and a shared `parse_json` helper that all future providers (Claude, OpenAI, Gemini, ...) must use.
- `providers/claude_sub_provider.py`: `ClaudeSubProvider` runs prompts through the Claude Code CLI (`claude -p`) via `subprocess`, sets `XDG_CONFIG_HOME=/data` for persistent login across add-on restarts, and appends a strict instruction forcing raw JSON output (no markdown fences).
- `providers/factory.py`: `ProviderFactory` picks the AI provider implementation by name (request parameter or `AI_PROVIDER` env var), defaulting to `claude_sub`, so additional providers can be registered without changing `app.py`.
- `app.py`: Flask server listening on port 8000, exposing `POST /ask` (routes a `prompt` to the provider factory and returns its JSON response) and `GET /health` for container health checks.
- `.gitignore`: Excludes Python `__pycache__`/`.pyc` artifacts from version control.

### Fixed
- **Corrected the repository layout so Home Assistant accepts it as a valid add-on repository.** A HA add-on *repository* requires a `repository.yaml` (or `.json`) manifest at the root and each add-on in its own subfolder. The previous flat layout (add-on files directly in the root, no `repository.yaml`) was still reported as "not a valid add-on repository".
  - Added `repository.yaml` at the repo root (`name`, `url`, `maintainer`) so the Supervisor recognizes the repository.
  - Moved the add-on files (`config.yaml`, `Dockerfile`, `app.py`, `providers/`, `info.md`) back into the `skytech_omniai/` subfolder, which is the required per-add-on directory.

### Changed
- Earlier (incorrect) attempt: moved the add-on files out of `skytech_omniai/` into the repo root. This was reverted — the real cause of the validation error was the missing `repository.yaml`, not the subfolder depth.
