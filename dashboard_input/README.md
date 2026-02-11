# Dashboard input

Put these two files here so the results dashboard uses them on startup (no upload needed):

- **org_hierarchy.json** — Flat list of nodes (id, name, level, parent_id), e.g. from the org simulator export.
- **item_bank.json** — IRT item bank (item_id, dimension_id, nu, lambda, sigma), e.g. from the org simulator export.

The dashboard loads them automatically when you run `streamlit run app_dashboard.py`.
