import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(".")
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()

DATA_DIR = BASE_DIR / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
LOG_DIR = DATA_DIR / "logs"
LIBRARY_FILE = DATA_DIR / "library.json"
ERRORS_FILE = DATA_DIR / "errors.json"
CONFIG_FILE = DATA_DIR / "config.json"

AUDIO_EXTENSIONS = [".opus", ".webm", ".m4a", ".mp3"]
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
CONVERTIBLE_AUDIO_EXTENSIONS = [".webm", ".m4a"]
CONVERTIBLE_IMAGE_EXTENSIONS = [".webp", ".png"]

DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
