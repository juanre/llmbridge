# LLMBridge

A unified Python service for interacting with multiple LLM providers (OpenAI, Anthropic, Google, Ollama) with automatic model management, usage tracking, and cost calculation.

## Features

- **Unified Interface**: Single API for all LLM providers
- **Database Options**: Use SQLite for local development or PostgreSQL for production
- **Automatic Model Registry**: Pre-configured with latest models and pricing
- **Usage Tracking**: Track API calls, costs, and usage patterns
- **File Support**: Handle images and PDFs across providers
- **Type Safety**: Full type hints and Pydantic validation

## Installation

```bash
# Using uv (recommended)
uv add llmbridge

# Using pip
pip install llmbridge
```

## Quick Start

### 1. Basic Usage (No Database)

```python
import asyncio
from llmbridge.service import LLMBridge
from llmbridge.schemas import LLMRequest, Message

async def main():
    # Initialize service without database
    service = LLMBridge(enable_db_logging=False)
    
    # Make a request
    request = LLMRequest(
        messages=[Message(role="user", content="Hello!")],
        model="gpt-4o-mini"
    )
    
    response = await service.chat(request)
    print(response.content)

asyncio.run(main())
```

### 2. With SQLite Database (Local Development)

```python
import asyncio
from llmbridge.service_sqlite import LLMBridgeSQLite
from llmbridge.schemas import LLMRequest, Message

async def main():
    # Initialize with SQLite (default: llmbridge.db)
    service = LLMBridgeSQLite()
    
    # Or specify a custom SQLite file
    service = LLMBridgeSQLite(db_path="my_app.db")
    
    # Make requests - all calls are logged to database
    request = LLMRequest(
        messages=[Message(role="user", content="Hello!")],
        model="claude-3-5-haiku-20241022"
    )
    
    response = await service.chat(request)
    print(f"Response: {response.content}")
    print(f"Cost: ${response.usage.get('cost', 0):.4f} if tracked")

asyncio.run(main())
```

### 3. With PostgreSQL Database (Production)

```python
import asyncio
from llmbridge.service import LLMBridge

async def main():
    # Initialize with PostgreSQL
    service = LLMBridge(
        db_connection_string="postgresql://user:pass@localhost/dbname"
    )
    
    # Your application code here
    ...

asyncio.run(main())
```

## Database Setup

### SQLite (Automatic)
No setup needed! The database and tables are created automatically when you first use it.

### PostgreSQL
```bash
# 1. Create database
createdb llmbridge

# 2. Run migrations (automatic on first use)
# Tables and default models are created automatically
```

## Model Management

### List Available Models

```python
from llmbridge.db_sqlite import SQLiteDatabase

async def list_models():
    db = SQLiteDatabase()  # Uses SQLite
    await db.initialize()
    
    # List all active models
    models = await db.list_models()
    for model in models:
        print(f"{model.provider}:{model.model_name} - ${model.dollars_per_million_tokens_input}/M input")
    
    await db.close()
```

### Get Usage Statistics

```python
async def get_usage():
    # For SQLite
    from llmbridge.db_sqlite import SQLiteDatabase
    db = SQLiteDatabase()
    
    # For PostgreSQL
    # from llmbridge.db import LLMDatabase
    # db = LLMDatabase(connection_string="postgresql://...")
    
    await db.initialize()
    
    # Get usage for last 30 days
    stats = await db.get_usage_stats(days=30)
    print(f"Total calls: {stats.total_calls}")
    print(f"Total cost: ${stats.total_cost:.2f}")
    
    await db.close()
```

## Command-line Interface (CLI)

The package installs a CLI named `llm-models` for managing the model registry.

### Prerequisites
- For PostgreSQL mode: a running PostgreSQL and DB env vars
- For SQLite mode: a writable path to an .db file

Create a `.env` or export variables in your shell:

```bash
# Option A: PostgreSQL (server)
export DATABASE_HOST=localhost
export DATABASE_PORT=5432
export DATABASE_NAME=postgres
export DATABASE_USER=postgres
export DATABASE_PASSWORD=postgres
export DATABASE_SCHEMA=llmbridge

# Option B: SQLite (local file)
# Either set the env var, or pass --sqlite path on the CLI
export LLMBRIDGE_SQLITE_DB=./llmbridge.db

# Provider API keys (used for discovery/pricing or generation)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=...
export OLLAMA_BASE_URL=http://localhost:11434
```

