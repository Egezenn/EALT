import json
import logging
import shutil
import sys
import threading
from logging import Handler
from pathlib import Path
from typing import Any, Dict

from . import const

_active_config_file: Path = const.CONFIG_FILE


def set_config_file(config_file: Path) -> None:
    """Sets the active config file used for resolving paths."""
    global _active_config_file
    _active_config_file = Path(config_file)
    config = get_config()
    downloads_dir = config.get("downloads_dir")
    if downloads_dir:
        path = Path(downloads_dir).expanduser()
        if not path.is_absolute():
            path = _active_config_file.parent / path
        const.DOWNLOADS_DIR = path
    library = config.get("library")
    if library:
        path = Path(library).expanduser()
        if not path.is_absolute():
            path = _active_config_file.parent / path
        const.LIBRARY_FILE = path


def get_config() -> dict[str, Any]:
    """Reads the active config file."""
    return read_json(_active_config_file)


worker_config = threading.local()


def init_worker(worker_id: int, padding: int):
    """Initializes worker configuration for logging."""
    worker_config.log_file = const.LOG_DIR / f"log_{str(worker_id).zfill(padding)}.log"


class ThreadFileHandler(Handler):
    """
    A logging handler that writes to a thread-local log file if configured,
    otherwise falls back to the main log file.
    """

    def __init__(self, main_log_path: Path = None):
        super().__init__()
        self.main_log_path = main_log_path or (const.LOG_DIR / "logs.log")

    def emit(self, record):
        try:
            msg = self.format(record)
            log_file = getattr(worker_config, "log_file", None)

            if log_file:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            else:
                with open(self.main_log_path, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
        except Exception:
            self.handleError(record)


def setup_logging(verbosity: str = "INFO"):
    """Sets up logging configuration."""
    if const.LOG_DIR.exists():
        for log_file in const.LOG_DIR.glob("*.log"):
            try:
                log_file.unlink()
            except Exception:
                pass

    level = getattr(logging, verbosity.upper(), logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s - %(levelname)s - %(message)s",
        handlers=[
            ThreadFileHandler(),
            logging.StreamHandler(),
        ],
    )


def check_dependencies():
    """Check if required external dependencies are available."""
    missing = []

    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")

    if not (shutil.which("magick") or shutil.which("convert")):
        missing.append("magick (or convert)")

    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")

    if missing:
        print(f"ERROR: Required dependencies not found: {', '.join(missing)}")
        print("Please install the missing dependencies and ensure they are in your PATH.")
        sys.exit(1)


def read_json(path: Path) -> Dict[str, Any]:
    """Reads a JSON file and returns a dictionary."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, data: Dict[str, Any]):
    """Writes a dictionary to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_safe_filename(text: str) -> str:
    """Sanitizes a string to be used as a filename."""
    return "".join([c for c in text if c.isalpha() or c.isdigit() or c in " .-_"]).strip()


def parse_extras(extras_str: str) -> list[str]:
    """Parses a comma-separated string of extras."""
    if not extras_str:
        return []
    return [x.strip() for x in extras_str.split(",") if x.strip()]
