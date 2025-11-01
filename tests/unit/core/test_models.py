"""Unit tests for core.models module."""

import unittest
import uuid

from core.enums import UserRole
from core.models import User, UserFollow


class TestUserModel(unittest.TestCase):
    """Tests for User model."""

    def test_user_model_has_correct_db_table_name(self):
        """Test that User model uses correct database table name."""
        self.assertEqual(User._meta.db_table, "users")

    def test_user_model_ordering(self):
        """Test that User model orders by created_at descending."""
        self.assertEqual(User._meta.ordering, ["-created_at"])

    def test_user_model_has_expected_fields(self):
        """Test that User model has all expected fields."""
        expected_fields = {
            "user_id",
            "role",
            "username",
            "email",
            "password_hash",
            "full_name",
            "bio",
            "is_active",
            "created_at",
            "updated_at",
        }
        actual_fields = {field.name for field in User._meta.get_fields()}
        self.assertTrue(expected_fields.issubset(actual_fields))

    def test_user_str_representation(self):
        """Test User __str__ method returns username and email."""
        user = User(
            user_id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="hash123",
        )
        self.assertEqual(str(user), "testuser (test@example.com)")

    def test_user_repr_representation(self):
        """Test User __repr__ method returns detailed info."""
        user_id = uuid.uuid4()
        user = User(
            user_id=user_id,
            username="testuser",
            email="test@example.com",
            password_hash="hash123",
        )
        expected = f"<User(user_id={user_id}, username='testuser')>"
        self.assertEqual(repr(user), expected)

    def test_user_role_choices(self):
        """Test that User role field has correct choices."""
        role_field = User._meta.get_field("role")
        expected_choices = [
            (UserRole.ADMIN.value, UserRole.ADMIN.value),
            (UserRole.USER.value, UserRole.USER.value),
        ]
        self.assertEqual(role_field.choices, expected_choices)

    def test_user_role_default_value(self):
        """Test that User role defaults to USER."""
        role_field = User._meta.get_field("role")
        self.assertEqual(role_field.default, UserRole.USER.value)

    def test_user_username_is_unique(self):
        """Test that username field is unique."""
        username_field = User._meta.get_field("username")
        self.assertTrue(username_field.unique)

    def test_user_email_is_unique(self):
        """Test that email field is unique."""
        email_field = User._meta.get_field("email")
        self.assertTrue(email_field.unique)

    def test_user_full_name_is_optional(self):
        """Test that full_name field is optional."""
        full_name_field = User._meta.get_field("full_name")
        self.assertFalse(full_name_field.null)
        self.assertTrue(full_name_field.blank)
        self.assertEqual(full_name_field.default, "")

    def test_user_bio_is_optional(self):
        """Test that bio field is optional."""
        bio_field = User._meta.get_field("bio")
        self.assertFalse(bio_field.null)
        self.assertTrue(bio_field.blank)
        self.assertEqual(bio_field.default, "")

    def test_user_is_active_defaults_to_true(self):
        """Test that is_active defaults to True."""
        is_active_field = User._meta.get_field("is_active")
        self.assertTrue(is_active_field.default)


class TestUserFollowModel(unittest.TestCase):
    """Tests for UserFollow model."""

    def test_user_follow_model_has_correct_db_table_name(self):
        """Test that UserFollow model uses correct database table name."""
        self.assertEqual(UserFollow._meta.db_table, "user_follows")

    def test_user_follow_model_ordering(self):
        """Test that UserFollow model orders by followed_at descending."""
        self.assertEqual(UserFollow._meta.ordering, ["-followed_at"])

    def test_user_follow_model_has_expected_fields(self):
        """Test that UserFollow model has all expected fields."""
        expected_fields = {"follower", "followee", "followed_at"}
        actual_fields = {field.name for field in UserFollow._meta.get_fields()}
        self.assertTrue(expected_fields.issubset(actual_fields))

    def test_user_follow_has_unique_together_constraint(self):
        """Test that UserFollow has unique constraint on follower+followee."""
        self.assertEqual(UserFollow._meta.unique_together, (("follower", "followee"),))

    def test_user_follow_follower_has_correct_db_column(self):
        """Test that follower field maps to follower_id column."""
        follower_field = UserFollow._meta.get_field("follower")
        self.assertEqual(follower_field.db_column, "follower_id")

    def test_user_follow_followee_has_correct_db_column(self):
        """Test that followee field maps to followee_id column."""
        followee_field = UserFollow._meta.get_field("followee")
        self.assertEqual(followee_field.db_column, "followee_id")

    def test_user_follow_follower_related_name(self):
        """Test that follower field has correct related name."""
        follower_field = UserFollow._meta.get_field("follower")
        self.assertEqual(follower_field.remote_field.related_name, "following")

    def test_user_follow_followee_related_name(self):
        """Test that followee field has correct related name."""
        followee_field = UserFollow._meta.get_field("followee")
        self.assertEqual(followee_field.remote_field.related_name, "followers")

    def test_user_follow_str_representation(self):
        """Test UserFollow __str__ method returns follower-followee info."""
        follower = User(
            user_id=uuid.uuid4(),
            username="follower_user",
            email="follower@example.com",
            password_hash="hash1",
        )
        followee = User(
            user_id=uuid.uuid4(),
            username="followee_user",
            email="followee@example.com",
            password_hash="hash2",
        )
        user_follow = UserFollow(follower=follower, followee=followee)
        self.assertEqual(str(user_follow), "follower_user follows followee_user")

    def test_user_follow_repr_representation(self):
        """Test UserFollow __repr__ method returns detailed info."""
        follower = User(
            user_id=uuid.uuid4(),
            username="follower_user",
            email="follower@example.com",
            password_hash="hash1",
        )
        followee = User(
            user_id=uuid.uuid4(),
            username="followee_user",
            email="followee@example.com",
            password_hash="hash2",
        )
        user_follow = UserFollow(follower=follower, followee=followee)
        expected = "<UserFollow(follower=follower_user, followee=followee_user)>"
        self.assertEqual(repr(user_follow), expected)


if __name__ == "__main__":
    unittest.main()
