import os
from pathlib import Path

import typer

from app import cli_ui
from app.models import Profile
from app.paste import read_paste
from app.paths import ResumePathResolver
from app.store import ProfileStore
from app.term import ask, confirm, esc, rule, say, say_err, show, spin
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
    from app.fx import banner

    store = _store()
    profile = store.load() if store.exists() else None
    banner("Your career warehouse → a tailored one-page resume. Local. Truthful. Free. ✨")
    say(cli_ui.home(profile, str(store._path)))


@app.command()
def init(
    path: str | None = typer.Argument(None, help="Optional first resume PDF"),
) -> None:
    """Start Resume OS: import your resume(s) into the warehouse."""
    from app.fx import banner

    store = _store()
    banner("Your career warehouse → a tailored one-page resume. Local. Truthful. Free. ✨")
    say(cli_ui.init_welcome())

    if not store.exists():
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
    else:
        say(cli_ui.already_inited(store.load(), str(store._path)))

    _session(store)


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


@app.command()
def check(
    fix: bool = typer.Option(False, "--fix", help="Walk through each issue and fix it in the warehouse"),
) -> None:
    """Proofread the warehouse: typos, grammar, and resume style (all local)."""
    from app.proofread import Proofreader, configured_engine, first_languagetool_run, warehouse_texts

    from app.fx import Steps, download_bar, rule_gradient

    store = _store()
    profile = _load_profile(store)
    rule_gradient("Proofread")
    texts = warehouse_texts(profile)
    engine = configured_engine()
    with Steps() as steps:
        label = "Starting the grammar checker" if engine == "languagetool" else "Loading the spell checker"
        with steps.step("🔤", label) as s:
            if engine == "languagetool" and first_languagetool_run():
                s.detail("first run: downloading LanguageTool (~260 MB, one time, stays local)")
            with download_bar(s):
                reader = Proofreader(profile)
            s.detail(reader.note or reader.engine)
        try:
            with steps.step("📝", f"Checking {len(texts)} lines") as s:
                issues = reader.check(texts)
                s.detail(f"{len(issues)} issue(s)" if issues else "all clear")
        except BaseException:
            reader.close()
            raise
    say("")
    try:
        cli_ui.print_issues(issues, reader.engine)
        if fix and issues:
            _fix_loop(store, profile, reader)
        elif issues:
            say(cli_ui.next_steps("resume check --fix        fix them one by one (saved to the warehouse)"))
    finally:
        reader.close()


def _fix_loop(store: ProfileStore, profile: Profile, reader) -> None:
    from app.proofread import add_to_dictionary, apply_fix, warehouse_texts
    from app.warehouse import refresh_vocabulary

    rule("Fix")
    say("[dim]For each issue: a number picks a suggestion, [bold]e[/bold] types your own, "
        "[bold]i[/bold] adds the word to your dictionary, Enter skips, [bold]q[/bold] stops.[/]")
    changed: dict[str, str] = {}
    for where, original in warehouse_texts(profile).items():
        text, skipped = original, set()
        while True:
            pending = [i for i in reader.check({where: text}) if (i.snippet, i.message) not in skipped]
            if not pending:
                break
            issue = pending[0]
            say("")
            show(cli_ui.issue_line(issue))
            for n, sug in enumerate(issue.suggestions[:3], 1):
                say(f"  [bold]{n}[/] {esc(sug or '(remove)')}")
            choice = ask("fix", default="").strip()
            if choice.lower() == "q":
                return _save_fixes(store, profile, changed)
            if choice.isdigit() and 1 <= int(choice) <= len(issue.suggestions[:3]):
                text = apply_fix(text, issue, issue.suggestions[int(choice) - 1])
            elif choice.lower() == "e":
                new = ask("new text", default=text).strip()
                if new:
                    text = new
                skipped.add((issue.snippet, issue.message))
            elif choice.lower() == "i" and issue.kind == "spelling":
                path = add_to_dictionary(issue.snippet)
                reader.ignore(issue.snippet)
                say(f"[dim]Added “{esc(issue.snippet)}” to {esc(path)}[/]")
            else:
                skipped.add((issue.snippet, issue.message))
        if text != original:
            changed[where] = text
            say(f"[green]✓[/] {esc(where)}: {esc(text)}")
    _save_fixes(store, profile, changed)


