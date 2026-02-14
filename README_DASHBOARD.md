# Organizational Culture Dashboard

Read-only Streamlit app that displays precomputed culture results (5 super- and 15 sub-dimensions, 0–100 scale) with drill-down by org → division → department → team.

**For colleagues:** The full product and data spec (what the dashboard is, what each chart does, explainability text, glossary, data contract) is in **[DASHBOARD_SPEC.md](DASHBOARD_SPEC.md)**.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app_dashboard.py
```

The app loads `dashboard_input/culture_results.json` if present, otherwise `dashboard_input/culture_results_sample.json` (minimal sample so it runs out of the box).

## Host (e.g. Streamlit Community Cloud)

1. Push this branch to GitHub.
2. In Streamlit Cloud: New app → connect repo, choose branch `host_dashboard`.
3. Main file: `app_dashboard.py`.
4. Use the repo’s `requirements.txt`.

No secrets or env vars required for the sample data.
