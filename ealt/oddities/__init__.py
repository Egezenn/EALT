import typer

from . import explore as explore_module
from . import replace as replace_module

cli = typer.Typer()


@cli.command()
def replace() -> None:
    """Open a web UI to fix download errors."""
    replace_module.run()


@cli.command()
def explore() -> None:
    """Open a web UI to browse the music library."""
    explore_module.run()


def register(root: typer.Typer) -> None:
    """Registers the oddities subcommands onto the root CLI."""
    root.add_typer(cli, name="oddities", help="Odd utilities.")
