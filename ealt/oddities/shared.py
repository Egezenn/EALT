import html
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


def page(title: str, body: str, status: int = 200, style: str = "") -> tuple[str, int]:
    """Wraps content in a minimal HTML page with an inline stylesheet."""
    return (
        (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{style}</style></head><body>{body}</body></html>"
        ),
        status,
    )


class UIHandler(BaseHTTPRequestHandler):
    """Base request handler providing common page/bytes/error plumbing for oddities web UIs."""

    STYLE = ""

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)

    def _page(self, title: str, body: str, status: int = 200) -> tuple[str, int]:
        return page(title, body, status, self.STYLE)

    def _respond(self, response):
        body, status = response
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_bytes(self, data: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception as e:
            logger.debug(f"Client disconnected during send: {e}")

    def _send_missing(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_error(self, message: str):
        try:
            body = f"<h1>Error</h1><p>{html.escape(message)}</p>".encode()
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.debug(f"Client disconnected during error response: {e}")


def run_server(handler_cls: type[BaseHTTPRequestHandler], label: str) -> None:
    """Starts a local web server for an oddities UI and blocks until interrupted."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    logger.info(f"EALT {label} UI running at {url} (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.debug(f"Could not open browser: {e}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped.")
