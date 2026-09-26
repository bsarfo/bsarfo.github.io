# UnderwriteIQ (backup / alternative project idea)

A fintech alternative built before the team chose ReRouteAI: a small-business loan underwriting copilot that turns
a retiring senior underwriter's judgement into explicit IF-THEN rules (Class 3, Apex Insurance case), combines them
with a probability-of-default model, drafts the credit memo and adverse-action reasons with an LLM, and leaves the
decision to a named underwriter.

```bash
cd mis520-underwriteiq
pip install -r requirements.txt
python evaluate.py        # -> docs/results.md
streamlit run app.py
pytest -q tests           # 11 scenario tests
```

- `underwriteiq/knowledge_base.py` — 20 sourced, versioned rules (ask / assert / hard stop / hold / flag / refer / notch)
- `underwriteiq/inference.py` — forward-chaining engine with an audit trail
- `underwriteiq/model.py` — logistic regression PD model with reason codes; gradient boosting benchmark
- `underwriteiq/decision.py` — conflict resolution: missing info → hard stop → model grade → holds/flags → human
- `underwriteiq/memo.py` — Gemini (if `GEMINI_API_KEY`) or template credit memo

Data is a **synthetic** portfolio (`underwriteiq/data.py`, all assumptions documented). Headline finding: removing the
expert-captured features barely changes AUC (0.846 → 0.844) but doubles the model's approvals of uninsured
wildfire/flood-exposed borrowers (45 → 98); the rule holds all of them. Aggregate metrics hide concentrated tail risk.
