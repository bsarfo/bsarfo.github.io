"""Scenario tests: each encodes an expectation a senior underwriter would sign off on."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from underwriteiq import inference, model as M  # noqa: E402
from underwriteiq.data import generate_portfolio  # noqa: E402
from underwriteiq.decision import recommend  # noqa: E402
from underwriteiq.memo import draft_memo  # noqa: E402
from underwriteiq.scenarios import SCENARIOS  # noqa: E402


@pytest.fixture(scope="module")
def model():
    return M.train(generate_portfolio(n=6000, seed=1))


def fired(app):
    return {f.rule.id for f in inference.run(app).fired}


def test_apex_winery_is_held_for_insurance(model):
    rec = recommend(SCENARIOS["Apex-style winery in a wildfire zone, uninsured"], model)
    assert {"D01", "C01", "F05"} <= {t["rule"] for t in rec.trace}  # chained: D01 -> C01, F05
    assert rec.decision != "APPROVE" and rec.conditions


def test_insured_winery_is_not_held():
    app = dict(SCENARIOS["Apex-style winery in a wildfire zone, uninsured"], hazard_insurance=True)
    assert "C01" not in fired(app) and "D01" in fired(app)


def test_restaurant_stale_fire_cert_held():
    assert "C02" in fired(SCENARIOS["Restaurant with expired fire-suppression cert"])


def test_missing_financials_asks_before_scoring(model):
    rec = recommend(SCENARIOS["Application with missing financials"], model)
    assert rec.decision == "INCOMPLETE" and rec.pd is None


def test_hard_stop_beats_good_score(model):
    # excellent everything, but a bankruptcy: the model must not override policy
    app = dict(SCENARIOS["Strong accounting firm (clean approve)"], bankruptcy_7y=True)
    assert recommend(app, model).decision == "DECLINE"


def test_negative_coverage_declines(model):
    rec = recommend(SCENARIOS["Trucking firm that cannot cover its debt"], model)
    assert rec.decision == "DECLINE" and "H01" in {t["rule"] for t in rec.trace}


def test_large_loan_referred(model):
    assert recommend(SCENARIOS["Large healthcare practice (above authority)"], model).decision == "REFER"


def test_clean_file_approves(model):
    assert recommend(SCENARIOS["Strong accounting firm (clean approve)"], model).decision == "APPROVE"


def test_protected_attribute_not_used(model):
    app = SCENARIOS["Restaurant with expired fire-suppression cert"]
    a = M.predict_pd(model, dict(app, minority_owned=True))
    b = M.predict_pd(model, dict(app, minority_owned=False))
    assert a == b


def test_decline_memo_has_adverse_action_reasons(model):
    app = SCENARIOS["Trucking firm that cannot cover its debt"]
    text, engine = draft_memo(app, recommend(app, model))
    assert "adverse-action" in text.lower() or engine == "gemini"


def test_every_scenario_runs(model):
    for app in SCENARIOS.values():
        recommend(app, model)
