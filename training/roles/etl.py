#!/usr/bin/env python3
# ETL: logs -> dataset for selector model
import os

LOG = "logs/role_audit.log"
OUT = "training/roles/dataset.jsonl"
if not os.path.exists(LOG):
    print("no logs found")
else:
    with open(LOG) as f, open(OUT, "w") as o:
        for l in f:
            o.write(l)
print("wrote dataset to", OUT)
