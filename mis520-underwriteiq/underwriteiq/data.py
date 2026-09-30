"""Synthetic small-business loan portfolio.

Real bank loan files are confidential, so the MVP trains on a synthetic
portfolio whose structure follows public sources (SBA 7(a) loan data fields,
common credit-policy ratios such as DSCR and collateral coverage). Every
assumption lives in this file so the team can defend or change it, and the
generator can later be swapped for the public SBA dataset (see README).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# industry -> (base default log-odds shift, typical EBITDA margin, revenue scale)
INDUSTRIES = {
    "Restaurant / Food Service": (0.55, 0.09, 900_000),
    "Retail Trade": (0.25, 0.08, 1_200_000),
    "Construction": (0.30, 0.11, 1_500_000),
    "Healthcare Practice": (-0.45, 0.18, 1_400_000),
    "Professional Services": (-0.35, 0.16, 800_000),
    "Manufacturing": (0.00, 0.12, 2_500_000),
    "Transportation / Trucking": (0.35, 0.10, 1_300_000),
    "Winery / Agriculture": (0.15, 0.14, 1_100_000),
    "Hospitality / Lodging": (0.30, 0.15, 1_600_000),
    "Technology Services": (-0.10, 0.17, 1_000_000),
}

# industries whose physical assets are exposed to wildfire / flood
CAT_SENSITIVE = {"Winery / Agriculture", "Hospitality / Lodging", "Construction", "Restaurant / Food Service"}

HAZARD_ZONES = ["none", "wildfire", "flood"]
TERMS = [60, 84, 120, 300]

FEATURES = [
    "loan_amount", "term_months", "industry", "years_in_business", "employees",
    "annual_revenue", "ebitda", "existing_debt_service", "credit_score",
    "collateral_value", "prior_delinquencies", "revolving_utilization",
    "franchise", "urban", "hazard_zone", "hazard_insurance",
    "fire_cert_months", "bankruptcy_7y",
]


def annual_payment(amount: float, term_months: int, rate: float = 0.10) -> float:
    """Level annual debt service for an amortising loan (monthly payments)."""
    r = rate / 12
    return float(amount * r / (1 - (1 + r) ** -term_months) * 12)


def generate_portfolio(n: int = 20_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    names = list(INDUSTRIES)
    industry = rng.choice(names, size=n, p=[.14, .13, .10, .08, .12, .09, .08, .06, .08, .12])
    risk_shift = np.array([INDUSTRIES[i][0] for i in industry])
    margin = np.array([INDUSTRIES[i][1] for i in industry])
    rev_scale = np.array([INDUSTRIES[i][2] for i in industry])

    # audit-only attribute: never a model feature (ECOA / Reg B prohibits it),
    # used to test whether the system produces disparate outcomes.
    minority_owned = rng.random(n) < 0.30
    urban = rng.random(n) < np.where(minority_owned, 0.80, 0.60)

    years = np.clip(rng.gamma(2.0, 4.0, n), 0, 40).round(1)
    employees = np.clip(rng.lognormal(2.0, 0.8, n), 1, 400).round().astype(int)
    revenue = (rev_scale * rng.lognormal(0, 0.6, n) * (0.5 + np.minimum(years, 10) / 20)).round(-3)
    ebitda = (revenue * np.clip(margin + rng.normal(0, 0.05, n), -0.05, 0.40)).round(-2)

    # credit score: structural gap between groups mirrors documented wealth /
    # credit-access gaps, which is exactly why a fairness audit is required.
    credit = np.clip(rng.normal(np.where(minority_owned, 690, 705), 55, n), 520, 850).round().astype(int)

    term = rng.choice(TERMS, size=n, p=[.25, .30, .30, .15])
    # banks size business loans on cash flow: request = 0.8x-4.0x EBITDA
    loan = np.clip(np.maximum(ebitda, revenue * 0.05) * rng.uniform(0.8, 4.0, n), 25_000, 3_000_000).round(-3)
    existing_ds = (ebitda.clip(min=0) * rng.uniform(0, 0.45, n)).round(-2)
    collateral = (loan * np.clip(rng.normal(0.8, 0.45, n), 0, 2.5)).round(-3)
    delinq = rng.poisson(np.clip((720 - credit) / 60, 0.05, None))
    util = np.clip(rng.beta(2, 3, n) + (700 - credit) / 600, 0, 1).round(2)
    franchise = rng.random(n) < 0.12
    bankruptcy = rng.random(n) < np.clip((620 - credit) / 400, 0.005, 0.25)

    hazard = rng.choice(HAZARD_ZONES, size=n, p=[.78, .12, .10])
    insured = np.where(hazard == "none", True, rng.random(n) < 0.55)
    fire_cert = np.where(np.isin(industry, ["Restaurant / Food Service"]),
                         rng.integers(0, 30, n), -1)  # -1 = not applicable

    new_payment = np.array([annual_payment(a, t) for a, t in zip(loan, term)])
    dscr = ebitda / (existing_ds + new_payment)

    # ---- true default mechanism (what a senior underwriter "knows") ----
    logit = (
        -2.60
        + risk_shift
        - 0.018 * (credit - 700)
        - 0.9 * np.clip(dscr - 1.25, -1.5, 1.5)
        + 0.6 * (dscr < 1.0)  # cash flow cannot cover debt: sharp jump in risk
        + 0.55 * (years < 2) - 0.02 * np.minimum(years, 20)
        + 0.30 * delinq
        + 1.10 * util
        - 0.35 * np.clip(collateral / loan, 0, 1.5)
        - 0.35 * franchise
        + 1.30 * bankruptcy
        + 0.25 * (term >= 300)
        + rng.normal(0, 0.35, n)
    )
    # tacit risk: uninsured catastrophe exposure (the Apex / Brenda lesson) and
    # stale fire-suppression certification for restaurants
    cat_exposed = np.isin(industry, list(CAT_SENSITIVE)) & (hazard != "none")
    logit += np.where(cat_exposed & ~insured, 1.1, np.where(cat_exposed, 0.2, 0))
    logit += np.where(fire_cert > 12, 0.6, 0)

    default = rng.random(n) < 1 / (1 + np.exp(-logit))

    df = pd.DataFrame({
        "loan_id": [f"L{100000 + i}" for i in range(n)],
        "loan_amount": loan, "term_months": term, "industry": industry,
        "years_in_business": years, "employees": employees,
        "annual_revenue": revenue, "ebitda": ebitda,
        "existing_debt_service": existing_ds, "credit_score": credit,
        "collateral_value": collateral, "prior_delinquencies": delinq,
        "revolving_utilization": util, "franchise": franchise, "urban": urban,
        "hazard_zone": hazard, "hazard_insurance": insured,
        "fire_cert_months": fire_cert, "bankruptcy_7y": bankruptcy,
        "minority_owned": minority_owned, "default": default.astype(int),
    })
    return df


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "loans.csv"
    df = generate_portfolio()
    df.to_csv(out, index=False)
    print(f"wrote {len(df):,} loans to {out} | default rate {df['default'].mean():.1%}")
