#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
echo "=== ARE++ + GUARDS INSTALLER ==="
echo "Root: $ROOT"

# safety: don't run as root
if [ "$(id -u)" = "0" ]; then
  echo "Do not run as root; run as normal user in WSL."
  exit 1
fi

# create directories
mkdir -p ops/role_engine ops/opa/policies ops/guards ops/approvals mcp/roles mcp/server training/roles training/ml scripts logs model_artifacts observability tests simulator docs .github/workflows

# write INSTALL_OPTIONS.env
cat > ops/role_engine/INSTALL_OPTIONS.env <<'ENV'
AUTO_APPROVE=false
JWT_SECRET=dev-secret
OPA_URL=http://opa:8181
FORBIDDEN_ROLE_PREFIXES=hack,illegal,bio
MAX_AUTOGEN_RISK=0.6
MIN_VERIFY=0.6
ENV

# Role registry v2
cat > ops/role_engine/role_registry_v2.json <<'JSON'
{
  "meta": {"version":"2.0.0","created_by":"installer_overdrive","created_at":"$(date -Iseconds)"},
  "roles": {
    "Lead Engineer": {"purpose":"Automation & infra changes","capabilities":["orchestrate","apply_pr","run_infra"],"scoring_profile":{"priority":9,"confidence_weight":0.9,"risk_factor":0.9}},
    "Senior Architect": {"purpose":"Architecture & strategy","capabilities":["design","review_arch"],"scoring_profile":{"priority":9,"confidence_weight":0.85,"risk_factor":0.8}},
    "Full-Stack Guru": {"purpose":"Code, integration, merge","capabilities":["code","merge","debug"],"scoring_profile":{"priority":8,"confidence_weight":0.9,"risk_factor":0.9}},
    "Researcher": {"purpose":"RAG & analysis","capabilities":["query","upsert_memory"],"scoring_profile":{"priority":4,"confidence_weight":0.5,"risk_factor":0.2}},
    "Security Officer": {"purpose":"Security & compliance","capabilities":["approve_security","block_action"],"scoring_profile":{"priority":10,"confidence_weight":0.95,"risk_factor":1.0}},
    "Product Owner": {"purpose":"Requirements & acceptance","capabilities":["prioritize","acceptance"],"scoring_profile":{"priority":7,"confidence_weight":0.6,"risk_factor":0.6}},
    "Knowledge Curator": {"purpose":"Docs & memory","capabilities":["doc_update","memory_curation"],"scoring_profile":{"priority":3,"confidence_weight":0.4,"risk_factor":0.1}},
    "Coordinator": {"purpose":"Multi-agent coordination","capabilities":["route","delegate"],"scoring_profile":{"priority":6,"confidence_weight":0.6,"risk_factor":0.5}},
    "UX Designer": {"purpose":"UX & formatting","capabilities":["format","ux_improve"],"scoring_profile":{"priority":2,"confidence_weight":0.3,"risk_factor":0.1}}
  }
}
JSON

# Role JSON schema
cat > ops/role_engine/role_schema.json <<'JSON'
{ "$schema":"http://json-schema.org/draft-07/schema#","title":"ARE Role Definition Schema","type":"object","properties":{"name":{"type":"string"},"purpose":{"type":"string"},"responsibilities":{"type":"array","items":{"type":"string"}},"behaviors":{"type":"array","items":{"type":"string"}},"interactions":{"type":"array","items":{"type":"string"}},"scoring_profile":{"type":"object","properties":{"priority":{"type":"integer","minimum":1,"maximum":10},"confidence_weight":{"type":"number","minimum":0.0,"maximum":1.0},"risk_factor":{"type":"number","minimum":0.0,"maximum":1.0}},"required":["priority","confidence_weight","risk_factor"]},"version":{"type":"string"}},"required":["name","purpose","responsibilities","scoring_profile","version"]}
JSON

# ARE Service (FastAPI) - are_service.py
cat > ops/role_engine/are_service.py <<'PY'
#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import json, os, time, uuid
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
    name: str; purpose: str; responsibilities: list; behaviors: list = []; interactions: list = []; scoring_profile: dict; version: str
@app.get("/roles")
def list_roles():
    return load_registry()
