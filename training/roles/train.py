#!/usr/bin/env python3
# Very small trainer stub: reads dataset and writes model artifact
import os

OUT = "training/roles/selector_model.stub"
open(OUT, "w").write(
    "model-stub:" + str(os.path.getmtime(OUT) if os.path.exists(OUT) else 0)
)
print("wrote", OUT)
