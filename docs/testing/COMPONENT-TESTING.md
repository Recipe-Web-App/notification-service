# Component Testing

## Overview

Component tests verify business logic and API endpoints in isolation by mocking all external dependencies. These tests ensure that your application logic works correctly without requiring real databases, message queues, or external API services.

Component tests provide:
- **Fast execution** - No real I/O operations
- **Reliable results** - No flaky external dependencies
- **Isolated testing** - Focus purely on business logic
- **Comprehensive coverage** - Test all code paths including error scenarios

## What to Test

Component tests should cover:

- **API endpoints** - Request/response handling, validation, business logic
- **View logic** - Data processing, transformations, response formatting
- **Service layer** - Business logic orchestration
- **Authentication/Authorization** - Access control logic
- **Error handling** - Exception handling and error responses
- **Data validation** - Input validation and sanitization

## What to Mock

In component tests, mock ALL external dependencies:

- **Database queries** - Mock ORM calls and model saves
- **External API calls** - Mock requests to auth-service, email/SMS/push services
- **Message queues** - Mock SQS, RabbitMQ, Kafka producers/consumers
- **Cache operations** - Mock Redis/cache get/set operations
- **File system** - Mock file reads/writes
- **Time** - Use freezegun to control time

## Directory Structure

```
tests/component/
├── __init__.py
├── test_notification_endpoints.py    # Notification CRUD endpoints
├── test_authentication.py             # Auth flow tests
├── test_notification_service.py       # Business logic service
├── test_batch_operations.py           # Batch processing logic
└── test_error_handling.py             # Error scenarios
```

## Test Naming Convention

```python
class Test<EndpointName>Endpoint(TestCase):
    """Tests for <endpoint> endpoint."""

    def test_<method>_<scenario>_<expected_result>(self):
        """Test description."""
        pass

# Examples:
class TestSendNotificationEndpoint(TestCase):
    """Tests for POST /notifications/send/ endpoint."""

    def test_post_with_valid_payload_returns_201(self):
        """Test that valid notification request returns 201 Created."""
        pass

    def test_post_with_invalid_email_returns_400(self):
        """Test that invalid email returns 400 Bad Request."""
        pass
```

## Writing Component Tests

### Basic Endpoint Test with Mocking

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse


class TestCreateNotificationEndpoint(TestCase):
    """Tests for POST /notifications/ endpoint."""

    def setUp(self):
        """Set up test client and common data."""
        self.client = Client()
        self.url = reverse('notification-create')
        self.valid_payload = {
            'recipient': 'user@example.com',
            'message': 'Test notification',
            'type': 'email'
        }

    @patch('core.services.notification_service.send_to_queue')
    @patch('core.models.Notification.objects.create')
    def test_post_with_valid_data_creates_notification_and_queues(
        self, mock_create, mock_send_queue
    ):
        """Test that valid request creates notification and sends to queue."""
        # Arrange
        mock_notification = MagicMock()
        mock_notification.id = 123
        mock_notification.status = 'queued'
        mock_create.return_value = mock_notification

        # Act
        response = self.client.post(
            self.url,
            data=self.valid_payload,
            content_type='application/json'
        )

        # Assert
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], 123)
        self.assertEqual(response.json()['status'], 'queued')

        # Verify database interaction
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['recipient'], 'user@example.com')

        # Verify queue interaction
        mock_send_queue.assert_called_once_with(mock_notification)

    def test_post_with_missing_recipient_returns_400(self):
        """Test that missing recipient returns 400 Bad Request."""
        # Arrange
        invalid_payload = {
            'message': 'Test notification',
            'type': 'email'
        }

        # Act
        response = self.client.post(
            self.url,
            data=invalid_payload,
            content_type='application/json'
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertIn('recipient', response.json())
```

### Mocking External API Calls

```python
from unittest.mock import patch
import responses
from django.test import TestCase


class TestEmailNotificationService(TestCase):
    """Tests for email notification service."""

    @responses.activate
    def test_send_email_with_valid_data_calls_email_api(self):
        """Test that email service calls external email API."""
        # Arrange
        responses.add(
            responses.POST,
            'https://email-api.example.com/send',
            json={'message_id': 'msg_123', 'status': 'sent'},
            status=200
        )

        # Act
        result = send_email_notification(
            to='user@example.com',
            subject='Test',
            body='Test message'
        )

        # Assert
        self.assertEqual(result['status'], 'sent')
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            'https://email-api.example.com/send'
        )

    @responses.activate
    def test_send_email_when_api_fails_raises_exception(self):
        """Test that email API failure raises appropriate exception."""
        # Arrange
        responses.add(
            responses.POST,
            'https://email-api.example.com/send',
            json={'error': 'Service unavailable'},
            status=503
        )

        # Act & Assert
        with self.assertRaises(EmailServiceException):
            send_email_notification(
                to='user@example.com',
                subject='Test',
                body='Test message'
            )
