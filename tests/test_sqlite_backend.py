"""Tests for SQLite backend implementation."""

import pytest
import tempfile
import os
from pathlib import Path
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

from llmbridge.db_v2 import LLMDatabase, create_backend
from llmbridge.sqlite_backend import SQLiteBackend
from llmbridge.schemas import LLMModel, CallRecord


@pytest.fixture
async def sqlite_db():
    """Create a temporary SQLite database for testing."""
    # Create a temporary file for the database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Create database instance
    db = LLMDatabase(connection_string=f"sqlite:///{db_path}")
    await db.initialize()
    
    yield db
    
    # Cleanup
    await db.close()
    os.unlink(db_path)


@pytest.fixture
async def postgres_db(llm_test_db):
    """Create a PostgreSQL database for comparison testing."""
    db = LLMDatabase(connection_string=llm_test_db["db_url"])
    await db.initialize()
    
    yield db
    
    await db.close()


class TestBackendFactory:
    """Test the backend factory function."""
    
    def test_create_sqlite_backend_default(self):
        """Test creating SQLite backend with no connection string."""
        backend = create_backend(None)
        assert isinstance(backend, SQLiteBackend)
        assert backend.db_path == "llmbridge.db"
    
    def test_create_sqlite_backend_explicit(self):
        """Test creating SQLite backend with sqlite:// URL."""
        backend = create_backend("sqlite:///test.db")
        assert isinstance(backend, SQLiteBackend)
        assert backend.db_path == "test.db"
    
    def test_create_sqlite_backend_file_path(self):
        """Test creating SQLite backend with .db file path."""
        backend = create_backend("mydata.db")
        assert isinstance(backend, SQLiteBackend)
        assert backend.db_path == "mydata.db"
    
    def test_create_postgres_backend(self):
        """Test creating PostgreSQL backend."""
        from llmbridge.postgres_backend import PostgresBackend
        
        backend = create_backend("postgresql://user:pass@localhost/db")
        assert isinstance(backend, PostgresBackend)


