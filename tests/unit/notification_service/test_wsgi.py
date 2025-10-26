"""Unit tests for notification_service.wsgi module."""

import unittest

from notification_service import wsgi


class TestWsgiModule(unittest.TestCase):
    """Tests for WSGI configuration module."""

    def test_wsgi_application_is_created(self):
        """Test that WSGI application object is created."""
        self.assertTrue(hasattr(wsgi, "application"))
        self.assertIsNotNone(wsgi.application)


if __name__ == "__main__":
    unittest.main()
