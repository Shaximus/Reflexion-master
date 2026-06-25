"""
virality_factors.py
--------------------

Defines an enumeration of factors that influence the virality of content
on social media.  Each member of the enumeration represents a distinct
psychological or contextual trigger that can increase the likelihood
that a piece of content will be shared widely.  The auto() function is
used to assign unique values to each factor without manually
specifying integers.
"""

from enum import Enum, auto


class ViralityFactors(Enum):
    """Factors that increase the virality of content."""

    # Polarizing content that sparks debate
    CONTROVERSY = auto()
    # Content that elicits a strong emotional response
    EMOTION = auto()
    # Information gaps or intriguing questions that provoke curiosity
    CURIOSITY = auto()
    # Content that resonates with universal experiences
    RELATABILITY = auto()
    # Time‑sensitive or urgent content encouraging immediate action
    URGENCY = auto()
    # Unexplained phenomena or mysteries that invite speculation
    MYSTERY = auto()
    # Unexpected humor that delights and surprises
    HUMOR = auto()
    # Content that taps into existential or primal fears
    FEAR = auto()
    # Optimistic or uplifting visions of the future
    HOPE = auto()
    # Shocking revelations that upend expectations
    SHOCK = auto()
    # Mind‑opening discoveries that offer new perspectives
    REVELATION = auto()


__all__ = ["ViralityFactors"]
