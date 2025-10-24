# Notification Service

A Django-based notification service API for the recipe web app.

## Prerequisites

- Python 3.14
- Poetry

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

Start the development server:
```bash
poetry run local
```

The server will start at `http://localhost:8000`

## API Endpoints

### Health Check
- **URL**: `/health/`
- **Method**: `GET`
- **Response**: `{"status": "ok"}`

Example:
```bash
curl http://localhost:8000/health/
```
