# Contributing to LLMBridge

We love your input! We want to make contributing to LLMBridge as easy and transparent as possible.

## Development Setup

1. Fork the repo and create your branch from `main`
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/llmbridge.git
   cd llmbridge
   ```

3. Install development dependencies:
   ```bash
   # Using uv (recommended)
   uv pip install -e ".[dev]"
   
   # Or using pip
   pip install -e ".[dev]"
   ```

4. Set up pre-commit hooks (optional but recommended):
   ```bash
   pre-commit install
   ```

## Development Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and add tests

3. Run tests:
   ```bash
   pytest tests/
   ```

4. Format your code:
   ```bash
   black src/ tests/
   isort src/ tests/
   ```

5. Type check (optional):
   ```bash
   pyright src/
   ```

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the CHANGELOG.md with your changes
3. Ensure all tests pass
4. Update documentation if you're changing functionality
5. The PR will be merged once you have approval from a maintainer

## Testing

- Write tests for any new functionality
- Ensure all tests pass: `pytest tests/`
- Add integration tests for provider-specific features in `tests/integration/`
- Add unit tests for utility functions in `tests/unit/`

## Code Style

- We use `black` for code formatting
- We use `isort` for import sorting
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to all public functions and classes

## Adding a New Provider

To add support for a new LLM provider:

1. Create a new provider module in `src/llmbridge/providers/`
2. Inherit from `BaseLLMProvider` 
3. Implement required methods: `chat()`, `get_supported_models()`
4. Add provider to the factory in `base.py`
5. Add tests in `tests/unit/test_providers/` and `tests/integration/test_providers/`
6. Update documentation

## Reporting Bugs

Report bugs using GitHub Issues. Please include:
- Your Python version
- Detailed steps to reproduce
- What you expected to happen
- What actually happened
- Any relevant logs or error messages

## License

By contributing, you agree that your contributions will be licensed under the MIT License.