# Contributing to mcp-pm

First off, thank you for considering contributing to mcp-pm! We welcome contributions from everyone.

## Code of Conduct

This project and everyone participating in it is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to wgwcko@gmail.com.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the [existing issues](https://github.com/daveywong/mcp-pm/issues) to see if the problem has already been reported. If it hasn't, use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) when creating an issue.

### Suggesting Features

Feature suggestions are welcome! Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md) and provide as much detail as possible.

### Pull Requests

1. **Fork** the repository and create your branch from `main`.
2. **Install** the project in development mode:
   ```bash
   pip install -e ".[dev]"
   ```
3. **Make your changes** — ensure they are focused and well-tested.
4. **Run linting**:
   ```bash
   ruff check .
   ruff format --check .
   ```
5. **Run type checking**:
   ```bash
   mypy mcp_pm
   ```
6. **Run tests**:
   ```bash
   pytest
   ```
7. **Update documentation** if your changes affect the public API or user-facing behavior.
8. **Update CHANGELOG.md** following the [Keep a Changelog](https://keepachangelog.com/) format.
9. **Submit a pull request** using the [PR template](.github/PULL_REQUEST_TEMPLATE.md).

## Development Setup

```bash
# Clone the repository
git clone https://github.com/daveywong/mcp-pm.git
cd mcp-pm

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

## Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Type hints are required for all public functions and methods
- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- Use Python 3.11+ features where appropriate (e.g., `|` union types, `Self` type)

## Testing

- Write tests for all new features and bug fixes
- Tests should be placed in the `tests/` directory
- We use `pytest` as the test framework
- Aim for good test coverage

## Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in the present tense (e.g., "Add", "Fix", "Refactor")
- Reference issue numbers where applicable

## Release Process

Maintainers follow [Semantic Versioning](https://semver.org/):

1. Update `CHANGELOG.md`
2. Bump version in `pyproject.toml`
3. Create a signed tag: `git tag -s v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. Build and publish to PyPI

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

*Maintained by Davey Wong &lt;wgwcko@gmail.com&gt;*
