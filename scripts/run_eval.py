"""Eval gate (bootstrap). Case #1 runs the scripted golden path and
scores it. Office phase adds real golden cases (first: the KVP STM
defect project) under eval/golden/<case>/ with case.yaml + inputs."""
import subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    r = subprocess.run([sys.executable, "scripts/smoke_test.py"], cwd=ROOT,
                       capture_output=True, text=True)
    ok = r.returncode == 0
    print(f"| case            | result |")
    print(f"| bootstrap-cycle | {'PASS' if ok else 'FAIL'}   |")
    if not ok:
        print(r.stdout[-800:], r.stderr[-800:])
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
