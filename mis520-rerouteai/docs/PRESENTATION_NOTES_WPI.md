# ReRouteAI proposal — presentation notes (WPI template deck)

Deck: `docs/ReRouteAI_Proposal_WPI.pptx` · 11 presented slides in 12 minutes + appendix for Q&A.
Speaking pace: about 130 words per minute. The scripts below are drafts: say them in your own words.

## Suggested speaker split (change freely)

| Speaker | Slides | Time |
|---|---|---|
| Agnieszka | 1–3 (title, crisis, agent dilemma) | 0:00–2:00 |
| Delice | 4–5, 7 (why AI, how it works, scoring) | 2:00–3:40, 4:50–6:00 |
| Regina | 6, 10 (prediction, evaluation) | 3:40–4:50, 10:00–11:00 |
| Kofi | 8, 11 (live demo, ethics) | 6:00–8:00, 11:00–12:00 |
| All | 9 (each person states their own role) | 8:00–10:00 |

Before class: open `simulator/ReRouteAI_Simulator.html` in Chrome, check the green "60/60" badge, press **P**
(presenter mode), leave it on scene 1. Have the backup demo video on the desktop.

---

## Slide 1 — Title · a few seconds · Agnieszka

**Say:** "Good evening. We are Agnieszka, Regina, Delice and Kofi, and this is ReRouteAI, an AI assistant for
recovering from flight disruptions. Everything we show today runs in a working prototype."

**Transition:** "Let me start with the situation that gave us the idea."

---

## Slide 2 — The crisis: a missed connection · 0:00–1:00 · Agnieszka

**Goal:** make the problem concrete and put a price on it.

**Say:** "One of us flew Boston to Zürich to Warsaw. The Boston flight landed 95 minutes late. With passport control
and a checked bag, the earliest the passenger could board again was 9:50, and the Warsaw flight had already left.
At that moment an airline rebooking agent has a few minutes to choose between 18 possible recovery paths, through
Frankfurt, Vienna, Munich, or a later direct flight. And there is money on the line: under the European regulation
EU261, if the passenger reaches Warsaw more than 3 hours late the airline owes 300 euros, and more than 4 hours late,
600 euros, per passenger."

**Point to:** the red ✕ between Zürich and Warsaw, then the three numbers.

**Transition:** "So how do agents decide today?"

---

## Slide 3 — The agent dilemma · 1:00–2:00 · Agnieszka

**Goal:** show why the current default is not good enough, backed by research.

**Say:** "Under time pressure, agents fall back on one rule: book the next flight on our own airline. It's simple, but
it ignores three things. First, the new connection can also fail. Second, a seat on another airline might arrive hours
earlier. Third, hotel, meal and compensation costs keep growing with every hour of delay. Recent research agrees: Lu and
colleagues showed in 2025 that how passengers are transferred drives the cost of recovery, and that recovering every
flight isn't always the cheapest option. A 2025 review by Wu and colleagues calls for real-time recovery that handles
uncertainty and human factors. So our goal is simple: help the agent choose the route with the lowest expected total
cost, while the agent stays in charge."

**Point to:** the red goal banner at the bottom.

**Transition:** "Delice will explain why this needs AI rather than a better rule."

---

## Slide 4 — Why AI · 2:00–3:00 · Delice

**Goal:** pass the course test: real problem, AI is the right tool, feasible.

**Say:** "Three problems are tangled together here, and a fixed rule can't handle any of them. First, delay
uncertainty: the timetable assumes flights land on time, so we use machine learning to estimate the real chance.
Second, the number of possible routes: dozens of flights and connection times, which graph search handles in
milliseconds. Third, strict regulations: EU261, rebooking and baggage rules, which we retrieve and cite instead of
guessing. And this isn't rare: in 2023, 21.3 percent of U.S. flights were delayed and 1.65 percent cancelled."

**Point to:** the table row by row, then the statistic.

**If asked "why not just a rule?":** "Our simulation shows the 'next direct flight' rule costs the most of all the
strategies we tested."

**Transition:** "Here is how the pieces fit together."

---

## Slide 5 — How ReRouteAI works · 3:00–3:40 · Delice

**Goal:** a 40-second map of the system before the detail.

**Say:** "It works in three steps. Predict the real risk of each connection. Score every feasible route by its total
cost. Recommend the best one with an explanation. And the most important part is at the bottom: the human agent
decides. They approve the recommendation or pick another option, every override is logged with a reason, and nothing
is booked automatically."

**Transition:** "Regina will take step one."

---

## Slide 6 — Step 1: Predict real connection risk · 3:40–4:50 · Regina

**Goal:** explain the machine-learning part in plain terms.

**Say:** "Airline timetables assume every flight lands on time. Ours doesn't. We train a gradient-boosting model on
U.S. Bureau of Transportation Statistics history. Instead of a yes-or-no 'late' label, it predicts the whole range of
delays, from on time to more than five hours late, plus cancellation. We use features like the hour of the flight,
month, weekday, distance and how busy the airport is, and we test on months the model has never seen. Here's why it
matters: the Vienna route has a 50-minute connection. On the timetable that's a 100 percent connection. Our model says
about 65 percent."

**Point to:** 100% versus 65% on the right.

**If asked about the data:** "The prototype currently uses synthetic data in the BTS format; in October we retrain on
the real 2024 BTS files."

**Transition:** "Once we know the risk, Delice will explain how we choose."

---

## Slide 7 — Step 2: Score routes by total cost · 4:50–6:00 · Delice

**Goal:** explain the optimization and the EU261 step.

