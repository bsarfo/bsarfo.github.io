"""Decision policy: how rules, model and human combine (Class 2, slide 18:
rule/policy gate -> model -> validation -> human approval).

Conflict resolution, in order:
1. Missing information  -> INCOMPLETE. Never score what we have not seen.
2. Hard stop            -> DECLINE recommended. A high model score cannot
                           outweigh a policy violation (Class 3, slide 16).
3. Model PD + rule notches -> risk grade 1-10.
4. Holds / flags / referral change the path, not the grade.
The system only recommends; a named underwriter makes and signs the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import inference
from .model import predict_pd, reason_codes

# PD upper bound for each risk grade (grade 1 = best). Illustrative.
GRADE_BOUNDS = [0.02, 0.04, 0.06, 0.09, 0.12, 0.16, 0.22, 0.30, 0.40, 1.01]
APPROVE_MAX_GRADE = 5   # grades 1-5 may be approved by the underwriter
DECLINE_MIN_GRADE = 9   # grades 9-10 are recommended for decline


def pd_to_grade(pd_: float) -> int:
    return next(i + 1 for i, b in enumerate(GRADE_BOUNDS) if pd_ < b)


@dataclass
class Recommendation:
    decision: str            # APPROVE | APPROVE WITH CONDITIONS | REFER | DECLINE | INCOMPLETE
    grade: int | None
    pd: float | None
    headline: str
    facts: dict
    trace: list[dict]
    asks: list[str] = field(default_factory=list)
    hard_stops: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    referrals: list[str] = field(default_factory=list)
    mitigants: list[str] = field(default_factory=list)
    reasons: list[dict] = field(default_factory=list)


def recommend(app: dict, model) -> Recommendation:
    inf = inference.run(app)
    msgs = lambda a: [f.rule.message for f in inf.by_action(a)]  # noqa: E731
    base = dict(facts=inf.facts, trace=inf.trace(), asks=msgs("ask"), hard_stops=msgs("hard_stop"),
                conditions=msgs("hold"), flags=msgs("flag"), referrals=msgs("refer"),
                mitigants=msgs("notch"))

    if base["asks"]:
        return Recommendation("INCOMPLETE", None, None,
                              "Information missing - request it before any credit assessment.", **base)

    pd_ = predict_pd(model, app)
    grade = min(10, max(1, pd_to_grade(pd_) + inf.notch))
    reasons = reason_codes(model, app)

    if base["hard_stops"]:
        return Recommendation("DECLINE", grade, pd_,
                              "Policy hard stop - decline recommended; any exception needs written senior approval.",
                              reasons=reasons, **base)
    if grade >= DECLINE_MIN_GRADE:
        decision, headline = "DECLINE", f"Risk grade {grade}: estimated default risk too high for policy."
    elif base["referrals"] or grade > APPROVE_MAX_GRADE:
        decision, headline = "REFER", f"Risk grade {grade}: refer to senior underwriter / credit committee."
        if base["conditions"]:
            headline += " Conditions below must be cleared before booking."
    elif base["conditions"] or base["flags"]:
        decision, headline = "APPROVE WITH CONDITIONS", f"Risk grade {grade}: approvable once conditions are cleared."
    else:
        decision, headline = "APPROVE", f"Risk grade {grade}: within policy and risk appetite."
    return Recommendation(decision, grade, pd_, headline, reasons=reasons, **base)
