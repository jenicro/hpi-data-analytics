"""
Helpers for fractal drill-down explore viz: aggregation and simulation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .dimensions import DIMENSION_IDS, DOMAINS

# Dimension selector: "dim:zuversicht" or "domain:Positive Momentum"
def get_dimension_display_options() -> List[Tuple[str, str]]:
    """Return (value, label) for selector: 15 dimensions then 5 domains."""
    out: List[Tuple[str, str]] = []
    for dim_id in DIMENSION_IDS:
        out.append((f"dim:{dim_id}", dim_id))
    out.append(("---", "--- Domains ---"))
    for domain_name, dims in DOMAINS:
        out.append((f"domain:{domain_name}", f"Domain: {domain_name}"))
    return out


def get_value_for_selector(
    recs: List[Dict[str, Any]],
    team_id: str,
    selector: str,
) -> float:
    """One number for a team: mean over employees in that team (dimension or domain). Records are per employee."""
    team_recs = [r for r in recs if r["team_id"] == team_id]
    if not team_recs:
        return 0.0
    if selector.startswith("dim:"):
        dim_id = selector.split(":", 1)[1]
        vals = [float(r.get("true_latent", r.get("point", 0))) for r in team_recs if r["dimension_id"] == dim_id]
        return sum(vals) / len(vals) if vals else 0.0
    if selector.startswith("domain:"):
        domain_name = selector.split(":", 1)[1]
        dim_ids = []
        for dname, dims in DOMAINS:
            if dname == domain_name:
                dim_ids = [di for di, _ in dims]
                break
        if not dim_ids:
            return 0.0
        vals = [float(r.get("true_latent", r.get("point", 0))) for r in team_recs if r["dimension_id"] in dim_ids]
        return sum(vals) / len(vals) if vals else 0.0
    return 0.0


def get_point_interval_for_selector(
    recs: List[Dict[str, Any]],
    team_id: str,
    selector: str,
) -> Tuple[float, Optional[float], Optional[float]]:
    """Return (point, lower_95, upper_95) for a team: mean over employees in that team."""
    team_recs = [r for r in recs if r["team_id"] == team_id]
    if not team_recs:
        return (0.0, None, None)
    if selector.startswith("dim:"):
        dim_id = selector.split(":", 1)[1]
        sub = [r for r in team_recs if r["dimension_id"] == dim_id]
        if not sub:
            return (0.0, None, None)
        p = sum(float(r.get("point", r.get("true_latent", 0))) for r in sub) / len(sub)
        los = [r["lower_95"] for r in sub if r.get("lower_95") is not None]
        his = [r["upper_95"] for r in sub if r.get("upper_95") is not None]
        lo = sum(los) / len(los) if los else None
        hi = sum(his) / len(his) if his else None
        return (p, lo, hi)
    if selector.startswith("domain:"):
        domain_name = selector.split(":", 1)[1]
        dim_ids = []
        for dname, dims in DOMAINS:
            if dname == domain_name:
                dim_ids = [di for di, _ in dims]
                break
        if not dim_ids:
            return (0.0, None, None)
        sub = [r for r in team_recs if r["dimension_id"] in dim_ids]
        if not sub:
            return (0.0, None, None)
        p = sum(float(r.get("point", r.get("true_latent", 0))) for r in sub) / len(sub)
        los = [r["lower_95"] for r in sub if r.get("lower_95") is not None]
        his = [r["upper_95"] for r in sub if r.get("upper_95") is not None]
        lo = sum(los) / len(los) if los else None
        hi = sum(his) / len(his) if his else None
        return (p, lo, hi)
    return (0.0, None, None)


def build_hierarchy(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build lookup structures: by_id, team->(dept_id, div_id), divisions list, depts per div, teams per dept."""
    by_id = {n["id"]: n for n in nodes}
    team_to_dept: Dict[str, str] = {}
    team_to_div: Dict[str, str] = {}
    for n in nodes:
        if n["level"] == "team":
            tid = n["id"]
            team_to_dept[tid] = n["parent_id"] or ""
            dept = by_id.get(n["parent_id"]) if n["parent_id"] else None
            team_to_div[tid] = dept["parent_id"] if dept and dept.get("parent_id") else ""

    division_ids = sorted([n["id"] for n in nodes if n["level"] == "division"])
    dept_ids_per_div: Dict[str, List[str]] = {}
    for n in nodes:
        if n["level"] == "department":
            div_id = n["parent_id"] or ""
            dept_ids_per_div.setdefault(div_id, []).append(n["id"])
    for k in dept_ids_per_div:
        dept_ids_per_div[k].sort()

    team_ids_per_dept: Dict[str, List[str]] = {}
    for n in nodes:
        if n["level"] == "team":
            dept_id = n["parent_id"] or ""
            team_ids_per_dept.setdefault(dept_id, []).append(n["id"])
    for k in team_ids_per_dept:
        team_ids_per_dept[k].sort()

    return {
        "by_id": by_id,
        "team_to_dept": team_to_dept,
        "team_to_div": team_to_div,
        "division_ids": division_ids,
        "dept_ids_per_div": dept_ids_per_div,
        "team_ids_per_dept": team_ids_per_dept,
    }


