# SQLite Support Proposal for LLMBridge

## Executive Summary

This document proposes adding SQLite as an optional, lightweight database backend for llmbridge while keeping PostgreSQL (via pgdbm) as the production-grade option. The implementation requires minimal code changes (~200 lines) with zero duplication of business logic.

## Current State Analysis

### Database Operations in LLMBridge

After analyzing the codebase, llmbridge uses the database for three primary purposes:

1. **Model Registry** - Store LLM model metadata (pricing, capabilities, context limits)
2. **API Call Logging** - Track all LLM API calls for cost and usage analysis
3. **Usage Analytics** - Aggregate statistics for reporting and monitoring

### Actual Database Methods Used

```python
# Core operations (covers 95% of usage)
- fetch_one()    # Get single model
- fetch_all()    # List models
- execute()      # Insert API calls
- fetch_value()  # Get single aggregate value

# SQL operations used
- Simple SELECT with WHERE
- INSERT statements
- Basic aggregations (SUM, COUNT, AVG)
- ORDER BY and LIMIT
```

### PostgreSQL-Specific Features Currently Used

1. **Schemas** - `{{tables.llm_models}}` expands to `llmbridge.llm_models`
2. **UUID type** - For record IDs
3. **JSONB** - For storing tools and metadata
4. **gen_random_uuid()** - For generating IDs
5. **RETURNING clause** - Get ID after INSERT
6. **NUMERIC/DECIMAL** - For precise cost calculations
7. **Connection pooling** - Via pgdbm/asyncpg

## Proposed Architecture

### Design Principles

1. **Minimal Abstraction** - Only abstract what differs between databases
2. **No Business Logic Duplication** - Keep all logic in one place
3. **Backward Compatible** - Existing code continues to work unchanged
4. **Auto-Detection** - Automatically choose backend based on connection string
5. **Graceful Degradation** - Work without database if not configured

### Implementation Structure

```
llmbridge/
├── db.py                    # Main database class (minimal changes)
├── db_backends.py           # NEW: Thin backend abstraction (~150 lines)
├── migrations/
│   ├── postgresql/          # Existing PostgreSQL migrations
│   │   ├── 001_llm_schema.sql
│   │   └── 002_usage_hints.sql
│   └── sqlite/              # NEW: Simplified SQLite migrations
│       └── 001_init.sql    # Single file, simplified schema
```

## Detailed Implementation Plan

### 1. Backend Abstraction Layer (New File: `db_backends.py`)

