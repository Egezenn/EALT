# EALT <small>(Ege's Audio Library Thing)</small>

<a href="#"><img alt="horrible orange triangle" style="padding:16px;" align="left" src="assets/icon.svg"></a>

Duct taped python + yt-dlp + ffmpeg + magick + json = audio library pipeline

## Configuration

`data/config.json` `-c`/`--config`

```json
{
  "library": "data/library.json",
  "downloads_dir": "data/downloads"
}
```

`library.json`

```json
{
  "dQw4w9WgXcQ": {
    "artist": "Rick Astley",
    "title": "Never Gonna Give You Up",
    "album": "Whenever You Need Somebody",
    "desc": "i got rick rolled",
    "lock": true
  }
}
```

## Dependencies

### Binaries

| Package                                    | Usage                                      | License   |
| ------------------------------------------ | ------------------------------------------ | --------- |
| [Python ~=3.12](https://www.python.org)    | Core language                              | PSFL      |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloading files off of YouTube           | Unlicense |
| [FFmpeg](https://ffmpeg.org)               | Required for the conversion of audio files | LGPLv2.1  |
| [ImageMagick](https://imagemagick.org)     | Required for the conversion of image files | Custom    |

### Python packages

| Package                                                   | Usage               | License    |
| --------------------------------------------------------- | ------------------- | ---------- |
| [mutagen](https://github.com/quodlibet/mutagen)           | Tagging audio files | GPL-2.0    |
| [pyinstaller](https://github.com/pyinstaller/pyinstaller) | Compilation         | GPLv2      |
| [requests](https://github.com/psf/requests)               | Making requests     | Apache-2.0 |
| [typer](https://github.com/fastapi/typer)                 | CLI interface       | MIT        |
| [ytmusicapi](https://github.com/sigma67/ytmusicapi)       | Metadata fetching   | MIT        |

## Disclaimer

This project is not in any way, shape or form affiliated with YouTube, Google or any of their subsidiaries and affiliates.
