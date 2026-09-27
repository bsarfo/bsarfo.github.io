"""Run the whole ReRouteAI pipeline in order, then start the dashboard.

    python run_all.py          all steps (evaluation takes 1-2 minutes)
    python run_all.py --fast   skip the evaluation when results already exist

Steps: setup check -> evaluate -> tests -> build class simulator -> open the
simulator in your browser -> start the Streamlit dashboard. It stops at the
first step that fails. Stop the dashboard with the red square in PyCharm
(or Ctrl+C in a terminal).
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}


def step(n: int, title: str, cmd: list[str]) -> None:
    print(f"\n{'=' * 70}\nSTEP {n}: {title}\n{'=' * 70}", flush=True)
    t = time.perf_counter()
    result = subprocess.run(cmd, cwd=ROOT, env=ENV)
    if result.returncode != 0:
        print(f"\nSTEP {n} FAILED ({title}). Fix the error above, then run again.")
        sys.exit(result.returncode)
    print(f"-- {title}: done in {time.perf_counter() - t:.0f} s", flush=True)


def main() -> None:
    fast = "--fast" in sys.argv
    step(1, "Check setup", [PY, "verify_setup.py"])
    if fast and (ROOT / "docs" / "results.json").exists():
        print("\nSTEP 2: Evaluate -- skipped (--fast; using existing docs/results.md)")
    else:
        step(2, "Evaluate: train model, test it, simulate decisions", [PY, "evaluate.py"])
    step(3, "Tests", [PY, "-m", "pytest", "-q", "tests"])
    step(4, "Build class simulator", [PY, "build_simulator.py"])

    sim = ROOT / "simulator" / "ReRouteAI_Simulator.html"
    print(f"\nOpening the class simulator: {sim}")
    webbrowser.open(sim.as_uri())

    print(f"\n{'=' * 70}\nSTEP 5: Dashboard -> http://localhost:8501  (stop with the red square)\n{'=' * 70}",
          flush=True)
    os.chdir(ROOT)
    from streamlit.web import cli as stcli  # run in this process so PyCharm's stop button ends it
    sys.argv = ["streamlit", "run", "app.py"]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