```python
# src/llmbridge/db_backends.py
"""
Minimal database backend abstraction for SQLite and PostgreSQL support.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseBackend(ABC):
    """Minimal abstraction for database operations."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Initialize database connection."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    @abstractmethod
    async def execute(self, query: str, *args) -> None:
        """Execute a query without returning results."""
        pass
    
    @abstractmethod
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row as a dictionary."""
        pass
    
    @abstractmethod
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        pass
    
    @abstractmethod
    async def fetch_value(self, query: str, *args) -> Any:
        """Fetch a single value."""
        pass
    
    @abstractmethod
    async def execute_and_return_id(self, query: str, *args) -> int:
        """Execute INSERT and return generated ID."""
        pass
    
    def translate_sql(self, query: str) -> str:
        """Translate SQL for the specific backend. Override as needed."""
        return query
    
    @abstractmethod
    async def apply_migrations(self, migrations_path: Path) -> Dict[str, Any]:
        """Apply database migrations."""
        pass


class SQLiteBackend(DatabaseBackend):
    """SQLite implementation of database backend."""
    
    def __init__(self, db_path: str = "~/.llmbridge/llmbridge.db"):
        """
        Initialize SQLite backend.
        
        Args:
            db_path: Path to SQLite database file. 
                    Use ":memory:" for in-memory database.
        """
        self.db_path = db_path if db_path == ":memory:" else Path(db_path).expanduser()
        self.conn = None
        self._is_memory = db_path == ":memory:"
        
        # Create directory if needed
        if not self._is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def connect(self) -> None:
        """Initialize SQLite connection with optimal settings."""
        import aiosqlite
        
        db_path = ":memory:" if self._is_memory else str(self.db_path)
        self.conn = await aiosqlite.connect(db_path)
        
        # Enable row factory for dict-like access
        self.conn.row_factory = aiosqlite.Row
        
        # Optimize SQLite for better performance
        await self.conn.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging
        await self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        await self.conn.execute("PRAGMA foreign_keys=ON")  # Enforce FK constraints
        
        logger.info(f"SQLite database connected: {db_path}")
    
    async def disconnect(self) -> None:
        """Close SQLite connection."""
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("SQLite database disconnected")
    
    async def execute(self, query: str, *args) -> None:
        """Execute a query without returning results."""
        query = self.translate_sql(query)
        await self.conn.execute(query, args)
        await self.conn.commit()
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row as dictionary."""
        query = self.translate_sql(query)
        async with self.conn.execute(query, args) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        query = self.translate_sql(query)
        async with self.conn.execute(query, args) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def fetch_value(self, query: str, *args) -> Any:
        """Fetch a single value."""
        query = self.translate_sql(query)
        async with self.conn.execute(query, args) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def execute_and_return_id(self, query: str, *args) -> int:
        """Execute INSERT and return last inserted row ID."""
        query = self.translate_sql(query)
        # Remove RETURNING clause as SQLite handles this differently
        query = query.replace("RETURNING id", "")
        
        cursor = await self.conn.execute(query, args)
        await self.conn.commit()
        return cursor.lastrowid
    
    def translate_sql(self, query: str) -> str:
        """
        Translate PostgreSQL SQL to SQLite SQL.
        
        Handles:
        - Schema prefixes ({{tables.x}} -> x)
        - Data types (UUID -> TEXT, JSONB -> TEXT, etc.)
        - Functions (gen_random_uuid() -> hex(randomblob(16)))
        - Parameter placeholders ($1 -> ?)
        """
        # Remove schema prefixes
        query = query.replace("{{tables.", "")
        query = query.replace("}}", "")
        query = query.replace("{{schema}}.", "")
        
        # Data type translations
        query = query.replace("UUID", "TEXT")
        query = query.replace("JSONB", "TEXT")
        query = query.replace("NUMERIC(12,6)", "REAL")
        query = query.replace("DECIMAL(12,8)", "REAL")
        query = query.replace("TIMESTAMP WITH TIME ZONE", "TEXT")
        query = query.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        query = query.replace("BIGSERIAL", "INTEGER")
        query = query.replace("BIGINT", "INTEGER")
        
        # Function translations
        query = query.replace("gen_random_uuid()", "lower(hex(randomblob(16)))")
        query = query.replace("CURRENT_TIMESTAMP", "datetime('now')")
        query = query.replace("NOW()", "datetime('now')")
        
        # Parameter placeholder translation ($1, $2 -> ?, ?)
        import re
        def replace_param(match):
            return "?"
        query = re.sub(r'\$\d+', replace_param, query)
        
        return query
    
    async def apply_migrations(self, migrations_path: Path) -> Dict[str, Any]:
        """
        Apply SQLite migrations.
        
        Returns:
            Dict with keys: applied, skipped, total
        """
        # Create migrations tracking table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                applied_at TEXT DEFAULT (datetime('now')),
                checksum TEXT
            )
        """)
        
        # Find SQLite migration files
        sqlite_migrations = migrations_path / "sqlite"
        if not sqlite_migrations.exists():
            logger.warning(f"No SQLite migrations found at {sqlite_migrations}")
            return {"applied": [], "skipped": [], "total": 0}
        
        migration_files = sorted(sqlite_migrations.glob("*.sql"))
        applied = []
        skipped = []
        
        for migration_file in migration_files:
            filename = migration_file.name
            
            # Check if already applied
            existing = await self.fetch_value(
                "SELECT id FROM migration_history WHERE filename = ?",
                filename
            )
            
            if existing:
                skipped.append(filename)
                continue
            
            # Read and apply migration
            with open(migration_file) as f:
                sql = f.read()
            
            # Execute each statement (split by semicolon)
            for statement in sql.split(';'):
                if statement.strip():
                    await self.execute(statement)
            
            # Record migration
            await self.execute(
                "INSERT INTO migration_history (filename) VALUES (?)",
                filename
            )
            
            applied.append(filename)
            logger.info(f"Applied migration: {filename}")
        
        return {
            "applied": applied,
            "skipped": skipped,
            "total": len(migration_files)
        }


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL implementation using pgdbm."""
    
    def __init__(self, 
                 connection_string: str,
                 schema: str = "llmbridge",
                 enable_monitoring: bool = False,
                 **kwargs):
        """
        Initialize PostgreSQL backend.
        
        Args:
            connection_string: PostgreSQL connection string
            schema: Database schema name
            enable_monitoring: Enable query monitoring
            **kwargs: Additional pgdbm configuration
        """
        self.connection_string = connection_string
        self.schema = schema
        self.enable_monitoring = enable_monitoring
        self.kwargs = kwargs
        self.db = None
        self._migration_manager = None
    
    async def connect(self) -> None:
        """Initialize PostgreSQL connection via pgdbm."""
        from pgdbm import AsyncDatabaseManager, DatabaseConfig
        from pgdbm.monitoring import MonitoredAsyncDatabaseManager
        
        config = DatabaseConfig(
            connection_string=self.connection_string,
            schema=self.schema,
            **self.kwargs
        )
        
        if self.enable_monitoring:
            self.db = MonitoredAsyncDatabaseManager(config)
        else:
            self.db = AsyncDatabaseManager(config)
        
        await self.db.connect()
        logger.info(f"PostgreSQL database connected with schema: {self.schema}")
    
    async def disconnect(self) -> None:
        """Close PostgreSQL connection pool."""
        if self.db:
            await self.db.disconnect()
            self.db = None
            logger.info("PostgreSQL database disconnected")
    
    async def execute(self, query: str, *args) -> None:
        """Execute using pgdbm."""
        query = self.translate_sql(query)
        await self.db.execute(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch one using pgdbm."""
        query = self.translate_sql(query)
        return await self.db.fetch_one(query, *args)
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all using pgdbm."""
        query = self.translate_sql(query)
        return await self.db.fetch_all(query, *args)
    
    async def fetch_value(self, query: str, *args) -> Any:
        """Fetch value using pgdbm."""
        query = self.translate_sql(query)
        return await self.db.fetch_value(query, *args)
    
    async def execute_and_return_id(self, query: str, *args) -> int:
        """Execute and return ID using pgdbm."""
        query = self.translate_sql(query)
        return await self.db.execute_and_return_id(query, *args)
    
    def translate_sql(self, query: str) -> str:
        """Prepare query using pgdbm's template system."""
        if self.db:
            return self.db._prepare_query(query)
        return query
    
    async def apply_migrations(self, migrations_path: Path) -> Dict[str, Any]:
        """Apply PostgreSQL migrations using pgdbm."""
        from pgdbm import AsyncMigrationManager
        
        if not self._migration_manager:
            pg_migrations = migrations_path / "postgresql"
            self._migration_manager = AsyncMigrationManager(
                self.db,
                migrations_path=str(pg_migrations),
                module_name="llmbridge"
            )
        
        return await self._migration_manager.apply_pending_migrations()


def create_backend(db_url: Optional[str] = None, **kwargs) -> Optional[DatabaseBackend]:
    """
    Factory function to create appropriate database backend.
    
    Args:
        db_url: Database URL or path
        **kwargs: Additional backend-specific configuration
    
    Returns:
        DatabaseBackend instance or None if no database configured
    
    Examples:
        # PostgreSQL
        backend = create_backend("postgresql://user:pass@localhost/db")
        
        # SQLite file
        backend = create_backend("sqlite:///path/to/db.sqlite")
        backend = create_backend("/path/to/db.sqlite")
        
        # SQLite in-memory
        backend = create_backend(":memory:")
        
        # No database
        backend = create_backend(None)  # Returns None
    """
    if not db_url:
        return None
    
    # PostgreSQL
    if "postgresql://" in db_url or "postgres://" in db_url:
        try:
            return PostgreSQLBackend(db_url, **kwargs)
        except ImportError:
            raise ImportError(
                "PostgreSQL support requires pgdbm. "
                "Install with: pip install llmbridge[postgres]"
            )
    
    # SQLite (including memory)
    elif "sqlite://" in db_url:
        # Remove sqlite:// prefix
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        return SQLiteBackend(db_path)
    
    # File path or :memory:
    elif db_url == ":memory:" or Path(db_url).suffix in (".db", ".sqlite", ".sqlite3"):
        return SQLiteBackend(db_url)
    
    # Default to SQLite for unknown
    else:
        logger.warning(f"Unknown database URL format: {db_url}, defaulting to SQLite")
        return SQLiteBackend(db_url)
```

