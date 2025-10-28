"""Email service for sending notifications via SMTP."""

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from django.conf import settings
from django.template.loader import render_to_string

import structlog

logger = structlog.get_logger(__name__)


class EmailService:
    """Service for sending emails via SMTP.

    Handles email formatting, HTML/plain text conversion, and SMTP delivery.
    Supports template rendering and retry logic.
    """

    def __init__(self) -> None:
        """Initialize email service with SMTP configuration."""
        self.smtp_host = settings.EMAIL_HOST
        self.smtp_port = settings.EMAIL_PORT
        self.smtp_user = settings.EMAIL_HOST_USER
        self.smtp_password = settings.EMAIL_HOST_PASSWORD
        self.use_tls = settings.EMAIL_USE_TLS
        self.from_email = settings.DEFAULT_FROM_EMAIL

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: str | None = None,
    ) -> bool:
        """Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email content
            from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)

        Returns:
            True if email was sent successfully, False otherwise

        Raises:
            ValueError: If email address is invalid
            smtplib.SMTPException: If SMTP operation fails
        """
        # Validate email address
        if not self._is_valid_email(to_email):
            error_msg = f"Invalid email address: {to_email}"
            raise ValueError(error_msg)

        # Use default from_email if not provided
        sender = from_email or self.from_email

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        # Convert HTML to plain text
        plain_content = self._html_to_plain(html_content)

        # Attach both plain text and HTML versions
        part1 = MIMEText(plain_content, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        try:
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                # Login if credentials provided
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                # Send email
                server.send_message(msg)

                logger.info(
                    "email_sent",
                    to_email=to_email,
                    subject=subject,
                )
                return True

        except smtplib.SMTPException as e:
            logger.error(
                "email_send_failed",
                to_email=to_email,
                subject=subject,
                error=str(e),
            )
            raise

    def send_template_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict[str, Any] | None = None,
        from_email: str | None = None,
    ) -> bool:
        """Send an email using a Django template.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            template_name: Template path (e.g., 'emails/welcome.html')
            context: Template context variables
            from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)

        Returns:
            True if email was sent successfully, False otherwise

        Raises:
            ValueError: If email address is invalid
            smtplib.SMTPException: If SMTP operation fails
            django.template.TemplateDoesNotExist: If template not found
        """
        # Render template with context
        html_content = render_to_string(template_name, context or {})

        # Send email
        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=from_email,
        )

    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format.

        Args:
            email: Email address to validate

        Returns:
            True if email is valid, False otherwise
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _html_to_plain(self, html: str) -> str:
        """Convert HTML to plain text.

        Args:
            html: HTML content

        Returns:
            Plain text version of the HTML
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html)

        # Decode common HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        text = text.replace("&quot;", '"')

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = text.strip()

        return text
