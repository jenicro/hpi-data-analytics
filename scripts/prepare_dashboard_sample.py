"""
Build a smaller sample for the dashboard by removing whole units (no random sampling).
- Remove 2 departments entirely.
- From each remaining department, remove 1 team.
Team sizes in kept teams are unchanged. Then run IRT + hierarchical posterior on the subset
and write dashboard_input/culture_results_sample.json.

Usage:
  python scripts/prepare_dashboard_sample.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.dimensions import DIMENSION_IDS, DOMAINS
from src.bayesian_irt import get_superfactor_names
from src.items import irt_scores_from_response_dataset
from src.hierarchical_posterior import compute_hierarchical_posterior, sub_to_super_means_sds


def to_json_safe(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json_safe(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return obj


def build_hierarchy(org_nodes):
    """Return division_ids, division_to_depts, dept_to_teams (ids only)."""
    by_id = {n["id"]: n for n in org_nodes}
    division_ids = [n["id"] for n in org_nodes if n.get("level") == "division"]
    division_to_depts = {}
    dept_to_teams = {}
    for n in org_nodes:
        if n.get("level") == "department":
            pid = n.get("parent_id")
            if pid:
                division_to_depts.setdefault(pid, []).append(n["id"])
        if n.get("level") == "team":
            pid = n.get("parent_id")
            if pid:
                dept_to_teams.setdefault(pid, []).append(n["id"])
    return division_ids, division_to_depts, dept_to_teams


def main():
    responses_path = PROJECT_ROOT / "dashboard_input" / "item_responses.csv"
    org_path = PROJECT_ROOT / "dashboard_input" / "org_hierarchy.json"
    item_bank_path = PROJECT_ROOT / "dashboard_input" / "item_bank.json"
    output_path = PROJECT_ROOT / "dashboard_input" / "culture_results_sample.json"

    if not responses_path.exists() or not org_path.exists() or not item_bank_path.exists():
        print("Error: need item_responses.csv, org_hierarchy.json, item_bank.json in dashboard_input/")
        sys.exit(1)

    print("Loading org hierarchy and responses...")
    with open(org_path, encoding="utf-8") as f:
        org_nodes = json.load(f)
    response_df = pd.read_csv(responses_path)

    division_ids, division_to_depts, dept_to_teams = build_hierarchy(org_nodes)
    all_dept_ids = []
    for div_id in division_ids:
        all_dept_ids.extend(division_to_depts.get(div_id, []))

    # Remove 2 departments entirely (last 2 in list so deterministic)
    drop_depts = set(all_dept_ids[-2:]) if len(all_dept_ids) >= 2 else set()
    remaining_depts = [d for d in all_dept_ids if d not in drop_depts]

    # From each remaining department, remove 1 team (last team per dept)
    remaining_teams = set()
    for dept_id in remaining_depts:
        teams = dept_to_teams.get(dept_id, [])
        if len(teams) > 1:
            remaining_teams.update(teams[:-1])  # drop last team
        elif teams:
            remaining_teams.add(teams[0])  # keep the only team

    # Filter responses to remaining teams only (team sizes unchanged)
    response_sub = response_df[response_df["team_id"].astype(str).isin(remaining_teams)].copy()
    n_respondents = len(response_sub)

    # Filter org_nodes: company, all divisions, remaining depts, remaining teams, employees under remaining teams
    keep_team_ids = set(remaining_teams)
    keep_dept_ids = set(remaining_depts)
    keep_div_ids = set(division_ids)
    by_id = {n["id"]: n for n in org_nodes}

    def keep_node(n):
        level = n.get("level")
        nid = n.get("id")
        if level == "company":
            return True
        if level == "division":
            return nid in keep_div_ids
        if level == "department":
            return nid in keep_dept_ids
        if level == "team":
            return nid in keep_team_ids
        if level == "employee":
            return n.get("parent_id") in keep_team_ids
        return False

    org_sub = [n for n in org_nodes if keep_node(n)]

    print(f"Subset: {n_respondents} respondents, {len(remaining_teams)} teams, {len(remaining_depts)} departments, {len(division_ids)} divisions")
    print("Running IRT on subset...")
    theta_hat = irt_scores_from_response_dataset(response_sub, json.load(open(item_bank_path, encoding="utf-8")))

    print("Computing hierarchical posterior on subset...")
    hi = compute_hierarchical_posterior(org_sub, response_sub, theta_hat)

    n_teams = len(hi["team"]["means"]) if hi.get("team") and hi["team"].get("means") else 0
    n_departments = len(hi["department"]["means"]) if hi.get("department") and hi["department"].get("means") else 0
    n_divisions = len(hi["division"]["ids"]) if hi.get("division") and hi["division"].get("ids") else 0
    summary_stats = {
        "n_respondents": n_respondents,
        "n_teams": n_teams,
        "n_departments": n_departments,
        "n_divisions": n_divisions,
    }

    print("Sampling posterior for Statistical tab...")
    rng = np.random.default_rng(42)
    org = hi["org"]
    post_org = rng.normal(
        org["mean_super"],
        np.maximum(org["sd_super"], 0.1),
        size=(4000, len(get_superfactor_names())),
    )
    post_sub = rng.normal(
        org["mean_sub"],
        np.maximum(org["sd_sub"], 0.1),
        size=(4000, len(DIMENSION_IDS)),
    )
    post_org = np.clip(post_org, 0, 100)
    post_sub = np.clip(post_sub, 0, 100)

    respondent_scores = None
    if "team_id" in response_sub.columns:
        respondent_id_col = "respondent_id" if "respondent_id" in response_sub.columns else response_sub.columns[0]
        employee_id_col = "employee_id" if "employee_id" in response_sub.columns else None
        respondent_ids = response_sub[respondent_id_col].astype(str).tolist()
        team_ids = response_sub["team_id"].astype(str).tolist()
        employee_ids = response_sub[employee_id_col].astype(str).tolist() if employee_id_col else respondent_ids
        theta_super_per = np.array([
            sub_to_super_means_sds(theta_hat[i], np.zeros(len(DIMENSION_IDS)))[0]
            for i in range(len(theta_hat))
        ], dtype=float)
        respondent_scores = {
            "respondent_id": respondent_ids,
            "employee_id": employee_ids,
            "team_id": team_ids,
            "theta_sub": np.clip(theta_hat, 0, 100).tolist(),
            "theta_super": np.clip(theta_super_per, 0, 100).tolist(),
        }

    payload = {
        "summary_stats": summary_stats,
        "hierarchical_result": to_json_safe(hi),
        "posterior_theta_org": post_org.tolist(),
        "posterior_theta_sub": post_sub.tolist(),
    }
    if respondent_scores is not None:
        payload["respondent_scores"] = respondent_scores

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {output_path} ({n_respondents} respondents, {n_divisions} divisions, {n_departments} depts, {n_teams} teams).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
