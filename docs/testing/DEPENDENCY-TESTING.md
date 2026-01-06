# Dependency Testing

## Overview

Dependency tests (also called integration tests) verify that your application correctly integrates with real external services and dependencies. Unlike component tests which mock everything, dependency tests use actual databases, message queues, caches, and external APIs to validate end-to-end functionality.

These tests provide:
- **Confidence in integration** - Verify real service interactions
- **Contract validation** - Ensure external APIs work as expected
- **Configuration verification** - Validate connection settings and credentials
- **End-to-end flow testing** - Test complete request-to-response cycles

## What to Test

Dependency tests should cover:

- **Database operations** - Queries, transactions, migrations, constraints
- **Message queue operations** - Publishing, consuming, dead-letter handling
- **Cache operations** - Get, set, expiration, invalidation
- **External API integrations** - Auth service, email, SMS, push notification APIs
- **File storage** - S3 or local file operations
- **Full request flows** - End-to-end API request through all layers

## When to Use Dependency Tests

Use dependency tests when:
- Testing database schema and complex queries
- Validating external API contracts
- Testing transaction handling and rollback
- Verifying message queue behavior
- Testing cache invalidation strategies
- Debugging integration issues

## Directory Structure

```
tests/dependency/
├── __init__.py
├── test_database_operations.py      # Database integration tests
├── test_message_queue.py            # SQS/RabbitMQ/Kafka tests
├── test_cache_operations.py         # Redis/cache tests
├── test_auth_service.py             # Auth service integration
├── test_email_service.py            # Email API integration
├── test_sms_service.py              # SMS API integration
├── test_push_service.py             # Push notification integration
└── test_end_to_end_flows.py         # Complete request flows
```

## Infrastructure Setup

Dependency tests require real services. Use Docker containers managed by testcontainers:

### Docker Compose for Test Dependencies

Tests will automatically start required containers using testcontainers. See `docker-compose.test.yml` for service definitions.

## Writing Dependency Tests

### Database Integration Tests

```python
from django.test import TestCase, TransactionTestCase
from core.models import Notification, NotificationLog


class TestNotificationDatabaseOperations(TransactionTestCase):
    """Tests for notification database operations.

    Note: Use TransactionTestCase for tests that need transaction control.
    """

    def test_create_notification_persists_to_database(self):
        """Test that creating notification saves to database."""
        # Arrange
        notification_data = {
            'recipient': 'user@example.com',
            'message': 'Test message',
            'type': 'email',
            'status': 'pending'
        }

        # Act
        notification = Notification.objects.create(**notification_data)

        # Assert
        self.assertIsNotNone(notification.id)
        saved_notification = Notification.objects.get(id=notification.id)
        self.assertEqual(saved_notification.recipient, 'user@example.com')
        self.assertEqual(saved_notification.message, 'Test message')

    def test_update_notification_status_persists(self):
        """Test that updating notification status is persisted."""
        # Arrange
        notification = Notification.objects.create(
            recipient='user@example.com',
            message='Test',
            type='email',
            status='pending'
        )

        # Act
        notification.status = 'sent'
        notification.save()

        # Assert
        updated = Notification.objects.get(id=notification.id)
        self.assertEqual(updated.status, 'sent')

    def test_cascade_delete_removes_related_logs(self):
        """Test that deleting notification cascades to logs."""
        # Arrange
        notification = Notification.objects.create(
            recipient='user@example.com',
            message='Test',
            type='email'
        )
        NotificationLog.objects.create(
            notification=notification,
            event='created',
            details='Initial creation'
        )

        # Act
        notification.delete()

        # Assert
        self.assertEqual(NotificationLog.objects.count(), 0)

    def test_transaction_rollback_on_error(self):
        """Test that database transaction rolls back on error."""
        from django.db import transaction

        initial_count = Notification.objects.count()

        # Act & Assert
        with self.assertRaises(ValueError):
            with transaction.atomic():
                Notification.objects.create(
                    recipient='user@example.com',
                    message='Test',
                    type='email'
                )
                raise ValueError('Simulated error')

        # Verify rollback
        self.assertEqual(Notification.objects.count(), initial_count)
```

