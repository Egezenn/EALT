import logging
from typing import Optional

from .. import const
from . import mp3, opus

logger = logging.getLogger(__name__)


class Tagger:
    def tag(
        self,
        watch_id: str,
        artist: str,
        title: str,
        album: Optional[str] = None,
        desc: Optional[str] = None,
        delete_embeds: bool = False,
        embed_extras: list = None,
    ) -> bool:
        """
        Tags the audio file with artist, title, cover art, and lyrics.
        Optionally deletes source files after embedding.
        """
        audio_file = None
        for ext in [".opus", ".mp3"]:
            path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
            if path.exists():
                audio_file = path
                break

        if not audio_file:
            logger.error(f"No audio file found for {watch_id} to tag")
            return False

        cover_file = None
        for ext in [".jpg", ".webp"]:
            path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
            if path.exists():
                cover_file = path
                break

        lyrics_file = None
        for ext in [".lrc", ".txt"]:
            path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
            if path.exists():
                lyrics_file = path
                break

        try:
            embed_extras = embed_extras or []
            if audio_file.suffix == ".mp3":
                mp3.tag(audio_file, cover_file, artist, title, album, desc, lyrics_file, embed_extras)
            elif audio_file.suffix == ".opus":
                opus.tag(audio_file, cover_file, artist, title, album, desc, lyrics_file, embed_extras)

            if delete_embeds:
                if lyrics_file and lyrics_file.exists():
                    lyrics_file.unlink()
                    logger.info(f"Deleted embedded lyrics file: {lyrics_file.name}")
                if cover_file and cover_file.exists():
                    cover_file.unlink()
                    logger.info(f"Deleted embedded cover file: {cover_file.name}")

            logger.info(f"Tagged {watch_id}: {artist} - {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to tag {watch_id}: {e}")
            return False
