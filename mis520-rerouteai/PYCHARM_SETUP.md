# Run ReRouteAI in PyCharm with Anaconda

About 20 minutes the first time. Works on Windows and macOS.

**What you get:** five green ▶ run buttons in PyCharm.

| Button | What it does | Time |
|---|---|---|
| 1. Check setup | Confirms Python, packages and folder are right; trains the delay model | ~30 s |
| 2. Evaluate | Trains and tests the model, runs the simulations, writes `docs/results.md` | ~1–2 min |
| 3. Dashboard (Streamlit) | Opens the agent dashboard in your browser | stays running |
| 4. Tests | Runs the 10 scenario tests | ~5 s |
| 5. Build class simulator | Rebuilds `simulator/ReRouteAI_Simulator.html` from the Python engine | ~1 min |

---

## Step 1 — Install the tools (skip what you already have)

- **Anaconda Distribution:** <https://www.anaconda.com/download>. On Windows, keep the default "Just Me" install.
- **PyCharm** (Community edition is fine): <https://www.jetbrains.com/pycharm/download>
- **Git** (only for option A below): <https://git-scm.com/downloads>

## Step 2 — Get the code

The code is on the branch **`claude/fintech-ai-application-project-v1euzs`** of `github.com/bsarfo/bsarfo.github.io`
(pull request #3). Pick one:

**A. From PyCharm (recommended, keeps you in sync with the team)**
1. PyCharm welcome screen → **Clone Repository** (or *Get from VCS*).
2. URL: `https://github.com/bsarfo/bsarfo.github.io.git`, choose a folder, **Clone**.
3. When it opens, bottom-right branch widget → **Remote branches** →
   `origin/claude/fintech-ai-application-project-v1euzs` → **Checkout**.
4. Close this project (**File → Close Project**). You will reopen just the app folder in step 4.

**B. As a ZIP (no Git needed)**
1. Go to `https://github.com/bsarfo/bsarfo.github.io/tree/claude/fintech-ai-application-project-v1euzs`
2. **Code → Download ZIP**, then unzip it somewhere simple, e.g. `Documents\MIS520\`.

Either way you now have a folder containing **`mis520-rerouteai`**.

## Step 3 — Create the conda environment

Open **Anaconda Prompt** (Windows: Start menu) or **Terminal** (macOS), then:

```bash
cd path/to/bsarfo.github.io/mis520-rerouteai
conda env create -f environment.yml
conda activate rerouteai
python verify_setup.py
```

`verify_setup.py` should end with **"All good."** If `conda env create` says the environment already exists, run
`conda env update -f environment.yml` instead.

> Windows tip: to paste a path, Shift + right-click the folder in File Explorer → **Copy as path**, then type `cd `
> and paste.

## Step 4 — Open the app folder in PyCharm

1. **File → Open** → select the **`mis520-rerouteai`** folder itself (not the parent `bsarfo.github.io`
   folder) → **Open** → **Trust Project**.
   Opening this exact folder is what makes the run buttons and imports work.
2. Set the interpreter to the conda environment:
   - Bottom-right corner, click the interpreter name (it may say *No interpreter*) →
     **Add New Interpreter → Add Local Interpreter → Conda Environment**.
   - Choose **Use existing environment** → select **`rerouteai`** → **OK**.
   - If PyCharm cannot find conda, set **Path to conda** to:
     - Windows: `C:\Users\<you>\anaconda3\Scripts\conda.exe` (or `...\anaconda3\condabin\conda.bat`)
     - macOS: `~/anaconda3/bin/conda` (or `/opt/anaconda3/bin/conda`)
3. Wait for indexing to finish (progress bar at the bottom).

## Step 5 — Run it

Open the run dropdown at the top right (next to the green ▶). You will see the five configurations. Run them in
this order the first time:

1. **1. Check setup** → should end with "All good."
2. **2. Evaluate** → prints the results tables; saved to `docs/results.md`.
3. **4. Tests** → `10 passed`.
4. **3. Dashboard (Streamlit)** → the Run window shows `Local URL: http://localhost:8501`. Your browser usually
   opens by itself; if not, click the link. Stop it with the red ■ square.
5. **5. Build class simulator** → then open `simulator/ReRouteAI_Simulator.html` in Chrome or Edge
   (right-click the file in PyCharm → **Open In → Browser**). This is the presentation version and needs no Python.

> Don't see the five configurations? You opened the wrong folder (see step 4.1), or PyCharm hasn't loaded them yet:
> **File → Reload All from Disk**.

## Step 6 (before the final presentation) — Use real BTS data

1. <https://www.transtats.bts.gov/> → *Aviation* → *Airline On-Time Performance Data* →
   *Reporting Carrier On-Time Performance (1987–present)* → download the 12 monthly files for 2024.
2. Unzip the CSVs into `mis520-rerouteai/data/bts/` (create the folder).
3. Delete `models/delay_model.pkl`, then run **2. Evaluate** and **5. Build class simulator** again.
   The dashboard and simulator badge will switch from "synthetic" to "U.S. BTS".

Twelve monthly files are about 7 million rows; training needs roughly 4–8 GB of RAM. On a smaller laptop, start with
3–6 months.

## Optional — Gemini explanations in the dashboard

1. Get a key at <https://aistudio.google.com/apikey>.
2. In Anaconda Prompt: `conda activate rerouteai` then `pip install google-genai`.
3. In PyCharm: run dropdown → **Edit Configurations → 3. Dashboard (Streamlit) → Environment variables** → add
   `GEMINI_API_KEY=your-key`. Never commit the key to GitHub.

Without a key the dashboard uses a built-in template, so the demo always works.

---

## Troubleshooting

| You see | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'rerouteai'` | You opened the parent folder. Open `mis520-rerouteai` itself (step 4), or set **Working directory** in the run configuration to that folder. |
| `No module named streamlit / sklearn / pandas` | PyCharm is using the wrong interpreter. Bottom-right → choose **rerouteai** (step 4.2). |
| Run configurations show a red ✕ or "module not specified" | **Edit Configurations** → for each one set **Python interpreter** to *rerouteai* and **Working directory** to the `mis520-rerouteai` folder. |
| `conda` is not recognised (Windows) | Use **Anaconda Prompt**, not the normal Command Prompt or PowerShell. |
| `Port 8501 is already in use` | A dashboard is already running: stop it with ■, or open <http://localhost:8501>. |
| Browser doesn't open | Copy `http://localhost:8501` from the Run window into your browser. |
| Windows Firewall pop-up for Python | Allow on *Private networks*. The app only listens on your own computer. |
| `UnicodeDecodeError` / `UnicodeEncodeError` | Run `conda env update -f environment.yml` (it turns on UTF-8 mode), then restart PyCharm. |
| `Engine parity` badge in the simulator is amber | Rebuild with **5. Build class simulator** after any change to the Python engine. |
| Evaluate is slow | Normal on first run (about 1–2 minutes). The simulation in `evaluate.py` is the slow part. |

## Project map

```
mis520-rerouteai/
├── rerouteai/             the engine
│   ├── bts.py             BTS data loader + synthetic stand-in
│   ├── delay_model.py     gradient-boosting delay model
│   ├── timetable.py       airports, connection times, illustrative flights
│   ├── graph.py           time-expanded graph, Dijkstra / A*, fallback
│   ├── scoring.py         expected cost, EU261, baselines
│   ├── rag.py             policy retrieval + Gemini/template explanation
│   └── agent.py           step-by-step agent with audit log
├── policies/              texts the retrieval searches
├── app.py                 Streamlit dashboard            (button 3)
├── evaluate.py            model + decision evaluation    (button 2)
├── build_simulator.py     builds the class simulator     (button 5)
├── simulator/             ReRouteAI_Simulator.html + PRESENTER_GUIDE.md
├── tests/                 scenario tests                 (button 4)
├── verify_setup.py        setup check                    (button 1)
├── environment.yml        conda environment
└── .run/                  the five PyCharm run buttons
```
