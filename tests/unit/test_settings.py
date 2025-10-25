"""Unit tests for Django settings configuration.

This module tests both the main settings and test-specific settings
to ensure proper configuration for different environments.
"""

import unittest

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from notification_service import settings_test


class TestMainSettingsStructure(unittest.TestCase):
    """Tests for main settings module structure."""

    def test_main_settings_module_exists(self):
        """Test that main settings module can be imported."""
        self.assertIsNotNone(settings)

    def test_main_settings_has_docstring(self):
        """Test that main settings module has docstring."""
        self.assertIsNotNone(settings.__doc__)
        self.assertGreater(len(settings.__doc__), 0)


class TestTestSettingsConfiguration(SimpleTestCase):
    """Tests for test-specific settings configuration.

    These tests verify that test settings override main settings correctly.
    """

    def test_test_mode_flag_is_set(self):
        """Test that TEST_MODE flag is set to True in test settings."""
        self.assertTrue(hasattr(settings, "TEST_MODE"))
        self.assertTrue(settings.TEST_MODE)

    def test_debug_is_disabled_in_tests(self):
        """Test that DEBUG is False in test environment."""
        self.assertFalse(settings.DEBUG)

    def test_database_uses_in_memory_sqlite(self):
        """Test that test database is configured for in-memory SQLite."""
        db_config = settings.DATABASES["default"]

        self.assertEqual(db_config["ENGINE"], "django.db.backends.sqlite3")
        # Django test runner may modify the NAME, so check it's memory-based
        self.assertIn("memory", db_config["NAME"].lower())

    def test_password_hasher_uses_fast_hasher(self):
        """Test that test settings use fast password hasher."""
        self.assertIn(
            "django.contrib.auth.hashers.MD5PasswordHasher", settings.PASSWORD_HASHERS
        )

        # MD5PasswordHasher should be first for speed
        self.assertEqual(
            settings.PASSWORD_HASHERS[0],
            "django.contrib.auth.hashers.MD5PasswordHasher",
        )

    def test_cache_uses_local_memory(self):
        """Test that test settings use local memory cache."""
        cache_config = settings.CACHES["default"]

        self.assertEqual(
            cache_config["BACKEND"], "django.core.cache.backends.locmem.LocMemCache"
        )

    def test_test_settings_imports_from_main_settings(self):
        """Test that test settings inherits from main settings."""
        # Verify that basic Django settings are still present
        self.assertTrue(hasattr(settings, "INSTALLED_APPS"))
        self.assertTrue(hasattr(settings, "MIDDLEWARE"))
        self.assertTrue(hasattr(settings, "ROOT_URLCONF"))


class TestDatabaseConfiguration(SimpleTestCase):
    """Tests for database configuration."""

    def test_default_database_exists(self):
        """Test that default database is configured."""
        self.assertIn("default", settings.DATABASES)

    def test_database_engine_is_sqlite(self):
        """Test that database engine is SQLite."""
        db_engine = settings.DATABASES["default"]["ENGINE"]
        self.assertEqual(db_engine, "django.db.backends.sqlite3")

    def test_database_name_is_memory(self):
        """Test that test database uses in-memory database."""
        db_name = settings.DATABASES["default"]["NAME"]
        # Django test runner may use different in-memory formats
        self.assertIn("memory", db_name.lower())

    def test_databases_setting_is_dict(self):
        """Test that DATABASES setting is a dictionary."""
        self.assertIsInstance(settings.DATABASES, dict)


class TestInstalledAppsConfiguration(SimpleTestCase):
    """Tests for INSTALLED_APPS configuration."""

    def test_installed_apps_is_configured(self):
        """Test that INSTALLED_APPS is configured."""
        self.assertTrue(hasattr(settings, "INSTALLED_APPS"))
        self.assertIsNotNone(settings.INSTALLED_APPS)

    def test_core_app_is_installed(self):
        """Test that core app is in INSTALLED_APPS."""
        self.assertIn("core", settings.INSTALLED_APPS)

    def test_rest_framework_is_installed(self):
        """Test that rest_framework is in INSTALLED_APPS."""
        self.assertIn("rest_framework", settings.INSTALLED_APPS)

    def test_required_django_apps_are_installed(self):
        """Test that required Django contrib apps are installed."""
        required_apps = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ]

        for app in required_apps:
            with self.subTest(app=app):
                self.assertIn(app, settings.INSTALLED_APPS)


