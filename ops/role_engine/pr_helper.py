#!/usr/bin/env python3
"""
Safe PR helper: creates local branch & commit; pushing or opening a remote PR is manual.
Use GH CLI or API with review before pushing.
"""
import subprocess
import uuid


def create_pr_stub(repo_path, patch_text, title):
    branch = "are-proposal-" + str(uuid.uuid4())[:8]
    subprocess.check_call(["git", "checkout", "-b", branch], cwd=repo_path)
    p = subprocess.Popen(
        ["git", "apply", "-"], cwd=repo_path, stdin=subprocess.PIPE
    )
    p.communicate(patch_text.encode())
    subprocess.check_call(["git", "add", "-A"], cwd=repo_path)
    subprocess.check_call(["git", "commit", "-m", title], cwd=repo_path)
    return {"branch": branch, "status": "committed-local"}
