import html
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .. import const, utils
from .shared import UIHandler, page, render_template, run_server

logger = logging.getLogger(__name__)

_COVER_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_AUDIO_MIME = {".opus": "audio/ogg", ".mp3": "audio/mpeg", ".webm": "audio/webm", ".m4a": "audio/mp4"}


def _scan() -> list[dict]:
    """Scans the downloads dir for audio files and joins library metadata."""
    library = utils.read_json(const.LIBRARY_FILE)
    pref = {ext: i for i, ext in enumerate(const.AUDIO_EXTENSIONS)}
    items = {}
    for path in const.DOWNLOADS_DIR.iterdir():
        if not path.is_file() or path.suffix not in const.AUDIO_EXTENSIONS:
            continue
        watch_id = path.stem
        item = items.setdefault(watch_id, {"watch_id": watch_id, "audio": None})
        if item["audio"] is None or pref.get(path.suffix, 99) < pref.get(Path(item["audio"]).suffix, 99):
            item["audio"] = path.name

    result = []
    for watch_id, item in items.items():
        meta = library.get(watch_id, {})
        item["artist"] = meta.get("artist", "Unknown")
        item["title"] = meta.get("title", watch_id)
        item["album"] = meta.get("album")
        item["desc"] = meta.get("desc")
        item["cover"] = _cover_path(watch_id) is not None
        result.append(item)
    return sorted(result, key=lambda i: (i["artist"].lower(), i["title"].lower()))


def _cover_path(watch_id: str) -> Path | None:
    for ext in const.IMAGE_EXTENSIONS:
        path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
        if path.exists():
            return path
    return None


def _audio_path(watch_id: str) -> Path | None:
    for ext in const.AUDIO_EXTENSIONS:
        path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
        if path.exists():
            return path
    return None


def _lyrics_path(watch_id: str) -> Path | None:
    for ext in [".lrc", ".txt"]:
        path = const.DOWNLOADS_DIR / f"{watch_id}{ext}"
        if path.exists():
            return path
    return None


def _render_artists(items: list[dict], q: str = "", sort: str = "az") -> tuple[str, int]:
    if q:
        ql = q.lower()
        items = [i for i in items if ql in f"{i['artist']} - {i['title']}".lower()]

    by_artist = {}
    for item in items:
        by_artist.setdefault(item["artist"], []).append(item)

    def artist_key(artist: str) -> str:
        return artist.lower()

    if sort == "za":
        order = sorted(by_artist, key=artist_key, reverse=True)
    elif sort == "most":
        order = sorted(by_artist, key=lambda a: (-len(by_artist[a]), artist_key(a)))
    elif sort == "least":
        order = sorted(by_artist, key=lambda a: (len(by_artist[a]), artist_key(a)))
    else:
        order = sorted(by_artist, key=artist_key)

    sections = [(artist, by_artist[artist]) for artist in order]
    return render_template("explore.html", mode="artists", q=q, sort=sort, sections=sections)


