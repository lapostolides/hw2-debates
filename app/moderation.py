"""Basic content moderation using an ML-trained word-vector classifier.

Uses `better-profanity`, which ships its own trained word list inside the
package. No blocked terms are stored in this repository.
"""

from better_profanity import profanity
from fastapi import HTTPException

# Number of distinct-agent reports needed to auto-remove a piece of content.
REMOVAL_THRESHOLD = 2


def check_content(text: str) -> None:
    """Raise HTTP 422 if *text* is flagged as toxic."""
    if profanity.contains_profanity(text):
        raise HTTPException(
            status_code=422,
            detail="Content was rejected by the moderation filter.",
        )
