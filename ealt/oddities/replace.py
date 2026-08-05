import html
import logging
import re
import subprocess
import threading
from urllib.parse import parse_qs, quote, urlparse

import requests
from ytmusicapi import YTMusic

from .. import const, utils
from .shared import UIHandler, page, run_server

logger = logging.getLogger(__name__)

_lock = threading.Lock()

_thumb_cache: dict = {}
_thumb_lock = threading.Lock()

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
}

_action_logger = logging.getLogger(__name__ + ".actions")
_action_logger.setLevel(logging.INFO)
_action_logger.propagate = False
_action_handler = logging.FileHandler(const.LOG_DIR / "replace.log", encoding="utf-8", delay=True)
_action_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s - %(message)s"))
_action_logger.addHandler(_action_handler)


def _log_action(message: str) -> None:
    _action_logger.info(message)


_THUMB_RE = re.compile(r"=w\d+-h\d+")

STYLE = """
  body { font-family: sans-serif; font-size: 22px; max-width: 900px; margin: 40px auto; padding: 0 20px; }
  h1 { font-size: 44px; }
  h2 { font-size: 34px; }
  .card { border: 3px solid #222; padding: 24px; margin-bottom: 24px; }
  .match { display: flex; align-items: center; gap: 16px; border: 3px solid #222; padding: 16px; margin-bottom: 16px; }
  .btn { display: inline-block; font-size: 22px; font-weight: bold; padding: 14px 28px; margin: 4px 8px 4px 0;
         border: 3px solid #222; background: #eee; color: #000; text-decoration: none; cursor: pointer; }
  .btn:hover { background: #ddd; }
  .muted { color: #555; }
  .err { color: #a00; }
"""


def _load_errors() -> dict:
    return utils.read_json(const.ERRORS_FILE)


def _save_errors(errors: dict) -> None:
    utils.write_json(const.ERRORS_FILE, errors)


def _library_meta(watch_id: str) -> dict:
    return utils.read_json(const.LIBRARY_FILE).get(watch_id, {})


def _reason(entry) -> str:
    if isinstance(entry, dict):
        return entry.get("reason", "")
    return str(entry)


def _thumbnail_url(thumbnails: list) -> str:
    if not thumbnails:
        return ""
    url = max(thumbnails, key=lambda t: t.get("width", 0) * t.get("height", 0)).get("url", "")
    return _THUMB_RE.sub("=w480-h480", url)


def _fetch_thumbnail(url: str) -> tuple[str, bytes] | None:
    """Fetches a remote image server-side so browsers don't hit CORS/referer blocks."""
    with _thumb_lock:
        cached = _thumb_cache.get(url)
        if cached:
            return cached
    try:
        response = requests.get(url, headers=_HEADERS, timeout=10)
        response.raise_for_status()
        result = (response.headers.get("content-type", "image/jpeg"), response.content)
        with _thumb_lock:
            _thumb_cache[url] = result
        return result
    except Exception as e:
        logger.debug(f"Thumbnail fetch failed for {url}: {e}")
        return None


def _page(title: str, body: str, status: int = 200) -> tuple[str, int]:
    return page(title, body, status, STYLE)


def _render_index() -> tuple[str, int]:
    errors = _load_errors()
    library = utils.read_json(const.LIBRARY_FILE)
    cards = []
    for watch_id, entry in errors.items():
        if isinstance(entry, dict) and entry.get("ignore"):
            continue
        meta = library.get(watch_id, {})
        artist = meta.get("artist", "Unknown")
        title = meta.get("title", "Unknown")
        cards.append(f"""
            <div class="card">
              <h2>{html.escape(artist)} - {html.escape(title)}</h2>
              <p><strong>Watch ID:</strong> {html.escape(watch_id)}</p>
              <p><strong>Reason:</strong> {html.escape(_reason(entry))}</p>
              <a class="btn" href="/replace/{watch_id}">Look for replacements</a>
              <a class="btn" href="/ignore?watch_id={watch_id}">Ignore</a>
              <a class="btn" href="/delete?watch_id={watch_id}">Delete entry</a>
            </div>
            """)
    if cards:
        body = f"<h1>Fix errors ({len(cards)})</h1>{''.join(cards)}"
    else:
        body = "<h1>Fix errors</h1><p>Nothing to fix!</p>"
    return _page("Fix errors", body)


def _render_replacements(watch_id: str) -> tuple[str, int]:
    meta = _library_meta(watch_id)
    errors = _load_errors()
    artist = meta.get("artist", "")
    title = meta.get("title", "")
    query = f"{artist} {title}".strip() or watch_id
    matches = []
    try:
        results = YTMusic().search(query, filter="songs", limit=10)
        for r in results:
            artists = ", ".join(a.get("name", "") for a in r.get("artists", []))
            album = (r.get("album") or {}).get("name", "")
            video_id = r.get("videoId", "")
            thumb_url = _thumbnail_url(r.get("thumbnails", []))
            if thumb_url:
                img = f'<img src="/thumb?url={quote(thumb_url, safe="")}" width="120" height="120">'
            else:
                img = ""
            preview_params = (
                f"title={quote(r.get('title', ''), safe='')}"
                f"&artists={quote(artists, safe='')}"
                f"&album={quote(album, safe='')}"
                f"&duration={quote(r.get('duration', ''), safe='')}"
                f"&thumb={quote(thumb_url, safe='')}"
            )
            matches.append(f"""
                <div class="match">
                  {img}
                  <div>
                    <strong>{html.escape(r.get("title", ""))}</strong> — {html.escape(artists)}
                    <br><span class="muted">{html.escape(album)} · {html.escape(r.get("duration", ""))}</span>
                    <br><span class="muted">{html.escape(video_id)}</span>
                  </div>
                  <a class="btn" href="/preview/{html.escape(video_id)}?{preview_params}">Preview</a>
                  <a class="btn" href="/do_replace?watch_id={html.escape(watch_id)}&video={html.escape(video_id)}">Replace</a>
                </div>
                """)
    except Exception as e:
        matches.append(f'<p class="err">Search failed: {html.escape(str(e))}</p>')
    if not matches:
        matches.append("<p>No matches found.</p>")
    body = (
        f"<h1>Replacements for {html.escape(artist)} - {html.escape(title)}</h1>"
        f"<p><strong>Watch ID:</strong> {html.escape(watch_id)}</p>"
        f"<p><strong>Reason:</strong> {html.escape(_reason(errors.get(watch_id)))}</p>"
        f'<a class="btn" href="/">Back</a>'
        f"{''.join(matches)}"
    )
    return _page("Replacements", body)


