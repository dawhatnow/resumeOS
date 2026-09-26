"""One place for all terminal output. Color via Rich; tags strip in tests."""

from contextlib import contextmanager

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, Prompt

console = Console(highlight=False, soft_wrap=True)
err_console = Console(stderr=True, highlight=False)

DIVIDER = "[dim]────────────────────────────────────────[/]"


def say(message: str = "") -> None:
    console.print(message)


def show(renderable) -> None:
    """Print a Rich layout (table/grid). Unlike say(), it wraps to the terminal
    width with hanging indents instead of spilling to column 0. A str is Rich markup."""
    if isinstance(renderable, str):
        from rich.text import Text

        renderable = Text.from_markup(renderable)
    console.print(renderable, soft_wrap=False)


def rule(title: str | None = None) -> None:
    """Full-width line between main blocks only."""
    if title:
        console.rule(f"[cyan]{title}[/]", style="dim cyan")
    else:
        console.rule(style="dim cyan")


@contextmanager
def spin(message: str):
    """Dots spinner while something slow runs (PDF import)."""
    with console.status(f"[cyan]{message}[/]", spinner="dots"):
        yield


def say_err(message: str = "") -> None:
    err_console.print(message)


def ask(label: str, default: str | None = None) -> str:
    styled = f"[cyan]{label}[/]"
    if default is None:
        return Prompt.ask(styled).strip()
    return Prompt.ask(styled, default=default).strip()


def confirm(label: str) -> bool:
    return Confirm.ask(f"[yellow]{label}[/]")


def esc(value: object) -> str:
    return escape(str(value) if value is not None else "")


def item_id(iid: str) -> str:
    """Render [exp.1] in cyan. A closing \\] before [/] breaks Rich, so only [ is escaped."""
    return f"[bold cyan]\\[{esc(iid)}][/]"
