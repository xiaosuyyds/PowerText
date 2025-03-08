import os
from io import BytesIO
from typing import Optional
from pilmoji import source


class LocalEmojiSource(source.BaseSource):
    """A local source for emoji images."""

    def __init__(self, emoji_directory: str) -> None:
        """Initializes the local emoji source.

        Parameters
        ----------
        emoji_directory: str
            The directory where emoji images are stored.
        """
        self.emoji_directory = emoji_directory

    def _emoji_to_filename(self, emoji: str) -> str:
        """Converts an emoji character into a filename matching the local storage format."""
        codepoints = "_".join(f"u{ord(c):04x}" for c in emoji)
        return f"emoji_{codepoints}.png"

    def get_emoji(self, emoji: str, /) -> Optional[BytesIO]:
        """Retrieves an emoji image from the local directory."""
        filename = os.path.join(self.emoji_directory, self._emoji_to_filename(emoji))

        if not os.path.isfile(filename):
            return None

        with open(filename, "rb") as f:
            return BytesIO(f.read())

    def get_discord_emoji(self, id: int, /) -> Optional[BytesIO]:
        """Retrieves a Discord emoji image from the local directory."""
        filename = os.path.join(self.emoji_directory, f"discord_{id}.png")

        if not os.path.isfile(filename):
            raise FileNotFoundError(f"Discord emoji {id} not found.")

        with open(filename, "rb") as f:
            return BytesIO(f.read())

    def __repr__(self) -> str:
        return f"<LocalEmojiSource directory={self.emoji_directory}>"
