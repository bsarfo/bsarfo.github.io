"""Statistical layer: probability of default (PD) with plain-English reason codes.

Primary model: logistic regression (transparent, supports adverse-action reason
codes). Benchmark: gradient boosting, to show what accuracy we give up (if any)
for explainability.
"""

from __future__ import annotations

import pathlib
import pickle

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .inference import derive_ratios

MODEL_PATH = pathlib.Path(__file__).resolve().parents[1] / "models" / "pd_model.pkl"

NUMERIC = ["credit_score", "dscr", "years_in_business", "log_loan", "collateral_coverage",
           "prior_delinquencies", "revolving_utilization", "loan_to_revenue", "term_months",
           "startup", "franchise", "bankruptcy_7y", "uninsured_cat", "stale_fire_cert"]
CATEGORICAL = ["industry"]

# ECOA / Reg B: protected characteristics are never model inputs.
EXCLUDED = ["minority_owned"]

REASONS = {
    "credit_score": "Owner credit score is low relative to approved borrowers",
    "dscr": "Cash flow available for debt service is insufficient",
    "years_in_business": "Limited time in business",
    "log_loan": "Loan amount is large",
    "collateral_coverage": "Insufficient collateral",
    "prior_delinquencies": "Recent delinquent payment history",
    "revolving_utilization": "High utilisation of revolving credit",
    "loan_to_revenue": "Loan is large relative to business revenue",
    "term_months": "Long repayment term",
    "startup": "Business is a start-up",
    "franchise": "No franchise support",
    "bankruptcy_7y": "Recent bankruptcy",
    "uninsured_cat": "Uninsured wildfire / flood exposure",
    "stale_fire_cert": "Fire-suppression certification out of date",
    "industry": "Industry has elevated historical loss rates",
}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    rows = [derive_ratios(r) for r in df.to_dict("records")]
    f = pd.DataFrame(rows, index=df.index)
    from .knowledge_base import CAT_SENSITIVE
    out = pd.DataFrame(index=df.index)
    out["credit_score"] = f["credit_score"].astype(float)
    out["dscr"] = f["dscr"].clip(-1, 5).astype(float)
    out["years_in_business"] = f["years_in_business"].clip(0, 30).astype(float)
    out["log_loan"] = np.log(f["loan_amount"].astype(float))
    out["collateral_coverage"] = f["collateral_coverage"].clip(0, 2.5).astype(float)
    out["prior_delinquencies"] = f["prior_delinquencies"].clip(0, 6).astype(float)
    out["revolving_utilization"] = f["revolving_utilization"].astype(float)
    out["loan_to_revenue"] = f["loan_to_revenue"].clip(0, 3).astype(float)
    out["term_months"] = f["term_months"].astype(float)
    out["startup"] = (f["years_in_business"] < 2).astype(float)
    out["franchise"] = f["franchise"].astype(bool).astype(float)
    out["bankruptcy_7y"] = f["bankruptcy_7y"].astype(bool).astype(float)
    cat = f["industry"].isin(CAT_SENSITIVE) & (f["hazard_zone"] != "none")
    out["uninsured_cat"] = (cat & ~f["hazard_insurance"].astype(bool)).astype(float)
    out["stale_fire_cert"] = (f["fire_cert_months"].fillna(-1) > 12).astype(float)
    out["industry"] = f["industry"]
    return out


def _preprocess() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CATEGORICAL),
    ])


def make_logistic() -> Pipeline:
    return Pipeline([("prep", _preprocess()),
                     ("clf", LogisticRegression(max_iter=2000, C=1.0))])


def make_boosting() -> Pipeline:
    return Pipeline([("prep", _preprocess()),
                     ("clf", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                                            max_leaf_nodes=31, random_state=0))])


def train(df: pd.DataFrame) -> Pipeline:
    model = make_logistic()
    model.fit(build_features(df), df["default"])
    return model


def save(model: Pipeline, path: pathlib.Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(model, fh)


def load(path: pathlib.Path = MODEL_PATH) -> Pipeline:
    if not path.exists():
        from .data import generate_portfolio
        m = train(generate_portfolio())
        save(m, path)
        return m
    with open(path, "rb") as fh:
        return pickle.load(fh)


def predict_pd(model: Pipeline, app: dict) -> float:
    return float(model.predict_proba(build_features(pd.DataFrame([app])))[0, 1])


def reason_codes(model: Pipeline, app: dict, top: int = 4) -> list[dict]:
    """Rank features by how much they push this applicant's log-odds of default
    above the average applicant (coefficient x standardised value)."""
    X = build_features(pd.DataFrame([app]))
    prep, clf = model.named_steps["prep"], model.named_steps["clf"]
    z = prep.transform(X)
    z = z.toarray()[0] if hasattr(z, "toarray") else z[0]
    contrib = z * clf.coef_[0]
    names = prep.get_feature_names_out()
    agg: dict[str, float] = {}
    for n, c in zip(names, contrib):
        key = n.split("__", 1)[1]
        key = "industry" if key.startswith("industry_") else key
        agg[key] = agg.get(key, 0.0) + c
    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    return [{"factor": k, "reason": REASONS.get(k, k), "impact": round(v, 3)}
            for k, v in ranked[:top] if v > 0.05]
