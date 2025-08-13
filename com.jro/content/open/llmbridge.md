++
title = "LLMBridge"
date = 2025-08-13T00:00:00Z
draft = false
aliases = ["/llmbridge/"]
++

LLMBridge is a small, practical library to talk to multiple LLM providers through a single, consistent API, with optional SQLite/PostgreSQL logging and a curated model registry.

Install:

```bash
uv add llmbridge-py
# With PostgreSQL extras
uv add "llmbridge-py[postgres]"
```

CLI:

```bash
llmbridge init-db                 # initialize DB and seed models (uses DATABASE_URL or --sqlite)
llmbridge json-refresh            # load curated JSON model data
```

Why: keeping track of models, prices, and context windows across providers is hard and changes often. LLMBridge ships a small database schema and tools to refresh and curate model lists.

Generating JSON from PDFs:
- We parse provider PDFs (pricing/model tables) into structured JSONs.
- Use `llmbridge extract-from-pdfs` to generate raw JSONs from PDFs placed under `res/`.
- Run `llmbridge json-refresh` to load curated JSONs into your DB.

Examples live in the repo under `examples/`.

Links:
- GitHub: [juanre/llmbridge](https://github.com/juanre/llmbridge)

[![xkcd Machine Learning](https://imgs.xkcd.com/comics/machine_learning.png)](https://xkcd.com/1838/)

