"""Unit tests for Django app configuration.

This module tests the Django app configuration for the core application
and verifies it's properly integrated into the project.
"""

import unittest
from pathlib import Path

from django.apps import AppConfig, apps
from django.conf import settings
from django.test import SimpleTestCase

import core
import core.apps
from core import models
from core.apps import CoreConfig


class TestCoreAppConfig(unittest.TestCase):
    """Tests for CoreConfig class."""

    def test_core_config_inherits_from_appconfig(self):
        """Test that CoreConfig inherits from AppConfig."""
        self.assertTrue(issubclass(CoreConfig, AppConfig))

    def test_core_config_name_is_correct(self):
        """Test that CoreConfig has correct app name."""
        # CoreConfig.name is a class attribute, not instance
        self.assertEqual(CoreConfig.name, "core")

    def test_core_config_default_auto_field_is_set(self):
        """Test that CoreConfig has default_auto_field set."""
        self.assertEqual(CoreConfig.default_auto_field, "django.db.models.BigAutoField")

    def test_core_config_has_docstring(self):
        """Test that CoreConfig has a docstring."""
        self.assertIsNotNone(CoreConfig.__doc__)
        self.assertGreater(len(CoreConfig.__doc__), 0)

    def test_core_config_can_be_instantiated(self):
        """Test that CoreConfig can be instantiated."""
        # Test via Django's app registry instead of direct instantiation
        config = apps.get_app_config("core")
        self.assertIsInstance(config, CoreConfig)


class TestCoreAppIntegration(SimpleTestCase):
    """Tests for core app integration with Django."""

    def test_core_app_is_installed(self):
        """Test that core app is in INSTALLED_APPS."""
        self.assertIn("core", settings.INSTALLED_APPS)

    def test_core_app_is_registered(self):
        """Test that core app is registered with Django."""
        self.assertTrue(apps.is_installed("core"))

    def test_core_app_can_be_retrieved(self):
        """Test that core app config can be retrieved."""
        app_config = apps.get_app_config("core")
        self.assertIsNotNone(app_config)

    def test_core_app_config_is_correct_class(self):
        """Test that registered app config is CoreConfig."""
        app_config = apps.get_app_config("core")
        self.assertIsInstance(app_config, CoreConfig)

    def test_core_app_config_name_matches(self):
        """Test that app config name matches expected value."""
        app_config = apps.get_app_config("core")
        self.assertEqual(app_config.name, "core")

    def test_core_app_label_is_correct(self):
        """Test that app label is correct."""
        app_config = apps.get_app_config("core")
        self.assertEqual(app_config.label, "core")

    def test_core_app_path_exists(self):
        """Test that core app path exists and is correct."""
        app_config = apps.get_app_config("core")

        self.assertTrue(Path(app_config.path).exists())
        self.assertTrue(app_config.path.endswith("core"))

    def test_core_app_verbose_name(self):
        """Test that core app has a verbose name."""
        app_config = apps.get_app_config("core")

        # Default verbose name should be a readable version of the label
        self.assertIsNotNone(app_config.verbose_name)


class TestDjangoAppRegistry(SimpleTestCase):
    """Tests for Django app registry and installed apps."""

    def test_all_required_apps_installed(self):
        """Test that all required Django apps are installed."""
        required_apps = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "rest_framework",
            "core",
        ]

        for app in required_apps:
            with self.subTest(app=app):
                self.assertIn(app, settings.INSTALLED_APPS)

    def test_rest_framework_is_installed(self):
        """Test that REST framework is installed."""
        self.assertIn("rest_framework", settings.INSTALLED_APPS)
        self.assertTrue(apps.is_installed("rest_framework"))

    def test_django_contrib_apps_installed(self):
        """Test that standard Django contrib apps are installed."""
        contrib_apps = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
        ]

        for app in contrib_apps:
            with self.subTest(app=app):
                self.assertIn(app, settings.INSTALLED_APPS)

    def test_core_app_position_in_installed_apps(self):
        """Test that core app is positioned correctly in INSTALLED_APPS."""
        # Core should be after Django contrib apps and rest_framework
        core_index = settings.INSTALLED_APPS.index("core")

        # Should be after rest_framework
        rest_framework_index = settings.INSTALLED_APPS.index("rest_framework")
        self.assertGreater(core_index, rest_framework_index)

    def test_installed_apps_is_list_or_tuple(self):
        """Test that INSTALLED_APPS is a list or tuple."""
        self.assertIsInstance(settings.INSTALLED_APPS, (list, tuple))

    def test_installed_apps_not_empty(self):
        """Test that INSTALLED_APPS is not empty."""
        self.assertGreater(len(settings.INSTALLED_APPS), 0)


class TestCoreAppModels(SimpleTestCase):
    """Tests for core app models configuration."""

    def test_core_app_models_module_exists(self):
        """Test that core.models module exists."""
        self.assertIsNotNone(models)

    def test_core_app_default_auto_field_applied(self):
        """Test that default_auto_field setting is applied."""
        app_config = apps.get_app_config("core")

        # CoreConfig should have BigAutoField set
        self.assertEqual(app_config.default_auto_field, "django.db.models.BigAutoField")


class TestCoreAppStructure(unittest.TestCase):
    """Tests for core app file structure."""

    def test_core_module_can_be_imported(self):
        """Test that core module can be imported."""
        self.assertIsNotNone(core)

    def test_core_apps_module_can_be_imported(self):
        """Test that core.apps module can be imported."""
        self.assertIsNotNone(core.apps)

    def test_core_views_module_can_be_imported(self):
        """Test that core.views module can be imported."""
        self.assertIsNotNone(core.views)

    def test_core_urls_module_can_be_imported(self):
        """Test that core.urls module can be imported."""
        self.assertIsNotNone(core.urls)

    def test_core_models_module_can_be_imported(self):
        """Test that core.models module can be imported."""
        self.assertIsNotNone(core.models)

    def test_core_admin_module_can_be_imported(self):
        """Test that core.admin module can be imported."""
        self.assertIsNotNone(core.admin)


class TestAppConfigDocumentation(unittest.TestCase):
    """Tests for app configuration documentation."""

    def test_core_apps_module_has_docstring(self):
        """Test that core.apps module has docstring."""

        self.assertIsNotNone(core.apps.__doc__)
        self.assertGreater(len(core.apps.__doc__), 0)

    def test_core_config_class_has_docstring(self):
        """Test that CoreConfig class has docstring."""
        self.assertIsNotNone(CoreConfig.__doc__)
        self.assertIn("core", CoreConfig.__doc__.lower())


class TestAppConfigAttributes(SimpleTestCase):
    """Tests for CoreConfig attributes and properties."""

    def test_core_config_has_name_attribute(self):
        """Test that CoreConfig has name attribute."""
        self.assertTrue(hasattr(CoreConfig, "name"))

    def test_core_config_has_default_auto_field_attribute(self):
        """Test that CoreConfig has default_auto_field attribute."""
        self.assertTrue(hasattr(CoreConfig, "default_auto_field"))

    def test_core_config_default_auto_field_is_string(self):
        """Test that default_auto_field is a string."""
        self.assertIsInstance(CoreConfig.default_auto_field, str)

    def test_core_config_default_auto_field_is_valid(self):
        """Test that default_auto_field is a valid field type."""
        valid_auto_fields = [
            "django.db.models.BigAutoField",
            "django.db.models.AutoField",
            "django.db.models.SmallAutoField",
        ]

        self.assertIn(CoreConfig.default_auto_field, valid_auto_fields)


if __name__ == "__main__":
    unittest.main()
