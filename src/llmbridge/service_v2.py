"""
LLM service that manages providers and routes requests with database backend abstraction.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from llmbridge.api import LLMBridgeAPI
from llmbridge.base import BaseLLMProvider
from llmbridge.db_v2 import LLMDatabase
from llmbridge.providers.anthropic_api import AnthropicProvider
from llmbridge.providers.google_api import GoogleProvider
from llmbridge.providers.ollama_api import OllamaProvider
from llmbridge.providers.openai_api import OpenAIProvider
from llmbridge.schemas import LLMRequest, LLMResponse

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class LLMBridge:
    """LLM service that manages providers and routes requests."""

    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        origin: str = "llmbridge",
        enable_db_logging: bool = True,
        use_sqlite: Optional[bool] = None,
    ):
        """
        Initialize the LLM service.

        Args:
            db_connection_string: Database connection string.
                - PostgreSQL: "postgresql://user:pass@host/db"
                - SQLite: "sqlite:///path/to/db.db" or just "path/to/db.db"
                - None: Uses SQLite with default "llmbridge.db"
            origin: Origin identifier for database logging
            enable_db_logging: Whether to enable database logging
            use_sqlite: Force SQLite usage (deprecated, use connection string instead)
        """
        self.origin = origin
        self.enable_db_logging = enable_db_logging
        self._db_initialized = False

        # Initialize database if enabled
        if enable_db_logging:
            # Handle backward compatibility with use_sqlite parameter
            if use_sqlite is True and db_connection_string is None:
                db_connection_string = "llmbridge.db"
            elif use_sqlite is False and db_connection_string is None:
                # Use PostgreSQL with default settings
                db_connection_string = os.getenv(
                    "DATABASE_URL",
                    "postgresql://postgres:postgres@localhost/postgres"
                )
            
            self.db = LLMDatabase(connection_string=db_connection_string)
            self.api = None  # Will be initialized after db is initialized
        else:
            self.db = None
            self.api = None

        self.providers: Dict[str, BaseLLMProvider] = {}
        self._model_cache: Dict[str, Dict[str, Any]] = {}
        self._initialize_providers()

    async def _ensure_db_initialized(self):
        """Ensure database is initialized (async operation)."""
        if self.enable_db_logging and self.db and not self._db_initialized:
            try:
                logger.info("Initializing LLM service database connection")
                await self.db.initialize()
                logger.debug("Database connection established")

                self._db_initialized = True

                # Initialize API after database is ready
                self.api = LLMBridgeAPI(self.db)

                logger.info("LLM service database initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}", exc_info=True)
                logger.warning("Database logging will be disabled")
                self.db = None
                self.enable_db_logging = False

    def _initialize_providers(self):
        """Initialize all configured providers from environment variables."""
        logger.info("Initializing LLM providers")

        # OpenAI
        if openai_key := os.getenv("OPENAI_API_KEY"):
            try:
                self.providers["openai"] = OpenAIProvider(api_key=openai_key)
                logger.info("OpenAI provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider: {e}")

        # Anthropic
        if anthropic_key := os.getenv("ANTHROPIC_API_KEY"):
            try:
                self.providers["anthropic"] = AnthropicProvider(api_key=anthropic_key)
                logger.info("Anthropic provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic provider: {e}")

        # Google/Gemini
        if google_key := os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
            try:
                self.providers["google"] = GoogleProvider(api_key=google_key)
                logger.info("Google provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Google provider: {e}")

        # Ollama (local)
        if os.getenv("OLLAMA_API_BASE") or os.getenv("ENABLE_OLLAMA", "false").lower() == "true":
            try:
                self.providers["ollama"] = OllamaProvider()
                logger.info("Ollama provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama provider: {e}")

        logger.info(f"Initialized {len(self.providers)} providers")

    def register_provider(self, name: str, provider: Optional[BaseLLMProvider] = None, **kwargs):
        """
        Register a provider instance.

        Args:
            name: Provider name (e.g., 'openai', 'anthropic')
            provider: Provider instance (if None, will create based on name)
            **kwargs: Additional arguments for provider initialization
        """
        if provider:
            self.providers[name] = provider
        else:
            # Create provider based on name
            if name == "openai":
                self.providers[name] = OpenAIProvider(**kwargs)
            elif name == "anthropic":
                self.providers[name] = AnthropicProvider(**kwargs)
            elif name == "google":
                self.providers[name] = GoogleProvider(**kwargs)
            elif name == "ollama":
                self.providers[name] = OllamaProvider(**kwargs)
            else:
                raise ValueError(f"Unknown provider: {name}")

        logger.info(f"Registered provider: {name}")

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models for each provider."""
        result = {}
        for name, provider in self.providers.items():
            result[name] = provider.get_supported_models()
        return result

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """
        Route chat request to appropriate provider.

        Args:
            request: LLM request with messages and parameters

        Returns:
            LLM response from the provider
        """
        # Ensure database is initialized
        await self._ensure_db_initialized()

        start_time = time.time()

        # Extract provider from model name (e.g., "openai:gpt-4" -> "openai")
        if ":" in request.model:
            provider_name, model_name = request.model.split(":", 1)
        else:
            # Try to determine provider from model name
            provider_name = self._determine_provider(request.model)
            model_name = request.model

        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not available")

        provider = self.providers[provider_name]

        # Log the request start
        logger.info(f"Routing request to {provider_name} with model {model_name}")

        try:
            # Call the provider
            response = await provider.chat(
                messages=request.messages,
                model=model_name,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=request.tools,
                tool_choice=request.tool_choice,
                response_format=request.response_format,
                json_response=request.json_response,
            )

            # Log to database if enabled
            if self.enable_db_logging and self.db:
                try:
                    from decimal import Decimal
                    from uuid import uuid4
                    from llmbridge.schemas import CallRecord

                    # Calculate cost if we have pricing info
                    cost = None
                    if response.usage and self.api:
                        model_info = await self.api.get_model(provider_name, model_name)
                        if model_info:
                            cost = self.api.calculate_cost(
                                model_info,
                                response.usage.get("prompt_tokens", 0),
                                response.usage.get("completion_tokens", 0),
                            )

                    record = CallRecord(
                        id=uuid4(),
                        provider=provider_name,
                        model=model_name,
                        origin=self.origin,
                        prompt_tokens=response.usage.get("prompt_tokens") if response.usage else None,
                        completion_tokens=response.usage.get("completion_tokens") if response.usage else None,
                        total_tokens=response.usage.get("total_tokens") if response.usage else None,
                        cost=Decimal(str(cost)) if cost else None,
                        error=None,
                    )
                    await self.db.record_api_call(record)
                except Exception as e:
                    logger.error(f"Failed to log API call: {e}")

            elapsed = time.time() - start_time
            logger.info(f"Request completed in {elapsed:.2f}s")

            return response

        except Exception as e:
            # Log error to database if enabled
            if self.enable_db_logging and self.db:
                try:
                    from uuid import uuid4
                    from llmbridge.schemas import CallRecord

                    record = CallRecord(
                        id=uuid4(),
                        provider=provider_name,
                        model=model_name,
                        origin=self.origin,
                        error=str(e),
                    )
                    await self.db.record_api_call(record)
                except Exception as log_error:
                    logger.error(f"Failed to log API error: {log_error}")

            logger.error(f"Request failed: {e}")
            raise

    def _determine_provider(self, model: str) -> str:
        """Determine provider from model name."""
        # Common model prefixes
        if model.startswith(("gpt-", "o1-")):
            return "openai"
        elif model.startswith("claude-"):
            return "anthropic"
        elif model.startswith(("gemini-", "models/")):
            return "google"
        elif model.startswith(("llama", "mistral", "qwen")):
            return "ollama"

        # Check which providers support this model
        for name, provider in self.providers.items():
            if provider.validate_model(model):
                return name

        raise ValueError(f"No provider found for model: {model}")

    async def close(self):
        """Close database connections."""
        if self.db:
            await self.db.close()