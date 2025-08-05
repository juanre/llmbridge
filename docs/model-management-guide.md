# Model Management Guide

This guide explains how to manage the LLM model database, including extracting model information from provider documentation and keeping the database up to date.

## Overview

The LLM service maintains a database of available models with their capabilities and pricing. This information is managed through a two-step process:

1. **PDF Extraction**: Extract model information from provider documentation PDFs into JSON files
2. **Database Update**: Load the JSON files into the database

All costs are stored as **dollars per million tokens** throughout the system for consistency.

## Step 1: Extracting Model Information from PDFs

### Prerequisites

- OpenAI API key (for LLM-powered extraction)
- Provider documentation PDFs saved in `data/pdfs/`

### Download Provider Documentation

First, get the latest documentation from each provider:

```bash
# Show download instructions
llm-models extract-from-pdfs download-instructions
```

Download PDFs from:
- **Anthropic**: https://docs.anthropic.com/en/docs/about-claude/models
- **Google**: https://ai.google.dev/gemini-api/docs/models
- **OpenAI**: https://openai.com/api/pricing/

Save the PDFs to `data/pdfs/` with these names:
- `anthropic_models.pdf`
- `google_models.pdf`
- `openai_models.pdf`

### Generate JSON Files

Extract model information from the PDFs:

```bash
# Generate JSON files from PDFs
llm-models extract-from-pdfs generate

# This creates/updates:
# - data/models/anthropic.json
# - data/models/google.json
# - data/models/openai.json
```

The extraction process uses GPT-4 to:
- Parse model specifications from tables
- Extract pricing information
- Identify model capabilities
- Generate usage recommendations

### JSON File Structure

The generated JSON files follow this structure:

```json
{
  "provider": "anthropic",
  "last_updated": "2025-06-20",
  "source_documents": ["anthropic_models.pdf"],
  "models": [
    {
      "model_id": "claude-3-5-sonnet-20241022",
      "display_name": "Claude Sonnet 3.5 v2",
      "description": "Fast, versatile model for general tasks",
      "max_context": 200000,
      "max_output_tokens": 8192,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_mode": false,
      "supports_parallel_tool_calls": false,
      "dollars_per_million_tokens_input": 3.00,
      "dollars_per_million_tokens_output": 15.00
    }
  ],
  "model_selection": {
    "general_purpose": {
      "model_id": "claude-3-5-sonnet-20241022",
      "reasoning": "Best balance of speed, cost, and capability"
    },
    "coding": {
      "model_id": "claude-3-5-sonnet-20241022",
      "reasoning": "Excellent code generation and debugging"
    }
  }
}
```

## Step 2: Updating the Database

### Database Setup

Initialize the database (first time only):

```bash
# Setup database schema and run migrations
python scripts/setup_database.py setup

# Check database status
python scripts/setup_database.py status
```

If you need to start fresh:

```bash
# Reset database completely (WARNING: deletes all data)
python scripts/setup_database.py reset
```

### Load Models from JSON

Update the database with model information:

```bash
# Preview changes without applying them
llm-models json-refresh --dry-run

# Apply all changes
llm-models json-refresh

# Update specific providers only
llm-models json-refresh --providers anthropic openai

# Force reload all models (ignores existing data)
llm-models json-refresh --force
```

The refresh process will:
- Add new models not in the database
- Update existing models if information changed
- Mark missing models as inactive (sets `inactive_from` timestamp)
- Create a backup before making changes

### Viewing Models

Check what's in the database:

```bash
# List all active models with pricing
llm-models list

# Show detailed pricing information
llm-models list --pricing

# Export as JSON
llm-models list --format json > current-models.json

# Search for specific models
llm-models search gpt-4

# Get detailed info about a model
llm-models info claude-3-5-sonnet-20241022
```

## Manual JSON Editing

You can manually edit the JSON files to:
- Add new models
- Update pricing
- Fix incorrect information
- Add custom models

After editing, run `llm-models json-refresh` to update the database.

### Adding a New Model

Add to the appropriate provider JSON file:

```json
{
  "model_id": "new-model-name",
  "display_name": "Display Name",
  "description": "Model description",
  "max_context": 128000,
  "max_output_tokens": 4096,
  "supports_vision": false,
  "supports_function_calling": true,
  "supports_json_mode": true,
  "supports_parallel_tool_calls": false,
  "dollars_per_million_tokens_input": 5.00,
  "dollars_per_million_tokens_output": 15.00
}
```

### Updating Pricing

Simply edit the `dollars_per_million_tokens_input` and `dollars_per_million_tokens_output` fields in the JSON file.

## Maintenance Schedule

Recommended update frequency:

- **Weekly**: Run `llm-models json-refresh` to catch any manual JSON updates
- **Monthly**: Download new PDFs and regenerate JSON files
- **As needed**: When providers announce new models or pricing changes

## Backup and Recovery

The system automatically creates backups before each refresh:

```bash
# List available backups
ls -la data/backups/

# Backups are named: refresh_YYYYMMDD_HHMMSS.json

# Restore from a backup (if needed)
llm-models restore-backup refresh_20250620_143022.json
```

## Troubleshooting

### Missing Models

If models are missing from the PDF extraction:
1. Check the PDF contains the information
2. Review the extraction output for errors
3. Manually add missing models to the JSON

### Pricing Issues

If pricing seems incorrect:
1. Verify the PDF has current pricing
2. Check the JSON file values
3. Remember all prices are in dollars per million tokens

### Database Errors

If database operations fail:
1. Check PostgreSQL is running
2. Verify connection settings
3. Run `python scripts/setup_database.py status`
4. Check migration status

## Database Schema

The `llm_models` table stores:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| provider | VARCHAR(50) | Provider name (anthropic, openai, google, ollama) |
| model_name | VARCHAR(100) | Model identifier |
| display_name | VARCHAR(255) | Human-friendly name |
| description | TEXT | Model description |
| max_context | INTEGER | Maximum context window |
| max_output_tokens | INTEGER | Maximum output tokens |
| supports_vision | BOOLEAN | Vision capability |
| supports_function_calling | BOOLEAN | Function/tool calling |
| supports_json_mode | BOOLEAN | Structured JSON output |
| supports_parallel_tool_calls | BOOLEAN | Parallel tool execution |
| tool_call_format | VARCHAR(50) | Tool format (openai, anthropic, etc) |
| dollars_per_million_tokens_input | NUMERIC(12,6) | Input cost per 1M tokens |
| dollars_per_million_tokens_output | NUMERIC(12,6) | Output cost per 1M tokens |
| inactive_from | TIMESTAMP | When model became inactive (NULL = active) |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last update time |

## Best Practices

1. **Always preview changes** with `--dry-run` before applying
2. **Keep JSON files in version control** for history
3. **Document manual changes** in commit messages
4. **Monitor for new models** via provider announcements
5. **Verify pricing** against official documentation
6. **Test after updates** to ensure models work correctly
