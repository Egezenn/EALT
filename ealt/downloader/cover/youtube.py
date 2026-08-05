import logging
import subprocess

import requests
from ytmusicapi import YTMusic

from ... import const

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download(watch_id: str) -> bool:
    """Try to download cover art cascading from best to worst methods."""
    # 1. Try YouTube Music API (highest quality / square aspect ratio)
    try:
        ytmusic = YTMusic()
        song_info = ytmusic.get_song(watch_id)
        thumbnails = song_info.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [])

        if thumbnails:
            best_thumbnail = max(thumbnails, key=lambda x: x.get("width", 0) * x.get("height", 0))
            cover_url = best_thumbnail["url"]

            response = requests.get(cover_url, headers=HEADERS, timeout=10)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "webp" in content_type or cover_url.endswith(".webp"):
                cover_path = const.DOWNLOADS_DIR / f"{watch_id}.webp"
            else:
                cover_path = const.DOWNLOADS_DIR / f"{watch_id}.jpg"

            cover_path.write_bytes(response.content)
            logger.info(
                f"Downloaded cover art for {watch_id} ({best_thumbnail.get('width')}x{best_thumbnail.get('height')})"
            )
            return True
    except Exception as e:
        logger.debug(f"ytmusicapi download failed: {e}")

    # 2. Try direct WebP fallbacks
    for quality in ["maxresdefault", "sddefault", "hqdefault"]:
        try:
            cover_url = f"https://i.ytimg.com/vi_webp/{watch_id}/{quality}.webp"
            response = requests.get(cover_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            cover_path = const.DOWNLOADS_DIR / f"{watch_id}.webp"
            cover_path.write_bytes(response.content)
            logger.info(f"Downloaded WebP cover art for {watch_id} ({quality})")
            return True
        except Exception:
            continue

    # 3. Try direct JPG fallbacks
    for quality in ["maxresdefault", "sddefault", "hqdefault"]:
        try:
            cover_url = f"https://i.ytimg.com/vi/{watch_id}/{quality}.jpg"
            response = requests.get(cover_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            cover_path = const.DOWNLOADS_DIR / f"{watch_id}.jpg"
            cover_path.write_bytes(response.content)
            logger.info(f"Downloaded JPG cover art for {watch_id} ({quality})")
            return True
        except Exception:
            continue

    # 4. Try via oEmbed JSON endpoint
    if _download_via_oembed(watch_id):
        return True

    # 5. Try via yt-dlp --write-thumbnail as ultimate fallback
    if _download_via_ytdlp(watch_id):
        return True

    logger.warning(f"Failed to download cover for {watch_id} from all sources")
    return False


def _download_via_oembed(watch_id: str) -> bool:
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={watch_id}&format=json"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        thumbnail_url = data.get("thumbnail_url")
        if thumbnail_url:
            img_res = requests.get(thumbnail_url, headers=HEADERS, timeout=10)
            img_res.raise_for_status()

            content_type = img_res.headers.get("content-type", "")
            if "webp" in content_type or thumbnail_url.endswith(".webp"):
                cover_path = const.DOWNLOADS_DIR / f"{watch_id}.webp"
            else:
                cover_path = const.DOWNLOADS_DIR / f"{watch_id}.jpg"

            cover_path.write_bytes(img_res.content)
            logger.info(f"Downloaded cover art for {watch_id} via oEmbed")
            return True
    except Exception as e:
        logger.debug(f"oEmbed thumbnail download failed: {e}")
    return False


def _download_via_ytdlp(watch_id: str) -> bool:
    try:
        cmd = [
            "yt-dlp",
            "--write-thumbnail",
            "--skip-download",
            "--output",
            str(const.DOWNLOADS_DIR / watch_id),
            f"https://www.youtube.com/watch?v={watch_id}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            for ext in [".jpg", ".jpeg", ".webp", ".png"]:
                path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
                if path.exists():
                    logger.info(f"Downloaded cover art for {watch_id} via yt-dlp ({ext})")
                    return True
        else:
            logger.debug(f"yt-dlp thumbnail download failed: {result.stderr}")
    except Exception as e:
        logger.debug(f"yt-dlp thumbnail download failed: {e}")
    return False
