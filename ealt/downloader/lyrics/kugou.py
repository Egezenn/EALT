import base64
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download(watch_id: str, artist: str, title: str, lrc_path: Path) -> bool:
    """Try to download lyrics from Kugou"""
    try:
        search_url = "http://lyrics.kugou.com/search"
        params = {
            "ver": 1,
            "man": "yes",
            "client": "pc",
            "keyword": f"{artist} {title}",
        }

        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != 200 or not data.get("candidates"):
            logger.debug(f"No kugou results for {watch_id}")
            return False

        candidate = data["candidates"][0]
        accesskey = candidate.get("accesskey")
        song_id = candidate.get("id")

        if not accesskey or not song_id:
            return False

        lyrics_url = "http://lyrics.kugou.com/download"
        params = {
            "ver": 1,
            "client": "pc",
            "id": song_id,
            "accesskey": accesskey,
            "fmt": "lrc",
            "charset": "utf8",
        }

        response = requests.get(lyrics_url, params=params, timeout=10)
        response.raise_for_status()
        lyrics_data = response.json()

        if lyrics_data.get("status") == 200 and lyrics_data.get("content"):
            lyrics_content = base64.b64decode(lyrics_data["content"]).decode("utf-8")
            lrc_path.write_text(lyrics_content, encoding="utf-8")
            logger.info(f"Downloaded synced lyrics for {watch_id} from kugou (.lrc)")
            return True

        return False

    except Exception as e:
        logger.debug(f"kugou failed for {watch_id}: {e}")
        return False
