import html
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .. import const, utils
from .shared import UIHandler, page, run_server

logger = logging.getLogger(__name__)

STYLE = """
  body { font-family: sans-serif; margin: 0; }
  .page { max-width: 1100px; margin: 0 auto; height: 100vh; box-sizing: border-box; padding: 20px;
          display: flex; flex-direction: column; overflow: hidden; }
  .scroll { flex: 1; overflow-y: auto; min-height: 0; }
  h1 { font-size: 28px; }
  .tabs a { margin-right: 16px; font-size: 18px; }
  input, select, button { font-size: 16px; padding: 6px; }
  form { margin-bottom: 12px; }
  details { border: 1px solid #333; margin-bottom: 8px; padding: 10px; }
  summary { cursor: pointer; font-weight: bold; font-size: 18px; }
  .tracks { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }
  .track { border: 1px solid #333; padding: 8px; width: 150px; text-decoration: none; color: #000; }
  .track img { width: 150px; height: 150px; object-fit: cover; display: block; }
  .grid { display: flex; flex-wrap: wrap; gap: 12px; }
  .cell { width: 200px; height: 200px; position: relative; overflow: hidden;
          border: 1px solid #333; text-decoration: none; background: #ccc; }
  .cell img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .cell .label { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0, 0, 0, 0.7);
                 color: #fff; padding: 4px 8px; }
  .track-page { background-size: cover; background-position: center; height: 100vh; overflow: hidden;
                display: flex; justify-content: center; }
  .track-content { text-align: center; max-width: 720px; height: 100vh; box-sizing: border-box;
                   padding: 40px 20px; display: flex; flex-direction: column;
                   color: #fff; background: rgba(0, 0, 0, 0.55); }
  .track-content img { max-width: 300px; border: 1px solid #333; align-self: center; }
  .track-content audio { display: block; margin: 12px auto; }
  .track-page a { color: #ddd; }
  .track-back { position: fixed; top: 16px; left: 16px; z-index: 10; font-size: 18px; }
  .track-back a { color: #fff; background: rgba(0, 0, 0, 0.6); padding: 8px 16px; text-decoration: none; border: 1px solid #333; }
  .lyrics { font-size: 22px; line-height: 1.9; flex: 1; overflow-y: auto; min-height: 0; }
  .lyrics span { display: block; }
  .lyrics .active { font-weight: bold; }
  table { border-collapse: collapse; width: 100%; background: #fff; color: #000; }
  th, td { border: 1px solid #333; padding: 8px; text-align: left; }
  th { cursor: pointer; background: #eee; user-select: none; }
  th.sort-asc::after { content: " ▲"; }
  th.sort-desc::after { content: " ▼"; }
  tbody tr:hover { background: #f2f2f2; }
"""

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


def _page(title: str, body: str, status: int = 200) -> tuple[str, int]:
    return page(title, body, status, STYLE)


def _tabs(mode: str, q: str, sort: str) -> str:
    qp = ""
    if q:
        qp += f"&q={quote(q)}"
    if sort != "az":
        qp += f"&sort={quote(sort)}"
    return (
        f'<p class="tabs"><a href="/?mode=artists{qp}">By Artist</a>'
        f'<a href="/?mode=title{qp}">By Title</a>'
        f'<a href="/?mode=table{qp}">Table</a></p>'
    )


def _controls(mode: str, q: str, sort: str) -> str:
    def opt(value: str, label: str) -> str:
        sel = " selected" if sort == value else ""
        return f'<option value="{value}"{sel}>{label}</option>'

    if mode == "table":
        select = ""
    else:
        options = "".join(
            opt(v, l)
            for v, l in (
                [("az", "A-Z"), ("za", "Z-A")]
                if mode == "title"
                else [("az", "A-Z"), ("za", "Z-A"), ("most", "Most tracks"), ("least", "Least tracks")]
            )
        )
        select = f'<select name="sort">{options}</select>'
    return (
        '<form method="get">'
        f'<input type="hidden" name="mode" value="{mode}">'
        f'<input type="text" name="q" value="{html.escape(q)}" placeholder="Search">'
        f"{select}"
        '<button type="submit">Go</button>'
        "</form>"
    )


