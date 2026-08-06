import html
import logging
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


from importlib.resources import files

from jinja2 import Environment, FileSystemLoader

templates_dir = files("ealt.oddities") / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)


def page(title: str, body: str, status: int = 200, style: str = "") -> tuple[str, int]:
    """Fallback minimal page wrapper for basic errors or plain views."""
    return (
        (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{style}</style></head><body>{body}</body></html>"
        ),
        status,
    )


def render_template(template_name: str, **context) -> tuple[str, int]:
    """Renders a Jinja2 template with context."""
    status = context.pop("status", 200)
    template = jinja_env.get_template(template_name)
    return template.render(**context), status


class UIHandler(BaseHTTPRequestHandler):
    """Base request handler providing common page/bytes/error plumbing for oddities web UIs."""

    STYLE = ""

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)

    def _page(self, title: str, body: str, status: int = 200) -> tuple[str, int]:
        return page(title, body, status, self.STYLE)

    def _render(self, template_name: str, **context) -> tuple[str, int]:
        return render_template(template_name, **context)

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
    """Starts a local web server for an oddities UI and runs it in the background."""
    import os
    import subprocess
    import sys
    import time

    from .. import const

    if os.environ.get("EALT_BACKGROUND") == "1":
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        port = server.server_address[1]

        port_file = const.DATA_DIR / f"{label}.port"
        pid_file = const.DATA_DIR / f"{label}.pid"
        port_file.write_text(str(port))
        pid_file.write_text(str(os.getpid()))

        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            port_file.unlink(missing_ok=True)
            pid_file.unlink(missing_ok=True)
    else:
        pid_file = const.DATA_DIR / f"{label}.pid"
        port_file = const.DATA_DIR / f"{label}.port"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                try:
                    os.kill(pid, 15)  # SIGTERM
                    for _ in range(20):
                        time.sleep(0.05)
                        try:
                            os.kill(pid, 0)
                        except OSError:
                            break
                except OSError:
                    pass
            except ValueError:
                pass
            finally:
                pid_file.unlink(missing_ok=True)
                port_file.unlink(missing_ok=True)

        env = os.environ.copy()
        env["EALT_BACKGROUND"] = "1"

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "oddities", label]
        else:
            cmd = [sys.executable, "-m", "ealt", "oddities", label]

        port_file.unlink(missing_ok=True)

        log_file = const.LOG_DIR / f"{label}_server.log"
        try:
            log_f = open(log_file, "a", encoding="utf-8")
            subprocess.Popen(cmd, env=env, stdout=log_f, stderr=log_f, start_new_session=True)
        except Exception as e:
            logger.error(f"Failed to spawn background server: {e}")
            print(f"Failed to spawn background server: {e}")
            return

        port = None
        for _ in range(30):
            if port_file.exists():
                try:
                    port = int(port_file.read_text().strip())
                    break
                except ValueError:
                    pass
            time.sleep(0.1)

        if port is None:
            print(f"Failed to start {label} server in background.")
            return

        url = f"http://127.0.0.1:{port}"
        print(f"EALT {label} UI running on port {port} ({url})")

        try:
            webbrowser.open(url)
        except Exception as e:
            logger.debug(f"Could not open browser: {e}")
