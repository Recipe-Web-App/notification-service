# Notification Service

A Django-based notification service API for the recipe web app.

## Prerequisites

- Python 3.14
- Poetry
- Docker (for containerized deployment)
- Minikube & kubectl (for Kubernetes deployment)

## Setup

1. Install dependencies:
```bash
poetry install
```

2. Run migrations:
```bash
poetry run python manage.py migrate
```

## Running Locally

### Development Server

Start the development server:
```bash
poetry run local
```

The server will start at `http://localhost:8000`

### Production (Gunicorn)

For production-like environment:
```bash
poetry run gunicorn notification_service.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## Features

### Email Notification System

The notification service provides a reliable email notification system with the following features:

- **Queue-based delivery**: Uses Django-RQ with Redis for reliable async email sending
- **SMTP support**: Full HTML email support with CSS styling via Gmail SMTP
- **Automatic retries**: Exponential backoff retry logic (up to 3 attempts)
- **Full audit trail**: All notifications persisted with status tracking
- **Django signals**: Automatic notifications triggered by database events
- **Email templates**: Django template system for HTML emails

#### Architecture

1. **Notification Model**: Tracks all notifications with status (pending, queued, sent, failed)
2. **Email Service**: Handles SMTP email sending with retry logic
3. **Notification Service**: High-level API for creating and managing notifications
4. **Background Jobs**: Async email sending via RQ workers
5. **Django Signals**: Auto-trigger notifications (e.g., welcome email on user creation)

#### Email Configuration

Only 2 environment variables required:
- `EMAIL_HOST_USER`: Your Gmail address
- `EMAIL_HOST_PASSWORD`: Gmail app-specific password

All other settings (SMTP host, port, TLS) are hardcoded in configuration.

#### Starting the RQ Worker

For email notifications to be sent, you must run the RQ worker:

```bash
# Development
poetry run python -m django_rq.management.commands.rqworker default

# Docker Compose (automatic)
docker-compose up rq-worker
```

The worker processes queued email jobs from Redis.

#### Notification Workflow

1. Create notification via `NotificationService.create_notification()`
2. Notification is saved to database with `status=PENDING`
3. Notification is queued to Django-RQ (status changes to `QUEUED`)
4. RQ worker picks up job and sends email via SMTP
5. On success: `status=SENT`, `sent_at` timestamp set
6. On failure: Retry with exponential backoff (5min, 10min, 20min)
7. After 3 failed attempts: `status=FAILED`, `error_message` set

#### Email Templates

Templates located in `templates/emails/`:
- `base.html`: Base template with styling
- `welcome.html`: Welcome email for new users
- `notification.html`: Generic notification template

## API Endpoints

All API endpoints are prefixed with `/api/v1/notification/`

### Health Check Endpoints

#### Readiness Probe
- **URL**: `/api/v1/notification/health/ready`
- **Method**: `GET`
- **Response**: `{"status": "ready", "database": "connected"}` or `{"status": "not ready", "database": "disconnected"}`
- **Description**: Kubernetes readiness probe - checks database connectivity

#### Liveness Probe
- **URL**: `/api/v1/notification/health/live`
- **Method**: `GET`
- **Response**: `{"status": "alive"}`
- **Description**: Kubernetes liveness probe - simple alive check

### Examples

```bash
# Local development
curl http://localhost:8000/api/v1/notification/health/ready
curl http://localhost:8000/api/v1/notification/health/live

# Kubernetes (after deployment)
curl http://notification-service.local/api/v1/notification/health/ready
curl http://notification-service.local/api/v1/notification/health/live
```

## Kubernetes Deployment

### Prerequisites

- Minikube installed and running
- kubectl configured
- Docker installed

### Environment Configuration

This project uses two separate environment files depending on your use case:

#### For Local Development

1. Copy the example environment file:
```bash
cp .env.example .env.local
```

2. Update `.env.local` with your local configuration:
```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=recipe_db
POSTGRES_SCHEMA=notifications

# Notification Service Database User
NOTIFICATION_SERVICE_DB_USER=notification_user
NOTIFICATION_SERVICE_DB_PASSWORD=your_secure_password_here
```

The Django application (`notification_service/settings.py`) will automatically load `.env.local` when running locally.

#### For Container/Kubernetes Deployment

1. Copy the example environment file:
```bash
cp .env.example .env.prod
```

2. Update `.env.prod` with your production/container configuration. This file is sourced by the container management scripts (`scripts/containerManagement/`) to populate Kubernetes ConfigMaps and Secrets.

**Note**: In production Kubernetes deployments, environment variables are provided via ConfigMap and Secrets. The `.env.prod` file is only used by deployment scripts to generate these resources.

### Container Management Scripts

All scripts are located in `scripts/containerManagement/`:

#### Deploy
Full deployment (build, apply manifests, wait for ready):
```bash
./scripts/containerManagement/deploy-container.sh
```

#### Update
Update running deployment with new code:
```bash
./scripts/containerManagement/update-container.sh
```

#### Check Status
Comprehensive status dashboard:
```bash
./scripts/containerManagement/get-container-status.sh
```

#### Start/Stop
```bash
# Start (scale to 1 replica)
./scripts/containerManagement/start-container.sh

# Stop (scale to 0 replicas)
./scripts/containerManagement/stop-container.sh
```

#### Cleanup
Remove all Kubernetes resources:
```bash
./scripts/containerManagement/cleanup-container.sh
```

### Accessing the Service

After deployment, the service is accessible at:
- **Ingress URL**: `http://notification-service.local/api/v1/notification/`
- **Health Checks**:
  - Readiness: `http://notification-service.local/api/v1/notification/health/ready`
  - Liveness: `http://notification-service.local/api/v1/notification/health/live`

### Kubernetes Resources

The deployment includes:
- **Namespace**: `notification-service`
- **Deployment**: Django app with gunicorn (4 workers, 2 threads)
- **Service**: ClusterIP on port 8000
- **Ingress**: Routes `/api/v1/notification` to service
- **ConfigMap**: Database configuration
- **Secret**: Database password
- **NetworkPolicy**: Security policies for ingress/egress

### Health Probes Configuration

- **Readiness Probe**: Checks `/api/v1/notification/health/ready` every 10s
- **Liveness Probe**: Checks `/api/v1/notification/health/live` every 60s
- **Startup Probe**: Checks `/api/v1/notification/health/ready` during startup

## Development

### Pre-commit Hooks

This project uses pre-commit hooks for code quality. See `.pre-commit-setup.md` for details.

Install hooks:
```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

### Running Tests

```bash
# All tests
poetry run test-all

# Unit tests
poetry run test-unit

# Component tests
poetry run test-component

# Performance tests
poetry run test-performance
```