**Say:** "First, graph search removes routes that are impossible, for example connections shorter than the airport's
minimum connection time, or full flights. Then every remaining route gets one score in dollars: the ticket price, the
value of the traveller's time, and the risk of missing a connection and ending up on a worse flight. For the airline we
add the compensation, meals and hotel. Look at the table on the right: compensation doesn't grow smoothly, it jumps.
Under 3 hours it's zero, 3 to 4 hours it's 300 euros, over 4 hours it's 600. Just like the late-delivery penalty in
the VectorDash case, a few minutes can change the best answer. We also tested two search algorithms: A* finds the same
best route as Dijkstra while checking half as many options."

**Point to:** the three rows of the EU261 table.

**Transition:** "Kofi will now show it live."

---

## Slide 8 — Step 3: Recommend and adapt (live demo) · 6:00–8:00 · Kofi

**Goal:** show that the answer changes with the objective, and that the agent stays in control.

**Do:** switch to the simulator (already in presenter mode) and use **→** through scenes 1–5.

**Say (while clicking):**
- Scene 1: "Same disruption as before. For a leisure traveller, the best plan is a free reroute through Vienna."
- Scene 2: "For a student, who cares most about cost, the recommendation stays free."
- Scene 3: "For a business traveller, whose time is worth much more, the system now recommends a 260-dollar nonstop
  that's 97 percent reliable."
- Scene 4: "Now the airline's view. Paying 260 dollars for that seat is cheaper than paying 600 euros of compensation,
  so the airline should buy it."
- Scene 5: "If the delay was caused by weather, no compensation is owed, and the airline's cheapest plan becomes a
  late-evening flight. That tension is exactly why a human agent approves every decision."

**Back on the slide, point to** the last row of the table: the agent approves or overrides, and the reason is logged.

**If the demo fails:** play the backup video; don't troubleshoot live.

**Transition:** "Here's how we'll get from prototype to final product."

---

## Slide 9 — Roadmap and roles · 8:00–10:00 · all (about 30 seconds each)

**Goal:** a believable plan with named owners.

**Say (one person on the timeline, then each person their role):**
"In October we retrain the delay model on real BTS data and build the policy retrieval. In November we build the
agent workflow, test decisions on real U.S. history, and run a five-person user test. December is final delivery."
- Agnieszka: "I own the data and the timetable."
- Regina: "I own the machine-learning delay model."
- Delice: "I own the graph search and the cost model."
- Kofi: "I own the interface, the policy retrieval and the ethics review."
"We work in one shared GitHub repository, meet weekly, and every change is reviewed by a second teammate."

**Transition:** "Regina will explain how we'll prove it works."

---

## Slide 10 — How we will evaluate it · 10:00–11:00 · Regina

**Goal:** show you'll measure business value, not just accuracy, and be honest about early results.

**Say:** "We compare against the rules agents use today: earliest arrival, lowest fare, and the current default, the
next direct flight on the same airline. We measure cost saved per disruption, how many passengers arrive within three
hours, response time, which is about 0.2 seconds in the prototype, and a user test with five people. The chart is an
early result from simulated disruptions: ReRouteAI had the lowest average cost, 729 dollars against 962 for the current
default. To be clear, this uses synthetic data. The real test is the backtest on 2024 BTS delays."

**Point to:** the red bar versus the grey "Next direct" bar.

**If asked "is the simulation circular?":** "Partly, yes: it tests the decision logic using the model's own
uncertainty. That's why we also stress-test with delays 50 percent worse than predicted, and why the final evaluation
uses real historical delays."

**Transition:** "Finally, Kofi on how we keep this responsible."

---

## Slide 11 — Ethics and safeguards · 11:00–12:00 · Kofi

**Goal:** three specific safeguards, then open for questions.

**Say:** "Three safeguards. First, human in the loop: this is decision support only; a named agent signs off every
rebooking, and overrides are logged and reviewed. Second, equity: if we let value of time drive everything, passengers
on cheap tickets would always wait longest, so priority rules for minors, medical needs and reduced mobility come first.
Third, legal accuracy: the explanation can only use retrieved, cited policy text, so the system can't invent passenger
rights. We also use itinerary data only, and we label separate-ticket options clearly. Thank you. We're happy to take
questions."

---

## Appendix slides — use only when asked

| Slide | Use it when someone asks… | Short answer |
|---|---|---|
| Appendix A · Prior work | "What's new compared with research?" | Most research re-plans the whole airline schedule with fixed passenger costs. We decide for one passenger in real time, with a probability for each connection, other-airline seats and EU261 in one score, and a human approving. |
| Appendix B · Data | "Where does the data come from?" | U.S. BTS TranStats on-time data (currently a synthetic stand-in in the same format); a U.S. backtest scenario; the Zürich timetable is illustrative. We don't claim live seat inventory. |
| Appendix C · References | "What are your sources?" | Point to the list; the two 2025 papers are the most recent. |

## Other questions to prepare for

- **"Why the airline agent and not the traveller?"** The agent can act on the answer (buy another airline's seat,
  issue vouchers), the airline pays the costs, and the airline has the seat data. A traveller app is phase two.
- **"Doesn't this just save the airline money at the passenger's expense?"** Both views are shown side by side; when
  compensation applies, the airline's incentive is to get the passenger there sooner; vulnerable passengers come
  first; the passenger's own priority is used.
- **"What is RAG?"** Retrieval-augmented generation: the system looks up the relevant policy section first, then writes
  the answer only from that text, with a citation.
- **"Is the 65% real?"** It comes from the prototype model on synthetic data; it will change when we retrain on real BTS
  data. The method is what we're proposing.
