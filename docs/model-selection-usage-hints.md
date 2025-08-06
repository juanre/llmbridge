# Model Selection and Usage Hints

This document describes the model selection and usage hints system that helps users and applications choose the right LLM model for their specific use cases.

## Overview

The LLM service now includes intelligent model selection based on five key use cases:

1. **`deepest_model`** - Best for complex reasoning and intelligence tasks
2. **`largest_context`** - Model with the largest context window for processing long documents
3. **`largest_output`** - Model with the largest output capacity (crucial for PDF-to-markdown, long generation)
4. **`best_vision`** - Best model for image understanding and vision tasks
5. **`cheapest_good`** - Best price/performance ratio (not just the cheapest)

## Architecture

### JSON Structure

Each provider JSON file (`data/models/{provider}.json`) contains:

```json
{
  "provider": "anthropic",
  "last_updated": "2025-06-17",
  "source_documents": ["..."],
  "models": [
    // All non-obsolete models from the provider
  ],
  "model_selection": {
    "deepest_model": {
      "model_id": "claude-opus-4-20250514",
      "reasoning": "Why this model was selected"
    },
    "largest_context": { ... },
    "largest_output": { ... },
    "best_vision": { ... },
    "cheapest_good": { ... }
  }
}
```

### Database Schema

The usage hints are stored in the `model_usage_hints` table with SQL functions for querying:

- `get_model_for_use_case(provider, use_case)` - Get best model for a use case from a specific provider
- `get_all_models_for_use_case(use_case)` - Get best models across all providers
- `get_provider_usage_hints(provider)` - Get all usage hints for a provider

## Generating Model JSONs

### Prerequisites

1. Download documentation PDFs from provider websites:
   - Anthropic: pricing page and models overview
   - OpenAI: models comparison and pricing
   - Google: models documentation and pricing

2. Save PDFs in `res/` directory with naming convention:
   - `YYYY-MM-DD-{provider}-models.pdf`
   - `YYYY-MM-DD-{provider}-pricing.pdf`

### Running the Generator

```bash
# Step 1: Get download instructions
llm-models extract-from-pdfs download-instructions

# Step 2: Generate model JSONs with usage hints
llm-models extract-from-pdfs generate

# Optional: Generate for specific provider only
llm-models extract-from-pdfs generate --provider anthropic

# The command will:
# 1. Extract all non-obsolete models from PDFs
# 2. Analyze models for each use case
# 3. Generate provider JSONs with model_selection
```

### How It Works

1. **Model Extraction**: The script uses Anthropic API to read PDFs and extract model information
2. **Obsolete Detection**: Models are considered obsolete if:
   - They cost more than newer models with equal/better capabilities
   - They're explicitly deprecated
   - There's a direct replacement that's better AND cheaper
3. **Use Case Selection**: For each use case, the best model is selected based on:
   - Capabilities (context, output, vision support)
   - Performance characteristics
   - Cost-effectiveness
   - Intended use patterns

## Using Model Selection

### CLI Commands

```bash
# Show all usage hints
llm-models suggest --all

# Show hints for specific provider
llm-models suggest --all --provider anthropic

# Get best model for specific use case
llm-models suggest largest_output

# Get best model for use case from specific provider
llm-models suggest deepest_model --provider google
```

### Programmatic Access

```python
from llmbridge.model_refresh.json_model_loader import JSONModelLoader

# Load usage hints
loader = JSONModelLoader("data/models")
hints = loader.load_provider_usage_hints("anthropic")

# Get best model for a use case
best_model = hints["largest_output"]["model_id"]
reasoning = hints["largest_output"]["reasoning"]
```

### Integration with LLM Service

```python
# Example: Select model based on use case
selector = ModelSelector()
models = selector.get_best_model("largest_output")

# Use with LLM service
model_id = models["google"]["model_id"]
response = await llmbridge.chat(
    model=f"google:{model_id}",
    messages=[...]
)
```

## Use Case Examples

### 1. PDF to Markdown Conversion
**Need**: Large output capacity to avoid truncation

Best models:
- Google: `gemini-2.5-pro-preview-06-05` (65,536 tokens)
- Anthropic: `claude-sonnet-4-20250514` (64,000 tokens)
- OpenAI: `gpt-4.1` (16,384 tokens)

### 2. Complex Reasoning Tasks
**Need**: Maximum intelligence and reasoning capability

Best models:
- Anthropic: `claude-opus-4-20250514`
- OpenAI: `o3-pro`
- Google: `gemini-2.5-pro-preview-06-05`

### 3. Budget-Conscious Applications
**Need**: Good quality at lowest cost

Best models:
- Google: `gemini-1.5-flash` ($0.075/$0.30 per 1M tokens)
- OpenAI: `gpt-4o-mini` ($0.15/$0.60 per 1M tokens)
- Anthropic: `claude-3-5-haiku-20241022` ($0.80/$4.00 per 1M tokens)

### 4. Large Document Processing
**Need**: Maximum context window

Best models:
- Google: `gemini-1.5-pro` (2,097,152 tokens)
- Anthropic: All models (200,000 tokens)
- OpenAI: All models (128,000 tokens)

## Workflow

1. **Download PDFs**: Follow instructions from `llm-models extract-from-pdfs download-instructions`
2. **Generate JSONs**: Run `llm-models extract-from-pdfs generate` to update models
3. **Load to Database**: Use `llm-models json-refresh` to update database
4. **Query Usage Hints**: Use CLI or programmatic access to get recommendations
5. **Use in Applications**: Select models based on specific needs

## Benefits

- **Provider Flexibility**: If locked to one provider, still get the best model for that provider
- **Use Case Driven**: Models selected based on actual needs, not arbitrary choices
- **Cost Optimization**: Balance between capabilities and cost
- **Future Proof**: As new models are released, just regenerate JSONs
- **Transparent Reasoning**: Each selection includes explanation

## Maintenance

- Run `llm-models extract-from-pdfs generate` monthly or when new models are announced
- Review generated selections for accuracy
- Update use case definitions if new categories emerge
- Monitor model performance in production use
