"""Read a pasted job description from the terminal.

Line-by-line prompts can't take a real JD: its blank lines ended input early
(the rest leaked into the shell or the next prompt), and the tty's line
buffer silently cut lines past 4095 chars. This reads raw input instead:

- Bracketed paste (Windows Terminal, VS Code, most modern terminals) marks
  where a paste starts and ends, so newlines inside it never submit.
- Without it, a paste still arrives as one burst; a newline that arrives on
  its own, after a pause, is the user pressing Enter.
- Enter submits once there's text. Ctrl-D submits too. Piped stdin is read whole.
"""

import os
import re
import sys

PASTE_START = "\x1b[200~"
PASTE_END = "\x1b[201~"
# Key presses are tens of ms apart; chunks of one paste arrive sub-millisecond.
ENTER_GAP = 0.03
_OTHER_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z~]|\x1b[^\[]")


class PasteBuffer:
    """Terminal-independent state machine; fed raw chunks as they arrive."""

    def __init__(self) -> None:
        self._chars: list[str] = []
        self._pending = ""  # partial escape sequence split across reads
        self._in_paste = False
        self.done = False

    @property
    def text(self) -> str:
        return "".join(self._chars).strip()

    def feed(self, chunk: str, gap: float = 0.0) -> str:
        """Consume a chunk read `gap` seconds after the previous one.
        Returns what to echo."""
        data = self._pending + chunk.replace("\r\n", "\n").replace("\r", "\n")
        self._pending = ""
        echo: list[str] = []
        i = 0
        while i < len(data) and not self.done:
            if data.startswith(PASTE_START, i):
                self._in_paste = True
                i += len(PASTE_START)
                continue
            if data.startswith(PASTE_END, i):
                self._in_paste = False
                i += len(PASTE_END)
                continue
            ch = data[i]
            if ch == "\x1b":
                m = _OTHER_ESCAPE.match(data, i)
                if m is None:  # incomplete; wait for the rest
                    self._pending = data[i:]
                    break
                i = m.end()  # arrow keys etc.: ignore
                continue
            i += 1
            if ch == "\x04":  # Ctrl-D
                self.done = True
            elif ch in "\x7f\x08":
                if self._chars and self._chars[-1] != "\n":
                    self._chars.pop()
                    echo.append("\b \b")
            elif ch == "\n" and self._is_enter(gap, data):
                if self.text:
                    self.done = True
                echo.append("\n")
            elif ch == "\n" or ch == "\t" or ch >= " ":
                self._chars.append(ch)
                echo.append(ch)
        return "".join(echo)

    def _is_enter(self, gap: float, data: str) -> bool:
        """A newline read on its own, after a pause, is the Enter key. Paste
        bursts arrive as big chunks microseconds apart."""
        return not self._in_paste and data == "\n" and gap >= ENTER_GAP


def read_paste(*, whole_pipe: bool = True) -> str:
    """Block until the user submits a paste. Returns stripped text ("" if none).

    Piped stdin: read to EOF (`resume new - < jd.txt`), or with
    whole_pipe=False up to the first blank line, leaving the rest for later
    prompts (scripted `resume init` sessions).
    """
    if not sys.stdin.isatty():
        if whole_pipe:
            return sys.stdin.read().strip()
        return _read_lines_until(lambda line: not line.strip())
    try:
        import termios
    except ImportError:  # Windows without WSL: fall back to lines until "END"
        return _read_lines_until(lambda line: line.strip() == "END")
    return _read_tty(termios)


def _read_tty(termios) -> str:
    import select
    import time

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    raw = termios.tcgetattr(fd)
    raw[3] &= ~(termios.ICANON | termios.ECHO)  # no line buffer, we echo
    raw[6][termios.VMIN] = 1
    raw[6][termios.VTIME] = 0
    out = sys.stdout
    buf = PasteBuffer()
    try:
        termios.tcsetattr(fd, termios.TCSANOW, raw)
        out.write("\x1b[?2004h")  # enable bracketed paste
        out.flush()
        last = time.monotonic()
        while not buf.done:
            select.select([fd], [], [])
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            now = time.monotonic()
            echo = buf.feed(chunk.decode("utf-8", errors="replace"), gap=now - last)
            last = now
            if echo:
                out.write(echo)
                out.flush()
    finally:
        out.write("\x1b[?2004l")
        out.flush()
        termios.tcsetattr(fd, termios.TCSANOW, saved)
        # Drop anything typed/pasted after submit so it can't hit the next prompt.
        termios.tcflush(fd, termios.TCIFLUSH)
    out.write("\n")
    return buf.text


def _read_lines_until(stop) -> str:
    lines: list[str] = []
    for line in iter(sys.stdin.readline, ""):
        if lines and stop(line):
            break
        lines.append(line.rstrip("\n"))
    return "\n".join(lines).strip()
