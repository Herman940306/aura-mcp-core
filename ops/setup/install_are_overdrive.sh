#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
echo "=== INSTALL: ARE+ OVERDRIVE into: $ROOT ==="

# ensure dos2unix not required; create with unix endings
mkdir -p ops/role_engine ops/opa/policies mcp/roles mcp/server training/roles training/ml ops/approvals scripts logs model_artifacts observability tests simulator docs

# ---------------------------
# 0) Safety & ENV defaults
# ---------------------------
cat > ops/role_engine/INSTALL_OPTIONS.env <<'ENV'
# ARE+ Installer options (edit before enabling auto)
AUTO_APPROVE=false
JWT_SECRET=dev-secret
OPA_URL=http://opa:8181
FORBIDDEN_ROLE_PREFIXES=hack,illegal,bio
MAX_AUTOGEN_RISK=0.6
ENV

# ---------------------------
# 1) Enhanced Role Registry (versioned)
# ---------------------------
cat > ops/role_engine/role_registry_v2.json <<'JSON'
{
  "meta": {
    "version": "2.0.0",
    "created_by": "installer_overdrive",
    "created_at": "$(date -Iseconds)"
  },
  "roles": {
    "Lead Engineer": { "purpose":"Automation & infra changes", "capabilities":["orchestrate","apply_pr","run_infra"], "scoring_profile":{"priority":9,"confidence_weight":0.9,"risk_factor":0.9} },
    "Senior Architect": { "purpose":"Architecture & strategy", "capabilities":["design","review_arch"], "scoring_profile":{"priority":9,"confidence_weight":0.85,"risk_factor":0.8} },
    "Full-Stack Guru": { "purpose":"Code, integration, merge","capabilities":["code","merge","debug"], "scoring_profile":{"priority":8,"confidence_weight":0.9,"risk_factor":0.9} },
    "Researcher": { "purpose":"RAG & analysis","capabilities":["query","upsert_memory"], "scoring_profile":{"priority":4,"confidence_weight":0.5,"risk_factor":0.2} },
    "Security Officer": { "purpose":"Security & compliance","capabilities":["approve_security","block_action"], "scoring_profile":{"priority":10,"confidence_weight":0.95,"risk_factor":1.0} },
    "Product Owner": { "purpose":"Requirements & acceptance","capabilities":["prioritize","acceptance"], "scoring_profile":{"priority":7,"confidence_weight":0.6,"risk_factor":0.6} },
    "Knowledge Curator": { "purpose":"Docs & memory","capabilities":["doc_update","memory_curation"], "scoring_profile":{"priority":3,"confidence_weight":0.4,"risk_factor":0.1} },
    "Coordinator": { "purpose":"Multi-agent coordination","capabilities":["route","delegate"], "scoring_profile":{"priority":6,"confidence_weight":0.6,"risk_factor":0.5} },
    "UX Designer": { "purpose":"UX & formatting","capabilities":["format","ux_improve"], "scoring_profile":{"priority":2,"confidence_weight":0.3,"risk_factor":0.1} }
  }
}
JSON

# ---------------------------
# 2) Role Schema (strict)
# ---------------------------
cat > ops/role_engine/role_schema.json <<'JSON'
{
  "$schema":"http://json-schema.org/draft-07/schema#",
  "title":"ARE Role Definition Schema",
  "type":"object",
  "required":["name","purpose","responsibilities","scoring_profile","version"],
  "properties":{
    "name":{"type":"string"},
    "purpose":{"type":"string"},
    "responsibilities":{"type":"array","items":{"type":"string"}},
    "behaviors":{"type":"array","items":{"type":"string"}},
    "interactions":{"type":"array","items":{"type":"string"}},
    "scoring_profile":{
      "type":"object",
      "properties":{
        "priority":{"type":"integer","minimum":1,"maximum":10},
        "confidence_weight":{"type":"number","minimum":0.0,"maximum":1.0},
        "risk_factor":{"type":"number","minimum":0.0,"maximum":1.0}
      },
      "required":["priority","confidence_weight","risk_factor"]
    },
    "version":{"type":"string"}
  }
}
JSON

