"""One command, whole verdict: purity + smoke."""
import importlib, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def purity():
    banned = {"streamlit", "fastapi", "flask", "django"}
    for m in ("core.state", "core.gates", "core.tasks", "core.workspace",
              "modeler.runner", "modeler.agent_tools", "checker.qa",
              "ui.backend"):
        importlib.import_module(m)
    hit = banned & set(sys.modules)
    if hit:
        print(f"PURITY FAIL: UI frameworks imported by core: {hit}")
        return False
    print("purity: OK (core/domain import no UI framework)")
    return True

def main():
    ok = purity()
    r = subprocess.run([sys.executable, "scripts/smoke_test.py"],
                       cwd=os.path.dirname(os.path.dirname(
                           os.path.abspath(__file__))))
    ok = ok and r.returncode == 0
    print("CHECK:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