def _save_fixes(store: ProfileStore, profile: Profile, changed: dict[str, str]) -> None:
    from app.warehouse import refresh_vocabulary

    if not changed:
        say("[dim]No changes.[/]")
        return
    if not confirm(f"Save {len(changed)} fixed line(s) to the warehouse?"):
        say("[yellow]Not saved.[/]")
        return
    for where, text in changed.items():
        if where == "summary":
            profile.summary = text
        elif (bullet := profile.find_bullet(where)) is not None:
            bullet.text = text
        elif (item := profile.find_item(where)) is not None:
            item.title = text
    refresh_vocabulary(profile)
    store.save(profile)
    say(f"[bold green]Saved.[/] {len(changed)} line(s) updated in the warehouse.")


@app.command("new")
def new_resume(
    source: str | None = typer.Argument(
        None,
        help="Job URL, path to a .txt/.md JD, or '-' to paste",
    ),
    pdf: bool | None = typer.Option(
        None, "--pdf/--no-pdf", help="Go straight to review + PDF, or only print the match (default: ask)"
    ),
    rewrite: bool = typer.Option(
        False, "--rewrite", help="AI-tailor the bullets to the job when review opens (truth-checked; see config.toml)"
    ),
) -> None:
    """Match the warehouse to a job, review the picks, and build a one-page PDF."""
    profile = _load_profile(_store())
    _match_job(profile, source, build_pdf=True if rewrite else pdf, rewrite=rewrite)
    say(cli_ui.after_plan())


def _session(store: ProfileStore) -> None:
    while True:
        say(cli_ui.session_menu())
        choice = ask("Choose", default="paste").strip().lower()
        if choice in {"q", "quit", "exit"}:
            say("[dim]Later. Run [bold cyan]resume init[/] to come back.[/]")
            return
        if choice in {"p", "paste", "job", "new"}:
            _session_paste(store)
        elif choice in {"u", "update", "merge"}:
            _session_update(store)
        elif choice in {"s", "show"}:
            profile = store.load()
            rule("Warehouse")
            say(f"[bold]{format_counts(profile)}[/]\n")
            cli_ui.print_profile(profile)
        else:
            say("[yellow]Type paste, update, show, or quit.[/]")


def _session_paste(store: ProfileStore) -> None:
    say(cli_ui.paste_hint(url_ok=True))
    text = read_paste(whole_pipe=False)
    if not text:
        say("[yellow]Nothing pasted.[/]")
        return
    first = text.splitlines()[0].strip()
    if "\n" not in text and (
        first.lower().startswith(("http://", "https://")) or ResumePathResolver().resolve(first).exists()
    ):
        _match_job(store.load(), first)
        return
    _match_job(store.load(), "-", pasted=text)


def _session_update(store: ProfileStore) -> None:
    say("[dim]update:[/]  [bold cyan]pdf[/]  merge a resume   [bold cyan]job[/]  type a job   [bold cyan]project[/]   [bold cyan]bullet[/]   [bold cyan]back[/]")
    kind = ask("Update how", default="pdf").strip().lower()
    if kind in {"b", "back"}:
        return
    if kind in {"pdf", "resume", "merge"}:
        path = ask("Path to a resume PDF")
        incoming = _import_pdf(path)
        profile, report = ProfileMerger().merge(store.load(), incoming)
        say(f"[bold]This PDF would add:[/] {report.summary()}")
        if confirm("Merge it into the warehouse?"):
            store.save(profile)
            say(cli_ui.after_merge(report.summary(), profile, str(store._path)))
        else:
            say("[yellow]Cancelled.[/] Warehouse unchanged.")
        return
    if kind in {"job", "experience"}:
        experience()
        return
    if kind in {"project"}:
        project()
        return
    if kind in {"bullet"}:
        item_id = ask("Job or project id (e.g. exp.1)")
        text = ask("Bullet text")
        bullet(item_id, text)
        return
    say("[yellow]Type pdf, job, project, bullet, or back.[/]")


