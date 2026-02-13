# Contributing to Notification Service

Thank you for your interest in contributing to the Notification Service! This document provides guidelines and instructions for contributing.

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.14+
- uv (for dependency management)
- Git
- Docker (optional, for containerized development)

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR-USERNAME/notification-service
cd notification-service
```

2. **Install dependencies**

```bash
uv sync
```

3. **Set up pre-commit hooks** (required)

```bash
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

4. **Configure environment**

```bash
cp .env.example .env.local
# Edit .env.local with your database and Redis settings
```

5. **Run the development server**

```bash
# Start the Django server
uv run local

# In a separate terminal, start the RQ worker (required for email sending)
uv run python -m django_rq.management.commands.rqworker default
```

The server will start at `http://localhost:8000`

### Docker Development

Alternatively, use Docker for development:

```bash
docker-compose up
```

This starts the Django app, Redis, and RQ worker together.

## Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches
- `hotfix/*` - Urgent fixes for production

### Making Changes

1. Create a feature branch from `main`
2. Make your changes
3. Write or update tests
4. Ensure all tests pass
5. Commit your changes (pre-commit hooks run automatically)
6. Push and create a pull request

## Code Style

Pre-commit hooks handle formatting and linting automatically. The key tools are:

- **Ruff** - Linting and formatting (replaces black, flake8, isort)
- **mypy** - Type checking
- **interrogate** - Docstring coverage (80% minimum required)
- **bandit** - Security scanning

### Manual Commands

```bash
uv run ruff check core/ --fix    # Lint with auto-fix
uv run ruff format core/          # Format code
uv run mypy core/                 # Type check
uv run pre-commit run --all-files # Run all checks
```

### Style Guidelines

- **Line length**: 88 characters
- **Docstrings**: Google style, 80% coverage required
- **Imports**: All imports at the top of the file (no function-level imports)
- **Classes**: One class per file, export from `__init__.py`
- **Logging**: Use `structlog`, not Django's logging

See [.pre-commit-setup.md](../.pre-commit-setup.md) for detailed documentation.

## Testing

### Running Tests

```bash
# All tests
uv run test-all

# Specific test suites
uv run test-unit
uv run test-component
uv run test-dependency
uv run test-performance

# Run a specific test file
uv run pytest tests/unit/test_notification_service.py -v

# With coverage
uv run test-coverage
```

### Test Guidelines

- Write tests for all new functionality
- Aim for at least 80% code coverage
- Tests are in `tests/` organized by type: `unit/`, `component/`, `dependency/`, `performance/`

## Commit Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

### Types

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code formatting (no functional changes)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Build process or tooling changes

### Examples

```bash
feat(api): add endpoint for email notifications
fix(worker): resolve retry logic for failed jobs
docs(readme): update installation instructions
test(notifications): add tests for SMS delivery
```

## Pull Request Process

### Before Submitting

- [ ] Pre-commit hooks pass (`uv run pre-commit run --all-files`)
- [ ] All tests pass (`uv run test-all`)
- [ ] New tests added for new functionality
- [ ] Documentation updated if applicable
- [ ] Commit messages follow conventional commits

### Submitting

1. Push your changes to your fork
2. Create a pull request to the `main` branch
3. Fill out the pull request template
4. Wait for CI checks to pass
5. Request review from maintainers

## Important Notes

### Database

**This service does NOT own the database schema.** It is a read-only consumer of a shared database.

- All models have `managed = False`
- **Never run migrations** (`makemigrations` or `migrate`)
- Schema changes must be coordinated with the database owner

### Architecture Rules

These rules are enforced by pre-commit hooks and code review:

1. **No function-level imports** - All imports at the top of files
2. **No linter ignore comments** - Fix the code or add rule to `pyproject.toml`
3. **One class per file** - Export from package `__init__.py`
4. **Google-style docstrings** - Required for public functions and classes
5. **structlog for logging** - Not Django's built-in logging

## Security

**Do not create public issues for security vulnerabilities.**

Report security issues via:
- [GitHub Security Advisories](https://github.com/Recipe-Web-App/notification-service/security/advisories/new)
- Email: jsamuelsen11@gmail.com

## Questions and Support

- **Questions**: Use [GitHub Discussions](https://github.com/Recipe-Web-App/notification-service/discussions)
- **Bugs**: Create an issue using the bug report template
- **Features**: Create an issue using the feature request template

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

Thank you for contributing to the Notification Service!
