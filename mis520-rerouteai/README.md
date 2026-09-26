# ReRouteAI — AI-assisted flight disruption recovery

MIS520 *AI with Business Application* (WPI, Fall 2026) — group project prototype.

> A passenger flying Boston → Zürich → Warsaw lands 95 minutes late and misses the connection.
> Which recovery route gives the best **expected** outcome, given arrival time, the chance each
> connection actually works, rebooking cost, passenger-rights rules, and **whose priorities count**?

ReRouteAI is a decision-support tool for an airline rebooking agent (and, in a later version, the
traveller). It **recommends and explains; a human approves**. Nothing is booked.

## Quick start

```bash
cd mis520-rerouteai
pip install -r requirements.txt
python evaluate.py          # trains the delay model, runs all evaluations -> docs/results.md
streamlit run app.py        # dashboard at http://localhost:8501
pytest -q tests             # 10 scenario tests
python build_simulator.py   # standalone class simulator -> simulator/ReRouteAI_Simulator.html
```

**Class presentation:** open `simulator/ReRouteAI_Simulator.html` in any browser (offline, no install) and follow
`simulator/PRESENTER_GUIDE.md`. The page re-solves 60 scenarios from the Python engine on load and shows whether it
matches.

Optional: `export GEMINI_API_KEY=...` to have Google Gemini write the explanations (the course's
recommended LLM). Without a key a deterministic template is used, so the demo never depends on
the network.

### Use real BTS data (needed before the final presentation)

1. Go to <https://www.transtats.bts.gov/> → Aviation → *Airline On-Time Performance Data* →
   *Reporting Carrier On-Time Performance (1987–present)*; download 12 monthly files (e.g. 2024).
2. Unzip the CSVs into `mis520-rerouteai/data/bts/`.
3. Delete `models/delay_model.pkl` and re-run `python evaluate.py`. The app and report will say
   "BTS on-time performance (real)" instead of "synthetic".

Until then every number in `docs/results.md` comes from **synthetic data in BTS format**. It proves
the pipeline works; it is not evidence about real flights.

## How it works (four layers, mapped to the course)

```
BTS history ──► [2] Delay model (gradient boosting, 11 delay buckets + cancelled)
                         │  P(connection works), P(cancel), expected delay
Timetable + MCT ─► [1] Time-expanded graph ──► Dijkstra / A* + route enumeration
                         │  feasible routes (MCT, seats = hard constraints)
                         ▼
                 Expected-cost optimizer (traveller or airline view, adjustable value of time,
                 EU261 step costs, fallback cascade if a plan fails)  ──► ranked options + baselines
                         │
Policy docs ──► [3] TF-IDF retrieval ──► Gemini / template explanation with citations
                         │
                [4] Agent log: detect → watch original → alternatives → risk → optimize → explain → propose
                         ▼
                 Human agent approves or overrides (reason logged)
```

| Layer | File | Course module |
|---|---|---|
| Time-expanded graph, Dijkstra, A* with admissible heuristic, infeasible = no edge | `rerouteai/graph.py` | Class 4 Search & optimization |
| One objective in dollars, probability × consequence, sensitivity analysis | `rerouteai/scoring.py` | Class 4 VectorDash case |
| Delay-distribution model, time-based hold-out, calibration | `rerouteai/delay_model.py`, `evaluate.py` | Module II supervised learning |
| Explicit rules: MCT, seat inventory, EU261 thresholds, protected vs. separate tickets | `timetable.py`, `scoring.py`, `policies/` | Class 3 knowledge representation |
| Retrieval-augmented explanation with citations | `rerouteai/rag.py` | Module III RAG |
| Multi-step agent with audit log and human approval | `rerouteai/agent.py`, `app.py` | Module III agentic AI |

### Key modelling choices

- **Additive search weights.** Connection probabilities multiply along a route; using −ln P turns
  them into a sum so Dijkstra/A* stay exact. A* uses "fastest remaining block time" as an
  admissible heuristic, and it expands fewer nodes than Dijkstra with the same answer (tested).
- **Seats and minimum connection times are hard constraints**, not probabilities. A rebooking
  agent sees inventory; the uncertainty is in delays and cancellations.
- **A failed plan is not free.** If a connection breaks, the traveller falls back to the next
  protected options in sequence (each with its own risk), or an overnight stay.
- **The original connection is watched, not recommended.** A 5% chance that the missed flight is
  itself late enough to catch is shown as a note; it is not a plan.
- **EU261 is a step function** (0 / €300 / €600 at 3 h and 4 h for this journey). That nonlinearity
  is why buying a competitor seat can be cheaper for the airline than a free partner reroute.

## Honest limitations

- Timetable, fares, seats and minimum connection times are **illustrative**. `AJ811 AlpenJet` is a
  fictional carrier. Replace with a documented timetable for a chosen date.
- A delay model trained on U.S. data is applied to European airports through transferable features
  (hour, month, weekday, distance, airport busyness percentile). This is a stated domain shift.
- Connection risk ignores the correlation between an inbound delay and the onward flight's delay
  (conservative), and fallback options are treated as independent.
- The legal summary in `policies/` is simplified and must be checked against the regulation.
