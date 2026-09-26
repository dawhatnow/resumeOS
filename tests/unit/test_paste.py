from app.paste import PASTE_END, PASTE_START, PasteBuffer

JD = "Data Analyst\n\nRequirements\n- SQL\n\n\nNice to have\n- Python\n"


def test_bracketed_paste_keeps_blank_lines_until_enter():
    buf = PasteBuffer()
    buf.feed(PASTE_START + JD[:10], gap=1.0)
    buf.feed(JD[10:] + PASTE_END, gap=0.0001)
    assert not buf.done
    buf.feed("\n", gap=0.5)
    assert buf.done
    assert buf.text == JD.strip()


def test_plain_paste_burst_does_not_submit_on_its_newlines():
    buf = PasteBuffer()
    for i in range(0, len(JD), 7):  # arrives in pieces, microseconds apart
        buf.feed(JD[i:i + 7], gap=0.0001)
    assert not buf.done
    buf.feed("\n", gap=0.4)
    assert buf.done and buf.text == JD.strip()


def test_lone_newline_inside_a_fast_burst_is_content():
    buf = PasteBuffer()
    buf.feed("line one", gap=1.0)
    buf.feed("\n", gap=0.0001)
    buf.feed("line two", gap=0.0001)
    assert not buf.done


def test_enter_on_empty_input_waits_and_ctrl_d_submits():
    buf = PasteBuffer()
    buf.feed("\n", gap=1.0)
    assert not buf.done
    buf.feed("https://example.com/job", gap=1.0)
    buf.feed("\x04", gap=0.5)
    assert buf.done and buf.text == "https://example.com/job"


def test_escape_split_across_reads_and_backspace():
    buf = PasteBuffer()
    buf.feed("\x1b[20", gap=1.0)
    buf.feed("0~abcx\x7f" + PASTE_END, gap=0.0001)
    assert buf.text == "abc"


def test_long_single_line_is_not_truncated():
    buf = PasteBuffer()
    buf.feed(PASTE_START + "x" * 30000 + PASTE_END, gap=1.0)
    buf.feed("\n", gap=0.5)
    assert len(buf.text) == 30000
