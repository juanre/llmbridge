# Bug Report: LLMBridgeSQLite passes unsupported parameters to providers

## Description

`LLMBridgeSQLite.chat()` passes all `LLMRequest` fields to the underlying provider's `chat()` method, including optional fields that are `None`. This causes a `TypeError` when providers don't accept these parameters, specifically the `json_response` field.

## Environment

- **LLMBridge version**: 0.1.0
- **Python version**: 3.13
- **OS**: macOS (Darwin 24.5.0)
- **Provider**: AnthropicProvider (but likely affects others)
- **API Keys configured**: OPENAI_API_KEY, ANTHROPIC_API_KEY

## Steps to Reproduce

1. Install LLMBridge with SQLite support
2. Set up API keys for Anthropic or OpenAI
3. Run this minimal reproduction script:

```python
#!/usr/bin/env python3
import asyncio
from llmbridge import LLMRequest, Message
from llmbridge.service_sqlite import LLMBridgeSQLite

async def reproduce_bug():
    # Initialize with SQLite
    service = LLMBridgeSQLite(db_path="test.db")
    
    # Create a simple request
    request = LLMRequest(
        messages=[
            Message(role="user", content="Say hello")
        ],
        model="claude-3-haiku-20240307",  # or "gpt-4o-mini"
        temperature=0.1,
        max_tokens=100
    )
    
    # This will fail with TypeError
    response = await service.chat(request)
    print(response.content)

asyncio.run(reproduce_bug())
```

## Expected Behavior

The request should be processed successfully, with the LLM returning a response.

## Actual Behavior

The request fails with the following error:

```
TypeError: AnthropicProvider.chat() got an unexpected keyword argument 'json_response'
```

Full traceback:
```
Traceback (most recent call last):
  File "test.py", line 23, in <module>
    asyncio.run(reproduce_bug())
  File ".../asyncio/runners.py", line 195, in run
    return runner.run(main)
  File ".../asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
  File ".../asyncio/base_events.py", line 719, in run_until_complete
    return future.result()
  File "test.py", line 20, in reproduce_bug
    response = await service.chat(request)
  File ".../llmbridge/service_sqlite.py", line 181, in chat
    response = await provider.chat(
        messages=request.messages,
        model=model_name,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        response_format=request.response_format,
        tools=request.tools,
        tool_choice=request.tool_choice,
        json_response=request.json_response,
    )
TypeError: AnthropicProvider.chat() got an unexpected keyword argument 'json_response'
```

## Root Cause Analysis

The issue is in `service_sqlite.py` around line 175-181 where `LLMBridgeSQLite.chat()` passes all fields from the `LLMRequest` to the provider:

```python
response = await provider.chat(
    messages=request.messages,
    model=model_name,
    temperature=request.temperature,
    max_tokens=request.max_tokens,
    response_format=request.response_format,
    tools=request.tools,
    tool_choice=request.tool_choice,
    json_response=request.json_response,  # <-- This is the problem
)
```

The `LLMRequest` schema defines `json_response` as an optional field (defaults to `None`):
```python
class LLMRequest(BaseModel):
    # ...
    json_response: Optional[bool] = None
```

However, the provider's `chat()` method doesn't accept a `json_response` parameter, causing the TypeError when it's passed even as `None`.

## Suggested Fix

### Option 1: Only pass non-None values

```python
# In service_sqlite.py, build kwargs dynamically
kwargs = {
    'messages': request.messages,
    'model': model_name,
}

# Only add optional fields if they're not None
if request.temperature is not None:
    kwargs['temperature'] = request.temperature
if request.max_tokens is not None:
    kwargs['max_tokens'] = request.max_tokens
if request.response_format is not None:
    kwargs['response_format'] = request.response_format
if request.tools is not None:
    kwargs['tools'] = request.tools
if request.tool_choice is not None:
    kwargs['tool_choice'] = request.tool_choice
if request.json_response is not None:
    kwargs['json_response'] = request.json_response

response = await provider.chat(**kwargs)
```

### Option 2: Update providers to accept and ignore extra kwargs

```python
# In providers/anthropic_api.py
async def chat(self, messages, model=None, **kwargs):
    # Extract known parameters
    temperature = kwargs.get('temperature')
    max_tokens = kwargs.get('max_tokens')
    # Ignore unknown parameters like json_response
    # ...
```

### Option 3: Use a compatibility mapping

```python
# Define which fields each provider supports
PROVIDER_FIELDS = {
    'anthropic': ['messages', 'model', 'temperature', 'max_tokens', 'tools', ...],
    'openai': ['messages', 'model', 'temperature', 'max_tokens', 'response_format', ...],
    # ...
}

# Only pass supported fields
provider_type = self._get_provider_type(model)
supported_fields = PROVIDER_FIELDS.get(provider_type, [])
kwargs = {
    field: getattr(request, field) 
    for field in supported_fields 
    if hasattr(request, field) and getattr(request, field) is not None
}
response = await provider.chat(**kwargs)
```

## Workaround

Until fixed, users can work around this by:

1. Using the main `LLMBridge` class without SQLite logging:
```python
from llmbridge import LLMBridge
service = LLMBridge(enable_db_logging=False)
```

2. Or avoiding fields that cause issues in `LLMRequest`

## Impact

This bug prevents users from using `LLMBridgeSQLite` with any provider that doesn't accept all the optional fields defined in `LLMRequest`. Since `LLMBridgeSQLite` is the recommended approach for local development and testing, this significantly impacts the developer experience.

## Additional Notes

- The same issue likely exists in the main `service.py` file around line 230
- The bug also triggers a secondary error when trying to log the failure, as seen in the error logs:
  ```
  Failed to log API error: 1 validation error for CallRecord
  called_at
    Field required [type=missing, input_value={'id': UUID('...')}, input_type=dict]
  ```

This secondary issue suggests the error logging mechanism also needs attention.

## Proposed Test Case

```python
async def test_optional_fields_not_passed_as_none():
    """Test that None values in LLMRequest don't cause errors."""
    service = LLMBridgeSQLite(db_path=":memory:")
    
    # Request with minimal fields (others default to None)
    request = LLMRequest(
        messages=[Message(role="user", content="test")],
        model="claude-3-haiku-20240307"
    )
    
    # Should not raise TypeError
    response = await service.chat(request)
    assert response is not None
```

Please let me know if you need any additional information to reproduce or fix this issue.