# API Reference

## Core Classes

### LLMBridge
Main service class for routing requests to LLM providers.

```python
service = LLMBridge(
    db_connection_string: Optional[str] = None,  # Database connection
    db_manager: Optional[AsyncDatabaseManager] = None,  # External DB manager (pgdbm)
    origin: str = "llmbridge",                   # App identifier for tracking
    enable_db_logging: bool = True               # Enable database logging
)
```

### LLMBridgeSQLite
Convenience class for SQLite-based usage (local development).

```python
from llmbridge.service_sqlite import LLMBridgeSQLite

service = LLMBridgeSQLite(
    db_path: str = "llmbridge.db",  # SQLite database file
    origin: str = "llmbridge"       # App identifier for tracking
)
```

### LLMDatabase
Database interface for model registry and usage tracking. Supports owning its connection or using an injected `AsyncDatabaseManager` with a shared pool and schema isolation.

```python
from pgdbm import AsyncDatabaseManager

# Standalone (owns connection)
db = LLMDatabase(connection_string="postgresql://...")
await db.initialize()  # runs single initial migration in configured schema (or public)

# Shared manager (injected) with schema (pool creation omitted)
db_manager = AsyncDatabaseManager(..., schema="llmbridge")
db = LLMDatabase(db_manager=db_manager)  # llmbridge won't own the pool
await db.initialize()

# Methods
await db.list_models(provider: Optional[str] = None, active_only: bool = True)
await db.get_model(provider: str, model_name: str)
await db.record_api_call(...)
await db.get_usage_stats(origin: str, id_at_origin: str, days: int = 30)
await db.list_recent_calls(origin: str, id_at_origin: Optional[str] = None, limit: int = 100, offset: int = 0)
await db.close()
```

### SQLiteDatabase
SQLite database for local development and testing.

```python
from llmbridge.db_sqlite import SQLiteDatabase

db = SQLiteDatabase(db_path="llmbridge.db")
await db.initialize()  # Creates tables automatically

# Methods (similar to LLMDatabase)
await db.list_models(provider: Optional[str] = None, active_only: bool = True)
await db.get_model(provider: str, model_name: str)
await db.record_api_call(...)
await db.get_usage_stats(origin: str, id_at_origin: str, days: int = 30)
await db.get_recent_calls(origin: str, id_at_origin: Optional[str] = None, limit: int = 100)
await db.close()
```

### Request/Response Models

```python
# Request
request = LLMRequest(
    messages: List[Message],
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    response_format: Optional[Dict] = None,
    cache: Optional[Dict[str, Any]] = None,  # {"enabled": True, "ttl_seconds": 600}
    metadata: Optional[Dict[str, Any]] = None,
    json_response: Optional[bool] = None,
)

# Message
message = Message(
    role: str,  # "user", "assistant", "system"
    content: Union[str, List[Dict]]  # Text or multimodal content
)

# Response
response = LLMResponse(
    content: str,
    model: str,
    usage: Dict[str, int],  # Token counts
    finish_reason: str,
    tool_calls: Optional[List[Dict]] = None,
)
```

## File Utilities

```python
from llmbridge.file_utils import analyze_image, analyze_file

# Image analysis
content = analyze_image(
    file_path: str,
    prompt: str
)

# File analysis (PDFs, etc.)
content = analyze_file(
    file_path: str,
    prompt: str
)
```

## Model Information

```python
model = LLMModel(
    provider: str,
    model_name: str,
    display_name: Optional[str],
    max_context: Optional[int],
    max_output_tokens: Optional[int],
    supports_vision: bool,
    supports_function_calling: bool,
    supports_json_mode: bool,
    supports_parallel_tool_calls: bool,
    dollars_per_million_tokens_input: Optional[Decimal],
    dollars_per_million_tokens_output: Optional[Decimal],
)
```

## Usage Statistics

```python
stats = UsageStats(
    total_calls: int,
    total_tokens: int,
    total_cost: Decimal,
    avg_cost_per_call: Decimal,
    success_rate: Decimal,
)
```

## Caching

Response caching is available for deterministic requests (temperature ≤ 0.1).

```python
# Enable caching for a request
request = LLMRequest(
    messages=[Message(role="user", content="Hello")],
    model="gpt-4o-mini",
    temperature=0,  # Must be ≤ 0.1 for caching
    cache={"enabled": True, "ttl_seconds": 300}  # Cache for 5 minutes
)

# Cache backends:
# - SQLite/PostgreSQL: If DB logging is enabled, uses database cache
# - In-memory: If no DB, uses in-memory cache (not persistent)
```

## CLI

The `llmbridge` CLI can initialize databases and manage the model registry.

```bash
# PostgreSQL: initialize schema and seed default models
export DATABASE_URL=postgresql://user:pass@localhost/dbname
llmbridge init-db

# SQLite: initialize schema and seed default models
llmbridge --sqlite ./llmbridge.db init-db

# Load curated JSONs into the database
llmbridge json-refresh
llmbridge --sqlite ./llmbridge.db json-refresh
```

Notes:
- Postgres migrations require `pgcrypto` for UUIDs. The migration enables it if missing and uses `gen_random_uuid()`.
- OpenAI `o1*` models are routed via the Responses API and do not support tools or custom response formats.