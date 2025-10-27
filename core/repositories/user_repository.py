"""Repository for user-related database queries."""

from uuid import UUID

from django.db.models import QuerySet

from core.models import User, UserFollow


class UserRepository:
    """Repository for encapsulating user database queries.

    Provides a clean interface for common user-related database operations
    needed by the notification service.
    """

    @staticmethod
    def get_users_by_ids(user_ids: list[UUID]) -> QuerySet[User]:
        """Batch lookup users by their IDs.

        Efficiently retrieves multiple users in a single database query.
        Useful for bulk operations when sending notifications to multiple users.

        Args:
            user_ids: List of user UUIDs to look up

        Returns:
            QuerySet of User objects matching the provided IDs

        Example:
            >>> user_ids = [uuid1, uuid2, uuid3]
            >>> users = UserRepository.get_users_by_ids(user_ids)
            >>> for user in users:
            ...     print(user.email)
        """
        return User.objects.filter(user_id__in=user_ids)

    @staticmethod
    def user_follows(follower_id: UUID, followee_id: UUID) -> bool:
        """Check if one user follows another.

        Useful for authorization checks before sending follow-related notifications.

        Args:
            follower_id: UUID of the user who might be following
            followee_id: UUID of the user who might be followed

        Returns:
            True if follower_id follows followee_id, False otherwise

        Example:
            >>> follows = UserRepository.user_follows(user_a_id, user_b_id)
            >>> if follows:
            ...     print("User A follows User B")
        """
        return UserFollow.objects.filter(
            follower_id=follower_id, followee_id=followee_id
        ).exists()
