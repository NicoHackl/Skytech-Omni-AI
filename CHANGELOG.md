# Changelog

All notable changes to the Skytech OmniAI Home Assistant Add-on are documented in this file.

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
