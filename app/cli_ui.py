"""Status lines and next-step hints. Rich markup; IDs are escaped."""

import re

from rich.columns import Columns
from rich.table import Table
from rich.text import Text

from app.models import JobAnalysis, JobPosting, Profile, ResumePlan
from app.term import DIVIDER, esc, item_id, rule, say, show
from app.warehouse import format_counts


def item_lines(profile: Profile) -> list[str]:
    lines = []
    for item in profile.experiences:
        suffix = f" [dim]@ {esc(item.org)}[/]" if item.org else ""
        lines.append(f"  {item_id(item.id)} [bold]{esc(item.title)}[/]{suffix}")
    for item in profile.projects:
        lines.append(f"  {item_id(item.id)} [bold]{esc(item.title)}[/]")
    return lines


def next_steps(*lines: str) -> str:
    rows = [re.split(r"\s{2,}", line.strip(), maxsplit=1) for line in lines]
    width = max((len(r[0]) for r in rows if len(r) == 2), default=0)
    rendered = [DIVIDER, "[bold yellow]Next:[/]"]
    for parts in rows:
        if len(parts) == 2:
            pad = " " * (width - len(parts[0]))
            rendered.append(f"  [bold cyan]{esc(parts[0])}[/]{pad}  [dim]{esc(parts[1])}[/]")
        else:
            rendered.append(f"  [bold cyan]{esc(parts[0])}[/]")
    return "\n".join(rendered)


def after_create(profile: Profile, saved: str) -> str:
    items = "\n".join(item_lines(profile)) or "  [dim](no jobs or projects parsed)[/]"
    return "\n".join(
        [
            "[bold green]Done:[/] created the warehouse from that PDF.",
            f"      [bold]{esc(format_counts(profile))}[/]",
            f"      [dim]saved to {esc(saved)}[/]",
            DIVIDER,
            "[bold]In warehouse:[/]",
            items,
            "",
            next_steps(
                "resume import --merge <another.pdf>   add another resume (DS, PM, …)",
                "resume add experience                 type a job that wasn't on the PDF",
                "resume show                           see full bullets and IDs",
            ),
        ]
    )


def after_merge(report_summary: str, profile: Profile, saved: str) -> str:
    now = format_counts(profile).removeprefix("Warehouse: ")
    return "\n".join(
        [
            "[bold green]Done:[/] merged that PDF into the warehouse.",
            f"      {esc(report_summary)}",
            f"      now [bold]{esc(now)}[/]",
            f"      [dim]saved to {esc(saved)}[/]",
            "",
            next_steps(
                "resume import --merge <another.pdf>   add another resume",
                "resume add project                    type a project",
                "resume show                           see what you have",
            ),
        ]
    )


def after_add_item(kind: str, iid: str, title: str, profile: Profile) -> str:
    return "\n".join(
        [
            f"[bold green]Done:[/] added {esc(kind)} {item_id(iid)} [bold]{esc(title)}[/]",
            f"      [bold]{esc(format_counts(profile))}[/]",
            "",
            next_steps(
                "resume add bullet <id> --text \"...\"   add a bullet (ids in resume show)",
                "resume add experience                 another job",
                "resume add project                    another project",
                "resume show",
            ),
        ]
    )


def after_add_bullet(bullet_id: str, text: str, profile: Profile) -> str:
    return "\n".join(
        [
            f"[bold green]Done:[/] added {item_id(bullet_id)} {esc(text)}",
            f"      [bold]{esc(format_counts(profile))}[/]",
            "",
            next_steps(
                "resume add bullet <id> --text \"...\"   another bullet",
                "resume show",
            ),
        ]
    )


def after_show() -> str:
    return next_steps(
        "resume import --merge <pdf>           add another resume",
        "resume add experience                 type a job",
        "resume add project                    type a project",
        "resume add bullet exp.1 --text \"...\"  add a bullet under that id",
    )


def home(profile: Profile | None, path: str) -> str:
    if profile is None:
        return "\n".join(
            [
                "[bold bright_cyan]Resume OS[/] [dim]— career warehouse[/]",
                "",
                "[bold yellow]Status:[/] empty. Nothing imported yet.",
                "",
                next_steps(
                    "resume init                           start — import your resumes",
                ),
            ]
        )
    items = "\n".join(item_lines(profile))
    counts = format_counts(profile).removeprefix("Warehouse: ")
    return "\n".join(
        [
            "[bold bright_cyan]Resume OS[/] [dim]— career warehouse[/]",
            "",
            f"[bold]Status:[/] {esc(counts)}",
            f"[dim]File:[/]   {esc(path)}",
            DIVIDER,
            "[bold]In warehouse:[/]",
            items,
            next_steps(
                "resume new <url|file|->               match this warehouse to a job",
                "resume import --merge <pdf>           add another resume",
                "resume add experience                 type a job",
                "resume show                           see full bullets",
            ),
        ]
    )


