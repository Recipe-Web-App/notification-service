# Unit Testing

## Overview

Unit tests are the foundation of our testing strategy. They test individual functions, methods, and classes in complete isolation from external dependencies. Unit tests should be fast, focused, and test a single unit of functionality.

## What to Test

Unit tests should focus on:

- **Pure functions** - Functions with no side effects
- **Utility functions** - Helper functions and data transformations
- **Business logic** - Calculations, validations, formatting
- **Simple methods** - Methods that don't interact with external systems
- **Data models** - Model methods, properties, and validators

## What NOT to Test

Unit tests should NOT include:

- Database interactions (use dependency tests)
- API calls to external services (use component or dependency tests)
- File I/O operations (mock or use component tests)
- Time-dependent operations (use freezegun to control time)
- Complex integration flows (use component or dependency tests)

## Directory Structure

```
tests/unit/
├── __init__.py
├── test_utils.py           # Utility function tests
├── test_validators.py      # Validation logic tests
├── test_formatters.py      # Data formatting tests
├── test_models.py          # Model method tests
└── test_serializers.py     # Serializer tests
```

## Test Naming Convention

```python
class Test<ClassName>(unittest.TestCase):
    """Tests for <ClassName>."""

    def test_<method>_<scenario>_<expected_result>(self):
        """Test description."""
        pass

# Examples:
class TestEmailValidator(unittest.TestCase):
    """Tests for EmailValidator."""

    def test_validate_with_valid_email_returns_true(self):
        """Test that valid email passes validation."""
        pass

    def test_validate_with_invalid_email_raises_validation_error(self):
        """Test that invalid email raises ValidationError."""
        pass
```

## Writing Unit Tests

### Basic Structure (AAA Pattern)

```python
import unittest
from core.utils import format_phone_number


class TestFormatPhoneNumber(unittest.TestCase):
    """Tests for format_phone_number utility."""

    def test_format_phone_number_with_us_number_returns_formatted(self):
        """Test that US phone number is correctly formatted."""
        # Arrange
        phone = "5551234567"
        expected = "+1 (555) 123-4567"

        # Act
        result = format_phone_number(phone, country_code="US")

        # Assert
        self.assertEqual(result, expected)

    def test_format_phone_number_with_invalid_input_raises_error(self):
        """Test that invalid phone number raises ValueError."""
        # Arrange
        invalid_phone = "not-a-number"

        # Act & Assert
        with self.assertRaises(ValueError):
            format_phone_number(invalid_phone)
```

### Testing Pure Functions

```python
from core.utils import calculate_notification_priority


class TestCalculateNotificationPriority(unittest.TestCase):
    """Tests for calculate_notification_priority function."""

    def test_calculate_priority_for_critical_alert_returns_high(self):
        """Test that critical alerts get high priority."""
        result = calculate_notification_priority(
            alert_type="critical",
            user_preferences={"critical_alerts": "immediate"}
        )
        self.assertEqual(result, "high")

    def test_calculate_priority_for_info_message_returns_low(self):
        """Test that info messages get low priority."""
        result = calculate_notification_priority(
            alert_type="info",
            user_preferences={"info_alerts": "digest"}
        )
        self.assertEqual(result, "low")
```

### Testing Model Methods

```python
from django.test import TestCase
from core.models import Notification


class TestNotificationModel(TestCase):
    """Tests for Notification model methods."""

    def test_is_expired_when_timestamp_old_returns_true(self):
        """Test that old notifications are marked as expired."""
        notification = Notification(
            created_at=timezone.now() - timedelta(days=8)
        )
        self.assertTrue(notification.is_expired())

    def test_is_expired_when_timestamp_recent_returns_false(self):
        """Test that recent notifications are not expired."""
        notification = Notification(
            created_at=timezone.now() - timedelta(days=3)
        )
        self.assertFalse(notification.is_expired())

    def test_get_display_title_returns_formatted_string(self):
        """Test that display title is properly formatted."""
        notification = Notification(
            type="email",
            subject="Test Subject"
        )
        expected = "Email: Test Subject"
        self.assertEqual(notification.get_display_title(), expected)
```

