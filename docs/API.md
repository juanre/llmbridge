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
Database interface for model registry and usage tracking.

```python
db = LLMDatabase(
    connection_string: Optional[str] = None  # None = SQLite, or PostgreSQL URL
)

# Methods
await db.initialize()
await db.list_models(provider: Optional[str] = None, active_only: bool = True)
await db.get_model(provider: str, model_name: str)
await db.record_api_call(call_record: CallRecord)
await db.get_usage_stats(origin: Optional[str] = None, days: int = 30)
await db.get_recent_calls(limit: int = 100, offset: int = 0)
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