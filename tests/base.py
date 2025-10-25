"""Base test classes for different test types."""

from django.test import TestCase, TransactionTestCase


class BaseUnitTest(TestCase):
    """Base class for unit tests.

    Use this for tests that don't require database access or use
    SQLite in-memory for fast isolated testing.
    """

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        super().setUpClass()

    def setUp(self):
        """Set up test fixtures."""
        pass

    def tearDown(self):
        """Clean up after test."""
        pass


class BaseComponentTest(TestCase):
    """Base class for component tests.

    Use this for tests that mock external dependencies and test
    business logic with SQLite in-memory database.
    """

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        super().setUpClass()

    def setUp(self):
        """Set up test fixtures and mocks."""
        # Set up common mocks here
        pass

    def tearDown(self):
        """Clean up after test."""
        pass


class BaseDependencyTest(TransactionTestCase):
    """Base class for dependency tests.

    Use this for tests that interact with real dependencies like
    PostgreSQL, Redis, or LocalStack services from docker-compose.test.yml.

    Note: These tests should be run with PostgreSQL configured, not SQLite.
    """

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures and containers."""
        super().setUpClass()
        # Container setup will go here

    @classmethod
    def tearDownClass(cls):
        """Clean up containers."""
        super().tearDownClass()

    def setUp(self):
        """Set up test fixtures."""
        pass

    def tearDown(self):
        """Clean up after test."""
        pass
