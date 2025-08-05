# LLM Service

A unified Python service for interacting with multiple Large Language Model (LLM) providers including OpenAI, Anthropic, Google, and Ollama. This library provides a consistent interface across providers, automatic usage tracking, cost calculation, and comprehensive database logging capabilities.

## Features

- **Unified Interface**: Single API for multiple LLM providers (OpenAI, Anthropic, Google, Ollama)
- **File & Vision Support**: Built-in support for images, with utilities for PDF processing and file handling
- **Automatic Provider Detection**: Detects providers based on model names or explicit specification
- **Database Tracking**: Optional database logging of all API calls with cost calculation
- **Usage Analytics**: Track usage, costs, and performance metrics per user and application
- **Model Registry**: Built-in database of models with context limits and pricing information
- **Async Support**: Fully async/await compatible for high-performance applications
- **Type Safety**: Full type hints and Pydantic models for request/response validation
- **Extensible**: Easy to add new providers by implementing the base interface

## Installation

### Using uv (recommended)

```bash
uv add llmbridge
```

### Using pip

```bash
pip install llmbridge
```

### From source

```bash
git clone https://github.com/yourusername/llmbridge.git
cd llmbridge
uv pip install -e .
```

## Quick Start

### Basic Usage (No Database)

```python
import asyncio
from llm.service import LLMBridge
from llm.schemas import LLMRequest, Message

async def main():
    # Initialize service (will auto-detect providers from environment variables)
    service = LLMBridge(enable_db_logging=False)

    # Create a request
    request = LLMRequest(
        messages=[Message(role="user", content="What is the capital of France?")],
        model="gpt-4o-mini",  # or "claude-3-haiku-20240307", "gemini-1.5-flash", etc.
        temperature=0.7,
        max_tokens=100
    )

    # Get response
    response = await service.chat(request)
    print(response.content)
    print(f"Model used: {response.model}")
    print(f"Tokens used: {response.usage}")

asyncio.run(main())
```

### With Database Tracking

```python
import asyncio
from llm.service import LLMBridge
from llm.schemas import LLMRequest, Message

async def main():
    # Initialize with database tracking
    service = LLMBridge(
        db_connection_string="postgresql://postgres:postgres@localhost/mydb",
        origin="my-application",  # Your application name
        enable_db_logging=True
    )

    # Make a request with user tracking
    request = LLMRequest(
        messages=[Message(role="user", content="Explain quantum computing")],
        model="claude-3-sonnet-20240229"
    )

    # Pass user identifier for tracking
    response = await service.chat(request, id_at_origin="user@example.com")

    # Get usage statistics
    stats = await service.get_usage_stats("user@example.com", days=30)
    if stats:
        print(f"Total calls: {stats.total_calls}")
        print(f"Total cost: ${stats.total_cost}")
        print(f"Most used model: {stats.most_used_model}")

    # Always close the service to cleanup database connections
    await service.close()

asyncio.run(main())
```

## Model Management

The LLM service maintains a database of available models with their capabilities and pricing. This data is managed through a two-step process:

### 1. Extract Model Information from Provider Documentation

First, download the latest provider documentation PDFs and extract model information:

```bash
# Download the latest pricing PDFs from providers
llm-models extract-from-pdfs download-instructions

# This will show download links like:
# Anthropic: https://docs.anthropic.com/en/docs/about-claude/models
# Google: https://ai.google.dev/gemini-api/docs/models
# OpenAI: https://openai.com/api/pricing/

# Save the PDFs to data/pdfs/ directory with names like:
# - anthropic_models.pdf
# - google_models.pdf
# - openai_models.pdf

# Generate JSON files from the PDFs
llm-models extract-from-pdfs generate

# This creates/updates:
# - data/models/anthropic.json
# - data/models/google.json
# - data/models/openai.json
```

### 2. Update Database from JSON Files

Once you have the JSON files with model information, update the database:

```bash
# Initialize the database (first time only)
python scripts/setup_database.py setup

# Or reset the database completely
python scripts/setup_database.py reset

# Check database status
python scripts/setup_database.py status

# Refresh models from JSON files
llm-models json-refresh

# Preview changes without applying them
llm-models json-refresh --dry-run

# Refresh specific providers only
llm-models json-refresh --providers anthropic openai
```

### Model Information Storage

The system stores model information in JSON files (`data/models/`) with the following structure:
- **Model details**: ID, display name, description, context limits
- **Capabilities**: Vision support, function calling, JSON mode, etc.
- **Pricing**: Cost in dollars per million tokens for input and output
- **Usage hints**: Recommendations for when to use each model