def _render_artists(items: list[dict], q: str = "", sort: str = "az") -> tuple[str, int]:
    if q:
        items = [i for i in items if q.lower() in i["artist"].lower()]

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

    sections = []
    for artist in order:
        tracks = []
        for item in by_artist[artist]:
            cover = f'<img loading="lazy" src="/cover/{html.escape(item["watch_id"])}">' if item["cover"] else ""
            tracks.append(
                f'<a class="track" href="/track/{html.escape(item["watch_id"])}">{cover}'
                f"{html.escape(item['title'])}</a>"
            )
        sections.append(
            f"<details><summary>{html.escape(artist)} ({len(tracks)})</summary>"
            f'<div class="tracks">{"".join(tracks)}</div></details>'
        )
    body = (
        '<div class="page">'
        "<h1>Explore</h1>"
        f"{_tabs('artists', q, sort)}"
        f"{_controls('artists', q, sort)}"
        f'<div class="scroll">{"".join(sections) or "<p>No music found.</p>"}</div>'
        "</div>"
    )
    return _page("Explore", body)


def _render_title(items: list[dict], q: str = "", sort: str = "az") -> tuple[str, int]:
    if q:
        items = [i for i in items if q.lower() in i["title"].lower()]
    items = sorted(items, key=lambda i: i["title"].lower(), reverse=(sort == "za"))

    cells = []
    for item in items:
        cover = f'<img loading="lazy" src="/cover/{html.escape(item["watch_id"])}">' if item["cover"] else ""
        cells.append(
            f'<a class="cell" href="/track/{html.escape(item["watch_id"])}">{cover}'
            f'<span class="label">{html.escape(item["artist"])} — {html.escape(item["title"])}</span></a>'
        )
    body = (
        '<div class="page">'
        "<h1>Explore</h1>"
        f"{_tabs('title', q, sort)}"
        f"{_controls('title', q, sort)}"
        f'<div class="scroll"><div class="grid">{"".join(cells) or "<p>No music found.</p>"}</div></div>'
        "</div>"
    )
    return _page("Explore", body)


_SORT_SCRIPT = """
<script>
function sortTable(th, forceDir) {
  const tbody = th.closest('table').querySelector('tbody');
  const idx = Array.from(th.parentNode.children).indexOf(th);
  const asc = th.classList.contains('sort-asc');
  document.querySelectorAll('th').forEach((h) => h.classList.remove('sort-asc', 'sort-desc'));
  let dir;
  if (forceDir !== undefined) {
    dir = forceDir;
    th.classList.add(dir === 1 ? 'sort-asc' : 'sort-desc');
  } else {
    dir = asc ? -1 : 1;
    th.classList.add(asc ? 'sort-desc' : 'sort-asc');
  }
  const rows = Array.from(tbody.rows).sort((a, b) =>
    a.cells[idx].textContent.localeCompare(b.cells[idx].textContent, undefined, { numeric: true }) * dir
  );
  tbody.append(...rows);
}
document.querySelectorAll('th').forEach((th) => {
  th.addEventListener('click', () => sortTable(th));
});
const activeHeader = document.querySelector('th.sort-asc, th.sort-desc');
if (activeHeader) {
  sortTable(activeHeader, activeHeader.classList.contains('sort-asc') ? 1 : -1);
}
</script>
"""


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
    rows = []
    for item in items:
        desc = (item.get("desc") or "").strip().replace("\n", " ")
        if len(desc) > 80:
            desc = desc[:80] + "…"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['artist'])}</td>"
            f'<td><a href="/track/{html.escape(item["watch_id"])}">{html.escape(item["title"])}</a></td>'
            f"<td>{html.escape(item.get('album') or '')}</td>"
            f"<td>{html.escape(desc)}</td>"
            f"<td>{html.escape(item['watch_id'])}</td>"
            "</tr>"
        )
    body = (
        '<div class="page">'
        "<h1>Explore</h1>"
        f"{_tabs('table', q, 'az')}"
        f"{_controls('table', q, 'az')}"
        '<div class="scroll">'
        '<table><thead><tr><th class="sort-asc">Artist</th><th>Title</th><th>Album</th><th>Description</th><th>Watch ID</th></tr></thead>'
        f"<tbody>{''.join(rows) or '<tr><td colspan=5>No music found.</td></tr>'}</tbody></table>"
        "</div>"
        f"{_SORT_SCRIPT}"
        "</div>"
    )
    return _page("Explore", body)