@app.post("/roles")
def create_role(spec: RoleSpec):
    try:
        schema = json.load(open(SCHEMA_FILE))
        validate(instance=spec.dict(), schema=schema)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    for p in FORBIDDEN_PREFIXES:
        if spec.name.lower().startswith(p.lower()):
            raise HTTPException(status_code=403, detail="forbidden role name prefix")
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    draft_id = str(uuid.uuid4()); draft_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    draft = {"id": draft_id, "spec": spec.dict(), "meta":{"ts":time.time(),"status":"draft"}}
    open(draft_path,"w").write(json.dumps(draft,indent=2))
    risk = spec.scoring_profile.get("risk_factor",0.5)
    if AUTO_APPROVE and risk <= MAX_AUTOGEN_RISK:
        reg = load_registry(); reg["roles"][spec.name] = spec.dict(); reg["meta"]["last_updated"] = time.time(); save_registry(reg)
        draft["meta"]["status"] = "committed"; open(draft_path,"w").write(json.dumps(draft,indent=2))
        return {"ok":True,"committed":True,"role":spec.name}
    return {"ok":True,"draft_id":draft_id,"committed":False}
@app.post("/propose")
def propose_role_change(payload: dict = Body(...)):
    proposal = payload.get("proposal")
    if not proposal:
        raise HTTPException(status_code=400, detail="missing proposal")
    risk = proposal.get("scoring_profile",{}).get("risk_factor",0.5)
    draft_id = str(uuid.uuid4())
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    draft_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    draft = {"id":draft_id,"proposal":proposal,"reason":payload.get("reason"),"evidence":payload.get("evidence",[]),"meta":{"ts":time.time(),"risk":risk,"status":"proposed"}}
    open(draft_path,"w").write(json.dumps(draft,indent=2))
    return {"ok":True,"draft_id":draft_id,"risk":risk}
@app.post("/evaluate")
def evaluate_task(task: dict = Body(...)):
    task_text = task.get("task","").lower()
    reg = load_registry()["roles"]
    candidates = []
    for name,spec in reg.items():
        score = 0.0
        txt = (spec.get("purpose","")+" "+ " ".join(spec.get("responsibilities",[]))).lower()
        for w in set(task_text.split()):
            if len(w)>2 and w in txt: score += 1.0
        p = spec.get("scoring_profile",{}).get("priority",5); score = score * (p/10.0)
        candidates.append({"role":name,"score":score,"priority":p})
    candidates = sorted(candidates, key=lambda x:x["score"], reverse=True)
    return {"candidates":candidates[:task.get("topk",3)], "meta":{"task":task_text}}
@app.post("/simulate")
def simulate_role(role_name: str = Body(...), scenario: dict = Body(...)):
    sim_id = str(uuid.uuid4()); sim_path = os.path.join(SIM_DIR, sim_id + ".json")
    reg = load_registry()["roles"]; spec = reg.get(role_name)
    if not spec: raise HTTPException(status_code=404, detail="role not found")
    score = 0
    for r in spec.get("responsibilities",[]):
        for w in r.split():
            if w.lower() in scenario.get("text","").lower(): score += 1
    verdict = {"role":role_name,"sim_score":score,"ok": score>0}
    open(sim_path,"w").write(json.dumps({"id":sim_id,"verdict":verdict,"ts":time.time()},indent=2))
    return {"sim_id":sim_id,"verdict":verdict}
# run: uvicorn ops.role_engine.are_service:app --host 0.0.0.0 --port 9700
PY
chmod +x ops/role_engine/are_service.py

# selector_advanced
cat > mcp/roles/selector_advanced.py <<'PY'
#!/usr/bin/env python3
import json, os, math
REG="ops/role_engine/role_registry_v2.json"
def load_registry():
    return json.load(open(REG))["roles"]
def pseudo_model_score(text, role_spec):
    score=0.0
    txt = (role_spec.get("purpose","")+" "+ " ".join(role_spec.get("responsibilities",[]))).lower()
    for tok in set(text.lower().split()):
        if len(tok)>3 and tok in txt:
            score += 1.0
    p = role_spec.get("scoring_profile",{}).get("priority",5)
    return score * (p/10.0)
def calibrate_confidence(raw_score):
    return 1.0/(1.0+math.exp(-raw_score+1.0))
def select_roles(task_text, topk=3):
    reg=load_registry(); cand=[]
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

# negotiator_advanced
cat > mcp/roles/negotiator_advanced.py <<'PY'
#!/usr/bin/env python3
def arbitrate(opinions, threshold=0.7):
    opinions_sorted = sorted(opinions,key=lambda x:x.get("confidence",0.0), reverse=True)
    top = opinions_sorted[0]
    if top.get("confidence",0.0) >= threshold:
        return {"decision":"accept","role":top["role"],"confidence":top["confidence"]}
    votes={}
    for o in opinions:
        votes[o["role"]] = votes.get(o["role"],0.0) + o.get("confidence",0.0)
    winner = max(votes.items(), key=lambda x:x[1])
    if winner[1] >= threshold:
        return {"decision":"voted","role":winner[0],"weight":winner[1]}
    return {"decision":"escalate","to":"Coordinator","votes":votes}