```

### Mocking Database Operations

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase


class TestNotificationService(TestCase):
    """Tests for NotificationService."""

    @patch('core.models.Notification.objects.filter')
    def test_get_user_notifications_returns_filtered_list(self, mock_filter):
        """Test that service correctly filters notifications by user."""
        # Arrange
        mock_queryset = MagicMock()
        mock_notifications = [
            MagicMock(id=1, message='Test 1'),
            MagicMock(id=2, message='Test 2'),
        ]
        mock_queryset.__iter__ = MagicMock(return_value=iter(mock_notifications))
        mock_filter.return_value = mock_queryset

        service = NotificationService()

        # Act
        result = service.get_user_notifications(user_id=123)

        # Assert
        self.assertEqual(len(list(result)), 2)
        mock_filter.assert_called_once_with(user_id=123)

    @patch('core.models.Notification.objects.get')
    def test_mark_as_read_updates_status(self, mock_get):
        """Test that marking notification as read updates status."""
        # Arrange
        mock_notification = MagicMock()
        mock_notification.status = 'unread'
        mock_get.return_value = mock_notification

        service = NotificationService()

        # Act
        service.mark_as_read(notification_id=123)

        # Assert
        self.assertEqual(mock_notification.status, 'read')
        mock_notification.save.assert_called_once()
```

### Mocking Message Queue Operations

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase


class TestNotificationQueueService(TestCase):
    """Tests for notification queue service."""

    @patch('boto3.client')
    def test_send_to_sqs_publishes_message(self, mock_boto_client):
        """Test that notification is sent to SQS queue."""
        # Arrange
        mock_sqs = MagicMock()
        mock_boto_client.return_value = mock_sqs
        mock_sqs.send_message.return_value = {
            'MessageId': 'msg-123',
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }

        notification_data = {
            'id': 456,
            'type': 'email',
            'recipient': 'user@example.com'
        }

        # Act
        result = send_to_sqs_queue(notification_data)

        # Assert
        self.assertTrue(result)
        mock_sqs.send_message.assert_called_once()
        call_kwargs = mock_sqs.send_message.call_args[1]
        self.assertIn('MessageBody', call_kwargs)

    @patch('boto3.client')
    def test_send_to_sqs_when_fails_raises_exception(self, mock_boto_client):
        """Test that SQS failure raises appropriate exception."""
        # Arrange
        mock_sqs = MagicMock()
        mock_boto_client.return_value = mock_sqs
        mock_sqs.send_message.side_effect = Exception('SQS Error')

        # Act & Assert
        with self.assertRaises(QueueServiceException):
            send_to_sqs_queue({'id': 456})
```

### Mocking Authentication Service

```python
from unittest.mock import patch
import responses
from django.test import TestCase, Client
from django.urls import reverse


class TestAuthenticatedEndpoints(TestCase):
    """Tests for endpoints requiring authentication."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @responses.activate
    def test_endpoint_with_valid_token_succeeds(self):
        """Test that valid auth token allows access."""
        # Arrange - Mock auth service validation
        responses.add(
            responses.POST,
            'https://auth-service.example.com/validate',
            json={'user_id': 123, 'valid': True},
            status=200
        )

        # Act
        response = self.client.get(
            reverse('notification-list'),
            HTTP_AUTHORIZATION='Bearer valid-token'
        )

        # Assert
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_endpoint_with_invalid_token_returns_401(self):
        """Test that invalid auth token returns 401."""
        # Arrange - Mock auth service rejection
        responses.add(
            responses.POST,
            'https://auth-service.example.com/validate',
            json={'valid': False, 'error': 'Invalid token'},
            status=401
        )

        # Act
        response = self.client.get(
            reverse('notification-list'),
            HTTP_AUTHORIZATION='Bearer invalid-token'
        )

        # Assert
        self.assertEqual(response.status_code, 401)

    def test_endpoint_without_token_returns_401(self):
        """Test that missing auth token returns 401."""
        # Act
        response = self.client.get(reverse('notification-list'))

        # Assert
        self.assertEqual(response.status_code, 401)
```

### Testing Error Handling

```python
from unittest.mock import patch
from django.test import TestCase, Client


class TestNotificationErrorHandling(TestCase):
    """Tests for notification endpoint error handling."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @patch('core.services.notification_service.send_notification')
    def test_endpoint_handles_service_exception_gracefully(self, mock_send):
        """Test that service exceptions are handled and return 500."""
        # Arrange
        mock_send.side_effect = Exception('Unexpected error')

        # Act
        response = self.client.post(
            '/api/notifications/',
            data={'recipient': 'user@example.com', 'message': 'Test'},
            content_type='application/json'
        )

        # Assert
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.json())

    @patch('core.models.Notification.objects.create')
    def test_endpoint_handles_database_error(self, mock_create):
        """Test that database errors are handled appropriately."""
        # Arrange
        from django.db import DatabaseError
        mock_create.side_effect = DatabaseError('Connection lost')

        # Act
        response = self.client.post(
            '/api/notifications/',
            data={'recipient': 'user@example.com', 'message': 'Test'},
            content_type='application/json'
        )

        # Assert
        self.assertEqual(response.status_code, 500)