# ---------------------------
# 3) ARE Core Service (FastAPI) - advanced (role manager + evolver + proposer)
# ---------------------------
cat > ops/role_engine/are_service.py <<'PY'
#!/usr/bin/env python3
"""
ARE Service - Autonomous Role Engine (overdrive)
Provides:
 - /roles GET/POST/PUT (versioned)
 - /propose POST (auto-propose role modifications)
 - /evaluate POST (role selection candidates)
 - /simulate POST (simulate role behavior in sandbox)
Safety: changes default to draft; AUTO_APPROVE env controls auto-commit.
"""
import os, json, time, uuid, tempfile, subprocess
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from jsonschema import validate, ValidationError

REG_FILE = "ops/role_engine/role_registry_v2.json"
SCHEMA_FILE = "ops/role_engine/role_schema.json"
DRAFTS_DIR = "ops/role_engine/drafts"
SIM_DIR = "simulator"
AUTO_APPROVE = os.getenv("AUTO_APPROVE","false").lower() == "true"
FORBIDDEN_PREFIXES = os.getenv("FORBIDDEN_ROLE_PREFIXES","").split(",")
MAX_AUTOGEN_RISK = float(os.getenv("MAX_AUTOGEN_RISK","0.6"))

app = FastAPI(title="ARE+ Service")

def load_registry():
    return json.load(open(REG_FILE))

def save_registry(obj):
    with open(REG_FILE,"w") as f:
        json.dump(obj,f,indent=2)

class RoleSpec(BaseModel):
    name: str
    purpose: str
    responsibilities: list
    behaviors: list = []
    interactions: list = []
    scoring_profile: dict
    version: str

@app.get("/roles")
def list_roles():
    return load_registry()

@app.post("/roles")
def create_role(spec: RoleSpec):
    # validate schema
    try:
        schema = json.load(open(SCHEMA_FILE))
        validate(instance=spec.dict(), schema=schema)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # safety: forbidden prefixes
    for p in FORBIDDEN_PREFIXES:
        if spec.name.lower().startswith(p.lower()):
            raise HTTPException(status_code=403, detail="forbidden role name prefix")
    # store as draft
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    draft_id = str(uuid.uuid4())
    draft_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    draft = {"id": draft_id, "spec": spec.dict(), "meta":{"ts":time.time(),"status":"draft"}}
    open(draft_path,"w").write(json.dumps(draft,indent=2))
    # auto-approve if env allows and risk low
    risk = spec.scoring_profile.get("risk_factor",0.5)
    if AUTO_APPROVE and risk <= MAX_AUTOGEN_RISK:
        reg = load_registry()
        reg["roles"][spec.name] = spec.dict()
        reg["meta"]["last_updated"] = time.time()
        save_registry(reg)
        draft["meta"]["status"] = "committed"
        open(draft_path,"w").write(json.dumps(draft,indent=2))
        return {"ok":True,"committed":True,"role":spec.name}
    return {"ok":True,"draft_id":draft_id,"committed":False}

@app.post("/propose")
def propose_role_change(payload: dict = Body(...)):
    """
    payload: {
      "reason":"text",
      "evidence":[...], // logs or patterns
      "proposal": { RoleSpec }
    }
    This endpoint uses heuristics to propose role edits.
    """
    proposal = payload.get("proposal")
    if not proposal:
        raise HTTPException(status_code=400, detail="missing proposal")
    # basic risk heuristics: if proposal increases risk over threshold, mark high-risk
    risk = proposal.get("scoring_profile",{}).get("risk_factor",0.5)
    draft_id = str(uuid.uuid4())
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    draft_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    draft = {"id":draft_id,"proposal":proposal,"reason":payload.get("reason"),"evidence":payload.get("evidence",[]),"meta":{"ts":time.time(),"risk":risk,"status":"proposed"}}
    open(draft_path,"w").write(json.dumps(draft,indent=2))
    return {"ok":True,"draft_id":draft_id,"risk":risk}

