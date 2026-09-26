"""UnderwriteIQ web app (Streamlit).   Run:  streamlit run app.py"""

import csv
import datetime as dt
import pathlib

import pandas as pd
import streamlit as st

from underwriteiq import model as M
from underwriteiq.data import INDUSTRIES
from underwriteiq.decision import recommend
from underwriteiq.knowledge_base import rules_table
from underwriteiq.memo import draft_memo
from underwriteiq.scenarios import SCENARIOS

ROOT = pathlib.Path(__file__).resolve().parent
LOG = ROOT / "models" / "decision_log.csv"
COLOR = {"APPROVE": "green", "APPROVE WITH CONDITIONS": "blue", "REFER": "orange",
         "DECLINE": "red", "INCOMPLETE": "gray"}

st.set_page_config(page_title="UnderwriteIQ", layout="wide")


@st.cache_resource
def get_model():
    return M.load()


model = get_model()
st.title("UnderwriteIQ")
st.caption("Small-business loan underwriting copilot: captured expert rules + risk model + drafted memo. "
           "It recommends; the underwriter decides.")

tab_app, tab_kb, tab_log = st.tabs(["Assess an application", "Knowledge base", "Decision log"])

with tab_app:
    preset = st.selectbox("Load a scenario", ["(blank)"] + list(SCENARIOS))
    d = SCENARIOS.get(preset, SCENARIOS["Strong accounting firm (clean approve)"])
    num = lambda v, default: default if v is None else v  # noqa: E731

    with st.form("app"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("Request")
            industry = st.selectbox("Industry", list(INDUSTRIES), index=list(INDUSTRIES).index(d["industry"]))
            loan_amount = st.number_input("Loan amount ($)", 10_000, 5_000_000, int(d["loan_amount"]), 10_000)
            term = st.selectbox("Term (months)", [60, 84, 120, 300], index=[60, 84, 120, 300].index(d["term_months"]))
            years = st.number_input("Years in business", 0.0, 60.0, float(d["years_in_business"]), 0.5)
            franchise = st.checkbox("Franchise", d["franchise"])
        with c2:
            st.subheader("Financials")
            has_fin = st.checkbox("Financial statements provided", d["annual_revenue"] is not None)
            revenue = st.number_input("Annual revenue ($)", 0, 50_000_000, int(num(d["annual_revenue"], 0)), 10_000)
            ebitda = st.number_input("EBITDA ($)", -5_000_000, 20_000_000, int(num(d["ebitda"], 0)), 5_000)
            existing = st.number_input("Existing annual debt service ($)", 0, 5_000_000,
                                       int(d["existing_debt_service"]), 5_000)
            collateral = st.number_input("Collateral value ($)", 0, 10_000_000, int(d["collateral_value"]), 10_000)
        with c3:
            st.subheader("Credit & risk")
            credit = st.slider("Owner credit score", 300, 850, int(d["credit_score"]))
            delinq = st.number_input("Delinquencies (24 mo)", 0, 20, int(d["prior_delinquencies"]))
            util = st.slider("Revolving utilisation", 0.0, 1.0, float(d["revolving_utilization"]))
            bankruptcy = st.checkbox("Bankruptcy in last 7 years", d["bankruptcy_7y"])
            hazard = st.selectbox("Hazard zone", ["none", "wildfire", "flood"],
                                  index=["none", "wildfire", "flood"].index(d["hazard_zone"]))
            insured = st.checkbox("Hazard insurance in place", d["hazard_insurance"])
            fire = st.number_input("Months since fire-suppression certification (-1 = n/a)", -1, 120,
                                   int(d["fire_cert_months"]))
        submitted = st.form_submit_button("Assess", type="primary")

    if submitted or preset != "(blank)":
        app = dict(loan_amount=loan_amount, term_months=term, industry=industry, years_in_business=years,
                   employees=d["employees"], annual_revenue=revenue if has_fin else None,
                   ebitda=ebitda if has_fin else None, existing_debt_service=existing, credit_score=credit,
                   collateral_value=collateral, prior_delinquencies=delinq, revolving_utilization=util,
                   franchise=franchise, urban=True, hazard_zone=hazard, hazard_insurance=insured,
                   fire_cert_months=fire, bankruptcy_7y=bankruptcy)
        rec = recommend(app, model)

        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"### :{COLOR[rec.decision]}[{rec.decision}]")
        m2.metric("Risk grade (1 best - 10 worst)", rec.grade if rec.grade else "-")
        m3.metric("Probability of default", f"{rec.pd:.1%}" if rec.pd is not None else "-")
        m4.metric("DSCR", f"{rec.facts.get('dscr', '-')}x")
        st.info(rec.headline)

        left, right = st.columns(2)
        with left:
            for title, items, fn in [("Information required", rec.asks, st.warning),
                                     ("Policy hard stops", rec.hard_stops, st.error),
                                     ("Conditions before booking", rec.conditions, st.warning),
                                     ("Review items", rec.flags, st.warning),
                                     ("Escalation", rec.referrals, st.warning),
                                     ("Compensating factors", rec.mitigants, st.success)]:
                if items:
                    fn(f"**{title}**\n\n" + "\n".join(f"- {m}" for m in items))
            if rec.reasons:
                st.markdown("**Main model risk drivers**")
                st.dataframe(pd.DataFrame(rec.reasons), hide_index=True, width="stretch")
        with right:
            st.markdown("**Why: rule trace (audit trail)**")
            st.dataframe(pd.DataFrame(rec.trace)[["rule", "name", "action", "evidence"]]
                         if rec.trace else pd.DataFrame(), hide_index=True, width="stretch")

        with st.expander("Draft credit memo", expanded=True):
            text, engine = draft_memo(app, rec)
            st.caption(f"Drafted by: {engine}. Verify every figure before use.")
            st.text(text) if engine == "template" else st.markdown(text)

        st.markdown("#### Underwriter decision")
        with st.form("decide"):
            who = st.text_input("Underwriter name")
            final = st.radio("Final decision", ["Accept recommendation", "Override"], horizontal=True)
            why = st.text_area("Override rationale (required for overrides)")
            if st.form_submit_button("Record decision"):
                if not who or (final == "Override" and not why):
                    st.error("Name, and a rationale for overrides, are required.")
                else:
                    new = not LOG.exists()
                    LOG.parent.mkdir(exist_ok=True)
                    with open(LOG, "a", newline="") as fh:
                        w = csv.writer(fh)
                        if new:
                            w.writerow(["timestamp", "underwriter", "industry", "loan_amount",
                                        "recommendation", "grade", "final", "rationale"])
                        w.writerow([dt.datetime.now().isoformat(timespec="seconds"), who, industry,
                                    loan_amount, rec.decision, rec.grade, final, why])
                    st.success("Recorded. Overrides feed the monthly rule-review meeting.")

with tab_kb:
    st.markdown("Every rule is readable, sourced and versioned, so credit officers can review and "
                "update the captured expertise without touching code.")
    st.dataframe(pd.DataFrame(rules_table()), hide_index=True, width="stretch")

with tab_log:
    if LOG.exists():
        log = pd.read_csv(LOG)
        st.metric("Override rate", f"{(log['final'] == 'Override').mean():.0%}")
        st.dataframe(log, hide_index=True, width="stretch")
    else:
        st.write("No decisions recorded yet.")
