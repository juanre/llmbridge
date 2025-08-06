"""PostgreSQL backend implementation for llmbridge using pgdbm."""

from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from uuid import UUID

from pgdbm import AsyncDatabaseManager
from .database_backends import DatabaseBackend


class PostgresBackend(DatabaseBackend):
    """PostgreSQL database backend implementation using pgdbm."""

    def __init__(self, connection_string: str):
        """Initialize PostgreSQL backend.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        self.db_manager: Optional[AsyncDatabaseManager] = None

    async def initialize(self) -> None:
        """Initialize the database connection."""
        self.db_manager = AsyncDatabaseManager(self.connection_string)
        await self.db_manager.initialize()

    async def close(self) -> None:
        """Close the database connection."""
        if self.db_manager:
            await self.db_manager.close()
            self.db_manager = None

    async def execute(self, query: str, params: Optional[Tuple] = None) -> None:
        """Execute a query without returning results."""
        if not self.db_manager:
            raise RuntimeError("Database not initialized")
        
        await self.db_manager.execute(query, params)

    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row from the database."""
        if not self.db_manager:
            raise RuntimeError("Database not initialized")
        
        result = await self.db_manager.fetch_row(query, params)
        if result:
            return dict(result)
        return None

    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows from the database."""
        if not self.db_manager:
            raise RuntimeError("Database not initialized")
        
        results = await self.db_manager.fetch_rows(query, params)
        return [dict(row) for row in results]

    async def fetch_value(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from the database."""
        if not self.db_manager:
            raise RuntimeError("Database not initialized")
        
        return await self.db_manager.fetch_value(query, params)

    async def insert_returning(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute an INSERT query and return the generated ID."""
        if not self.db_manager:
            raise RuntimeError("Database not initialized")
        
        # PostgreSQL supports RETURNING clause directly
        result = await self.db_manager.fetch_value(query, params)
        return result

    def get_placeholder(self, index: int) -> str:
        """Get the parameter placeholder for the given index (1-based)."""
        # PostgreSQL uses $1, $2, etc.
        return f"${index}"