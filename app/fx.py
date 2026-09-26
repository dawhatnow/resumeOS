"""Terminal effects: gradient banner with a glow sweep, Cursor-style live step
tracker (spinner, shimmer, timers, progress bars, streaming preview).

Everything animated turns itself off when output isn't a terminal (tests,
pipes, CI) or when RESUME_PLAIN=1 — then steps print as plain ✓ lines.
"""

import os
import time
from contextlib import contextmanager

from rich.console import Group
from rich.live import Live
from rich.progress_bar import ProgressBar
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from app.term import console

PALETTE = ["#00d7ff", "#5f87ff", "#af5fff", "#ff5fd7"]  # cyan → blue → violet → pink

_ART = [
    "██████╗ ███████╗███████╗██╗   ██╗███╗   ███╗███████╗     ██████╗ ███████╗",
    "██╔══██╗██╔════╝██╔════╝██║   ██║████╗ ████║██╔════╝    ██╔═══██╗██╔════╝",
    "██████╔╝█████╗  ███████╗██║   ██║██╔████╔██║█████╗      ██║   ██║███████╗",
    "██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╔╝██║██╔══╝      ██║   ██║╚════██║",
    "██║  ██║███████╗███████║╚██████╔╝██║ ╚═╝ ██║███████╗    ╚██████╔╝███████║",
    "╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝     ╚═════╝ ╚══════╝",
]


def animated() -> bool:
    return console.is_terminal and not os.environ.get("RESUME_PLAIN") and not os.environ.get("CI")


# --- colour helpers ---

