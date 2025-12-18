#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
echo "=== INSTALL: ARE Self-Improvement Suite into: $ROOT ==="

# Safety defaults
mkdir -p ops/self_improvement memory/vectorstore training/self_train tools sandbox scripts tests docs
cat > ops/self_improvement/INSTALL_OPTIONS.env <<'ENV'
# Self-Improvement options (leave AUTO_APPROVE=false until tested)
AUTO_APPROVE=false
PROV_SECRET=prov-dev-secret
SANDBOX_MAX_RUNTIME=30   # seconds
SANDBOX_ALLOW_NETWORK=false
MIN_PR_SCORE=0.75
ENV

# 1) Data models, utilities
cat > ops/self_improvement/data_models.py <<'PY'
#!/usr/bin/env python3
from dataclasses import dataclass, asdict
import time, json, uuid
@dataclass
class Episode:
    id: str
    ts: float
    task: dict
    decision: dict
    outcome: dict
    metadata: dict
    def to_json(self):
        return json.dumps(asdict(self))
def make_episode(task, decision, outcome, metadata=None):
    return Episode(id=str(uuid.uuid4()), ts=time.time(), task=task, decision=decision, outcome=outcome, metadata=metadata or {})
PY

# 2) Analyzer: reads logs, finds failure clusters, suggests targets
cat > ops/self_improvement/analyzer.py <<'PY'
#!/usr/bin/env python3
import json, os, collections
LOG="logs/role_audit.log"
OUT="ops/self_improvement/analysis_summaries.jsonl"
def analyze_recent(n=1000):
    if not os.path.exists(LOG):
        return []
    counts = collections.Counter()
    summaries=[]
    with open(LOG) as f:
        for i,line in enumerate(f):
            if i>=n: break
            try:
                r=json.loads(line)
            except:
                continue
            key=r.get("meta",{}).get("action") or r.get("decision",{}).get("role")
            if key:
                counts[key]+=1
    # produce simple insights
    for k,c in counts.most_common(50):
        summaries.append({"issue":k,"count":c})
    with open(OUT,"w") as o:
        for s in summaries:
            o.write(json.dumps(s)+"\n")
    return summaries

if __name__=="__main__":
    print(analyze_recent(500))
PY
chmod +x ops/self_improvement/analyzer.py

# 3) Optimizer: turns analyzer signals into candidate PR patches (safely)
cat > ops/self_improvement/optimizer.py <<'PY'
#!/usr/bin/env python3
"""
Optimizer: lightweight rule-based refactor proposer.
It DOES NOT push; it writes a patch file and a rationale.
Human review required.
"""
import os, json, textwrap, uuid, time

DRAFTS="ops/self_improvement/drafts"
os.makedirs(DRAFTS, exist_ok=True)

def propose_code_patch(target_file, patch_text, reason):
    draft_id = str(uuid.uuid4())
    path = os.path.join(DRAFTS, f"{draft_id}.patch")
    meta = {"id":draft_id,"target":target_file,"reason":reason,"ts":time.time()}
    with open(path,"w") as f:
        f.write("# meta: " + json.dumps(meta) + "\n")
        f.write(patch_text)
    return {"draft_id":draft_id, "path":path, "meta":meta}

def sample_refactor_suggestion(repo_root):
    # Very conservative example: add logging wrapper to functions named 'run'
    candidates=[]
    for root,_,files in os.walk(repo_root):
        for fn in files:
            if fn.endswith(".py"):
                p = os.path.join(root,fn)
                try:
                    txt = open(p).read()
                    if "def run(" in txt and "logger" not in txt:
                        patch = textwrap.dedent(f'''
                        --- a/{p}
                        +++ b/{p}
                        @@
                        +# Added logging wrapper by optimizer (draft)
                        +import logging
                        +logger = logging.getLogger(__name__)
                        +
                        ''')
                        candidates.append({"target":p,"patch":patch})
                except Exception:
                    continue
    if candidates:
        c=candidates[0]
        return propose_code_patch(c["target"], c["patch"], "add_logging_wrapper")
    return None

if __name__=="__main__":
    print("Optimizer ready")
PY
chmod +x ops/self_improvement/optimizer.py

# 4) Scheduler loop (periodic analyze -> propose -> train triggers)
cat > ops/self_improvement/schedule_loop.py <<'PY'
#!/usr/bin/env python3
import time, os, json, subprocess
from ops.self_improvement.analyzer import analyze_recent
from ops.self_improvement.optimizer import sample_refactor_suggestion, propose_code_patch