### Testing Validators

```python
from django.core.exceptions import ValidationError
from core.validators import validate_notification_payload


class TestNotificationPayloadValidator(unittest.TestCase):
    """Tests for validate_notification_payload function."""

    def test_validate_with_complete_payload_succeeds(self):
        """Test that valid payload passes validation."""
        payload = {
            "recipient": "user@example.com",
            "message": "Test message",
            "type": "email"
        }
        # Should not raise
        validate_notification_payload(payload)

    def test_validate_with_missing_recipient_raises_error(self):
        """Test that missing recipient raises ValidationError."""
        payload = {
            "message": "Test message",
            "type": "email"
        }
        with self.assertRaises(ValidationError) as cm:
            validate_notification_payload(payload)
        self.assertIn("recipient", str(cm.exception))

    def test_validate_with_empty_message_raises_error(self):
        """Test that empty message raises ValidationError."""
        payload = {
            "recipient": "user@example.com",
            "message": "",
            "type": "email"
        }
        with self.assertRaises(ValidationError):
            validate_notification_payload(payload)
```

## Common Assertions

### Django TestCase Assertions

```python
# Equality
self.assertEqual(a, b)
self.assertNotEqual(a, b)

# Identity
self.assertIs(a, b)
self.assertIsNot(a, b)

# Boolean
self.assertTrue(x)
self.assertFalse(x)

# Null checks
self.assertIsNone(x)
self.assertIsNotNone(x)

# Membership
self.assertIn(item, container)
self.assertNotIn(item, container)

# Exceptions
with self.assertRaises(ValueError):
    function_that_raises()

# Regex matching
self.assertRegex(text, pattern)

# Numeric comparisons
self.assertGreater(a, b)
self.assertLess(a, b)
self.assertAlmostEqual(a, b, places=2)

# Collections
self.assertListEqual(list1, list2)
self.assertDictEqual(dict1, dict2)
self.assertCountEqual(list1, list2)  # Unordered comparison
```

## Setup and Teardown

```python
class TestNotificationFormatter(unittest.TestCase):
    """Tests for NotificationFormatter."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.formatter = NotificationFormatter()
        self.sample_data = {
            "user": "John Doe",
            "action": "login"
        }

    def tearDown(self):
        """Clean up after each test method."""
        # Usually not needed for unit tests, but available if necessary
        pass

    def test_format_message_includes_username(self):
        """Test that formatted message includes username."""
        result = self.formatter.format_message(self.sample_data)
        self.assertIn("John Doe", result)
```

## Testing Edge Cases

Always test edge cases and boundary conditions:

```python
class TestCalculateRetryDelay(unittest.TestCase):
    """Tests for calculate_retry_delay function."""

    def test_with_zero_attempts_returns_minimum_delay(self):
        """Test delay for first attempt."""
        result = calculate_retry_delay(attempts=0)
        self.assertEqual(result, 1)

    def test_with_max_attempts_returns_maximum_delay(self):
        """Test delay caps at maximum."""
        result = calculate_retry_delay(attempts=10)
        self.assertLessEqual(result, 3600)  # Max 1 hour

    def test_with_negative_attempts_raises_error(self):
        """Test that negative attempts raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_retry_delay(attempts=-1)

    def test_exponential_backoff_increases_correctly(self):
        """Test that delay increases exponentially."""
        delay1 = calculate_retry_delay(attempts=1)
        delay2 = calculate_retry_delay(attempts=2)
        delay3 = calculate_retry_delay(attempts=3)

        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)
```

## Parameterized Tests

For testing multiple similar scenarios:

