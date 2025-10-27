# VS Code IDE Configuration

This directory contains VS Code IDE settings optimized for Django development with this project.

## Contents

- **`settings.json`** - Workspace settings for Python, Django, Ruff, mypy, and editor preferences
- **`launch.json`** - Debug configurations for Django, pytest, and Docker
- **`tasks.json`** - Task runners for development, testing, and code quality
- **`extensions.json`** - Recommended VS Code extensions
- **`snippets/django.code-snippets`** - Django/DRF code snippets
- **`.env.debug`** - Environment variables for debugging sessions

## Quick Start

### 1. Install Recommended Extensions

When you open this project in VS Code, you'll be prompted to install recommended extensions. Click "Install All" or manually install them from the Extensions view.

**Essential extensions:**
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)
- Django (batisteo.vscode-django)

### 2. Configure Python Interpreter

1. Press `Cmd/Ctrl + Shift + P`
2. Type "Python: Select Interpreter"
3. Choose the Poetry virtual environment (`.venv/bin/python`)

### 3. Run the Development Server

**Option A: Using Tasks (Recommended)**
1. Press `Cmd/Ctrl + Shift + P`
2. Type "Tasks: Run Task"
3. Select "Django: Run Local Server"

**Option B: Using Debug Configuration**
1. Open the Run and Debug view (`Cmd/Ctrl + Shift + D`)
2. Select "Django: Run Server (Development)" from the dropdown
3. Press F5 or click the green play button

## Debug Configurations

### Django Development

- **Django: Run Server (Development)** - Standard development server
- **Django: Run Server (Test Settings)** - Server with test settings
- **Django: Run Local (run_local.py)** - Custom local runner
- **Django: Management Command** - Run any Django management command
- **Django: Migrate** - Run database migrations
- **Django: Make Migrations** - Create new migrations
- **Django: Shell** - Open Django shell

### Testing & Debugging

- **Pytest: All Tests** - Run entire test suite with debugger
- **Pytest: Current File** - Debug tests in current file
- **Pytest: Current Test at Cursor** - Debug specific test (select test name first)
- **Pytest: Unit Tests** - Run only unit tests
- **Pytest: Component Tests** - Run component tests
- **Pytest: Dependency Tests** - Run dependency tests
- **Pytest: With Coverage** - Run tests with coverage report

### Docker Debugging

- **Docker: Attach to Django** - Attach debugger to running Django container
  - Requires debugpy installed and listening on port 5678
  - Configure your Dockerfile to enable remote debugging

## Available Tasks

Access tasks via `Cmd/Ctrl + Shift + P` → "Tasks: Run Task"

### Development Tasks
- Django: Run Local Server
- Django: Run Server
- Django: Shell
- Django: Make Migrations
- Django: Migrate
- Django: Show Migrations

### Testing Tasks
- Test: Run All Tests
- Test: Unit Tests
- Test: Component Tests
- Test: Dependency Tests
- Test: Performance Tests
- Test: With Coverage
- Test: Open Coverage Report

### Code Quality Tasks
- Lint: Ruff Check
- Lint: Ruff Fix
- Format: Ruff Format
- Format: isort
- Type Check: mypy
- Security: Bandit
- Pre-commit: Run All Hooks

### Docker Tasks
- Docker: Compose Up
- Docker: Compose Down
- Docker: Compose Restart
- Docker: View Logs
- Docker: Rebuild

### Dependency Tasks
- Poetry: Install Dependencies
- Poetry: Update Dependencies
- Poetry: Show Outdated

## Code Snippets

Type these prefixes and press `Tab` to insert code snippets:

### Django Models & Serializers
- `dj-model` - Complete Django model with Meta class
- `dj-field` - Django model field
- `drf-serializer` - DRF ModelSerializer
- `drf-base-serializer` - DRF base Serializer

### Views & ViewSets
- `drf-viewset` - DRF ModelViewSet
- `drf-apiview` - DRF APIView
- `dj-view-func` - Django function-based view

### Pydantic Schemas
- `pydantic-schema` - Pydantic BaseModel schema
- `pydantic-field` - Pydantic field with validation

### Repository & Service Patterns
- `repo-class` - Repository pattern class
- `service-class` - Service pattern class

### Testing
- `pytest-test` - Pytest test class
- `pytest-fixture` - Pytest fixture

### Other
- `dj-command` - Django management command
- `dj-admin` - Django admin registration
- `dj-url` - Django URL pattern
- `drf-router` - DRF router configuration
- `docstring` - Google-style docstring
- `type-checking` - TYPE_CHECKING import block

## Keyboard Shortcuts

### Debugging
- `F5` - Start debugging / Continue
- `Shift + F5` - Stop debugging
- `Ctrl/Cmd + Shift + F5` - Restart debugging
- `F9` - Toggle breakpoint
- `F10` - Step over
- `F11` - Step into
- `Shift + F11` - Step out

### Testing
- Test Explorer shows up in the sidebar (beaker icon)
- Click the play button next to any test to run/debug it
- Right-click for more options

### Code Navigation
- `F12` - Go to definition
- `Alt + F12` - Peek definition
- `Shift + F12` - Find all references
- `Ctrl/Cmd + Shift + O` - Go to symbol in file
- `Ctrl/Cmd + T` - Go to symbol in workspace

### Code Editing
- `Ctrl/Cmd + Space` - Trigger suggestions
- `Ctrl/Cmd + .` - Quick fix
- `Shift + Alt + F` - Format document
- `F2` - Rename symbol

## Settings Highlights

### Format on Save
Files are automatically formatted with Ruff when saved, and imports are organized automatically.

### Linting
Ruff runs on save with comprehensive rule sets configured in `pyproject.toml`.

### Type Checking
mypy is configured to run with Django support via django-stubs.

### Test Discovery
Tests are automatically discovered from the `tests/` directory using pytest.

## Customization

### Personal Settings
Create a `.vscode/settings.local.json` file for personal settings (git-ignored by default):
```json
{
  "python.defaultInterpreterPath": "/custom/path/to/python"
}
```

### Debug Environment Variables
Edit `.vscode/.env.debug` to add debug-specific environment variables.

### Additional Tasks
Add custom tasks to `.vscode/tasks.json` under the `tasks` array.

## Troubleshooting

### Python Interpreter Not Found
1. Ensure Poetry virtual environment is created: `poetry install`
2. Reload VS Code window: `Cmd/Ctrl + Shift + P` → "Developer: Reload Window"
3. Manually select interpreter: `Cmd/Ctrl + Shift + P` → "Python: Select Interpreter"

### Linting Not Working
1. Ensure Ruff extension is installed
2. Check Output panel (View → Output) and select "Ruff" from dropdown
3. Verify `pyproject.toml` exists with Ruff configuration

### Tests Not Discovered
1. Ensure pytest is installed: `poetry install --with test`
2. Reload tests: Test Explorer → Refresh button
3. Check Python Test Log: Output panel → "Python Test Log"

### Format on Save Not Working
1. Verify Ruff extension is installed and enabled
2. Check that `editor.formatOnSave` is `true` in settings
3. Ensure file is not excluded in settings

## Additional Resources

- [VS Code Python Documentation](https://code.visualstudio.com/docs/python/python-tutorial)
- [VS Code Django Tutorial](https://code.visualstudio.com/docs/python/tutorial-django)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
