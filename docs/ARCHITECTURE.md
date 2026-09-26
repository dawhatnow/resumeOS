# Architecture

M1 is a local warehouse. PDF in, `~/.resume/profile.yaml` out. Merge and
typed add grow that file. Apply/PDF is not in this tree yet.

## Principles

1. **The one-pager is an output. The profile is inventory.** Import is the
   on-ramp, not the ceiling. `--merge` unions another PDF; it does not
   replace.
2. **User-authored text is truth.** Import and `resume add` write what the
   user already wrote. Nothing invents jobs or bullets.
3. **Small classes.** Import is a facade over parsers. Merge/add live in
   `app/warehouse.py`. The CLI does not contain merge logic.

## Flow

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

## Tests

`tests/unit/` — import regressions, merge/add, store round-trip, path
resolution, CLI (`show`, `add`, merge-without-warehouse).

## M2 — apply (added; M1 above is unchanged)

`resume new` → `JobMatcher` (`app/apply.py`): fetch/clean JD, keyword-match
the warehouse, print a top-N plan. Always prints; coverage is not a gate.
See `docs/milestones/M2.md`.