class TestMiddlewareConfiguration(SimpleTestCase):
    """Tests for MIDDLEWARE configuration."""

    def test_middleware_is_configured(self):
        """Test that MIDDLEWARE is configured."""
        self.assertTrue(hasattr(settings, "MIDDLEWARE"))
        self.assertIsNotNone(settings.MIDDLEWARE)

    def test_middleware_is_list_or_tuple(self):
        """Test that MIDDLEWARE is a list or tuple."""
        self.assertIsInstance(settings.MIDDLEWARE, (list, tuple))

    def test_security_middleware_is_enabled(self):
        """Test that SecurityMiddleware is enabled."""
        self.assertIn(
            "django.middleware.security.SecurityMiddleware", settings.MIDDLEWARE
        )

    def test_session_middleware_is_enabled(self):
        """Test that SessionMiddleware is enabled."""
        self.assertIn(
            "django.contrib.sessions.middleware.SessionMiddleware", settings.MIDDLEWARE
        )

    def test_csrf_middleware_is_enabled(self):
        """Test that CsrfViewMiddleware is enabled."""
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)

    def test_authentication_middleware_is_enabled(self):
        """Test that AuthenticationMiddleware is enabled."""
        self.assertIn(
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            settings.MIDDLEWARE,
        )


class TestURLConfiguration(SimpleTestCase):
    """Tests for URL and routing configuration."""

    def test_root_urlconf_is_configured(self):
        """Test that ROOT_URLCONF is configured."""
        self.assertTrue(hasattr(settings, "ROOT_URLCONF"))
        self.assertIsNotNone(settings.ROOT_URLCONF)

    def test_root_urlconf_points_to_correct_module(self):
        """Test that ROOT_URLCONF points to notification_service.urls."""
        self.assertEqual(settings.ROOT_URLCONF, "notification_service.urls")


class TestCacheConfiguration(SimpleTestCase):
    """Tests for cache configuration."""

    def test_caches_is_configured(self):
        """Test that CACHES setting is configured."""
        self.assertTrue(hasattr(settings, "CACHES"))
        self.assertIsNotNone(settings.CACHES)

    def test_default_cache_exists(self):
        """Test that default cache is configured."""
        self.assertIn("default", settings.CACHES)

    def test_cache_backend_is_locmem(self):
        """Test that cache backend is local memory in tests."""
        backend = settings.CACHES["default"]["BACKEND"]
        self.assertEqual(backend, "django.core.cache.backends.locmem.LocMemCache")


class TestSecuritySettings(SimpleTestCase):
    """Tests for security-related settings."""

    def test_secret_key_is_set(self):
        """Test that SECRET_KEY is set."""
        self.assertTrue(hasattr(settings, "SECRET_KEY"))
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertGreater(len(settings.SECRET_KEY), 0)

    def test_allowed_hosts_is_configured(self):
        """Test that ALLOWED_HOSTS is configured."""
        self.assertTrue(hasattr(settings, "ALLOWED_HOSTS"))
        self.assertIsNotNone(settings.ALLOWED_HOSTS)

    def test_password_validators_exist(self):
        """Test that password validators are configured."""
        self.assertTrue(hasattr(settings, "AUTH_PASSWORD_VALIDATORS"))


