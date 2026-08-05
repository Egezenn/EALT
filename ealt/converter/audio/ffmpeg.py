import logging
import subprocess

from ... import const

logger = logging.getLogger(__name__)


def convert(watch_id: str, target_format: str = "opus", keep_source: bool = False) -> bool:
    """
    Converts the downloaded audio file to the target format.
    Supported formats: 'opus', 'mp3'.
    """
    source_file = None
    for ext in const.CONVERTIBLE_AUDIO_EXTENSIONS:
        path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
        if path.exists():
            source_file = path
            break

    if not source_file:
        if (const.DOWNLOADS_DIR / f"{watch_id}.{target_format}").exists():
            return True

        logger.error(
            f"No source file found for {watch_id} (checked convertible formats: {const.CONVERTIBLE_AUDIO_EXTENSIONS})"
        )
        return False

    output_file = const.DOWNLOADS_DIR / f"{watch_id}.{target_format}"

    if output_file.exists():
        if source_file == output_file:
            return True
        return True

    command = ["ffmpeg", "-i", str(source_file)]

    if target_format == "opus":
        if source_file.suffix == ".webm":
            command.extend(["-c:a", "copy"])
        else:
            command.extend(["-c:a", "libopus", "-b:a", "128k"])
    elif target_format == "mp3":
        command.extend(["-acodec", "libmp3lame", "-b:a", "192k"])
    else:
        logger.error(f"Unsupported format: {target_format}")
        return False

    command.extend(["-loglevel", "error", "-y", str(output_file)])

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Converted {watch_id} to {target_format}")
        if not keep_source and source_file != output_file:
            try:
                source_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete source file {source_file}: {e}")
        return True
    else:
        logger.error(f"FFmpeg failed for {watch_id}: {result.stderr}")
        return False
