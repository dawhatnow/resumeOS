# Resume OS — career warehouse (M1)

A local CLI. One warehouse for every job and project you will stand behind.
Later: paste a job, get a truthful one-page PDF. That half is not built yet.

## How users run it (no GitHub clone)

They do **not** download the repo onto the desktop. They install the `resume`
command once, then type `resume init`.

```bash
# one-time (needs Python 3.11+)
pipx install resumeos          # after we publish to PyPI (M7)

# until PyPI is up, same idea from the repo URL — still no clone:
pipx install git+https://github.com/dawhatnow/resumeOS.git
```

Then anytime:

```bash
resume init
```

That starts the app: pick a resume PDF, optionally merge more (DS, PM, …),
done. Warehouse lives in `~/.resume/profile.yaml`.

```bash
resume                 # status
resume show
resume add experience
```

`pipx` puts `resume` on their PATH in an isolated env. Not a folder on the
Desktop.

## Dev (this repo)

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/write_sample_pdfs.py
export RESUME_HOME=/tmp/resume-m1-demo
resume init samples/swe.pdf
```

Technical guides: `docs/milestones/`. Tests: `pytest tests/unit`.
