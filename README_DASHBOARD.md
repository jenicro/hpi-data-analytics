# Organizational Culture Dashboard

Read-only Streamlit app that displays precomputed culture results (5 super- and 15 sub-dimensions, 0–100 scale) with drill-down by org → division → department → team.

**For colleagues:** The full product and data spec (what the dashboard is, what each chart does, explainability text, glossary, data contract) is in **[DASHBOARD_SPEC.md](DASHBOARD_SPEC.md)**.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app_dashboard.py
```

Which dataset is loaded is set in **`dashboard_input/dashboard_config.json`**:
- `"data_file": "culture_results_sample.json"` → sample data (what the deployed branch uses).
- `"data_file": "culture_results.json"` → your full results.

If the config file is missing, the app uses `culture_results.json` if present, else `culture_results_sample.json`.

## Host on Hugging Face Spaces

1. **Create a token:** Hugging Face → Settings → Access Tokens → New token (read + write).
2. **Store the token (HF only, does not touch GitHub):**  
   Open `C:\Users\jenic\.git-credentials-huggingface` and replace `PASTE_YOUR_TOKEN_HERE` with your token, then save. Git is configured to use this file only for `huggingface.co`.
3. **Push this branch to your Space:**
   ```bash
   git checkout host_dashboard
   git remote add hf https://huggingface.co/spaces/cromi/dashboard
   # If "remote hf already exists": git remote set-url hf https://huggingface.co/spaces/cromi/dashboard
   git push hf host_dashboard:main --force
   ```
4. Wait for the Space to rebuild; open https://huggingface.co/spaces/cromi/dashboard

## Host (e.g. Streamlit Community Cloud)

1. Push this branch to GitHub.
2. In Streamlit Cloud: New app → connect repo, choose branch `host_dashboard`.
3. Main file: `app_dashboard.py`.
4. Use the repo’s `requirements.txt`.

No secrets or env vars required for the sample data.