```python
class TestEmailValidation(unittest.TestCase):
    """Tests for email validation."""

    def test_valid_emails(self):
        """Test that valid email formats pass validation."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user123@test-domain.com",
        ]

        for email in valid_emails:
            with self.subTest(email=email):
                self.assertTrue(is_valid_email(email))

    def test_invalid_emails(self):
        """Test that invalid email formats fail validation."""
        invalid_emails = [
            "invalid",
            "@example.com",
            "user@",
            "user @example.com",
            "user@.com",
        ]

        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertFalse(is_valid_email(email))
```

## Best Practices

### DO

- Test one thing per test
- Use descriptive test names
- Keep tests simple and readable
- Test edge cases and boundary conditions
- Use setUp for common test data
- Test both success and failure paths
- Make assertions specific and meaningful

### DON'T

- Test framework/library code
- Test multiple unrelated things in one test
- Use complex logic in tests
- Share state between tests
- Depend on test execution order
- Mock what you're testing (only mock dependencies)
- Write tests that depend on external state

## Running Unit Tests

```bash
# Run all unit tests
uv run test-unit

# Run specific test file
uv run pytest tests/unit/test_validators.py -v

# Run specific test class
uv run pytest tests/unit/test_validators.py::TestEmailValidator -v

# Run specific test method
uv run pytest tests/unit/test_validators.py::TestEmailValidator::test_validate_with_valid_email_returns_true -v

# Run with verbose output
uv run pytest tests/unit/ -v
```

## Coverage

Unit tests should achieve high coverage for the code they test:

```bash
# Run with coverage
uv run test-coverage

# Run unit tests with coverage for specific module
uv run pytest tests/unit/ --cov=core.utils --cov-report=term-missing
```

Aim for:
- 95%+ coverage for utility functions
- 90%+ coverage for model methods
- 85%+ coverage for validators and serializers

## Example: Complete Test File

```python
"""Tests for notification utility functions."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.utils import (
    format_notification_message,
    calculate_send_delay,
    sanitize_user_input,
)


class TestFormatNotificationMessage(unittest.TestCase):
    """Tests for format_notification_message utility."""

    def test_format_with_template_and_context_returns_formatted(self):
        """Test that template is correctly formatted with context."""
        template = "Hello {name}, you have {count} new messages."
        context = {"name": "John", "count": 5}
        expected = "Hello John, you have 5 new messages."

        result = format_notification_message(template, context)

        self.assertEqual(result, expected)

    def test_format_with_missing_context_key_raises_error(self):
        """Test that missing context key raises KeyError."""
        template = "Hello {name}, you have {count} messages."
        context = {"name": "John"}  # Missing 'count'

        with self.assertRaises(KeyError):
            format_notification_message(template, context)


class TestCalculateSendDelay(unittest.TestCase):
    """Tests for calculate_send_delay function."""

    def test_calculate_delay_for_immediate_priority_returns_zero(self):
        """Test that immediate priority has no delay."""
        result = calculate_send_delay(priority="immediate")
        self.assertEqual(result, 0)

    def test_calculate_delay_for_low_priority_returns_hours(self):
        """Test that low priority has several hours delay."""
        result = calculate_send_delay(priority="low")
        self.assertGreaterEqual(result, 3600)  # At least 1 hour


class TestSanitizeUserInput(TestCase):
    """Tests for sanitize_user_input function."""

    def test_sanitize_removes_script_tags(self):
        """Test that script tags are removed."""
        input_text = "Hello <script>alert('xss')</script> World"
        expected = "Hello  World"

        result = sanitize_user_input(input_text)

        self.assertEqual(result, expected)

    def test_sanitize_preserves_safe_html(self):
        """Test that safe HTML is preserved."""
        input_text = "Hello <b>World</b>"

        result = sanitize_user_input(input_text)

        self.assertIn("<b>", result)
        self.assertIn("</b>", result)
```

## Related Documentation

- [Testing Overview](./TESTING.md)
- [Component Testing](./COMPONENT-TESTING.md)
- [Dependency Testing](./DEPENDENCY-TESTING.md)
- [Performance Testing](./PERFORMANCE-TESTING.md)