def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _hex(c: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % c


def palette_at(t: float) -> tuple[int, int, int]:
    """0..1 along PALETTE."""
    t = min(max(t, 0.0), 1.0) * (len(PALETTE) - 1)
    i = min(int(t), len(PALETTE) - 2)
    return _mix(_rgb(PALETTE[i]), _rgb(PALETTE[i + 1]), t - i)


def gradient(lines: list[str] | str, glow_at: float | None = None, bold: bool = True) -> Text:
    """Left-to-right gradient; glow_at = column of a bright band (for the sweep)."""
    lines = [lines] if isinstance(lines, str) else lines
    width = max(len(l) for l in lines) or 1
    out = Text()
    for n, line in enumerate(lines):
        for col, ch in enumerate(line):
            color = palette_at(col / width)
            if glow_at is not None:
                color = _mix(color, (255, 255, 255), max(0.0, 1 - abs(col - glow_at) / 7) * 0.85)
            out.append(ch, style=f"{'bold ' if bold else ''}{_hex(color)}")
        if n < len(lines) - 1:
            out.append("\n")
    return out


def shimmer(label: str, t: float) -> Text:
    """Cursor-style moving highlight across a label."""
    pos = (t * 22) % (len(label) + 12) - 6
    out = Text()
    for i, ch in enumerate(label):
        glow = max(0.0, 1 - abs(i - pos) / 4)
        out.append(ch, style=_hex(_mix((150, 150, 165), (235, 250, 255), glow)))
    return out


# --- banner ---

def banner(subtitle: str = "") -> None:
    art = _ART if console.width >= len(_ART[0]) + 2 else ["✦ RESUME OS"]
    width = len(art[0])
    if animated():
        with Live(console=console, refresh_per_second=40, transient=False) as live:
            frames = 22
            for f in range(frames + 1):
                live.update(gradient(art, glow_at=-10 + f * (width + 20) / frames))
                time.sleep(0.03)
            live.update(gradient(art))
    else:
        console.print(gradient(art))
    if subtitle:
        console.print(Text(subtitle, style="dim"))


def rule_gradient(title: str) -> None:
    """A section header: '── ✦ Title ─────' with the gradient."""
    width = max(20, console.width)
    head = f"── ✦ {title} "
    console.print(gradient(head + "─" * max(0, width - len(head)), bold=False))


# --- live steps ---

_ACTIVE: "Steps | None" = None


class _Step:
    def __init__(self, icon: str, label: str) -> None:
        self.icon, self.label = icon, label
        self.detail = ""
        self.preview: list[str] = []
        self.progress: tuple[float, float | None, str] | None = None  # done, total, text
        self.start = time.monotonic()
        self.elapsed = 0.0
        self.state = "run"  # run | ok | fail


class StepHandle:
    """What `with steps.step(...) as s:` gives you."""

    def __init__(self, owner: "Steps", step: _Step) -> None:
        self._owner, self._step = owner, step

    def detail(self, text: str) -> None:
        self._step.detail = text
        self._owner._refresh()

    def preview(self, text: str, lines: int = 3) -> None:
        """Show the tail of streaming text (e.g. an LLM writing) under the step."""
        tail = [l for l in text.replace("\r", "").split("\n") if l.strip()][-lines:]
        self._step.preview = tail
        self._owner._refresh()

    def progress(self, done: float, total: float | None, text: str = "") -> None:
        self._step.progress = (done, total, text)
        self._owner._refresh()


class Steps:
    """with Steps() as steps:
           with steps.step("🔎", "Finding requirements") as s:
               s.detail("11 must-haves")
    """

    def __init__(self) -> None:
        self._steps: list[_Step] = []
        self._live: Live | None = None

    def __enter__(self) -> "Steps":
        global _ACTIVE
        if animated() and _ACTIVE is None:
            self._live = Live(self, console=console, refresh_per_second=15, transient=False)
            self._live.__enter__()
        _ACTIVE = _ACTIVE or self
        return self

    def __exit__(self, *exc) -> None:
        global _ACTIVE
        if self._live is not None:
            self._live.__exit__(*exc)
            self._live = None
        if _ACTIVE is self:
            _ACTIVE = None

    @contextmanager
    def step(self, icon: str, label: str):
        st = _Step(icon, label)
        self._steps.append(st)
        self._refresh()
        try:
            yield StepHandle(self, st)
        except BaseException as e:
            st.state, st.elapsed = "fail", time.monotonic() - st.start
            if not st.detail:
                st.detail = str(e)[:80]
            self._finish(st)
            raise
        st.state, st.elapsed = "ok", time.monotonic() - st.start
        self._finish(st)

    def _finish(self, st: _Step) -> None:
        st.preview, st.progress = [], None
        if self._live is None:
            console.print(self._line(st))
        self._refresh()

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.refresh()

    def _line(self, st: _Step) -> Text:
        t = time.monotonic()
        if st.state == "run":
            mark = Spinner("dots", style="bold #00d7ff").render(t)
            label = shimmer(st.label, t)
            secs = t - st.start
        else:
            mark = Text("✓", style="bold green") if st.state == "ok" else Text("✗", style="bold red")
            label = Text(st.label, style="default" if st.state == "ok" else "red")
            secs = st.elapsed
        line = Text("  ").append_text(mark).append(f" {st.icon} ").append_text(label)
        if st.detail:
            line.append(f"  {st.detail}", style="dim")
        if secs >= 0.05 or st.state == "run":
            line.append(f"  {secs:.1f}s", style="dim #5f87ff")
        return line

    def __rich__(self):
        rows = []
        for st in self._steps:
            rows.append(self._line(st))
            if st.state == "run" and st.progress:
                done, total, text = st.progress
                grid = Table.grid(padding=(0, 1))
                grid.add_column(width=6)
                grid.add_column(width=min(40, max(10, console.width - 40)))
                grid.add_column()
                grid.add_row("", ProgressBar(total=total or None, completed=done, width=min(40, max(10, console.width - 40)),
                                             complete_style="#af5fff", finished_style="green", pulse_style="#5f87ff"),
                             Text(text, style="dim"))
                rows.append(grid)
            if st.state == "run" and st.preview:
                for p in st.preview:
                    t = Text("      │ ", style="dim #5f87ff").append(p, style="italic dim")
                    t.truncate(max(20, console.width - 2), overflow="ellipsis")
                    rows.append(t)
        return Group(*rows)


def active_steps() -> "Steps | None":
    return _ACTIVE


# --- download bar for libraries that use tqdm (LanguageTool) ---

class _TqdmToSteps:
    """Minimal tqdm stand-in that drives the current Steps progress bar."""

    def __init__(self, total=None, desc="", **_kw) -> None:
        self.total, self.n, self.desc = total, 0, desc
        self._t0 = time.monotonic()
        self._handle = _CURRENT_DOWNLOAD

    def update(self, n: int = 1) -> None:
        self.n += n
        if self._handle is None:
            return
        rate = self.n / max(0.001, time.monotonic() - self._t0)
        mb = lambda b: f"{b / 1e6:.0f} MB"
        text = f"{mb(self.n)}{' / ' + mb(self.total) if self.total else ''} · {rate / 1e6:.1f} MB/s"
        if self.total and rate > 0:
            text += f" · {max(0, (self.total - self.n) / rate):.0f}s left"
        self._handle.progress(self.n, self.total, text)

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


_CURRENT_DOWNLOAD: StepHandle | None = None


@contextmanager
def download_bar(handle: StepHandle):
    """Route LanguageTool's download progress into this step's bar."""
    global _CURRENT_DOWNLOAD
    import types

    try:
        from language_tool_python import download_lt
    except ImportError:
        yield
        return
    original = download_lt.tqdm
    _CURRENT_DOWNLOAD = handle
    download_lt.tqdm = types.SimpleNamespace(tqdm=_TqdmToSteps)
    try:
        yield
    finally:
        download_lt.tqdm = original
        _CURRENT_DOWNLOAD = None
