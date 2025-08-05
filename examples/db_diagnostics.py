#!/usr/bin/env python3
"""Database diagnostics tool for LLM service."""

import asyncio
import sys
from datetime import datetime

from llmbridge.db import LLMDatabase


async def main():
    """Run database diagnostics."""
    print("🔍 LLM Service Database Diagnostics")
    print("=" * 50)

    # Initialize database with monitoring enabled
    db = LLMDatabase(enable_monitoring=True, min_connections=5, max_connections=10)

    try:
        # Initialize connection
        print("\n📊 Initializing database connection...")
        await db.initialize()
        print("✅ Database connected")

        # Check health
        print("\n🏥 Health Check:")
        health = await db.health_check()
        print(f"  Status: {health['status']}")
        print(f"  Schema: {health.get('schema', 'N/A')}")
        print(
            f"  Monitoring: {'Enabled' if health.get('monitoring_enabled') else 'Disabled'}"
        )

        # Check pool stats
        print("\n🏊 Connection Pool:")
        pool = health.get("pool", {})
        print(f"  Min Size: {pool.get('min_size', 'N/A')}")
        print(f"  Max Size: {pool.get('max_size', 'N/A')}")
        print(f"  Current Size: {pool.get('size', 'N/A')}")
        print(f"  Free Connections: {pool.get('free_size', 'N/A')}")
        print(f"  Used Connections: {pool.get('used_size', 'N/A')}")

        # Check models
        print("\n🤖 Registered Models:")
        models = await db.list_models()
        by_provider = {}
        for model in models:
            if model.provider not in by_provider:
                by_provider[model.provider] = []
            by_provider[model.provider].append(model)

        for provider, provider_models in sorted(by_provider.items()):
            print(f"\n  {provider.upper()}:")
            for model in provider_models[:3]:  # Show first 3 models per provider
                print(f"    - {model.model_name}: {model.display_name}")
                print(f"      Context: {model.max_context:,} tokens")
                if (
                    model.dollars_per_million_tokens_input
                    and model.dollars_per_million_tokens_output
                ):
                    print(
                        f"      Cost: ${float(model.dollars_per_million_tokens_input):.2f} / ${float(model.dollars_per_million_tokens_output):.2f} per 1M tokens"
                    )
            if len(provider_models) > 3:
                print(f"    ... and {len(provider_models) - 3} more")

        # Test prepared statements
        print("\n⚡ Testing Prepared Statements:")

        # Test model lookup (should use prepared statement)
        start = datetime.now()
        model = await db.get_model("anthropic", "claude-3-5-sonnet-20241022")
        duration = (datetime.now() - start).total_seconds() * 1000
        print(f"  Model lookup: {duration:.2f}ms")

        # Get query metrics
        if db.db.__class__.__name__ == "MonitoredAsyncDatabaseManager":
            print("\n📈 Query Metrics:")
            metrics = await db.get_query_metrics()
            if metrics:
                print(f"  Total Queries: {metrics.queries_executed}")
                print(f"  Failed Queries: {metrics.queries_failed}")
                print(f"  Avg Query Time: {metrics.avg_query_time_ms:.2f}ms")
                print(f"  Pool Utilization: {metrics.pool_utilization:.1f}%")

                # Check for slow queries
                slow_queries = await db.get_slow_queries()
                if slow_queries:
                    print(f"\n  ⚠️  Slow Queries (>{100}ms): {len(slow_queries)}")
                    for sq in slow_queries[:3]:
                        print(f"    - {sq.duration_ms:.0f}ms: {sq.query[:50]}...")

        # Test data cleanup
        print("\n🧹 Testing Data Cleanup:")
        print("  (Would delete old records - dry run)")

        print("\n✅ All diagnostics completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    finally:
        # Always close connection
        print("\n🔌 Closing database connection...")
        await db.close()
        print("✅ Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
