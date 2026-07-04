# Changelog

All notable changes to the Skytech OmniAI Home Assistant Add-on are documented in this file.

## [Unreleased]

### Added
- Initial project scaffolding for the Skytech OmniAI Home Assistant Add-on.
- `skytech_omniai/config.yaml`: Home Assistant add-on configuration exposing port 8000, mapping persistent `/data` storage, and defining the `provider` option (default `claude_sub`).
- `skytech_omniai/Dockerfile`: Alpine-based image installing Node.js/npm, Python 3, pip, the `@anthropic-ai/claude-code` CLI, and a Python virtualenv with Flask.
