"""Status lines and next-step hints. Rich markup; IDs are escaped."""

import re

from app.models import JobAnalysis, JobPosting, Profile, ResumePlan
from app.term import DIVIDER, esc, item_id, rule, say
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
    rendered = [DIVIDER, "[bold yellow]Next:[/]"]
    for line in lines:
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) == 2:
            rendered.append(f"  [bold cyan]{esc(parts[0])}[/]  [dim]{esc(parts[1])}[/]")
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


def print_plan(posting: JobPosting, analysis: JobAnalysis, plan: ResumePlan, profile: Profile) -> None:
    label = posting.title or posting.company or posting.source
    say(f"[bold]Job:[/] {esc(label)}")
    if posting.url:
        say(f"[dim]{esc(posting.url)}[/]")
    say(f"[bold]Must-haves:[/] {esc(plan.coverage)}")
    if analysis.missing:
        say(f"[yellow]Missing from warehouse:[/] {esc(', '.join(analysis.missing))}")
    elif analysis.must_have:
        say("[dim]No must-have gaps in the warehouse (coverage is for this pick list).[/]")
    say("")
    say("[bold]Keep[/]  [dim](weak match still ships — this is not a gate)[/]")
    for pick in plan.selected:
        item = profile.find_item(pick.item_id)
        title = item.title if item else pick.item_id
        org = f" @ {item.org}" if item and item.org else ""
        say(f"  {item_id(pick.item_id)} [bold]{esc(title)}{esc(org)}[/]  [cyan]{pick.score:.0f}[/]  [dim]{esc(pick.reason)}[/]")
        if item:
            for bid in pick.bullet_ids:
                bullet = profile.find_bullet(bid)
                if bullet:
                    say(f"    [dim]-[/] {esc(bullet.text)}")
    if plan.excluded:
        say("")
        say("[dim]On the bench:[/] " + " ".join(item_id(i) for i in plan.excluded))


def after_plan() -> str:
    return next_steps(
        "resume new <url|file|->               try another job",
        "resume show                           edit the warehouse",
        "(PDF export is M3 — not built yet)",
    )


def print_profile(profile: Profile) -> None:
    p = profile.personal
    say(f"[bold cyan]Name:[/]    {esc(p.name) or '[dim]none[/]'}")
    say(f"[bold cyan]Email:[/]   {esc(p.email) or '[dim]none[/]'}")
    say(f"[bold cyan]Phone:[/]   {esc(p.phone) or '[dim]none[/]'}")
    links = ", ".join(p.links) if p.links else None
    say(f"[bold cyan]Links:[/]   {esc(links) if links else '[dim]none found[/]'}")
    say(f"[bold cyan]Summary:[/] {esc(profile.summary) if profile.summary else '[dim]none found[/]'}")

    rule("Experience")
    say(f"[bold blue]Experience ({len(profile.experiences)}):[/]")
    for item in profile.experiences:
        org = f" [dim]@ {esc(item.org)}[/]" if item.org else ""
        dates = f" [dim]({esc(item.dates)})[/]" if item.dates else ""
        say(f"  {item_id(item.id)} [bold]{esc(item.title)}[/]{org}{dates}")
        for bullet in item.bullets:
            say(f"    [dim]-[/] {esc(bullet.text)}")

    rule("Projects")
    say(f"[bold magenta]Projects ({len(profile.projects)}):[/]")
    for item in profile.projects:
        tech = f" [green]\\[{esc(', '.join(item.tech))}][/]" if item.tech else ""
        say(f"  {item_id(item.id)} [bold]{esc(item.title)}[/]{tech}")
        for bullet in item.bullets:
            say(f"    [dim]-[/] {esc(bullet.text)}")

    rule("Education")
    say(f"[bold blue]Education ({len(profile.education)}):[/]")
    for edu in profile.education:
        say(f"  [bold]{esc(edu.school)}[/] [dim]— {esc(edu.degree)} ({esc(edu.dates)})[/]")

    skills = ", ".join(profile.skills) if profile.skills else None
    say("")
    say(f"[bold green]Skills:[/] {esc(skills) if skills else '[dim]none found[/]'}")
