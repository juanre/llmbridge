# LLMBridge Setup Guide - Complete Implementation

## 📋 Overview

This guide walks through setting up a module to use llmbridge, from initial configuration to production deployment. It covers environment setup, database initialization, model population, and common usage patterns.

---

## 🚀 Step 1: Installation

```bash
# Using uv (recommended)
uv add llmbridge

# Or using pip
pip install llmbridge

# For development with all extras
pip install "llmbridge[dev,pdf]"
```

---

## 🔧 Step 2: Environment Configuration

Create a `.env` file in your project root:

```bash
# .env

# === LLM Provider API Keys ===
# At least one provider is recommended
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxx
# GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxx  # Alternative to GOOGLE_API_KEY

# Ollama runs locally, no API key needed
# But ensure Ollama is installed and running: https://ollama.ai

# === Database Configuration ===
# Option 1: Connection string (takes precedence)
DATABASE_URL=postgresql://user:password@localhost:5432/myapp

# Option 2: Individual components
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=postgres
DB_PASSWORD=secretpassword  # Or use DB_PASSWORD env var

# === Optional Configuration ===
DB_SCHEMA=llmbridge          # Default schema name
DB_MIN_CONNECTIONS=2         # Minimum pool size
DB_MAX_CONNECTIONS=10        # Maximum pool size
ENABLE_DB_LOGGING=true       # Enable database logging
ENABLE_MONITORING=true       # Enable performance monitoring

# === Application Settings ===
APP_NAME=my-application     # Your application name for tracking
LOG_LEVEL=INFO              # Logging level
```

---

## 🗄️ Step 3: Database Setup

### **Option A: Automatic Setup (Easiest)**

```python
# setup_database.py
import asyncio
from llmbridge import LLMBridge

async def setup():
    """Automatic database setup with migrations."""
    
    # Initialize service (will create schema and tables automatically)
    service = LLMBridge(
        db_connection_string="postgresql://postgres:password@localhost/myapp",
        origin="my-app",
        enable_db_logging=True
    )
    
    # This will:
    # 1. Create the llmbridge schema if it doesn't exist
    # 2. Apply all migrations automatically
    # 3. Create necessary tables and indexes
    await service._ensure_db_initialized()
    
    print("✅ Database setup complete!")
    
    # Check the setup
    models = await service.get_models_from_db()
    print(f"📊 Found {len(models)} models in database")
    
    await service.close()

if __name__ == "__main__":
    asyncio.run(setup())
```

### **Option B: Manual Setup with Scripts**

```bash
# 1. Create database if needed
createdb myapp

# 2. Run the setup script provided by llmbridge
python -m llmbridge.scripts.setup_database setup

# Or reset everything
python -m llmbridge.scripts.setup_database reset

# Check status
python -m llmbridge.scripts.setup_database status
```

### **Option C: Direct SQL Setup**

```sql
-- Create schema
CREATE SCHEMA IF NOT EXISTS llmbridge;

-- The migrations will be applied automatically on first use,
-- or you can apply them manually from:
-- llmbridge/src/llmbridge/migrations/*.sql
```

---

## 📊 Step 4: Populate Model Data

### **Method 1: Automatic Model Discovery (Recommended)**

```python
# populate_models.py
import asyncio
from llmbridge import LLMBridge
from llmbridge.model_refresh import CompleteRefreshManager

async def populate_models():
    """Automatically discover and populate models from providers."""
    
    # Initialize service
    service = LLMBridge(
        db_connection_string="postgresql://postgres:password@localhost/myapp",
        enable_db_logging=True
    )
    
    await service._ensure_db_initialized()
    
    # Create refresh manager
    refresh_manager = CompleteRefreshManager(
        db=service.db,
        providers={
            "openai": service.providers.get("openai"),
            "anthropic": service.providers.get("anthropic"),
            "google": service.providers.get("google"),
        }
    )
    
    # Discover models from APIs
    print("🔍 Discovering models from provider APIs...")
    results = await refresh_manager.refresh_all_providers()
    
    for provider, result in results.items():
        print(f"\n{provider}:")
        print(f"  - Discovered: {result['discovered_count']} models")
        print(f"  - Added: {result['added_count']} new models")
        print(f"  - Updated: {result['updated_count']} existing models")
    
    await service.close()

if __name__ == "__main__":
    asyncio.run(populate_models())
```

### **Method 2: Load from JSON Files**

First, prepare JSON files with model data:

