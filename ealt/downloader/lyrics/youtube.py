import logging
from pathlib import Path

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)


def download(watch_id: str, lrc_path: Path) -> bool:
    """Try to download lyrics from YouTube Music"""
    try:
        ytmusic = YTMusic()
        watch_playlist = ytmusic.get_watch_playlist(videoId=watch_id)

        if not watch_playlist or "lyrics" not in watch_playlist:
            return False

        lyrics_browse_id = watch_playlist["lyrics"]
        if not lyrics_browse_id:
            return False

        lyrics_data = ytmusic.get_lyrics(lyrics_browse_id)
        if not lyrics_data or "lyrics" not in lyrics_data:
            return False

        lyrics_text = lyrics_data["lyrics"]

        if "syncedLyrics" in lyrics_data and lyrics_data["syncedLyrics"]:
            lrc_path.write_text(lyrics_data["syncedLyrics"], encoding="utf-8")
            logger.info(f"Downloaded synced lyrics for {watch_id} from YouTube (.lrc)")
            return True
        else:
            lrc_path.write_text(lyrics_text, encoding="utf-8")
            logger.info(f"Downloaded lyrics for {watch_id} from YouTube (.lrc)")
            return True

    except Exception as e:
        logger.debug(f"YouTube lyrics failed for {watch_id}: {e}")
        return False