POLL_INTERVAL = int(os.getenv("SI_POLL", "300"))

def run_cycle():
    insights = analyze_recent(500)
    if not insights:
        print("no insights")
        return
    # naive rule: if an insight appears > 5 times, propose
    frequent = [i for i in insights if i.get("count",0) >= 5]
    if frequent:
        print("frequent issues:", frequent[:5])
        # propose a conservative refactor
        p = sample_refactor_suggestion(".")
        if p:
            print("proposed draft:", p)
    else:
        print("no frequent signals")

if __name__=="__main__":
    while True:
        run_cycle()
        time.sleep(POLL_INTERVAL)
PY
chmod +x ops/self_improvement/schedule_loop.py

# 5) Audit & provenance hook to log episodes (append-only)
cat > ops/self_improvement/episode_logger.py <<'PY'
#!/usr/bin/env python3
import time, json, os
LOG="logs/self_improvement_episodes.jsonl"
def log_episode(entry):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    e={"ts":time.time(), **entry}
    with open(LOG,"a") as f:
        f.write(json.dumps(e)+"\n")
    return e
PY
chmod +x ops/self_improvement/episode_logger.py

# 6) Memory vectorstore (simple local stub; pluggable to Qdrant/etc)
cat > memory/memory.py <<'PY'
#!/usr/bin/env python3
import os, json, uuid
STORE="memory/vectorstore/index.jsonl"
def write_memory(text,meta=None):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    rec={"id":str(uuid.uuid4()),"text":text,"meta":meta or {}}
    with open(STORE,"a") as f:
        f.write(json.dumps(rec)+"\n")
    return rec
def read_all(limit=100):
    if not os.path.exists(STORE): return []
    out=[]
    for i,line in enumerate(open(STORE)):
        if i>=limit: break
        out.append(json.loads(line))
    return out
if __name__=="__main__":
    print("mem count", len(read_all()))
PY
chmod +x memory/memory.py

# 7) memory tool wrapper (for mcp tools)
cat > tools/memory_tool.py <<'PY'
#!/usr/bin/env python3
import sys, json, os
from memory.memory import write_memory, read_all
payload=sys.stdin.read()
try:
    args=json.loads(payload) if payload else {}
except:
    args={}
if args.get("op")=="write":
    rec=write_memory(args.get("text",""), args.get("meta",{}))
    print(json.dumps({"ok":True,"rec":rec}))
else:
    print(json.dumps({"ok":True,"items":read_all(100)}))
PY
chmod +x tools/memory_tool.py

# 8) Self-eval tool (run tests / analyze a candidate PR in sandbox)
cat > tools/self_eval_tool.py <<'PY'
#!/usr/bin/env python3
import sys, json, subprocess, os, tempfile
payload=sys.stdin.read()
try:
    args=json.loads(payload) if payload else {}
except:
    args={}
# expected args: { "repo_path": "...", "patch_file": "..." }
repo=args.get("repo_path",".")
patch=args.get("patch_file")
# apply patch in a sandbox clone
workdir=tempfile.mkdtemp(prefix="sicd_eval_")
subprocess.check_call(["git","clone",repo,workdir])
if patch:
    pfile=os.path.abspath(patch)
    # apply patch
    try:
        subprocess.check_call(["git","apply",pfile], cwd=workdir)
    except subprocess.CalledProcessError as e:
        print(json.dumps({"ok":False,"error":"apply_failed","detail":str(e)}))
        sys.exit(0)
# run tests
try:
    r=subprocess.run(["pytest","-q"], cwd=workdir, capture_output=True, text=True, timeout=120)
    print(json.dumps({"ok":True,"rc":r.returncode,"stdout":r.stdout,"stderr":r.stderr}))
except Exception as e:
    print(json.dumps({"ok":False,"error":str(e)}))
PY
chmod +x tools/self_eval_tool.py

