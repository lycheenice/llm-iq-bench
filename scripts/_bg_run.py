#!/usr/bin/env python3
"""后台启动一个 run_benchmark 命令，完全脱离当前 shell（double-fork）。
用法: python3 scripts/_bg_run.py <plan> > logfile 2>&1
"""
import os, sys, subprocess

def main():
    plan = sys.argv[1]
    repo = "/home/lychee/mycode/llm-iq-bench"
    cmd = [sys.executable, f"{repo}/scripts/run_benchmark.py", "run",
           "--plan", f"{repo}/plans/{plan}/plan.yaml", "--model", "glm-local"]
    # double-fork detach
    if os.fork() != 0:
        print(f"detached launcher for {plan} (parent exiting)")
        return
    os.setsid()
    if os.fork() != 0:
        os._exit(0)
    os.chdir(repo)
    sys.stdout.flush()
    out = open(f"/tmp/opencode/logs/rerun_{plan}.log", "w", encoding="utf-8")
    os.dup2(out.fileno(), 1); os.dup2(out.fileno(), 2)
    os.execv(cmd[0], cmd)

if __name__ == "__main__":
    main()