### 2. Modified LLMDatabase Class (`db.py`)

```python
# src/llmbridge/db.py - Key changes only

from .db_backends import create_backend, DatabaseBackend

class LLMDatabase:
    """Async database manager for LLM service."""
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        backend: Optional[DatabaseBackend] = None,  # Allow injecting backend
        schema: str = "llmbridge",
        enable_monitoring: bool = False,
        **kwargs
    ):
        """
        Initialize database manager.
        
        Args:
            connection_string: Database connection string
            backend: Pre-configured backend (for testing)
            schema: Schema name (PostgreSQL only)
            enable_monitoring: Enable monitoring (PostgreSQL only)
        """
        self.schema = schema
        self._initialized = False
        
        # Use provided backend or create from connection string
        if backend:
            self.backend = backend
        else:
            self.backend = create_backend(
                connection_string,
                schema=schema,
                enable_monitoring=enable_monitoring,
                **kwargs
            )
        
        # If no backend, database operations will be disabled
        self.enabled = self.backend is not None
        
        # Migration path depends on backend type
        base_migrations = Path(__file__).parent / "migrations"
        if self.backend and hasattr(self.backend, '__class__'):
            backend_type = self.backend.__class__.__name__
            if 'SQLite' in backend_type:
                self.migrations_path = base_migrations / "sqlite"
            else:
                self.migrations_path = base_migrations / "postgresql"
        else:
            self.migrations_path = base_migrations
    
    async def initialize(self):
        """Initialize database connection and apply migrations."""
        if not self.enabled:
            logger.warning("Database disabled - no connection string provided")
            return
            
        if self._initialized:
            return
        
        # Connect to database
        await self.backend.connect()
        
        # Apply migrations
        result = await self.backend.apply_migrations(self.migrations_path.parent)
        logger.info(f"Applied {len(result.get('applied', []))} migrations")
        
        self._initialized = True
    
    async def close(self):
        """Close database connection."""
        if self._initialized and self.backend:
            await self.backend.disconnect()
            self._initialized = False
    
    # ALL EXISTING METHODS REMAIN THE SAME!
    # Just replace self.db with self.backend
    
    async def get_model(self, provider: str, model_name: str) -> Optional[LLMModel]:
        """Get model - UNCHANGED except self.db -> self.backend"""
        if not self.enabled:
            return None
            
        query = """
            SELECT * FROM {{tables.llm_models}}
            WHERE provider = $1 AND model_name = $2
        """
        result = await self.backend.fetch_one(query, provider, model_name)
        return LLMModel(**result) if result else None
    
    async def record_api_call(self, **kwargs) -> Optional[int]:
        """Record API call - UNCHANGED except self.db -> self.backend"""
        if not self.enabled:
            return None
            
        query = """
            INSERT INTO {{tables.llm_api_calls}} (
                origin, id_at_origin, provider, model_name,
                prompt_tokens, completion_tokens, total_tokens,
                response_time_ms, estimated_cost, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """
        return await self.backend.execute_and_return_id(query, *values)
    
    # ... all other methods stay the same, just use self.backend
```