@app.post("/evaluate")
def evaluate_task(task: dict = Body(...)):
    """
    Expect: {"task":"text","context":{...},"topk":3}
    Returns scored candidate roles (heuristic + model hook)
    """
    task_text = task.get("task","").lower()
    reg = load_registry()["roles"]
    candidates = []
    for name,spec in reg.items():
        score = 0.0
        # match keywords in purpose/responsibilities
        txt = (spec.get("purpose","")+" "+ " ".join(spec.get("responsibilities",[]))).lower()
        for w in set(task_text.split()):
            if len(w)>2 and w in txt: score += 1.0
        # boost with priority
        p = spec.get("scoring_profile",{}).get("priority",5)
        score = score * (p/10.0)
        candidates.append({"role":name,"score":score,"priority":p})
    candidates = sorted(candidates, key=lambda x:x["score"], reverse=True)
    # return topk
    return {"candidates":candidates[:task.get("topk",3)], "meta":{"task":task_text}}

@app.post("/simulate")
def simulate_role(role_name: str = Body(...), scenario: dict = Body(...)):
    """
    Run an isolated simulation of what role would do (sandbox stub).
    This writes to simulator/ and returns a synthetic verdict.
    """
    sim_id = str(uuid.uuid4())
    sim_path = os.path.join(SIM_DIR, sim_id + ".json")
    # naive simulation: score how many keywords match
    content = scenario.get("text","")
    reg = load_registry()["roles"]
    spec = reg.get(role_name)
    if not spec:
        raise HTTPException(status_code=404, detail="role not found")
    score = 0
    for r in spec.get("responsibilities",[]):
        for w in r.split():
            if w.lower() in content.lower():
                score += 1
    verdict = {"role":role_name,"sim_score":score,"ok": score>0}
    open(sim_path,"w").write(json.dumps({"id":sim_id,"verdict":verdict,"ts":time.time()},indent=2))
    return {"sim_id":sim_id,"verdict":verdict}

# run with: uvicorn ops.role_engine.are_service:app --host 0.0.0.0 --port 9206
PY
chmod +x ops/role_engine/are_service.py

# ---------------------------
# 4) Advanced Role Selector (ML-ready) + Confidence
# ---------------------------
cat > mcp/roles/selector_advanced.py <<'PY'
#!/usr/bin/env python3
"""
Advanced role selector:
 - loads registry
 - uses heuristics + placeholder ML model
 - returns roles with confidence and explanation
"""
import json, os, math
REG="ops/role_engine/role_registry_v2.json"
MODEL_STUB="training/roles/selector_model.stub"

def load_registry():
    return json.load(open(REG))["roles"]

def pseudo_model_score(text, role_spec):
    # placeholder: TF-like scoring: keyword overlap / length normalization
    score=0.0
    txt = (role_spec.get("purpose","")+" "+ " ".join(role_spec.get("responsibilities",[]))).lower()
    for tok in set(text.lower().split()):
        if len(tok)>3 and tok in txt:
            score += 1.0
    # scale by priority
    p = role_spec.get("scoring_profile",{}).get("priority",5)
    return score * (p/10.0)

def calibrate_confidence(raw_score):
    # simple sigmoid to [0,1]
    return 1.0/(1.0+math.exp(-raw_score+1.0))

def select_roles(task_text, topk=3):
    reg=load_registry()
    cand=[]
    for name, spec in reg.items():
        raw = pseudo_model_score(task_text, spec)
        conf = calibrate_confidence(raw)
        cand.append({"role":name,"raw_score":raw,"confidence":conf,"explain":[f"raw:{raw:.2f}","priority:{spec.get('scoring_profile',{}).get('priority',5)}"]})
    cand=sorted(cand,key=lambda x:x["confidence"], reverse=True)
    return cand[:topk]

