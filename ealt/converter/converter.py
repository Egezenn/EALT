import logging

from . import audio, image

logger = logging.getLogger(__name__)


class Converter:
    def convert_audio(self, watch_id: str, target_format: str = "opus", keep_source: bool = False) -> bool:
        """
        Converts the downloaded audio file to the target format.
        Supported formats: 'opus', 'mp3'.
        """
        return audio.ffmpeg.convert(watch_id, target_format, keep_source)

    def convert_image(
        self, watch_id: str, target_format: str = ".jpg", keep_source: bool = False, square_crop: bool = True
    ) -> bool:
        """
        Converts the cover art to the target format using ImageMagick.
        """
        return image.magick.convert(watch_id, target_format, keep_source, square_crop)
