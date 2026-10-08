import logging
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from .. import const, core

logger = logging.getLogger(__name__)

_BACKUP_PATTERN = re.compile(r"^Metrolist_(\d+)\.backup$", re.IGNORECASE)


def _extract_timestamp(filename: str) -> int:
    match = _BACKUP_PATTERN.match(filename)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 0
    return 0


def find_latest_backup(search_dirs: list[Path] | None = None) -> Path | None:
    """
    Finds the Metrolist backup file with the highest timestamp stamp.
    """

    if search_dirs is None:
        search_dirs = [const.DATA_DIR, Path("data"), Path(".")]

    candidates = []
    seen = set()

    for directory in search_dirs:
        if not directory.exists():
            continue
        for file in directory.glob("Metrolist_*.backup"):
            resolved = file.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(file)

    if not candidates:
        return None

    return max(candidates, key=lambda f: _extract_timestamp(f.name))


def extract_liked_songs(backup_path: Path) -> dict[str, dict]:
    """
    Extracts liked songs from a Metrolist .backup zip archive's song.db.
    Returns a dict mapping watch_id -> metadata dictionary.
    """
    if not backup_path.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return {}

    try:
        with zipfile.ZipFile(backup_path, "r") as z:
            namelist = z.namelist()
            if "song.db" not in namelist:
                logger.error(f"'song.db' not found in backup archive: {backup_path}")
                return {}

            with tempfile.TemporaryDirectory() as tmp_dir:
                db_path = z.extract("song.db", path=tmp_dir)
                for extra in ["song.db-wal", "song.db-shm"]:
                    if extra in namelist:
                        z.extract(extra, path=tmp_dir)

                conn = sqlite3.connect(db_path)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT s.id, s.title, s.albumName, a.name, sam.position
                        FROM song s
                        LEFT JOIN song_artist_map sam ON s.id = sam.songId
                        LEFT JOIN artist a ON sam.artistId = a.id
                        WHERE s.liked = 1
                        ORDER BY s.id, sam.position ASC
                        """
                    )
                    rows = cur.fetchall()
                finally:
                    conn.close()

    except Exception as e:
        logger.error(f"Failed to read backup file {backup_path}: {e}")
        return {}

    liked_songs: dict[str, dict] = {}
    for song_id, title, album_name, artist_name, _pos in rows:
        if not song_id:
            continue
        if song_id not in liked_songs:
            liked_songs[song_id] = {
                "title": title or "Unknown",
                "album": album_name,
                "artists": [],
            }
        if artist_name and artist_name not in liked_songs[song_id]["artists"]:
            liked_songs[song_id]["artists"].append(artist_name)

    result = {}
    for song_id, data in liked_songs.items():
        meta = {
            "artist": ", ".join(data["artists"]) if data["artists"] else "Unknown",
            "title": data["title"],
        }
        if data["album"]:
            meta["album"] = data["album"]
        result[song_id] = meta

    return result


def import_liked_songs(backup_path: Path | None = None) -> tuple[int, int]:
    """
    Imports liked songs from the latest (or specified) Metrolist backup file
    into library.json if they don't already exist.
    Returns (imported_count, skipped_count).
    """
    if backup_path is None:
        backup_path = find_latest_backup()

    if backup_path is None:
        logger.error("No Metrolist backup files (Metrolist_*.backup) found in data directory.")
        return 0, 0

    logger.info(f"Using Metrolist backup: {backup_path}")
    liked_songs = extract_liked_songs(backup_path)

    if not liked_songs:
        logger.info("No liked songs found to import.")
        return 0, 0

    library_obj = core.Library()
    imported_count = 0
    skipped_count = 0

    for song_id, meta in liked_songs.items():
        if library_obj.get(song_id) is not None:
            skipped_count += 1
            continue

        library_obj.update(song_id, meta, save_to_disk=False)
        imported_count += 1

    if imported_count > 0:
        library_obj.save()

    logger.info(
        f"Imported {imported_count} new liked songs (skipped {skipped_count} existing) from {backup_path.name}"
    )
    return imported_count, skipped_count


def run(backup_file: Path | None = None) -> None:
    """Entry point for oddities import-metrolist command."""
    imported, skipped = import_liked_songs(backup_path=backup_file)
    print(f"Imported {imported} new liked songs (skipped {skipped} existing).")


