"""Check that the ReRouteAI project is set up correctly.

Run from PyCharm ("1. Check setup") or:  python verify_setup.py
"""

from __future__ import annotations

import importlib
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
ok = True


def check(label: str, passed: bool, fix: str = "") -> None:
    global ok
    print(f"  [{'OK' if passed else 'FAIL'}] {label}")
    if not passed:
        ok = False
        if fix:
            print(f"         fix: {fix}")


print("ReRouteAI setup check\n")
print("1. Python")
check(f"Python {sys.version.split()[0]} at {sys.executable}", sys.version_info >= (3, 10),
      "select the 'rerouteai' conda environment as the project interpreter (Python 3.10+)")

print("\n2. Packages")
for name in ["numpy", "pandas", "sklearn", "streamlit", "altair", "pytest"]:
    try:
        mod = importlib.import_module(name)
        check(f"{name} {getattr(mod, '__version__', '')}", True)
    except ImportError:
        check(name, False, "conda env update -f environment.yml   (in Anaconda Prompt, inside this folder)")

print("\n3. Project folder")
check(f"working folder is {ROOT.name}", (ROOT / "rerouteai").is_dir() and pathlib.Path.cwd().resolve() == ROOT,
      "open the mis520-rerouteai folder itself as the PyCharm project, or set Working directory to it")
real = list((ROOT / "data" / "bts").glob("*.csv"))
print(f"  [INFO] BTS files in data/bts/: {len(real)} ({'real data will be used' if real else 'synthetic stand-in will be used'})")

if not ok:
    print("\nFix the items marked FAIL, then run this check again.")
    sys.exit(1)

print("\n4. Engine (the first run trains the delay model, about 10-60 seconds)")
sys.path.insert(0, str(ROOT))
from rerouteai import delay_model as D  # noqa: E402
from rerouteai.agent import run_agent  # noqa: E402
from rerouteai.scoring import PROFILES  # noqa: E402
from rerouteai.timetable import Disruption  # noqa: E402

t = time.perf_counter()
model = D.load()
check(f"delay model ready ({model.source}) in {time.perf_counter() - t:.1f} s", True)
run = run_agent(model, Disruption(), PROFILES["Business traveller"])
best = run.best
check(f"recommendation for the Zurich case: {' + '.join(f.id for f in best.itinerary.flights)} "
      f"({best.p_success:.0%} likely to work, ${best.total:,.0f} expected cost)", best is not None)

print("\nAll good. Next: run '3. Dashboard (Streamlit)' or '5. Build class simulator'.")
