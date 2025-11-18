"""Component tests for template list endpoint."""

from unittest.mock import patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User


class TestTemplateListEndpoint(TestCase):
    """Component tests for GET /templates."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.admin_id = uuid4()
        self.user_id = uuid4()
        self.url = "/api/v1/notification/templates"

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_user_scope_returns_200(self, mock_authenticate):
        """Test GET with user scope returns HTTP 200 with templates."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn("templates", data)
        self.assertIsInstance(data["templates"], list)

        # Verify template count (8 templates)
        self.assertEqual(len(data["templates"]), 9)

        # Verify first template structure
        template = data["templates"][0]
        self.assertIn("template_type", template)
        self.assertIn("display_name", template)
        self.assertIn("description", template)
        self.assertIn("required_fields", template)
        self.assertIn("endpoint", template)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_admin_scope_returns_200(self, mock_authenticate):
        """Test GET with admin scope returns HTTP 200 with templates."""
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["templates"]), 9)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_without_required_scope_returns_403(self, mock_authenticate):
        """Test GET without notification scope returns HTTP 403."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["some:other:scope"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "forbidden")
        self.assertIn("notification:user", data["detail"])

    def test_get_without_authentication_returns_401(self):
        """Test GET without authentication returns HTTP 401."""
        response = self.client.get(self.url)

        # DRF returns 401 for unauthenticated requests
        self.assertEqual(response.status_code, 401)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_returns_all_template_types(self, mock_authenticate):
        """Test GET returns all expected template types."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        template_types = [t["template_type"] for t in data["templates"]]

        expected_types = [
            "recipe_published",
            "recipe_liked",
            "recipe_commented",
            "new_follower",
            "mention",
            "password_reset",
            "recipe_trending",
            "email_changed",
            "password_changed",
        ]

        self.assertEqual(sorted(template_types), sorted(expected_types))

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_template_has_correct_required_fields(self, mock_authenticate):
        """Test each template has correct required_fields."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)
        data = response.json()

        # Find recipe_published template
        recipe_published = next(
            t for t in data["templates"] if t["template_type"] == "recipe_published"
        )

        # Verify required fields
        self.assertEqual(
            sorted(recipe_published["required_fields"]),
            sorted(["recipient_ids", "recipe_id"]),
        )

        # Verify endpoint
        self.assertEqual(
            recipe_published["endpoint"], "/notifications/recipe-published"
        )

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_password_reset_template_has_correct_fields(self, mock_authenticate):
        """Test password_reset template has correct required_fields."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)
        data = response.json()

        # Find password_reset template
        password_reset = next(
            t for t in data["templates"] if t["template_type"] == "password_reset"
        )

        # Verify required fields
        self.assertEqual(
            sorted(password_reset["required_fields"]),
            sorted(["recipient_ids", "reset_token", "expiry_hours"]),
        )

        # Verify endpoint
        self.assertEqual(password_reset["endpoint"], "/notifications/password-reset")

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_recipe_liked_template_has_liker_id(self, mock_authenticate):
        """Test recipe_liked template includes liker_id in required fields."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)
        data = response.json()

        # Find recipe_liked template
        recipe_liked = next(
            t for t in data["templates"] if t["template_type"] == "recipe_liked"
        )

        # Verify liker_id is in required fields
        self.assertIn("liker_id", recipe_liked["required_fields"])
        self.assertIn("recipe_id", recipe_liked["required_fields"])
        self.assertIn("recipient_ids", recipe_liked["required_fields"])

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_all_templates_have_display_names(self, mock_authenticate):
        """Test all templates have non-empty display names."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)
        data = response.json()

        for template in data["templates"]:
            self.assertIsNotNone(template["display_name"])
            self.assertGreater(len(template["display_name"]), 0)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_all_templates_have_descriptions(self, mock_authenticate):
        """Test all templates have non-empty descriptions."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)
        data = response.json()

        for template in data["templates"]:
            self.assertIsNotNone(template["description"])
            self.assertGreater(len(template["description"]), 0)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_all_templates_have_valid_endpoints(self, mock_authenticate):
        """Test all templates have endpoints starting with /notifications/."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        response = self.client.get(self.url)
        data = response.json()

        for template in data["templates"]:
            self.assertTrue(template["endpoint"].startswith("/notifications/"))