### 3. SQLite Migration File

```sql
-- migrations/sqlite/001_init.sql
-- Simplified schema for SQLite

-- Model registry table
CREATE TABLE IF NOT EXISTS llm_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    display_name TEXT,
    description TEXT,
    
    -- Capabilities
    max_context INTEGER,
    max_output_tokens INTEGER,
    supports_vision INTEGER DEFAULT 0,  -- Boolean as 0/1
    supports_function_calling INTEGER DEFAULT 0,
    supports_json_mode INTEGER DEFAULT 0,
    supports_parallel_tool_calls INTEGER DEFAULT 0,
    tool_call_format TEXT,
    
    -- Pricing (stored as REAL for simplicity)
    dollars_per_million_tokens_input REAL,
    dollars_per_million_tokens_output REAL,
    
    -- Metadata
    inactive_from TEXT,  -- ISO timestamp
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    
    -- Constraints
    UNIQUE(provider, model_name)
);

-- API call logging table
CREATE TABLE IF NOT EXISTS llm_api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Request identification
    origin TEXT NOT NULL,
    id_at_origin TEXT,
    
    -- Model information
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    
    -- Token usage
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    
    -- Performance metrics
    response_time_ms INTEGER,
    estimated_cost REAL,
    
    -- Request parameters (stored as JSON strings)
    temperature REAL,
    max_tokens INTEGER,
    tools_used TEXT,  -- JSON array
    system_prompt_hash TEXT,  -- SHA256 hash
    
    -- Response status
    status TEXT DEFAULT 'success',
    error_type TEXT,
    error_message TEXT,
    
    -- Timestamp
    called_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_api_calls_origin ON llm_api_calls(origin, id_at_origin);
CREATE INDEX IF NOT EXISTS idx_api_calls_provider ON llm_api_calls(provider, model_name);
CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON llm_api_calls(called_at);

-- Simple usage analytics view
CREATE VIEW IF NOT EXISTS usage_summary AS
SELECT 
    origin,
    id_at_origin,
    provider,
    model_name,
    COUNT(*) as call_count,
    SUM(total_tokens) as total_tokens,
    SUM(estimated_cost) as total_cost,
    AVG(response_time_ms) as avg_response_time,
    DATE(called_at) as date
FROM llm_api_calls
WHERE status = 'success'
GROUP BY origin, id_at_origin, provider, model_name, DATE(called_at);
```

