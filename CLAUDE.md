# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Django-based notification service API for a recipe web app ecosystem. This service is a **read-only consumer** of a shared database - it does NOT own the schema. The service provides email notifications for recipe-related, social, and system events using a queue-based architecture with Redis and Django-RQ.

## Development Commands

### Environment Setup
```bash
# Install dependencies
poetry install

# Install pre-commit hooks
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

### Running Locally
```bash
# Start development server
poetry run local

# Start RQ worker (required for email sending)
poetry run python -m django_rq.management.commands.rqworker default

# Production-like server with gunicorn
poetry run gunicorn notification_service.wsgi:application --bind 0.0.0.0:8000 --workers 4
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

# With coverage
poetry run test-coverage
```

### Linting and Formatting
```bash
# Run ruff linter
poetry run ruff check core/
poetry run ruff check core/ --fix

# Run type checker
poetry run mypy core/

# Format code
poetry run ruff format core/

# Run pre-commit hooks manually
poetry run pre-commit run --all-files
```

### Kubernetes Deployment
All scripts are in `scripts/containerManagement/`:
```bash
# Full deployment (build, apply, wait)
./scripts/containerManagement/deploy-container.sh

# Update running deployment
./scripts/containerManagement/update-container.sh

# Check status
./scripts/containerManagement/get-container-status.sh

# Start/stop
./scripts/containerManagement/start-container.sh
./scripts/containerManagement/stop-container.sh

# Cleanup all resources
./scripts/containerManagement/cleanup-container.sh
```

## Architecture

### Core Principles

1. **Unmanaged Models**: This service does NOT own the database schema. All models have `managed = False` in their Meta class. Never run migrations or generate new migrations.

2. **Shared Database**: The service reads from a shared PostgreSQL database using a dedicated schema (`POSTGRES_SCHEMA` env var, typically `notifications`).

3. **Queue-Based Email**: Emails are sent asynchronously via Django-RQ workers. Jobs are queued to Redis, processed by background workers.

4. **OAuth2 Authentication**: Optional OAuth2 integration with the auth-service for protected endpoints (feature-flagged).

### Directory Structure

```
core/
├── models/          # Django ORM models (unmanaged, one class per file)
├── schemas/         # Pydantic schemas for validation (organized by feature)
├── services/        # Business logic layer
│   ├── notification_service.py        # Core notification logic
│   ├── recipe_notification_service.py # Recipe-related notifications
│   ├── social_notification_service.py # Social notifications (follows, mentions)
│   ├── system_notification_service.py # System notifications (password reset)
│   ├── admin_service.py               # Admin operations (stats, retries)
│   ├── email_service.py               # SMTP email sending
│   ├── health_service.py              # Health check logic
│   └── downstream/                    # External service clients
├── jobs/            # Django-RQ background jobs
├── signals/         # Django signals for event-driven notifications
├── middleware/      # Custom middleware (rate limiting, request ID, security)
├── auth/            # OAuth2 authentication
├── repositories/    # Data access layer
├── exceptions/      # Custom exceptions and handlers
├── constants/       # Application constants
└── enums/           # Enumeration types

notification_service/
├── settings.py      # Django settings (loads .env.local)
├── settings_test.py # Test settings
└── urls.py          # Root URL config
```

### Service Layer Pattern

The service layer is organized by domain:

- **notification_service.py**: Core notification CRUD operations
- **recipe_notification_service.py**: Recipe events (published, liked, commented)
- **social_notification_service.py**: Social events (new follower, mentions)
- **system_notification_service.py**: System events (password reset, welcome)
- **admin_service.py**: Admin operations (stats, retry failed notifications)

Each service encapsulates business logic and coordinates between repositories, jobs, and external services.

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

OAuth2 is optional and feature-flagged:
- `OAUTH2_SERVICE_ENABLED`: Enable OAuth2 authentication
- `OAUTH2_SERVICE_TO_SERVICE_ENABLED`: Enable service-to-service auth
- `OAUTH2_INTROSPECTION_ENABLED`: Use token introspection vs local JWT validation

Health check endpoints (`/health/live`, `/health/ready`) are exempt from authentication.

Middleware stack:
1. `RequestIDMiddleware`: Adds X-Request-ID for tracing
2. `ProcessTimeMiddleware`: Tracks request duration
3. `RateLimitMiddleware`: Rate limiting via Redis
4. `SecurityHeadersMiddleware`: Security headers
5. `SecurityContextMiddleware`: Stores authenticated user context

### Database Schema

The service uses a shared PostgreSQL database with dedicated schema. Key models:

- **Notification**: Core notification record with status tracking
- **User**: Read-only user data from shared database
- **UserFollow**: Read-only follow relationships

All models have `managed = False` - migrations are disabled via `MIGRATION_MODULES = DisableMigrations()` in settings.

### Health Checks

Two endpoints for Kubernetes:
- `/api/v1/notification/health/live`: Liveness probe (always returns 200)
- `/api/v1/notification/health/ready`: Readiness probe (checks database connectivity, returns degraded status if DB unavailable)

The readiness probe uses a degraded mode pattern - it returns 200 OK even when database is down, but indicates degraded status in response body. This prevents pod restarts while allowing background reconnection.

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

### Local Development
Create `.env.local` in the project root (use `.env.example` as template):
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=recipe_db
POSTGRES_SCHEMA=notifications
NOTIFICATION_SERVICE_DB_USER=notification_user
NOTIFICATION_SERVICE_DB_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Email (Gmail SMTP)
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/notification-service.log
```