if __name__=="__main__":
    import sys, json
    t=" ".join(sys.argv[1:]) or "run unit tests and propose patch"
    print(json.dumps(select_roles(t,3), indent=2))
PY
chmod +x mcp/roles/selector_advanced.py

# ---------------------------
# 5) Role Negotiator & Voting (arbitration with confidence)
# ---------------------------
cat > mcp/roles/negotiator_advanced.py <<'PY'
#!/usr/bin/env python3
"""
Negotiator: accepts multiple role opinions and decides:
 - Accept top if confidence > threshold
 - If tied/low confidence -> escalate to Coordinator / human
 - Supports weighted voting
"""
def arbitrate(opinions, threshold=0.7):
    # opinions: [{"role":"X","confidence":0.8, "actor":"agent-A"},...]
    opinions_sorted = sorted(opinions,key=lambda x:x["confidence"], reverse=True)
    top = opinions_sorted[0]
    if top["confidence"] >= threshold:
        return {"decision":"accept","role":top["role"],"confidence":top["confidence"]}
    # check weighted votes
    votes={}
    for o in opinions:
        votes[o["role"]] = votes.get(o["role"],0.0) + o["confidence"]
    winner = max(votes.items(), key=lambda x:x[1])
    # if winner weight strong enough
    if winner[1] >= threshold:
        return {"decision":"voted","role":winner[0],"weight":winner[1]}
    return {"decision":"escalate","to":"Coordinator","votes":votes}
PY
chmod +x mcp/roles/negotiator_advanced.py

# ---------------------------
# 6) Role Evolver (genetics-like basic prototype)
# ---------------------------
cat > ops/role_engine/evolver.py <<'PY'
#!/usr/bin/env python3
"""
Role Evolver - prototype:
 - takes audit logs and proposals
 - proposes variations (mutations) to existing roles
 - writes drafts to drafts/
This is intentionally conservative: proposals are drafted, not auto-committed.
"""
import json, os, random, time, copy, uuid
REG="ops/role_engine/role_registry_v2.json"
DRAFTS="ops/role_engine/drafts"
LOGS="logs/role_audit.log"

def load_roles():
    return json.load(open(REG))["roles"]

def sample_mutation(role):
    spec = copy.deepcopy(role)
    # mutate priority slightly
    p = spec.get("scoring_profile",{}).get("priority",5)
    newp = max(1, min(10, p + random.choice([-1,0,1])))
    spec["scoring_profile"]["priority"] = newp
    spec["version"] = spec.get("version","1.0.0") + ".mut"+str(int(time.time()))
    return spec

def propose_mutations(n=2):
    roles = load_roles()
    os.makedirs(DRAFTS, exist_ok=True)
    proposals=[]
    for i in range(n):
        name = random.choice(list(roles.keys()))
        mutated = sample_mutation(roles[name])
        draft_id = str(uuid.uuid4())
        draft = {"id":draft_id,"original":name,"proposal":mutated,"meta":{"ts":time.time()}}
        path = os.path.join(DRAFTS, draft_id+".json")
        open(path,"w").write(json.dumps(draft,indent=2))
        proposals.append(draft)
    return proposals

if __name__=="__main__":
    print(propose_mutations(3))
PY
chmod +x ops/role_engine/evolver.py

# ---------------------------
# 7) Audit + Provenance (append-only + HMAC stub)
# ---------------------------
cat > ops/role_engine/audit_provenance.py <<'PY'
#!/usr/bin/env python3
import os, json, time, hmac, hashlib
AUDIT_LOG="logs/role_provenance.log"
SECRET=os.getenv("PROV_SECRET","prov-dev-secret")
def append_event(evt: dict):
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    evt_with_ts = {"ts":time.time(), **evt}
    raw = json.dumps(evt_with_ts, separators=(',',':'))
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    record = {"entry": evt_with_ts, "sig": sig}
    open(AUDIT_LOG,"a").write(json.dumps(record)+"\\n")
    return record
