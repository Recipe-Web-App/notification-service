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

## API Endpoints

All API endpoints are prefixed with `/api/v1/notification/`

### Health Check Endpoints

#### General Health
- **URL**: `/api/v1/notification/health/`
- **Method**: `GET`
- **Response**: `{"status": "ok"}`
- **Description**: Basic health check endpoint

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
curl http://localhost:8000/api/v1/notification/health/
curl http://localhost:8000/api/v1/notification/health/ready
curl http://localhost:8000/api/v1/notification/health/live

# Kubernetes (after deployment)
curl http://notification-service.local/api/v1/notification/health/
```

## Kubernetes Deployment

### Prerequisites

- Minikube installed and running
- kubectl configured
- Docker installed

### Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Update `.env` with your configuration:
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
- **Health Check**: `http://notification-service.local/api/v1/notification/health/`

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
