"""Forward-chaining inference engine with a full audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .data import annual_payment
from .knowledge_base import RULES, Cond, Rule


def _missing(v: Any) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def derive_ratios(app: dict) -> dict:
    """Compute the financial ratios an underwriter would compute by hand."""
    facts = dict(app)
    amount, term = app.get("loan_amount"), app.get("term_months")
    ebitda, existing = app.get("ebitda"), app.get("existing_debt_service") or 0
    if not _missing(amount) and not _missing(term):
        facts["new_debt_service"] = round(annual_payment(amount, int(term)), 2)
        if not _missing(ebitda):
            facts["dscr"] = round(ebitda / (existing + facts["new_debt_service"]), 2)
    if not _missing(app.get("collateral_value")) and amount:
        facts["collateral_coverage"] = round(app["collateral_value"] / amount, 2)
    if not _missing(app.get("annual_revenue")) and app.get("annual_revenue") and amount:
        facts["loan_to_revenue"] = round(amount / app["annual_revenue"], 2)
    return facts


def _holds(c: Cond, facts: dict) -> bool:
    v = facts.get(c.fact)
    if c.op == "missing":
        return _missing(v)
    if c.op == "present":
        return not _missing(v)
    if _missing(v):
        return False  # unknown facts never satisfy a condition; 'ask' rules catch them
    if c.op == "is_true":
        return bool(v) is True
    if c.op == "is_false":
        return bool(v) is False
    if c.op == "in":
        return v in c.value
    if c.op == "not_in":
        return v not in c.value
    return {"<": v < c.value, "<=": v <= c.value, ">": v > c.value,
            ">=": v >= c.value, "==": v == c.value, "!=": v != c.value}[c.op]


@dataclass
class Firing:
    rule: Rule
    evidence: dict

    def as_row(self) -> dict:
        return {"rule": self.rule.id, "name": self.rule.name, "action": self.rule.action,
                "message": self.rule.message, "evidence": self.evidence, "source": self.rule.source}


@dataclass
class InferenceResult:
    facts: dict
    fired: list[Firing] = field(default_factory=list)

    def by_action(self, action: str) -> list[Firing]:
        return [f for f in self.fired if f.rule.action == action]

    @property
    def notch(self) -> int:
        return sum(f.rule.notch for f in self.by_action("notch"))

    def trace(self) -> list[dict]:
        return [f.as_row() for f in self.fired]


def run(app: dict, rules: list[Rule] = RULES) -> InferenceResult:
    """Fire rules until no new rule fires (forward chaining to a fixed point)."""
    facts = derive_ratios(app)
    result = InferenceResult(facts=facts)
    fired_ids: set[str] = set()
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if rule.id in fired_ids or not all(_holds(c, facts) for c in rule.when):
                continue
            fired_ids.add(rule.id)
            result.fired.append(Firing(rule, {c.fact: facts.get(c.fact) for c in rule.when}))
            if rule.action == "assert":
                facts.update(rule.sets)
                changed = True  # new facts may enable earlier rules
    return result
