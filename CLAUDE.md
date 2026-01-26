# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Django-based notification service API for a recipe web app ecosystem. This service is a **read-only consumer** of a shared database - it does NOT own the schema. The service provides email notifications for recipe-related, social, and system events using a queue-based architecture with Redis and Django-RQ.

**Python version**: 3.14 (required)

## Development Commands

### Environment Setup
```bash
poetry install
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

### Running Locally
```bash
# Start development server
poetry run local

# Start RQ worker (required for email sending)
poetry run python -m django_rq.management.commands.rqworker default
```

### Testing
```bash
# All tests
poetry run test-all

# Specific test suites
poetry run test-unit
poetry run test-component
poetry run test-dependency
poetry run test-performance

# Run a single test file
poetry run pytest tests/unit/test_notification_service.py -v

# Run a specific test function
poetry run pytest tests/unit/test_notification_service.py::TestNotificationService::test_create_notification -v

# With coverage
poetry run test-coverage
```

### Linting and Formatting
```bash
poetry run ruff check core/ --fix    # Lint with auto-fix
poetry run ruff format core/          # Format code
poetry run mypy core/                 # Type check
poetry run pre-commit run --all-files # Run all pre-commit hooks
```

### Kubernetes Deployment
Scripts are in `scripts/containerManagement/`:
```bash
./scripts/containerManagement/deploy-container.sh   # Full deployment
./scripts/containerManagement/update-container.sh   # Update running deployment
./scripts/containerManagement/get-container-status.sh
./scripts/containerManagement/start-container.sh
./scripts/containerManagement/stop-container.sh
./scripts/containerManagement/cleanup-container.sh  # Remove all resources
```

## Architecture

### Core Principles

1. **Unmanaged Models**: This service does NOT own the database schema. All models have `managed = False` in their Meta class. Never run migrations or generate new migrations.

2. **Shared Database**: The service reads from a shared PostgreSQL database using a dedicated schema (`POSTGRES_SCHEMA` env var, typically `notifications`).

3. **Queue-Based Email**: Emails are sent asynchronously via Django-RQ workers. Jobs are queued to Redis, processed by background workers.

4. **OAuth2 Authentication**: Optional OAuth2 integration with the auth-service for protected endpoints (feature-flagged).

### Key Architecture Layers

- **`core/services/`**: Business logic layer organized by domain (recipe, social, system notifications)
- **`core/schemas/`**: Pydantic schemas for request/response validation
- **`core/repositories/`**: Data access layer
- **`core/jobs/`**: Django-RQ background jobs for async email sending
- **`core/middleware/`**: Request ID, rate limiting, security headers
- **`core/services/downstream/`**: Clients for external services

### Background Job Processing

Email sending is async via Django-RQ:

1. API endpoint creates a notification record (status: `PENDING`)
2. Notification is queued to Django-RQ (status: `QUEUED`)
3. RQ worker picks up job and calls `email_service.send_email()`
4. On success: status → `SENT`, `sent_at` timestamp set
5. On failure: Retry with exponential backoff (5min, 10min, 20min)
6. After 3 failures: status → `FAILED`, `error_message` set

**Important**: The RQ worker MUST be running for emails to be sent. Use `poetry run python -m django_rq.management.commands.rqworker default` in development.

### Authentication & Security

OAuth2 is optional and feature-flagged via `OAUTH2_SERVICE_ENABLED`, `OAUTH2_SERVICE_TO_SERVICE_ENABLED`, and `OAUTH2_INTROSPECTION_ENABLED`. Health check endpoints are exempt from authentication.

### Database

The service uses a shared PostgreSQL database. All models have `managed = False` - migrations are disabled. Key models: `Notification`, `User`, `UserFollow`.

## Critical Development Rules

### 1. NO FUNCTION-LEVEL IMPORTS
All imports MUST be at the top of the file. Never use imports inside functions or methods.

**Wrong:**
```python
def my_function():
    from some_module import SomeClass  # NEVER
```

**Correct:**
```python
from some_module import SomeClass

def my_function():
    # Use SomeClass here
```

### 2. NO LINTER IGNORE COMMENTS
Never use inline linter ignore comments (`# noqa:`, `# type: ignore`, `# pylint: disable`). If linter errors occur, either fix the code or add the rule to the `pyproject.toml` ignore list.

### 3. ONE CLASS PER FILE
Each class must be in its own file. Export from the package `__init__.py`.

**Wrong:**
```python
# models.py
class User: pass
class Notification: pass
```

**Correct:**
```python
# user.py
class User: pass

# notification.py
class Notification: pass

# __init__.py
from .user import User
from .notification import Notification
```

### 4. NO MIGRATIONS
All models are unmanaged (`managed = False`). Never run `python manage.py makemigrations` or `python manage.py migrate`. Schema changes must be coordinated with the database owner.

### 5. GOOGLE-STYLE DOCSTRINGS
Use Google-style docstrings for all public functions, classes, and methods. Ruff is configured to enforce this (`convention = "google"`).

### 6. STRUCTLOG LOGGING
Use `structlog` for structured logging, not Django's logging. Example:
```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("event_description", key1="value1", key2="value2")
```

## Environment Configuration

Create `.env.local` from `.env.example` for local development. Key variables:
- Database: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_SCHEMA`, `NOTIFICATION_SERVICE_DB_USER`, `NOTIFICATION_SERVICE_DB_PASSWORD`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- Email: `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (Gmail app password)

For Kubernetes: Environment variables are provided via ConfigMap and Secrets.

## Testing

Tests are in `tests/` organized by type: `unit/`, `component/`, `dependency/`, `performance/`. Use pytest fixtures from `tests/conftest.py`.

## Common Patterns

### Creating a New Notification Type
1. Add Pydantic request/response schemas in `core/schemas/notification/`
2. Add business logic method in appropriate service (`recipe_notification_service.py`, etc.)
3. Add API view in `core/views.py`
4. Add URL route in `core/urls.py`
5. Add component tests in `tests/component/`

### Adding a New Service
1. Create service file in `core/services/`
2. Export from `core/services/__init__.py`
3. Follow dependency injection pattern

## Kubernetes

The service runs in namespace `notification-service` with Kong Gateway routing at `http://sous-chef-proxy.local/api/v1/notification/`. The RQ worker runs as a separate deployment.
