# Contributing to Kyromesh Python SDK

Thank you for your interest in contributing to the Kyromesh Python SDK! This guide will help you get started.

## ⚠️ Contribution workflow: Fork + PR only

This repository uses a **fork + pull request** workflow:

- Do **not** push directly to `main`
- **Fork** the repository
- Create a feature or fix branch in **your fork**
- Open a **pull request** to `main` in the upstream repo
- Wait for review and CI checks before merging
- Only maintainers create release tags and publish to PyPI

This ensures:
- Safer, review-driven development
- Reliable, automated publishing from the upstream repo only
- No accidental publishes from forks

## Development Setup

### Prerequisites

- Python 3.9+
- Git
- pip

### Local Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/kyromesh-python-sdk.git
cd kyromesh-python-sdk

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode (includes dev dependencies)
pip install -e ".[dev]"
```

Replace `YOUR_USERNAME` with your GitHub username.

## Making Changes

### Code Style

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **MyPy** for type checking

Format your code before committing:

```bash
black kyromesh/ tests/
ruff check . --fix
mypy kyromesh/
```

### Testing

Run all tests:

```bash
# Unit tests
pytest tests/test_client.py -v

# Property-based tests
pytest tests/test_client_pbt.py -v

# All tests with coverage
pytest tests/ -v --cov=kyromesh --cov-report=html
```

Tests must pass before submitting a PR.

### Type Hints

All code must include type hints:

```python
def run_job(
    self,
    task: str,
    input: Dict[str, Any],
    timeout: int = 300,
) -> Job:
    """Submit an async job."""
    pass
```

## Submitting Changes

### 1. Create a Branch

```bash
git checkout -b fix/descriptive-name
```

Use descriptive branch names:

- `feature/add-batch-support`
- `fix/handle-timeout-errors`
- `docs/update-readme`
- `chore/update-dependencies`

### 2. Commit Messages

Write clear, descriptive commit messages:

```text
Add support for custom timeout values

- Allow users to specify timeout per job
- Add timeout validation
- Update tests and documentation
```

### 3. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:

- Clear title describing the change
- Description of what changed and why
- Reference to any related issues (e.g., `Closes #123`)

### 4. PR Validation

Your PR will automatically:

- ✅ Run linting (Black, Ruff)
- ✅ Run type checking (MyPy)
- ✅ Run unit tests
- ✅ Run property-based tests
- ✅ Verify package metadata

All checks must pass before merging.

## What Happens After Merge

- Merged PRs are part of the `main` branch
- Releases are created by maintainers via release tags (e.g., `sdk-python-v0.2.0`)
- PyPI publishing happens **only** from the upstream repo via trusted publishing
- Forks and external contributors **cannot** publish to PyPI

## Code Guidelines

### Docstrings

All public functions and classes must have docstrings:

```python
def run_job(self, task: str, input: Dict[str, Any]) -> Job:
    """
    Submit an async job for execution.
    
    Args:
        task: The task type (e.g., "summarize", "classify")
        input: Input data for the task
    
    Returns:
        Job object with job_id and status
    
    Raises:
        AuthError: If API key is invalid
        QuotaExceededError: If quota is exceeded
    """
    pass
```

### Error Handling

Use custom exceptions from `kyromesh.exceptions`:

```python
from kyromesh.exceptions import QuotaExceededError


if response.status_code == 429:
    raise QuotaExceededError("Quota exceeded for this month")
```

### Testing

Write tests for all new features:

```python
def test_run_job_with_timeout():
    """Test that jobs respect timeout parameter."""
    kyro = Kyromesh(api_key="km_test_xxx")
    job = kyro.run_job(
        task="test",
        input={"data": "test"},
        timeout=10
    )
    assert job.timeout == 10
```

## Property-Based Testing

For complex logic, add property-based tests using Hypothesis:

```python
from hypothesis import given, strategies as st


@given(st.integers(min_value=1, max_value=3600))
def test_timeout_always_positive(timeout):
    """Timeout should always be positive."""
    kyro = Kyromesh(api_key="km_test_xxx")
    job = kyro.run_job(
        task="test",
        input={"data": "test"},
        timeout=timeout
    )
    assert job.timeout > 0
```

## Documentation

Update documentation for new features:

1. **README.md** — Add usage examples  
2. **Docstrings** — Add to all public APIs  
3. **CONTRIBUTING.md** — Update if adding new guidelines  

## Reporting Issues

Found a bug? Please report it:

1. Check if the issue already exists
2. Create a new issue with:
   - Clear title  
   - Description of the problem  
   - Steps to reproduce  
   - Expected vs actual behavior  
   - Python version and OS  

## Questions?

- Check existing issues and discussions
- Review the README and documentation
- Open a discussion on GitHub

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building a welcoming community!

---

Thank you for contributing! 🎉