def add_menu() -> str:
    return "\n".join(
        [
            "[bold]Add[/] something that wasn't on a PDF.",
            "",
            next_steps(
                "resume add experience                 a job",
                "resume add project                    a project",
                "resume add bullet exp.1 --text \"...\"  a bullet (run resume show for ids)",
            ),
        ]
    )


def no_warehouse() -> str:
    return "[bold red]Nothing imported yet.[/]\n\n" + next_steps(
        "resume init                           start — import your resumes",
    )


def init_welcome() -> str:
    return "\n".join(
        [
            "[bold bright_cyan]Resume OS[/]",
            "[dim]We'll build one warehouse from every resume you have —[/]",
            "[dim]SWE, DS, PM, whatever. Then stay here: paste a job or update.[/]",
            "",
        ]
    )


def already_inited(profile: Profile, path: str) -> str:
    items = "\n".join(item_lines(profile))
    counts = format_counts(profile).removeprefix("Warehouse: ")
    return "\n".join(
        [
            "[bold green]Already set up.[/] Warehouse is ready.",
            f"[bold]Status:[/] {esc(counts)}",
            f"[dim]File:[/]   {esc(path)}",
            DIVIDER,
            "[bold]In warehouse:[/]",
            items,
            next_steps(
                "paste                                 match a job (JD / URL / file)",
                "update                                add another resume or type work",
                "show / quit",
            ),
        ]
    )


def session_menu() -> str:
    return "\n".join(
        [
            DIVIDER,
            "[bold]What next?[/]",
            "  [bold cyan]paste[/]   [dim]job description, URL, or JD file — pick from warehouse[/]",
            "  [bold cyan]update[/]  [dim]merge another resume PDF, or type a job / project / bullet[/]",
            "  [bold cyan]show[/]    [dim]full warehouse[/]",
            "  [bold cyan]quit[/]    [dim]leave[/]",
        ]
    )


def after_init(profile: Profile, saved: str) -> str:
    items = "\n".join(item_lines(profile)) or "  [dim](no jobs or projects parsed)[/]"
    return "\n".join(
        [
            "[bold green]Done:[/] warehouse is ready. Stay in this session or quit and come back with resume init.",
            f"      [bold]{esc(format_counts(profile))}[/]",
            f"      [dim]saved to {esc(saved)}[/]",
            DIVIDER,
            "[bold]In warehouse:[/]",
            items,
            next_steps(
                "paste                                 match a job",
                "update                                add a resume or type work",
                "show / quit",
            ),
        ]
    )


def error(message: str, next_line: str | None = None) -> str:
    lines = [f"[bold red]Error:[/] {esc(message)}"]
    if next_line:
        lines.append(f"[bold yellow]Next:[/]  [bold cyan]{esc(next_line)}[/]")
    return "\n".join(lines)


def paste_hint(url_ok: bool = False) -> str:
    what = "the job description, or a URL / file path" if url_ok else "the job description"
    return f"[dim]Paste {what}, then press [bold]Enter[/]. Blank lines in the paste are fine.[/]"


_MUST_STYLE = "bold bright_green"
_NICE_STYLE = "green"
_KEYWORD_STYLE = "cyan"


