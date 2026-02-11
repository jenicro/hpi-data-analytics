# Org hierarchy simulator (latent simulator – org only)

Generate an organizational hierarchy (Company → Divisions → Departments → Teams) for a large automobile manufacturer. No items/dimensions yet; this step only creates the org structure.

## Quick start

**Suggested config (counts):**
```bash
python scripts/run_org_cli.py
```
Writes `data/org.json` with 1 company, 6 divisions, 39 departments, 195 teams (default suggestion).

**Suggested config (explicit division/department names):**
```bash
python scripts/run_org_cli.py --suggest-explicit
```

**Streamlit app (adjust counts, then generate and download):**
```bash
streamlit run app_org.py
```

## Config options

- **Suggest (counts)** – One-click: 6 divisions, variable departments per division, 5 teams per department; company name "AutoCorp". You can then change every number and prefix in the app or via config file.
- **Suggest (explicit)** – Same scale but with realistic names (Production, R&D, Sales & Marketing, Procurement, HR, Finance; departments like Body Shop, Assembly, E-Mobility, etc.).
- **Custom** – Edit a YAML/JSON config (see `config/org_suggestion.yaml` and `config/org_explicit_example.yaml`) and run:
  ```bash
  python scripts/run_org_cli.py --config config/org_suggestion.yaml --out data/org.json
  ```
  To export the current suggestion as a config file for editing:
  ```bash
  python scripts/run_org_cli.py --save-config config/my_org.yaml
  ```

## Output

- **Flat list** of nodes: `id`, `name`, `level` (company | division | department | team), `parent_id`, `level_index`. Written to `--out` (default `data/org.json`).
- Optional **nested tree**: `--out-tree path.json` (CLI) or "Download hierarchy (nested tree JSON)" in the app.

## Project layout

- `src/org_config.py` – Config schema and `get_suggested_config()` / `get_suggested_explicit_config()`
- `src/org_generator.py` – `generate_hierarchy(config)` → list of nodes; `hierarchy_to_tree()`, `get_teams()`, `summary()`
- `app_org.py` – Streamlit UI
- `scripts/run_org_cli.py` – CLI
- `config/` – Example YAML configs
