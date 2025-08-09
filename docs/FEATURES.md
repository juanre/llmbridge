# Advanced Features

## Model Selection Hints

The service provides intelligent model selection based on use cases:

- **`deepest_model`**: Best for complex reasoning tasks
- **`largest_context`**: For processing long documents
- **`largest_output`**: For generating long content
- **`best_vision`**: For image understanding
- **`cheapest_good`**: Best price/performance ratio

```python
# Get usage-hint recommendations per provider via SQL helper views/functions
# Example: use the view materialized by migrations
rows = await db.db.fetch_all("SELECT * FROM {{tables.llm_models}}")

# Or use API layer to filter
from llmbridge.api.service import LLMBridgeAPI
api = LLMBridgeAPI(db)
vision_models = [m for m in await api.list_models() if m.supports_vision]
```

## File handling

Providers accept text and multimodal content via their official SDKs. For PDFs or images, convert to supported input formats (base64 inline blobs or URLs) using the `Message.content` list structure shown in provider docs/code.

## Function Calling

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
}]

request = LLMRequest(
    messages=[Message(role="user", content="What's the weather in Paris?")],
    model="gpt-4o",
    tools=tools
)

response = await service.chat(request)
if response.tool_calls:
    # Handle function calls
    for tool_call in response.tool_calls:
        print(f"Calling {tool_call['function']['name']}")
```

## Response Formats

```python
# JSON mode
request = LLMRequest(
    messages=[Message(role="user", content="List 3 colors")],
    model="gpt-4o",
    response_format={"type": "json_object"}
)

# Structured output (OpenAI)
schema = {
    "type": "object",
    "properties": {
        "colors": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

request = LLMRequest(
    messages=[Message(role="user", content="List 3 colors")],
    model="gpt-4o",
    response_format={"type": "json_object", "schema": schema}
)
```