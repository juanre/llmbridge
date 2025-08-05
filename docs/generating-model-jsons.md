# Generating Model JSON Files

This guide explains how to generate and update the model JSON files that power the LLM service.

## Overview

The system uses JSON files to store curated model information instead of scraping APIs or websites. This provides:
- Reliability (no scraping failures)
- Control (curated model selection)
- Rich metadata (detailed descriptions and use cases)

## Methods to Generate JSONs

### Method 1: Automated PDF Extraction (Recommended)

Extract model information from provider documentation PDFs using Claude.

```bash
# 1. Get download instructions
llm-models extract-from-pdfs download-instructions

# 2. Download PDFs to res/ directory following the instructions
# Files should be named like: YYYY-MM-DD-provider-description.pdf
# Example: 2025-06-16-anthropic-models.pdf

# 3. Ensure API key is set
export ANTHROPIC_API_KEY='your-claude-api-key'

# 4. Run extraction
llm-models extract-from-pdfs generate

# Optional: Extract for specific provider only
llm-models extract-from-pdfs generate --provider anthropic
```

The command will:
1. Read PDFs from `res/` directory
2. Send to Claude for analysis using the LLM service
3. Extract ALL non-obsolete models (not just top 3)
4. Analyze models for use case selection
5. Generate JSON files in `data/models/` with model_selection

### Method 2: Manual Creation

Create or edit JSON files directly in `data/models/`.

#### JSON Structure

```json
{
  "provider": "anthropic",
  "last_updated": "2025-06-16",
  "source_documents": ["2025-06-16-anthropic-models.pdf"],
  "models": [
    {
      "model_id": "claude-opus-4-20250514",
      "display_name": "Claude Opus 4",
      "description": "Most capable model for complex reasoning...",
      "use_cases": [
        "Complex reasoning and analysis",
        "Creative writing and storytelling"
      ],
      "max_context": 200000,
      "max_output_tokens": 4096,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_mode": false,
      "supports_parallel_tool_calls": false,
      "dollars_per_million_tokens_input": 15.00,
      "dollars_per_million_tokens_output": 75.00,
      "release_date": "2025-05-14",
      "deprecation_date": null,
      "notes": "Significant upgrade from Opus 3"
    }
  ]
}
```

### Method 3: Semi-Automated with Claude

If you don't have the PDFs set up for automated extraction:

1. Copy model information from provider websites
2. Create a prompt for Claude:

```
Please extract model information from the following documentation and format it as JSON:

[Paste model documentation here]

Format each model with these fields:
- model_id: exact API identifier
- display_name: human-friendly name
- description: comprehensive description
- use_cases: list of ideal use cases
- max_context: context window in tokens
- dollars_per_million_tokens_input/output: pricing
[etc...]

Return only the JSON array of models.
```

3. Use the response to create/update JSON files

## Updating Models

### When to Update

- New model releases
- Pricing changes
- Model deprecations
- Capability updates

### Update Process

1. **Get Latest Information**
   - Download latest PDFs from provider sites
   - Or copy information from provider documentation

2. **Run Extraction or Edit**
   ```bash
   # Automated extraction
   llm-models extract-from-pdfs generate

   # Or manual edit
   vim data/models/anthropic.json
   ```

3. **Review Changes**
   ```bash
   # Preview what will change
   llm-models json-refresh --dry-run
   ```

4. **Apply Updates**
   ```bash
   # Update database
   llm-models json-refresh
   ```

## Model Selection Criteria

The system now extracts ALL non-obsolete models and selects the best for each use case:

1. **Model Inclusion**: Include all models that are NOT obsolete
2. **Obsolete Detection**: A model is obsolete if:
   - It costs more than a newer model with equal/better capabilities
   - It's explicitly deprecated or marked as legacy
   - There's a direct replacement that's better AND cheaper
3. **Use Case Selection**: Best model per provider for:
   - `deepest_model`: Complex reasoning and intelligence
   - `largest_context`: Maximum context window
   - `largest_output`: Maximum output tokens
   - `best_vision`: Best vision/image capabilities
   - `cheapest_good`: Best price/performance ratio

## Validation

After generating JSONs:

```bash
# Validate JSON syntax
python -m json.tool data/models/anthropic.json

# Check model count
cat data/models/summary.json | jq .

# Test database update
llm-models json-refresh --dry-run
```

## Troubleshooting

### PDF Extraction Issues

If PDF extraction fails:
1. Check PDF is readable: `pdftotext file.pdf`
2. Try different PDF library: `pip install pdfplumber`
3. Convert to text manually and use Method 3

### JSON Validation Errors

Common issues:
- Missing required fields (model_id, pricing)
- Invalid JSON syntax (trailing commas)
- Wrong number types (use 15.00 not "15.00")

### Database Update Failures

- Check database connection
- Verify column names match schema
- Look for duplicate model_ids

## Best Practices

1. **Version Control**: Commit JSON changes with descriptive messages
2. **Documentation**: Update source_documents field
3. **Testing**: Always dry-run before applying
4. **Backup**: Database backs up automatically on refresh
5. **Consistency**: Follow existing naming patterns

## Example Workflow

```bash
# 1. Get download instructions
llm-models extract-from-pdfs download-instructions

# 2. Download latest provider docs as PDFs
# Save to res/2025-06-16-provider-models.pdf

# 3. Extract models
export ANTHROPIC_API_KEY='sk-ant-...'
llm-models extract-from-pdfs generate

# 4. Review generated JSONs
cat data/models/anthropic.json | jq '.models[] | {id: .model_id, cost: .dollars_per_million_tokens_input}'

# 5. Review model selections
cat data/models/anthropic.json | jq '.model_selection'

# 6. Test update
llm-models json-refresh --dry-run

# 7. Apply if looks good
llm-models json-refresh

# 8. Verify
llm-models list
llm-models suggest --all
```
