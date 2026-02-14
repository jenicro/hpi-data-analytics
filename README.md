---
title: Culture Dashboard
emoji: 📊
colorFrom: blue
colorTo: green
sdk: docker
app_file: app_dashboard.py
pinned: false
---

# Organizational Culture Dashboard

Read-only Streamlit app that displays precomputed culture results (5 super- and 15 sub-dimensions, 0–100 scale) with drill-down by org → division → department → team.

**For colleagues:** The full product and data spec is in **[DASHBOARD_SPEC.md](DASHBOARD_SPEC.md)**.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app_dashboard.py
```

Which dataset is loaded is set in **`dashboard_input/dashboard_config.json`** (`culture_results_sample.json` or `culture_results.json`).
