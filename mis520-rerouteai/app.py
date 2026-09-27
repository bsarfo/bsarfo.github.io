"""ReRouteAI dashboard (Streamlit).   Run:  streamlit run app.py"""

import csv
import datetime as dt
import pathlib
from dataclasses import replace

import altair as alt
import pandas as pd
import streamlit as st

from rerouteai import delay_model as D
from rerouteai.agent import facts_text, run_agent
from rerouteai.rag import PolicyIndex, answer
from rerouteai.scoring import PROFILES, Assumptions
from rerouteai.timetable import CARRIER_NAMES, TIMETABLE, Disruption, hhmm

ROOT = pathlib.Path(__file__).resolve().parent
LOG = ROOT / "models" / "decision_log.csv"
# categorical slots 1-5 of the validated reference palette, dark-surface steps
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]

st.set_page_config(page_title="ReRouteAI", layout="wide")


@st.cache_resource
def get_model():
    return D.load()


@st.cache_resource
def get_index():
    return PolicyIndex()


model, index = get_model(), get_index()


def show(text: str) -> None:
    """Render plain text safely in markdown ($ would otherwise start LaTeX)."""
    st.markdown(text.replace("$", "\\$").replace("\n", "  \n"))

st.title("ReRouteAI")
st.caption("AI-assisted flight disruption recovery · decision support for one disrupted itinerary · "
           "prototype: timetable, fares and seats are illustrative; nothing is booked.")

with st.sidebar:
    st.header("Disruption")
    delay = st.slider("Inbound delay into Zürich (min)", 0, 300, 95, 5)
    bag = st.checkbox("Checked bag", True)
    month = st.selectbox("Month", list(range(1, 13)), index=6)
    st.header("Who is deciding?")
    perspective = st.radio("Optimize for", ["traveller", "airline"], horizontal=True)
    prof_name = st.selectbox("Traveller profile", list(PROFILES), index=2)
    base = PROFILES[prof_name]
    vot = st.slider("Priority: cost ← → time  (value of time, $/h)", 0, 500, int(base.value_of_time), 5,
                    help="How many dollars one hour of late arrival is worth to this traveller.")
    profile = replace(base, value_of_time=float(vot))
    st.header("Assumptions")
    eu = st.checkbox("EU261 compensation applies (airline-caused delay)", True)
    hotel = st.number_input("Hotel per night ($)", 0, 1000, 180, 10)
    st.caption(f"Delay model trained on: {model.source}")

d = Disruption(inbound_delay=delay, checked_bag=bag, month=month)
a = Assumptions(eu261_applies=eu, hotel=float(hotel))
run = run_agent(model, d, profile, perspective, a, index=index)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Journey", "BOS → WAW")
c2.metric("Lands in Zürich", hhmm(d.scheduled_in + d.inbound_delay), f"+{delay} min", delta_color="inverse")
c3.metric("Ready to board", hhmm(d.ready_time))
c4.metric("Original connection", "LX1346 08:25", "missed" if d.ready_time > 505 else "on",
          delta_color="inverse" if d.ready_time > 505 else "normal")

if not run.ranked:
    st.error("No feasible recovery route found. Escalate to a human agent.")
    st.stop()

best = run.best
fl = best.itinerary.flights
st.subheader("Recommendation")
r1, r2, r3, r4, r5 = st.columns([2.2, 1, 1, 1, 1])
r1.markdown(f"#### {best.itinerary.label}\n" + "  \n".join(
    f"**{f.id}** {CARRIER_NAMES.get(f.carrier, f.carrier)} · {f.origin} {hhmm(f.dep)} → {f.dest} {hhmm(f.arr)}"
    + ("" if f.protected else " · *separate ticket*") for f in fl))
r2.metric("Chance the plan works", f"{best.p_success:.0%}")
r3.metric("Expected arrival", hhmm(best.expected_arrival))
r4.metric("Expected delay", f"{best.expected_delay_min / 60:.1f} h")
r5.metric(f"Expected {perspective} cost", f"${best.total:,.0f}")
for f, p in run.catchable:
    st.info(f"Watching {f.id} ({hhmm(f.dep)}): {p:.0%} chance it leaves late enough to catch. "
            "Not relied on; the recommendation above stands if it departs on time.")

tab_rank, tab_why, tab_ask, tab_agent, tab_data = st.tabs(
    ["Ranked options", "Why this route", "Ask ReRouteAI", "Agent log", "Timetable & model"])

with tab_rank:
    rows = [s.row() for s in run.ranked]
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
    st.markdown("**Baselines** (deck slide 5)")
    base_rows = [{"Baseline": k, "Route": v.itinerary.label, "Flights": " + ".join(f.id for f in v.itinerary.flights),
                  "Expected cost ($)": round(v.total), "Extra vs recommendation ($)": round(v.total - best.total)}
                 for k, v in run.baselines.items() if v is not None]
    st.dataframe(pd.DataFrame(base_rows), hide_index=True, width="stretch")