PY
chmod +x mcp/roles/negotiator_advanced.py

# evolver prototype
cat > ops/role_engine/evolver.py <<'PY'
#!/usr/bin/env python3
import json, os, random, time, copy, uuid
REG="ops/role_engine/role_registry_v2.json"; DRAFTS="ops/role_engine/drafts"
def load_roles(): return json.load(open(REG))["roles"]
def sample_mutation(role):
    spec = copy.deepcopy(role)
    p = spec.get("scoring_profile",{}).get("priority",5)
    newp = max(1, min(10, p + random.choice([-1,0,1])))
    spec["scoring_profile"]["priority"] = newp
    spec["version"] = spec.get("version","1.0.0") + ".mut" + str(int(time.time()))
    return spec
def propose_mutations(n=2):
    roles = load_roles(); os.makedirs(DRAFTS, exist_ok=True); proposals=[]
    for i in range(n):
        name = random.choice(list(roles.keys())); mutated = sample_mutation(roles[name])
        draft_id = str(uuid.uuid4()); draft = {"id":draft_id,"original":name,"proposal":mutated,"meta":{"ts":time.time()}}
        path = os.path.join(DRAFTS, draft_id+".json"); open(path,"w").write(json.dumps(draft,indent=2)); proposals.append(draft)
    return proposals
if __name__=="__main__":
    print(propose_mutations(3))
PY
chmod +x ops/role_engine/evolver.py

# audit_provenance
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
    open(AUDIT_LOG,"a").write(json.dumps(record)+"\n")
    return record
PY
chmod +x ops/role_engine/audit_provenance.py

# hallucination checker (RAG cross-check)
cat > ops/guards/hallucination_checker.py <<'PY'
#!/usr/bin/env python3
import os, requests, math
QDRANT = os.getenv("QDRANT_URL","http://aura-ia-rag:9202")
EMB = os.getenv("EMB_URL","http://aura-ia-ml:9201")
def embed(texts):
    r = requests.post(EMB+"/embed", json={"texts": texts}, timeout=30)
    return r.json().get("vectors", [])
def search(vector, topk=5, collection="agent_knowledge"):
    url = f"{QDRANT}/collections/{collection}/points/search"
    resp = requests.post(url, json={"vector": vector, "top": topk}, timeout=30)
    return resp.json().get("result") or resp.json()
def support_score(claim_text, topk=5):
    vectors = embed([claim_text])
    if not vectors: return {"score":0.0,"sources":[]}
    v = vectors[0]
    res = search(v, topk=topk)
    count = len(res) if isinstance(res, list) else 0
    score = 1 - math.exp(-0.5 * count)
    sources=[]
    for p in res:
        sources.append({"type":"qdrant","ref": str(p.get("id")), "payload": p.get("payload",{})})
    return {"score": score, "sources": sources}
PY
chmod +x ops/guards/hallucination_checker.py

# llm output schema
cat > ops/guards/llm_output_schema.json <<'JSON'
{ "$schema":"http://json-schema.org/draft-07/schema#","title":"LLM Output Schema","type":"object","required":[ "result","rationale","sources","confidence","verdict" ],"properties":{"result":{"type":"string"},"rationale":{"type":"object","properties":{"steps":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}}},"sources":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string"},"ref":{"type":"string"}}}},"confidence":{"type":"number","minimum":0,"maximum":1},"verdict":{"type":"string","enum":["verified","unverified","refetch","human_review"]},"metadata":{"type":"object"}}}
JSON

# LLM guard middleware
cat > mcp/server/guards_middleware.py <<'PY'
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import json, os
from jsonschema import validate, ValidationError
from ops.guards.hallucination_checker import support_score
SCHEMA = "ops/guards/llm_output_schema.json"
MIN_VERIFY_THRESHOLD = float(os.getenv("MIN_VERIFY", "0.6"))
class LLMGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        try:
            data = await resp.json()
        except Exception:
            return resp
        if isinstance(data, dict) and "result" in data:
            try:
                validate(instance=data, schema=json.load(open(SCHEMA)))
            except ValidationError as e:
                raise HTTPException(status_code=500, detail=f"LLM output invalid schema: {e.message}")
            claim = data.get("result","")
            s = support_score(claim)
            data.setdefault("metadata",{})["support"] = s
            if s["score"] >= MIN_VERIFY_THRESHOLD:
                data["verdict"] = "verified"
            else:
                if data.get("confidence",0.0) >= 0.85:
                    data["verdict"] = "human_review"
                else:
                    data["verdict"] = "unverified"
            # build new response
            from starlette.responses import JSONResponse
            return JSONResponse(content=data, status_code=resp.status_code, headers=resp.headers)
        return resp
PY
chmod +x mcp/server/guards_middleware.py

# no_lie_prompt
cat > ops/guards/no_lie_prompt.txt <<'TXT'
SYSTEM: YOU ARE A TRANSPARENT ASSISTANT.
Rules:
1) Every factual statement must be supported by verifiable sources. If you cannot find evidence, say "I don't know" and suggest a retrieval plan.
2) For any conclusion provide a short RATIONALE with step-by-step reasoning.
3) Return output strictly as JSON matching ops/guards/llm_output_schema.json.
4) Always include a numeric CONFIDENCE in [0,1]. Be calibrated.
5) Do not generate fabricated URLs or references.
END
TXT

