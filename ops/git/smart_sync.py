#!/usr/bin/env python3
"""
Smart Sync: incremental, low-IO repo sync for agents & CI.

Usage:
  python ops/git/smart_sync.py --repo /path/to/repo --ref origin/main --mode incremental
Modes:
  - incremental   : git fetch --depth=1 + git reset --hard <ref>
  - shallow       : git clone --depth=1 (to target dir)
  - sparse        : clone + sparse-checkout set <paths>
  - worktree      : create/use a worktree for branch
"""
import argparse
import os
import shlex
import subprocess
import sys


def run(cmd, cwd=None, check=True):
    print(f"> {cmd}")
    p = subprocess.run(
        cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=False
    )
    if p.stdout:
        print(p.stdout.strip())
    if p.stderr:
        print(p.stderr.strip(), file=sys.stderr)
    if check and p.returncode != 0:
        raise SystemExit(f"Command failed: {cmd}\n{p.stderr}")
    return p


def ensure_git_repo(path, remote_url=None):
    if not os.path.exists(os.path.join(path, ".git")):
        if not remote_url:
            raise SystemExit("Repo not found and no remote_url provided")
        run(
            f"git clone --no-tags --depth=1 {shlex.quote(remote_url)} {shlex.quote(path)}",
            check=True,
        )
    return True


def incremental_sync(path, ref="origin/main"):
    # fetch only latest commit and hard-reset
    run("git remote set-branches origin '*' || true", cwd=path)
    run("git fetch --depth=1 origin", cwd=path)
    run(f"git reset --hard {ref}", cwd=path)
    run("git clean -fdx", cwd=path)
    return True


def shallow_clone(target, remote_url):
    run(
        f"git clone --no-tags --depth=1 {shlex.quote(remote_url)} {shlex.quote(target)}"
    )
    return True


def sparse_clone(target, remote_url, paths):
    run(
        f"git clone --no-checkout --filter=blob:none {shlex.quote(remote_url)} {shlex.quote(target)}"
    )
    run("git sparse-checkout init --cone", cwd=target)
    run(
        "git sparse-checkout set " + " ".join(shlex.quote(p) for p in paths),
        cwd=target,
    )
    run("git checkout", cwd=target)
    return True


def create_worktree(repo_path, branch, worktrees_dir):
    os.makedirs(worktrees_dir, exist_ok=True)
    wt_path = os.path.join(worktrees_dir, branch)
    # create worktree
    run(
        f"git worktree add {shlex.quote(wt_path)} -B {shlex.quote(branch)}",
        cwd=repo_path,
    )
    return wt_path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--remote", required=False)
    p.add_argument("--ref", default="origin/main")
    p.add_argument(
        "--mode",
        choices=["incremental", "shallow", "sparse", "worktree"],
        default="incremental",
    )
    p.add_argument("--paths", nargs="*", help="paths for sparse")
    p.add_argument("--branch", help="worktree branch name")
    p.add_argument("--worktrees_dir", default=".worktrees")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    repo = os.path.abspath(args.repo)
    if args.mode == "shallow":
        if os.path.exists(repo) and os.path.isdir(os.path.join(repo, ".git")):
            print("Repo exists; running incremental instead")
            incremental_sync(repo, args.ref)
        else:
            shallow_clone(repo, args.remote)
    elif args.mode == "sparse":
        sparse_clone(repo, args.remote, args.paths or [])
    elif args.mode == "worktree":
        if not args.branch:
            raise SystemExit("worktree mode requires --branch")
        create_worktree(repo, args.branch, args.worktrees_dir)
    else:
        # incremental
        ensure_git_repo(repo, args.remote)
        incremental_sync(repo, args.ref)
    print("Smart sync complete.")
