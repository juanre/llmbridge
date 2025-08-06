"""SQLite backend implementation for llmbridge."""

import aiosqlite
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pathlib import Path

from .database_backends import DatabaseBackend

# Configure datetime adapter for Python 3.12+
def adapt_datetime(val):
    """Adapt datetime to ISO 8601 string."""
    return val.isoformat()

def convert_datetime(val):
    """Convert ISO 8601 string to datetime."""
    return datetime.fromisoformat(val.decode())

# Register the adapters
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("TIMESTAMP", convert_datetime)


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend implementation."""

    def __init__(self, db_path: str = "llmbridge.db"):
        """Initialize SQLite backend.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize the database connection and create tables if needed."""
        # Enable parse_decltypes to use our custom converters
        self.conn = await aiosqlite.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self.conn.row_factory = aiosqlite.Row
        
        # Enable foreign keys
        await self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Create tables if they don't exist
        await self._create_tables()
        await self._insert_default_models()
        
    async def _create_tables(self) -> None:
        """Create the required tables if they don't exist."""
        # Create models table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                display_name TEXT,
                description TEXT,
                max_context INTEGER,
                max_output_tokens INTEGER,
                supports_vision BOOLEAN DEFAULT 0,
                supports_function_calling BOOLEAN DEFAULT 0,
                supports_json_mode BOOLEAN DEFAULT 0,
                supports_parallel_tool_calls BOOLEAN DEFAULT 0,
                tool_call_format TEXT,
                dollars_per_million_tokens_input REAL,
                dollars_per_million_tokens_output REAL,
                inactive_from TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, model_name)
            )
        """)
        
        # Create api_calls table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id TEXT PRIMARY KEY,
                origin TEXT NOT NULL,
                id_at_origin TEXT NOT NULL,
                model_id INTEGER,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                estimated_cost REAL NOT NULL,
                dollars_per_million_tokens_input_used REAL,
                dollars_per_million_tokens_output_used REAL,
                error_type TEXT,
                error_message TEXT,
                called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        """)
        
        # Create indices
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_calls_called_at 
            ON api_calls(called_at DESC)
        """)
        
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_calls_provider_model 
            ON api_calls(provider, model_name)
        """)
        
        await self.conn.commit()

    async def _insert_default_models(self) -> None:
        """Insert default model configurations if the table is empty."""
        count = await self.fetch_value("SELECT COUNT(*) FROM models", ())
        if count > 0:
            return
            
        # Default models data (provider, model_name, display_name, description, max_context, max_output_tokens,
        # supports_vision, supports_function_calling, supports_json_mode, supports_parallel_tool_calls,
        # dollars_per_million_tokens_input, dollars_per_million_tokens_output)
        default_models = [
            # OpenAI models
            ("openai", "gpt-4o", "GPT-4o", "Latest GPT-4 Omni model", 128000, 16384, True, True, True, True, 2.50, 10.00),
            ("openai", "gpt-4o-mini", "GPT-4o Mini", "Small, affordable GPT-4 Omni model", 128000, 16384, True, True, True, True, 0.15, 0.60),
            ("openai", "gpt-4-turbo", "GPT-4 Turbo", "GPT-4 Turbo with vision", 128000, 4096, True, True, True, True, 10.00, 30.00),
            ("openai", "gpt-3.5-turbo", "GPT-3.5 Turbo", "Fast, affordable GPT-3.5", 16385, 4096, False, True, True, False, 0.50, 1.50),
            
            # Anthropic models
            ("anthropic", "claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "Most intelligent Claude model", 200000, 8192, True, True, False, False, 3.00, 15.00),
            ("anthropic", "claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "Fast and affordable Claude model", 200000, 8192, False, True, False, False, 1.00, 5.00),
            ("anthropic", "claude-3-opus-20240229", "Claude 3 Opus", "Powerful Claude model for complex tasks", 200000, 4096, True, True, False, False, 15.00, 75.00),
            
            # Google models
            ("google", "gemini-1.5-pro", "Gemini 1.5 Pro", "Google's most capable model", 2097152, 8192, True, True, False, False, 1.25, 5.00),
            ("google", "gemini-1.5-flash", "Gemini 1.5 Flash", "Fast and efficient Gemini model", 1048576, 8192, True, True, False, False, 0.075, 0.30),
            ("google", "gemini-pro", "Gemini Pro", "Capable general-purpose model", 32768, 8192, False, True, False, False, 0.50, 1.50),
        ]
        
        for model_data in default_models:
            await self.conn.execute("""
                INSERT OR IGNORE INTO models (
                    provider, model_name, display_name, description,
                    max_context, max_output_tokens, supports_vision,
                    supports_function_calling, supports_json_mode, supports_parallel_tool_calls,
                    dollars_per_million_tokens_input, dollars_per_million_tokens_output
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, model_data)
        
        await self.conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def execute(self, query: str, params: Optional[Tuple] = None) -> None:
        """Execute a query without returning results."""
        if not self.conn:
            raise RuntimeError("Database not initialized")
        
        # Convert query from PostgreSQL format to SQLite format
        query = self._convert_query(query)
        params = self._convert_params(params)
        
        await self.conn.execute(query, params or ())
        await self.conn.commit()

    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row from the database."""
        if not self.conn:
            raise RuntimeError("Database not initialized")
        
        query = self._convert_query(query)
        params = self._convert_params(params)
        
        async with self.conn.execute(query, params or ()) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows from the database."""
        if not self.conn:
            raise RuntimeError("Database not initialized")
        
        query = self._convert_query(query)
        params = self._convert_params(params)
        
        async with self.conn.execute(query, params or ()) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetch_value(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from the database."""
        if not self.conn:
            raise RuntimeError("Database not initialized")
        
        query = self._convert_query(query)
        params = self._convert_params(params)
        
        async with self.conn.execute(query, params or ()) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

    async def insert_returning(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute an INSERT query and return the generated ID."""
        if not self.conn:
            raise RuntimeError("Database not initialized")
        
        query = self._convert_query(query)
        params = self._convert_params(params)
        
        # SQLite doesn't support RETURNING clause in the same way
        # We need to handle this differently
        if "RETURNING" in query.upper():
            # Remove RETURNING clause and execute insert
            query = query[:query.upper().index("RETURNING")].strip()
        
        cursor = await self.conn.execute(query, params or ())
        await self.conn.commit()
        
        # Return the last inserted row ID
        return cursor.lastrowid

    def get_placeholder(self, index: int) -> str:
        """Get the parameter placeholder for the given index (1-based)."""
        # SQLite uses ? for placeholders
        return "?"

    def _convert_query(self, query: str) -> str:
        """Convert PostgreSQL-style query to SQLite format."""
        if not query:
            return query
            
        # Convert $1, $2, etc. to ?
        import re
        query = re.sub(r'\$\d+', '?', query)
        
        # Convert PostgreSQL NOW() to SQLite datetime
        query = query.replace("NOW()", "datetime('now')")
        query = query.replace("now()", "datetime('now')")
        
        # Convert boolean literals
        query = query.replace(" TRUE", " 1")
        query = query.replace(" FALSE", " 0")
        query = query.replace(" true", " 1") 
        query = query.replace(" false", " 0")
        
        # Convert UUID generation
        query = query.replace("gen_random_uuid()", "?")
        
        # Handle ON CONFLICT for SQLite
        query = query.replace("ON CONFLICT", "ON CONFLICT")
        
        return query

    def _convert_params(self, params: Optional[Tuple]) -> Optional[Tuple]:
        """Convert parameters to SQLite-compatible format."""
        if not params:
            return params
            
        converted = []
        for param in params:
            if isinstance(param, UUID):
                converted.append(str(param))
            elif isinstance(param, Decimal):
                converted.append(float(param))
            elif isinstance(param, bool):
                converted.append(1 if param else 0)
            elif isinstance(param, dict):
                converted.append(json.dumps(param))
            else:
                converted.append(param)
        
        return tuple(converted)