# OPA policy (basic)
cat > ops/opa/policies/role_policy_full.rego <<'REGO'
package mcp.authz
default allow = false
allow {
  input.action == "call_tool"
  some r
  r := input.roles[_]
  input.tool_required[_] == r
}
REGO

cat > ops/opa/policies/no_lie.rego <<'REGO'
package mcp.guards
default allow_claim = false
allow_claim {
  input.action == "produce_factual_claim"
  input.outputs.verdict == "verified"
}
REGO

# approval service
cat > ops/approvals/approval_service.py <<'PY'
#!/usr/bin/env python3
from fastapi import FastAPI
import json, os, time, uuid
QUEUE="ops/approvals/queue.jsonl"
app=FastAPI(title="ApprovalQueue")
def append(q): open(QUEUE,"a").write(json.dumps(q)+"\n")
@app.post("/submit")
def submit(action: dict):
    rec = {"id":str(uuid.uuid4()),"ts":time.time(),"action":action,"status":"pending"}
    append(rec)
    return {"ok":True,"id":rec["id"]}
@app.post("/approve/{id}")
def approve(id: str):
    rec={"id":id,"ts":time.time(),"action":"approve"}
    append(rec)
    return {"ok":True}
PY
chmod +x ops/approvals/approval_service.py

# SICD PR generator safe wrapper
cat > training/sicd/pr_generator.py <<'PY'
#!/usr/bin/env python3
import subprocess, os, json
def apply_patch_and_open_pr(repo_path, patch_text, title, body, remote='origin', actor_roles=None):
    allowed_roles = {"Lead Engineer","Full-Stack Guru"}
    if actor_roles:
        if not (set(actor_roles) & allowed_roles):
            return {"error":"actor lacks permission to create PR"}
    try:
        subprocess.check_call(['git','checkout','-b','sicd/auto-fix'], cwd=repo_path)
        p = subprocess.Popen(['git','apply','-'], cwd=repo_path, stdin=subprocess.PIPE)
        p.communicate(patch_text.encode())
        subprocess.check_call(['git','add','-A'], cwd=repo_path)
        subprocess.check_call(['git','commit','-m', title], cwd=repo_path)
        return {'branch':'sicd/auto-fix','title':title}
    except Exception as e:
        return {'error':str(e)}
PY
chmod +x training/sicd/pr_generator.py

# code quality check script
cat > ops/guards/code_quality_check.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "Running code quality checks..."
if command -v flake8 >/dev/null 2>&1; then flake8 || (echo "flake8 failed"; exit 1); fi
if command -v mypy >/dev/null 2>&1; then mypy . || (echo "mypy failed"; exit 1); fi
pytest -q --maxfail=1 || (echo "pytest failed"; exit 1)
if command -v coverage >/dev/null 2>&1; then
  coverage run -m pytest && coverage report --fail-under=80 || (echo "coverage threshold failed"; exit 1)
fi
if command -v bandit >/dev/null 2>&1; then
  bandit -r . -q || (echo "bandit found issues"; exit 1)
fi
echo "Quality checks passed."
SH
chmod +x ops/guards/code_quality_check.sh

# pre-commit
cat > .pre-commit-config.yaml <<'YML'
repos:
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.5.0
  hooks:
    - id: trailing-whitespace
    - id: end-of-file-fixer