_LRC_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

_LYRICS_SCRIPT = """
<script>
const player = document.getElementById('player');
const lines = Array.from(document.querySelectorAll('#lyrics span[data-t]'));
player.addEventListener('timeupdate', () => {
  const t = player.currentTime;
  let active = null;
  for (const el of lines) {
    if (parseFloat(el.dataset.t) <= t) active = el;
  }
  lines.forEach(el => el.classList.toggle('active', el === active));
});
</script>
"""


def _render_lyrics(text: str) -> str:
    """Renders LRC/plain lyrics; timed lines become highlightable spans."""
    spans = []
    for line in text.splitlines():
        matches = _LRC_RE.findall(line)
        content = _LRC_RE.sub("", line).strip()
        if not content:
            continue
        if matches:
            seconds = int(matches[0][0]) * 60 + float(matches[0][1])
            spans.append(f'<span data-t="{seconds:.2f}">{html.escape(content)}</span>')
        else:
            spans.append(f"<span>{html.escape(content)}</span>")
    if not spans:
        return ""
    timed = any("data-t=" in s for s in spans)
    script = _LYRICS_SCRIPT if timed else ""
    return f'<div class="lyrics" id="lyrics">{"".join(spans)}</div>{script}'


def _render_track(watch_id: str, items: list[dict]) -> tuple[str, int]:
    item = next((i for i in items if i["watch_id"] == watch_id), None)
    if item is None:
        return _page("Not found", "<h1>404</h1>", status=404)
    cover_url = f"/cover/{html.escape(watch_id)}"
    if item["cover"]:
        bg = f"background-image:url('{cover_url}')"
        cover = f'<img src="{cover_url}">'
    else:
        bg = "background:#222"
        cover = ""
    audio = f'<audio id="player" controls src="/audio/{html.escape(watch_id)}"></audio>' if item["audio"] else ""
    lyrics = ""
    lyrics_path = _lyrics_path(watch_id)
    if lyrics_path:
        lyrics = f"<h2>Lyrics</h2>{_render_lyrics(lyrics_path.read_text(encoding='utf-8', errors='replace'))}"
    lines = [
        f"<p><strong>Artist:</strong> {html.escape(item['artist'])}</p>",
        f"<p><strong>Title:</strong> {html.escape(item['title'])}</p>",
        f"<p><strong>Watch ID:</strong> {html.escape(watch_id)}</p>",
    ]
    if item.get("album"):
        lines.append(f"<p><strong>Album:</strong> {html.escape(item['album'])}</p>")
    if item.get("desc"):
        lines.append(f"<p><strong>Description:</strong> {html.escape(item['desc'])}</p>")
    body = (
        f'<div class="track-page" style="{bg}">'
        f'<div class="track-back"><a href="javascript:history.back()">Back</a></div>'
        f'<div class="track-content">'
        f"<h1>{html.escape(item['artist'])} - {html.escape(item['title'])}</h1>"
        f"{cover}{audio}{''.join(lines)}"
        f"{lyrics}"
        f"</div></div>"
    )
    return _page(item["title"], body)


class ExploreHandler(UIHandler):
    STYLE = STYLE

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
                if sort not in ("az", "za", "most", "least"):
                    sort = "az"
                if mode == "table":
                    self._respond(_render_table(items, q))
                elif mode == "title":
                    self._respond(_render_title(items, q, sort))
                else:
                    self._respond(_render_artists(items, q, sort))
            elif path.startswith("/track/"):
                self._respond(_render_track(path.rsplit("/", 1)[-1], items))
            elif path.startswith("/cover/"):
                self._send_cover(path.rsplit("/", 1)[-1])
            elif path.startswith("/audio/"):
                self._send_audio(path.rsplit("/", 1)[-1])
            else:
                self._respond(_page("Not found", "<h1>404</h1>", status=404))
        except Exception as e:
            logger.exception("Explore request failed")
            self._respond(_page("Error", f"<h1>Error</h1><p>{html.escape(str(e))}</p>", status=500))

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