def print_plan(posting: JobPosting, analysis: JobAnalysis, plan: ResumePlan, profile: Profile) -> None:
    from app.analyzing.analyzer import inventory_keys, profile_vocabulary, requirement_keys
    from app.analyzing.terms import TermIndex

    index = TermIndex(profile_vocabulary(profile))
    rule(esc(posting.title or "Job"))
    source = posting.url or f"pasted · {len(posting.raw_text.split())} words"
    say(f"[dim]{esc(source)}[/]")
    say("")

    inventory = inventory_keys(profile, index)
    covered = set(plan.covered)

    def mark(term: str) -> Text:
        if term in covered:
            return Text(f"✓ {term}", style="green")
        if any(term in g and covered.intersection(g) for g in analysis.alternatives):
            return Text(f"✓ {term}", style="dim green")  # an either/or sibling is covered
        if requirement_keys(term, analysis.alternatives, index) & inventory:
            return Text(f"○ {term}", style="yellow")
        return Text(f"✗ {term}", style="red")

    def chips(terms: list[str]) -> Columns:
        return Columns([mark(t) for t in terms], padding=(0, 3))

    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column(ratio=1)
    if analysis.must_have:
        head = Text.assemble(("Must-haves: ", "bold"), (plan.coverage, "bold"), "  ", _bar(plan.must_have_hit, plan.must_have_total))
        grid.add_row(head, chips(analysis.must_have))
    else:
        grid.add_row(Text("Must-haves:", style="bold"), Text("none found in this posting", style="dim"))
    if analysis.nice_to_have:
        nice_hit = sum(1 for t in analysis.nice_to_have if t in covered)
        grid.add_row(
            Text.assemble(("Nice-to-have: ", "bold"), f"{nice_hit}/{len(analysis.nice_to_have)}"),
            chips(analysis.nice_to_have),
        )
    show(grid)
    show(
        "[dim][green]✓[/] on this resume   [yellow]○[/] in your warehouse, not in these picks   "
        "[red]✗[/] not in your warehouse   [dim green]✓[/] an either/or option is covered[/]"
    )

    styles = {index.key(t): _KEYWORD_STYLE for t in analysis.keywords}
    styles.update({index.key(t): _NICE_STYLE for t in analysis.nice_to_have})
    styles.update({index.key(t): _MUST_STYLE for t in analysis.must_have})
    top = max((p.score for p in plan.selected), default=0) or 1
    say("")
    say("[bold]Keep[/] [dim]— best matches first; a weak match still makes a resume[/]")
    say("")
    for label, prefix in (("Experience", "exp."), ("Projects", "proj.")):
        picks = [p for p in plan.selected if p.item_id.startswith(prefix)]
        if not picks:
            continue
        say(f"[bold blue]{label}[/]")
        for pick in picks:
            item = profile.find_item(pick.item_id)
            if item is None:
                continue
            _print_pick(pick, item, profile, index, styles, top)
            say("")

    if plan.excluded:
        benched = []
        for iid in plan.excluded:
            item = profile.find_item(iid)
            benched.append(f"{item_id(iid)} [dim]{esc(item.title) if item else ''}[/]")
        show("[dim]On the bench:[/] " + "   ".join(benched))


def _bar(hit: int, total: int, width: int = 12) -> Text:
    filled = round(width * hit / total) if total else 0
    color = "green" if hit * 3 >= total * 2 else "yellow" if hit * 3 >= total else "red"
    return Text.assemble(("━" * filled, color), ("━" * (width - filled), "grey35"))


def _print_pick(pick, item, profile: Profile, index, styles: dict[str, str], top: float) -> None:
    dots = round(5 * pick.score / top)
    head = Text.assemble(
        (f"[{pick.item_id}]", "bold cyan"),
        " ",
        (item.title, "bold"),
        (f" · {item.org}" if item.org else "", "dim"),
        "  ",
        ("●" * dots, "cyan"),
        ("○" * (5 - dots), "grey35"),
    )
    show(head)
    reason = pick.reason.removeprefix("matches: ")
    if pick.reason.startswith("matches: "):
        say(f"   [dim]matches[/] {esc(reason)}")
    else:
        say("   [dim]no keyword overlap — fills the slot[/]")
    bullets = Table.grid(padding=(0, 1))
    bullets.add_column(width=4, justify="right")
    bullets.add_column(ratio=1)
    for bid in pick.bullet_ids:
        bullet = profile.find_bullet(bid)
        if bullet:
            bullets.add_row(Text("•", style="dim"), _highlight(bullet.text, index, styles))
    show(bullets)


def _highlight(text: str, index, styles: dict[str, str]) -> Text:
    """Bullet text with the job's terms coloured where they appear."""
    out = Text(text)
    for start, end, key in index.find_spans(text):
        style = styles.get(key) or next((styles[k] for k in index.expand([key]) if k in styles), None)
        if style:
            out.stylize(style, start, end)
    return out


def after_plan() -> str:
    return next_steps(
        "resume new <url|file|->               try another job",
        "resume show                           see the whole warehouse",
    )


def default_pdf_name(profile: Profile, posting: JobPosting) -> str:
    parts = [profile.personal.name or "Resume", posting.title or ""]
    stem = "_".join(re.sub(r"[^A-Za-z0-9]+", "_", p).strip("_") for p in parts if p)
    return f"{stem[:80] or 'Resume'}.pdf"