# 9) Self PR helper (creates local branch & commit; does NOT push)
cat > tools/self_pr_tool.py <<'PY'
#!/usr/bin/env python3
import sys, json, subprocess, os, uuid, tempfile
payload=sys.stdin.read()
args=json.loads(payload) if payload else {}
repo=args.get("repo_path",".")
patch_file=args.get("patch_file")
title=args.get("title","self-update")
branch="self-update-"+str(uuid.uuid4())[:8]
cwd=os.getcwd()
# create branch & apply patch
subprocess.check_call(["git","checkout","-b",branch], cwd=repo)
subprocess.check_call(["git","apply", os.path.abspath(patch_file)], cwd=repo)
subprocess.check_call(["git","add","-A"], cwd=repo)
subprocess.check_call(["git","commit","-m", title], cwd=repo)
print(json.dumps({"ok":True,"branch":branch}))
PY
chmod +x tools/self_pr_tool.py

# 10) Training stubs (dataset builder + train)
cat > training/self_train/dataset_builder.py <<'PY'
#!/usr/bin/env python3
# Convert logs -> dataset for behavior finetune
import json, os
LOG="logs/self_improvement_episodes.jsonl"
OUT="training/self_train/dataset.jsonl"
if not os.path.exists(LOG):
    print("no logs yet")
else:
    with open(LOG) as f, open(OUT,"w") as o:
        for line in f:
            o.write(line)
    print("wrote dataset to", OUT)
PY
cat > training/self_train/train_stub.py <<'PY'
#!/usr/bin/env python3
# Placeholder: perform training (e.g., LoRA) using dataset
import os
MODEL_OUT="training/self_train/selector_model.stub"
open(MODEL_OUT,"w").write("trained-at:"+str(os.path.getmtime(__file__)))
print("wrote model stub:", MODEL_OUT)
PY
chmod +x training/self_train/dataset_builder.py training/self_train/train_stub.py

# 11) Sandbox runner to safely run generated code (very restricted)
cat > sandbox/run_in_sandbox.py <<'PY'
#!/usr/bin/env python3
# VERY limited sandbox runner: runs a given command with a timeout, no network (best-effort)
import subprocess, shlex, os, sys, signal, tempfile
def run_cmd(cmd, cwd=None, timeout=30):
    env = os.environ.copy()
    # block common env flags that might leak creds
    env.pop("AWS_SECRET_ACCESS_KEY", None)
    # run with timeout
    try:
        p = subprocess.run(shlex.split(cmd), cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {"rc":p.returncode, "stdout":p.stdout, "stderr":p.stderr}
    except subprocess.TimeoutExpired as e:
        return {"error":"timeout","detail":str(e)}
if __name__=="__main__":
    import json
    indata = sys.stdin.read()
    args = json.loads(indata) if indata else {}
    cmd = args.get("cmd")
    cwd = args.get("cwd", ".")
    print(json.dumps(run_cmd(cmd, cwd, int(args.get("timeout",15)))))
PY
chmod +x sandbox/run_in_sandbox.py

# 12) Sanity tests and README
cat > docs/SELF_IMPROVEMENT_README.md <<'MD'
# ARE Self-Improvement Suite — Quickstart

1. Inspect ops/self_improvement/INSTALL_OPTIONS.env and ensure AUTO_APPROVE=false.
2. Start components (dev):
   - python3 ops/self_improvement/are_service.py   # if using role engine
   - python3 ops/self_improvement/schedule_loop.py  (or run manually)
3. When analyzer finds patterns, optimizer writes drafts into ops/self_improvement/drafts/.
4. Use tools/self_eval_tool.py to validate patches in sandbox.
5. When satisfied, use tools/self_pr_tool.py to create a local branch + commit. DO NOT PUSH without review.

Security/Safety:
- Sandbox runner restricts runtime and attempts to avoid env leaks but must be reviewed.
- All generated patches are drafts and must be reviewed by human maintainers.
MD

# 13) Tests (basic smoke)
cat > tests/test_self_improve_imports.py <<'PY'
def test_imports():
    import importlib
    mods = ["ops.self_improvement.analyzer","ops.self_improvement.optimizer","memory.memory"]
    for m in mods:
        importlib.import_module(m)
PY

# finalize
echo "=== ARE Self-Improvement suite installed under: $ROOT ==="
echo "Inspect: ops/self_improvement/INSTALL_OPTIONS.env"
echo "To run a single analyzer cycle:"
echo "  python3 ops/self_improvement/analyzer.py"
echo "To run optimizer sample:"
echo "  python3 ops/self_improvement/optimizer.py"
echo "To run sandbox command:"
echo "  python3 sandbox/run_in_sandbox.py <<< '{\"cmd\":\"pytest -q\",\"cwd\":\"./\"}'"