### Message Queue Integration Tests

```python
import boto3
from django.test import TestCase
from testcontainers.localstack import LocalStackContainer
from core.services.queue_service import QueueService


class TestSQSIntegration(TestCase):
    """Tests for SQS message queue integration."""

    @classmethod
    def setUpClass(cls):
        """Set up LocalStack container for SQS."""
        super().setUpClass()
        cls.localstack = LocalStackContainer(image="localstack/localstack:latest")
        cls.localstack.with_services("sqs")
        cls.localstack.start()

        # Configure boto3 to use LocalStack
        cls.sqs_client = boto3.client(
            'sqs',
            endpoint_url=cls.localstack.get_url(),
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )

        # Create test queue
        response = cls.sqs_client.create_queue(QueueName='test-notifications')
        cls.queue_url = response['QueueUrl']

    @classmethod
    def tearDownClass(cls):
        """Stop LocalStack container."""
        cls.localstack.stop()
        super().tearDownClass()

    def test_send_message_to_queue_succeeds(self):
        """Test sending message to SQS queue."""
        # Arrange
        queue_service = QueueService(
            queue_url=self.queue_url,
            sqs_client=self.sqs_client
        )
        message_body = {
            'notification_id': 123,
            'type': 'email',
            'recipient': 'user@example.com'
        }

        # Act
        result = queue_service.send_message(message_body)

        # Assert
        self.assertTrue(result['success'])
        self.assertIn('MessageId', result)

    def test_receive_message_from_queue_returns_message(self):
        """Test receiving message from SQS queue."""
        # Arrange
        queue_service = QueueService(
            queue_url=self.queue_url,
            sqs_client=self.sqs_client
        )
        test_message = {'notification_id': 456, 'type': 'sms'}
        queue_service.send_message(test_message)

        # Act
        messages = queue_service.receive_messages(max_messages=1)

        # Assert
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['notification_id'], 456)

    def test_message_visibility_timeout_works(self):
        """Test that message visibility timeout prevents duplicate processing."""
        # Arrange
        queue_service = QueueService(
            queue_url=self.queue_url,
            sqs_client=self.sqs_client
        )
        queue_service.send_message({'notification_id': 789})

        # Act - First receive
        messages1 = queue_service.receive_messages(
            max_messages=1,
            visibility_timeout=5
        )

        # Immediately try to receive again
        messages2 = queue_service.receive_messages(max_messages=1)

        # Assert
        self.assertEqual(len(messages1), 1)
        self.assertEqual(len(messages2), 0)  # Should be invisible
```

### Cache Integration Tests

```python
from django.test import TestCase
from django.core.cache import cache
from testcontainers.redis import RedisContainer
from core.services.cache_service import CacheService


class TestRedisIntegration(TestCase):
    """Tests for Redis cache integration."""

    @classmethod
    def setUpClass(cls):
        """Set up Redis container."""
        super().setUpClass()
        cls.redis_container = RedisContainer("redis:7-alpine")
        cls.redis_container.start()

        # Configure Django cache to use test Redis
        cls.redis_url = cls.redis_container.get_connection_url()

    @classmethod
    def tearDownClass(cls):
        """Stop Redis container."""
        cls.redis_container.stop()
        super().tearDownClass()

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_set_and_get_works(self):
        """Test basic cache set and get operations."""
        # Act
        cache.set('test_key', 'test_value', timeout=60)
        result = cache.get('test_key')

        # Assert
        self.assertEqual(result, 'test_value')

    def test_cache_expiration_removes_key(self):
        """Test that cache keys expire correctly."""
        import time

        # Arrange
        cache.set('temp_key', 'temp_value', timeout=1)

        # Act
        time.sleep(2)
        result = cache.get('temp_key')

        # Assert
        self.assertIsNone(result)

    def test_cache_invalidation_removes_pattern(self):
        """Test invalidating multiple keys by pattern."""
        # Arrange
        cache.set('user:123:profile', 'profile_data')
        cache.set('user:123:settings', 'settings_data')
        cache.set('user:456:profile', 'other_profile')

        cache_service = CacheService()

        # Act
        cache_service.invalidate_pattern('user:123:*')

        # Assert
        self.assertIsNone(cache.get('user:123:profile'))
        self.assertIsNone(cache.get('user:123:settings'))
        self.assertIsNotNone(cache.get('user:456:profile'))
```