def unique_path(folder, name: str):
    """folder/name.pdf, or name-2.pdf, name-3.pdf… so nothing is overwritten."""
    from pathlib import Path

    name = Path(name).name or "Resume.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    path = Path(folder) / name
    n = 2
    while path.exists():
        path = Path(folder) / f"{Path(name).stem}-{n}.pdf"
        n += 1
    return path


def after_render(path, win_path: str | None, result, profile: Profile) -> str:
    lines = [f"[bold green]Done:[/] one-page PDF saved.", f"      [bold]{esc(win_path or str(path))}[/]"]
    if result.dropped:
        dropped = []
        for did in result.dropped:
            bullet = profile.find_bullet(did)
            item = None if bullet else profile.find_item(did)
            dropped.append(f"{item_id(did)} [dim]{esc((bullet.text if bullet else item.title if item else '')[:60])}…[/]")
        lines.append(f"      [dim]To fit one page at {result.font_size:g}pt, left out:[/]")
        lines.extend(f"        {d}" for d in dropped)
    return "\n".join(lines)


def print_profile(profile: Profile) -> None:
    p = profile.personal
    none = Text("none found", style="dim")
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_row("Name:", Text(p.name) if p.name else none)
    grid.add_row("Email:", Text(p.email) if p.email else none)
    grid.add_row("Phone:", Text(p.phone) if p.phone else none)
    grid.add_row("Links:", Text("\n".join(p.links)) if p.links else none)
    grid.add_row("Summary:", Text(profile.summary) if profile.summary else none)
    show(grid)

    rule("Experience")
    say(f"[bold blue]Experience ({len(profile.experiences)}):[/]")
    for item in profile.experiences:
        org = f" [dim]@ {esc(item.org)}[/]" if item.org else ""
        dates = f" [dim]({esc(item.dates)})[/]" if item.dates else ""
        say(f"  {item_id(item.id)} [bold]{esc(item.title)}[/]{org}{dates}")
        _print_bullets(item)

    rule("Projects")
    say(f"[bold magenta]Projects ({len(profile.projects)}):[/]")
    for item in profile.projects:
        tech = f" [green]\\[{esc(', '.join(item.tech))}][/]" if item.tech else ""
        say(f"  {item_id(item.id)} [bold]{esc(item.title)}[/]{tech}")
        _print_bullets(item)

    rule("Education")
    say(f"[bold blue]Education ({len(profile.education)}):[/]")
    for edu in profile.education:
        say(f"  [bold]{esc(edu.school)}[/] [dim]— {esc(edu.degree)} ({esc(edu.dates)})[/]")

    skills = ", ".join(profile.skills) if profile.skills else None
    say("")
    show(f"[bold green]Skills:[/] {esc(skills) if skills else '[dim]none found[/]'}")


def _print_bullets(item) -> None:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=4, justify="right")
    grid.add_column(ratio=1)
    for bullet in item.bullets:
        grid.add_row(Text("•", style="dim"), Text(bullet.text))
    show(grid)


_KIND_STYLE = {"spelling": "red", "grammar": "yellow", "style": "cyan"}


def issue_line(issue) -> Text:
    """'exp.2.3  spelling  …built the dashbord for…  → dashboard'"""
    color = _KIND_STYLE.get(issue.kind, "white")
    lo, hi = max(0, issue.start - 30), min(len(issue.text), issue.end + 30)
    context = Text("…" if lo else "", style="dim")
    context.append(issue.text[lo:issue.start], style="dim")
    context.append(issue.text[issue.start:issue.end] or " ", style=f"bold {color} underline")
    context.append(issue.text[issue.end:hi], style="dim")
    context.append("…" if hi < len(issue.text) else "", style="dim")
    line = Text.assemble((f"{issue.where:<9}", "cyan"), (f"{issue.kind:<9}", color), context)
    line.append(f"\n{' ' * 18}{issue.message}", style="default")
    if issue.suggestions:
        line.append("  → ", style="dim")
        line.append(" / ".join(s or "(remove)" for s in issue.suggestions[:3]), style="green")
    return line


def print_issues(issues, engine: str) -> None:
    if not issues:
        say(f"[bold green]✓ No issues found[/] [dim]({esc(engine)})[/]")
        return
    counts = {k: sum(1 for i in issues if i.kind == k) for k in ("spelling", "grammar", "style")}
    summary = "  ".join(f"[{_KIND_STYLE[k]}]{n} {k}[/]" for k, n in counts.items() if n)
    say(f"[bold]{len(issues)} issue(s):[/] {summary} [dim]({esc(engine)})[/]")
    for issue in issues:
        show(issue_line(issue))
