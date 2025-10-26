"""Unit tests for notification_service.asgi module."""

import unittest

from notification_service import asgi


class TestAsgiModule(unittest.TestCase):
    """Tests for ASGI configuration module."""

    def test_asgi_application_is_created(self):
        """Test that ASGI application object is created."""
        self.assertTrue(hasattr(asgi, "application"))
        self.assertIsNotNone(asgi.application)


if __name__ == "__main__":
    unittest.main()
