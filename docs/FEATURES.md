# Advanced Features

## Model Selection Hints

The service provides intelligent model selection based on use cases:

- **`deepest_model`**: Best for complex reasoning tasks
- **`largest_context`**: For processing long documents
- **`largest_output`**: For generating long content
- **`best_vision`**: For image understanding
- **`cheapest_good`**: Best price/performance ratio

```python
# Get model recommendations
models = await db.list_models()
# Filter by capabilities as needed
vision_models = [m for m in models if m.supports_vision]
```

## PDF and File Handling

The service supports PDF files across providers:

- **Anthropic**: Native PDF support using document content blocks
- **Google**: Native PDF support using inline document data
- **OpenAI**: Automatic routing to Assistants API for PDFs
- **Ollama**: Text-only (no document support)

```python
from llmbridge.file_utils import analyze_file

# Analyze a PDF
content = analyze_file("document.pdf", "Summarize this document")
request = LLMRequest(
    messages=[Message(role="user", content=content)],
    model="claude-3-5-sonnet-20241022"
)
response = await service.chat(request)
```

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