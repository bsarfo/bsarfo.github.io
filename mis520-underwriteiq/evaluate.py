"""Evaluate UnderwriteIQ: technical, business and fairness metrics.

Compares three underwriting policies on a held-out test portfolio:
  A. Checklist   - what a junior underwriter does with the standard checklist (Alex)
  B. Model only  - approve if predicted risk grade <= 5
  C. UnderwriteIQ - knowledge-base rules + model + escalation (hybrid)

Run:  python evaluate.py        (writes docs/results.md and models/pd_model.pkl)
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

from underwriteiq import inference
from underwriteiq import model as M
from underwriteiq.data import generate_portfolio
from underwriteiq.decision import APPROVE_MAX_GRADE, DECLINE_MIN_GRADE, pd_to_grade

ROOT = pathlib.Path(__file__).resolve().parent

# ---- business assumptions (state them on the slide; change them here) ----
NET_SPREAD = 0.03        # annual net interest margin earned on a performing loan
AVG_LIFE_YEARS = 3.0     # average outstanding life after amortisation / prepayment
BASE_LGD = 0.60          # loss given default with no collateral
COMMITTEE_APPROVES_UP_TO_GRADE = 6  # assumption for referred loans in the simulation


def ks_stat(y, p) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def hybrid_decisions(test: pd.DataFrame, pd_hat: np.ndarray) -> pd.Series:
    out = []
    for app, p in zip(test.to_dict("records"), pd_hat):
        inf = inference.run(app)
        acts = {f.rule.action for f in inf.fired}
        grade = min(10, max(1, pd_to_grade(p) + inf.notch))
        if "ask" in acts:
            d = "INCOMPLETE"
        elif "hard_stop" in acts or grade >= DECLINE_MIN_GRADE:
            d = "DECLINE"
        elif "hold" in acts:
            d = "HOLD"  # not booked until the condition is cleared, whoever approves it
        elif "refer" in acts or grade > APPROVE_MAX_GRADE:
            d = "REFER" if grade <= COMMITTEE_APPROVES_UP_TO_GRADE else "REFER-DECLINED"
        elif "flag" in acts:
            d = "APPROVE WITH CONDITIONS"
        else:
            d = "APPROVE"
        out.append(d)
    return pd.Series(out, index=test.index)


def economics(df: pd.DataFrame, approved: pd.Series) -> dict:
    a = df[approved]
    cov = (a["collateral_value"] / a["loan_amount"]).clip(0, 1)
    lgd = BASE_LGD * (1 - 0.5 * cov)
    income = (a["loan_amount"] * NET_SPREAD * AVG_LIFE_YEARS * (1 - a["default"])).sum()
    loss = (a["loan_amount"] * lgd * a["default"]).sum()
    return {
        "approval_rate": float(approved.mean()),
        "loans_approved": int(approved.sum()),
        "default_rate_of_approved": float(a["default"].mean()) if len(a) else 0.0,
        "credit_losses_$": float(loss),
        "interest_income_$": float(income),
        "net_profit_$": float(income - loss),
    }


def fairness(df: pd.DataFrame, approved: pd.Series) -> dict:
    rates = approved.groupby(df["minority_owned"]).mean()
    return {"approval_rate_minority_owned": float(rates.get(True, np.nan)),
            "approval_rate_other": float(rates.get(False, np.nan)),
            "adverse_impact_ratio": float(rates.min() / rates.max())}


def main() -> dict:
    df = generate_portfolio()
    train, test = train_test_split(df, test_size=0.3, random_state=7, stratify=df["default"])
    Xtr, Xte = M.build_features(train), M.build_features(test)

    lr = M.make_logistic().fit(Xtr, train["default"])
    gb = M.make_boosting().fit(Xtr, train["default"])
    tacit = ["uninsured_cat", "stale_fire_cert"]
    lr_no_tacit = M.make_logistic()
    Xtr_nt, Xte_nt = Xtr.copy(), Xte.copy()
    Xtr_nt[tacit] = 0.0
    Xte_nt[tacit] = 0.0
    lr_no_tacit.fit(Xtr_nt, train["default"])

    p_lr, p_gb = lr.predict_proba(Xte)[:, 1], gb.predict_proba(Xte)[:, 1]
    p_nt = lr_no_tacit.predict_proba(Xte_nt)[:, 1]
    technical = {name: {"AUC": roc_auc_score(test["default"], p), "KS": ks_stat(test["default"], p),
                        "Brier": brier_score_loss(test["default"], p)}
                 for name, p in [("Logistic regression (deployed)", p_lr), ("Gradient boosting (benchmark)", p_gb),
                                 ("Logistic without captured expert features", p_nt)]}

    facts = pd.DataFrame([inference.derive_ratios(r) for r in test.to_dict("records")], index=test.index)
    checklist = (test["credit_score"] >= 640) & (facts["dscr"] >= 1.25) & ~test["bankruptcy_7y"]
    grades = pd.Series([pd_to_grade(p) for p in p_lr], index=test.index)
    model_only = grades <= APPROVE_MAX_GRADE
    hybrid = hybrid_decisions(test, p_lr)
    hybrid_approved = hybrid.isin(["APPROVE", "APPROVE WITH CONDITIONS", "REFER"])

    policies = {"A. Checklist (status quo)": checklist, "B. Model only": model_only,
                "C. UnderwriteIQ hybrid": hybrid_approved}
    business = {k: economics(test, v) for k, v in policies.items()}
    fair = {k: fairness(test, v) for k, v in policies.items()}

    cat = facts.index[(test["hazard_zone"] != "none") & ~test["hazard_insurance"]
                      & test["industry"].isin(["Winery / Agriculture", "Hospitality / Lodging",
                                               "Construction", "Restaurant / Food Service"])]
    apex = {"uninsured_cat_exposed_loans_in_test": int(len(cat)),
            "their_default_rate": float(test.loc[cat, "default"].mean()),
            "approved_by_checklist": int(checklist.loc[cat].sum()),
            "approved_by_model_only": int(model_only.loc[cat].sum()),
            "approved_by_model_without_expert_features": int(
                (pd.Series([pd_to_grade(p) for p in p_nt], index=test.index) <= APPROVE_MAX_GRADE).loc[cat].sum()),
            "booked_by_hybrid_without_insurance": int(hybrid_approved.loc[cat].sum())}

    workload = hybrid.value_counts(normalize=True).round(4).to_dict()

    M.save(M.train(train))
    results = {"test_size": int(len(test)), "portfolio_default_rate": float(test["default"].mean()),
               "technical": technical, "business": business, "fairness": fair, "apex_case": apex,
               "hybrid_decision_mix": workload,
               "assumptions": {"net_spread": NET_SPREAD, "avg_life_years": AVG_LIFE_YEARS, "base_lgd": BASE_LGD,
                               "committee_approves_up_to_grade": COMMITTEE_APPROVES_UP_TO_GRADE}}
    write_report(results)
    return results


def write_report(r: dict) -> None:
    money = lambda v: f"${v / 1e6:,.1f}M"  # noqa: E731
    L = ["# UnderwriteIQ - evaluation results", "",
         f"Held-out test portfolio: {r['test_size']:,} synthetic applications, "
         f"{r['portfolio_default_rate']:.1%} would default if all were approved.", "",
         "Generated by `python evaluate.py`; numbers change if the data generator or assumptions change.", "",
         "## 1. Technical metrics (probability-of-default model)", "",
         "| Model | AUC | KS | Brier |", "|---|---|---|---|"]
    L += [f"| {k} | {v['AUC']:.3f} | {v['KS']:.3f} | {v['Brier']:.4f} |" for k, v in r["technical"].items()]
    L += ["", "## 2. Business metrics (policy simulation)", "",
          "| Policy | Approval rate | Default rate of approved | Credit losses | Interest income | Net profit |",
          "|---|---|---|---|---|---|"]
    L += [f"| {k} | {v['approval_rate']:.1%} | {v['default_rate_of_approved']:.1%} | {money(v['credit_losses_$'])} "
          f"| {money(v['interest_income_$'])} | {money(v['net_profit_$'])} |" for k, v in r["business"].items()]
    L += ["", "## 3. Fairness audit (approval rates; minority ownership is never a model input)", "",
          "| Policy | Minority-owned | Other | Adverse impact ratio (>= 0.80 passes the four-fifths screen) |",
          "|---|---|---|---|"]
    L += [f"| {k} | {v['approval_rate_minority_owned']:.1%} | {v['approval_rate_other']:.1%} | "
          f"{v['adverse_impact_ratio']:.2f} |" for k, v in r["fairness"].items()]
    a = r["apex_case"]
    L += ["", "## 4. The Apex lesson: uninsured catastrophe exposure", "",
          f"- {a['uninsured_cat_exposed_loans_in_test']} test applications are asset-heavy businesses in a "
          f"wildfire/flood zone without hazard insurance; {a['their_default_rate']:.1%} of them default.",
          f"- The checklist approves {a['approved_by_checklist']} of them; the model alone approves "
          f"{a['approved_by_model_only']} ({a['approved_by_model_without_expert_features']} if the expert-captured "
          "features are removed).",
          "- Note the AUC barely moves when those features are removed: a concentrated tail risk is invisible "
          "in an aggregate metric, which is why Brenda's rule belongs in the knowledge base.",
          f"- UnderwriteIQ books {a['booked_by_hybrid_without_insurance']} of them without insurance "
          "(rule C01 holds them until coverage is in place).", "",
          "## 5. Hybrid decision mix (underwriter workload)", ""]
    L += [f"- {k}: {v:.1%}" for k, v in sorted(r["hybrid_decision_mix"].items(), key=lambda kv: -kv[1])]
    L += ["", "## Assumptions", ""] + [f"- {k}: {v}" for k, v in r["assumptions"].items()]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "results.md").write_text("\n".join(L) + "\n")
    (ROOT / "docs" / "results.json").write_text(json.dumps(r, indent=2))


if __name__ == "__main__":
    res = main()
    print((ROOT / "docs" / "results.md").read_text())