PY
chmod +x ops/role_engine/audit_provenance.py

# ---------------------------
# 8) OPA policies (advanced) + harness
# ---------------------------
cat > ops/opa/policies/role_policy_full.rego <<'REGO'
package mcp.authz

default allow = false

# action call: {"action":"call_tool","roles":["..."], "tool_required":["R1","R2"], "actor":"agent-x","risk":0.3}

allow {
  input.action == "call_tool"
  not forbidden_role_prefix(input.roles)
  some r
  r := input.roles[_]
  input.tool_required[_] == r
}

forbidden_role_prefix(roles) {
  some i
  p := input.forbidden_prefixes[_]
  roles[i] == rp
  startswith(lower(rp), lower(p))
}
REGO

cat > ops/opa/test_harness.sh <<'SH'
#!/usr/bin/env bash
set -e
echo "OPA policy harness: linting policy"
docker run --rm -v $(pwd)/ops/opa/policies:/policies openpolicyagent/opa:0.51.2 test /policies
SH
chmod +x ops/opa/test_harness.sh

# ---------------------------
# 9) Observability / tracing skeleton
# ---------------------------
cat > observability/otel_config.py <<'PY'
# Placeholder OpenTelemetry config: instrument your FastAPI servers and role flows
# Use OTEL exporter e.g., OTLP to collector.
print("Install and configure OpenTelemetry SDK in your services.")
PY

# ---------------------------
# 10) Approval queue & UI stub (HTTP)
# ---------------------------
cat > ops/approvals/approval_service.py <<'PY'
#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
import json, os, time, uuid
QUEUE="ops/approvals/queue.jsonl"
app=FastAPI(title="ApprovalQueue")
def append(q):
    open(QUEUE,"a").write(json.dumps(q)+"\\n")
@app.post("/submit")
def submit(action: dict):
    rec = {"id":str(uuid.uuid4()),"ts":time.time(),"action":action,"status":"pending"}
    append(rec)
    return {"ok":True,"id":rec["id"]}
@app.post("/approve/{id}")
def approve(id: str):
    # naive: mark as approved in file (append)
    rec={"id":id,"ts":time.time(),"action":"approve"}
    append(rec)
    return {"ok":True}
PY
chmod +x ops/approvals/approval_service.py

# ---------------------------
# 11) Training / ETL skeletons & trainer (ML)
# ---------------------------
cat > training/roles/etl.py <<'PY'
#!/usr/bin/env python3
# ETL: logs -> dataset for selector model
import json, os
LOG="logs/role_audit.log"
OUT="training/roles/dataset.jsonl"
if not os.path.exists(LOG):
    print("no logs found")
else:
    with open(LOG) as f, open(OUT,"w") as o:
        for l in f:
            o.write(l)
print("wrote dataset to", OUT)
PY
cat > training/roles/train.py <<'PY'
#!/usr/bin/env python3
# Very small trainer stub: reads dataset and writes model artifact
import os
OUT="training/roles/selector_model.stub"
open(OUT,"w").write("model-stub:"+str(os.path.getmtime(OUT) if os.path.exists(OUT) else 0))
print("wrote", OUT)
PY
chmod +x training/roles/etl.py training/roles/train.py

# ---------------------------
# 12) PR generator safe wrapper (no push by default)
# ---------------------------
cat > ops/role_engine/pr_helper.py <<'PY'
#!/usr/bin/env python3
"""
Safe PR helper: creates local branch & commit; pushing or opening a remote PR is manual.
Use GH CLI or API with review before pushing.
"""
import subprocess, os, uuid
def create_pr_stub(repo_path, patch_text, title):
    branch="are-proposal-"+str(uuid.uuid4())[:8]
    subprocess.check_call(['git','checkout','-b',branch], cwd=repo_path)
    p = subprocess.Popen(['git','apply','-'], cwd=repo_path, stdin=subprocess.PIPE)
    p.communicate(patch_text.encode())
    subprocess.check_call(['git','add','-A'], cwd=repo_path)
    subprocess.check_call(['git','commit','-m', title], cwd=repo_path)
    return {"branch":branch,"status":"committed-local"}
