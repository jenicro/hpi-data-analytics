"""
Hierarchical posterior for dashboard: team → department → division → org.
Heuristic conjugate normal updates with between-unit variance so posteriors stay smooth (no sharp spikes).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .dimensions import DOMAINS, DIMENSION_IDS, N_DIMENSIONS

# Heuristic: prior and variance parameters (scale 0–100)
PRIOR_MEAN = 50.0
PRIOR_SD = 15.0
SIGMA_MEASUREMENT = 5.0   # IRT measurement error SD per person
SIGMA_BETWEEN_PERSON = 8.0
SIGMA_BETWEEN_TEAM = 6.0
SIGMA_BETWEEN_DEPT = 5.0
SIGMA_BETWEEN_DIVISION = 5.0
MIN_POSTERIOR_SD = 2.0     # Floor so we never get spikes


def _build_hierarchy(org_nodes: List[Dict[str, Any]]) -> Tuple[Dict, Dict, Dict, Dict, Dict]:
    """Build lookups: by_id, team->dept, team->division, dept->division, and node names."""
    by_id = {n["id"]: n for n in org_nodes}
    team_to_dept: Dict[str, str] = {}
    team_to_division: Dict[str, str] = {}
    dept_to_division: Dict[str, str] = {}
    for n in org_nodes:
        if n.get("level") == "team":
            tid = n["id"]
            pid = n.get("parent_id")
            team_to_dept[tid] = pid or ""
            if pid and pid in by_id:
                dept = by_id[pid]
                div_id = dept.get("parent_id") or ""
                team_to_division[tid] = div_id
                dept_to_division[pid] = div_id
    return by_id, team_to_dept, team_to_division, dept_to_division, by_id


def _conjugate_update(
    prior_mean: float,
    prior_sd: float,
    data_means: np.ndarray,
    data_sds: np.ndarray,
    between_sd: float,
    min_sd: float = MIN_POSTERIOR_SD,
) -> Tuple[float, float]:
    """Posterior for mean given prior and child estimates (each child has mean ± sd)."""
    prior_prec = 1.0 / (prior_sd ** 2)
    # Each child contributes precision 1 / (child_sd^2 + between_sd^2)
    child_var = np.maximum(data_sds ** 2 + between_sd ** 2, 1e-6)
    data_prec = np.sum(1.0 / child_var)
    post_prec = prior_prec + data_prec
    post_mean = (prior_prec * prior_mean + np.sum(data_means / child_var)) / post_prec
    post_sd = max(1.0 / (post_prec ** 0.5), min_sd)
    return float(np.clip(post_mean, 0, 100)), float(post_sd)


def compute_hierarchical_posterior(
    org_nodes: List[Dict[str, Any]],
    response_df: Any,
    theta_hat: np.ndarray,
) -> Dict[str, Any]:
    """
    Bottom-up: person thetas (theta_hat) → team → department → division → org.
    Returns a nested structure with posteriors (mean, sd) per dimension at each level,
    plus lists of ids and names for drill-down.
    """
    # #region agent log
    _th = np.asarray(theta_hat)
    import time
    _log = open(r"c:\Users\jenic\OneDrive - JENEWEIN AG\HPI_Ressources\hpi-data-analytics\.cursor\debug.log", "a", encoding="utf-8")
    _log.write('{"location":"hierarchical_posterior.py:entry","message":"compute_hierarchical_posterior entry","data":{"theta_hat_shape":%s,"theta_hat_ndim":%s},"hypothesisId":"H1","timestamp":%d}\n' % (list(_th.shape), _th.ndim, time.time() * 1000))
    _log.close()
    # #endregion
    by_id, team_to_dept, team_to_division, dept_to_division, _ = _build_hierarchy(org_nodes)
    n_dim = N_DIMENSIONS

    # Map: team_id -> list of row indices in response_df (and thus theta_hat)
    if "team_id" not in response_df.columns:
        return _empty_result()
    team_to_rows: Dict[str, List[int]] = {}
    for i in range(len(response_df)):
        tid = str(response_df.iloc[i]["team_id"])
        team_to_rows.setdefault(tid, []).append(i)

    # Person-level "posterior" is just theta_hat; we treat each person as mean with SD = measurement
    person_sd = np.full(n_dim, SIGMA_MEASUREMENT, dtype=float)

    # --- Team level ---
    team_means: Dict[str, np.ndarray] = {}
    team_sds: Dict[str, np.ndarray] = {}
    for tid, rows in team_to_rows.items():
        if not rows:
            continue
        # #region agent log
        _log2 = open(r"c:\Users\jenic\OneDrive - JENEWEIN AG\HPI_Ressources\hpi-data-analytics\.cursor\debug.log", "a", encoding="utf-8")
        _log2.write('{"location":"hierarchical_posterior.py:before_index","message":"before theta_hat[rows,:]","data":{"tid":%s,"rows_sample":%s,"theta_hat_shape":%s,"theta_hat_ndim":%s},"hypothesisId":"H2","timestamp":%d}\n' % (repr(tid), rows[:5] if len(rows) > 5 else rows, list(np.asarray(theta_hat).shape), np.asarray(theta_hat).ndim, __import__("time").time() * 1000))
        _log2.close()
        # #endregion
        thetas = theta_hat[rows, :]  # (n_persons, 15)
        n = thetas.shape[0]
        # Prior N(50, 15); data = mean(thetas), variance of mean = (sigma_between^2 + sigma_meas^2) / n
        var_mean = (SIGMA_BETWEEN_PERSON ** 2 + SIGMA_MEASUREMENT ** 2) / max(n, 1)
        data_prec = 1.0 / max(var_mean, 1e-6)
        prior_prec = 1.0 / (PRIOR_SD ** 2)
        post_prec = prior_prec + data_prec
        mean_d = np.mean(thetas, axis=0)
        post_sd_d = np.maximum(1.0 / (post_prec ** 0.5), MIN_POSTERIOR_SD)
        team_means[tid] = np.clip((prior_prec * PRIOR_MEAN + data_prec * mean_d) / post_prec, 0, 100)
        team_sds[tid] = np.full(n_dim, post_sd_d)

    # --- Department level (aggregate teams) ---
    dept_to_teams: Dict[str, List[str]] = {}
    for tid in team_means:
        dept_id = team_to_dept.get(tid) or ""
        if dept_id:
            dept_to_teams.setdefault(dept_id, []).append(tid)
    dept_means: Dict[str, np.ndarray] = {}
    dept_sds: Dict[str, np.ndarray] = {}
    for dept_id, tids in dept_to_teams.items():
        t_means = np.array([team_means[t] for t in tids])
        t_sds = np.array([team_sds[t] for t in tids])
        prior_mean_d = np.full(n_dim, PRIOR_MEAN)
        prior_sd_d = np.full(n_dim, PRIOR_SD)
        m = np.zeros(n_dim)
        s = np.zeros(n_dim)
        for d in range(n_dim):
            m[d], s[d] = _conjugate_update(
                PRIOR_MEAN, PRIOR_SD, t_means[:, d], t_sds[:, d], SIGMA_BETWEEN_TEAM
            )
        dept_means[dept_id] = m
        dept_sds[dept_id] = s

    # --- Division level (aggregate departments) ---
    division_to_depts: Dict[str, List[str]] = {}
    for dept_id in dept_means:
        div_id = dept_to_division.get(dept_id) or ""
        if div_id:
            division_to_depts.setdefault(div_id, []).append(dept_id)
    division_means: Dict[str, np.ndarray] = {}
    division_sds: Dict[str, np.ndarray] = {}
    for div_id, dept_ids in division_to_depts.items():
        d_means = np.array([dept_means[d] for d in dept_ids])
        d_sds = np.array([dept_sds[d] for d in dept_ids])
        m = np.zeros(n_dim)
        s = np.zeros(n_dim)
        for dim in range(n_dim):
            m[dim], s[dim] = _conjugate_update(
                PRIOR_MEAN, PRIOR_SD, d_means[:, dim], d_sds[:, dim], SIGMA_BETWEEN_DIVISION
            )
        division_means[div_id] = m
        division_sds[div_id] = s

    # --- Org level (aggregate divisions) ---
    div_ids = list(division_means.keys())
    if not div_ids:
        org_mean = np.full(n_dim, PRIOR_MEAN)
        org_sd = np.full(n_dim, PRIOR_SD)
    else:
        d_means = np.array([division_means[d] for d in div_ids])
        d_sds = np.array([division_sds[d] for d in div_ids])
        m = np.zeros(n_dim)
        s = np.zeros(n_dim)
        for dim in range(n_dim):
            m[dim], s[dim] = _conjugate_update(
                PRIOR_MEAN, PRIOR_SD, d_means[:, dim], d_sds[:, dim], SIGMA_BETWEEN_DIVISION
            )
        org_mean = m
        org_sd = s

    # Superfactor (5) from subfactor (15): average means and pool SDs per domain
    def sub_to_super(means_15: np.ndarray, sds_15: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        m_sup = np.zeros(len(DOMAINS))
        s_sup = np.zeros(len(DOMAINS))
        idx = 0
        for k, (_name, dims) in enumerate(DOMAINS):
            n_d = len(dims)
            m_sup[k] = np.mean(means_15[idx : idx + n_d])
            s_sup[k] = np.mean(sds_15[idx : idx + n_d])
            idx += n_d
        return m_sup, s_sup

    org_m_sup, org_s_sup = sub_to_super(org_mean, org_sd)
    return {
        "org": {"mean_sub": org_mean, "sd_sub": org_sd, "mean_super": org_m_sup, "sd_super": org_s_sup},
        "division": {"ids": div_ids, "means": division_means, "sds": division_sds, "by_id": by_id},
        "department": {"dept_to_teams": dept_to_teams, "dept_to_division": dept_to_division, "means": dept_means, "sds": dept_sds},
        "team": {"team_to_dept": team_to_dept, "team_to_division": team_to_division, "means": team_means, "sds": team_sds},
        "by_id": by_id,
        "team_to_dept": team_to_dept,
        "team_to_division": team_to_division,
        "dept_to_division": dept_to_division,
        "division_to_depts": division_to_depts,
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "org": {},
        "division": {"ids": [], "means": {}, "sds": {}, "by_id": {}},
        "department": {"dept_to_teams": {}, "dept_to_division": {}, "means": {}, "sds": {}},
        "team": {"team_to_dept": {}, "team_to_division": {}, "means": {}, "sds": {}},
        "by_id": {},
        "team_to_dept": {},
        "team_to_division": {},
        "dept_to_division": {},
        "division_to_depts": {},
    }


def sub_to_super_means_sds(means_15: np.ndarray, sds_15: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    m_sup = np.zeros(len(DOMAINS))
    s_sup = np.zeros(len(DOMAINS))
    idx = 0
    for k, (_name, dims) in enumerate(DOMAINS):
        n_d = len(dims)
        m_sup[k] = np.mean(means_15[idx : idx + n_d])
        s_sup[k] = np.mean(sds_15[idx : idx + n_d])
        idx += n_d
    return m_sup, s_sup
