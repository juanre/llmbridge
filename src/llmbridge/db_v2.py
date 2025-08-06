"""Database manager for LLM service with backend abstraction."""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4
from datetime import datetime

from .database_backends import DatabaseBackend
from .postgres_backend import PostgresBackend
from .sqlite_backend import SQLiteBackend
from .schemas import CallRecord, LLMModel, UsageStats

logger = logging.getLogger(__name__)


def create_backend(connection_string: Optional[str] = None) -> DatabaseBackend:
    """Factory function to create appropriate database backend.
    
    Args:
        connection_string: Database connection string.
            - If starts with 'postgresql://' or 'postgres://', creates PostgreSQL backend
            - If starts with 'sqlite://' or ends with '.db', creates SQLite backend
            - If None, creates SQLite backend with default database
    
    Returns:
        DatabaseBackend instance
    """
    if connection_string is None:
        # Default to SQLite for local development
        return SQLiteBackend("llmbridge.db")
    elif connection_string.startswith(("postgresql://", "postgres://")):
        return PostgresBackend(connection_string)
    elif connection_string.startswith("sqlite://"):
        # Extract path from sqlite:///path/to/db.db
        db_path = connection_string.replace("sqlite:///", "").replace("sqlite://", "")
        return SQLiteBackend(db_path)
    elif connection_string.endswith(".db"):
        # Assume it's a SQLite file path
        return SQLiteBackend(connection_string)
    else:
        # Default to PostgreSQL for backward compatibility
        return PostgresBackend(connection_string)