PY
chmod +x ops/role_engine/pr_helper.py

# ---------------------------
# 13) Simulator / Canary runner skeleton
# ---------------------------
cat > simulator/run_simulation.py <<'PY'
#!/usr/bin/env python3
import json, os, time
SIMDIR="simulator"
os.makedirs(SIMDIR, exist_ok=True)
def run_case(case):
    # simple run: calls are_service simulate through local file
    path=os.path.join(SIMDIR, "case_"+str(int(time.time()))+".json")
    open(path,"w").write(json.dumps(case))
    return {"ok":True,"case":path}
if __name__=="__main__":
    print(run_case({"text":"sample scenario","expected":"Coordinator"}))
PY
chmod +x simulator/run_simulation.py

# ---------------------------
# 14) Tests (pytest) - role enforcement
# ---------------------------
cat > tests/test_role_enforcement.py <<'PY'
import json, os
def test_registry_exists():
    assert os.path.exists("ops/role_engine/role_registry_v2.json")
def test_schema_exists():
    assert os.path.exists("ops/role_engine/role_schema.json")
def test_selector_stub_runs():
    import subprocess, json
    p = subprocess.run(["python3","mcp/roles/selector_advanced.py","run","unit","tests"], capture_output=True)
    assert p.returncode == 0
PY

# ---------------------------
# 15) Docs & runbook
# ---------------------------
cat > docs/ARE_PLUS_README.md <<'MD'
# ARE+ (Autonomous Role Engine - OVERDRIVE)
Quick start:
1) Review ops/role_engine/INSTALL_OPTIONS.env and tune AUTO_APPROVE, secrets.
2) Run role service:
   python3 ops/role_engine/are_service.py
   or: uvicorn ops.role_engine.are_service:app --host 0.0.0.0 --port 9700
3) Start approval and role services for HITL:
   python3 ops/approvals/approval_service.py
4) Run OPA (optional):
   ./scripts/run_opa.sh
5) Use selector:
   python3 mcp/roles/selector_advanced.py "run tests and propose patch"
Security notes: change JWT_SECRET, set AUTO_APPROVE=false until you trust automation.
MD

# ---------------------------
# 16) helper scripts
# ---------------------------
cat > scripts/start_all_are.sh <<'SH'
#!/usr/bin/env bash
# start role manager and approval queue (dev)
echo "Start role manager (uvicorn recommended) and approval queue (uvicorn recommended)"
python3 ops/role_engine/are_service.py &
python3 ops/approvals/approval_service.py &
echo "Started (background). Check logs or run uvicorn for production."
SH
chmod +x scripts/start_all_are.sh

cat > scripts/run_sanity_all.sh <<'SH'
#!/usr/bin/env bash
set -e
./scripts/sanity_roles.sh || true
pytest -q || true
echo "Sanity run complete"
SH
chmod +x scripts/run_sanity_all.sh

# ---------------------------
# 17) Sanity script (existing)
# ---------------------------
cat > scripts/sanity_roles.sh <<'SH'
#!/usr/bin/env bash
set -e
echo "=== SANITY: ARE+ ==="
python3 - <<'PY'
import json
r=json.load(open('ops/role_engine/role_registry_v2.json'))
print('roles_count:',len(r['roles']))
PY
python3 mcp/roles/selector_advanced.py "run tests and prepare patch"
echo "=== DONE ==="
SH
chmod +x scripts/sanity_roles.sh

# ---------------------------
# 18) finalize
# ---------------------------
echo "=== ARE+ OVERDRIVE INSTALL COMPLETE ==="
echo "Files created under: $ROOT"
echo "Read docs/ARE_PLUS_README.md for usage."
echo "IMPORTANT: Inspect ops/role_engine/INSTALL_OPTIONS.env and change AUTO_APPROVE, JWT_SECRET before enabling."
