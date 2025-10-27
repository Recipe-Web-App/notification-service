"""Unit tests for core.repositories.user_repository module."""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from core.repositories import UserRepository


class TestUserRepository(unittest.TestCase):
    """Tests for UserRepository."""

    @patch("core.repositories.user_repository.User")
    def test_get_users_by_ids_filters_correctly(self, mock_user_model):
        """Test that get_users_by_ids filters by user_id__in."""
        user_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        mock_queryset = MagicMock()
        mock_user_model.objects.filter.return_value = mock_queryset

        result = UserRepository.get_users_by_ids(user_ids)

        mock_user_model.objects.filter.assert_called_once_with(user_id__in=user_ids)
        self.assertEqual(result, mock_queryset)

    @patch("core.repositories.user_repository.User")
    def test_get_users_by_ids_with_empty_list(self, mock_user_model):
        """Test that get_users_by_ids handles empty list."""
        user_ids = []
        mock_queryset = MagicMock()
        mock_user_model.objects.filter.return_value = mock_queryset

        result = UserRepository.get_users_by_ids(user_ids)

        mock_user_model.objects.filter.assert_called_once_with(user_id__in=[])
        self.assertEqual(result, mock_queryset)

    @patch("core.repositories.user_repository.UserFollow")
    def test_user_follows_returns_true_when_exists(self, mock_userfollow_model):
        """Test that user_follows returns True when relationship exists."""
        follower_id = uuid.uuid4()
        followee_id = uuid.uuid4()
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_userfollow_model.objects.filter.return_value = mock_queryset

        result = UserRepository.user_follows(follower_id, followee_id)

        mock_userfollow_model.objects.filter.assert_called_once_with(
            follower_id=follower_id, followee_id=followee_id
        )
        mock_queryset.exists.assert_called_once()
        self.assertTrue(result)

    @patch("core.repositories.user_repository.UserFollow")
    def test_user_follows_returns_false_when_not_exists(self, mock_userfollow_model):
        """Test that user_follows returns False when relationship doesn't exist."""
        follower_id = uuid.uuid4()
        followee_id = uuid.uuid4()
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_userfollow_model.objects.filter.return_value = mock_queryset

        result = UserRepository.user_follows(follower_id, followee_id)

        mock_userfollow_model.objects.filter.assert_called_once_with(
            follower_id=follower_id, followee_id=followee_id
        )
        mock_queryset.exists.assert_called_once()
        self.assertFalse(result)

    @patch("core.repositories.user_repository.UserFollow")
    def test_user_follows_with_same_user(self, mock_userfollow_model):
        """Test user_follows when checking if user follows themselves."""
        user_id = uuid.uuid4()
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_userfollow_model.objects.filter.return_value = mock_queryset

        result = UserRepository.user_follows(user_id, user_id)

        mock_userfollow_model.objects.filter.assert_called_once_with(
            follower_id=user_id, followee_id=user_id
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
