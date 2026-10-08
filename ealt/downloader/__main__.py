"yt-dlp based YouTube Watch ID downloader"

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .. import const, metadata, utils
from . import cover, lyrics

logger = logging.getLogger(__name__)

_errors_lock = threading.Lock()


def _extract_error_reason(watch_id: str, stderr: str) -> str:
    lines = stderr.strip().splitlines()
    error_lines = [line for line in lines if line.startswith("ERROR:")]
    if error_lines:
        reason = error_lines[-1]
        for prefix in (f"ERROR: [youtube] {watch_id}: ", f"ERROR: {watch_id}: "):
            if reason.startswith(prefix):
                return reason[len(prefix) :]
        return reason
    return stderr.strip()


def record_download_error(watch_id: str, reason: str):
    """Records a download failure reason to errors.json."""
    with _errors_lock:
        errors = utils.read_json(const.ERRORS_FILE)
        errors[watch_id] = {"reason": reason, "time": int(time.time())}
        utils.write_json(const.ERRORS_FILE, errors)


def remove_download_error(watch_id: str):
    """Removes a download failure entry from errors.json."""
    with _errors_lock:
        errors = utils.read_json(const.ERRORS_FILE)
        if watch_id in errors:
            del errors[watch_id]
            utils.write_json(const.ERRORS_FILE, errors)


def cleanup_resolved_errors() -> int:
    """Removes entries from errors.json if their corresponding audio file exists."""
    with _errors_lock:
        errors = utils.read_json(const.ERRORS_FILE)
        if not errors:
            return 0

        to_remove = [
            watch_id
            for watch_id in errors
            if any((const.DOWNLOADS_DIR / f"{watch_id}{ext}").exists() for ext in const.AUDIO_EXTENSIONS)
        ]

        if to_remove:
            for wid in to_remove:
                del errors[wid]
            utils.write_json(const.ERRORS_FILE, errors)
            logger.info(f"Cleaned up {len(to_remove)} resolved entries from {const.ERRORS_FILE}")
            return len(to_remove)

        return 0




class Downloader:
    def __init__(
        self,
        download_extras: list = None,
        remote_components: bool = True,
        cookies: bool | Path | str | None = False,
    ):
        self.download_extras = download_extras or []
        self.remote_components = remote_components
        self.cookies = utils.resolve_cookies(cookies)


    def fetch_metadata(self, watch_id: str) -> dict[str, str] | None:
        """
        Fetches metadata (artist, title, album) from YouTube Music.
        """
        return metadata.fetch_youtube_metadata(watch_id)

    def download(
        self,
        watch_id: str,
        artist: str | None = None,
        title: str | None = None,
        existing_meta: dict[str, Any] | None = None,
    ) -> bool:
        """
        Downloads audio and cover art for a given watch_id.
        Returns True on success.
        """
        existing_meta = existing_meta or {}

        existing_files = list(const.DOWNLOADS_DIR.glob(f"{watch_id}.*"))
        has_audio = any(f.suffix in const.AUDIO_EXTENSIONS for f in existing_files)

        has_cover = any((const.DOWNLOADS_DIR / f"{watch_id}{ext}").exists() for ext in const.IMAGE_EXTENSIONS)

        if has_audio:
            logger.info(f"Skipping audio download for {watch_id} (already exists)")
        else:
            url = f"https://www.youtube.com/watch?v={watch_id}"
            output_template = str(const.DOWNLOADS_DIR / f"{watch_id}.%(ext)s")

            cmd = [
                "yt-dlp",
                "--format",
                "bestaudio/best",
                "--output",
                output_template,
                "--quiet",
                "--ignore-errors",
            ]
            if self.remote_components:
                cmd.extend(["--remote-components", "ejs:github"])
            if self.cookies:
                cmd.extend(["--cookies", str(self.cookies)])
            cmd.append(url)

            try:
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    logger.error(f"yt-dlp failed for {watch_id}: {result.stderr}")
                    record_download_error(
                        watch_id,
                        _extract_error_reason(watch_id, result.stderr)
                        or f"yt-dlp exited with code {result.returncode}",
                    )
                    return False

            except Exception as e:
                logger.error(f"Audio download failed for {watch_id}: {e}")
                record_download_error(watch_id, str(e))
                return False

        if "cover" in self.download_extras:
            if has_cover:
                logger.info(f"Skipping cover art download for {watch_id} (already exists)")
            else:
                cover.youtube.download(
                    watch_id,
                    remote_components=self.remote_components,
                    cookies=self.cookies,
                )


        if "lyric" in self.download_extras:
            if artist and title:

                self._download_lyrics(watch_id, artist, title)
            else:
                logger.info(f"Skipping lyrics download for {watch_id} (missing artist and/or title metadata)")

        return True

    def _download_lyrics(self, watch_id: str, artist: str | None = None, title: str | None = None) -> bool:
        """
        Downloads lyrics for a given watch_id.
        Tries multiple sources in order: lrclib -> kugou -> YouTube Music.
        Saves as .lrc file.
        Returns True if successful, False otherwise.
        """
        lrc_path = const.DOWNLOADS_DIR / f"{watch_id}.lrc"

        if lrc_path.exists():
            logger.info(f"Skipping lyrics download for {watch_id} (already exists)")
            return True

        if artist and title:
            if lyrics.lrclib.download(watch_id, artist, title, lrc_path):
                return True

            if lyrics.kugou.download(watch_id, artist, title, lrc_path):
                return True

        if lyrics.youtube.download(watch_id, lrc_path):
            return True

        logger.info(f"No lyrics available for {watch_id} from any source")
        return False