class TestInternationalizationSettings(SimpleTestCase):
    """Tests for internationalization settings."""

    def test_language_code_is_set(self):
        """Test that LANGUAGE_CODE is set."""
        self.assertTrue(hasattr(settings, "LANGUAGE_CODE"))
        self.assertIsNotNone(settings.LANGUAGE_CODE)

    def test_timezone_is_set(self):
        """Test that TIME_ZONE is set."""
        self.assertTrue(hasattr(settings, "TIME_ZONE"))
        self.assertIsNotNone(settings.TIME_ZONE)

    def test_use_i18n_is_set(self):
        """Test that USE_I18N is set."""
        self.assertTrue(hasattr(settings, "USE_I18N"))

    def test_use_tz_is_set(self):
        """Test that USE_TZ is set."""
        self.assertTrue(hasattr(settings, "USE_TZ"))


class TestStaticFilesSettings(SimpleTestCase):
    """Tests for static files settings."""

    def test_static_url_is_set(self):
        """Test that STATIC_URL is set."""
        self.assertTrue(hasattr(settings, "STATIC_URL"))
        self.assertIsNotNone(settings.STATIC_URL)


class TestTemplateConfiguration(SimpleTestCase):
    """Tests for template configuration."""

    def test_templates_is_configured(self):
        """Test that TEMPLATES is configured."""
        self.assertTrue(hasattr(settings, "TEMPLATES"))
        self.assertIsNotNone(settings.TEMPLATES)

    def test_templates_is_list(self):
        """Test that TEMPLATES is a list."""
        self.assertIsInstance(settings.TEMPLATES, list)

    def test_templates_not_empty(self):
        """Test that TEMPLATES is not empty."""
        self.assertGreater(len(settings.TEMPLATES), 0)

    def test_django_template_backend_configured(self):
        """Test that Django template backend is configured."""
        backends = [t["BACKEND"] for t in settings.TEMPLATES]
        self.assertIn("django.template.backends.django.DjangoTemplates", backends)


class TestWSGIConfiguration(SimpleTestCase):
    """Tests for WSGI configuration."""

    def test_wsgi_application_is_set(self):
        """Test that WSGI_APPLICATION is set."""
        self.assertTrue(hasattr(settings, "WSGI_APPLICATION"))
        self.assertIsNotNone(settings.WSGI_APPLICATION)

    def test_wsgi_application_points_to_correct_module(self):
        """Test that WSGI_APPLICATION points to correct module."""
        self.assertEqual(
            settings.WSGI_APPLICATION, "notification_service.wsgi.application"
        )


class TestDefaultAutoFieldConfiguration(SimpleTestCase):
    """Tests for default auto field configuration."""

    def test_default_auto_field_is_set(self):
        """Test that DEFAULT_AUTO_FIELD is set."""
        self.assertTrue(hasattr(settings, "DEFAULT_AUTO_FIELD"))
        self.assertIsNotNone(settings.DEFAULT_AUTO_FIELD)

    def test_default_auto_field_uses_bigautofield(self):
        """Test that DEFAULT_AUTO_FIELD uses BigAutoField."""
        self.assertEqual(settings.DEFAULT_AUTO_FIELD, "django.db.models.BigAutoField")


class TestSettingsOverride(SimpleTestCase):
    """Tests for settings override functionality."""

    @override_settings(DEBUG=True)
    def test_override_settings_decorator_works(self):
        """Test that override_settings decorator works correctly."""
        self.assertTrue(settings.DEBUG)

    @override_settings(CUSTOM_SETTING="test_value")
    def test_can_add_custom_settings(self):
        """Test that custom settings can be added via override."""
        self.assertEqual(settings.CUSTOM_SETTING, "test_value")

    def test_settings_return_to_normal_after_override(self):
        """Test that settings return to normal after override context."""
        # DEBUG should be False in test settings
        self.assertFalse(settings.DEBUG)


class TestTestSettingsModule(unittest.TestCase):
    """Tests for test settings module."""

    def test_test_settings_module_exists(self):
        """Test that test settings module can be imported."""
        self.assertIsNotNone(settings_test)

    def test_test_settings_has_docstring(self):
        """Test that test settings module has docstring."""
        self.assertIsNotNone(settings_test.__doc__)
        self.assertGreater(len(settings_test.__doc__), 0)


if __name__ == "__main__":
    unittest.main()
