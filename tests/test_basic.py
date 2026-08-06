import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ealt import const, utils
from ealt.__main__ import cli

runner = CliRunner()


def test_parse_extras():
    """Test the parse_extras utility function."""
    assert utils.parse_extras("cover,lyric") == ["cover", "lyric"]
    assert utils.parse_extras(" cover , lyric ") == ["cover", "lyric"]
    assert utils.parse_extras("") == []
    assert utils.parse_extras(None) == []


def test_cli_help():
    """Smoke test to ensure the CLI help command runs without error."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "EALT" in result.output
    # The output might vary, check basic presence
    assert "Download a single video" in result.output


def test_check_dependencies(capsys):
    """Test that check_dependencies prints errors and exits if binaries are missing."""
    with patch("ealt.utils.which", return_value=None):
        with pytest.raises(SystemExit) as excinfo:
            utils.check_dependencies()

        assert excinfo.value.code == 1

        # Check output
        captured = capsys.readouterr()
        assert "ERROR: Required dependencies not found" in captured.out
        assert "yt-dlp" in captured.out


def test_set_config_updates_downloads_dir(tmp_path):
    """Test that setting a config updates const.DOWNLOADS_DIR."""
    original_downloads_dir = const.DOWNLOADS_DIR

    custom_dir = tmp_path / "custom_downloads"
    config_data = {"downloads_dir": str(custom_dir)}
    config_file = tmp_path / "config.json"

    with open(config_file, "w") as f:
        json.dump(config_data, f)

    try:
        utils.set_config_file(config_file)
        assert const.DOWNLOADS_DIR == custom_dir
    finally:
        const.DOWNLOADS_DIR = original_downloads_dir


def test_set_config_updates_library_file(tmp_path):
    """Test that setting a config updates const.LIBRARY_FILE."""
    original_library_file = const.LIBRARY_FILE

    custom_lib = tmp_path / "custom_library.json"
    config_data = {"library": str(custom_lib)}
    config_file = tmp_path / "config.json"

    with open(config_file, "w") as f:
        json.dump(config_data, f)

    try:
        utils.set_config_file(config_file)
        assert const.LIBRARY_FILE == custom_lib
    finally:
        const.LIBRARY_FILE = original_library_file