### 4. Service Layer Changes (`service.py`)

```python
# src/llmbridge/service.py - Minimal changes

class LLMBridge:
    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        db_manager: Optional[AsyncDatabaseManager] = None,  # For backward compat
        origin: str = "llmbridge",
        enable_db_logging: bool = True,
    ):
        """Initialize LLM service with optional database."""
        
        self.origin = origin
        self.enable_db_logging = enable_db_logging and (db_connection_string or db_manager)
        
        if self.enable_db_logging:
            if db_manager:
                # Backward compatibility: wrap pgdbm manager
                from .db_backends import PostgreSQLBackend
                backend = PostgreSQLBackend(db_manager.config.get_dsn())
                backend.db = db_manager  # Use existing manager
                self.db = LLMDatabase(backend=backend)
            elif db_connection_string:
                # Auto-detect backend from connection string
                self.db = LLMDatabase(connection_string=db_connection_string)
            else:
                self.db = None
                self.enable_db_logging = False
        else:
            self.db = None
        
        # ... rest of initialization unchanged
```

### 5. Package Configuration (`pyproject.toml`)

```toml
[project]
name = "llmbridge"
version = "0.2.0"
dependencies = [
    # Core dependencies (no database)
    "httpx>=0.24.0",
    "openai>=1.0.0",
    "anthropic>=0.18.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    
    # SQLite support included by default
    "aiosqlite>=0.19.0",
]

[project.optional-dependencies]
# PostgreSQL support
postgres = [
    "pgdbm>=0.1.0",
    "asyncpg>=0.28.0",
]

# All database backends
all = [
    "pgdbm>=0.1.0",
    "asyncpg>=0.28.0",
    "aiosqlite>=0.19.0",
]

# Development
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

## Usage Examples

### 1. Local Development (SQLite)

```python
from llmbridge import LLMBridge

