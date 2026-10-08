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


def test_run_help():
    """Test that the run command help includes --fix-unavailable."""
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "--fix-unavailable" in result.output


def test_library_replace(tmp_path):
    """Test Library.replace replaces watch_id while keeping metadata."""
    from ealt import core

    original_library_file = const.LIBRARY_FILE
    const.LIBRARY_FILE = tmp_path / "library.json"
    try:
        utils.write_json(const.LIBRARY_FILE, {"old_id": {"artist": "Artist", "title": "Song"}})
        lib = core.Library()
        lib.replace("old_id", "new_id", {"artist": "Artist", "title": "Song"})
        assert lib.get("old_id") is None
        assert lib.get("new_id") == {"artist": "Artist", "title": "Song"}
    finally:
        const.LIBRARY_FILE = original_library_file


def test_remove_download_error(tmp_path):
    """Test downloader.remove_download_error removes entries from errors.json."""
    from ealt.downloader import record_download_error, remove_download_error

    original_errors_file = const.ERRORS_FILE
    const.ERRORS_FILE = tmp_path / "errors.json"
    try:
        record_download_error("failed_id", "Unavailable")
        assert "failed_id" in utils.read_json(const.ERRORS_FILE)
        remove_download_error("failed_id")
        assert "failed_id" not in utils.read_json(const.ERRORS_FILE)
    finally:
        const.ERRORS_FILE = original_errors_file


def test_process_item_fix_unavailable(tmp_path, monkeypatch):
    """Test process_item fixes unavailable track when --fix-unavailable is enabled."""
    from unittest.mock import MagicMock

    from ealt import core

    mock_dl = MagicMock()
    mock_dl.download.side_effect = lambda wid, *args, **kwargs: wid == "replaced_id"
    mock_dl.fetch_metadata.return_value = None

    mock_cv = MagicMock()
    mock_cv.convert_audio.return_value = True
    mock_cv.convert_image.return_value = True

    mock_tg = MagicMock()
    mock_tg.tag.return_value = True

    monkeypatch.setattr(
        "ealt.metadata.search_exact_match",
        lambda artist, title, exclude_id=None: "replaced_id" if exclude_id == "orig_id" else None,
    )

    item_tuple = (1, ("orig_id", {"artist": "Test Artist", "title": "Test Title"}, "Test Title"))
    options = {
        "keep_source": False,
        "format": "opus",
        "delete_embeds": False,
        "embed_extras": [],
        "force_metadata": False,
        "tag_albums": False,
        "total": 1,
        "album_tags": {},
        "square_crop": True,
        "fix_unavailable": True,
    }

    target_id, _updated_meta, success, replaced_from = core.process_item(
        item_tuple, options, mock_dl, mock_cv, mock_tg
    )
    assert success is True
    assert target_id == "replaced_id"
    assert replaced_from == "orig_id"


def test_remote_components_cli_options():
    """Test that run and download commands support --remote-components and --no-remote-components."""
    res_run = runner.invoke(cli, ["run", "--help"])
    assert res_run.exit_code == 0
    assert "remote-components" in res_run.output

    res_dl = runner.invoke(cli, ["download", "--help"])
    assert res_dl.exit_code == 0
    assert "remote-components" in res_dl.output

    # Verify --no-remote-components is a valid flag
    res_run_no = runner.invoke(cli, ["run", "--no-remote-components", "--help"])
    assert res_run_no.exit_code == 0



def test_downloader_remote_components_flag():
    """Test that Downloader passes --remote-components ejs:github to yt-dlp by default."""
    from unittest.mock import MagicMock

    from ealt.downloader import Downloader

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Enabled (default)
        dl_enabled = Downloader(remote_components=True)
        dl_enabled.download("test_id_enabled")
        args_enabled = mock_run.call_args[0][0]
        assert "--remote-components" in args_enabled
        assert "ejs:github" in args_enabled

        # Disabled
        mock_run.reset_mock()
        dl_disabled = Downloader(remote_components=False)
        dl_disabled.download("test_id_disabled")
        args_disabled = mock_run.call_args[0][0]
        assert "--remote-components" not in args_disabled


