"""
Integration tests for the LLM service with real providers.
"""

import asyncio
import os

import pytest
from llmbridge.schemas import LLMRequest, LLMResponse, Message
from llmbridge.service import LLMBridge


@pytest.mark.llm
@pytest.mark.integration
@pytest.mark.slow
class TestLLMBridgeIntegration:
    """Integration tests for LLMBridge with real providers."""

    @pytest.fixture
    def llmbridge(self):
        """Create LLMBridge without database dependency for now."""
        # Note: In the future, this could be extended to use a test database
        # For now, we'll test the service without DB integration
        return LLMBridge()

    @pytest.mark.asyncio
    async def test_anthropic_provider_integration(self, llmbridge):
        """Test Anthropic provider through LLM service."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not found in environment")

        # Register Anthropic provider
        llmbridge.register_provider("anthropic", api_key=api_key)

        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Say 'Hello from Anthropic'")],
            model="anthropic:claude-3-7-sonnet-20250219",
            max_tokens=20,
        )

        # Send request
        response = await llmbridge.chat(request)

        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert "hello" in response.content.lower()
        assert response.model == "claude-3-7-sonnet-20250219"

    @pytest.mark.asyncio
    async def test_openai_provider_integration(self, llmbridge):
        """Test OpenAI provider through LLM service."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not found in environment")

        # Register OpenAI provider
        llmbridge.register_provider("openai", api_key=api_key)

        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Say 'Hello from OpenAI'")],
            model="openai:gpt-4o-mini",
            max_tokens=20,
        )

        # Send request
        response = await llmbridge.chat(request)

        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert "hello" in response.content.lower()
        assert response.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    @pytest.mark.google
    async def test_google_provider_integration(self, llmbridge):
        """Test Google provider through LLM service."""
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            pytest.skip("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment")

        # Skip if we've been hitting rate limits
        if os.getenv("SKIP_GOOGLE_TESTS"):
            pytest.skip("Skipping Google tests due to rate limits")

        # Register Google provider
        llmbridge.register_provider("google", api_key=api_key)

        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Say 'Hello from Google'")],
            model="google:gemini-1.5-pro",
            max_tokens=20,
        )

        # Send request
        response = await llmbridge.chat(request)

        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert "hello" in response.content.lower()
        assert response.model == "gemini-1.5-pro"

    @pytest.mark.asyncio
    @pytest.mark.ollama
    async def test_ollama_provider_integration(self, llmbridge):
        """Test Ollama provider through LLM service."""
        # Check if Ollama is available
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code != 200:
                    pytest.skip("Ollama not running at localhost:11434")
        except (httpx.ConnectError, httpx.RequestError):
            pytest.skip("Ollama not running at localhost:11434")

        # Register Ollama provider
        llmbridge.register_provider("ollama")

        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Say 'Hello from Ollama'")],
            model="ollama:llama3.2:1b",
            max_tokens=20,
        )

        # Send request
        response = await llmbridge.chat(request)

        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert response.model == "llama3.2:1b"

    @pytest.mark.asyncio
    async def test_provider_switching(self, llmbridge):
        """Test switching between providers."""
        # Try to get at least one API key
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if not anthropic_key and not openai_key:
            pytest.skip("Need at least one API key for testing")

        providers_tested = 0

        if anthropic_key:
            llmbridge.register_provider("anthropic", api_key=anthropic_key)
            request = LLMRequest(
                messages=[Message(role="user", content="Say 'test'")],
                model="anthropic:claude-3-7-sonnet-20250219",
                max_tokens=10,
            )
            response = await llmbridge.chat(request)
            assert isinstance(response, LLMResponse)
            providers_tested += 1

        if openai_key:
            llmbridge.register_provider("openai", api_key=openai_key)
            request = LLMRequest(
                messages=[Message(role="user", content="Say 'test'")],
                model="openai:gpt-4o-mini",
                max_tokens=10,
            )
            response = await llmbridge.chat(request)
            assert isinstance(response, LLMResponse)
            providers_tested += 1

        assert providers_tested >= 1, "At least one provider should have been tested"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, llmbridge):
        """Test handling concurrent requests to same provider."""
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("No API key found for testing")

        if os.getenv("OPENAI_API_KEY"):
            provider = "openai"
            model = "openai:gpt-4o-mini"
            llmbridge.register_provider(provider, api_key=os.getenv("OPENAI_API_KEY"))
        else:
            provider = "anthropic"
            model = "anthropic:claude-3-7-sonnet-20250219"
            llmbridge.register_provider(
                provider, api_key=os.getenv("ANTHROPIC_API_KEY")
            )

        # Create multiple requests
        requests = []
        for i in range(3):
            request = LLMRequest(
                messages=[Message(role="user", content=f"Say exactly 'Response {i}'")],
                model=model,
                max_tokens=10,
            )
            requests.append(llmbridge.chat(request))

        # Execute concurrently
        responses = await asyncio.gather(*requests)

        # Verify all responses
        assert len(responses) == 3
        for i, response in enumerate(responses):
            assert isinstance(response, LLMResponse)
            assert response.content is not None
            assert f"{i}" in response.content or "Response" in response.content

    @pytest.mark.asyncio
    async def test_error_handling_invalid_provider(self, llmbridge):
        """Test error handling for invalid provider."""
        request = LLMRequest(
            messages=[Message(role="user", content="test")], model="invalid:model"
        )

        with pytest.raises(ValueError, match="Provider .* not found"):
            await llmbridge.chat(request)

    @pytest.mark.asyncio
    async def test_error_handling_missing_api_key(self, llmbridge):
        """Test error handling for missing API key."""
        # Use a provider that's definitely not registered
        request = LLMRequest(
            messages=[Message(role="user", content="test")],
            model="definitely_not_a_provider:gpt-4",
        )

        with pytest.raises(ValueError, match="Provider .* not found"):
            await llmbridge.chat(request)
