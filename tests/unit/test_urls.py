"""Unit tests for URL configuration.

This module tests URL routing, resolution, and reverse lookups for the
notification service application.
"""

import unittest

from django.test import SimpleTestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

import core
import notification_service
from core.views import HealthCheckView
from notification_service import urls


class TestCoreURLPatterns(SimpleTestCase):
    """Tests for core app URL patterns."""

    def test_health_check_url_resolves(self):
        """Test that /health/ URL resolves to HealthCheckView."""
        url = "/health/"
        resolved = resolve(url)

        self.assertEqual(resolved.func.cls, HealthCheckView)

    def test_health_check_url_name(self):
        """Test that health check URL has correct name."""
        url = "/health/"
        resolved = resolve(url)

        self.assertEqual(resolved.url_name, "health-check")

    def test_health_check_reverse_lookup(self):
        """Test that 'health-check' reverse lookup returns correct URL."""
        url = reverse("health-check")
        self.assertEqual(url, "/health/")

    def test_health_check_reverse_resolve_cycle(self):
        """Test that reverse and resolve form a proper cycle."""
        # reverse -> resolve -> should give us back the same name
        url = reverse("health-check")
        resolved = resolve(url)

        self.assertEqual(resolved.url_name, "health-check")
        self.assertEqual(url, "/health/")


class TestMainURLPatterns(SimpleTestCase):
    """Tests for main project URL patterns."""

    def test_admin_url_is_configured(self):
        """Test that /admin/ URL is configured."""
        url = "/admin/"
        resolved = resolve(url)

        # Should resolve without error
        self.assertIsNotNone(resolved)

    def test_admin_url_resolves_to_admin_site(self):
        """Test that /admin/ resolves to Django admin."""
        url = "/admin/"
        resolved = resolve(url)

        # The admin URLs should be configured
        self.assertTrue(hasattr(resolved.func, "admin_site"))

    def test_admin_reverse_lookup(self):
        """Test that admin URLs can be reverse looked up."""
        # Test the admin index page
        url = reverse("admin:index")
        self.assertEqual(url, "/admin/")

    def test_core_urls_included_at_root(self):
        """Test that core URLs are included at root path."""
        # Health check should be at /health/ (not /core/health/)
        url = reverse("health-check")
        self.assertEqual(url, "/health/")
        self.assertFalse(url.startswith("/core/"))


class TestURLResolutionErrors(SimpleTestCase):
    """Tests for URL resolution error handling."""

    def test_nonexistent_url_raises_404(self):
        """Test that non-existent URLs raise Resolver404."""
        with self.assertRaises(Resolver404):
            resolve("/does-not-exist/")

    def test_invalid_url_pattern_raises_404(self):
        """Test that invalid URL patterns raise Resolver404."""
        with self.assertRaises(Resolver404):
            resolve("/invalid/pattern/123/")

    def test_reverse_nonexistent_name_raises_error(self):
        """Test that reversing non-existent URL name raises error."""
        with self.assertRaises(NoReverseMatch):
            reverse("nonexistent-url-name")


class TestURLNamespaces(SimpleTestCase):
    """Tests for URL namespaces and organization."""

    def test_admin_namespace_exists(self):
        """Test that admin namespace exists."""
        # Should not raise NoReverseMatch
        try:
            reverse("admin:index")
        except Exception as e:
            self.fail(f"Admin namespace not configured: {e}")

    def test_core_urls_have_no_namespace(self):
        """Test that core URLs don't have a namespace prefix."""
        # Health check should be accessible without namespace
        url = reverse("health-check")
        self.assertIsNotNone(url)

        # This should raise because there's no 'core' namespace
        with self.assertRaises(NoReverseMatch):
            reverse("core:health-check")


class TestURLPatternStructure(SimpleTestCase):
    """Tests for URL pattern structure and organization."""

    def test_urlpatterns_is_list(self):
        """Test that urlpatterns is a list."""
        self.assertIsInstance(urls.urlpatterns, list)

    def test_urlpatterns_not_empty(self):
        """Test that urlpatterns is not empty."""
        self.assertGreater(len(urls.urlpatterns), 0)

    def test_core_urlpatterns_is_list(self):
        """Test that core urlpatterns is a list."""
        self.assertIsInstance(urls.urlpatterns, list)

    def test_core_urlpatterns_not_empty(self):
        """Test that core urlpatterns is not empty."""
        self.assertGreater(len(urls.urlpatterns), 0)


class TestURLPathFormats(SimpleTestCase):
    """Tests for URL path format conventions."""

    def test_health_url_has_trailing_slash(self):
        """Test that health URL follows Django convention with trailing slash."""
        url = reverse("health-check")
        self.assertTrue(url.endswith("/"))

    def test_admin_url_has_trailing_slash(self):
        """Test that admin URL has trailing slash."""
        url = reverse("admin:index")
        self.assertTrue(url.endswith("/"))

    def test_all_urls_use_consistent_format(self):
        """Test that all URLs use consistent format (trailing slashes)."""
        urls_to_test = [
            "health-check",
            "admin:index",
        ]

        for url_name in urls_to_test:
            url = reverse(url_name)
            self.assertTrue(
                url.endswith("/"),
                f"URL {url_name} -> {url} doesn't end with trailing slash",
            )


class TestURLDocumentation(unittest.TestCase):
    """Tests for URL configuration documentation."""

    def test_main_urls_has_module_docstring(self):
        """Test that main urls module has docstring."""
        self.assertIsNotNone(notification_service.urls.__doc__)
        self.assertGreater(len(notification_service.urls.__doc__), 0)

    def test_core_urls_has_module_docstring(self):
        """Test that core urls module has docstring."""
        self.assertIsNotNone(core.urls.__doc__)
        self.assertGreater(len(core.urls.__doc__), 0)


if __name__ == "__main__":
    unittest.main()
