"""Database backend implementations for llmbridge.

This module provides database abstraction to support both PostgreSQL (via pgdbm)
and SQLite for local development scenarios.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from uuid import UUID
import json


class DatabaseBackend(ABC):
    """Abstract base class for database backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database connection and create tables if needed."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    async def execute(self, query: str, params: Optional[Tuple] = None) -> None:
        """Execute a query without returning results."""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row from the database."""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows from the database."""
        pass

    @abstractmethod
    async def fetch_value(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from the database."""
        pass

    @abstractmethod
    async def insert_returning(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute an INSERT query and return the generated ID."""
        pass

    @abstractmethod
    def get_placeholder(self, index: int) -> str:
        """Get the parameter placeholder for the given index (1-based)."""
        pass