```json
// data/models/openai.json
{
  "provider": "openai",
  "models": [
    {
      "model_name": "gpt-4o",
      "display_name": "GPT-4 Optimized",
      "description": "Most capable GPT-4 model",
      "max_context": 128000,
      "max_output_tokens": 16384,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_mode": true,
      "dollars_per_million_tokens_input": 2.5,
      "dollars_per_million_tokens_output": 10.0
    },
    {
      "model_name": "gpt-4o-mini",
      "display_name": "GPT-4 Optimized Mini",
      "description": "Affordable GPT-4 model",
      "max_context": 128000,
      "max_output_tokens": 16384,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_mode": true,
      "dollars_per_million_tokens_input": 0.15,
      "dollars_per_million_tokens_output": 0.6
    }
  ]
}
```

Then load them:

```bash
# Using the CLI tool
llm-models refresh-from-json --path data/models/

# Or programmatically
```

```python
# load_from_json.py
import asyncio
import json
from pathlib import Path
from llmbridge import LLMBridge

async def load_models_from_json():
    """Load models from JSON files."""
    
    service = LLMBridge(
        db_connection_string="postgresql://postgres:password@localhost/myapp",
        enable_db_logging=True
    )
    
    await service._ensure_db_initialized()
    
    # Load each provider's JSON
    models_dir = Path("data/models")
    for json_file in models_dir.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
        
        provider = data["provider"]
        models = data["models"]
        
        print(f"Loading {len(models)} models for {provider}...")
        
        for model in models:
            # Insert or update model
            await service.db.upsert_model(
                provider=provider,
                **model
            )
    
    print("✅ Models loaded successfully!")
    await service.close()

if __name__ == "__main__":
    asyncio.run(load_models_from_json())
```

### **Method 3: Extract from Provider Documentation PDFs**

```bash
# 1. Download provider documentation PDFs
# Save them to data/pdfs/ as:
# - anthropic_models.pdf
# - google_models.pdf  
# - openai_models.pdf

# 2. Extract model information
llm-models extract-from-pdfs generate

# 3. This creates JSON files in data/models/

# 4. Load into database
llm-models refresh-from-json
```

---

## 💻 Step 5: Using LLMBridge in Your Module

### **Basic Usage Pattern**

```python
# my_module.py
import asyncio
import os
from typing import Optional
from llmbridge import LLMBridge
from llmbridge.schemas import LLMRequest, Message

class MyAIService:
    """Example service using LLMBridge."""
    
    def __init__(self, db_url: Optional[str] = None):
        """Initialize with optional database URL."""
        
        # Get database URL from environment or parameter
        db_url = db_url or os.getenv("DATABASE_URL")
        
        # Initialize LLMBridge
        self.llm = LLMBridge(
            db_connection_string=db_url,
            origin="my-ai-service",  # Identify your service
            enable_db_logging=True   # Enable tracking
        )
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize the service (call once at startup)."""
        if not self._initialized:
            await self.llm._ensure_db_initialized()
            self._initialized = True
            
            # Verify setup
            models = await self.llm.get_models_from_db()
            print(f"✅ Service initialized with {len(models)} models available")
    
    async def chat(self, user_message: str, user_id: str = "anonymous"):
        """Simple chat interface."""
        
        await self.initialize()
        
        request = LLMRequest(
            messages=[
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content=user_message)
            ],
            model="gpt-4o-mini",  # or "claude-3-haiku-20240307", etc.
            temperature=0.7,
            max_tokens=500
        )
        
        # Chat with user tracking
        response = await self.llm.chat(request, id_at_origin=user_id)
        
        return response.content
    
    async def get_user_stats(self, user_id: str):
        """Get usage statistics for a user."""
        
        await self.initialize()
        
        stats = await self.llm.get_usage_stats(user_id, days=30)
        if stats:
            return {
                "total_requests": stats.total_calls,
                "total_cost": float(stats.total_cost),
                "average_response_time": stats.avg_response_time_ms,
                "most_used_model": stats.most_used_model
            }
        return None
    
    async def close(self):
        """Cleanup (call at shutdown)."""
        await self.llm.close()

# Usage example
async def main():
    service = MyAIService()
    
    # Initialize once
    await service.initialize()
    
    # Chat
    response = await service.chat(
        "What's the capital of France?",
        user_id="user@example.com"
    )
    print(f"Response: {response}")
    
    # Check usage
    stats = await service.get_user_stats("user@example.com")
    print(f"Usage stats: {stats}")
    
    # Cleanup
    await service.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### **Advanced Integration with Shared Database**

```python
# advanced_setup.py
import asyncio
import os
from pgdbm import AsyncDatabaseManager, DatabaseConfig
from llmbridge import LLMBridge
from llmbridge.db import LLMDatabase

