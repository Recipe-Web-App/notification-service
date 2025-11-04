"""Pagination classes for API endpoints."""

from rest_framework.pagination import PageNumberPagination


class NotificationPageNumberPagination(PageNumberPagination):
    """Pagination class for notification list endpoints.

    Provides page-number based pagination with configurable page size.
    Matches the OpenAPI specification requirements for notification endpoints.
    """

    page_size = 20  # Default from OpenAPI spec
    page_size_query_param = "page_size"
    max_page_size = 100  # Maximum from OpenAPI spec
