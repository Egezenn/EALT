import base64
import logging
from pathlib import Path
from typing import Optional

from mutagen.flac import Picture
from mutagen.oggopus import OggOpus

logger = logging.getLogger(__name__)


def tag(
    audio_path: Path,
    cover_path: Optional[Path],
    artist: str,
    title: str,
    album: Optional[str] = None,
    desc: Optional[str] = None,
    lyrics_file: Optional[Path] = None,
    embed_extras: list = None,
):
    audio = OggOpus(audio_path)
    if artist:
        audio["artist"] = artist
    if title:
        audio["title"] = title
    if album:
        audio["album"] = album
    if desc:
        audio["DESCRIPTION"] = desc

    if "lyric" in embed_extras and lyrics_file and lyrics_file.exists():
        lyrics_text = lyrics_file.read_text(encoding="utf-8")
        audio["lyrics"] = lyrics_text

    if "cover" in embed_extras and cover_path and cover_path.exists():
        with open(cover_path, "rb") as img:
            image_data = img.read()

        pic = Picture()
        pic.data = image_data
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.desc = "Cover"

        audio["metadata_block_picture"] = [base64.b64encode(pic.write()).decode("ascii")]

    audio.save()