class IntegratedSystem:
    """System with multiple modules sharing a database connection."""
    
    def __init__(self):
        self.shared_pool = None
        self.llm_service = None
        self.app_db = None
    
    async def initialize(self):
        """Initialize all components with shared connection pool."""
        
        # Create shared connection pool
        config = DatabaseConfig(
            connection_string=os.getenv("DATABASE_URL"),
            min_connections=10,
            max_connections=50
        )
        
        self.shared_pool = await AsyncDatabaseManager.create_shared_pool(config)
        
        # Create database managers for different modules
        self.app_db = AsyncDatabaseManager(
            pool=self.shared_pool,
            schema="application"
        )
        
        # Create LLM database manager
        llm_db = AsyncDatabaseManager(
            pool=self.shared_pool,
            schema="llmbridge"
        )
        
        # Initialize LLM service with shared connection
        self.llm_service = LLMBridge(
            db_manager=llm_db,
            origin="integrated-system",
            enable_db_logging=True
        )
        
        await self.llm_service._ensure_db_initialized()
        
        print("✅ Integrated system initialized")
    
    async def process_with_ai(self, data: dict, user_id: str):
        """Process data with AI and store results."""
        
        # Use LLM for processing
        from llmbridge.schemas import LLMRequest, Message
        
        request = LLMRequest(
            messages=[
                Message(role="system", content="Analyze this data."),
                Message(role="user", content=str(data))
            ],
            model="gpt-4o-mini"
        )
        
        response = await self.llm_service.chat(request, id_at_origin=user_id)
        
        # Store results in application database
        await self.app_db.execute(
            "INSERT INTO {{tables.ai_results}} (user_id, result) VALUES ($1, $2)",
            user_id, response.content
        )
        
        return response.content
    
    async def cleanup(self):
        """Cleanup all resources."""
        await self.llm_service.close()
        await self.shared_pool.close()
```

---

## 🔍 Step 6: Verify Setup

Create a verification script:

```python
# verify_setup.py
import asyncio
import os
from llmbridge import LLMBridge

async def verify_setup():
    """Verify that everything is set up correctly."""
    
    print("🔍 Verifying LLMBridge setup...\n")
    
    # Check environment variables
    print("1️⃣ Environment Variables:")
    env_vars = {
        "OPENAI_API_KEY": "❌ Missing" if not os.getenv("OPENAI_API_KEY") else "✅ Set",
        "ANTHROPIC_API_KEY": "❌ Missing" if not os.getenv("ANTHROPIC_API_KEY") else "✅ Set",
        "GOOGLE_API_KEY": "❌ Missing" if not os.getenv("GOOGLE_API_KEY") else "✅ Set",
        "DATABASE_URL": "❌ Missing" if not os.getenv("DATABASE_URL") else "✅ Set",
    }
    for key, status in env_vars.items():
        print(f"  {key}: {status}")
    
    # Initialize service
    print("\n2️⃣ Database Connection:")
    try:
        service = LLMBridge(
            db_connection_string=os.getenv("DATABASE_URL"),
            enable_db_logging=True
        )
        await service._ensure_db_initialized()
        print("  ✅ Database connected successfully")
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return
    
    # Check providers
    print("\n3️⃣ Available Providers:")
    for provider_name in service.providers:
        print(f"  ✅ {provider_name}")
    
    # Check models
    print("\n4️⃣ Available Models:")
    for provider in ["openai", "anthropic", "google"]:
        try:
            models = await service.get_models_from_db(provider=provider)
            if models:
                print(f"  {provider}: {len(models)} models")
                for model in models[:3]:  # Show first 3
                    print(f"    - {model.model_name}")
            else:
                print(f"  {provider}: No models found (run populate_models.py)")
        except:
            pass
    
    # Test a simple request
    print("\n5️⃣ Test Request:")
    try:
        from llmbridge.schemas import LLMRequest, Message
        
        request = LLMRequest(
            messages=[Message(role="user", content="Say 'Hello, World!'")],
            model="gpt-4o-mini",
            max_tokens=10
        )
        
        response = await service.chat(request, id_at_origin="test-user")
        print(f"  ✅ Response: {response.content[:50]}...")
        
        # Check if it was logged
        calls = await service.list_recent_calls(id_at_origin="test-user", limit=1)
        if calls:
            print(f"  ✅ Call logged to database")
    except Exception as e:
        print(f"  ❌ Test request failed: {e}")
    
    await service.close()
    print("\n✅ Setup verification complete!")

if __name__ == "__main__":
    asyncio.run(verify_setup())
