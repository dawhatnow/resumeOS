# Resume OS — career warehouse (M1)

A local CLI that turns resume PDFs into one warehouse — every job and
project you will stand behind, not just the last one-pager. Later milestones
will score that warehouse against a job posting and export a PDF. That is
not built yet.

## Try it

From the repo (uses the venv + fake resumes in `samples/`, does **not**
touch `~/.resume`):

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/write_sample_pdfs.py

export RESUME_HOME=/tmp/resume-m1-demo
resume import samples/swe.pdf -y
resume import --merge samples/ds.pdf -y
resume show
```

Your real warehouse is `~/.resume/profile.yaml`. Drop `RESUME_HOME` and
point `import` at your own PDFs.

```bash
resume import ~/Downloads/your.pdf -y
resume import --merge ~/Downloads/another.pdf -y
resume add experience
resume show
```

Technical guides (how it’s coded + which libs): `docs/milestones/`.
M1 is as-built; M2–M7 are the build plan. New work goes in new modules,
not `warehouse.py`.

Requires Python 3.11+. Windows / `file://` paths work under WSL.

## Tests

```bash
pytest tests/unit
```

## Layout

```
app/
  cli.py            import, merge, add, show
  warehouse.py      merge + typed add
  models.py         Profile / Item / Bullet
  store.py          ~/.resume/profile.yaml
  paths.py          pasted path → Path
  importing/        PDF → Profile
tests/unit/
docs/ARCHITECTURE.md
```
