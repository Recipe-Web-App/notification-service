"""Review model."""

from typing import ClassVar

from django.db import models


class Review(models.Model):
    """Review model matching recipe_manager.reviews table.

    This model represents recipe reviews/ratings with a 0-5 star scale.
    This model is unmanaged as the database schema is owned by another service.
    """

    review_id = models.BigAutoField(primary_key=True)
    recipe_id = models.BigIntegerField()
    user_id = models.UUIDField()
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Django model metadata."""

        db_table = "reviews"
        managed = False  # Schema is managed externally
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """Return string representation of review."""
        return (
            f"Review {self.review_id}: {self.rating} stars for recipe {self.recipe_id}"
        )

    def __repr__(self) -> str:
        """Return detailed representation of review."""
        return (
            f"<Review(review_id={self.review_id}, "
            f"recipe_id={self.recipe_id}, "
            f"user_id={self.user_id}, "
            f"rating={self.rating})>"
        )
