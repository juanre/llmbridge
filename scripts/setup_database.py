#!/usr/bin/env python3
"""Setup database for LLM service - creates schema and runs migrations."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llmbridge.db import LLMDatabase


async def setup_database():
    """Initialize database and run migrations."""
    print("Setting up LLM service database...")

    # Create database connection
    db = LLMDatabase()

    try:
        # Initialize connection and schema
        await db.initialize()
        print("✓ Database connection established")
        print(f"✓ Using schema: {db.config.schema}")

        # Run migrations
        print("\nApplying migrations...")
        result = await db.apply_migrations()

        if result.get("applied"):
            print(f"✓ Applied {len(result['applied'])} migrations:")
            for migration in result["applied"]:
                print(f"  - {migration}")

        if result.get("skipped"):
            print(f"✓ Skipped {len(result['skipped'])} already applied migrations")

        # Verify tables exist
        print("\nVerifying database structure...")
        pool_stats = await db.get_pool_stats()
        print(f"✓ Connection pool status: {pool_stats}")

        # Test a basic query
        models = await db.list_models()
        print(f"✓ Database ready! Found {len(models)} models in registry")

        return True

    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        return False

    finally:
        await db.close()


async def reset_database():
    """Drop and recreate the database schema."""
    print("⚠️  WARNING: This will DELETE all data in the llmbridge schema!")
    response = input("Are you sure you want to continue? (yes/no): ")

    if response.lower() != "yes":
        print("Aborted.")
        return False

    db = LLMDatabase()

    try:
        await db.initialize()

        # Drop the schema cascade
        print("\nDropping schema...")
        await db.db.execute("DROP SCHEMA IF EXISTS llmbridge CASCADE")
        print("✓ Schema dropped")

        # Recreate by reinitializing
        await db.close()
        db = LLMDatabase()
        await db.initialize()

        # Run migrations on fresh schema
        print("\nApplying migrations to fresh schema...")
        result = await db.apply_migrations()
        print(f"✓ Applied {len(result.get('applied', []))} migrations")

        print("\n✓ Database reset complete!")
        return True

    except Exception as e:
        print(f"✗ Database reset failed: {e}")
        return False

    finally:
        await db.close()


async def check_status():
    """Check database status and migration state."""
    db = LLMDatabase()

    try:
        await db.initialize()

        print("Database Status")
        print("=" * 50)

        # Connection info
        print(f"Schema: {db.config.schema}")
        print(f"Connection: {db.config.connection_string}")

        # Pool stats
        pool_stats = await db.get_pool_stats()
        print("\nConnection Pool:")
        print(f"  - Size: {pool_stats.get('size', 'N/A')}")
        print(f"  - Free: {pool_stats.get('free', 'N/A')}")
        print(f"  - Pending: {pool_stats.get('pending', 'N/A')}")

        # Migration status
        print("\nMigration Status:")
        # async-db-utils doesn't have get_status method, so we'll just note migrations are managed
        print("  ✓ Migrations are managed by async-db-utils")

        # Model count
        models = await db.list_models()
        print("\nModel Registry:")
        print(f"  - Total models: {len(models)}")

        # Group by provider
        by_provider = {}
        for model in models:
            by_provider.setdefault(model.provider, 0)
            by_provider[model.provider] += 1

        for provider, count in sorted(by_provider.items()):
            print(f"  - {provider}: {count} models")

        # Health check
        print("\nHealth Check:")
        health = await db.health_check()
        print(f"  - Status: {health['status']}")
        if health.get("error"):
            print(f"  - Error: {health['error']}")

        return True

    except Exception as e:
        print(f"✗ Status check failed: {e}")
        return False

    finally:
        await db.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Service Database Setup")
    parser.add_argument(
        "command", choices=["setup", "reset", "status"], help="Command to run"
    )

    args = parser.parse_args()

    if args.command == "setup":
        success = asyncio.run(setup_database())
    elif args.command == "reset":
        success = asyncio.run(reset_database())
    elif args.command == "status":
        success = asyncio.run(check_status())

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
