#!/usr/bin/env python3
"""
Example demonstrating the shared connection pattern for llmbridge.

This example shows how to integrate llmbridge into a larger application
while sharing database connections to avoid connection pool exhaustion.

Run with: python examples/shared_connection_example.py
"""

import asyncio
import logging

from pgdbm import AsyncDatabaseManager, DatabaseConfig
from llmbridge import LLMRequest, LLMBridge, Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Application:
    """Example application that uses multiple services with shared connections."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.shared_db = None
        self.llmbridge = None

    async def startup(self):
        """Initialize all services with shared database connection."""
        logger.info("Starting application...")

        # Create shared database manager with a single pool
        config = DatabaseConfig(
            connection_string=self.db_url,
            min_connections=5,
            max_connections=20,  # Single pool for all services
            schema="public",  # Main application schema
        )
        self.shared_db = AsyncDatabaseManager(config)
        await self.shared_db.connect()
        logger.info("Shared database connected")

        # Create LLM service using the shared connection
        self.llmbridge = LLMBridge(
            db_manager=self.shared_db,  # Pass the shared manager
            origin="example-app",
            enable_db_logging=True,
        )

        # Initialize LLM service database (creates schema, runs migrations)
        await self.llmbridge.db.initialize()
        logger.info("LLM service initialized with shared connection")

        # Check pool stats to verify sharing
        stats = await self.shared_db.get_pool_stats()
        logger.info(f"Pool stats: size={stats['size']}, max={stats['max_size']}")

    async def process_request(self, prompt: str, user_id: str = "example-user"):
        """Process a user request using the LLM service."""
        request = LLMRequest(
            messages=[
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content=prompt),
            ],
            model="gpt-3.5-turbo",  # Use a cheaper model for testing
            temperature=0.7,
            max_tokens=150,
        )

        try:
            # Chat with tracking
            response = await self.llmbridge.chat(request, id_at_origin=user_id)
            return response.content
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return None

    async def show_usage_stats(self, user_id: str = "example-user"):
        """Display usage statistics for a user."""
        stats = await self.llmbridge.get_usage_stats(user_id, days=30)
        if stats:
            print(f"\n📊 Usage Stats for {user_id}:")
            print(f"  Total calls: {stats.total_calls}")
            print(f"  Total tokens: {stats.total_tokens}")
            print(f"  Total cost: ${stats.total_cost}")
            print(f"  Most used model: {stats.most_used_model}")
        else:
            print(f"No usage stats found for {user_id}")

    async def shutdown(self):
        """Clean shutdown of all services."""
        logger.info("Shutting down application...")

        # Note: We don't close individual services' connections
        # because they're using the shared manager

        # Only disconnect the shared manager
        if self.shared_db:
            await self.shared_db.disconnect()
            logger.info("Shared database disconnected")


async def main():
    """Run the example application."""
    print("🚀 Shared Connection Pattern Example")
    print("=" * 50)

    # Use a test database URL
    db_url = "postgresql://postgres:postgres@localhost/postgres"
    app = Application(db_url)

    try:
        # Startup
        await app.startup()
        print("\n✅ Application started successfully!")

        # Check available models
        models = await app.llmbridge.get_models_from_db()
        print(f"\n📚 Found {len(models)} models in database")

        # Process a request (only if API keys are configured)
        available_providers = app.llmbridge.get_available_models()
        if available_providers:
            print("\n💬 Processing a sample request...")
            response = await app.process_request("What is 2+2?")
            if response:
                print(f"Response: {response}")

            # Show usage stats
            await app.show_usage_stats()
        else:
            print(
                "\n⚠️  No LLM providers available. Set API keys to test chat functionality."
            )

        # Verify connection sharing
        pool_stats = await app.shared_db.get_pool_stats()
        print(
            f"\n🏊 Connection pool usage: {pool_stats['size']}/{pool_stats['max_size']} connections"
        )

    except Exception as e:
        logger.error(f"Application error: {e}")

    finally:
        # Always cleanup
        await app.shutdown()
        print("\n✅ Application shutdown complete")


if __name__ == "__main__":
    print("This example demonstrates the shared connection pattern.")
    print("Make sure PostgreSQL is running and accessible.")
    print()
    asyncio.run(main())
