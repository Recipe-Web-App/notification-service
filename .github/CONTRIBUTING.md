# Contributing to Notification Service

Thank you for your interest in contributing to the Notification Service! This document provides guidelines and instructions for contributing.

## Code of Conduct

This project adheres to a [Code of Conduct](.github/CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.14+
- Poetry (for dependency management)
- Git
- Docker (optional, for containerized development)

### Development Setup

1. **Fork and clone the repository**

```bash
git fork https://github.com/Recipe-Web-App/notification-service
git clone https://github.com/YOUR-USERNAME/notification-service
cd notification-service
```

2. **Install Poetry** (if not already installed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. **Install dependencies**

```bash
poetry install
```

4. **Run database migrations**

```bash
poetry run python manage.py migrate
```

5. **Create a superuser** (optional)

```bash
poetry run python manage.py createsuperuser
```

6. **Run the development server**

```bash
poetry run local
# Or
poetry run python manage.py runserver
```

The server will start at `http://localhost:8000`

### Docker Development Setup

Alternatively, you can use Docker for development:

```bash
docker-compose up
```

### Setting Up Pre-commit Hooks (Required)

We use pre-commit hooks to enforce code quality, security, and documentation standards automatically.

**Install pre-commit hooks:**

```bash
# Install the git hooks
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg

# Run on all files (first time setup)
poetry run pre-commit run --all-files
```

**What pre-commit checks:**
- ✅ Code formatting (Ruff format, isort) - **auto-fixes**
- ✅ Code linting (Ruff) - **auto-fixes many issues**
- ✅ Code modernization (django-upgrade) - **auto-fixes**
- ✅ Type checking (mypy)
- ✅ Documentation (interrogate - 80% coverage required)
- ✅ Security (bandit, osv-scanner)
- ✅ Commit message format (conventional commits)

**See [.pre-commit-setup.md](../.pre-commit-setup.md) for detailed documentation.**

## Development Workflow

### Branch Strategy

We use a simple branch strategy:

- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches
- `hotfix/*` - Urgent fixes for production

### Creating a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### Making Changes

1. Make your changes
2. Write or update tests
3. Ensure all tests pass
4. Format your code
5. Commit your changes
6. Push your branch
7. Create a pull request

## Testing

### Running Tests

Run the Django test suite:

```bash
poetry run python manage.py test
```

### Running Tests with Coverage

```bash
poetry add --group dev coverage
poetry run coverage run --source='.' manage.py test
poetry run coverage report
poetry run coverage html  # Generate HTML report
```

### Test Guidelines

- Write tests for all new functionality
- Update tests when modifying existing functionality
- Aim for at least 80% code coverage
- Use Django's built-in test framework (unittest)
- Test files should match the pattern `test_*.py`
- Place tests in a `tests/` directory or use `test_*.py` naming

### Example Test Structure

```python
from django.test import TestCase
from core.models import Notification

class NotificationTestCase(TestCase):
    def setUp(self):
        Notification.objects.create(
            type="email",
            recipient="test@example.com"
        )

    def test_notification_creation(self):
        notification = Notification.objects.get(recipient="test@example.com")
        self.assertEqual(notification.type, "email")
```

## Code Style

### Automated Formatting and Linting

**Pre-commit hooks handle all formatting and linting automatically!**

When you commit, the following tools run automatically:

#### Ruff - Linter and Formatter

**Ruff** is an extremely fast Python linter and formatter written in Rust.

Features:
- Code formatting
- Style guide enforcement (PEP 8)
- Comprehensive linting
- Docstring checking (Google style)
- Modern Python syntax enforcement
- Django-specific rules (DJ)

```bash
# Manual run (pre-commit does this automatically)
poetry run ruff check . --fix          # Run linter with auto-fix
poetry run ruff format .                # Run formatter
```

#### Additional Tools

- **isort** - Import organizer (Django-aware)
- **mypy** - Static type checking
- **interrogate** - Docstring coverage checker

```bash
# Manual run (pre-commit does this automatically)
poetry run isort .
poetry run mypy notification_service/ core/
poetry run interrogate notification_service/
```

#### Security

- **bandit** - Python security scanner
- **osv-scanner** - Dependency vulnerability scanner (Google OSV)

```bash
# Manual run (pre-commit does this automatically)
poetry run bandit -r notification_service/ core/
osv-scanner scan --lockfile=poetry.lock:poetry.lock
```

### Documentation Requirements

**80% docstring coverage is required** (enforced by pre-commit).

Use **Google-style docstrings**:

```python
def send_notification(recipient: str, message: str, channel: str = "email") -> bool:
    """Send a notification to a recipient.

    Args:
        recipient: Email address or phone number of the recipient.
        message: Notification message content.
        channel: Notification channel (email, sms, push). Defaults to "email".

    Returns:
        True if notification was sent successfully, False otherwise.

    Raises:
        ValueError: If recipient format is invalid.
        ConnectionError: If notification service is unavailable.

    Examples:
        >>> send_notification("user@example.com", "Hello!")
        True
    """
    pass
```

Check documentation coverage:

```bash
poetry run interrogate --verbose notification_service/
```

### Style Guidelines

- **Line length:** 120 characters (enforced by Ruff)
- **Imports:** Organized by isort and Ruff (Django-aware)
- **Docstrings:** Google style, 80% coverage minimum
- **Type hints:** Use where appropriate
- **Naming:** Follow PEP 8 conventions
- **Code quality:** Enforced by Ruff (includes flake8, pylint, and more)

## Commit Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code formatting (no functional changes)
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding or updating tests
- `chore:` - Build process or tooling changes
- `security:` - Security fixes
- `deps:` - Dependency updates

### Examples

```bash
feat(api): add endpoint for email notifications
fix(database): resolve migration conflict
docs(readme): update installation instructions
test(notifications): add tests for SMS delivery
```

## Pull Request Process

### Before Submitting

- [ ] **Pre-commit hooks installed and passing**
- [ ] Code is formatted with `Ruff` (pre-commit auto-formats)
- [ ] Linting passes with `Ruff` (pre-commit auto-fixes many issues)
- [ ] Type checking passes with `mypy`
- [ ] Docstrings added (80% coverage required)
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow conventional commits format
- [ ] Branch is up to date with `develop`
- [ ] No security vulnerabilities (bandit, osv-scanner pass)

### Submitting a Pull Request

1. Push your changes to your fork
2. Create a pull request to the `develop` branch
3. Fill out the pull request template completely
4. Wait for CI checks to pass
5. Request review from maintainers
6. Address any feedback

### PR Requirements

- All CI checks must pass
- At least one approval from a maintainer
- No merge conflicts with base branch
- Code coverage does not decrease
- No security vulnerabilities introduced

## Django-Specific Guidelines

### Models

- Use meaningful model and field names
- Add `help_text` to fields
- Use `verbose_name` and `verbose_name_plural` in Meta
- Add `__str__` methods to all models
- Use Django's built-in fields when possible
- Create migrations after model changes

### Views and Serializers

- Use Django REST Framework for API endpoints
- Keep views thin, business logic in models or services
- Use serializers for data validation
- Add proper permission classes
- Document API endpoints

### Database Migrations

- Create migrations for all model changes
- Name migrations descriptively
- Test migrations on a copy of production data
- Never edit existing migrations (create new ones)
- Include both forward and backward migrations

### Settings

- Never commit secrets or API keys
- Use environment variables for configuration
- Update `.env.example` when adding new variables
- Document all settings in comments

## Security

### Reporting Security Vulnerabilities

**Do not create public issues for security vulnerabilities.**

Please report security vulnerabilities through [GitHub Security Advisories](https://github.com/Recipe-Web-App/notification-service/security/advisories/new) or email jsamuelsen11@gmail.com.

### Security Guidelines

- Never commit secrets, API keys, or passwords
- Use Django's built-in security features
- Sanitize user input
- Use parameterized queries (Django ORM handles this)
- Keep dependencies up to date
- Follow OWASP security best practices

## Questions and Support

- **Questions**: Use [GitHub Discussions](https://github.com/Recipe-Web-App/notification-service/discussions)
- **Bugs**: Create an issue using the bug report template
- **Features**: Create an issue using the feature request template
- **Chat**: Join our community discussions

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [PEP 8 Style Guide](https://pep8.org/)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to the Notification Service! 🎉
