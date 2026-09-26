import typer

from app import cli_ui
from app.models import Profile
from app.paths import ResumePathResolver
from app.store import ProfileStore
from app.term import ask, confirm, rule, say, say_err, spin
from app.warehouse import ProfileMerger, add_bullet, add_experience, add_project, format_counts

app = typer.Typer(
    help="Resume OS — local career warehouse.",
    invoke_without_command=True,
    no_args_is_help=False,
)
add_app = typer.Typer(
    help="Add a job, project, or bullet to the warehouse.",
    invoke_without_command=True,
    no_args_is_help=False,
)
app.add_typer(add_app, name="add")


def _store() -> ProfileStore:
    return ProfileStore()


def _load_profile(store: ProfileStore) -> Profile:
    try:
        return store.load()
    except FileNotFoundError:
        say_err(cli_ui.no_warehouse())
        raise typer.Exit(code=1)


def _import_pdf(raw_path: str) -> Profile:
    from app.importing.profile_builder import ProfileImporter

    path = ResumePathResolver().resolve(raw_path)
    try:
        with spin("Reading PDF…"):
            return ProfileImporter().import_pdf(path)
    except (FileNotFoundError, ValueError) as e:
        say_err(cli_ui.error(str(e), "resume init"))
        raise typer.Exit(code=1)


@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    store = _store()
    profile = store.load() if store.exists() else None
    rule("Resume OS")
    say(cli_ui.home(profile, str(store._path)))


@app.command()
def init(
    path: str | None = typer.Argument(None, help="Optional first resume PDF"),
) -> None:
    """Start Resume OS: import your resume(s) into the warehouse."""
    store = _store()
    rule("Resume OS")
    say(cli_ui.init_welcome())

    if store.exists():
        say(cli_ui.already_inited(store.load(), str(store._path)))
        return

    say("Point me at a resume PDF. One is enough to start; you can add more in a moment.")
    if path is None:
        path = ask("Path to a resume PDF (drag a file here or paste)")
    incoming = _import_pdf(path)
    store.save(incoming)
    say(f"[bold green]Imported.[/] {format_counts(incoming)}")

    while confirm("Add another resume PDF to the warehouse?"):
        extra = ask("Path to the next PDF")
        incoming = _import_pdf(extra)
        profile, report = ProfileMerger().merge(store.load(), incoming)
        store.save(profile)
        say(f"[bold green]Merged.[/] {report.summary()}")

    rule()
    say(cli_ui.after_init(store.load(), str(store._path)))


@app.command("import")
def import_profile(
    path: str | None = typer.Argument(None, help="Path to a resume PDF"),
    merge: bool = typer.Option(False, "--merge", help="Union this PDF into the existing warehouse"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
) -> None:
    """Create the warehouse from a PDF, or merge another PDF into it."""
    if path is None:
        path = ask("Path to a resume PDF (drag a file here or paste)")

    store = _store()
    if merge and not store.exists():
        say_err(cli_ui.no_warehouse())
        raise typer.Exit(code=1)

    incoming = _import_pdf(path)

    if merge:
        profile, report = ProfileMerger().merge(store.load(), incoming)
        say(f"[bold]This PDF would add:[/] {report.summary()}")
        if not yes and not confirm("Merge it into the warehouse?"):
            say("[yellow]Cancelled.[/] Warehouse unchanged.")
            raise typer.Exit(code=1)
        saved = store.save(profile)
        say(cli_ui.after_merge(report.summary(), profile, str(saved)))
        return

    if store.exists() and not yes:
        say("[yellow]A warehouse already exists.[/] Import without --merge replaces it.")
        if not confirm("Replace the existing warehouse?"):
            say("[yellow]Cancelled.[/] Use:  [bold cyan]resume import --merge <this.pdf>[/]")
            raise typer.Exit(code=1)

    saved = store.save(incoming)
    say(cli_ui.after_create(incoming, str(saved)))


@app.command()
def show() -> None:
    """Print the warehouse and item IDs."""
    profile = _load_profile(_store())
    rule("Warehouse")
    say(f"[bold]{format_counts(profile)}[/]\n")
    cli_ui.print_profile(profile)
    say(cli_ui.after_show())


@add_app.callback()
def add_home(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        say(cli_ui.add_menu())


@add_app.command()
def experience() -> None:
    """Add a job to the warehouse."""
    store = _store()
    profile = _load_profile(store)
    say("[bold]Adding a job.[/] [dim]Blank skips optional fields.[/]\n")
    title = ask("Job title (e.g. Data Analyst)")
    if not title:
        say_err(cli_ui.error("Title is required."))
        raise typer.Exit(code=1)
    org = _optional_ask("Company (blank to skip)")
    dates = _optional_ask("Dates (e.g. 2019 - 2020)")
    location = _optional_ask("Location (blank to skip)")
    item = add_experience(
        profile,
        title=title,
        org=org,
        dates=dates,
        location=location,
        bullets=_prompt_bullets(),
    )
    store.save(profile)
    title = item.title + (f" @ {item.org}" if item.org else "")
    say(cli_ui.after_add_item("job", item.id, title, profile))


@add_app.command()
def project() -> None:
    """Add a project to the warehouse."""
    store = _store()
    profile = _load_profile(store)
    say("[bold]Adding a project.[/] [dim]Blank skips optional fields.[/]\n")
    title = ask("Project name")
    if not title:
        say_err(cli_ui.error("Title is required."))
        raise typer.Exit(code=1)
    tech_raw = _optional_ask("Tech, comma-separated (blank to skip)")
    tech = [t.strip() for t in (tech_raw or "").split(",") if t.strip()]
    item = add_project(profile, title=title, tech=tech, bullets=_prompt_bullets())
    store.save(profile)
    title = item.title + (f" [{', '.join(item.tech)}]" if item.tech else "")
    say(cli_ui.after_add_item("project", item.id, title, profile))


@add_app.command()
def bullet(
    item_id: str = typer.Argument(..., help="Job or project id from `resume show`, e.g. exp.1"),
    text: str | None = typer.Option(None, "--text", help="Bullet text; prompted if omitted"),
) -> None:
    """Add a bullet under an existing job or project."""
    store = _store()
    profile = _load_profile(store)
    if text is None:
        text = ask("Bullet text")
    text = text.strip()
    if not text:
        say_err(cli_ui.error("Bullet text is required."))
        raise typer.Exit(code=1)
    try:
        added = add_bullet(profile, item_id, text)
    except ValueError as e:
        say_err(cli_ui.error(str(e), "resume show"))
        raise typer.Exit(code=1)
    store.save(profile)
    say(cli_ui.after_add_bullet(added.id, added.text, profile))


def _optional_ask(label: str) -> str | None:
    value = ask(label, default="")
    return value or None


def _prompt_bullets() -> list[str]:
    say("[dim]Bullets — one per line, blank line when done.[/]")
    bullets: list[str] = []
    while True:
        line = ask("  bullet", default="")
        if not line:
            return bullets
        bullets.append(line)


if __name__ == "__main__":
    app()
