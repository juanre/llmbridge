# LLM Service API Quick Reference

## Setup
```python
from llm.api import LLMBridgeAPI
from llm.db import LLMDatabase

db = LLMDatabase(connection_string)
await db.initialize()
api = LLMBridgeAPI(db)
```

## Model Discovery
```python
# List all models
models = await api.list_models()

# List by provider
openai_models = await api.list_models(provider="openai")

# Include inactive models
all_models = await api.list_models(active_only=False)

# Sort by cost
cheap_models = await api.list_models(sort_by="cost", sort_order="asc")

# Get specific model
model = await api.get_model("openai", "gpt-4o")

# Get provider info
providers = await api.get_providers()
```

## Cost Calculations
```python
# Calculate cost with breakdown
breakdown = await api.calculate_cost(
    "openai", "gpt-4o",
    input_tokens=1000,
    output_tokens=500
)

# Just get total cost
total = await api.calculate_cost(
    "openai", "gpt-4o", 1000, 500,
    include_breakdown=False
)

# Compare costs across models
comparisons = await api.compare_model_costs(
    input_tokens=10000,
    output_tokens=2000
)

# Estimate conversation cost
estimate = await api.estimate_cost_for_conversation(
    "anthropic", "claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}],
    expected_output_tokens=100
)
```

## Model Filtering
```python
# By features
vision_models = await api.find_models_by_features(
    vision=True,
    function_calling=True
)

# By cost range
budget_models = await api.find_models_by_cost_range(
    max_input_cost_per_million=5.0,
    max_output_cost_per_million=15.0
)

# By context size
large_context = await api.find_models_by_context_size(
    min_context=100000
)

# Text search
results = await api.search_models("gpt")

# By requirements
from llm.api.types import ModelRequirements

reqs = ModelRequirements(
    min_context_size=50000,
    requires_vision=True,
    max_input_cost_per_million=20.0
)
compatible = await api.find_compatible_models(reqs)
```

## Model Management
```python
# Activate/deactivate
await api.activate_model("openai", "gpt-4")
await api.deactivate_model("openai", "gpt-3.5-turbo")

# Bulk updates
updates = [
    ("openai", "gpt-4", True),      # activate
    ("anthropic", "claude-2", False) # deactivate
]
results = await api.bulk_update_model_status(updates)

# Activate all from provider
count = await api.activate_all_models("openai")
```

## Model Validation
```python
# Validate model exists and is active
result = await api.validate_model_request("openai", "gpt-4o")

# Validate with requirements
result = await api.validate_model_request(
    "openai", "gpt-4o",
    requirements=reqs
)

# Get alternatives
alternatives = await api.suggest_alternative_models(
    "anthropic", "claude-3-opus-20240229"
)

# Get recommendations for use case
recommendations = await api.get_model_recommendations(
    use_case="code_generation",
    budget_per_million_tokens=10.0
)
```

## Statistics & Health
```python
# Model statistics
stats = await api.get_model_statistics()
print(f"Total: {stats.total_models}, Active: {stats.active_models}")

# Provider statistics
provider_stats = await api.get_provider_summary("openai")

# Cost statistics
cost_stats = await api.get_cost_statistics()

# Service health
health = await api.get_service_health()

# Data integrity check
integrity = await api.verify_model_data_integrity()
```

## Utility Methods
```python
# Get model families
families = await api.get_model_families()  # {"gpt": [...], "claude": [...]}

# Normalize model name
normalized = await api.normalize_model_name("openai", "gpt4")  # -> "gpt-4"

# Estimate tokens
tokens = await api.estimate_tokens("Hello world", "openai", "gpt-4")
```

## Common Patterns

### Finding Best Model for Budget
```python
models = await api.find_models_by_cost_range(
    max_input_cost_per_million=10.0
)
# Filter by features you need
with_vision = [m for m in models if m.supports_vision]
# Sort by context size
with_vision.sort(key=lambda m: m.max_context_tokens or 0, reverse=True)
best = with_vision[0] if with_vision else None
```

### Checking Model Availability
```python
async def ensure_model_available(provider: str, model_name: str):
    model = await api.get_model(provider, model_name)
    if not model:
        return f"Model {provider}:{model_name} not found"
    if not model.is_active:
        return f"Model {provider}:{model_name} is inactive"
    return None  # Model is available
```

### Cost-Aware Model Selection
```python
async def select_model_for_budget(
    max_cost_per_1k_tokens: float,
    min_context: int = 0
):
    # Convert to per-million for API
    max_per_million = max_cost_per_1k_tokens * 1000

    models = await api.find_models_by_cost_range(
        max_input_cost_per_million=max_per_million
    )

    # Filter by context
    suitable = [
        m for m in models
        if m.max_context_tokens and m.max_context_tokens >= min_context
    ]

    # Sort by capabilities (prefer more features)
    suitable.sort(
        key=lambda m: sum([
            m.supports_vision,
            m.supports_function_calling,
            m.supports_json_mode
        ]),
        reverse=True
    )

    return suitable[0] if suitable else None
```
