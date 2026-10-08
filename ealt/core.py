import logging
import queue

from . import const, downloader, metadata, utils

logger = logging.getLogger(__name__)


class Library:
    def __init__(self):
        self.data = utils.read_json(const.LIBRARY_FILE)

    def save(self):
        """Saves the current state of the library to disk."""
        sorted_data = dict(
            sorted(
                self.data.items(),
                key=lambda x: (
                    x[1].get("artist", "").lower(),
                    x[1].get("title", "").lower(),
                ),
            )
        )
        utils.write_json(const.LIBRARY_FILE, sorted_data)

    def get(self, watch_id: str) -> dict | None:
        """Retrieves metadata for a given watch_id."""
        return self.data.get(watch_id)

    def update(self, watch_id: str, metadata: dict, save_to_disk: bool = True):
        """
        Updates or adds an entry to the library.
        """
        if watch_id in self.data:
            self.data[watch_id].update(metadata)
            logger.debug(f"Updated metadata for {watch_id}")
        else:
            self.data[watch_id] = metadata
            logger.info(f"Added {watch_id} with metadata")

        if save_to_disk:
            self.save()

    def replace(self, old_watch_id: str, new_watch_id: str, metadata: dict, save_to_disk: bool = True):
        """
        Replaces an existing entry with a new watch_id in the library.
        """
        if old_watch_id in self.data:
            del self.data[old_watch_id]
        self.data[new_watch_id] = metadata
        logger.info(f"Replaced {old_watch_id} with {new_watch_id} in library")

        if save_to_disk:
            self.save()

    def remove(self, watch_id: str):
        """Removes an entry from the library."""
        if watch_id in self.data:
            del self.data[watch_id]
            self.save()
            logger.info(f"Removed {watch_id}")


    def __iter__(self):
        return iter(self.data)

    def items(self):
        return self.data.items()


def process_item(item_tuple, options, dl, cv, tg):
    """
    Helper function to process a single item in a thread.
    Returns (watch_id, updated_meta_or_None, success_status, replaced_from_or_None)
    """
    _, (watch_id, meta, title) = item_tuple

    keep_source = options["keep_source"]
    format = options["format"]
    delete_embeds = options["delete_embeds"]
    embed_extras = options["embed_extras"]
    force_metadata = options["force_metadata"]
    tag_albums = options["tag_albums"]
    fix_unavailable = options.get("fix_unavailable", False)

    if options.get("skip_existing") and (const.DOWNLOADS_DIR / f"{watch_id}.{format}").exists():
        logger.debug(f"  Skipping {watch_id} (audio already exists)")
        return watch_id, None, True, None

    if watch_id in options.get("skip_error_ids", ()):
        logger.debug(f"  Skipping {watch_id} (previous download error)")
        return watch_id, None, True, None

    locked = meta.get("lock", False)
    artist = meta.get("artist")

    updated_meta = None

    should_fetch = False
    if not locked and (force_metadata or not artist or not title or tag_albums and "album" not in meta):
        should_fetch = True


    if should_fetch:
        logger.info(f"  Fetching metadata for {watch_id}...")
        fetched = dl.fetch_metadata(watch_id)
        if fetched:
            if updated_meta is None:
                updated_meta = meta.copy()

            if fetched.get("artist"):
                updated_meta["artist"] = fetched["artist"]
                artist = fetched["artist"]
            if fetched.get("title"):
                updated_meta["title"] = fetched["title"]
                title = fetched["title"]

            if fetched.get("album"):
                updated_meta["album"] = fetched["album"]
            elif "album" not in updated_meta:
                updated_meta["album"] = ""

            logger.info(f"  Updated metadata: {artist} - {title}")

    current_meta = updated_meta if updated_meta else meta

    artist = current_meta.get("artist")
    title = current_meta.get("title")
    display_artist = artist if artist else "Unknown"
    display_title = title if title else "Unknown"

    i = item_tuple[0]
    total = options["total"]
    album_tag = options.get("album_tags", {}).get(watch_id, "")

    logger.info(f"[{i}/{total}] Processing {watch_id}: {display_artist} - {display_title} (Album: {album_tag})")

    target_id = watch_id
    success = dl.download(watch_id, artist, title, existing_meta=current_meta)
    if not success:
        if fix_unavailable and artist and title:
            logger.info(
                f"  Download failed for {watch_id}. Searching YouTube Music for 100% match on '{artist} - {title}'..."
            )
            replacement_id = metadata.search_exact_match(artist, title, exclude_id=watch_id)
            if replacement_id:
                logger.info(f"  Found replacement for {watch_id}: {replacement_id}")
                success = dl.download(replacement_id, artist, title, existing_meta=current_meta)
                if success:
                    target_id = replacement_id
                    downloader.remove_download_error(watch_id)
        if not success:
            logger.info(f"  Skipping {watch_id} (Download failed)")
            return watch_id, updated_meta, False, None

    if not cv.convert_audio(target_id, format, keep_source=keep_source):
        logger.info(f"  Skipping {target_id} (Conversion failed)")
        return target_id, updated_meta, False, None

    if not cv.convert_image(target_id, keep_source=keep_source, square_crop=options.get("square_crop", True)):
        logger.info(f"  Warning: Image conversion failed for {target_id}")

    desc = current_meta.get("desc")

    if not tg.tag(
        target_id, artist, title, album=album_tag, desc=desc, delete_embeds=delete_embeds, embed_extras=embed_extras
    ):
        logger.info(f"  Warning: Tagging failed for {target_id}")

    if updated_meta is None:
        updated_meta = current_meta.copy()

    return target_id, updated_meta, True, (watch_id if target_id != watch_id else None)



def pool_initializer(q, padding):
    """Initializer for worker threads."""
    try:
        worker_id = q.get_nowait()
        utils.init_worker(worker_id, padding)
    except queue.Empty:
        pass
