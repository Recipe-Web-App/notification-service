"""Tests for EmailService."""

import smtplib
from unittest.mock import MagicMock, patch

from django.template import TemplateDoesNotExist

import pytest

from core.services.email_service import EmailService


class TestEmailService:
    """Test suite for EmailService."""

    @pytest.fixture
    def email_service(self):
        """Create EmailService instance."""
        return EmailService()

    @pytest.fixture
    def mock_smtp(self):
        """Mock SMTP server."""
        with patch("core.services.email_service.smtplib.SMTP") as mock:
            smtp_instance = MagicMock()
            mock.return_value.__enter__.return_value = smtp_instance
            yield smtp_instance

    def test_send_email_success(self, email_service, mock_smtp):
        """Test successful email sending."""
        result = email_service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<p>Test message</p>",
        )

        assert result is True
        mock_smtp.send_message.assert_called_once()

    def test_send_email_with_custom_from(self, email_service, mock_smtp):
        """Test sending email with custom from address."""
        result = email_service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
            from_email="custom@example.com",
        )

        assert result is True
        call_args = mock_smtp.send_message.call_args[0][0]
        assert call_args["From"] == "custom@example.com"

    def test_send_email_invalid_email(self, email_service):
        """Test sending email with invalid email address."""
        with pytest.raises(ValueError, match="Invalid email address"):
            email_service.send_email(
                to_email="invalid-email",
                subject="Test",
                html_content="<p>Test</p>",
            )

    def test_send_email_smtp_exception(self, email_service):
        """Test email sending with SMTP exception."""
        with patch("core.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value.send_message.side_effect = (
                smtplib.SMTPException("SMTP error")
            )

            with pytest.raises(smtplib.SMTPException):
                email_service.send_email(
                    to_email="test@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )

    def test_send_email_uses_tls(self, email_service, mock_smtp):
        """Test that email service uses TLS."""
        email_service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        mock_smtp.starttls.assert_called_once()

    def test_send_email_authenticates(self, email_service, mock_smtp):
        """Test that email service authenticates with SMTP server."""
        email_service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        mock_smtp.login.assert_called_once()

    def test_send_template_email_success(self, email_service, mock_smtp):
        """Test sending email with Django template."""
        with patch("core.services.email_service.render_to_string") as mock_render:
            mock_render.return_value = "<p>Rendered template</p>"

            result = email_service.send_template_email(
                to_email="test@example.com",
                subject="Test",
                template_name="emails/test.html",
                context={"name": "John"},
            )

            assert result is True
            mock_render.assert_called_once_with("emails/test.html", {"name": "John"})
            mock_smtp.send_message.assert_called_once()

    def test_send_template_email_template_not_found(self, email_service):
        """Test sending email with non-existent template."""
        with patch("core.services.email_service.render_to_string") as mock_render:
            mock_render.side_effect = TemplateDoesNotExist("Template not found")

            with pytest.raises(TemplateDoesNotExist):
                email_service.send_template_email(
                    to_email="test@example.com",
                    subject="Test",
                    template_name="emails/nonexistent.html",
                )

    def test_html_to_plain_conversion(self, email_service):
        """Test HTML to plain text conversion."""
        html = "<h1>Title</h1><p>Paragraph with <strong>bold</strong> text.</p>"
        plain = email_service._html_to_plain(html)

        assert "Title" in plain
        assert "Paragraph with bold text." in plain
        assert "<h1>" not in plain
        assert "<p>" not in plain

    def test_html_entities_decoded(self, email_service):
        """Test HTML entities are decoded in plain text."""
        html = "<p>&lt;tag&gt; &amp; &quot;quotes&quot; &nbsp;</p>"
        plain = email_service._html_to_plain(html)

        assert "<tag>" in plain
        assert "&" in plain
        assert '"quotes"' in plain

    def test_valid_email_validation(self, email_service):
        """Test email validation for valid emails."""
        assert email_service._is_valid_email("test@example.com") is True
        assert email_service._is_valid_email("user.name+tag@example.co.uk") is True

    def test_invalid_email_validation(self, email_service):
        """Test email validation for invalid emails."""
        assert email_service._is_valid_email("invalid") is False
        assert email_service._is_valid_email("@example.com") is False
        assert email_service._is_valid_email("test@") is False
        assert email_service._is_valid_email("test @example.com") is False
