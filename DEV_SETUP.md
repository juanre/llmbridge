# Development Setup

This document explains the development environment setup for LLMBridge contributors.

## Local Development

### Symlinks in the Repository

The repository may contain symlinks to local development dependencies:
- `mcp-client` - Example integration with MCP (Model Context Protocol) client
- `pgdbm` - PostgreSQL database manager (if developing pgdbm features locally)

These symlinks are ignored by git (see `.gitignore`) and are not required for general development.

### Setting Up Your Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/juanreyero/llmbridge.git
   cd llmbridge
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env  # If available
   # Edit .env with your API keys
   ```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/unit/

# Run only SQLite tests
pytest tests/test_sqlite.py

# Run with coverage
pytest --cov=llmbridge tests/
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
pyright src/
```

## Building for Distribution

### Local Build Testing

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the build
twine check dist/*

# Test installation in a fresh environment
python -m venv test-env
test-env/bin/pip install dist/*.whl
```

### Publishing to PyPI

1. **Test on TestPyPI first:**
   ```bash
   twine upload --repository testpypi dist/*
   ```

2. **Install from TestPyPI to verify:**
   ```bash
   pip install --index-url https://test.pypi.org/simple/ llmbridge
   ```

3. **Publish to PyPI:**
   ```bash
   twine upload dist/*
   ```

## Continuous Integration

The project uses GitHub Actions for CI/CD. The workflow:
- Runs tests on Python 3.10, 3.11, and 3.12
- Checks code formatting with black and isort
- Builds the package
- Automatically publishes to PyPI on tagged releases (v*)

To trigger a release:
```bash
git tag v0.1.0
git push origin v0.1.0
```

## Troubleshooting

### Missing Dependencies

If you encounter import errors for development dependencies:
```bash
pip install -e ".[dev,postgres]"
```

### Database Tests Failing

SQLite tests should work out of the box. For PostgreSQL tests:
```bash
# Start a local PostgreSQL instance
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15

# Set environment variables
export DATABASE_HOST=localhost
export DATABASE_PORT=5432
export DATABASE_NAME=postgres
export DATABASE_USER=postgres
export DATABASE_PASSWORD=postgres
```

### Symlink Issues

If you see errors related to symlinks (pgdbm, mcp-client), you can safely ignore them or remove the symlinks:
```bash
rm -f pgdbm mcp-client
```

These are only used for specific local development scenarios and are not required for contributing to LLMBridge.