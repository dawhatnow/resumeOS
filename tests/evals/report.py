"""Print what the matcher makes of postings, for checking by hand.

    python -m tests.evals.report                      # all postings
    python -m tests.evals.report tests/evals/postings/x.txt
"""

import glob, sys
from app.store import ProfileStore
from app.models import JobPosting
from app.analyzing.analyzer import JobAnalyzer
from app.planning.planner import ResumePlanner
p = ProfileStore().load()
files = sys.argv[1:] or sorted(glob.glob("tests/evals/postings/*.txt"))
for f in files:
    a = JobAnalyzer().analyze(JobPosting(url=f, source="file", raw_text=open(f).read()), p)
    plan = ResumePlanner().plan(a, p)
    print(f"\n=== {f.split('/')[-1]}")
    print("must   ", a.must_have); print("nice   ", a.nice_to_have)
    print("kw-only", [k for k in a.keywords if k not in a.must_have + a.nice_to_have]); print("missing", a.missing, " coverage", plan.coverage)
    for s in plan.selected: print(f"  {s.item_id:7} {s.score:5.1f} {s.reason}  {s.bullet_ids}")