### External API Integration Tests

```python
import os
from django.test import TestCase
from core.services.auth_service import AuthService
from core.services.email_service import EmailService


class TestAuthServiceIntegration(TestCase):
    """Tests for auth service API integration.

    Note: These tests require the auth service to be running.
    Set TEST_AUTH_SERVICE_URL environment variable.
    """

    def setUp(self):
        """Set up auth service client."""
        auth_url = os.getenv('TEST_AUTH_SERVICE_URL', 'http://localhost:8001')
        self.auth_service = AuthService(base_url=auth_url)

    def test_validate_token_with_valid_token_returns_user(self):
        """Test that valid token returns user information."""
        # Arrange
        # This assumes you have a test token from the auth service
        test_token = self._get_test_token()

        # Act
        result = self.auth_service.validate_token(test_token)

        # Assert
        self.assertTrue(result['valid'])
        self.assertIn('user_id', result)

    def test_validate_token_with_invalid_token_returns_error(self):
        """Test that invalid token returns error."""
        # Act
        result = self.auth_service.validate_token('invalid-token')

        # Assert
        self.assertFalse(result['valid'])

    def _get_test_token(self):
        """Helper to get a valid test token."""
        # Implementation depends on your auth service test setup
        return os.getenv('TEST_AUTH_TOKEN', 'test-token')


class TestEmailServiceIntegration(TestCase):
    """Tests for email service API integration.

    Note: These tests require email service credentials.
    Use test/sandbox mode for the email provider.
    """

    def setUp(self):
        """Set up email service client."""
        self.email_service = EmailService(
            api_key=os.getenv('TEST_EMAIL_API_KEY'),
            sandbox_mode=True
        )

    def test_send_email_with_valid_data_succeeds(self):
        """Test sending email through real API."""
        # Act
        result = self.email_service.send_email(
            to='test@example.com',
            subject='Test Email',
            body='This is a test email',
            from_email='notifications@example.com'
        )

        # Assert
        self.assertTrue(result['success'])
        self.assertIn('message_id', result)

    def test_send_email_with_invalid_recipient_fails(self):
        """Test that invalid recipient returns error."""
        # Act
        result = self.email_service.send_email(
            to='invalid-email',
            subject='Test',
            body='Test',
            from_email='notifications@example.com'
        )

        # Assert
        self.assertFalse(result['success'])
        self.assertIn('error', result)
```

### End-to-End Flow Tests

```python
from django.test import TestCase, Client
from django.urls import reverse
from core.models import Notification


class TestNotificationEndToEndFlow(TestCase):
    """End-to-end tests for complete notification flows."""

    def setUp(self):
        """Set up test client and dependencies."""
        self.client = Client()
        # Assume test dependencies (DB, queue, cache) are available

    def test_create_and_send_notification_complete_flow(self):
        """Test complete flow from creation to sending."""
        # Step 1: Create notification via API
        response = self.client.post(
            reverse('notification-create'),
            data={
                'recipient': 'user@example.com',
                'message': 'Test notification',
                'type': 'email'
            },
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer test-token'
        )

        # Assert creation
        self.assertEqual(response.status_code, 201)
        notification_id = response.json()['id']

        # Step 2: Verify database persistence
        notification = Notification.objects.get(id=notification_id)
        self.assertEqual(notification.status, 'queued')

        # Step 3: Process notification (simulate worker)
        from core.workers.notification_worker import process_notification
        result = process_notification(notification_id)

        # Assert processing
        self.assertTrue(result['success'])

        # Step 4: Verify status update
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')

        # Step 5: Verify via API
        response = self.client.get(
            reverse('notification-detail', kwargs={'pk': notification_id}),
            HTTP_AUTHORIZATION='Bearer test-token'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'sent')
```

