# PDF and Non-Image File Handling in LLM Service

## Current State

The LLM service now supports PDF files and other document types across multiple providers:

- **Anthropic Claude**: Native PDF support using document content blocks
- **Google Gemini**: Native PDF support using inline document data
- **OpenAI GPT**: PDF support via Assistants API (automatically handled)
- **Ollama**: Text-only (no document support)

PDF files are automatically routed to the appropriate API for each provider, providing a seamless experience.

## How It Works

### Universal File Interface

All providers use a standardized document content format:

```python
{
    "type": "document",
    "source": {
        "type": "base64",
        "media_type": "application/pdf",
        "data": "JVBERi0xLjQ..."  # base64 encoded PDF
    }
}
```

### Provider-Specific Implementation

#### OpenAI (Automatic Assistants API Integration)

When PDF content is detected, the OpenAI provider automatically:

1. **Uploads** the PDF to OpenAI's Files API
2. **Creates** a temporary assistant with file search capabilities
3. **Processes** the document using the Assistants API
4. **Extracts** the response and formats it consistently
5. **Cleans up** uploaded files, assistants, and threads

This happens transparently - users don't need to change their code.

**Limitations with PDF processing:**
- Tools and custom response formats are not supported
- Uses estimated token counts (Assistants API doesn't provide exact counts)

#### Anthropic Claude

Direct native support using the universal document format:

```python
# Document content is passed directly to Claude
content = [
    {"type": "text", "text": "Analyze this PDF"},
    {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": "JVBERi0xLjQ..."
        }
    }
]
```

#### Google Gemini

Converts universal format to Google's inline data format:

```python
# Automatically converted to:
types.Part(
    inline_data=types.Blob(
        mime_type="application/pdf",
        data=decoded_pdf_bytes
    )
)
```

## Usage Examples

### Simple PDF Analysis

```python
from llm.file_utils import analyze_file
from llm.providers.openai_api import OpenAIProvider

# Works the same across all providers
content = analyze_file("document.pdf", "Extract key information")

# OpenAI will automatically use Assistants API
provider = OpenAIProvider()
response = await provider.chat(
    messages=[Message(role="user", content=content)],
    model="gpt-4o"
)
```

### Using the Service Layer

```python
from llm.service import LLMBridge
from llm.schemas import LLMRequest, Message
from llm.file_utils import analyze_file

service = LLMBridge()

# Universal file interface works with any provider
content = analyze_file("report.pdf", "Summarize this report")

request = LLMRequest(
    messages=[Message(role="user", content=content)],
    model="gpt-4o",  # or "claude-3-5-sonnet", "gemini-1.5-pro"
)

response = await service.chat(request)
```

## Migration from Previous Implementation

No code changes required! The implementation:

- **Maintains backward compatibility** with existing image processing
- **Adds transparent PDF support** for OpenAI
- **Preserves existing behavior** for other providers
- **Provides consistent interface** across all providers

Previous error messages directing users to use other providers are no longer needed - OpenAI now handles PDFs automatically.
