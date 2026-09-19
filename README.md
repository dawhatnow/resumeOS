# resumeOS — Resume Tailor CLI

A command-line tool that builds a reusable "career profile" from your existing
resume, and (eventually) tailors that profile into a one-page resume for a
specific job posting — without ever inventing a claim you didn't already make.

> **Status:** the import/parsing half of this tool is real and working today.
> The job-tailoring half (`resume new <url>`) is scaffolded with real
> interfaces but most stages are intentionally unimplemented stubs. See
> [Project status](#project-status) below for the honest breakdown, and
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it's all wired together.

## What it does today

```
$ resume
Creating a new resume...
Enter the path to your master resume (PDF): ~/Downloads/my_resume.pdf
Name: Jane Doe
Email: jane.doe@example.com
Phone: 555-123-4567
Links: https://linkedin.com/in/janedoe, https://github.com/janedoe
Summary: ...

Experience (4):
  [exp.1] Senior Backend Engineer @ Acme Corp (Jan 2023 – Present)
    - Rebuilt the billing pipeline in Go, cutting latency from 12s to 400ms...
  ...

Projects (5): ...
Education (1): ...
Skills: Python, Go, SQL, PostgreSQL, AWS, S3, ECS, ECR, ...

Saved profile to ~/.resume/profile.yaml
```

Point it at a PDF resume and it:
1. Extracts clean text from the PDF (handles a common PDF-extraction bug
   where spaces get dropped around styled/hyperlinked text).
2. Pulls out contact info — name, email, phone, and links (including
   clickable "LinkedIn"/"GitHub" link *annotations* that don't have a
   visible URL in the text).
3. Splits the resume into sections (Experience, Projects, Education,
   Skills, Awards, ...) and parses each into structured entries — every
   job/project becomes an `Item` with a stable ID, dates, tech list, and a
   list of `Bullet`s, each with *its own* ID, matched tech terms, and any
   numeric claims it makes.
4. Saves the result to `~/.resume/profile.yaml` — a durable, human-editable
   source of truth for the rest of the pipeline to read from later.

## The bigger idea (not yet built)

The long-term goal (see the original design spec, saved in project memory)
is `resume new <job-url>`: paste a job posting URL, and get back a
one-page PDF resume tailored to that posting — selecting and lightly
rewriting bullets from your profile to match the job's language, while a
pure-code **truth guard** guarantees nothing on the page is a claim your
profile doesn't already support. At most one LLM call per job, and zero
with `--no-rewrite`.

That pipeline's shape exists in code today (`app/pipeline.py` and friends)
but most of its stages raise `NotImplementedError` on purpose — see
[Project status](#project-status).

## Quickstart

```bash
# from the repo root
pip install -e ".[dev]"     # or: /path/to/venv/bin/pip install -e ".[dev]"
resume                       # prompts for a PDF path, builds your profile
```

Requires Python 3.11+ (uses `X | None` union syntax and `dataclasses`).

If you're on WSL and paste a Windows path (`C:\Users\...`) or a
`file://` URI copied from a browser/file explorer, it's handled
automatically — no need to convert it yourself.

## Running tests

```bash
pytest tests/unit                       # fast, deterministic, no network
pytest tests/integration -m network     # hits real live URLs — see below
```

The integration suite fetches real job postings and a few deliberately
broken URLs (404, unresolvable domain) to check error handling. It's
excluded from a plain `pytest` run since it needs internet access and
depends on third-party sites' HTML staying roughly stable.

## Project status

| Stage (per design spec) | Class | Status |
|---|---|---|
| Import (PDF → Profile) | `app.importing.ProfileImporter` and friends | ✅ Real, tested |
| Profile persistence | `app.store.ProfileStore` | ✅ Real, tested |
| Truth guard | `app.guard.TruthGuard` | 🟡 3 of 4 rules real; tech-term rule (`check_tech`) not yet implemented |
| Fetch (generic HTML) | `app.fetching.GenericFetcher` | ✅ Real, tested against live URLs |
| Fetch (Greenhouse/Lever/Ashby APIs) | `app.fetching.*` | ⬜ Stub — routing logic works, `.fetch()` raises `NotImplementedError` |
| Analyze (JD cleaning, keyword/embedding match) | `app.analyzing.*` | ⬜ Stub |
| Plan (scoring, selection) | `app.planning.*` | ⬜ Stub |
| Review (approve/edit UI) | `app.review.PlanReviewer` | ⬜ Stub |
| Write (the one LLM call) | `app.ai.*`, `app.ai.writer.ResumeWriter` | 🟡 Control flow (retry-then-fallback) is real; `NullProvider` (for `--no-rewrite`) is real; Ollama/Gemini providers are stubs |
| Render (Typst + fit loop) | `app.render.ResumeRenderer` | ⬜ Stub |
| Orchestration | `app.pipeline.ResumePipeline` | ✅ Wires all of the above in order — will raise on the first unbuilt stage it reaches, which is expected |

**Why ship stubs instead of waiting?** Each stage is a real class with a
real interface (often an abstract base class) today, so the shape of the
whole system is visible and testable now, and each stage can be filled in
independently later without touching the others. A stub always raises
`NotImplementedError` rather than silently doing nothing — if you see that
exception, it's telling you the truth about what's missing.

## Project structure

```
app/
  models.py        data models shared across every stage
  paths.py          resolves pasted paths (file://, Windows, ~) to a real Path
  importing/        PDF → Profile (the fully-working half of the tool)
  guard.py          truth checks that gate what can reach a rendered resume
  store.py          persists the profile to ~/.resume/profile.yaml
  ai/               swappable LLM provider interface + the Write stage
  fetching/         job posting fetchers (per job board) + routing
  analyzing/        JD cleaning + keyword/embedding matching (stub)
  planning/         bullet scoring + selection (stub)
  review.py         plan approval UI (stub)
  render.py         PDF rendering + one-page fit loop (stub)
  pipeline.py       orchestrates all of the above for `resume new <url>`
  cli.py            Typer commands — thin, no business logic
tests/
  unit/             fast, deterministic
  integration/      live-network tests (opt-in via -m network)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how each piece works,
the design patterns used, and how to extend it (add a new job-board
fetcher, a new AI provider, etc.).
