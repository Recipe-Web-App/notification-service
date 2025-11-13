"""Recipe difficulty levels enumeration."""

from enum import Enum


class DifficultyLevel(str, Enum):
    """Recipe difficulty levels."""

    BEGINNER = "BEGINNER"
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"
