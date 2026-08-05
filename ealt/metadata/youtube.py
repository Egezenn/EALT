import logging
from typing import Dict, Optional

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)


def fetch_youtube_metadata(watch_id: str) -> Optional[Dict[str, str]]:
    """Fetches metadata (artist, title, album) from YouTube Music."""
    try:
        ytmusic = YTMusic()
        song = ytmusic.get_song(watch_id)
        video_details = song.get("videoDetails", {})

        title = video_details.get("title")
        author = video_details.get("author")

        return {
            "artist": author,
            "title": title,
            "album": None,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch metadata for {watch_id}: {e}")
        return None
