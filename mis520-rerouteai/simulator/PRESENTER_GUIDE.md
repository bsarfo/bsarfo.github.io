# ReRouteAI Simulator — presenter guide

Open `ReRouteAI_Simulator.html` in Chrome or Edge (works offline; no install). Press **P** for presenter mode,
then **→** to step through the 10 scenes. Rebuild after any engine change with `python build_simulator.py`.

Before class: open the file once on the presenting laptop, confirm the green **"Matches Python engine · 60/60"**
badge, and record a backup screen video.

| Key | Action |
|---|---|
| ← → | previous / next scene |
| P | presenter mode (hides the control rail, larger type) |
| R | run the simulation |
| 1–5 | Options · Simulation lab · Sensitivity · Search · Assumptions |

## Script (≈ 4 minutes for the live-demo slot)

| Scene | Say | Point at |
|---|---|---|
| 1 | "LX53 lands 95 minutes late. The 08:25 Warsaw flight is gone. ReRouteAI finds every reroute that respects connection times and seats, and ranks them by expected cost." | Red ✕ on the map, the recommendation board |
| 2 | "A student: every hour is worth little, so the free reroute wins." | Traveller pays $0 |
| 3 | "Same flights, a business traveller. Now paying $260 for a 97%-reliable nonstop is worth it." | Board changes to the separate-ticket nonstop |
| 4 | "Now the airline decides. EU261 jumps from €0 to €300 to €600 at 3 and 4 hours. Buying that seat keeps the passenger under the step." | Expected EU261 in the breakdown |
| 5 | "Weather delay: no compensation, so the airline's cheapest plan is a late flight on its own network." | Arrival time jumps to the evening |
| 6 | "Where does the answer flip? Each line is a route. Where lines cross, the recommendation changes." | The winner band and the crossings |
| 7 | "Promises are not results. We replay 1,000 random disruptions, drawing each flight's delay from the model." | Headline with confidence intervals |
| 8 | "What if our model is too optimistic? Delays 50% worse, same test." | Savings shrink but stay positive vs. the status quo |
| 9 | "Class 4: Dijkstra and A* on a time-expanded graph. −ln P makes risk additive, so the search stays exact. A* expands fewer nodes." | Node counts |
| 10 | "Every risk number comes from our trained model, and the page proves on load that it matches the Python engine." | Parity badge → open the report |

## How to defend it (likely questions)

**"Are these numbers real?"** The engine is real and tested; the inputs are labelled. Delay probabilities come from
our trained model (currently on synthetic BTS-format data; the badge says so and will switch when we load real BTS
files). Timetable, fares and seats are illustrative, and AlpenJet is fictional.

**"How do we know the browser demo is the same as your code?"** On load the page re-solves 60 scenarios the Python
engine solved and compares routes, costs, probabilities and search node counts. Click the badge for the report.

**"Isn't your simulation circular? You test the model with the model."** Partly, yes, and we say so. It tests the
*decision logic* under the model's uncertainty. That is why we include the stress test (delays 50% worse than
predicted), and why the final evaluation is a backtest on real 2024 BTS delays.

**"Why doesn't ReRouteAI beat 'lowest fare' in the lab?"** For a leisure traveller the cheapest free reroute is often the
same plan; the table shows how often the two pick the same route. The gains show up against the status-quo rule
("next direct on the same airline") and against "earliest arrival", which ignores risk. The result is reported with a
95% confidence interval, and "no significant difference" is shown when the interval includes zero.

**"Why expected cost and not just the earliest flight?"** Earliest-by-timetable ignores the chance a tight connection
fails and what the fallback costs. The lab shows "earliest arrival" costs more on average.

**"Isn't valuing time in dollars unfair?"** It can be. That is why the priority is set by the traveller, not inferred
from fare class, and why the airline's priority rules (minors, reduced mobility, medical) come first.

**"Why A* if Dijkstra already works?"** On this small network both are instant; A* matters at airline scale. The
heuristic (fastest remaining flying time) never overestimates, so A* is guaranteed to find the same best route.
