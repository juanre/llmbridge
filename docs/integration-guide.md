# LLM Service Integration Guide

This guide explains how to integrate llmbridge into your application, with special focus on database connection management to avoid connection pool exhaustion.

## Table of Contents

1. [Installation](#installation)
2. [Basic Usage](#basic-usage)
3. [Database Integration](#database-integration)
4. [Shared Connection Pattern](#shared-connection-pattern)
5. [Testing](#testing)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Installation

### As a Package

```bash
# From your application directory
uv add /path/to/llmbridge

# Or if using pip
pip install -e /path/to/llmbridge
```

### Requirements

- Python 3.11+
- PostgreSQL 12+
- async-db-utils
- Environment variables for LLM provider API keys

## Basic Usage

### Standalone Mode

In standalone mode, llmbridge creates and manages its own database connection pool:

```python
from llm.service import LLMBridge

# Create service with its own connection pool
service = LLMBridge(
    db_connection_string="postgresql://user:pass@localhost/db",
    origin="my-app",
    enable_db_logging=True
)

# Initialize database (required)
await service.db.initialize()
await service.db.apply_migrations()

# Use the service
response = await service.chat(request, id_at_origin="user-123")

# Cleanup when done
await service.close()
```

### Without Database

For simpler use cases without database logging:

```python
service = LLMBridge(enable_db_logging=False)

# No database initialization needed
response = await service.chat(request)
```

## Database Integration

### Database Features

When database logging is enabled, llmbridge provides:

1. **Model Registry** - Stores LLM model information, capabilities, and pricing
2. **API Call Tracking** - Records all LLM API calls with token usage and costs
3. **Usage Analytics** - Provides usage statistics and cost analysis
4. **Model Discovery** - Query available models by provider and capabilities

### Schema Organization

LLM service uses its own database schema (`llmbridge` by default) to keep tables isolated:

```sql
-- All tables are created in the llmbridge schema
llmbridge.llm_models        -- Model registry
llmbridge.llm_api_calls     -- API call logs
llmbridge.usage_analytics   -- Aggregated analytics
```

### Database API Examples

```python
# Get all available models
models = await service.get_models_from_db()

# Get models from specific provider
openai_models = await service.get_models_from_db(provider="openai")

# Get specific model information
model = await service.get_model_from_db("anthropic", "claude-3-5-sonnet-20241022")

# Get usage statistics
stats = await service.get_usage_stats("user-123", days=30)

# Get usage hints for use cases
hints = await service.get_usage_hints("largest_context")
```

## Shared Connection Pattern

The shared connection pattern solves connection pool exhaustion when integrating llmbridge into larger applications like task-engine.

### The Problem

When multiple services each create their own connection pools, you can quickly exhaust PostgreSQL's connection limit:

```python
# BAD: Each service creates its own pool
task_engine_db = TaskEngineDb(max_connections=20)      # 20 connections
llmbridge = LLMBridge(max_connections=10)           # +10 connections
auth_service = AuthService(max_connections=10)         # +10 connections
# Total: 40 connections!
```

### The Solution

Share a single AsyncDatabaseManager instance across all services:

```python
from pgdbm_utils import AsyncDatabaseManager, DatabaseConfig
from llm.service import LLMBridge

# 1. Create a shared database manager
config = DatabaseConfig(
    connection_string="postgresql://user:pass@localhost/db",
    min_connections=10,
    max_connections=30  # Single pool for all services
)
shared_db_manager = AsyncDatabaseManager(config)
await shared_db_manager.connect()

# 2. Create LLM service with shared manager
llmbridge = LLMBridge(
    db_manager=shared_db_manager,  # Pass the shared manager
    origin="task-engine",
    enable_db_logging=True
)

# 3. Initialize the service (creates schema, runs migrations)
await llmbridge.db.initialize()

# 4. Use normally
response = await llmbridge.chat(request, id_at_origin="user-123")

# 5. Cleanup - only disconnect the shared manager once
await shared_db_manager.disconnect()
```

### Integration with Task-Engine

Here's a complete example of integrating llmbridge into task-engine:

```python
# task-engine/src/providers/service_factory.py

from core.db import TaskEngineDb
from llm.service import LLMBridge

class ServiceFactory:
    """Factory for creating services with shared database connections."""

    def __init__(self, task_engine_db: TaskEngineDb):
        self.task_engine_db = task_engine_db
        self._services = {}

    async def get_llmbridge(self) -> LLMBridge:
        """Get LLM service with shared connection."""
        if 'llm' not in self._services:
            # Get the underlying AsyncDatabaseManager from task-engine
            db_manager = self.task_engine_db.db

            # Create LLM service with shared manager
            self._services['llm'] = LLMBridge(
                db_manager=db_manager,
                origin="task-engine",
                enable_db_logging=True
            )

            # Initialize the service's database
            await self._services['llm'].db.initialize()

        return self._services['llm']

# Usage in task-engine
async def main():
    # Create task-engine database with larger pool
    task_db = TaskEngineDb(
        connection_string=settings.database_url,
        min_connections=10,
        max_connections=30  # Sized for all services
    )
    await task_db.initialize()

    # Create service factory
    factory = ServiceFactory(task_db)

    # Get services as needed
    llmbridge = await factory.get_llmbridge()

    # Use services...

    # Cleanup
    await task_db.close()  # This closes the shared pool
```

### Using from_manager Method

For cleaner code, use the `from_manager` class method:

```python
from llm.db import LLMDatabase

# Method 1: Direct usage
service = LLMBridge(
    db_manager=shared_db_manager,
    origin="my-app"
)

# Method 2: Using from_manager for custom schema
llm_db = LLMDatabase.from_manager(
    shared_db_manager,
    schema="custom_schema"  # Use different schema name
)
# Then you would need to manually initialize and use this database
```

## Testing

### Unit Tests

For unit tests, create isolated test databases:

```python
import pytest
from llm.service import LLMBridge

@pytest.fixture
async def llmbridge():
    """Create test LLM service."""
    service = LLMBridge(
        db_connection_string="postgresql://localhost/test_db",
        origin="test",
        enable_db_logging=True
    )

    await service.db.initialize()
    await service.db.apply_migrations()

    yield service

    # Cleanup
    await service.close()

async def test_chat(llmbridge):
    """Test chat functionality."""
    response = await llmbridge.chat(
        request,
        id_at_origin="test-user"
    )
    assert response.content is not None
```

### Testing Shared Connections

Test that your integration properly shares connections:

```python
import pytest
from pgdbm_utils import AsyncDatabaseManager, DatabaseConfig

async def test_shared_connection():
    """Test shared connection pattern."""
    # Create shared manager
    config = DatabaseConfig(
        connection_string="postgresql://localhost/test",
        max_connections=5  # Small pool to test sharing
    )
    shared_manager = AsyncDatabaseManager(config)
    await shared_manager.connect()

    try:
        # Create multiple services
        service1 = LLMBridge(db_manager=shared_manager, origin="test1")
        service2 = LLMBridge(db_manager=shared_manager, origin="test2")

        # Initialize both
        await service1.db.initialize()
        await service2.db.initialize()

        # Verify they share the same manager
        assert service1.db.db is shared_manager
        assert service2.db.db is shared_manager

        # Get pool stats
        stats = await shared_manager.get_pool_stats()
        assert stats['size'] <= 5  # Within our limit

    finally:
        await shared_manager.disconnect()
```

### Integration Tests

Test the complete integration:

```python
async def test_task_engine_integration():
    """Test LLM service integration with task-engine."""
    # Create task-engine database
    task_db = TaskEngineDb(connection_string=test_db_url)
    await task_db.initialize()

    # Create factory
    factory = ServiceFactory(task_db)

    # Get LLM service
    llmbridge = await factory.get_llmbridge()

    # Verify it works
    models = await llmbridge.get_models_from_db()
    assert isinstance(models, list)

    # Verify shared connection
    pool_stats = await task_db.db.get_pool_stats()
    assert pool_stats['size'] <= task_db.config.max_connections

    # Cleanup
    await factory.close_all()
    await task_db.close()
```

## Best Practices

### 1. Connection Management

- **Always use shared connections** in production when integrating multiple services
- **Size your pool appropriately** - plan for peak concurrent usage across all services
- **Monitor pool usage** - use `get_pool_stats()` to track connection usage

### 2. Schema Isolation

- Each service should use its own schema for clean separation
- Never directly access another service's tables
- Use the service's API methods instead

### 3. Error Handling

```python
try:
    response = await service.chat(request, id_at_origin=user_id)
except Exception as e:
    logger.error(f"LLM service error: {e}")
    # Handle gracefully - database logging failures shouldn't break the app
```

### 4. Lifecycle Management

- Initialize services at application startup
- Keep service instances for the application lifetime
- Only close/disconnect at application shutdown

### 5. Configuration

```python
# Use environment variables for configuration
LLMBRIDGE_SCHEMA = os.getenv("LLMBRIDGE_SCHEMA", "llmbridge")
LLMBRIDGE_MIN_CONNECTIONS = int(os.getenv("LLMBRIDGE_MIN_CONNECTIONS", "2"))
LLMBRIDGE_MAX_CONNECTIONS = int(os.getenv("LLMBRIDGE_MAX_CONNECTIONS", "5"))
```

## Troubleshooting

### Connection Pool Exhaustion

**Symptoms:**
- "too many connections" errors
- Slow database operations
- Application hangs

**Solution:**
1. Check if you're using shared connections properly
2. Review pool statistics: `await db.get_pool_stats()`
3. Increase max_connections if needed
4. Check for connection leaks

### Schema Not Found

**Error:** `schema "llmbridge" does not exist`

**Solution:**
```python
# Ensure initialize is called
await service.db.initialize()  # This creates the schema
```

### Migration Failures

**Error:** Migration errors on startup

**Solution:**
1. Check migration files exist in `llm/migrations/`
2. Verify database user has CREATE SCHEMA permission
3. Check for conflicting schema modifications

### Slow Queries

**Symptom:** LLM service database operations are slow

**Solution:**
```python
# Enable monitoring
service = LLMBridge(
    db_manager=shared_manager,
    enable_monitoring=True  # Enables slow query logging
)

# Check slow queries
slow_queries = await service.db.get_slow_queries()
```

### Testing Connection Verification

To verify your integration is working correctly:

```python
# Check connection sharing
print(f"Service using external DB: {service.db._external_db}")
print(f"Pool stats: {await service.db.db.get_pool_stats()}")

# Verify schema
result = await service.db.db.fetch_value(
    "SELECT current_schema()"
)
print(f"Current schema: {result}")
```

## Example: Complete Integration

Here's a complete example showing best practices:

```python
# app.py
import asyncio
import logging
from contextlib import asynccontextmanager
from pgdbm_utils import AsyncDatabaseManager, DatabaseConfig
from llm.service import LLMBridge

logger = logging.getLogger(__name__)

class Application:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.shared_db = None
        self.llmbridge = None

    async def startup(self):
        """Initialize all services with shared connection."""
        # Create shared database manager
        config = DatabaseConfig(
            connection_string=self.db_url,
            min_connections=10,
            max_connections=30,
            schema="public"  # Main app schema
        )
        self.shared_db = AsyncDatabaseManager(config)
        await self.shared_db.connect()
        logger.info("Database connected")

        # Create LLM service
        self.llmbridge = LLMBridge(
            db_manager=self.shared_db,
            origin="my-app",
            enable_db_logging=True
        )
        await self.llmbridge.db.initialize()
        logger.info("LLM service initialized")

    async def shutdown(self):
        """Clean shutdown of all services."""
        if self.shared_db:
            await self.shared_db.disconnect()
            logger.info("Database disconnected")

    async def process_request(self, user_prompt: str, user_id: str):
        """Process a user request with LLM."""
        from llm.schemas import LLMRequest, Message

        request = LLMRequest(
            messages=[
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content=user_prompt)
            ],
            model="gpt-4",
            temperature=0.7
        )

        try:
            response = await self.llmbridge.chat(request, id_at_origin=user_id)
            return response.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise

# Usage
async def main():
    app = Application("postgresql://localhost/myapp")

    try:
        await app.startup()

        # Process requests
        result = await app.process_request(
            "What is the capital of France?",
            "user-123"
        )
        print(f"Response: {result}")

        # Check usage
        stats = await app.llmbridge.get_usage_stats("user-123")
        print(f"Usage: {stats}")

    finally:
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

This integration guide provides a complete overview of how to properly integrate llmbridge into your application, with special attention to the shared connection pattern that prevents connection pool exhaustion.
