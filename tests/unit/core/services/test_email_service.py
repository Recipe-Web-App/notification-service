"""Tests for EmailService."""

import smtplib
from unittest.mock import MagicMock, patch

from django.template import TemplateDoesNotExist
from django.test import TestCase

from core.services.email_service import EmailService


class TestEmailService(TestCase):
    """Test suite for EmailService."""

    def setUp(self):
        """Set up test fixtures."""
        self.email_service = EmailService()

    @patch("core.services.email_service.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp_class):
        """Test successful email sending."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        result = self.email_service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<p>Test message</p>",
        )

        self.assertIs(result, True)
        mock_smtp.send_message.assert_called_once()

    @patch("core.services.email_service.smtplib.SMTP")
    def test_send_email_with_custom_from(self, mock_smtp_class):
        """Test sending email with custom from address."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        result = self.email_service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
            from_email="custom@example.com",
        )

        self.assertIs(result, True)
        call_args = mock_smtp.send_message.call_args[0][0]
        self.assertEqual(call_args["From"], "custom@example.com")

    def test_send_email_invalid_email(self):
        """Test sending email with invalid email address."""
        with self.assertRaisesRegex(ValueError, "Invalid email address"):
            self.email_service.send_email(
                to_email="invalid-email",
                subject="Test",
                html_content="<p>Test</p>",
            )

    def test_send_email_smtp_exception(self):
        """Test email sending with SMTP exception."""
        with patch("core.services.email_service.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value.send_message.side_effect = (
                smtplib.SMTPException("SMTP error")
            )

            with self.assertRaises(smtplib.SMTPException):
                self.email_service.send_email(
                    to_email="test@example.com",
                    subject="Test",
                    html_content="<p>Test</p>",
                )

    @patch("core.services.email_service.smtplib.SMTP")
    def test_send_email_uses_tls(self, mock_smtp_class):
        """Test that email service uses TLS."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        self.email_service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        mock_smtp.starttls.assert_called_once()

    @patch("core.services.email_service.smtplib.SMTP")
    def test_send_email_authenticates(self, mock_smtp_class):
        """Test that email service authenticates with SMTP server."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        self.email_service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        mock_smtp.login.assert_called_once()

    @patch("core.services.email_service.smtplib.SMTP")
    def test_send_template_email_success(self, mock_smtp_class):
        """Test sending email with Django template."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        with patch("core.services.email_service.render_to_string") as mock_render:
            mock_render.return_value = "<p>Rendered template</p>"

            result = self.email_service.send_template_email(
                to_email="test@example.com",
                subject="Test",
                template_name="emails/test.html",
                context={"name": "John"},
            )

            self.assertIs(result, True)
            mock_render.assert_called_once_with("emails/test.html", {"name": "John"})
            mock_smtp.send_message.assert_called_once()

    def test_send_template_email_template_not_found(self):
        """Test sending email with non-existent template."""
        with patch("core.services.email_service.render_to_string") as mock_render:
            mock_render.side_effect = TemplateDoesNotExist("Template not found")

            with self.assertRaises(TemplateDoesNotExist):
                self.email_service.send_template_email(
                    to_email="test@example.com",
                    subject="Test",
                    template_name="emails/nonexistent.html",
                )

    def test_html_to_plain_conversion(self):
        """Test HTML to plain text conversion."""
        html = "<h1>Title</h1><p>Paragraph with <strong>bold</strong> text.</p>"
        plain = self.email_service._html_to_plain(html)

        self.assertIn("Title", plain)
        self.assertIn("Paragraph with bold text.", plain)
        self.assertNotIn("<h1>", plain)
        self.assertNotIn("<p>", plain)

    def test_html_entities_decoded(self):
        """Test HTML entities are decoded in plain text."""
        html = "<p>&lt;tag&gt; &amp; &quot;quotes&quot; &nbsp;</p>"
        plain = self.email_service._html_to_plain(html)

        self.assertIn("<tag>", plain)
        self.assertIn("&", plain)
        self.assertIn('"quotes"', plain)

    def test_valid_email_validation(self):
        """Test email validation for valid emails."""
        self.assertIs(self.email_service._is_valid_email("test@example.com"), True)
        self.assertIs(
            self.email_service._is_valid_email("user.name+tag@example.co.uk"), True
        )

    def test_invalid_email_validation(self):
        """Test email validation for invalid emails."""
        self.assertIs(self.email_service._is_valid_email("invalid"), False)
        self.assertIs(self.email_service._is_valid_email("@example.com"), False)
        self.assertIs(self.email_service._is_valid_email("test@"), False)
        self.assertIs(self.email_service._is_valid_email("test @example.com"), False)
