import logging

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)


def fetch_youtube_metadata(watch_id: str) -> dict[str, str] | None:
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


def search_exact_match(artist: str, title: str, exclude_id: str | None = None) -> str | None:
    """
    Searches YouTube Music for a song that matches 100% on artist and title.
    Returns the matching videoId if found, else None.
    """
    if not artist or not title:
        return None

    query = f"{artist} {title}".strip()
    try:
        ytmusic = YTMusic()
        results = ytmusic.search(query, filter="songs", limit=20)
        target_artist = artist.strip().casefold()
        target_title = title.strip().casefold()

        for r in results:
            video_id = r.get("videoId")
            if not video_id or (exclude_id and video_id == exclude_id):
                continue

            r_title = (r.get("title") or "").strip().casefold()
            if r_title != target_title:
                continue

            r_artists = [
                a.get("name", "").strip()
                for a in r.get("artists", [])
                if isinstance(a, dict) and a.get("name")
            ]
            combined_artists = ", ".join(r_artists).casefold()

            if combined_artists == target_artist or any(a.casefold() == target_artist for a in r_artists):
                return video_id
    except Exception as e:
        logger.warning(f"Failed to search YouTube Music for '{artist} - {title}': {e}")

    return None