@pytest.mark.asyncio
class TestSQLiteBackend:
    """Test SQLite backend functionality."""
    
    async def test_initialization(self, sqlite_db):
        """Test that SQLite database initializes correctly."""
        assert sqlite_db._initialized
        assert sqlite_db.backend is not None
        assert isinstance(sqlite_db.backend, SQLiteBackend)
    
    async def test_default_models_inserted(self, sqlite_db):
        """Test that default models are inserted on initialization."""
        models = await sqlite_db.list_models()
        assert len(models) > 0
        
        # Check for specific expected models
        model_names = {f"{m.provider}:{m.model_name}" for m in models}
        assert "openai:gpt-4o" in model_names
        assert "anthropic:claude-3-5-sonnet-20241022" in model_names
        assert "google:gemini-1.5-pro" in model_names
    
    async def test_add_and_get_model(self, sqlite_db):
        """Test adding and retrieving a model."""
        test_model = LLMModel(
            provider="test",
            model_name="test-model",
            display_name="Test Model",
            description="A test model",
            max_context=1000,
            max_output_tokens=500,
            supports_vision=True,
            supports_function_calling=False,
            dollars_per_million_tokens_input=Decimal("1.50"),
            dollars_per_million_tokens_output=Decimal("3.00"),
        )
        
        # Add model
        model_id = await sqlite_db.add_model(test_model)
        assert model_id is not None
        
        # Retrieve model
        retrieved = await sqlite_db.get_model("test", "test-model")
        assert retrieved is not None
        assert retrieved.provider == "test"
        assert retrieved.model_name == "test-model"
        assert retrieved.max_context == 1000
        assert retrieved.supports_vision is True
        assert retrieved.supports_function_calling is False
    
    async def test_list_models_by_provider(self, sqlite_db):
        """Test listing models filtered by provider."""
        openai_models = await sqlite_db.list_models(provider="openai")
        assert len(openai_models) > 0
        assert all(m.provider == "openai" for m in openai_models)
        
        anthropic_models = await sqlite_db.list_models(provider="anthropic")
        assert len(anthropic_models) > 0
        assert all(m.provider == "anthropic" for m in anthropic_models)
    
    async def test_update_model(self, sqlite_db):
        """Test updating a model's configuration."""
        # First get an existing model
        models = await sqlite_db.list_models()
        test_model = models[0]
        
        # Update it
        updates = {
            "description": "Updated description",
            "max_context": 999999,
        }
        
        success = await sqlite_db.update_model(test_model.id, updates)
        assert success is True
        
        # Verify the update succeeded
        all_models = await sqlite_db.list_models(provider=test_model.provider, active_only=False)
        updated_model = next((m for m in all_models if m.id == test_model.id), None)
        assert updated_model is not None
        assert updated_model.description == "Updated description"
        assert updated_model.max_context == 999999
    
    async def test_deactivate_model(self, sqlite_db):
        """Test deactivating a model."""
        # Get a model
        models = await sqlite_db.list_models()
        test_model = models[0]
        
        # Deactivate it
        success = await sqlite_db.deactivate_model(test_model.provider, test_model.model_name)
        assert success is True
        
        # Should not be in active models
        active_models = await sqlite_db.list_models(provider=test_model.provider)
        assert test_model.model_name not in [m.model_name for m in active_models]
        
        # Should be in all models
        all_models = await sqlite_db.list_models(provider=test_model.provider, active_only=False)
        assert test_model.model_name in [m.model_name for m in all_models]
    
    async def test_record_api_call(self, sqlite_db):
        """Test recording an API call."""
        call_record = CallRecord(
            id=uuid4(),
            origin="test",
            id_at_origin="user-123",
            provider="openai",
            model_name="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost=Decimal("0.0015"),
            called_at=datetime.now(timezone.utc),
        )
        
        call_id = await sqlite_db.record_api_call(call_record)
        assert call_id == call_record.id
        
        # Verify it was recorded
        recent_calls = await sqlite_db.get_recent_calls(limit=1)
        assert len(recent_calls) == 1
        assert recent_calls[0].provider == "openai"
        assert recent_calls[0].model_name == "gpt-4o"
        assert recent_calls[0].total_tokens == 150
    
    async def test_record_api_call_with_error(self, sqlite_db):
        """Test recording an API call with an error."""
        call_record = CallRecord(
            id=uuid4(),
            origin="test",
            id_at_origin="user-456",
            provider="anthropic",
            model_name="claude-3-opus",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal("0"),
            error_type="rate_limited",
            error_message="Rate limit exceeded",
            called_at=datetime.now(timezone.utc),
        )
        
        call_id = await sqlite_db.record_api_call(call_record)
        assert call_id == call_record.id
        
        # Verify error was recorded
        recent_calls = await sqlite_db.get_recent_calls(limit=1)
        assert len(recent_calls) == 1
        assert recent_calls[0].error_message == "Rate limit exceeded"
        assert recent_calls[0].total_tokens == 0
    
    async def test_get_usage_stats(self, sqlite_db):
        """Test getting usage statistics."""
        # Record some calls
        for i in range(5):
            call = CallRecord(
                id=uuid4(),
                origin="test",
                id_at_origin=f"user-{i}",
                provider="openai" if i % 2 == 0 else "anthropic",
                model_name="gpt-4o" if i % 2 == 0 else "claude-3-sonnet",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                estimated_cost=Decimal("0.0015"),
                called_at=datetime.now(timezone.utc),
            )
            await sqlite_db.record_api_call(call)
        
        # Get stats
        stats = await sqlite_db.get_usage_stats(origin="test", days=30)
        
        assert stats.total_calls == 5
        assert stats.total_tokens == 750  # 5 calls * 150 tokens
        assert stats.total_cost == Decimal("0.0075")  # 5 * 0.0015
        assert stats.avg_cost_per_call == Decimal("0.0015")
        assert stats.success_rate == Decimal("1.0")
    
    async def test_get_recent_calls(self, sqlite_db):
        """Test getting recent API calls with pagination."""
        # Record 10 calls
        for i in range(10):
            call = CallRecord(
                id=uuid4(),
                origin="test",
                id_at_origin=f"user-{i}",
                provider="openai",
                model_name=f"model-{i}",
                prompt_tokens=50,
                completion_tokens=50 + i,
                total_tokens=100 + i,
                estimated_cost=Decimal("0.001"),
                called_at=datetime.now(timezone.utc),
            )
            await sqlite_db.record_api_call(call)
        
        # Get first page
        page1 = await sqlite_db.get_recent_calls(limit=5, offset=0)
        assert len(page1) == 5
        
        # Get second page
        page2 = await sqlite_db.get_recent_calls(limit=5, offset=5)
        assert len(page2) == 5
        
        # Verify they're different
        page1_ids = {c.id for c in page1}
        page2_ids = {c.id for c in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0


@pytest.mark.asyncio
class TestSQLiteVsPostgreSQL:
    """Test that SQLite backend produces same results as PostgreSQL."""
    
    @pytest.mark.skip(reason="Requires PostgreSQL to be running")
    async def test_model_operations_parity(self, sqlite_db, postgres_db):
        """Test that model operations work the same in both backends."""
        test_model = LLMModel(
            provider="test",
            model_name="parity-test",
            display_name="Parity Test",
            max_context=2000,
            supports_vision=True,
            dollars_per_million_tokens_input=Decimal("2.50"),
        )
        
        # Add to both databases
        sqlite_id = await sqlite_db.add_model(test_model)
        postgres_id = await postgres_db.add_model(test_model)
        
        assert sqlite_id is not None
        assert postgres_id is not None
        
        # Retrieve from both
        sqlite_model = await sqlite_db.get_model("test", "parity-test")
        postgres_model = await postgres_db.get_model("test", "parity-test")
        
        assert sqlite_model.provider == postgres_model.provider
        assert sqlite_model.model_name == postgres_model.model_name
        assert sqlite_model.max_context == postgres_model.max_context
        assert sqlite_model.supports_vision == postgres_model.supports_vision