def _stream_preview(video_id: str, seconds: int = 10) -> bytes:
    """Returns the first `seconds` of audio as a webm blob via yt-dlp + ffmpeg."""
    url_result = subprocess.run(
        [
            "yt-dlp",
            "-g",
            "-f",
            "bestaudio/best",
            "--quiet",
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if url_result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {url_result.stderr.strip()}")
    stream_url = url_result.stdout.strip().splitlines()[-1]

    clip_result = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-ss",
            "0",
            "-t",
            str(seconds),
            "-i",
            stream_url,
            "-c",
            "copy",
            "-f",
            "webm",
            "pipe:1",
        ],
        capture_output=True,
        check=False,
    )
    if clip_result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {clip_result.stderr.decode(errors='replace').strip()}")
    _log_action(f"Previewed {video_id} (first {seconds}s)")
    return clip_result.stdout


def _render_preview(video_id: str, query: dict) -> tuple[str, int]:
    title = query.get("title", [""])[0]
    artists = query.get("artists", [""])[0]
    album = query.get("album", [""])[0]
    duration = query.get("duration", [""])[0]
    thumb = query.get("thumb", [""])[0]
    if thumb:
        img = f'<img src="/thumb?url={quote(thumb, safe="")}" width="120" height="120">'
    else:
        img = ""
    card = f"""
        <div class="match">
          {img}
          <div>
            <strong>{html.escape(title)}</strong> — {html.escape(artists)}
            <br><span class="muted">{html.escape(album)} · {html.escape(duration)}</span>
            <br><span class="muted">{html.escape(video_id)}</span>
          </div>
        </div>
        """
    body = (
        "<h1>Preview</h1>"
        f"{card}"
        f'<audio autoplay controls src="/stream/{html.escape(video_id)}"></audio>'
        f'<br><br><a class="btn" href="javascript:history.back()">Back</a>'
    )
    return _page("Preview", body)


def _ignore(watch_id: str) -> None:
    with _lock:
        errors = _load_errors()
        entry = errors.get(watch_id)
        if entry is not None:
            if isinstance(entry, dict):
                entry["ignore"] = True
            else:
                errors[watch_id] = {"reason": entry, "ignore": True}
            _save_errors(errors)
            _log_action(f"Ignored {watch_id}")


def _delete(watch_id: str) -> None:
    with _lock:
        errors = _load_errors()
        errors.pop(watch_id, None)
        _save_errors(errors)
        _log_action(f"Deleted error entry {watch_id}")


def _do_replace(watch_id: str, video_id: str) -> None:
    if not video_id:
        return
    with _lock:
        library = utils.read_json(const.LIBRARY_FILE)
        if watch_id in library:
            meta = library.pop(watch_id)
            if video_id not in library:
                library[video_id] = meta
            utils.write_json(const.LIBRARY_FILE, library)
        errors = _load_errors()
        errors.pop(watch_id, None)
        _save_errors(errors)
        _log_action(f"Replaced {watch_id} with {video_id}")


class FixHandler(UIHandler):
    STYLE = STYLE

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/":
                self._respond(_render_index())
            elif path.startswith("/replace/"):
                self._respond(_render_replacements(path.rsplit("/", 1)[-1]))
            elif path.startswith("/preview/"):
                self._respond(_render_preview(path.rsplit("/", 1)[-1], query))
            elif path.startswith("/stream/"):
                self._send_audio(path.rsplit("/", 1)[-1])
            elif path == "/thumb":
                self._send_thumbnail(query.get("url", [""])[0])
            elif path == "/ignore":
                _ignore(query.get("watch_id", [""])[0])
                self._redirect("/")
            elif path == "/delete":
                _delete(query.get("watch_id", [""])[0])
                self._redirect("/")
            elif path == "/do_replace":
                _do_replace(query.get("watch_id", [""])[0], query.get("video", [""])[0])
                self._redirect("/")
            else:
                self._respond(_page("Not found", "<h1>404</h1>", status=404))
        except Exception as e:
            logger.exception("Fix request failed")
            self._respond(_page("Error", f"<h1>Error</h1><p>{html.escape(str(e))}</p>", status=500))

    def _send_audio(self, video_id: str):
        try:
            data = _stream_preview(video_id)
        except Exception as e:
            logger.error(f"Preview failed for {video_id}: {e}")
            self._send_error(f"Preview failed: {e}")
            return
        self._send_bytes(data, "audio/webm")

    def _send_thumbnail(self, url: str):
        result = _fetch_thumbnail(url)
        if result is None:
            self._send_missing()
            return
        content_type, data = result
        self._send_bytes(data, content_type)


def run() -> None:
    """Starts the fix web UI and blocks until interrupted."""
    run_server(FixHandler, "fix")
