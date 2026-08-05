import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download(watch_id: str, artist: str, title: str, lrc_path: Path) -> bool:
    """Try to download lyrics from lrclib.net"""
    try:
        url = "https://lrclib.net/api/search"
        params = {"artist_name": artist, "track_name": title}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json()

        if not results or len(results) == 0:
            logger.debug(f"No lrclib results for {watch_id}")
            return False

        lyrics_data = results[0]

        if lyrics_data.get("syncedLyrics"):
            lrc_path.write_text(lyrics_data["syncedLyrics"], encoding="utf-8")
            logger.info(f"Downloaded synced lyrics for {watch_id} from lrclib (.lrc)")
            return True
        elif lyrics_data.get("plainLyrics"):
            lrc_path.write_text(lyrics_data["plainLyrics"], encoding="utf-8")
            logger.info(f"Downloaded lyrics for {watch_id} from lrclib (.lrc)")
            return True

        return False

    except Exception as e:
        logger.debug(f"lrclib failed for {watch_id}: {e}")
        return False