class LLMDatabase:
    """Database manager for LLM service with backend abstraction."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        backend: Optional[DatabaseBackend] = None,
    ):
        """Initialize database manager.

        Args:
            connection_string: Database connection string.
            backend: Optional pre-configured database backend.
        """
        if backend:
            self.backend = backend
        else:
            self.backend = create_backend(connection_string)
        
        self._initialized = False

    async def initialize(self):
        """Initialize database connection."""
        if self._initialized:
            return
        
        await self.backend.initialize()
        self._initialized = True

    async def close(self):
        """Close database connections."""
        if self._initialized:
            await self.backend.close()
            self._initialized = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    # Model management methods

    async def add_model(self, model: LLMModel) -> int:
        """Add a new model to the registry."""
        placeholder = self.backend.get_placeholder
        
        query = f"""
            INSERT INTO models (
                provider, model_name, display_name, description,
                max_context, max_output_tokens, supports_vision,
                supports_function_calling, supports_json_mode, supports_parallel_tool_calls,
                tool_call_format, dollars_per_million_tokens_input, dollars_per_million_tokens_output,
                inactive_from
            ) VALUES (
                {placeholder(1)}, {placeholder(2)}, {placeholder(3)}, {placeholder(4)},
                {placeholder(5)}, {placeholder(6)}, {placeholder(7)},
                {placeholder(8)}, {placeholder(9)}, {placeholder(10)},
                {placeholder(11)}, {placeholder(12)}, {placeholder(13)}, {placeholder(14)}
            )
        """
        
        if isinstance(self.backend, PostgresBackend):
            query += " RETURNING id"
            
        params = (
            model.provider,
            model.model_name,
            model.display_name,
            model.description,
            model.max_context,
            model.max_output_tokens,
            model.supports_vision,
            model.supports_function_calling,
            model.supports_json_mode,
            model.supports_parallel_tool_calls,
            model.tool_call_format,
            float(model.dollars_per_million_tokens_input) if model.dollars_per_million_tokens_input else None,
            float(model.dollars_per_million_tokens_output) if model.dollars_per_million_tokens_output else None,
            model.inactive_from,
        )
        
        return await self.backend.insert_returning(query, params)

    async def get_model(self, provider: str, model_name: str) -> Optional[LLMModel]:
        """Get a specific model by provider and name."""
        placeholder = self.backend.get_placeholder
        
        query = f"""
            SELECT * FROM models
            WHERE provider = {placeholder(1)} 
            AND model_name = {placeholder(2)}
            AND inactive_from IS NULL
        """
        
        row = await self.backend.fetch_one(query, (provider, model_name))
        
        if row:
            return self._row_to_model(row)
        return None

    async def list_models(
        self, provider: Optional[str] = None, active_only: bool = True
    ) -> List[LLMModel]:
        """List all models, optionally filtered by provider."""
        placeholder = self.backend.get_placeholder
        
        if provider:
            query = f"""
                SELECT * FROM models
                WHERE provider = {placeholder(1)}
            """
            params = (provider,)
            if active_only:
                query += " AND inactive_from IS NULL"
        else:
            if active_only:
                query = "SELECT * FROM models WHERE inactive_from IS NULL"
                params = ()
            else:
                query = "SELECT * FROM models"
                params = ()
        
        query += " ORDER BY provider, model_name"
        
        rows = await self.backend.fetch_all(query, params)
        return [self._row_to_model(row) for row in rows]

    async def update_model(self, model_id: int, updates: Dict) -> bool:
        """Update a model's configuration."""
        if not updates:
            return False
        
        placeholder = self.backend.get_placeholder
        set_clauses = []
        params = []
        param_index = 1
        
        for key, value in updates.items():
            set_clauses.append(f"{key} = {placeholder(param_index)}")
            if isinstance(value, Decimal):
                params.append(float(value))
            else:
                params.append(value)
            param_index += 1
        
        params.append(model_id)
        
        query = f"""
            UPDATE models
            SET {', '.join(set_clauses)}
            WHERE id = {placeholder(param_index)}
        """
        
        await self.backend.execute(query, tuple(params))
        return True

    async def deactivate_model(self, provider: str, model_name: str) -> bool:
        """Deactivate a model."""
        placeholder = self.backend.get_placeholder
        
        # SQLite uses datetime() function differently
        if isinstance(self.backend, SQLiteBackend):
            date_val = "datetime('now')"
            query = f"""
                UPDATE models
                SET inactive_from = {date_val}
                WHERE provider = {placeholder(1)} AND model_name = {placeholder(2)}
            """
            params = (provider, model_name)
        else:
            query = f"""
                UPDATE models
                SET inactive_from = NOW()
                WHERE provider = {placeholder(1)} AND model_name = {placeholder(2)}
            """
            params = (provider, model_name)
        
        await self.backend.execute(query, params)
        return True

    # API call tracking methods

    async def record_api_call(self, call_record: CallRecord) -> UUID:
        """Record an API call for tracking and billing."""
        placeholder = self.backend.get_placeholder
        
        call_id = call_record.id or uuid4()
        
        query = f"""
            INSERT INTO api_calls (
                id, origin, id_at_origin, model_id, provider, model_name,
                prompt_tokens, completion_tokens, total_tokens,
                estimated_cost, dollars_per_million_tokens_input_used,
                dollars_per_million_tokens_output_used, error_type, error_message, called_at
            ) VALUES (
                {placeholder(1)}, {placeholder(2)}, {placeholder(3)}, {placeholder(4)},
                {placeholder(5)}, {placeholder(6)}, {placeholder(7)}, {placeholder(8)},
                {placeholder(9)}, {placeholder(10)}, {placeholder(11)}, {placeholder(12)},
                {placeholder(13)}, {placeholder(14)}, {placeholder(15)}
            )
        """
        
        params = (
            str(call_id),
            call_record.origin,
            call_record.id_at_origin,
            call_record.model_id,
            call_record.provider,
            call_record.model_name,
            call_record.prompt_tokens,
            call_record.completion_tokens,
            call_record.total_tokens,
            float(call_record.estimated_cost),
            float(call_record.dollars_per_million_tokens_input_used) if call_record.dollars_per_million_tokens_input_used else None,
            float(call_record.dollars_per_million_tokens_output_used) if call_record.dollars_per_million_tokens_output_used else None,
            call_record.error_type if hasattr(call_record, 'error_type') else None,
            call_record.error_message if hasattr(call_record, 'error_message') else None,
            call_record.called_at if hasattr(call_record, 'called_at') else datetime.utcnow(),
        )
        
        await self.backend.execute(query, params)
        return call_id

    async def get_usage_stats(
        self, origin: Optional[str] = None, days: int = 30
    ) -> UsageStats:
        """Get usage statistics for the specified period."""
        placeholder = self.backend.get_placeholder
        
        # SQLite uses datetime() function differently
        if isinstance(self.backend, SQLiteBackend):
            date_calc = f"datetime('now', '-{days} days')"
        else:
            date_calc = f"NOW() - INTERVAL '{days} days'"
        
        base_query = f"""
            FROM api_calls
            WHERE called_at >= {date_calc}
        """
        
        params = ()
        if origin:
            base_query += f" AND origin = {placeholder(1)}"
            params = (origin,)
        
        # Get aggregated stats
        stats_query = f"""
            SELECT
                COUNT(*) as total_calls,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(estimated_cost), 0) as total_cost,
                COUNT(DISTINCT provider) as unique_providers,
                COUNT(DISTINCT model_name) as unique_models
            {base_query}
        """
        
        row = await self.backend.fetch_one(stats_query, params)
        
        # Get per-provider breakdown
        provider_query = f"""
            SELECT
                provider,
                COUNT(*) as calls,
                COALESCE(SUM(total_tokens), 0) as tokens,
                COALESCE(SUM(estimated_cost), 0) as cost
            {base_query}
            GROUP BY provider
        """
        
        provider_rows = await self.backend.fetch_all(provider_query, params)
        
        provider_breakdown = {
            row["provider"]: {
                "calls": row["calls"],
                "tokens": row["tokens"],
                "cost": float(row["cost"]) if row["cost"] else 0.0,
            }
            for row in provider_rows
        }
        
        total_calls = row["total_calls"]
        total_cost = float(row["total_cost"]) if row["total_cost"] else 0.0
        
        return UsageStats(
            total_calls=total_calls,
            total_tokens=row["total_tokens"],
            total_cost=Decimal(str(total_cost)),
            avg_cost_per_call=Decimal(str(total_cost / total_calls)) if total_calls > 0 else Decimal("0"),
            success_rate=Decimal("1.0"),  # TODO: Calculate based on error status
            # Note: UsageStats doesn't have unique_providers, unique_models, provider_breakdown
            # These would need to be added to the schema or handled differently
        )

    async def get_recent_calls(
        self, limit: int = 100, offset: int = 0
    ) -> List[CallRecord]:
        """Get recent API calls."""
        placeholder = self.backend.get_placeholder
        
        query = f"""
            SELECT * FROM api_calls
            ORDER BY called_at DESC
            LIMIT {placeholder(1)} OFFSET {placeholder(2)}
        """
        
        rows = await self.backend.fetch_all(query, (limit, offset))
        
        return [
            CallRecord(
                id=UUID(row["id"]),
                origin=row["origin"],
                id_at_origin=row["id_at_origin"],
                model_id=row["model_id"],
                provider=row["provider"],
                model_name=row["model_name"],
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
                estimated_cost=Decimal(str(row["estimated_cost"])),
                dollars_per_million_tokens_input_used=Decimal(str(row["dollars_per_million_tokens_input_used"])) 
                    if row["dollars_per_million_tokens_input_used"] else None,
                dollars_per_million_tokens_output_used=Decimal(str(row["dollars_per_million_tokens_output_used"]))
                    if row["dollars_per_million_tokens_output_used"] else None,
                error_type=row.get("error_type"),
                error_message=row.get("error_message"),
                called_at=row["called_at"],
            )
            for row in rows
        ]

    def _row_to_model(self, row: Dict) -> LLMModel:
        """Convert a database row to an LLMModel object."""
        return LLMModel(
            id=row.get("id"),
            provider=row["provider"],
            model_name=row["model_name"],
            display_name=row.get("display_name"),
            description=row.get("description"),
            max_context=row.get("max_context"),
            max_output_tokens=row.get("max_output_tokens"),
            supports_vision=bool(row.get("supports_vision")),
            supports_function_calling=bool(row.get("supports_function_calling")),
            supports_json_mode=bool(row.get("supports_json_mode")),
            supports_parallel_tool_calls=bool(row.get("supports_parallel_tool_calls")),
            tool_call_format=row.get("tool_call_format"),
            dollars_per_million_tokens_input=Decimal(str(row["dollars_per_million_tokens_input"])) 
                if row.get("dollars_per_million_tokens_input") else None,
            dollars_per_million_tokens_output=Decimal(str(row["dollars_per_million_tokens_output"]))
                if row.get("dollars_per_million_tokens_output") else None,
            inactive_from=row.get("inactive_from"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )