"""Test-specific Django settings."""

from django.db.models.signals import class_prepared

from .settings import *

# Use SQLite for faster tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable debug for tests
DEBUG = False

# Use a simple password hasher for speed
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


# Use local cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Suppress logs during tests (only show CRITICAL errors)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
        "level": "CRITICAL",
    },
    "loggers": {
        "django": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "core": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}

# Test-specific settings
TEST_MODE = True

# Force unmanaged models to be managed ONLY for tests
# The Notification and User models have managed=False because this service
# doesn't own the database schema. But we need the tables created for tests.


def make_unmanaged_models_managed(sender, **_kwargs):
    """Signal handler to make unmanaged models managed during tests.

    This fires when each model class is prepared by Django.
    """
    if not sender._meta.managed:
        sender._meta.managed = True


# Connect the signal - this will fire for each model as it's loaded
class_prepared.connect(make_unmanaged_models_managed)
