"""Knowledge base: senior-underwriter expertise written as explicit IF-THEN rules.

Each rule is data, not code, so a credit officer can read, review and version it
(Class 3: syntax = precise notation, semantics = symbols map to real things).

Action types
------------
assert     derive a new fact that other rules can chain on (forward chaining)
ask        required information is missing -> ask before assessing
hard_stop  policy says no; the model cannot override it (only a documented
           human exception can)
hold       approval blocked until a condition is cleared
flag       concern the underwriter must review
refer      outside this underwriter's authority -> escalate
notch      move the risk grade up (+) or down (-) as a compensating factor

The policy thresholds below are illustrative, modelled on common community-bank
credit policy; a real deployment would take them from the bank's own policy
manual and interviews with its senior underwriters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CAT_SENSITIVE = ["Winery / Agriculture", "Hospitality / Lodging", "Construction", "Restaurant / Food Service"]


@dataclass(frozen=True)
class Cond:
    fact: str
    op: str  # one of: < <= > >= == != in not_in missing present is_true is_false
    value: Any = None

    def text(self) -> str:
        if self.op in ("missing", "present", "is_true", "is_false"):
            return f"{self.fact} {self.op.replace('_', ' ')}"
        return f"{self.fact} {self.op.replace('_', ' ')} {self.value}"


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    when: tuple[Cond, ...]
    action: str
    message: str
    rationale: str
    source: str = "Senior underwriter interview (illustrative)"
    sets: dict = field(default_factory=dict)  # facts asserted by 'assert' rules
    notch: int = 0
    version: str = "1.0"


RULES: list[Rule] = [
    # ---------- information gathering (ask before assessing) ----------
    Rule("R01", "Missing financials",
         (Cond("annual_revenue", "missing"),), "ask",
         "Request two years of business tax returns and a YTD P&L.",
         "DSCR cannot be computed without revenue and cash flow."),
    Rule("R02", "Missing credit report",
         (Cond("credit_score", "missing"),), "ask",
         "Pull a personal credit report for every 20%+ owner.",
         "Owner credit is a primary repayment-behaviour signal."),
    Rule("R03", "Missing collateral valuation",
         (Cond("collateral_value", "missing"),), "ask",
         "Order an appraisal or provide collateral schedule.",
         "Collateral coverage drives loss-given-default."),

    # ---------- derived facts (chaining) ----------
    Rule("D01", "Catastrophe exposure",
         (Cond("industry", "in", CAT_SENSITIVE), Cond("hazard_zone", "in", ["wildfire", "flood"])),
         "assert", "Business has physical catastrophe exposure.",
         "Asset-heavy businesses in wildfire/flood zones can lose the collateral and the cash flow at once.",
         source="Lesson from the Apex Insurance case (Class 3)", sets={"cat_exposure": True}),
    Rule("D02", "Start-up business",
         (Cond("years_in_business", "<", 2),), "assert", "Business is a start-up (< 2 years).",
         "Start-ups lack an operating history to evidence repayment.", sets={"startup": True}),
    Rule("D03", "Tight cash-flow coverage",
         (Cond("dscr", ">=", 1.0), Cond("dscr", "<", 1.25)), "assert",
         "DSCR is below the 1.25x policy minimum.",
         "1.25x is a common minimum cushion for business loans.", sets={"thin_dscr": True}),

    # ---------- hard stops ----------
    Rule("H01", "Negative cash-flow coverage",
         (Cond("dscr", "<", 1.0),), "hard_stop",
         "Projected cash flow does not cover total debt service (DSCR < 1.0x).",
         "The business cannot repay from operations."),
    Rule("H02", "Recent bankruptcy",
         (Cond("bankruptcy_7y", "is_true"),), "hard_stop",
         "Owner bankruptcy within the last 7 years.",
         "Illustrative bank policy exclusion."),
    Rule("H03", "Credit score floor",
         (Cond("credit_score", "<", 600),), "hard_stop",
         "Owner credit score below policy floor of 600.",
         "Illustrative bank policy floor."),

    # ---------- holds (conditions precedent) ----------
    Rule("C01", "Uninsured catastrophe exposure",
         (Cond("cat_exposure", "is_true"), Cond("hazard_insurance", "is_false")), "hold",
         "Require wildfire/flood insurance naming the bank as loss payee, plus a site mitigation "
         "review (water source, defensible space, elevation).",
         "The checklist Alex used never asked this; Brenda would have.",
         source="Lesson from the Apex Insurance case (Class 3)"),
    Rule("C02", "Stale fire-suppression certificate",
         (Cond("industry", "==", "Restaurant / Food Service"), Cond("fire_cert_months", ">", 12)), "hold",
         "Fire-suppression system not certified in the last 12 months: obtain current certificate.",
         "Kitchen fires are a leading cause of restaurant closure.",
         source="Class 3 rule example (restaurant evaluation)"),
    Rule("C03", "Start-up equity injection",
         (Cond("startup", "is_true"), Cond("franchise", "is_false"), Cond("collateral_coverage", "<", 0.5)), "hold",
         "Start-up with thin collateral: verify owner equity injection of at least 10% of project cost.",
         "Owner equity aligns incentives and absorbs early losses."),

    # ---------- flags ----------
    Rule("F01", "Thin DSCR needs compensating factors",
         (Cond("thin_dscr", "is_true"),), "flag",
         "DSCR between 1.00x and 1.25x: document compensating factors (collateral, guarantor liquidity).",
         "Exceptions to policy must be justified in writing."),
    Rule("F02", "Recent delinquencies",
         (Cond("prior_delinquencies", ">=", 2),), "flag",
         "Two or more delinquencies in 24 months: obtain written explanation.",
         "Repeated late payment predicts future late payment."),
    Rule("F03", "High revolving utilisation",
         (Cond("revolving_utilization", ">", 0.8),), "flag",
         "Revolving utilisation above 80%: assess liquidity and working-capital needs.",
         "Maxed-out credit lines signal cash-flow stress."),
    Rule("F04", "Loan large relative to revenue",
         (Cond("loan_to_revenue", ">", 0.75),), "flag",
         "Loan exceeds 75% of annual revenue: verify use of proceeds and projections.",
         "Aggressive leverage relative to business size."),
    Rule("F05", "Long-horizon climate risk",
         (Cond("cat_exposure", "is_true"), Cond("term_months", ">", 120)), "flag",
         "Catastrophe-exposed borrower with a >10-year term: consider shorter term or climate stress test.",
         "Chained rule: exposure compounds over long horizons.",
         source="Lesson from the Apex Insurance case (Class 3)"),

    # ---------- authority / escalation ----------
    Rule("A01", "Above underwriter authority",
         (Cond("loan_amount", ">", 1_000_000),), "refer",
         "Loan above $1,000,000: senior credit committee approval required.",
         "Delegated lending authority limit (illustrative)."),

    # ---------- compensating factors ----------
    Rule("N01", "Strong collateral",
         (Cond("collateral_coverage", ">=", 1.0),), "notch",
         "Collateral fully covers the loan.", "Lower loss-given-default.", notch=-1),
    Rule("N02", "Franchise support",
         (Cond("franchise", "is_true"), Cond("startup", "is_true")), "notch",
         "Start-up backed by an established franchise system.",
         "Franchisor playbook reduces start-up failure risk.", notch=-1),
    Rule("N03", "Strong cash-flow coverage",
         (Cond("dscr", ">=", 2.0),), "notch",
         "DSCR at or above 2.0x.", "Large repayment cushion.", notch=-1),
]


def rules_table() -> list[dict]:
    """Plain rows for display / export (the rule book a credit officer reviews)."""
    return [{
        "id": r.id, "name": r.name,
        "IF": " AND ".join(c.text() for c in r.when),
        "THEN": r.action.upper() + (f" ({r.notch:+d} grade)" if r.notch else "") + ": " + r.message,
        "why": r.rationale, "source": r.source, "version": r.version,
    } for r in RULES]