### Production/Kubernetes
Environment variables are provided via ConfigMap and Secrets. The `.env.prod` file is only used by deployment scripts to generate K8s resources.

### Email Configuration
Only 2 environment variables required for email:
- `EMAIL_HOST_USER`: Gmail address
- `EMAIL_HOST_PASSWORD`: Gmail app-specific password

All other SMTP settings (host, port, TLS) are hardcoded in `settings.py`.

## Testing Strategy

Tests are organized by type:
- **unit/**: Fast, isolated tests with mocked dependencies
- **component/**: Integration tests for API endpoints
- **dependency/**: Tests for external dependencies (health checks)
- **performance/**: Locust-based load tests

Use pytest fixtures in `tests/conftest.py` for common setup. Mock external services (SMTP, Redis, database) in unit tests.

## Common Patterns

### Creating a New Notification Type
1. Add Pydantic request/response schemas in `core/schemas/notification/`
2. Add business logic method in appropriate service (`recipe_notification_service.py`, etc.)
3. Add API view in `core/views.py`
4. Add URL route in `core/urls.py`
5. Add component tests in `tests/component/`

### Adding a New Service
1. Create service file in `core/services/` (e.g., `new_service.py`)
2. Export from `core/services/__init__.py`
3. Follow dependency injection pattern (inject dependencies in constructor or as class-level singletons)

### Adding Middleware
1. Create middleware file in `core/middleware/`
2. Export from `core/middleware/__init__.py`
3. Add to `MIDDLEWARE` list in `settings.py` (order matters!)

## API Endpoint Structure

All endpoints are prefixed with `/api/v1/notification/`

Key endpoints:
- `GET /health/live`: Liveness probe
- `GET /health/ready`: Readiness probe
- `GET /templates`: List available notification templates
- `POST /notifications/recipe-published`: Create recipe published notification
- `POST /notifications/recipe-liked`: Create recipe liked notification
- `POST /notifications/recipe-commented`: Create recipe commented notification
- `POST /notifications/new-follower`: Create new follower notification
- `POST /notifications/mention`: Create mention notification
- `POST /notifications/password-reset`: Create password reset notification
- `GET /users/me/notifications`: Get authenticated user's notifications
- `GET /users/<user_id>/notifications`: Get user's notifications by ID
- `GET /stats`: Admin endpoint for notification statistics
- `POST /notifications/retry-failed`: Retry all failed notifications
- `POST /notifications/<id>/retry`: Retry specific notification

## Docker & Kubernetes

The service runs in Kubernetes (Minikube for local development):
- **Namespace**: `notification-service`
- **Deployment**: Django app with gunicorn (4 workers, 2 threads)
- **Service**: ClusterIP on port 8000
- **Ingress**: Routes `/api/v1/notification` to service (accessible at `http://sous-chef-proxy.local`)
- **ConfigMap**: Database and Redis configuration
- **Secret**: Sensitive credentials

The RQ worker runs as a separate deployment in the same namespace.

## Pre-commit Hooks

The project uses pre-commit hooks for code quality:
- ruff (linting)
- ruff-format (formatting)
- mypy (type checking)
- interrogate (docstring coverage)
- bandit (security)
- commitizen (commit message format)

See `.pre-commit-setup.md` for detailed configuration.