## Test Data Management

### Database Fixtures

```python
from django.test import TestCase
from tests.factories import NotificationFactory


class TestWithFixtures(TestCase):
    """Tests using database fixtures."""

    fixtures = ['test_users.json', 'test_notifications.json']

    def test_fixture_data_loaded(self):
        """Test that fixtures are loaded correctly."""
        notification = Notification.objects.get(pk=1)
        self.assertEqual(notification.recipient, 'fixture@example.com')
```

### Using Factories

```python
from django.test import TestCase
from tests.factories import NotificationFactory, UserFactory


class TestWithFactories(TestCase):
    """Tests using factory-generated data."""

    def test_create_notification_with_factory(self):
        """Test using factory to create test data."""
        # Arrange
        user = UserFactory(email='user@example.com')
        notification = NotificationFactory(
            recipient=user.email,
            type='email'
        )

        # Act
        notification.save()

        # Assert
        self.assertEqual(Notification.objects.count(), 1)
```

## Best Practices

### DO

- Use testcontainers for isolated test dependencies
- Clean up test data after each test
- Use transactions for database rollback
- Test both success and failure scenarios
- Verify external API contracts
- Use test/sandbox modes for external services
- Test edge cases (timeouts, connection failures)
- Document required environment variables

### DON'T

- Depend on production services
- Leave test data in databases
- Share state between tests
- Hard-code credentials (use environment variables)
- Make tests dependent on external service availability
- Skip cleanup in tearDown
- Test too many things in one test

## Running Dependency Tests

```bash
# Run all dependency tests
poetry run test-dependency

# Run specific test file
poetry run pytest tests/dependency/test_database_operations.py -v

# Run with test containers (automatic)
poetry run test-dependency

# Run specific integration
poetry run pytest tests/dependency/test_auth_service.py -v
```

## Environment Configuration

Dependency tests require environment configuration:

```bash
# Required environment variables
export TEST_AUTH_SERVICE_URL=http://localhost:8001
export TEST_EMAIL_API_KEY=test_key_sandbox
export TEST_SMS_API_KEY=test_key_sandbox
export TEST_PUSH_API_KEY=test_key_sandbox

# Optional - testcontainers will auto-start these
export TEST_POSTGRES_URL=postgresql://localhost:5432/test_db
export TEST_REDIS_URL=redis://localhost:6379/0
export TEST_SQS_ENDPOINT=http://localhost:4566
```

## Coverage Goals

Dependency tests should achieve:
- **80%+ coverage** for database operations
- **70%+ coverage** for external API integrations
- **100% coverage** for critical integration paths

## Troubleshooting

### Common Issues

**Tests are slow**
- Use testcontainers efficiently (class-level setup)
- Limit scope of dependency tests
- Run dependency tests less frequently (CI only)

**Flaky tests**
- Add retries for external API calls
- Increase timeouts
- Verify test isolation

**Container startup failures**
- Ensure Docker is running
- Check available ports
- Increase container startup timeout

## Related Documentation

- [Testing Overview](./TESTING.md)
- [Unit Testing](./UNIT-TESTING.md)
- [Component Testing](./COMPONENT-TESTING.md)
- [Performance Testing](./PERFORMANCE-TESTING.md)
- [testcontainers Documentation](https://testcontainers-python.readthedocs.io/)
- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
