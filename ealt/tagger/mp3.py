import logging
from pathlib import Path
from typing import Optional

from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, COMM, ID3, USLT, ID3NoHeaderError

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
    try:
        audio = ID3(audio_path)
    except ID3NoHeaderError:
        audio = ID3()

    if desc:
        audio.add(COMM(encoding=3, lang="eng", desc="Description", text=desc))

    if "cover" in embed_extras and cover_path and cover_path.exists():
        with open(cover_path, "rb") as albumart:
            audio.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=albumart.read(),
                )
            )

    if "lyric" in embed_extras and lyrics_file and lyrics_file.exists():
        lyrics_text = lyrics_file.read_text(encoding="utf-8")
        audio.add(USLT(encoding=3, lang="xxx", desc="", text=lyrics_text))

    audio.save(audio_path, v2_version=3)

    try:
        audio_easy = EasyID3(audio_path)
    except ID3NoHeaderError:
        audio_easy = EasyID3()

    if artist:
        audio_easy["artist"] = artist
    if title:
        audio_easy["title"] = title
    if album:
        audio_easy["album"] = album
    audio_easy.save(audio_path, v2_version=3)
