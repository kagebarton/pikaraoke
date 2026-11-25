"""The words a YouTube channel adds to an act's name, in one place.

The search ranking and the Genius query both read an act off a channel name ("Adele Official",
"Journey - Topic"), and they must agree on what counts as that decoration.
"""

import re

CHANNEL_NOISE = re.compile(
    r"\s*-\s*topic$|\b(?:official|vevo|music|videos?|records|topic|channel|tv)\b|官方專屬頻道", re.I
)


def channel_words(channel: str) -> str:
    """The channel's name without the words YouTube channels add to an act's name.

    Noise glued to the name ("AdeleVEVO") is left in: each caller decides what that means, and
    which names stand for no act. The ranking keeps a glued VEVO in its credit name on purpose,
    because its measured results depend on that spelling.
    """
    return CHANNEL_NOISE.sub(" ", channel)