def test_cookies_cli_options():
    """Test that run and download commands contain --cookies."""
    res_run = runner.invoke(cli, ["run", "--help"])
    assert res_run.exit_code == 0
    assert "--cookies" in res_run.output

    res_dl = runner.invoke(cli, ["download", "--help"])
    assert res_dl.exit_code == 0
    assert "--cookies" in res_dl.output


def test_resolve_cookies(tmp_path):
    """Test resolve_cookies behavior with explicit path and const.COOKIES_FILE fallback."""
    orig_cookies = const.COOKIES_FILE
    dummy_cookies = tmp_path / "cookies.txt"
    const.COOKIES_FILE = dummy_cookies
    try:
        # Falsy / disabled by default
        assert utils.resolve_cookies(False) is None
        assert utils.resolve_cookies() is None

        # When cookies=True and data/cookies.txt (const.COOKIES_FILE) exists
        dummy_cookies.write_text("# Netscape HTTP Cookie File")
        assert utils.resolve_cookies(True) == dummy_cookies

        # When cookies=False, returns None even if file exists
        assert utils.resolve_cookies(False) is None

        # Explicit path takes precedence
        custom_cookies = tmp_path / "custom_cookies.txt"
        custom_cookies.write_text("# Custom Cookies")
        assert utils.resolve_cookies(custom_cookies) == custom_cookies

        # Explicit non-existent path
        assert utils.resolve_cookies(tmp_path / "nonexistent.txt") is None
    finally:
        const.COOKIES_FILE = orig_cookies



def test_downloader_cookies_flag(tmp_path):
    """Test that Downloader passes --cookies to yt-dlp when cookies file is present."""
    from unittest.mock import MagicMock

    from ealt.downloader import Downloader

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        dl = Downloader(cookies=cookies_file)
        dl.download("test_id_cookies")
        args = mock_run.call_args[0][0]
        assert "--cookies" in args
        assert str(cookies_file) in args

        # Test boolean flag cookies=True with const.COOKIES_FILE
        orig_cookies = const.COOKIES_FILE
        const.COOKIES_FILE = cookies_file
        try:
            mock_run.reset_mock()
            dl_bool = Downloader(cookies=True)
            dl_bool.download("test_id_cookies_bool")
            args_bool = mock_run.call_args[0][0]
            assert "--cookies" in args_bool
            assert str(cookies_file) in args_bool

            # Test cookies=False
            mock_run.reset_mock()
            dl_no_cookies = Downloader(cookies=False)
            dl_no_cookies.download("test_id_no_cookies")
            args_no = mock_run.call_args[0][0]
            assert "--cookies" not in args_no
        finally:
            const.COOKIES_FILE = orig_cookies


def test_cleanup_resolved_errors(tmp_path):
    """Test that cleanup_resolved_errors deletes errors.json entries if their audio exists."""
    from ealt.downloader import cleanup_resolved_errors

    orig_downloads = const.DOWNLOADS_DIR
    orig_errors = const.ERRORS_FILE

    const.DOWNLOADS_DIR = tmp_path / "downloads"
    const.DOWNLOADS_DIR.mkdir()
    const.ERRORS_FILE = tmp_path / "errors.json"

    try:
        # Create audio file for resolved_id
        (const.DOWNLOADS_DIR / "resolved_id.opus").write_text("audio")

        # Set up errors.json with resolved_id and unresolved_id
        utils.write_json(
            const.ERRORS_FILE,
            {
                "resolved_id": {"reason": "Unavailable", "time": 12345},
                "unresolved_id": {"reason": "Unavailable", "time": 12345},
            },
        )

        removed_count = cleanup_resolved_errors()
        assert removed_count == 1

        remaining_errors = utils.read_json(const.ERRORS_FILE)
        assert "resolved_id" not in remaining_errors
        assert "unresolved_id" in remaining_errors
    finally:
        const.DOWNLOADS_DIR = orig_downloads
        const.ERRORS_FILE = orig_errors






