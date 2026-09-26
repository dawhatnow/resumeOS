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

## Make a resume for a job

Warehouse must already exist (`resume init`).

```bash
resume new https://jobs.lever.co/acme/…      # Greenhouse, Lever, Ashby, most career sites
resume new ./jd.txt
resume new -                                  # paste, then Enter
resume new <job> --rewrite                    # AI-tailor bullets (truth-checked; see M6.md)
```

Shows what the job asks for and your best-matching bullets, then **review**
(toggle / edit / `rewrite` / `check` / `style` / `preview`) and a one-page
PDF on your Desktop. Nothing reaches the PDF that your warehouse doesn't back.

```bash
resume ls                # every resume you've made
resume open 1            # back into review for that job
resume export 1          # that PDF onto the Desktop again
resume status 1 applied  # track it
resume check --fix       # proofread the warehouse
```

Optional extras: `pip install -e ".[grammar]"` (LanguageTool, needs Java),
`".[embeddings]"` (meaning-based matching). AI provider: `~/.resume/config.toml`.

Technical guides: `docs/milestones/` and `docs/ARCHITECTURE.md`.
Tests: `pytest` (unit + evals), `pytest -m network` (live job boards).
