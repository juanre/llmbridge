# API Reference

## Core Classes

### LLMBridge
Main service class for routing requests to LLM providers.

```python
service = LLMBridge(
    db_connection_string: Optional[str] = None,  # Database connection
    origin: str = "llmbridge",                   # App identifier for tracking
    enable_db_logging: bool = True               # Enable database logging
)
```

### LLMDatabase
Database interface for model registry and usage tracking. Supports owning its connection or using an injected `AsyncDatabaseManager` with a shared pool and schema isolation.

```python
from pgdbm import AsyncDatabaseManager

# Standalone (owns connection)
db = LLMDatabase(connection_string="postgresql://...")
await db.initialize()  # runs single initial migration in configured schema (or public)

# Shared pool (injected manager with schema)
pool = await AsyncDatabaseManager.create_shared_pool(config)
db_manager = AsyncDatabaseManager(pool=pool, schema="llmbridge")
db = LLMDatabase(db_manager=db_manager)
await db.initialize()

# Methods
await db.list_models(provider: Optional[str] = None, active_only: bool = True)
await db.get_model(provider: str, model_name: str)
await db.record_api_call(...)
await db.get_usage_stats(origin: str, id_at_origin: str, days: int = 30)
await db.list_recent_calls(origin: str, id_at_origin: Optional[str] = None, limit: int = 100, offset: int = 0)
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