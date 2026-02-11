"""
Generate person-level (employee) true latent scores and point estimates with 95% intervals.
Each employee has a 15-dim latent (person latent); hierarchy effects (division/department/team) plus within-team individual variance.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .dimensions import DIMENSION_IDS, N_DIMENSIONS
from .latent_config import LatentGenConfig
from .org_generator import get_employees, get_teams


def _build_correlation_matrix(config: LatentGenConfig) -> np.ndarray:
    """15x15 correlation matrix: within-domain r_w, cross-domain r_b."""
    if config.correlation_matrix is not None and config.correlation_matrix.shape == (N_DIMENSIONS, N_DIMENSIONS):
        return np.array(config.correlation_matrix, dtype=float)
    from .dimensions import DOMAINS
    R = np.ones((N_DIMENSIONS, N_DIMENSIONS)) * config.r_cross_domain
    idx = 0
    for _domain_name, dims in DOMAINS:
        n = len(dims)
        R[idx : idx + n, idx : idx + n] = config.r_within_domain
        idx += n
    np.fill_diagonal(R, 1.0)
    return R


def _ensure_positive_definite(R: np.ndarray) -> np.ndarray:
    """Ensure R is positive definite (e.g. for Cholesky)."""
    min_eig = np.min(np.linalg.eigvalsh(R))
    if min_eig < 1e-8:
        R = R + (1e-8 - min_eig) * np.eye(R.shape[0])
    return R


def _employee_hierarchy_lookup(nodes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, str]]:
    """Return (employees, team_to_division, team_to_department). Each employee has parent_id = team_id."""
    by_id = {n["id"]: n for n in nodes}
    employees = get_employees(nodes)
    team_to_division: Dict[str, str] = {}
    team_to_department: Dict[str, str] = {}
    for node in nodes:
        if node["level"] != "team":
            continue
        team_id = node["id"]
        team_to_department[team_id] = node["parent_id"] or ""
        dept_id = node["parent_id"]
        dept = by_id.get(dept_id) if dept_id else None
        div_id = dept["parent_id"] if dept else None
        team_to_division[team_id] = div_id or ""
    return employees, team_to_division, team_to_department


def generate_latents(
    nodes: List[Dict[str, Any]],
    config: LatentGenConfig,
    *,
    include_true_latent: bool = True,
    rng: Optional[np.random.Generator] = None,
) -> List[Dict[str, Any]]:
    """
    Generate person-level (employee) culture scores from org structure.
    Returns flat list of records: employee_id, team_id, dimension_id, point, lower_95, upper_95, [true_latent].
    Each person has a 15-dim latent (theta = mu + div + dept + team + individual effects).
    """
    if rng is None:
        rng = np.random.default_rng()
    employees, team_to_div, team_to_dept = _employee_hierarchy_lookup(nodes)
    if not employees:
        return []
    teams = get_teams(nodes)
    div_ids = sorted(set(team_to_div.values()) - {""})
    dept_ids = sorted(set(team_to_dept.values()) - {""})
    sigma_total = config.sigma_total
    vw = getattr(config, "var_within", 0.20)
    v_ind = getattr(config, "var_individual", 0.45)
    vt = config.var_team
    vd = config.var_dept
    vdiv = config.var_division
    total = vw + v_ind + vt + vd + vdiv
    if total <= 0:
        total = 1.0
    vw, v_ind, vt, vd, vdiv = vw / total, v_ind / total, vt / total, vd / total, vdiv / total
    s_team = sigma_total * (vt ** 0.5)
    s_dept = sigma_total * (vd ** 0.5)
    s_div = sigma_total * (vdiv ** 0.5)
    s_individual = sigma_total * (v_ind ** 0.5)
    mu = np.array(config.mu, dtype=float)
    if len(mu) != N_DIMENSIONS:
        mu = np.resize(mu, N_DIMENSIONS)
    R = _build_correlation_matrix(config)
    R = _ensure_positive_definite(R)
    L = np.linalg.cholesky(R)

    div_effects: Dict[str, np.ndarray] = {}
    for did in div_ids:
        z = rng.standard_normal(N_DIMENSIONS)
        div_effects[did] = s_div * (L @ z)
    dept_effects: Dict[str, np.ndarray] = {}
    for did in dept_ids:
        z = rng.standard_normal(N_DIMENSIONS)
        dept_effects[did] = s_dept * (L @ z)
    team_effects: Dict[str, np.ndarray] = {}
    for team in teams:
        team_id = team["id"]
        z = rng.standard_normal(N_DIMENSIONS)
        team_effects[team_id] = s_team * (L @ z)

    base_sd = config.base_measurement_sd
    out: List[Dict[str, Any]] = []
    for emp in employees:
        employee_id = emp["id"]
        team_id = emp.get("parent_id") or ""
        div_id = team_to_div.get(team_id, "")
        dept_id = team_to_dept.get(team_id, "")
        z_ind = rng.standard_normal(N_DIMENSIONS)
        individual_effect = s_individual * (L @ z_ind)
        theta = (
            mu
            + div_effects.get(div_id, np.zeros(N_DIMENSIONS))
            + dept_effects.get(dept_id, np.zeros(N_DIMENSIONS))
            + team_effects.get(team_id, np.zeros(N_DIMENSIONS))
            + individual_effect
        )
        theta = np.clip(theta, 0, 100)
        point = theta + rng.standard_normal(N_DIMENSIONS) * base_sd
        point = np.clip(point, 0, 100)
        half_width = 1.96 * base_sd
        lower = np.clip(point - half_width, 0, 100)
        upper = np.clip(point + half_width, 0, 100)
        for i, dim_id in enumerate(DIMENSION_IDS):
            rec: Dict[str, Any] = {
                "employee_id": employee_id,
                "team_id": team_id,
                "dimension_id": dim_id,
                "point": float(point[i]),
                "lower_95": float(lower[i]),
                "upper_95": float(upper[i]),
            }
            if include_true_latent:
                rec["true_latent"] = float(theta[i])
            out.append(rec)
    return out
