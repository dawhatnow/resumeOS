"""Write samples/swe.pdf and samples/ds.pdf so M1 can be tried without a real resume."""

from pathlib import Path

SWE = """Jane Doe
jane.doe@example.com | 555-123-4567

Summary
Backend engineer focused on distributed systems.

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 - Present
- Rebuilt the billing pipeline in Go, cutting invoice-generation latency from 12s to 400ms for 50,000+ monthly customers.
- Led migration of the primary datastore from MySQL to PostgreSQL with zero downtime.

Projects
Task Queue § Code Python, Redis, Docker
- Built a distributed task queue supporting 10,000 jobs/sec.

Technical Skills
Python, Go, SQL, PostgreSQL

Education
State University
Bachelor of Science in Computer Science 2020
"""

DS = """Jane Doe
jane.doe@example.com

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 - Present
- Rebuilt the billing pipeline in Go, cutting invoice-generation latency from 12s to 400ms for 50,000+ monthly customers.
- Built a churn model in Python and pandas that flagged at-risk accounts.

Data Analyst @ Contoso Jan 2019 - May 2020
- Analyzed A/B tests in SQL and Python for 200,000 weekly users.

Projects
Churn Predictor § Code Python, pandas, scikit-learn
- Trained a classification model on 2 years of billing data.

Technical Skills
Python, pandas, SQL, scikit-learn
"""


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, text: str) -> None:
    ops = ["BT", "/F1 10 Tf", "50 760 Td"]
    for i, line in enumerate(text.splitlines()):
        if i:
            ops.append("0 -13 Td")
        ops.append(f"({_escape(line)}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_at = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "samples"
    write_pdf(root / "swe.pdf", SWE)
    write_pdf(root / "ds.pdf", DS)
    print(f"Wrote {root / 'swe.pdf'} and {root / 'ds.pdf'}")


if __name__ == "__main__":
    main()
