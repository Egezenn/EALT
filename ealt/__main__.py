import concurrent.futures
import logging
import queue
from pathlib import Path
from typing import Annotated

import typer

from . import const, converter, core, downloader, oddities, tagger, utils

utils.setup_logging()
logger = logging.getLogger(__name__)

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("ealt")
except ImportError, PackageNotFoundError:
    __version__ = "unknown"


cli = typer.Typer(
    context_settings=dict(help_option_names=["-h", "--help"]),
)


@cli.callback(no_args_is_help=True, invoke_without_command=True)
def main(
    config: Annotated[Path, typer.Option("-c", "--config", help="Path to config JSON")] = const.CONFIG_FILE,
    version: Annotated[bool | None, typer.Option("-v", "--version", help="Show the version and exit.")] = None,
) -> None:
    utils.set_config_file(config)
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    utils.check_dependencies()


@cli.command()
def run(
    index: Annotated[int, typer.Option("-i", "--index", help="Start processing from this index.")] = 1,
    workers: Annotated[int, typer.Option("-t", "--threads", help="Number of worker threads to use.")] = 3,
    delete_source: Annotated[
        bool, typer.Option("--delete-source/--keep-source", help="Delete source files after conversion.")
    ] = True,
    format: Annotated[str, typer.Option("-f", "--format", help="Target format")] = "opus",
    download_extras: Annotated[
        str, typer.Option("--download-extras", help="Comma-separated extras to download.")
    ] = "cover,lyric",
    embed_extras: Annotated[str, typer.Option("--embed-extras", help="Comma-separated extras to embed.")] = "cover",
    delete_embeds: Annotated[
        bool,
        typer.Option(
            "--delete-embeds/--keep-embeds", help="Delete source lyrics/cover files after embedding into audio."
        ),
    ] = False,
    tag_albums: Annotated[
        bool,
        typer.Option(
            "--tag-albums",
            help="Use album metadata from library for tagging (falls back to sequential index if missing).",
        ),
    ] = False,
    force_metadata: Annotated[
        bool, typer.Option("--force-metadata", help="Force metadata update from YouTube Music (respects lock).")
    ] = False,
    skip_existing: Annotated[bool, typer.Option("--skip-existing", help="Skip items that already have audio.")] = False,
    skip_errors: Annotated[
        bool, typer.Option("--skip-errors", help="Skip items that previously failed to download.")
    ] = False,
    square_crop: Annotated[
        bool, typer.Option("--square-crop/--no-square-crop", help="Enforce 1:1 square crop on cover art.")
    ] = True,
) -> None:
    """Process the entire library."""
    parsed_download_extras = utils.parse_extras(download_extras)
    parsed_embed_extras = utils.parse_extras(embed_extras)
    if not const.LIBRARY_FILE.exists():
        logger.info(f"Library file not found at {const.LIBRARY_FILE}")
        return

    library_obj = core.Library()

    items = []
    for watch_id, meta in library_obj.items():
        title = meta.get("title", "")
        items.append((watch_id, meta, title))

    total = len(items)
    logger.info(f"Processing {total} items from {const.LIBRARY_FILE}...")

    padding = len(str(total))

    album_tags = {}
    no_album_count = 0
    no_album_padding = 0
    if tag_albums:
        no_album_count = sum(1 for _, meta, _ in items if not meta.get("album"))
        no_album_padding = len(str(no_album_count))

    no_album_counter = 0

    processed_items = []

    for i, (watch_id, meta, *_) in enumerate(items, 1):
        album_tag = str(i).zfill(padding)
        if tag_albums:
            if meta.get("album"):
                album_tag = meta["album"]
            else:
                no_album_counter += 1
                album_tag = str(no_album_counter).zfill(no_album_padding)

        album_tags[watch_id] = album_tag

        if i >= index:
            processed_items.append((i, (watch_id, meta, meta.get("title"))))

    options = {
        "keep_source": not delete_source,
        "format": format,
        "download_extras": parsed_download_extras,
        "delete_embeds": delete_embeds,
        "embed_extras": parsed_embed_extras,
        "force_metadata": force_metadata,
        "skip_existing": skip_existing,
        "skip_error_ids": set(utils.read_json(const.ERRORS_FILE)) if skip_errors else set(),
        "tag_albums": tag_albums,
        "total": total,
        "album_tags": album_tags,
        "square_crop": square_crop,
    }

    worker_queue = queue.Queue()
    for i in range(1, workers + 1):
        worker_queue.put(i)

    const.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    dl = downloader.Downloader(download_extras=parsed_download_extras)
    cv = converter.Converter()
    tg = tagger.Tagger()

    worker_padding = len(str(workers))

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers, initializer=core.pool_initializer, initargs=(worker_queue, worker_padding)
    ) as executor:
        futures = {executor.submit(core.process_item, item, options, dl, cv, tg): item for item in processed_items}

        count = 0
        try:
            for future in concurrent.futures.as_completed(futures):
                try:
                    watch_id, updated_meta, success = future.result()

                    if updated_meta:
                        library_obj.update(watch_id, updated_meta, save_to_disk=False)

                    count += 1
                    if count % 10 == 0:
                        library_obj.save()

                except Exception as e:
                    logger.error(f"Worker failed: {e}")

        except KeyboardInterrupt:
            logger.info("Interrupted, shutting down workers...")
            executor.shutdown(wait=False, cancel_futures=True)
            raise

    # Final save
    library_obj.save()
    logger.info("Done.")


