from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ealt import const
from ealt.converter import Converter


@patch("subprocess.run")
def test_convert_audio_ffmpeg_success(mock_run, tmp_path):
    # Setup paths and files
    original_downloads_dir = const.DOWNLOADS_DIR
    const.DOWNLOADS_DIR = tmp_path

    try:
        watch_id = "test_audio"
        source_file = tmp_path / f"{watch_id}.webm"
        source_file.write_text("dummy webm audio content")

        # Configure subprocess mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        cv = Converter()
        # Mock file system actions or target file creation since subprocess doesn't actually run
        output_file = tmp_path / f"{watch_id}.opus"

        # Simulate output file creation by ffmpeg
        def side_effect(*args, **kwargs):
            output_file.write_text("dummy opus content")
            return mock_result

        mock_run.side_effect = side_effect

        success = cv.convert_audio(watch_id, target_format="opus", keep_source=False)

        assert success is True
        assert output_file.exists()
        assert not source_file.exists()  # deleted since keep_source is False
        mock_run.assert_called_once()

    finally:
        const.DOWNLOADS_DIR = original_downloads_dir


@patch("subprocess.run")
def test_convert_image_magick_success(mock_run, tmp_path):
    original_downloads_dir = const.DOWNLOADS_DIR
    const.DOWNLOADS_DIR = tmp_path

    try:
        watch_id = "test_image"
        source_file = tmp_path / f"{watch_id}.webp"
        source_file.write_text("dummy webp image content")

        # Configure subprocess mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        cv = Converter()
        output_file = tmp_path / f"{watch_id}.jpg"

        # Simulate output file creation by magick
        def side_effect(*args, **kwargs):
            output_file.write_text("dummy jpg content")
            return mock_result

        mock_run.side_effect = side_effect

        success = cv.convert_image(watch_id, target_format=".jpg", keep_source=False, square_crop=True)

        assert success is True
        assert output_file.exists()
        assert not source_file.exists()
        mock_run.assert_called_once()

    finally:
        const.DOWNLOADS_DIR = original_downloads_dir