- repo: https://github.com/psf/black
  rev: 24.1.0
  hooks:
    - id: black
- repo: https://github.com/PyCQA/flake8
  rev: 6.0.0
  hooks:
    - id: flake8
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.2.0
  hooks:
    - id: mypy
YML

# GitHub Actions: quality & guard
cat > .github/workflows/quality_and_guard.yml <<'YAML'
name: Quality & Guard Checks
on: [pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Setup Python
      uses: actions/setup-python@v4
      with: python-version: '3.11'
    - name: Install deps
      run: |
        python -m pip install -r requirements.txt || true
        pip install flake8 mypy coverage bandit jsonschema || true
    - name: Run code quality
      run: bash ops/guards/code_quality_check.sh
    - name: Validate ARE role schemas
      run: |
        python - <<'PY'
import json,glob
schema=json.load(open('ops/role_engine/role_schema.json'))
for f in glob.glob('mcp/roles/*.json')+glob.glob('ops/role_engine/drafts/*.json'):
    try:
        j=json.load(open(f))
        from jsonschema import validate
        validate(instance=j, schema=schema)
        print("OK",f)
    except Exception as e:
        print("Schema validation failed for",f,e); raise
PY
YAML

# tests: basic
cat > tests/test_role_enforcement.py <<'PY'
import os
def test_registry_exists():
    assert os.path.exists("ops/role_engine/role_registry_v2.json")
def test_selector_runs():
    import subprocess
    p = subprocess.run(["python3","mcp/roles/selector_advanced.py","run","unit","tests"], capture_output=True)
    assert p.returncode == 0
PY

# OPA test harness
cat > ops/opa/test_harness.sh <<'SH'
#!/usr/bin/env bash
set -e
echo "OPA policy harness: please install docker and run this to test policies"
echo "docker run --rm -v $(pwd)/ops/opa/policies:/policies openpolicyagent/opa:0.51.2 test /policies"
SH
chmod +x ops/opa/test_harness.sh

# scripts
cat > scripts/sanity_roles.sh <<'SH'
#!/usr/bin/env bash
set -e
echo "=== SANITY: ARE+ ==="
python3 - <<'PY'
import json
r=json.load(open('ops/role_engine/role_registry_v2.json'))
print('roles_count:',len(r['roles']))
PY
python3 mcp/roles/selector_advanced.py "run tests and prepare patch" || true
echo "=== DONE ==="
SH
chmod +x scripts/sanity_roles.sh

cat > scripts/start_all_are.sh <<'SH'
#!/usr/bin/env bash
echo "Start ARE service and approval service (dev mode)"
python3 ops/role_engine/are_service.py &
python3 ops/approvals/approval_service.py &
echo "Started in background (dev). Use uvicorn for production."
SH
chmod +x scripts/start_all_are.sh

# Try to patch mcp/server/main.py to wire guards middleware + auth_roles + role_audit
MAIN="mcp/server/main.py"
if [ -f "${MAIN}" ]; then
  cp "${MAIN}" "${MAIN}.bak_$(date +%s)"
  echo "Backed up ${MAIN} to ${MAIN}.bak_*"
  # insert imports and middleware registration if not already present
  python3 - <<'PY'
import io,sys,re
p="mcp/server/main.py"
s=open(p).read()
if "from mcp.server.guards_middleware import LLMGuardMiddleware" not in s:
    s = s.replace("from fastapi import FastAPI", "from fastapi import FastAPI\\nfrom mcp.server.guards_middleware import LLMGuardMiddleware\\nfrom mcp.server.auth_roles import get_current_identity\\nfrom mcp.server.role_audit import log_event\\n")
    # add middleware registration after app = FastAPI(...)
    s = re.sub(r'(app\\s*=\\s*FastAPI\\([^\\)]*\\))', r'\\1\\napp.add_middleware(LLMGuardMiddleware)\\n', s, count=1)
    open(p,"w").write(s)
    print("patched mcp/server/main.py (middleware + auth imports inserted)")
else:
    print("mcp/server/main.py already appears patched; skipping")
PY
else
  echo "No mcp/server/main.py found — please integrate mcp/server/guards_middleware.py and ops/guards/* into your server manually"
fi

echo "=== INSTALL COMPLETE ==="
echo "Read ops/role_engine/INSTALL_OPTIONS.env to adjust AUTO_APPROVE, JWT_SECRET, etc."
echo "Run: ./scripts/start_all_are.sh  (dev)  or run uvicorn for production."