def _match_job(
    profile: Profile,
    source: str | None,
    pasted: str | None = None,
    build_pdf: bool | None = None,
    rewrite: bool = False,
) -> None:
    from app.apply import JobMatcher
    from app.fetching.generic import FetchError

    if source is None:
        source = ask("Job URL, JD file, or '-' to paste")
    if pasted is None and source.strip() in {"-", "paste"}:
        say(cli_ui.paste_hint())
        pasted = read_paste()
    from app.fx import Steps

    matcher = JobMatcher()
    is_url = source.strip().lower().startswith(("http://", "https://"))
    say("")
    try:
        with Steps() as steps:
            icon, label = ("🌐", "Fetching the job posting") if is_url else ("📄", "Reading the job description")
            with steps.step(icon, label) as s:
                posting = matcher.fetch(source, pasted=pasted)
                where = posting.source if posting.source in {"greenhouse", "lever", "ashby"} else ""
                s.detail(" · ".join(x for x in [where, posting.company, f"{len(posting.raw_text.split())} words"] if x))
            with steps.step("🔎", "Finding requirements") as s:
                analysis = matcher.analyze(posting, profile)
                s.detail(f"{len(analysis.must_have)} must-haves · {len(analysis.nice_to_have)} nice-to-haves")
            meaning = None
            if matcher.meaning_enabled():
                with steps.step("🧠", "Comparing meaning, not just keywords") as s:
                    s.detail("local model")
                    meaning = matcher.meaning(analysis, profile)
                    s.detail(f"{sum(1 for v in (meaning or {}).values() if v[0] > 0)} bullets on-topic" if meaning else "skipped")
            with steps.step("🧮", "Picking your strongest bullets") as s:
                plan = matcher.plan(analysis, profile, meaning)
                s.detail(f"{len(plan.selected)} items · coverage {plan.coverage}")
    except FetchError as e:
        say_err(cli_ui.error(str(e), "resume new -   (then paste the description)"))
        return
    except ValueError as e:
        say_err(cli_ui.error(str(e)))
        return
    say("")
    cli_ui.print_plan(posting, analysis, plan, profile)
    if build_pdf is None:
        say("")
        build_pdf = confirm("Review these picks and build the one-page PDF?")
    if build_pdf:
        _review_and_render(profile, posting, analysis, plan, rewrite=rewrite)


def _review_and_render(profile: Profile, posting, analysis, plan, rewrite: bool = False) -> None:
    from app.paths import desktop_dir, windows_path
    from app.render import RenderError, ResumeRenderer
    from app.review import PlanReviewer

    def rewriter(bullet_ids: list[str], on_text=None):
        from app.ai.provider import load_provider
        from app.ai.writer import BulletWriter

        return BulletWriter(load_provider(), profile).rewrite(bullet_ids, analysis, posting, on_text=on_text)

    from app.fx import rule_gradient

    rule_gradient("Review")

    def proofreader():
        from app.proofread import Proofreader

        return Proofreader(profile)

    from app.style import load_style

    def previewer(current_plan, style) -> str:
        from app.paths import open_file

        with spin("Rendering a preview…"):
            result = ResumeRenderer().fit(profile, current_plan, analysis.keywords, style=style)
        home = Path(os.environ.get("RESUME_HOME", Path.home() / ".resume")).expanduser()
        path = home / "cache" / "preview.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result.pdf)
        dropped = f", {len(result.dropped)} bullet(s) left out to fit" if result.dropped else ""
        opened = "opened" if open_file(path) else "saved"
        return f"[green]✓[/] Preview {opened}: [bold]{esc(windows_path(path) or str(path))}[/] [dim]({style.describe()}{dropped})[/]"

    reviewer = PlanReviewer(
        profile, plan, rewriter=rewriter, rewrite_on_start=rewrite, proofreader=proofreader,
        previewer=previewer, style=load_style(),
    )
    reviewed = reviewer.run()
    if reviewed is None:
        say("[yellow]Cancelled.[/] No PDF written.")
        return
    from app.fx import Steps

    say("")
    try:
        with Steps() as steps:
            with steps.step("📐", "Laying out one page") as s:
                result = ResumeRenderer().fit(
                    profile, reviewed, analysis.keywords, on_progress=s.detail, style=reviewer.style
                )
                note = f"dropped {len(result.dropped)} to fit" if result.dropped else "fits"
                s.detail(f"{result.font_size:g}pt · {note}")
            with steps.step("🔍", "Finding your Desktop") as s:
                out_dir = desktop_dir()
                s.detail(windows_path(out_dir) or str(out_dir))
    except RenderError as e:
        say_err(cli_ui.error(str(e)))
        return
    name = ask("File name", default=cli_ui.default_pdf_name(profile, posting))
    path = cli_ui.unique_path(out_dir, name)
    try:
        with Steps() as steps, steps.step("💾", "Saving the PDF") as s:
            out_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(result.pdf)
            s.detail(f"{len(result.pdf) // 1024} KB")
    except OSError as e:
        say_err(cli_ui.error(f"Couldn't write {path}: {e}"))
        return
    cli_ui.celebrate(path, windows_path(path), result, profile)


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
