# Changelog

## Unreleased

Breaking changes:
- CLI renamed from `llm-models` to `llmbridge`. Update your scripts/automation accordingly.
- OpenAI PDF handling unified: we continue to support PDF analysis via the OpenAI Assistants API pathway, but the internal API changed and deprecation warnings are suppressed. PDF path still does not allow tools or custom response_format.

Features:
- Added `llmbridge init-db` command to initialize the database schema and seed curated models for both PostgreSQL (via `DATABASE_URL`) and SQLite (`--sqlite path`).
- OpenAI o1/o1-mini routed via Responses API (no tools or response_format).

Fixes:
- Do not pass unsupported kwargs from SQLite service to providers; only non-None supported parameters are sent. Also ensure `called_at` is provided when logging calls.
- Ollama model listing uses SDK’s dict response shape consistently.
- PostgreSQL migrations now use `pgcrypto` and `gen_random_uuid()` for UUIDs.
- Guarded None pricing in Postgres cost calculation.
- Removed deprecated usage-hints service methods relying on private db internals.
- For OpenAI Chat Completions vision, remote image URLs are left intact in request content and only inlined to data URLs at send-time, preserving original content for tests and callers.

Docs:
- Updated README and docs/API.md for new CLI name, init-db, initialization patterns (managed vs injected pgdbm), pgcrypto note, and OpenAI o1/Responses behavior.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-09

### Added
- Initial release of LLMBridge
- Unified interface for OpenAI, Anthropic, Google, and Ollama LLMs
- Optional SQLite database for local development
- Optional PostgreSQL database for production use
- Built-in response caching with TTL support
- Model registry with cost tracking
- Usage statistics and API call logging
- Command-line interface for model management
- Support for image and file processing
- Function calling and tool use across providers
- JSON mode and structured output support
- Comprehensive test suite
- MIT License for open source use

### Features
- Simple API: Single interface for all LLM providers
- Database flexibility: SQLite for local dev, PostgreSQL for production
- Smart caching: Opt-in response caching for deterministic requests
- Cost tracking: Monitor usage and costs across providers
- Model discovery: Auto-refresh models from provider APIs
- CLI tools: Manage models, view stats, and configure the service

### Supported Providers
- OpenAI (GPT-4, GPT-4o, GPT-3.5)
- Anthropic (Claude 3 Opus, Sonnet, Haiku, Claude 3.5 Sonnet)
- Google (Gemini Pro, Gemini Flash)
- Ollama (Local models)

[0.1.0]: https://github.com/juanreyero/llmbridge/releases/tag/v0.1.0