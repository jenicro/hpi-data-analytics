"""
Prepare precomputed culture results for the dashboard.
Runs IRT + hierarchical posterior on response data and writes a single JSON file
that the dashboard loads with no on-the-fly statistics.

Usage:
  python scripts/prepare_dashboard_data.py
  python scripts/prepare_dashboard_data.py --responses path/to/responses.csv --output path/to/culture_results.json

Reads from dashboard_input/ by default; writes dashboard_input/culture_results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Project root = parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.dimensions import DIMENSION_IDS, DOMAINS
from src.bayesian_irt import get_superfactor_names
from src.items import irt_scores_from_response_dataset
from src.hierarchical_posterior import compute_hierarchical_posterior, sub_to_super_means_sds


def to_json_safe(obj):
    """Convert nested structure with numpy arrays to JSON-serializable (lists)."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json_safe(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return obj


def main():
    parser = argparse.ArgumentParser(description="Precompute culture results for the dashboard.")
    parser.add_argument(
        "--responses",
        type=Path,
        default=PROJECT_ROOT / "dashboard_input" / "item_responses.csv",
        help="Path to response data CSV",
    )
    parser.add_argument(
        "--item-bank",
        type=Path,
        default=PROJECT_ROOT / "dashboard_input" / "item_bank.json",
        help="Path to item bank JSON",
    )
    parser.add_argument(
        "--org-hierarchy",
        type=Path,
        default=PROJECT_ROOT / "dashboard_input" / "org_hierarchy.json",
        help="Path to org hierarchy JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "dashboard_input" / "culture_results.json",
        help="Output path for culture_results.json",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=6000,
        help="Number of posterior samples to store for Statistical tab",
    )
    args = parser.parse_args()

    if not args.responses.exists():
        print(f"Error: Responses file not found: {args.responses}")
        sys.exit(1)
    if not args.item_bank.exists():
        print(f"Error: Item bank not found: {args.item_bank}")
        sys.exit(1)
    if not args.org_hierarchy.exists():
        print(f"Error: Org hierarchy not found: {args.org_hierarchy}")
        sys.exit(1)

    print("Loading response data...")
    response_df = pd.read_csv(args.responses)
    n_respondents = len(response_df)

    print("Loading item bank and org hierarchy...")
    with open(args.item_bank, encoding="utf-8") as f:
        item_bank = json.load(f)
    with open(args.org_hierarchy, encoding="utf-8") as f:
        org_nodes = json.load(f)

    print("Running IRT (this may take a while)...")
    theta_hat = irt_scores_from_response_dataset(response_df, item_bank)

    print("Computing hierarchical posterior...")
    hi = compute_hierarchical_posterior(org_nodes, response_df, theta_hat)

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
    super_names = get_superfactor_names()
    post_org = rng.normal(
        org["mean_super"],
        np.maximum(org["sd_super"], 0.1),
        size=(args.samples, len(super_names)),
    )
    post_sub = rng.normal(
        org["mean_sub"],
        np.maximum(org["sd_sub"], 0.1),
        size=(args.samples, len(DIMENSION_IDS)),
    )
    post_org = np.clip(post_org, 0, 100)
    post_sub = np.clip(post_sub, 0, 100)

    # Per-respondent scores for drill-down individual scores (team level)
    respondent_scores = None
    if "team_id" in response_df.columns:
        respondent_id_col = "respondent_id" if "respondent_id" in response_df.columns else response_df.columns[0]
        team_id_col = "team_id"
        employee_id_col = "employee_id" if "employee_id" in response_df.columns else None
        respondent_ids = response_df[respondent_id_col].astype(str).tolist()
        team_ids = response_df[team_id_col].astype(str).tolist()
        employee_ids = response_df[employee_id_col].astype(str).tolist() if employee_id_col else respondent_ids
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {args.output} ({n_respondents} respondents, {n_divisions} divisions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