def _render_title(items: list[dict], q: str = "", sort: str = "az", page: int = 1) -> tuple[str, int]:
    if q:
        ql = q.lower()
        items = [i for i in items if ql in f"{i['artist']} - {i['title']}".lower()]
    items = sorted(items, key=lambda i: i["title"].lower(), reverse=(sort == "za"))

    limit = 50
    total_items = len(items)
    total_pages = max(1, (total_items + limit - 1) // limit)
    page = max(1, min(page, total_pages))
    start = (page - 1) * limit
    end = start + limit
    paginated_items = items[start:end]

    return render_template(
        "explore.html",
        mode="title",
        q=q,
        sort=sort,
        items=paginated_items,
        page=page,
        total_pages=total_pages,
        has_next=(page < total_pages),
        has_prev=(page > 1),
    )


_LRC_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


def _parse_lyrics(text: str) -> list[dict]:
    """Parses LRC/plain lyrics into structure for template rendering."""
    spans = []
    for line in text.splitlines():
        matches = _LRC_RE.findall(line)
        content = _LRC_RE.sub("", line).strip()
        if not content:
            continue
        if matches:
            seconds = int(matches[0][0]) * 60 + float(matches[0][1])
            spans.append({"t": seconds, "content": content})
        else:
            spans.append({"t": None, "content": content})
    return spans


def _render_track(watch_id: str, items: list[dict], spage: int = 0) -> tuple[str, int]:
    item = next((i for i in items if i["watch_id"] == watch_id), None)
    if item is None:
        return render_template("base.html", title="Not found", content="<h1>404 Not Found</h1>", status=404)

    sorted_items = sorted(items, key=lambda i: (i["title"].lower(), i["artist"].lower()))

    current_idx = 0
    for idx, i in enumerate(sorted_items):
        if i["watch_id"] == watch_id:
            current_idx = idx
            break

    limit = 50
    total_items = len(sorted_items)
    total_pages = max(1, (total_items + limit - 1) // limit)

    if spage <= 0:
        spage = (current_idx // limit) + 1

    spage = max(1, min(spage, total_pages))
    start = (spage - 1) * limit
    end = start + limit
    paginated_sidebar_items = sorted_items[start:end]

    lyrics_spans = []
    timed_lyrics = False
    lyrics_path = _lyrics_path(watch_id)
    if lyrics_path:
        lyrics_spans = _parse_lyrics(lyrics_path.read_text(encoding="utf-8", errors="replace"))
        timed_lyrics = any(span["t"] is not None for span in lyrics_spans)

    return render_template(
        "track.html",
        item=item,
        items=paginated_sidebar_items,
        spage=spage,
        total_pages=total_pages,
        has_next=(spage < total_pages),
        has_prev=(spage > 1),
        lyrics_spans=lyrics_spans,
        timed_lyrics=timed_lyrics,
    )


class ExploreHandler(UIHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            items = _scan()
            if path == "/":
                mode = query.get("mode", ["artists"])[0]
                q = query.get("q", [""])[0]
                sort = query.get("sort", ["az"])[0]
                try:
                    page_num = int(query.get("page", ["1"])[0])
                except ValueError:
                    page_num = 1
                if sort not in ("az", "za", "most", "least"):
                    sort = "az"
                if mode == "title":
                    self._respond(_render_title(items, q, sort, page_num))
                else:
                    self._respond(_render_artists(items, q, sort))

            elif path.startswith("/track/"):
                try:
                    spage = int(query.get("spage", ["0"])[0])
                except ValueError:
                    spage = 0
                self._respond(_render_track(path.rsplit("/", 1)[-1], items, spage))
            elif path.startswith("/cover/"):
                self._send_cover(path.rsplit("/", 1)[-1])
            elif path.startswith("/audio/"):
                self._send_audio(path.rsplit("/", 1)[-1])
            else:
                self._respond(
                    render_template("base.html", title="Not found", content="<h1>404 Not Found</h1>", status=404)
                )
        except Exception as e:
            logger.exception("Explore request failed")
            self._respond(
                render_template(
                    "base.html", title="Error", content=f"<h1>Error</h1><p>{html.escape(str(e))}</p>", status=500
                )
            )

    def _send_cover(self, watch_id: str):
        path = _cover_path(watch_id)
        if path is None:
            self._send_missing()
            return
        self._send_bytes(path.read_bytes(), _COVER_MIME.get(path.suffix, "application/octet-stream"))

    def _send_audio(self, watch_id: str):
        path = _audio_path(watch_id)
        if path is None:
            self._send_missing()
            return
        self._send_bytes(path.read_bytes(), _AUDIO_MIME.get(path.suffix, "application/octet-stream"))


def run() -> None:
    """Starts the explore web UI and blocks until interrupted."""
    run_server(ExploreHandler, "explore")