# File-based SQLite (default for local development)
service = LLMBridge(
    db_connection_string="~/llmbridge.db",  # or "sqlite:///path/to/db.sqlite"
    enable_db_logging=True
)

# In-memory database (great for testing)
service = LLMBridge(
    db_connection_string=":memory:",
    enable_db_logging=True
)

# No database (API calls only, no logging)
service = LLMBridge(enable_db_logging=False)
```

### 2. Production (PostgreSQL)

```python
from llmbridge import LLMBridge

# PostgreSQL with full features
service = LLMBridge(
    db_connection_string="postgresql://user:pass@localhost/myapp",
    enable_db_logging=True
)

# With monitoring
service = LLMBridge(
    db_connection_string="postgresql://user:pass@localhost/myapp",
    enable_db_logging=True,
    enable_monitoring=True  # PostgreSQL only
)
```

### 3. Auto-Detection

```python
import os
from llmbridge import LLMBridge

# Automatically detect backend from DATABASE_URL
service = LLMBridge(
    db_connection_string=os.getenv("DATABASE_URL"),
    enable_db_logging=True
)
# Will use:
# - PostgreSQL if URL starts with postgresql://
# - SQLite if URL starts with sqlite:// or is a file path
# - No database if DATABASE_URL is not set
```

### 4. Backward Compatibility

```python
# Existing code continues to work unchanged
from pgdbm import AsyncDatabaseManager
from llmbridge import LLMBridge

db_manager = AsyncDatabaseManager(config)
service = LLMBridge(db_manager=db_manager)  # Still works!
```

## Testing Strategy

### Unit Tests

```python
# tests/test_backends.py
import pytest
from llmbridge.db_backends import SQLiteBackend, create_backend

@pytest.mark.asyncio
async def test_sqlite_backend():
    """Test SQLite backend operations."""
    backend = SQLiteBackend(":memory:")
    await backend.connect()
    
    # Test table creation
    await backend.execute("""
        CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)
    """)
    
    # Test insert and retrieve
    id = await backend.execute_and_return_id(
        "INSERT INTO test (name) VALUES (?)", "test_value"
    )
    assert id == 1
    
    result = await backend.fetch_one("SELECT * FROM test WHERE id = ?", 1)
    assert result["name"] == "test_value"
    
    await backend.disconnect()

@pytest.mark.asyncio
async def test_backend_auto_detection():
    """Test automatic backend selection."""
    
    # PostgreSQL URL
    backend = create_backend("postgresql://localhost/test")
    assert backend.__class__.__name__ == "PostgreSQLBackend"
    
    # SQLite URL
    backend = create_backend("sqlite:///test.db")
    assert backend.__class__.__name__ == "SQLiteBackend"
    
    # File path
    backend = create_backend("/path/to/test.db")
    assert backend.__class__.__name__ == "SQLiteBackend"
    
    # Memory
    backend = create_backend(":memory:")
    assert backend.__class__.__name__ == "SQLiteBackend"
```

### Integration Tests

```python
# tests/test_sqlite_integration.py
import pytest
from llmbridge import LLMBridge
from llmbridge.schemas import LLMRequest, Message

