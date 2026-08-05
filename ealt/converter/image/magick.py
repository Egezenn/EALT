import logging
import subprocess

from ... import const

logger = logging.getLogger(__name__)


def convert(watch_id: str, target_format: str = ".jpg", keep_source: bool = False, square_crop: bool = True) -> bool:
    """
    Converts the cover art to the target format using ImageMagick.
    """
    source_file = None
    for ext in const.CONVERTIBLE_IMAGE_EXTENSIONS:
        path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
        if path.exists():
            source_file = path
            break

    output_file = const.DOWNLOADS_DIR / f"{watch_id}{target_format}"

    if output_file.exists():
        if not square_crop:
            return True
        input_file = output_file
    elif source_file is not None:
        input_file = source_file
    else:
        logger.warning(f"No cover art found for {watch_id}")
        return False

    command = ["magick", str(input_file)]
    if square_crop:
        command += [
            "-gravity",
            "Center",
            "-crop",
            "%[fx:w<h?w:h]x%[fx:w<h?w:h]+0+0",
            "+repage",
        ]
    command.append(str(output_file))

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        if input_file != output_file:
            logger.info(f"Converted cover for {watch_id} to {target_format}")
            if not keep_source and source_file:
                try:
                    source_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to delete source cover {source_file}: {e}")
        return True
    else:
        logger.error(f"ImageMagick failed for {watch_id}: {result.stderr}")
        return False
