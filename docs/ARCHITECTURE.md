# Architecture

resumeOS turns a job posting into a truthful, tailored, one-page resume PDF,
locally and for $0. Two halves:

- **Warehouse (M1):** every resume you've written, merged into
  `~/.resume/profile.yaml`. Inventory, never invented.
- **Compile (M2, M3, M6):** job posting → match → review → (optional AI
  rewrite) → truth guard → Typst PDF.

```
resume new <url|file|->
  JobSourceRouter ─► JobAnalyzer ─► ResumePlanner ─► print_plan
  (fetch/paste)      (clean, terms)  (score, pick)      │
                                                        ▼
  PDF ◄─ ResumeRenderer ◄─ PlanReviewer ◄─── "build the PDF?"
  (Typst, fit loop)        (toggle/edit/rewrite/check)
                               │   every edit / rewrite
                               └─► TruthGuard (+ Proofreader before build)
```

## Principles

1. **The one-pager is an output. The profile is inventory.** Import is the
   on-ramp, not the ceiling. `--merge` unions another PDF; it does not
   replace.
2. **User-authored text is truth.** Import and `resume add` write what the
   user already wrote. Nothing invents jobs or bullets.
3. **Small classes.** Import is a facade over parsers. Merge/add live in
   `app/warehouse.py`. The CLI does not contain merge logic.

## Warehouse flow (M1)

```
PDF ──► ProfileImporter ──► Profile
                                │
                    ProfileMerger (optional)
                                │
                         ProfileStore
                          ~/.resume/profile.yaml
```

`resume import` writes a new warehouse. `resume import --merge` loads the
existing one, unions the incoming PDF, prints a report, then saves.
`resume add` appends a job, project, or bullet. `resume show` prints IDs
and counts.

## Merge rules (`app/warehouse.py`)

- Same job/project = same title + org (case-insensitive). Keep existing
  IDs. Union bullets; skip duplicate text. Mint `exp.1.N` only for new
  lines.
- New job/project = append with the next `exp.N` / `proj.N`.
- Skills, links, education details = union. Personal blanks fill from the
  incoming PDF. Existing summary wins.
- Vocabulary is rebuilt after every merge/add.

## Import (`app/importing/`)

`ProfileImporter` is a facade over:

1. **`PdfTextExtractor`** — `pdfplumber` with `x_tolerance=0.5`. Default
   tolerance (and pypdf) drop spaces around styled/hyperlinked spans.
2. **`LinkAnnotationExtractor`** — PDF `/Annots` URIs, because "LinkedIn"
   often has no visible URL.
3. **`ContactInfoParser`** — email/phone/URLs; first non-blank line as name.
4. **`SectionSplitter`** — heading aliases. Text before the first heading
   is `"header"`.
5. **`ExperienceItemParser` / `ProjectItemParser`** — see below.
6. **`SkillsParser`** — category lines + `AWS(S3, ECS, ECR)` expansion.
7. **`EducationParser`** — school, degree+date, detail bullets.
8. **`VocabularyBuilder` / `BulletTechTagger`** — declared tech union;
   tag bullets with terms they actually mention (longest first).

### Continuation-aware item parsing

A wrapped bullet looks like a new header if you treat every non-bullet
line as a new item. That turned 4 jobs into 19. A non-bullet line starts
a new item only on a **positive header signal**; otherwise it folds onto
the previous bullet or `location`.

- Experience header: `Title @ Org May 2026 – Aug 2026`
- Project header: title + link label + tech list, e.g.
  `My Project § Code Python, PyTorch, AWS`. Resumes without that tech-list
  format still collapse projects into one item — known limit.

### Skills: match category labels at line start

Joining the whole skills section and splitting on `Category:` ate the last
skill when it touched the next label (`Golang\nFrameworks` → dropped
Golang). Category labels are only recognized at the start of a physical
line.

## Persistence

`ProfileStore` writes dataclasses through PyYAML and rebuilds nested
objects on load. Path is `~/.resume/profile.yaml`.

`ResumePathResolver` accepts `~`, quotes, `file://`, and Windows paths
under WSL.

## M5 — fetch (`app/fetching/`)

Greenhouse / Lever / Ashby public APIs (no keys), then JSON-LD `JobPosting`
or page text for any other site; JS-only pages ask you to paste. See M5.md.