All costs are stored as **dollars per million tokens** throughout the system. The conversion to actual cost only happens when calculating the total cost for a specific number of tokens.

### Viewing Available Models

```bash
# List all models with pricing and capabilities
llm-models list

# Show pricing information
llm-models list --pricing

# Search for specific models
llm-models search gpt-4

# Get detailed information about a model
llm-models info gpt-4o

# Export model data as JSON
llm-models list --format json > models.json
```

## Provider Configuration

### Environment Variables

The service automatically initializes providers based on available API keys:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Google
export GOOGLE_API_KEY=...  # or GEMINI_API_KEY

# Ollama (no API key required, runs locally)
# Requires Ollama to be installed and running
```

### Manual Provider Registration

```python
from llm.service import LLMBridge

service = LLMBridge(enable_db_logging=False)

# Register providers manually
service.register_provider("openai", api_key="sk-...")
service.register_provider("anthropic", api_key="sk-ant-...")
service.register_provider("ollama")  # No API key needed
```

## Database Integration

The service uses PostgreSQL with async-db-utils for high-performance database operations:

### Database Features

- **Connection Pooling**: Configurable min/max connections with automatic recycling
- **Schema Management**: Automatic schema creation and isolation
- **Migration Support**: Version-controlled database migrations
- **Performance Monitoring**: Optional query monitoring with slow query detection
- **Prepared Statements**: Optimized queries for frequent operations
- **Transaction Support**: ACID compliance with automatic rollback on errors

### What Data is Stored

#### 📊 **LLM Models Registry** (`llm_models` table)
- Model information, capabilities, and pricing
- Costs stored as dollars per million tokens
- Active/inactive status tracking with timestamps

#### 📈 **API Call Tracking** (`llm_api_calls` table)
- Complete request metadata and response details
- Token usage and cost calculation
- Performance metrics and error tracking
- Privacy: System prompts are SHA-256 hashed

#### 📅 **Daily Analytics** (`usage_analytics_daily` table)
- Aggregated daily usage statistics
- Cost and performance metrics per user
- Model popularity tracking

### Database Setup

```python
from llm.service import LLMBridge

# Automatic setup (recommended)
service = LLMBridge(
    db_connection_string="postgresql://postgres:postgres@localhost/mydb",
    enable_db_logging=True
)
# Database is initialized automatically on first use

# With custom configuration
service = LLMBridge(
    db_connection_string="postgresql://postgres:postgres@localhost/mydb",
    enable_db_logging=True,
    db_config={
        "min_connections": 10,
        "max_connections": 20,
        "enable_monitoring": True
    }
)
```

## Usage Examples

### System Messages

```python
from llm.schemas import LLMRequest, Message

request = LLMRequest(
    messages=[
        Message(role="system", content="You are a helpful Python tutor."),
        Message(role="user", content="How do I create a dictionary?")
    ],
    model="gpt-4o-mini"
)

response = await service.chat(request)
```

### Vision Support

```python
from llm import analyze_image

# Analyze an image
content = analyze_image("screenshot.png", "What's in this image?")
request = LLMRequest(
    messages=[Message(role="user", content=content)],
    model="gpt-4o"
)
response = await service.chat(request)
```

### Function Calling

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
}]

request = LLMRequest(
    messages=[Message(role="user", content="What's the weather in Paris?")],
    model="gpt-4o",
    tools=tools
)
```

### Cost Tracking

```python
# Every call automatically tracks costs
response = await service.chat(request, id_at_origin="user123")

# Get usage statistics
stats = await service.get_usage_stats("user123", days=30)
print(f"Total cost: ${stats.total_cost}")
print(f"Average per call: ${stats.avg_cost_per_call}")
```

## Testing

```bash
# Run all tests
pytest

# Run with specific test database
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/test_db pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest -k "test_database"
```

## Architecture

The service follows a clean architecture with:

- **Providers**: Implement the `BaseLLMProvider` interface
- **Database**: Uses async-db-utils for connection management
- **Schemas**: Pydantic models for type safety
- **Service**: Orchestrates providers and database operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Adding a New Provider

1. Create a new file in `src/llm/providers/`
2. Implement the `BaseLLMProvider` interface
3. Add provider initialization in `LLMBridge`
4. Add tests in `tests/unit/test_providers/`
5. Update documentation

## License

MIT License - see LICENSE file for details.
