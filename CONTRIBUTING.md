# Contributing to Bybit Strategy Tester

Thank you for your interest in contributing! This document provides guidelines
and standards for contributing to this project.

## Code of Conduct

Be respectful and considerate in all interactions. We welcome contributors of
all experience levels.

## Getting Started

1.  Fork the repository
2.  Clone your fork: `git clone https://github.com/YOUR_USERNAME/bybit_strategy_tester_v2.git`
3.  Create a feature branch: `git checkout -b feature/my-feature`
4.  Set up development environment (see [QUICKSTART.md](QUICKSTART.md))

## Development Setup

```powershell
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

## Code Style

This project follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

### Key Standards

- **Line length**: 120 characters maximum
- **Imports**: Use absolute imports, sorted with isort
- **Type hints**: Required for public functions
- **Docstrings**: Google-style docstrings for all public functions

### Example Function

```python
def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
) -> float:
    """Calculate the Sharpe ratio for a series of returns.

    The Sharpe ratio measures risk-adjusted return. Higher values indicate
    better risk-adjusted performance.

    Args:
        returns: List of periodic returns as decimals (e.g., 0.05 for 5%).
        risk_free_rate: Annualized risk-free rate. Defaults to 0.0.

    Returns:
        The annualized Sharpe ratio.

    Raises:
        ValueError: If returns list is empty.

    Example:
        >>> returns = [0.01, 0.02, -0.01, 0.03]
        >>> calculate_sharpe_ratio(returns)
        1.23
    """
    if not returns:
        raise ValueError("Returns list cannot be empty")

    # Implementation...
```

### Linting and Formatting

Before committing, run code quality checks:

#### On Windows (Recommended)

Use `dev.ps1` for all code quality checks:

```powershell
# Check code quality
.\dev.ps1 lint

# Format code
.\dev.ps1 format

# Run all checks
.\dev.ps1 lint; .\dev.ps1 format; .\dev.ps1 test
```

> **Note**: `pre-commit run` may fail on Windows due to Git Bash fork issues.
> Use `dev.ps1` commands instead. Pre-commit checks run automatically in
> GitHub Actions CI/CD pipeline.

#### On Linux/Mac

```bash
# Using make
make lint
make format

# Or using pre-commit
pre-commit run --all-files
```

#### Pre-commit on Windows (Optional)

If you need pre-commit locally on Windows, try these alternatives:

1.  **Use WSL2** (recommended for full compatibility):

    ```powershell
    wsl --install
    # Then in WSL:
    cd /mnt/d/bybit_strategy_tester_v2
    pre-commit run --all-files
    ```

2.  **Clear cache and retry**:

    ```powershell
    Remove-Item "$env:USERPROFILE\.cache\pre-commit" -Recurse -Force
    pre-commit run --all-files
    ```

3.  **Reboot** if you see "fork: Resource temporarily unavailable" errors.

#### CI/CD Checks

All pre-commit checks run automatically on GitHub Actions when you push:

- Ruff linting
- Ruff formatting
- Bandit security scan
- MyPy type checking

## Testing

All new features must include tests.

### Running Tests

```powershell
# Run all tests
.\dev.ps1 test

# Run with coverage
.\dev.ps1 test-cov

# Run specific test file
pytest tests/backend/api/mcp/test_mcp_tools.py -v
```

### Test Standards

- Use `pytest` for all tests
- Follow AAA pattern: Arrange, Act, Assert
- Use descriptive test names: `test_function_should_do_something_when_condition`
- Mock external services (APIs, databases)

### Example Test

```python
class TestBacktestService:
    """Tests for BacktestService."""

    def test_run_backtest_returns_valid_metrics(self, mock_data):
        """Test that backtest returns valid performance metrics."""
        # Arrange
        service = BacktestService()
        config = BacktestConfig(symbol="BTCUSDT", strategy="MACD")

        # Act
        result = service.run(config, mock_data)

        # Assert
        assert result.success is True
        assert result.metrics.sharpe_ratio > 0
        assert result.metrics.total_trades >= 0
```

## Pull Request Process

### Before Submitting

1.  Run all tests: `.\dev.ps1 test`
2.  Run linter: `.\dev.ps1 lint`
3.  Format code: `.\dev.ps1 format`
4.  Update documentation if needed

### PR Guidelines

- Use a descriptive title: `feat: Add walk-forward optimization`
- Fill out the PR template
- Reference related issues: `Fixes #123`
- Keep PRs focused and reasonably sized

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, no code change
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:

```
feat(backtest): Add GPU acceleration support

fix(api): Handle empty response from Bybit

docs: Update QUICKSTART with Docker instructions

refactor(metrics): Extract Sortino calculation
```

## Documentation

### Adding Documentation

- Place new docs in appropriate `docs/` subdirectory
- Use Google developer documentation style
- Include code examples where helpful
- Update `docs/README.md` index if adding new files

### Documentation Structure

```
docs/
├── api/           # API documentation
├── architecture/  # System design
├── guides/        # User guides
├── reference/     # Reference documentation
└── ai/            # AI agent documentation
```

## Release Process

Releases are managed by maintainers. To request a release:

1.  Ensure all tests pass
2.  Update CHANGELOG.md
3.  Create a release PR
4.  Tag the release: `git tag v2.1.0`

## Questions?

- Open a GitHub issue for bugs or features
- Check existing documentation in `docs/`
- Review closed issues for similar questions

Thank you for contributing! 🚀
