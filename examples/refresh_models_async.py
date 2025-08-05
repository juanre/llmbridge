#!/usr/bin/env python3
"""Async model refresh tool for LLM service."""

import argparse
import asyncio
import logging
import sys
from typing import Any, Dict, List

from llmbridge.db import LLMDatabase
from llmbridge.model_refresh.async_refresh_manager import AsyncModelRefreshManager
from llmbridge.pricing import (
    AnthropicPricingScraper,
    GooglePricingScraper,
    OpenAIPricingScraper,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def scrape_models(providers: List[str]) -> List[Dict[str, Any]]:
    """Scrape model information from providers."""
    all_models = []

    scrapers = {
        "anthropic": AnthropicPricingScraper(),
        "openai": OpenAIPricingScraper(),
        "google": GooglePricingScraper(),
    }

    for provider in providers:
        if provider not in scrapers:
            logger.warning(f"Unknown provider: {provider}")
            continue

        logger.info(f"Scraping {provider} models...")
        try:
            scraper = scrapers[provider]
            models = scraper.scrape()
            all_models.extend(models)
            logger.info(f"Found {len(models)} {provider} models")
        except Exception as e:
            logger.error(f"Failed to scrape {provider}: {e}")

    return all_models


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Refresh LLM models in database")
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=["anthropic", "openai", "google", "all"],
        default=["all"],
        help="Providers to refresh",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying them"
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Skip creating backup before refresh"
    )
    parser.add_argument(
        "--skip-costs", action="store_true", help="Skip updating cost information"
    )
    parser.add_argument(
        "--rollback", metavar="SNAPSHOT", help="Rollback to a specific snapshot"
    )
    parser.add_argument(
        "--db-url",
        help="Database connection URL",
        default="postgresql://postgres:postgres@localhost/postgres",
    )

    args = parser.parse_args()

    # Initialize database
    db = LLMDatabase(
        connection_string=args.db_url,
        enable_monitoring=True,
        min_connections=5,
        max_connections=10,
    )

    try:
        await db.initialize()
        logger.info("Database connected")

        # Create refresh manager
        manager = AsyncModelRefreshManager(
            db=db, backup_enabled=not args.no_backup, dry_run=args.dry_run
        )

        if args.rollback:
            # Perform rollback
            logger.info(f"Rolling back to snapshot: {args.rollback}")
            success = await manager.rollback_to_snapshot(args.rollback)
            return 0 if success else 1

        # Determine providers
        providers = args.providers
        if "all" in providers:
            providers = ["anthropic", "openai", "google"]

        # Scrape models
        logger.info(f"Scraping models from: {', '.join(providers)}")
        scraped_models = await scrape_models(providers)

        if not scraped_models:
            logger.error("No models scraped")
            return 1

        logger.info(f"Total scraped models: {len(scraped_models)}")

        if args.dry_run:
            # Show preview
            logger.info("Running in dry-run mode - preview only")
            preview = await manager.get_refresh_preview(
                scraped_models, skip_cost_update=args.skip_costs
            )

            print("\n=== REFRESH PREVIEW ===")
            print(f"Current models in DB: {preview['current_model_count']}")
            print(f"Scraped models: {preview['scraped_model_count']}")
            print("\nChanges:")
            print(f"  New models: {preview['changes']['new']}")
            print(f"  Updated models: {preview['changes']['updated']}")
            print(f"  Deactivated models: {preview['changes']['deactivated']}")

            if preview["new_models"]:
                print("\nNew models (first 10):")
                for model in preview["new_models"]:
                    if "..." in model:
                        print(f"  {model['...']}")
                    else:
                        print(
                            f"  - {model['provider']}/{model['model']}: {model['display_name']}"
                        )

            if preview["updated_models"]:
                print("\nUpdated models (first 10):")
                for model in preview["updated_models"]:
                    if "..." in model:
                        print(f"  {model['...']}")
                    else:
                        print(
                            f"  - {model['provider']}/{model['model']}: {', '.join(model['changes'])}"
                        )

            if preview["deactivated_models"]:
                print("\nDeactivated models (first 10):")
                for model in preview["deactivated_models"]:
                    if "..." in model:
                        print(f"  {model['...']}")
                    else:
                        print(
                            f"  - {model['provider']}/{model['model']}: {model['reason']}"
                        )
        else:
            # Perform actual refresh
            logger.info("Starting model refresh...")
            summary = await manager.refresh_models(
                scraped_models, skip_cost_update=args.skip_costs
            )

            print("\n=== REFRESH COMPLETE ===")
            print(f"Duration: {summary.duration_seconds:.2f} seconds")
            print(f"Models before: {summary.models_before}")
            print(f"Models after: {summary.models_after}")
            print("\nChanges applied:")
            print(f"  Added: {summary.result.added_count}")
            print(f"  Updated: {summary.result.updated_count}")
            print(f"  Deactivated: {summary.result.deactivated_count}")

            if summary.result.errors:
                print(f"\nErrors encountered: {len(summary.result.errors)}")
                for error in summary.result.errors[:5]:
                    print(f"  - {error}")
                if len(summary.result.errors) > 5:
                    print(f"  ... and {len(summary.result.errors) - 5} more")

        # Show pool stats
        pool_stats = await db.get_pool_stats()
        print(f"\nConnection pool stats: {pool_stats}")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        await db.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
