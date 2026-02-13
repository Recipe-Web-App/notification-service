"""Test runner scripts for uv commands."""

import subprocess
import sys


def run_command(command):
    """Run a shell command and return exit code."""
    result = subprocess.run(command, check=False, shell=True)
    return result.returncode


def run_all():
    """Run all tests (unit, component, dependency)."""
    print("Running all tests...")
    exit_code = run_command(
        "python manage.py test tests.unit tests.component tests.dependency "
        "--settings=notification_service.settings_test"
    )
    sys.exit(exit_code)


def run_unit():
    """Run unit tests only."""
    print("Running unit tests...")
    exit_code = run_command(
        "python manage.py test tests.unit --settings=notification_service.settings_test"
    )
    sys.exit(exit_code)


def run_component():
    """Run component tests only."""
    print("Running component tests...")
    exit_code = run_command(
        "python manage.py test tests.component "
        "--settings=notification_service.settings_test"
    )
    sys.exit(exit_code)


def run_dependency():
    """Run dependency tests only."""
    print("Running dependency tests...")
    exit_code = run_command(
        "python manage.py test tests.dependency "
        "--settings=notification_service.settings_test"
    )
    sys.exit(exit_code)


def run_performance():
    """Run performance tests with Locust in headless mode."""
    print("Running performance tests...")
    exit_code = run_command(
        "locust -f tests/performance/locustfile_notifications.py "
        "--headless --users 10 --spawn-rate 2 --run-time 10s "
        "--host=http://localhost:8000"
    )
    sys.exit(exit_code)


def run_coverage():
    """Run tests with coverage report."""
    print("Running tests with coverage...")
    commands = [
        "coverage erase",
        (
            "coverage run --source='.' manage.py test "
            "tests.unit tests.component tests.dependency "
            "--settings=notification_service.settings_test"
        ),
        "coverage report",
        "coverage html",
    ]

    for cmd in commands:
        exit_code = run_command(cmd)
        if exit_code != 0:
            sys.exit(exit_code)

    print("\nCoverage HTML report generated in htmlcov/")
    print("Open htmlcov/index.html in a browser to view")
    sys.exit(0)
