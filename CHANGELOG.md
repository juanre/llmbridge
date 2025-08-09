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