import typer

from . import editor as editor_module
from . import explore as explore_module
from . import replace as replace_module

cli = typer.Typer()


@cli.command()
def replace() -> None:
    """Open a web UI to replace download errors."""
    replace_module.run()


@cli.command()
def explore() -> None:
    """Open a web UI to browse the music library."""
    explore_module.run()


@cli.command()
def editor() -> None:
    """Open a web UI to edit the library metadata in a table."""
    editor_module.run()


@cli.command()
def kill() -> None:
    """Kill any running oddity servers."""
    import os
    import signal

    from .. import const

    killed_any = False
    for label in ["explore", "replace", "editor"]:
        pid_file = const.DATA_DIR / f"{label}.pid"
        port_file = const.DATA_DIR / f"{label}.port"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Killed {label} server (PID {pid})")
                killed_any = True
            except ProcessLookupError:
                print(f"Server {label} was not running (stale PID file)")
            except Exception as e:
                print(f"Failed to kill {label} server: {e}")
            finally:
                pid_file.unlink(missing_ok=True)
                port_file.unlink(missing_ok=True)
    if not killed_any:
        print("No running oddity servers found.")


def register(root: typer.Typer) -> None:
    """Registers the oddities subcommands onto the root CLI."""
    root.add_typer(cli, name="oddities", help="Odd utilities.")
