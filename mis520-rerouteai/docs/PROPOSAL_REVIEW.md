# ReRouteAI proposal — critical review and fixes

Reviewed: `ReRouteAI.pptx` and `ReRouteAI_Futuristic_Dashboard_Proposal.pptx` (same 9 slides; the second adds a
title image) against the MIS520 *Project Instructions*, *Course Overview*, *Syllabus*, and Classes 2–4.

## 0. Check these dates with Prof. Cheng first — the course documents disagree

| Item | Project Instructions (Class 1 slides) | Syllabus schedule | Your deck |
|---|---|---|---|
| Proposal | Wed **Sep 30** (Class #6) | **Oct 7** (Class 7) | Oct 7 |
| Final presentation | Wed **Dec 2** (Class #13) | **Dec 9** (Class 14) | Dec 9 |
| Written report | "Just slides, no written report" (Course Overview) | "comprehensive written report suitable for executive audiences" | — |
| Points | Participation 225 / HW 300 (Course Overview) | Participation 255 / HW 270 (Syllabus) | — |

Proposal = 100 pts, final = 150 pts, peer evaluation = 50 pts in both. Final slides are due **3 days after** the final
presentation and should let someone "understand and potentially recreate" the project. Plan for the **earlier** dates
until the instructor confirms.

## 1. Scorecard against the rubric

| Rubric item (Project Instructions) | In the deck? | Fix |
|---|---|---|
| Define the business problem | Yes (slides 2–3) | Tighten slide 2 wording (below) |
| **Specify the end users** | Weak: "travelers and airline staff" | Pick a primary user: **airline rebooking / disruption agents**. The traveller app is phase 2 |
| **Expected value / bottom-line impact** | Only a formula on slide 9 | Put a number on slide 3: cost per misconnected passenger and the EU261 step (€0 / €300 / €600) |
| One-sentence format "We will help [users] achieve [goal] by [AI], resulting in [benefit]" | Missing | Add to slide 3 (draft below) |
| Frame business → technical problem (input / processing / output) | Implicit (slide 4) | Label slide 4 as Input → Processing → Output |
| AI technologies | Yes | Name them: gradient boosting, time-expanded graph + Dijkstra/A*, RAG, agent workflow |
| **Relevant research / prior studies; similar solutions; what is unique** | **Missing** | New slide (below) |
| C1 real problem / C2 is AI right / C3 feasible | Not argued explicitly | New "Why AI" slide, or fold into slides 3 and 6 |
| Plan & timeline | Vague ("prototype through November") | Weekly milestones tied to the course modules (below) |
| Team responsibilities | Yes, good | Add names; add "how we collaborate" (GitHub repo, weekly check-in) |
| Success metrics: technical, **business**, **user experience** | Technical + business only | Add response time (< 1 s measured) and a 5-person user test |
| Testing approach | Partly | Held-out months + backtest + scenario tests |
| Ethics: bias, privacy, transparency, unintended consequences | Brief | Expand (section 4). Biggest point: **value of time can systematically disadvantage low-value travellers** |

Timing: slides 2–9 add up to 12 minutes (3 problem + 5 technical + 2 plan + 2 evaluation), which matches the
rubric. Keep it.

## 2. Slide-by-slide edits

**Slide 2 — The missed connection.** "An inbound delay causes the Warsaw connection to depart" reads as a mistake.
Suggested: *"A 95-minute inbound delay means the traveller lands after the Warsaw connection has left."*
Add one concrete cost line: *"Arrive 4 h late on a Boston→Warsaw ticket: up to €600 EU261 compensation per
passenger, plus meals or a hotel."*

**Slide 3 — Business question.** Add the one-sentence pitch:
> We will help **airline rebooking agents** choose the recovery route with the **lowest expected cost** for a
> misconnected passenger by **combining a delay-risk model, route search and policy retrieval**, which will
> **reduce compensation and care costs and cut decision time**, while showing the traveller's trade-offs transparently.

**Slide 4 — Architecture.** Show it as Input → Processing → Output, and add the human approval step at the end
(Class 2, slide 18: rule gate → model → validation → human approval).

**Slide 5 — Decision model.** Write the objective in dollars (VectorDash lesson: "one common score in dollars
makes very different outcomes comparable"):

`Expected cost = cash cost + value of time × expected delay + Σ P(fail at leg i) × cost of fallback + stop penalty [+ airline: E(EU261) + care]`

Avoid the "−λ·PreferenceMatch" term from the brainstorm version: it mixes units. Mention that search uses −ln P so
probabilities become additive and Dijkstra/A* stay exact.

**Slide 6 — Data.** Good that you state what you will *not* claim. Add: **run a second, all-U.S. scenario**
(e.g. BOS→ORD→MSP) where BTS data is real end to end, so you can **backtest on actual 2024 delays**. That turns the
final "Results & Metrics" section from simulation into evidence.

**Slide 7 — Demo.** Replace the placeholder options with what the prototype actually shows (illustrative timetable):

| Who | Recommended | Why |
|---|---|---|
| Student (value of time ≈ $0–10/h) | Next direct LX1348 14:20 | 96% reliable, free |
| Leisure ($25–100/h) | Via Vienna OS566 + OS627 | Earliest free option; 65% the tight connection works |
| Business / urgent (≥ $150/h) | Separate-ticket nonstop 11:15 | 97% reliable, $260, lands ~13:30 |
| Airline view, EU261 applies | Same separate-ticket nonstop | Buying a seat ($260) is cheaper than a €600 compensation step |
| Airline view, weather (EU261 exempt) | Late-evening LX1350 | No compensation risk, so the cheapest seat wins |

This is the Class 4 point made live: nothing about the flights changed; the objective did.

**Slide 8 — Plan.** Add names and the timeline in section 3.

**Slide 9 — Evaluation.** Add response time and user testing, and state your baselines (earliest arrival, lowest
fare, next direct on the same carrier).

## 3. New slide drafts

### "Why AI — and why now" (C1 / C2 / C3)
- **C1 real problem:** missed connections cost airlines rebooking, compensation and hotel costs, and cost travellers
  hours. [Add one sourced statistic, e.g. the share of flights arriving 15+ min late in your BTS year — compute it from
  the data you download.]
- **C2 AI is the right tool:** the decision is under uncertainty (needs prediction), combinatorial (needs search), and
  governed by text rules (needs retrieval). A fixed rule like "next direct flight" ignores all three — in our simulation
  it costs the most of any baseline.
- **C3 feasible:** public BTS data; small search graph; APIs for the LLM; a working prototype already exists.

### "Prior work and our edge" — verify every citation before using it
- Operations research on airline disruption management, e.g. Clausen, Larsen, Larsen & Rezanova (2010), *Disruption
  management in the airline industry — concepts, models and methods*, Computers & Operations Research; Bratu &
  Barnhart (2006), *Flight operations recovery: new approaches considering passenger recovery*, Journal of Scheduling.
- Flight-delay prediction with BTS data is a common ML benchmark (many papers; pick one you have read).
- Industry: airline apps that auto-rebook misconnected passengers; GDS/airline disruption-management tools; consumer
  delay-prediction features in travel search products.
- **Our edge:** a *transparent* expected-cost objective that (1) uses calibrated connection risk instead of the
  timetable alone, (2) prices regulatory step costs such as EU261, (3) lets the user set the time-vs-cost priority,
  (4) explains with cited policy text, and (5) always ends with human approval.

## 4. Ethics points worth adding (graders reward specificity)
- **Value-of-time bias.** If the airline plugs in value of time by fare class or status, low-fare travellers always get
  the slow option. Mitigation: apply the priority order in the rebooking policy first (minors, reduced mobility,
  medical), and use the passenger's *stated* priority rather than an inferred worth.
- **Automation bias.** Agents may rubber-stamp; the app requires a named approver and a written reason to override,
  and overrides are reviewed.
- **LLM hallucination about legal rights.** The explanation may only use retrieved policy text and optimizer numbers,
  with citations; the prototype has a no-LLM fallback.
- **Privacy.** Uses itinerary data only; no PNR names, no payment data; minimisation as on slide 9.
- **Unintended consequences.** Recommending separate tickets shifts risk to the traveller (no protection, re-check bags);
  the app labels such options explicitly.

## 5. Timeline tied to the course
| Dates (2026) | Course module | Milestone | Lead |
|---|---|---|---|
| by Oct 7 | Unsupervised learning / proposal | Proposal; BTS 2024 downloaded; prototype demo recorded as backup | All |
| Oct 14 | LLMs, prompt engineering | Real-BTS delay model + calibration report; explanation prompt tested | Model lead |
| Oct 21 | RAG | Real policy texts (EU261 text, carrier conditions of carriage) indexed; retrieval hit@3 ≥ 90% | Product lead |
| Oct 28 | Agentic AI & MCP | Agent log + tool calls; U.S. backtest scenario built | Optimization lead |
| Nov 4 | Computer vision & multimodal | Documented timetable for the Zürich case; sensitivity analysis | Data lead |
| Nov 11 | Ethics | Ethics review; 5-person user test (task time, agreement with expert choice) | Product lead |
| Nov 18–25 | Review / break | Freeze features; record backup demo video; rehearse | All |
| Dec 2 or Dec 9 | Final | 15 min: problem 3 / solution 4 / live demo 4 / results 4 | Demo driver |

## 6. Numbers from the prototype you can quote (label them as synthetic until re-run on real BTS)
From `docs/results.md`:
- **Traveller cases:** ReRouteAI had the lowest realised cost of all strategies — about $77 less than earliest-arrival
  and $233 less than "next direct, same carrier" per disruption. It still wins when delays are 50% worse than the model
  predicts.
- **Airline cases:** about $409 less than "next direct, same carrier" per passenger, but only about $6 better than
  simply taking the earliest arrival (and slightly worse when delays are underestimated). Say this openly: for the
  airline, earliest arrival is already a strong heuristic *because* EU261 rewards earliness. Our value over it is
  personalisation, explanation and risk visibility.
- **Delay model:** only modestly better than a lookup of "late rate by departure hour" (PR-AUC 0.33 vs 0.31).
  Schedule-only features carry limited signal. Real-time features (inbound aircraft delay, weather) are the upgrade path.
- **Retrieval:** 12/12 test questions find the right policy section in the top 3.
- **Search:** A* returns the same route as Dijkstra while expanding about half the nodes; full pipeline ≈ 0.2 s.
- **ROI formula:** (saving per passenger + agent time saved) × misconnected passengers per year − operating cost.
  The prototype's $20M/yr uses one illustrative network and an assumed 50,000 passengers; **present the formula and a
  range, not that figure**.

## 7. Likely questions in Q&A
1. *Is this just Google Flights?* No: it scores the chance each connection works, prices failure and
   compensation, and changes with whose cost counts.
2. *Your model is trained on U.S. data but the demo is in Europe.* Yes: a stated domain shift. The U.S. backtest
   scenario is where we prove it; the Zürich case is the motivating story.
3. *Where do seat availability and fares come from?* Illustrative in the prototype; in production from the airline's
   inventory system. We never claim live inventory.
4. *Why not let the LLM decide?* LLM fluency is not evidence (Class 2). It only explains numbers produced by the
   model and the optimizer, with citations.
5. *What if the recommendation is wrong?* A human approves every rebooking; overrides are logged and reviewed.
