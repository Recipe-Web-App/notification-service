"""Constants used throughout the notification service application."""

# HTTP Headers
REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"

# Rate Limiting Defaults
DEFAULT_RATE_LIMIT_REQUESTS = 100  # Number of requests
DEFAULT_RATE_LIMIT_WINDOW = 60  # Time window in seconds

# Performance Thresholds
SLOW_REQUEST_THRESHOLD = 1.0  # Log requests slower than 1 second

# Security Headers
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'",
}