## M2 — match (`app/analyzing/`, `app/planning/`)

- `TermIndex` (`terms.py`): built-in tech lexicon + your vocabulary + your
  `~/.resume/vocab/aliases.yaml`, all resolved to canonical keys. Longest
  match first with span masking (C++ never also counts as C). Case rules
  for Go/C/R/REST. `IMPLIES`: PostgreSQL counts as SQL, PyTorch as ML.
- `KeywordMatcher`: JD sections (Requirements / Nice to have / Benefits…)
  → must / nice / keywords, plus either/or groups ("Tableau, Power BI, or
  similar"). Degree lines are skipped.
- `BulletScorer` / `ResumePlanner`: 3 / 2 / 1 per unique term per item,
  bullets ranked by their own text; top 3 jobs, 3 projects, 4 bullets.
- `SemanticMatcher` (`semantic.py`, optional `[embeddings]` extra): local
  bge-small via fastembed/ONNX. Bullets close in meaning to a JD
  requirement line get up to +2 (a keyword must-have is +3). Ranks only —
  coverage stays keyword-based because that's what an ATS sees.
- Evals on real postings: `tests/evals/` (see M2.md).

## M3 — review + PDF (`app/review.py`, `app/guard.py`, `app/render.py`)

- **Review** works on a copy of the plan; edits live in `plan.edits` and are
  never written to the warehouse.
- **TruthGuard** — `check_bullet` (your edits): no new numbers, no tech the
  bullet's own job/project doesn't back, length cap. `check_rewrite` (AI):
  the same, plus no dropped numbers or job keywords.
- **Renderer** — data goes to `templates/resume.typ` as JSON (never parsed
  as markup), Typst's embedded fonts only. Fit loop: font step → drop the
  lowest-scoring bullet → refill what fits. Output to the Windows Desktop
  under WSL.

## M6 — AI rewrite (`app/ai/`)

`load_provider()` reads `~/.resume/config.toml`; one `OpenAICompatibleProvider`
covers Ollama (default), Groq, Gemini, OpenRouter. Keys only from env vars.
`BulletWriter`: cache → one batched call → guard → one retry with reasons →
original. Accepted answers are cached in `~/.resume/cache/rewrites/` and
re-verified on reuse.

## Proofreading (`app/proofread.py`)

Style rules in plain code (weak openers, first person, placeholders, tense,
repeated verbs) + spelling/grammar from LanguageTool (optional
`[grammar]` extra, local, en-CA) or an offline word list. Tech names,
acronyms, your vocabulary and `~/.resume/dictionary.txt` are never typos.

## Storage — everything under `~/.resume/`

| Path | What |
|---|---|
| `profile.yaml` | the warehouse |
| `config.toml` | `[llm]` provider/model, `[proofread]` engine |
| `vocab/aliases.yaml` | your extra terms/aliases for matching |
| `dictionary.txt` | words the proofreader accepts |
| `cache/rewrites/` | AI rewrites, keyed on model + bullet + job wording |
| `cache/languagetool/` | LanguageTool download (grammar extra) |
| `cache/embeddings/` | embedding model + cached bullet vectors (embeddings extra) |

`RESUME_HOME` moves all of it (tests use this).

## Decisions (where the code differs from the original spec on purpose)

- **Review uses typed commands, not checkboxes.** `exp.2.3` toggles,
  `edit`/`rewrite`/`check` act on ids you can see — faster from the
  keyboard than a checkbox list of 30 bullets, and scriptable in tests.
- **Dataclasses, not Pydantic.** Stage boundaries are still typed models in
  `app/models.py`; nothing crosses a process or network boundary that
  would need Pydantic's validation. Revisit if a stage starts reading
  untrusted JSON (the AI writer parses its own, defensively).
- **Typst via the pip package**, not the CLI binary: one install step.
- **LanguageTool is optional** so the base install stays light for PyPI.
- **fastembed instead of sentence-transformers** for embeddings: same idea,
  ONNX instead of PyTorch (~70 MB vs 700 MB+), optional extra.

## Tests

`tests/unit/` (import regressions, merge/add, store, CLI, matcher, guard,
renderer, review, AI writer, proofreader — isolated `RESUME_HOME` via
`conftest.py`) and `tests/evals/`
(real postings; warehouse-side checks run against your own warehouse,
including the spec targets: one page, nothing invented).
