"""Demo / test scenarios: realistic cases plus edge cases (final-demo best practice)."""

_BASE = dict(loan_amount=400_000, term_months=120, industry="Professional Services", years_in_business=9,
             employees=12, annual_revenue=1_600_000, ebitda=300_000, existing_debt_service=20_000,
             credit_score=745, collateral_value=450_000, prior_delinquencies=0, revolving_utilization=0.25,
             franchise=False, urban=True, hazard_zone="none", hazard_insurance=True, fire_cert_months=-1,
             bankruptcy_7y=False)

SCENARIOS = {
    "Strong accounting firm (clean approve)": dict(_BASE),
    "Apex-style winery in a wildfire zone, uninsured": dict(
        _BASE, industry="Winery / Agriculture", hazard_zone="wildfire", hazard_insurance=False,
        loan_amount=650_000, term_months=300, annual_revenue=1_400_000, ebitda=260_000,
        collateral_value=700_000, years_in_business=14),
    "Restaurant with expired fire-suppression cert": dict(
        _BASE, industry="Restaurant / Food Service", loan_amount=250_000, term_months=84,
        annual_revenue=1_100_000, ebitda=150_000, collateral_value=120_000, fire_cert_months=18,
        credit_score=705, years_in_business=5),
    "Start-up franchise café": dict(
        _BASE, industry="Restaurant / Food Service", franchise=True, years_in_business=0.5,
        loan_amount=350_000, annual_revenue=700_000, ebitda=110_000, collateral_value=150_000,
        credit_score=720, fire_cert_months=2, term_months=120),
    "Trucking firm that cannot cover its debt": dict(
        _BASE, industry="Transportation / Trucking", loan_amount=900_000, term_months=84,
        annual_revenue=1_300_000, ebitda=140_000, existing_debt_service=60_000, credit_score=660,
        revolving_utilization=0.85, prior_delinquencies=2),
    "Application with missing financials": dict(_BASE, annual_revenue=None, ebitda=None),
    "Large healthcare practice (above authority)": dict(
        _BASE, industry="Healthcare Practice", loan_amount=1_800_000, term_months=120,
        annual_revenue=4_500_000, ebitda=900_000, collateral_value=2_000_000, credit_score=790),
}
