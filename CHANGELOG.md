# Changelog

All notable changes to the Skytech OmniAI Home Assistant Add-on are documented in this file.

## [Unreleased]

### Added
- Initial project scaffolding for the Skytech OmniAI Home Assistant Add-on.
- `skytech_omniai/config.yaml`: Home Assistant add-on configuration exposing port 8000, mapping persistent `/data` storage, and defining the `provider` option (default `claude_sub`).
- `skytech_omniai/Dockerfile`: Alpine-based image installing Node.js/npm, Python 3, pip, the `@anthropic-ai/claude-code` CLI, and a Python virtualenv with Flask.
- `skytech_omniai/providers/base_provider.py`: Abstract `BaseProvider` class defining the `execute(prompt) -> dict` interface and a shared `parse_json` helper that all future providers (Claude, OpenAI, Gemini, ...) must use.
- `skytech_omniai/providers/claude_sub_provider.py`: `ClaudeSubProvider` runs prompts through the Claude Code CLI (`claude -p`) via `subprocess`, sets `XDG_CONFIG_HOME=/data` for persistent login across add-on restarts, and appends a strict instruction forcing raw JSON output (no markdown fences).
- `skytech_omniai/providers/factory.py`: `ProviderFactory` picks the AI provider implementation by name (request parameter or `AI_PROVIDER` env var), defaulting to `claude_sub`, so additional providers can be registered without changing `app.py`.
