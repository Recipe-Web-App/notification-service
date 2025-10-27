"""User role enumeration for database user roles."""

from enum import Enum


class UserRole(str, Enum):
    """User role enumeration matching database USER_ROLE_ENUM."""

    ADMIN = "ADMIN"
    USER = "USER"
