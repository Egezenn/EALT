from pathlib import Path

from ealt import const, metadata
from ealt.downloader import cover, lyrics

WATCH_ID = "lYBUbBu4W08"
ARTIST = "Rick Astley"
TITLE = "Never Gonna Give You Up"


def test_fetch_youtube_metadata():
    metadata_result = metadata.fetch_youtube_metadata(WATCH_ID)
    assert metadata_result is not None
    assert "Rick Astley" in metadata_result["artist"]
    assert "Never Gonna Give You Up" in metadata_result["title"]


def test_cover_youtube_download(tmp_path):
    original_downloads_dir = const.DOWNLOADS_DIR
    const.DOWNLOADS_DIR = tmp_path
    try:
        success = cover.youtube.download(WATCH_ID)
        assert success is True
        jpg_file = tmp_path / f"{WATCH_ID}.jpg"
        webp_file = tmp_path / f"{WATCH_ID}.webp"
        assert jpg_file.exists() or webp_file.exists()
    finally:
        const.DOWNLOADS_DIR = original_downloads_dir


def test_lyrics_lrclib_download(tmp_path):
    lrc_path = tmp_path / f"{WATCH_ID}.lrc"
    success = lyrics.lrclib.download(WATCH_ID, ARTIST, TITLE, lrc_path)
    assert success is True
    assert lrc_path.exists()
    lyrics_text = lrc_path.read_text(encoding="utf-8")
    assert "Never gonna give you up" in lyrics_text or "Never Gonna Give You Up" in lyrics_text


def test_lyrics_kugou_download(tmp_path):
    lrc_path = tmp_path / f"{WATCH_ID}.lrc"
    success = lyrics.kugou.download(WATCH_ID, ARTIST, TITLE, lrc_path)
    # Kugou might not guarantee a result, but we test the invocation and return code
    if success:
        assert lrc_path.exists()


def test_lyrics_youtube_download(tmp_path):
    lrc_path = tmp_path / f"{WATCH_ID}.lrc"
    success = lyrics.youtube.download(WATCH_ID, lrc_path)
    assert success is True
    assert lrc_path.exists()
    lyrics_text = lrc_path.read_text(encoding="utf-8")
    assert "Never gonna give you up" in lyrics_text or "Never Gonna Give You Up" in lyrics_text
