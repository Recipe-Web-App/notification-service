"""UserFollow model."""

from typing import ClassVar

from django.db import models


class UserFollow(models.Model):
    """User follow relationship model matching recipe_manager.user_follows table.

    This model tracks follower relationships between users.
    This model is unmanaged as the database schema is owned by another service.
    """

    follower = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="following",
        db_column="follower_id",
    )
    followee = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="followers",
        db_column="followee_id",
    )
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Django model metadata."""

        db_table = "user_follows"
        managed = False  # Schema is managed externally
        unique_together: ClassVar[list[list[str]]] = [["follower", "followee"]]
        ordering: ClassVar[list[str]] = ["-followed_at"]

    def __str__(self) -> str:
        """Return string representation of follow relationship."""
        return f"{self.follower.username} follows {self.followee.username}"

    def __repr__(self) -> str:
        """Return detailed representation of follow relationship."""
        return (
            f"<UserFollow(follower={self.follower.username}, "
            f"followee={self.followee.username})>"
        )
