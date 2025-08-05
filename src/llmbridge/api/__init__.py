"""LLM Service API module.

This module provides a complete API for interacting with LLM models without
exposing any internal database schema or implementation details.
"""

from llmbridge.api.service import LLMBridgeAPI
from llmbridge.api.types import (CostBreakdown, ModelInfo, ModelRequirements,
                                   ModelStatistics, ProviderInfo,
                                   ProviderStats, RefreshResult, ServiceHealth,
                                   ValidationResult)

__all__ = [
    # Types
    "ModelInfo",
    "ProviderInfo",
    "ProviderStats",
    "ModelStatistics",
    "CostBreakdown",
    "ModelRequirements",
    "RefreshResult",
    "ValidationResult",
    "ServiceHealth",
    # Service
    "LLMBridgeAPI",
]