@cli.command()
def download(
    watch_id: Annotated[str, typer.Argument(help="Watch ID")],
    download_extras: Annotated[
        str, typer.Option("--download-extras", help="Comma-separated extras to download.")
    ] = "cover,lyric",
) -> None:
    """Download a single video by Watch ID."""
    extras = utils.parse_extras(download_extras)
    const.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    dl = downloader.Downloader(download_extras=extras)
    if dl.download(watch_id):
        logger.info(f"Downloaded {watch_id}")
    else:
        logger.info(f"Failed to download {watch_id}")


@cli.command()
def convert(
    watch_id: Annotated[str, typer.Argument(help="Watch ID")],
    delete_source: Annotated[
        bool, typer.Option("--delete-source/--keep-source", help="Delete source files after conversion.")
    ] = True,
    format: Annotated[str, typer.Option("--format", "-f", help="Target format (opus*/mp3)")] = "opus",
    square_crop: Annotated[
        bool, typer.Option("--square-crop/--no-square-crop", help="Enforce 1:1 square crop on cover art.")
    ] = True,
) -> None:
    """Convert a downloaded video."""
    working_dir = const.DOWNLOADS_DIR
    if not working_dir.exists():
        logger.error(f"Directory {working_dir} does not exist.")
        return

    cv = converter.Converter()

    success_audio = cv.convert_audio(watch_id, format, keep_source=not delete_source)
    success_image = cv.convert_image(watch_id, keep_source=not delete_source, square_crop=square_crop)

    if success_audio:
        logger.info(f"Converted audio for {watch_id} to {format}")
    else:
        logger.info(f"Failed to convert audio for {watch_id}")

    if success_image:
        logger.info(f"Converted image for {watch_id}")
    else:
        logger.info(f"Failed to convert image for {watch_id} (or no image found)")


@cli.command()
def tag(
    watch_id: Annotated[str, typer.Argument(help="Watch ID")],
    artist: Annotated[str | None, typer.Option("--artist", help="Artist name")] = None,
    title: Annotated[str | None, typer.Option("--title", help="Track title")] = None,
    embed_extras: Annotated[str, typer.Option("--embed-extras", help="Comma-separated extras to embed.")] = "cover",
    delete_embeds: Annotated[
        bool,
        typer.Option(
            "--delete-embeds/--keep-embeds", help="Delete source lyrics/cover files after embedding into audio."
        ),
    ] = False,
    lock: Annotated[bool, typer.Option("--lock", help="Lock metadata in library.")] = False,
    album: Annotated[str | None, typer.Option("--album", help="Album name")] = None,
    desc: Annotated[str | None, typer.Option("--desc", help="Description")] = None,
    tag_album: Annotated[bool, typer.Option("--tag-album", help="Tag album from metadata.")] = False,
) -> None:
    """Tag a file."""
    extras = utils.parse_extras(embed_extras)
    working_dir = const.DOWNLOADS_DIR
    if not working_dir.exists():
        logger.error(f"Directory {working_dir} does not exist.")
        return

    library_obj = core.Library()
    current_meta = library_obj.get(watch_id) or {}

    updates_made = False

    if artist:
        current_meta["artist"] = artist
        updates_made = True
    if title:
        current_meta["title"] = title
        updates_made = True
    if album:
        current_meta["album"] = album
        updates_made = True
    if desc:
        current_meta["desc"] = desc
        updates_made = True
    if lock:
        current_meta["lock"] = True
        updates_made = True

    final_artist = current_meta.get("artist")
    final_title = current_meta.get("title")

    if not final_artist or not final_title:
        logger.info(f"Metadata missing for {watch_id}. Checking YouTube...")
        dl = downloader.Downloader()
        fetched = dl.fetch_metadata(watch_id)

        if fetched:
            if not final_artist and fetched.get("artist"):
                final_artist = fetched["artist"]
                current_meta["artist"] = final_artist
                updates_made = True

            if not final_title and fetched.get("title"):
                final_title = fetched["title"]
                current_meta["title"] = final_title
                updates_made = True

            if fetched.get("album"):
                if tag_album and "album" not in current_meta:
                    current_meta["album"] = fetched["album"]
                    updates_made = True
        else:
            logger.warning(f"Could not fetch metadata for {watch_id}")

    if updates_made:
        library_obj.update(watch_id, current_meta)

    display_artist = final_artist if final_artist else "Unknown"
    display_title = final_title if final_title else "Unknown"

    tag_album_value = None
    if album:
        tag_album_value = album
    elif tag_album:
        tag_album_value = current_meta.get("album")

    tg = tagger.Tagger()
    if tg.tag(
        watch_id,
        display_artist,
        display_title,
        album=tag_album_value,
        desc=current_meta.get("desc"),
        embed_extras=extras,
        delete_embeds=delete_embeds,
    ):
        logger.info(f"Tagged {watch_id}")
    else:
        logger.info(f"Failed to tag {watch_id}")


oddities.register(cli)


if __name__ == "__main__":
    cli()