```

---

## 📚 Common Patterns

### **Pattern 1: Model Selection by Use Case**

```python
async def select_best_model(service, use_case: str):
    """Select the best model for a use case."""
    
    # Get recommendations
    hints = await service.get_usage_hints(use_case)
    
    # use_case options:
    # - "deepest_model": Most capable reasoning
    # - "largest_context": Biggest context window
    # - "best_vision": Best image understanding
    # - "cheapest_good": Best value for money
    # - "fastest": Lowest latency
    
    if hints:
        best_model = hints[0]  # One per provider
        return f"{best_model['provider']}:{best_model['model_name']}"
    
    return "gpt-4o-mini"  # Fallback
```

### **Pattern 2: Cost-Aware Processing**

```python
async def process_with_budget(service, content: str, max_cost: float = 0.10):
    """Process content within a budget."""
    
    from llmbridge.schemas import LLMRequest, Message
    
    # Start with cheapest model
    models = [
        ("gpt-4o-mini", 0.15),  # $0.15 per million tokens
        ("claude-3-haiku-20240307", 0.25),
        ("gpt-4o", 2.50),
    ]
    
    for model, cost_per_million in models:
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(content) / 4
        estimated_cost = (estimated_tokens / 1_000_000) * cost_per_million
        
        if estimated_cost <= max_cost:
            request = LLMRequest(
                messages=[Message(role="user", content=content)],
                model=model
            )
            return await service.chat(request)
    
    raise ValueError(f"Content too large for budget ${max_cost}")
```

### **Pattern 3: Retry with Fallback**

```python
async def chat_with_fallback(service, message: str):
    """Try primary provider, fall back if needed."""
    
    from llmbridge.schemas import LLMRequest, Message
    
    providers = ["anthropic", "openai", "google"]
    
    for provider in providers:
        try:
            # Get default model for provider
            models = await service.get_models_from_db(provider=provider)
            if not models:
                continue
            
            request = LLMRequest(
                messages=[Message(role="user", content=message)],
                model=f"{provider}:{models[0].model_name}"
            )
            
            return await service.chat(request)
            
        except Exception as e:
            print(f"Provider {provider} failed: {e}")
            continue
    
    raise Exception("All providers failed")
```

---

## 🚦 Production Checklist

- [ ] **Environment variables** configured in `.env` or secrets manager
- [ ] **Database** created and accessible
- [ ] **Migrations** applied (automatic or manual)
- [ ] **Models** populated via API discovery or JSON import
- [ ] **Connection pooling** configured appropriately
- [ ] **Error handling** implemented with retries
- [ ] **Monitoring** enabled for production
- [ ] **Costs** tracked and budgets set
- [ ] **Backup** strategy for model configurations
- [ ] **Health checks** implemented for providers

---

## 🆘 Troubleshooting

```python
# debug_setup.py
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Check what's happening
async def debug():
    from llmbridge import LLMBridge
    
    service = LLMBridge(
        db_connection_string="postgresql://...",
        enable_db_logging=True
    )
    
    # This will show detailed connection logs
    await service._ensure_db_initialized()
```

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| "No providers available" | Check API keys in `.env` file |
| "Database connection failed" | Verify PostgreSQL is running and credentials are correct |
| "No models found" | Run the model population scripts |
| "Rate limit exceeded" | Implement retry logic with exponential backoff |
| "Module 'llmbridge' not found" | Ensure llmbridge is installed: `pip install llmbridge` |
| "Schema does not exist" | Run database setup script or let it auto-initialize |
| "Permission denied on schema" | Ensure database user has CREATE SCHEMA privileges |

### Debug Commands

```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Test database connection
psql -h localhost -U postgres -d myapp -c "SELECT 1"

# Check if schema exists
psql -h localhost -U postgres -d myapp -c "\dn llmbridge"

# List tables in schema
psql -h localhost -U postgres -d myapp -c "\dt llmbridge.*"

# Check environment variables
python -c "import os; print('OPENAI_API_KEY:', 'Set' if os.getenv('OPENAI_API_KEY') else 'Missing')"
```

---

## 📚 Additional Resources

- [API Reference](./api-reference.md)
- [Model Management Guide](./model-management.md)
- [Cost Optimization Guide](./cost-optimization.md)
- [Migration Guide](./migrations.md)
- [Testing Guide](./testing.md)

---

## 🤝 Support

For issues or questions:
1. Check the [troubleshooting section](#-troubleshooting) above
2. Review the [GitHub issues](https://github.com/yourusername/llmbridge/issues)
3. Open a new issue with debug logs and configuration details

This complete guide should help any module integrate with llmbridge successfully!