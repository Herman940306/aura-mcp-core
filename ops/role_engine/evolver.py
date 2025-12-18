#!/usr/bin/env python3
"""
Role Evolver - prototype:
 - takes audit logs and proposals
 - proposes variations (mutations) to existing roles
 - writes drafts to drafts/
This is intentionally conservative: proposals are drafted, not auto-committed.
"""
import copy
import json
import os
import random
import time
import uuid

REG = "ops/role_engine/role_registry_v2.json"
DRAFTS = "ops/role_engine/drafts"
LOGS = "logs/role_audit.log"


def load_roles():
    return json.load(open(REG))["roles"]


def sample_mutation(role):
    spec = copy.deepcopy(role)
    # mutate priority slightly
    p = spec.get("scoring_profile", {}).get("priority", 5)
    newp = max(1, min(10, p + random.choice([-1, 0, 1])))
    spec["scoring_profile"]["priority"] = newp
    spec["version"] = (
        spec.get("version", "1.0.0") + ".mut" + str(int(time.time()))
    )
    return spec


def propose_mutations(n=2):
    roles = load_roles()
    os.makedirs(DRAFTS, exist_ok=True)
    proposals = []
    for i in range(n):
        name = random.choice(list(roles.keys()))
        mutated = sample_mutation(roles[name])
        draft_id = str(uuid.uuid4())
        draft = {
            "id": draft_id,
            "original": name,
            "proposal": mutated,
            "meta": {"ts": time.time()},
        }
        path = os.path.join(DRAFTS, draft_id + ".json")
        open(path, "w").write(json.dumps(draft, indent=2))
        proposals.append(draft)
    return proposals


if __name__ == "__main__":
    print(propose_mutations(3))