@pytest.mark.asyncio
async def test_sqlite_full_flow():
    """Test complete flow with SQLite backend."""
    
    # Initialize with in-memory SQLite
    service = LLMBridge(
        db_connection_string=":memory:",
        enable_db_logging=True
    )
    
    await service._ensure_db_initialized()
    
    # Add a model
    from llmbridge.schemas import LLMModel
    model = LLMModel(
        provider="openai",
        model_name="gpt-4o-mini",
        display_name="GPT-4 Mini",
        max_context=128000,
        dollars_per_million_tokens_input=0.15,
        dollars_per_million_tokens_output=0.60
    )
    await service.db.upsert_model(model)
    
    # Verify model was added
    retrieved = await service.db.get_model("openai", "gpt-4o-mini")
    assert retrieved.model_name == "gpt-4o-mini"
    
    # Make an API call (mocked)
    request = LLMRequest(
        messages=[Message(role="user", content="Test")],
        model="gpt-4o-mini"
    )
    
    # Record the call
    await service.db.record_api_call(
        origin="test",
        id_at_origin="user1",
        provider="openai",
        model_name="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=20,
        estimated_cost=0.001,
        response_time_ms=100
    )
    
    # Get usage stats
    stats = await service.db.get_usage_stats("test", "user1", days=1)
    assert stats["total_calls"] == 1
    assert stats["total_tokens"] == 30
    
    await service.close()
```

## Migration Path for Existing Users

### For Users Currently Using pgdbm

**No changes required!** Existing code continues to work:

```python
# This still works
service = LLMBridge(
    db_connection_string="postgresql://...",
    enable_db_logging=True
)
```

### For New Users

**Start simple with SQLite:**

```bash
# Install without PostgreSQL dependency
pip install llmbridge

# Use with SQLite automatically
export DATABASE_URL="~/llmbridge.db"
```

**Upgrade to PostgreSQL when needed:**

```bash
# Add PostgreSQL support
pip install llmbridge[postgres]

# Change connection string
export DATABASE_URL="postgresql://..."
```

## Performance Considerations

### SQLite Performance Characteristics

**Pros:**
- Zero configuration
- Excellent read performance
- Low memory footprint
- Perfect for development and testing
- Good for up to ~100 requests/second

**Cons:**
- Single writer at a time (though WAL mode helps)
- No true async (aiosqlite uses thread pool)
- Limited concurrent performance
- File-based (except :memory:)

### PostgreSQL Performance Characteristics

**Pros:**
- True async with connection pooling
- Excellent concurrent performance
- Scales to thousands of requests/second
- Advanced features (JSONB, arrays, etc.)
- Production-grade reliability

**Cons:**
- Requires separate server process
- More complex setup
- Higher resource usage
- Overkill for development

### Recommendations

| Use Case | Recommended Backend | Rationale |
|----------|-------------------|-----------|
| Local Development | SQLite | Zero configuration, fast startup |
| Testing | SQLite (:memory:) | Isolated, fast, no cleanup needed |
| Small Applications | SQLite | Simple, sufficient performance |
| Production API | PostgreSQL | Scalability, concurrent access |
| Multi-service | PostgreSQL | Connection pooling, isolation |

## Implementation Timeline

### Phase 1: Core Implementation (2-3 days)
- [ ] Create `db_backends.py` with abstract interface
- [ ] Implement SQLiteBackend class
- [ ] Implement PostgreSQLBackend wrapper
- [ ] Create factory function

### Phase 2: Integration (1-2 days)
- [ ] Modify LLMDatabase to use backends
- [ ] Update service.py for auto-detection
- [ ] Create SQLite migrations
- [ ] Update configuration

### Phase 3: Testing (2-3 days)
- [ ] Write backend unit tests
- [ ] Write integration tests
- [ ] Test migration system
- [ ] Performance benchmarking

### Phase 4: Documentation (1 day)
- [ ] Update README
- [ ] Update setup guide
- [ ] Add migration guide
- [ ] Update examples

## Summary

This proposal adds SQLite support to llmbridge with:

- **~200 lines of new code** (mostly in db_backends.py)
- **Zero duplication** of business logic
- **Complete backward compatibility**
- **Automatic backend selection**
- **Graceful degradation** without database
- **Simple migration path** between backends

The implementation is minimal, focused, and maintains the simplicity that makes llmbridge valuable while adding flexibility for different deployment scenarios.