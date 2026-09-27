"""Run the ReRouteAI agent once and print every step (no dashboard).

    python demo_agent.py

Change the settings below and run again to see how the recommendation changes.
"""

from rerouteai import delay_model as D
from rerouteai.agent import run_agent
from rerouteai.scoring import PROFILES, Assumptions
from rerouteai.timetable import Disruption, hhmm

# ---- try changing these ----------------------------------------------------
INBOUND_DELAY = 95                  # minutes late into Zurich
PROFILE = "Business traveller"      # "Student (cost first)", "Leisure traveller", "Business traveller", "Urgent (medical / family)"
PERSPECTIVE = "traveller"           # "traveller" or "airline"
EU261_APPLIES = True                # False = weather delay, no compensation owed
QUESTION = "I have a checked bag. What should I do, and am I owed compensation?"
# ------------------------------------------------------------------------------

model = D.load()
d = Disruption(inbound_delay=INBOUND_DELAY)
run = run_agent(model, d, PROFILES[PROFILE], PERSPECTIVE, Assumptions(eu261_applies=EU261_APPLIES),
                question=QUESTION)

print(f"\nDelay model trained on: {model.source}")
print(f"Scenario: LX53 lands {INBOUND_DELAY} min late; {PROFILE}; optimizing for the {PERSPECTIVE}\n")

print("AGENT STEPS")
for s in run.steps:
    print(f"  {s['step']}. {s['action']}: {s['result']}")

print("\nTOP 5 OPTIONS (lowest expected cost first)")
for i, s in enumerate(run.ranked[:5], 1):
    flights = " + ".join(f.id for f in s.itinerary.flights)
    print(f"  {i}. {s.itinerary.label:<18} {flights:<17} works {s.p_success:4.0%}   "
          f"arrives {hhmm(s.arrival_if_ok):>8}   expected cost ${s.total:,.0f}")

print("\nBASELINES")
for name, s in run.baselines.items():
    if s is not None:
        print(f"  {name:<32} {' + '.join(f.id for f in s.itinerary.flights):<17} "
              f"${s.total:,.0f}  (+${s.total - run.best.total:,.0f} vs recommendation)")

print(f"\nEXPLANATION ({run.engine})\n{run.explanation}")
print(f"\nDone in {run.runtime_ms:.0f} ms.")
