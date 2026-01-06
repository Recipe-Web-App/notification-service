# Testing Documentation

## Overview

This document provides a high-level overview of the testing strategy for the notification service. Our testing approach is comprehensive and covers multiple layers of the application to ensure reliability, correctness, and performance.

## Testing Philosophy

We follow a multi-layered testing strategy that balances speed, confidence, and maintainability:

1. **Fast, focused unit tests** for pure logic
2. **Isolated component tests** for business logic with mocked dependencies
3. **Realistic dependency tests** for integration validation
4. **Performance tests** to ensure system scalability

## Test Types

We implement four distinct types of tests, each serving a specific purpose:

| Test Type | Purpose | Speed | Dependencies |
|-----------|---------|-------|--------------|
| **Unit** | Test pure functions and isolated logic | Very Fast | None |
| **Component** | Test business logic with mocked I/O | Fast | Mocked |
| **Dependency** | Test real external service integrations | Slow | Real services |
| **Performance** | Test system performance and scalability | Slow | Real/simulated load |

### Detailed Documentation

For comprehensive information about each test type, see:

- [Unit Testing](./UNIT-TESTING.md)
- [Component Testing](./COMPONENT-TESTING.md)
- [Dependency Testing](./DEPENDENCY-TESTING.md)
- [Performance Testing](./PERFORMANCE-TESTING.md)

## Directory Structure

```
tests/
├── __init__.py
├── unit/                    # Pure function and utility tests
│   ├── __init__.py
│   └── test_*.py
├── component/               # Business logic tests with mocked I/O
│   ├── __init__.py
│   └── test_*.py
├── dependency/              # Real external service integration tests
│   ├── __init__.py
│   └── test_*.py
├── performance/             # Locust performance and load tests
│   ├── __init__.py
│   └── locustfile_*.py
├── fixtures/                # Shared test fixtures and data
│   ├── __init__.py
│   └── *.json
├── factories/               # Factory Boy factories for test data
│   ├── __init__.py
│   └── *.py
└── conftest.py             # Pytest configuration and shared fixtures
```

## Running Tests

### Quick Commands

```bash
# Run all tests
poetry run test-all

# Run specific test types
poetry run test-unit
poetry run test-component
poetry run test-dependency
poetry run test-performance

# Run with coverage report
poetry run test-coverage
```

### Detailed Test Execution

#### Unit Tests
```bash
poetry run test-unit
```
Fast tests for pure functions and isolated logic. Should complete in seconds.

#### Component Tests
```bash
poetry run test-component
```
Tests business logic with all external dependencies mocked. Should complete in under a minute.

#### Dependency Tests
```bash
poetry run test-dependency
```
Integration tests with real external services (database, message queues, etc.). Requires Docker.

#### Performance Tests
```bash
poetry run test-performance
```
Runs Locust load tests against the service. Generates performance reports.

#### All Tests
```bash
poetry run test-all
```
Runs unit, component, and dependency tests in sequence. Performance tests run separately.

#### Coverage Reports
```bash
poetry run test-coverage
```
Runs all tests with coverage tracking and generates an HTML report in `htmlcov/`.

## Quality Gates

### Coverage Requirements

- **Minimum overall coverage**: 80%
- **Critical path coverage**: 95%
- **New code coverage**: 90%

### Test Execution Requirements

- All unit and component tests must pass before merge
- Dependency tests must pass in CI/CD pipeline
- Performance tests must not regress beyond defined baselines

## CI/CD Integration

Tests run automatically in GitHub Actions:

- **On Pull Request**: Unit + Component tests (fast feedback)
- **On Merge to Main**: All test types including dependency tests
- **Nightly**: Full test suite + performance regression tests

See `.github/workflows/tests.yml` for configuration details.

## Best Practices

### General Guidelines

1. **Write tests first** when fixing bugs (TDD for bug fixes)
2. **Keep tests independent** - tests should not depend on execution order
3. **Use descriptive names** - test names should describe what they test
4. **Follow AAA pattern** - Arrange, Act, Assert
5. **One assertion per test** when possible (or related assertions)
6. **Mock external dependencies** in component tests
7. **Use factories** for test data creation

### Test Naming Convention

```python
def test_<function_name>_<scenario>_<expected_result>(self):
    """Test description."""
    pass

# Examples:
def test_send_notification_with_valid_data_succeeds(self):
def test_send_notification_with_invalid_email_raises_error(self):
def test_get_notification_status_when_not_found_returns_404(self):
```

### Code Quality

- Tests should be as readable as production code
- Avoid complex logic in tests
- Extract common setup to fixtures or setUp methods
- Keep tests DRY but prefer clarity over brevity

## Common Testing Tools

### Core Framework

- **Django's unittest**: Built-in test framework with TestCase classes
- **factory-boy**: Object factory for test data generation
- **faker**: Realistic fake data generation

### Mocking & Isolation

- **unittest.mock**: Python's built-in mocking library
- **responses**: Mock HTTP requests/responses
- **freezegun**: Time-travel for time-dependent tests

### Integration & Dependencies

- **testcontainers**: Dockerized dependencies (PostgreSQL, Redis, LocalStack)

### Performance

- **locust**: Load testing and performance validation
- Custom performance assertion utilities

## Getting Help

- Review test-type-specific documentation in this directory
- Check existing tests for examples
- Ask the team in `#engineering` Slack channel

## Related Documentation

- [Contributing Guidelines](../../.github/CONTRIBUTING.md)
- [OpenAPI Specification](../openapi.yaml)