```

### Using Freezegun for Time Control

```python
from freezegun import freeze_time
from django.test import TestCase
from datetime import datetime


class TestScheduledNotifications(TestCase):
    """Tests for scheduled notification logic."""

    @freeze_time("2025-01-15 10:00:00")
    def test_get_due_notifications_returns_past_scheduled(self):
        """Test that notifications scheduled in past are returned."""
        # Arrange
        with patch('core.models.Notification.objects.filter') as mock_filter:
            mock_filter.return_value = [
                MagicMock(scheduled_at=datetime(2025, 1, 15, 9, 0))
            ]

            # Act
            result = get_due_notifications()

            # Assert
            self.assertEqual(len(result), 1)
            # Verify filter was called with correct datetime
            mock_filter.assert_called_once()

    @freeze_time("2025-01-15 10:00:00")
    def test_schedule_notification_sets_future_time(self):
        """Test that scheduling sets correct future timestamp."""
        # Act
        result = schedule_notification(delay_hours=2)

        # Assert
        expected_time = datetime(2025, 1, 15, 12, 0)
        self.assertEqual(result.scheduled_at, expected_time)
```

## Mock Helpers and Utilities

Create reusable mock helpers in `tests/component/mocks.py`:

```python
"""Mock helpers for component tests."""

from unittest.mock import MagicMock


def create_mock_notification(**kwargs):
    """Create a mock Notification object."""
    defaults = {
        'id': 1,
        'recipient': 'user@example.com',
        'message': 'Test message',
        'type': 'email',
        'status': 'pending',
    }
    defaults.update(kwargs)

    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)

    return mock


def mock_auth_service_success():
    """Return responses configuration for successful auth."""
    return {
        'method': responses.POST,
        'url': 'https://auth-service.example.com/validate',
        'json': {'user_id': 123, 'valid': True},
        'status': 200
    }


def mock_email_service_success():
    """Return responses configuration for successful email send."""
    return {
        'method': responses.POST,
        'url': 'https://email-api.example.com/send',
        'json': {'message_id': 'msg_123', 'status': 'sent'},
        'status': 200
    }
```

## Best Practices

### DO

- Mock ALL external dependencies (database, APIs, queues)
- Test both success and failure scenarios
- Verify mock calls to ensure code behaves correctly
- Use descriptive mock names
- Test error handling and edge cases
- Keep mocks close to the test (or in shared utilities)
- Use `responses` library for HTTP mocking
- Use `freezegun` for time-dependent tests

### DON'T

- Make real API calls
- Access real databases
- Depend on external service availability
- Over-mock (don't mock what you're testing)
- Create complex mock hierarchies
- Share mocked state between tests
- Mock too deep (indicates code needs refactoring)

## Common Patterns

### Testing Request Validation

```python
class TestRequestValidation(TestCase):
    """Tests for request validation."""

    def test_missing_required_field_returns_400(self):
        """Test that missing required fields return 400."""
        response = self.client.post(
            '/api/notifications/',
            data={'message': 'Test'},  # Missing 'recipient'
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_email_format_returns_400(self):
        """Test that invalid email format returns 400."""
        response = self.client.post(
            '/api/notifications/',
            data={'recipient': 'not-an-email', 'message': 'Test'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
```

### Testing Batch Operations

```python
class TestBatchNotifications(TestCase):
    """Tests for batch notification operations."""

    @patch('core.services.notification_service.send_notification')
    def test_send_batch_processes_all_notifications(self, mock_send):
        """Test that batch operation processes all items."""
        # Arrange
        mock_send.return_value = {'status': 'success'}
        batch = [
            {'recipient': 'user1@example.com', 'message': 'Test 1'},
            {'recipient': 'user2@example.com', 'message': 'Test 2'},
            {'recipient': 'user3@example.com', 'message': 'Test 3'},
        ]

        # Act
        result = send_batch_notifications(batch)

        # Assert
        self.assertEqual(len(result), 3)
        self.assertEqual(mock_send.call_count, 3)
```

## Running Component Tests

```bash
# Run all component tests
uv run test-component

# Run specific test file
uv run pytest tests/component/test_notification_endpoints.py -v

# Run with verbose output
uv run pytest tests/component/ -v

# Run with coverage
uv run pytest tests/component/ --cov=core --cov-report=term-missing
```

## Coverage Goals

Component tests should achieve:
- **90%+ coverage** for API endpoints
- **85%+ coverage** for service layer
- **100% coverage** for critical paths (authentication, payment, etc.)

## Related Documentation

- [Testing Overview](./TESTING.md)
- [Unit Testing](./UNIT-TESTING.md)
- [Dependency Testing](./DEPENDENCY-TESTING.md)
- [Performance Testing](./PERFORMANCE-TESTING.md)
- [Mocking Best Practices](https://docs.python.org/3/library/unittest.mock.html)