### Initialize database schema and migrations
Run once to create the schema and apply migrations.

- PostgreSQL mode:
```bash
python -m llmbridge.scripts.setup_database setup
python -m llmbridge.scripts.setup_database status
# DANGEROUS: delete and recreate
python -m llmbridge.scripts.setup_database reset --force
```

- SQLite mode: tables are auto-created on first use (no migrations step).

### Populate the models database
Two options: discover from provider APIs (PostgreSQL only), or load from JSON files (PostgreSQL and SQLite).

- Option A: Discover via provider APIs (PostgreSQL only)
```bash
llm-models refresh --dry-run
llm-models refresh
llm-models refresh --enable-pricing
```

- Option B: Load curated JSONs (PostgreSQL or SQLite)
```bash
# Generate JSONs (optional helper)
llm-models extract-from-pdfs download-instructions
llm-models extract-from-pdfs generate

# Apply to Postgres
llm-models json-refresh

# Apply to SQLite (use flag or env var)
llm-models --sqlite ./llmbridge.db json-refresh
# or
LLMBRIDGE_SQLITE_DB=./llmbridge.db llm-models json-refresh

# Preview
llm-models --sqlite ./llmbridge.db json-refresh --dry-run
```

### Inspecting and maintaining the registry

- PostgreSQL
```bash
llm-models list
llm-models search --vision --max-cost 5
llm-models info anthropic:claude-3-5-sonnet-20241022
llm-models suggest cheapest_good
llm-models status
llm-models clean free-models
llm-models clean wipe-all --force
```

- SQLite
```bash
llm-models --sqlite ./llmbridge.db list
llm-models --sqlite ./llmbridge.db search --vision --max-cost 5
llm-models --sqlite ./llmbridge.db info anthropic:claude-3-5-sonnet-20241022
# Heuristic suggestions and status
llm-models --sqlite ./llmbridge.db suggest --all
llm-models --sqlite ./llmbridge.db status
# Maintenance
llm-models --sqlite ./llmbridge.db clean free-models
llm-models --sqlite ./llmbridge.db clean wipe-all --force
```

Notes:
- In SQLite mode, `refresh` (API discovery) is not supported; use `json-refresh`.
- Suggestions in SQLite mode are heuristic (computed in CLI) rather than DB functions.
- Backups apply to PostgreSQL; for SQLite, back up the `.db` file as needed.

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# API Keys (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...  # or GEMINI_API_KEY
OLLAMA_API_BASE=http://localhost:11434  # Optional

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost/dbname  # For PostgreSQL
# Or leave unset to use SQLite
```

### Provider-Specific Models

```python
# Explicitly specify provider
response = await service.chat(
    LLMRequest(
        messages=[Message(role="user", content="Hello")],
        model="anthropic:claude-3-5-sonnet-20241022"  # Provider prefix
    )
)

# Auto-detection also works
response = await service.chat(
    LLMRequest(
        messages=[Message(role="user", content="Hello")],
        model="gpt-4o"  # Automatically uses OpenAI
    )
)
```

## File and Image Support

```python
from llmbridge.file_utils import analyze_image

# Analyze an image
image_content = analyze_image(
    "path/to/image.png",
    "What's in this image?"
)

request = LLMRequest(
    messages=[Message(role="user", content=image_content)],
    model="gpt-4o"  # Use a vision-capable model
)

response = await service.chat(request)
```

## API Reference

### Core Classes

- `LLMBridge`: Main service class for routing requests
- `LLMDatabase`: Database interface for model registry and usage tracking
- `LLMRequest`: Request model with messages and parameters
- `LLMResponse`: Response model with content and usage metadata
- `Message`: Individual message in a conversation

### Key Methods

- `service.chat(request)`: Send a chat request to an LLM
- `db.list_models()`: List available models
- `db.get_usage_stats()`: Get usage statistics
- `db.record_api_call()`: Log an API call

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run specific test file
pytest tests/test_sqlite_backend.py
```

## License

MIT

## Contributing

Pull requests welcome! Please ensure all tests pass and add new tests for new features.