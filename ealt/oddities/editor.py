import html
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import const, utils
from .shared import UIHandler, render_template, run_server

logger = logging.getLogger(__name__)

_COVER_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


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


def _render_table(items: list[dict], q: str = "") -> tuple[str, int]:
    if q:
        ql = q.lower()
        items = [
            i
            for i in items
            if ql in i["artist"].lower()
            or ql in i["title"].lower()
            or ql in (i.get("album") or "").lower()
            or ql in (i.get("desc") or "").lower()
            or ql in i["watch_id"].lower()
        ]
    for item in items:
        desc = (item.get("desc") or "").strip().replace("\n", " ")
        if len(desc) > 80:
            desc = desc[:80] + "…"
        item["truncated_desc"] = desc
    return render_template("editor.html", q=q, items=items)


class EditorHandler(UIHandler):
    STYLE = ""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            items = _scan()
            if path == "/":
                q = query.get("q", [""])[0]
                self._respond(_render_table(items, q))
            elif path.startswith("/cover/"):
                self._send_cover(path.rsplit("/", 1)[-1])
            else:
                self._respond(
                    render_template("base.html", title="Not found", content="<h1>404 Not Found</h1>", status=404)
                )
        except Exception as e:
            logger.exception("Editor request failed")
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


def run() -> None:
    """Starts the editor web UI and blocks until interrupted."""
    run_server(EditorHandler, "editor")
