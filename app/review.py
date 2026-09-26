"""Review the plan before rendering: toggle, edit, reorder, add, approve.

Terminal commands, not chat. Every edit passes the TruthGuard before it is
accepted. Works on a copy; the caller gets the reviewed plan back, or None
if the user quits.
"""

import copy
from typing import Callable

from rich.table import Table
from rich.text import Text

from app.guard import TruthGuard
from app.models import PlannedPick, Profile, ResumePlan
from app.term import ask, console, esc, say, show

HELP = [
    ("Enter / pdf", "approve and build the PDF"),
    ("exp.2.3", "toggle that bullet on/off"),
    ("edit exp.2.3", "rewrite a bullet (truth-checked)"),
    ("rewrite", "AI-tailor all bullets on the resume to the job (truth-checked)"),
    ("rewrite exp.2 / exp.2.3", "AI-tailor one job/project or one bullet"),
    ("reset exp.2.3 / reset all", "back to the original wording"),
    ("up exp.2.3", "move a bullet up"),
    ("add proj.3 / drop exp.4", "add or remove a job/project"),
    ("check", "proofread the bullets on the resume (typos, grammar, style)"),
    ("list", "show everything again"),
    ("quit", "cancel, no PDF"),
]


class PlanReviewer:
    def __init__(
        self,
        profile: Profile,
        plan: ResumePlan,
        *,
        prompt: Callable[..., str] = ask,
        bullets_per_item: int = 4,
        rewriter: Callable[[list[str]], "RewriteResult"] | None = None,
        rewrite_on_start: bool = False,
        proofreader: Callable[[], object] | None = None,
    ) -> None:
        self._proofreader_factory = proofreader
        self._proofreader = None
        self._rewriter = rewriter
        self._rewrite_on_start = rewrite_on_start
        self._profile = profile
        self._plan = copy.deepcopy(plan)
        self._prompt = prompt
        self._guard = TruthGuard(profile)
        self._per_item = bullets_per_item

    def run(self) -> ResumePlan | None:
        self._print()
        if self._rewrite_on_start:
            say(self._rewrite("") or "")
        while True:
            raw = self._prompt("review", default="pdf").strip()
            cmd, _, arg = raw.partition(" ")
            cmd, arg = cmd.lower(), arg.strip()
            if cmd in {"", "pdf", "done", "approve", "ok", "y"}:
                if not any(p.bullet_ids for p in self._plan.selected):
                    say("[yellow]Nothing selected. Add an item first.[/]")
                    continue
                issues = self._check()
                if issues and cmd != "pdf!":
                    answer = self._prompt("build anyway? (y = yes, n = back to review)", default="n").strip().lower()
                    if answer not in {"y", "yes"}:
                        say("[dim]Fix with [bold]edit <id>[/bold], then press Enter again.[/]")
                        continue
                self._close()
                return self._plan
            if cmd == "check":
                if self._check() is None:
                    say("[yellow]Proofreading isn't available here.[/]")
                continue
            if cmd in {"q", "quit", "cancel"}:
                self._close()
                return None
            if cmd in {"?", "h", "help"}:
                self._print_help()
                continue
            if cmd in {"l", "ls", "list"}:
                self._print()
                continue
            message = self._apply(cmd, arg)
            if message:
                say(message)
                continue
            # Show just what changed.
            target = (arg or cmd).rsplit(".", 1)[0] if self._profile.find_bullet(arg or cmd) else arg
            pick = next((p for p in self._plan.selected if p.item_id == target), None)
            if pick:
                self._print_item(pick)
            else:
                say(f"[dim]{esc(target)} removed. Type [bold]list[/bold] to see everything.[/]")

    # --- commands ---

    def _apply(self, cmd: str, arg: str) -> str | None:
        """Run one command; returns an error message, or None on success."""
        if not arg and self._profile.find_bullet(cmd):
            return self._toggle(cmd)
        if cmd == "edit":
            return self._edit(arg)
        if cmd == "reset":
            if arg == "all":
                self._plan.edits.clear()
                self._plan.rewritten.clear()
                self._print()
                return "[dim]All bullets back to their original wording.[/]"
            if arg not in self._plan.edits:
                return f"[yellow]{esc(arg)} has no edit.[/]"
            del self._plan.edits[arg]
            if arg in self._plan.rewritten:
                self._plan.rewritten.remove(arg)
            return None
        if cmd == "rewrite":
            return self._rewrite(arg)
        if cmd == "up":
            return self._move_up(arg)
        if cmd == "add":
            return self._add_item(arg)
        if cmd == "drop":
            return self._drop_item(arg)
        return "[yellow]Unknown command.[/] Type [bold]?[/] for help."

    def _check(self) -> list | None:
        """Proofread what will be printed (edits and rewrites included).
        None = no proofreader configured."""
        from app.cli_ui import print_issues
        from app.term import spin

        if self._proofreader_factory is None:
            return None
        if self._proofreader is None:
            with spin("Starting the proofreader…"):
                self._proofreader = self._proofreader_factory()
        texts = {
            bid: self._plan.edits.get(bid, self._profile.find_bullet(bid).text)
            for p in self._plan.selected
            for bid in p.bullet_ids
            if self._profile.find_bullet(bid)
        }
        with spin("Proofreading…"):
            issues = self._proofreader.check(texts)
        print_issues(issues, self._proofreader.engine)
        return issues

    def _close(self) -> None:
        if self._proofreader is not None:
            self._proofreader.close()
            self._proofreader = None

    def _pick_for_bullet(self, bullet_id: str) -> PlannedPick | None:
        item_id = bullet_id.rsplit(".", 1)[0]
        return next((p for p in self._plan.selected if p.item_id == item_id), None)

    def _toggle(self, bullet_id: str) -> str | None:
        pick = self._pick_for_bullet(bullet_id)
        if pick is None:
            return f"[yellow]Its job/project isn't on the resume.[/] Try [bold]add {esc(bullet_id.rsplit('.', 1)[0])}[/]."
        if bullet_id in pick.bullet_ids:
            pick.bullet_ids.remove(bullet_id)
        else:
            pick.bullet_ids.append(bullet_id)  # goes last; `up` moves it
        return None

    def _edit(self, bullet_id: str) -> str | None:
        bullet = self._profile.find_bullet(bullet_id)
        if bullet is None:
            return f"[yellow]No bullet {esc(bullet_id)}.[/]"
        pick = self._pick_for_bullet(bullet_id)
        if pick is None or bullet_id not in pick.bullet_ids:
            return f"[yellow]Turn {esc(bullet_id)} on first (type {esc(bullet_id)}).[/]"
        current = self._plan.edits.get(bullet_id, bullet.text)
        say(f"[dim]Original:[/] {esc(bullet.text)}")
        new = self._prompt("new text (blank keeps it)", default="").strip()
        if not new or new == current:
            return "[dim]Unchanged.[/]"
        problems = self._guard.check_bullet(bullet_id, new)
        if problems:
            return "[red]Not saved:[/]\n" + "\n".join(f"  [red]•[/] {esc(p)}" for p in problems)
        if new == bullet.text:
            self._plan.edits.pop(bullet_id, None)
        else:
            self._plan.edits[bullet_id] = new
        if bullet_id in self._plan.rewritten:
            self._plan.rewritten.remove(bullet_id)  # now it's your wording
        return None

    def _rewrite(self, target: str) -> str:
        """AI rewrite of kept bullets (all, one item, or one bullet). Always
        returns a message; results are shown here, not as a normal redraw."""
        from app.ai.provider import ProviderError
        from app.term import spin

        if self._rewriter is None:
            return "[yellow]Rewriting isn't available here.[/]"
        kept = [bid for p in self._plan.selected for bid in p.bullet_ids]
        if target:
            ids = [b for b in kept if b == target or b.rsplit(".", 1)[0] == target]
            if not ids:
                return f"[yellow]{esc(target)} isn't on the resume.[/]"
        else:
            ids = kept
        ids = [b for b in ids if b not in self._plan.edits or b in self._plan.rewritten]  # keep your own edits
        if not ids:
            return "[dim]Nothing to rewrite (your own edits are left alone).[/]"
        try:
            with spin(f"Rewriting {len(ids)} bullet(s)… local models can take a few minutes"):
                result = self._rewriter(ids)
        except ProviderError as e:
            return f"[red]Rewrite failed:[/] {esc(str(e))}"
        for bid, text in result.accepted.items():
            self._plan.edits[bid] = text
            if bid not in self._plan.rewritten:
                self._plan.rewritten.append(bid)
        lines = []
        for bid, text in result.accepted.items():
            original = self._profile.find_bullet(bid).text
            lines.append(f"[magenta]✦[/] [cyan]{esc(bid)}[/]\n    [dim]- {esc(original)}[/]\n    [green]+ {esc(text)}[/]")
        for bid, problems in result.rejected.items():
            lines.append(f"[red]✗[/] [cyan]{esc(bid)}[/] [dim]kept original —[/] {esc('; '.join(problems))}")
        summary = (
            f"[bold]Rewrite:[/] {len(result.accepted)} tailored, {len(result.unchanged)} already fine, "
            f"{len(result.rejected)} rejected by the truth guard [dim]({result.calls} call(s))[/]. "
            "[dim]reset <id> undoes one, reset all undoes all.[/]"
        )
        return "\n".join(lines + [summary])

    def _move_up(self, bullet_id: str) -> str | None:
        pick = self._pick_for_bullet(bullet_id)
        if pick is None or bullet_id not in pick.bullet_ids:
            return f"[yellow]{esc(bullet_id)} isn't on the resume.[/]"
        i = pick.bullet_ids.index(bullet_id)
        if i > 0:
            pick.bullet_ids[i - 1], pick.bullet_ids[i] = pick.bullet_ids[i], pick.bullet_ids[i - 1]
        return None

    def _add_item(self, item_id: str) -> str | None:
        item = self._profile.find_item(item_id)
        if item is None:
            return f"[yellow]No job/project {esc(item_id)}.[/]"
        if any(p.item_id == item_id for p in self._plan.selected):
            return f"[yellow]{esc(item_id)} is already on the resume.[/]"
        scores = self._plan.bullet_scores
        best = sorted(item.bullets, key=lambda b: -scores.get(b.id, 0.0))[: self._per_item]
        self._plan.selected.append(
            PlannedPick(
                item_id=item_id,
                bullet_ids=[b.id for b in best],
                reason="added in review",
                score=self._plan.scores.get(item_id, 0.0),
            )
        )
        if item_id in self._plan.excluded:
            self._plan.excluded.remove(item_id)
        return None

    def _drop_item(self, item_id: str) -> str | None:
        pick = next((p for p in self._plan.selected if p.item_id == item_id), None)
        if pick is None:
            return f"[yellow]{esc(item_id)} isn't on the resume.[/]"
        self._plan.selected.remove(pick)
        self._plan.excluded.append(item_id)
        return None

    # --- display ---

    def _print(self) -> None:
        say("")
        say("[bold]Review[/] [dim]— [/][green]■[/][dim] on the resume, □ off, [/][magenta]✎[/][dim] your edit, [/][magenta]✦[/][dim] AI rewrite. Type [/][bold]?[/][dim] for commands.[/]")
        for label, prefix in (("Experience", "exp."), ("Projects", "proj.")):
            picks = [p for p in self._plan.selected if p.item_id.startswith(prefix)]
            if not picks:
                continue
            say(f"[bold blue]{label}[/]")
            for pick in picks:
                self._print_item(pick)
        if self._plan.excluded:
            benched = []
            for iid in self._plan.excluded:
                item = self._profile.find_item(iid)
                benched.append(f"[cyan]{esc(iid)}[/] [dim]{esc(item.title) if item else ''}[/]")
            show("[dim]Not included:[/] " + "   ".join(benched))

    def _print_item(self, pick: PlannedPick) -> None:
        item = self._profile.find_item(pick.item_id)
        if item is None:
            return
        org = f" · {item.org}" if item.org else ""
        show(Text.assemble((f"[{item.id}] ", "bold cyan"), (item.title, "bold"), (org, "dim")))
        id_width = max((len(b.id) for b in item.bullets), default=6)
        grid = Table.grid(padding=(0, 1))
        grid.add_column(width=3, min_width=3, justify="right", no_wrap=True)
        grid.add_column(width=id_width, min_width=id_width, no_wrap=True)
        grid.add_column()
        # Rich squeezes fixed columns before truncating a no_wrap one, so
        # cut the text to the room that's left ourselves.
        room = max(20, console.width - 3 - id_width - 2)

        def line(text: str, style: str = "") -> Text:
            t = Text(text, style=style)
            t.truncate(room, overflow="ellipsis")
            return t

        kept = [b for b in (self._profile.find_bullet(bid) for bid in pick.bullet_ids) if b]
        rest = [b for b in item.bullets if b.id not in pick.bullet_ids]
        for bullet in kept:
            if bullet.id in self._plan.rewritten:
                mark = Text("✦", style="magenta")
            elif bullet.id in self._plan.edits:
                mark = Text("✎", style="magenta")
            else:
                mark = Text("■", style="green")
            text = self._plan.edits.get(bullet.id, bullet.text)
            grid.add_row(mark, Text(bullet.id, style="cyan"), line(text))
        for bullet in rest:
            grid.add_row(Text("□", style="dim"), Text(bullet.id, style="dim cyan"), line(bullet.text, "dim"))
        show(grid)

    def _print_help(self) -> None:
        width = max(len(c) for c, _ in HELP)
        for command, what in HELP:
            say(f"  [bold cyan]{esc(command)}[/]{' ' * (width - len(command))}  [dim]{esc(what)}[/]")
