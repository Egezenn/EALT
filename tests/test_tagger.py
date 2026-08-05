from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ealt import const
from ealt.tagger import Tagger


@patch("ealt.tagger.mp3.ID3")
@patch("ealt.tagger.mp3.EasyID3")
def test_tag_mp3_success(mock_easy_id3, mock_id3, tmp_path):
    original_downloads_dir = const.DOWNLOADS_DIR
    const.DOWNLOADS_DIR = tmp_path

    try:
        watch_id = "test_tag_mp3"
        audio_file = tmp_path / f"{watch_id}.mp3"
        audio_file.write_text("dummy mp3 content")

        # Configure mocks
        mock_id3_instance = MagicMock()
        mock_id3.return_value = mock_id3_instance

        mock_easy_instance = MagicMock()
        mock_easy_id3.return_value = mock_easy_instance

        tg = Tagger()
        success = tg.tag(
            watch_id,
            artist="Artist Name",
            title="Track Title",
            album="Album Name",
            desc="Description",
            delete_embeds=False,
            embed_extras=["cover"],
        )

        assert success is True
        mock_id3_instance.save.assert_called_once()
        mock_easy_instance.save.assert_called_once()

    finally:
        const.DOWNLOADS_DIR = original_downloads_dir


@patch("ealt.tagger.opus.OggOpus")
def test_tag_opus_success(mock_ogg_opus, tmp_path):
    original_downloads_dir = const.DOWNLOADS_DIR
    const.DOWNLOADS_DIR = tmp_path

    try:
        watch_id = "test_tag_opus"
        audio_file = tmp_path / f"{watch_id}.opus"
        audio_file.write_text("dummy opus content")

        # Configure mock
        mock_opus_instance = MagicMock()
        mock_ogg_opus.return_value = mock_opus_instance

        tg = Tagger()
        success = tg.tag(
            watch_id,
            artist="Artist Name",
            title="Track Title",
            album="Album Name",
            desc="Description",
            delete_embeds=False,
            embed_extras=[],
        )

        assert success is True
        mock_opus_instance.save.assert_called_once()

    finally:
        const.DOWNLOADS_DIR = original_downloads_dir