with tab_why:
    st.markdown("**Expected cost breakdown, top 5 options** - the lowest total wins.")
    top = run.ranked[:5]
    parts = []
    for s in top:
        name = f"{s.itinerary.label} ({' + '.join(f.id for f in s.itinerary.flights)})"
        for comp, val in s.breakdown.items():
            parts.append({"Option": name, "Component": comp, "Cost ($)": round(val, 2)})
    comps = list(top[0].breakdown)
    chart = (alt.Chart(pd.DataFrame(parts))
             .mark_bar(cornerRadiusEnd=4, stroke="#0f1115", strokeWidth=2)
             .encode(y=alt.Y("Option:N", sort=[f"{s.itinerary.label} ({' + '.join(f.id for f in s.itinerary.flights)})"
                                               for s in top], title=None,
                             scale=alt.Scale(paddingInner=0.35), axis=alt.Axis(labelLimit=320, labelOverlap=False)),
                     x=alt.X("sum(Cost ($)):Q", title="Expected cost ($)"),
                     color=alt.Color("Component:N", scale=alt.Scale(domain=comps, range=SERIES[:len(comps)]),
                                     legend=alt.Legend(orient="top", title=None, labelLimit=320, columns=3)),
                     order=alt.Order("Component:N"),
                     tooltip=["Option", "Component", alt.Tooltip("Cost ($):Q", format="$,.0f")])
             .properties(height=330)
             .configure_axis(gridColor="#2a2a28", domainColor="#52514e", labelColor="#c3c2b7", titleColor="#c3c2b7")
             .configure_view(stroke=None))
    st.altair_chart(chart, width="stretch")
    st.markdown("**How the recommendation changes with the value of time** (same disruption):")
    sens = []
    for v in [0, 10, 25, 50, 100, 150, 250, 400]:
        r = run_agent(model, d, replace(profile, value_of_time=float(v)), "traveller", a, index=index).best
        sens.append({"Value of time ($/h)": v, "Recommended": r.itinerary.label,
                     "Flights": " + ".join(f.id for f in r.itinerary.flights),
                     "P(works)": f"{r.p_success:.0%}", "Traveller pays ($)": round(r.traveller_cash)})
    st.dataframe(pd.DataFrame(sens), hide_index=True, width="stretch")
    st.caption("Different priorities lead to different optimal solutions (Class 4). "
               "Search check: Dijkstra expanded {dijkstra_expanded} nodes, A* {astar_expanded}; same route: "
               "{same_route}.".format(**run.search_stats))

with tab_ask:
    show(run.explanation)
    st.caption(f"Explanation engine: {run.engine}. Set GEMINI_API_KEY to use Gemini; answers may only use "
               "retrieved policy text and the optimizer's numbers.")
    q = st.text_input("Ask a question", placeholder="I have checked luggage - am I owed compensation?")
    if q:
        text, hits, engine = answer(q, facts_text(run, d, profile, perspective), index)
        show(text)
        st.dataframe(pd.DataFrame([{"Section": c.id, "Heading": c.heading, "Similarity": round(s, 3)}
                                   for c, s in hits]), hide_index=True, width="stretch")

    st.markdown("#### Agent decision")
    with st.form("approve"):
        agent = st.text_input("Agent name")
        choice = st.radio("Decision", ["Approve recommendation", "Choose another option"], horizontal=True)
        alt_opt = st.selectbox("If another option, which?", [r["Route"] + " · " + r["Flights"] for r in rows])
        reason = st.text_area("Reason (required when overriding)")
        if st.form_submit_button("Record"):
            if not agent or (choice != "Approve recommendation" and not reason):
                st.error("Agent name, and a reason for overrides, are required.")
            else:
                new = not LOG.exists()
                LOG.parent.mkdir(exist_ok=True)
                with open(LOG, "a", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    if new:
                        w.writerow(["time", "agent", "inbound_delay", "profile", "perspective",
                                    "recommended", "decision", "chosen", "reason"])
                    w.writerow([dt.datetime.now().isoformat(timespec="seconds"), agent, delay, profile.name,
                                perspective, " + ".join(f.id for f in fl), choice,
                                alt_opt if choice != "Approve recommendation" else "", reason])
                st.success("Recorded. Overrides are reviewed weekly to recalibrate costs and rules.")

with tab_agent:
    st.dataframe(pd.DataFrame(run.steps), hide_index=True, width="stretch")
    st.caption(f"End-to-end runtime: {run.runtime_ms:.0f} ms")

with tab_data:
    st.markdown("Illustrative timetable (seats = seats left when rebooking; 0 = full, excluded).")
    st.dataframe(pd.DataFrame([{"Flight": f.id, "Carrier": CARRIER_NAMES.get(f.carrier, f.carrier),
                                "From": f.origin, "To": f.dest, "Dep": hhmm(f.dep), "Arr": hhmm(f.arr),
                                "Protected": f.protected, "Seats": f.seats, "Walk-up fare ($)": f.fare}
                               for f in TIMETABLE]), hide_index=True, width="stretch")
    res = ROOT / "docs" / "results.md"
    if res.exists():
        with st.expander("Evaluation results (docs/results.md)"):
            st.markdown(res.read_text(encoding="utf-8"))