def aggregate_means(
    latent_records: List[Dict[str, Any]],
    hierarchy: Dict[str, Any],
    selector: str,
) -> Dict[str, float]:
    """Return org_mean, division_means[div_id], department_means[dept_id], team_values[team_id]."""
    by_id = hierarchy["by_id"]
    team_to_dept = hierarchy["team_to_dept"]
    team_to_div = hierarchy["team_to_div"]
    team_ids_seen = set(r["team_id"] for r in latent_records)
    team_values = {tid: get_value_for_selector(latent_records, tid, selector) for tid in team_ids_seen}

    all_vals = list(team_values.values())
    org_mean = sum(all_vals) / len(all_vals) if all_vals else 0.0

    division_means: Dict[str, float] = {}
    for div_id in hierarchy["division_ids"]:
        tids = []
        for tid, d in team_to_dept.items():
            if team_to_div.get(tid) == div_id:
                tids.append(tid)
        if tids:
            division_means[div_id] = sum(team_values.get(t, 0) for t in tids) / len(tids)
        else:
            division_means[div_id] = org_mean

    department_means: Dict[str, float] = {}
    for div_id, dept_ids in hierarchy["dept_ids_per_div"].items():
        for dept_id in dept_ids:
            tids = hierarchy["team_ids_per_dept"].get(dept_id, [])
            if tids:
                department_means[dept_id] = sum(team_values.get(t, 0) for t in tids) / len(tids)
            else:
                department_means[dept_id] = division_means.get(div_id, org_mean)

    return {
        "org_mean": org_mean,
        "division_means": division_means,
        "department_means": department_means,
        "team_values": team_values,
    }


def simulate_individuals(
    team_id: str,
    latent_records: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    selector: str,
    within_sd: float = 10.0,
    rng: Optional[Any] = None,
) -> List[float]:
    """Return actual person-level values for this team (one per employee). Records are per employee; no simulation."""
    if selector.startswith("dim:"):
        dim_id = selector.split(":", 1)[1]
        sub = [r for r in latent_records if r["team_id"] == team_id and r["dimension_id"] == dim_id]
    elif selector.startswith("domain:"):
        domain_name = selector.split(":", 1)[1]
        dim_ids = []
        for dname, dims in DOMAINS:
            if dname == domain_name:
                dim_ids = [di for di, _ in dims]
                break
        sub = [r for r in latent_records if r["team_id"] == team_id and r["dimension_id"] in dim_ids]
        # one value per employee: average their domain dims
        by_emp: Dict[str, List[float]] = {}
        for r in sub:
            eid = r.get("employee_id", "")
            v = float(r.get("true_latent", r.get("point", 0)))
            by_emp.setdefault(eid, []).append(v)
        return [sum(vs) / len(vs) for vs in by_emp.values()] if by_emp else []
    else:
        return []
    return [float(r.get("true_latent", r.get("point", 0))) for r in sub]
