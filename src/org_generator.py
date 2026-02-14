"""
Generate organizational hierarchy (tree) from HierarchyConfig.
Output: list of nodes with id, name, level, parent_id; optional nested tree.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .org_config import (
    CountsConfig,
    ExplicitConfig,
    HierarchyConfig,
    DivisionSpec,
    DepartmentSpec,
)


LEVELS = ("company", "division", "department", "team", "employee")


def _node_id(level: str, *parts: int) -> str:
    """Stable id: company_0, division_0, department_0_0, team_0_0_0."""
    return "_".join([level] + [str(p) for p in parts])


def _generate_from_counts(c: CountsConfig, rng: Optional[Any] = None) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    company_id = _node_id("company", 0)
    nodes.append({
        "id": company_id,
        "name": c.company_name,
        "level": "company",
        "parent_id": None,
        "level_index": 0,
    })

    depts_per_div = c.get_departments_per_division()
    teams_per_dept = c.get_teams_per_department()
    use_team_size_range = (
        getattr(c, "n_employees_per_team_min", None) is not None
        and getattr(c, "n_employees_per_team_max", None) is not None
        and rng is not None
    )
    team_min = getattr(c, "n_employees_per_team_min", 8)
    team_max = getattr(c, "n_employees_per_team_max", 8)
    employees_per_team = c.get_employees_per_team() if not use_team_size_range else None
    dept_flat_idx = 0
    team_flat_idx = 0

    for div_idx, n_depts in enumerate(depts_per_div):
        div_id = _node_id("division", div_idx)
        nodes.append({
            "id": div_id,
            "name": f"{c.division_name_prefix} {div_idx + 1}",
            "level": "division",
            "parent_id": company_id,
            "level_index": div_idx,
        })

        for dept_idx in range(n_depts):
            n_teams = teams_per_dept[dept_flat_idx] if dept_flat_idx < len(teams_per_dept) else 4
            dept_id = _node_id("department", div_idx, dept_idx)
            nodes.append({
                "id": dept_id,
                "name": f"{c.department_name_prefix} {div_idx + 1}.{dept_idx + 1}",
                "level": "department",
                "parent_id": div_id,
                "level_index": dept_idx,
            })

            for team_idx in range(n_teams):
                if use_team_size_range:
                    n_employees = int(rng.integers(team_min, team_max + 1))
                else:
                    n_employees = employees_per_team[team_flat_idx] if team_flat_idx < len(employees_per_team) else 8
                team_id = _node_id("team", div_idx, dept_idx, team_idx)
                nodes.append({
                    "id": team_id,
                    "name": f"{c.team_name_prefix} {div_idx + 1}.{dept_idx + 1}.{team_idx + 1}",
                    "level": "team",
                    "parent_id": dept_id,
                    "level_index": team_idx,
                })
                for emp_idx in range(n_employees):
                    emp_id = _node_id("employee", div_idx, dept_idx, team_idx, emp_idx)
                    nodes.append({
                        "id": emp_id,
                        "name": f"{c.employee_name_prefix} {div_idx + 1}.{dept_idx + 1}.{team_idx + 1}.{emp_idx + 1}",
                        "level": "employee",
                        "parent_id": team_id,
                        "level_index": emp_idx,
                    })
                team_flat_idx += 1
            dept_flat_idx += 1

    return nodes


def _generate_from_explicit(e: ExplicitConfig, rng: Optional[Any] = None) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    company_id = _node_id("company", 0)
    nodes.append({
        "id": company_id,
        "name": e.company_name,
        "level": "company",
        "parent_id": None,
        "level_index": 0,
    })

    for div_idx, div in enumerate(e.divisions):
        div_id = _node_id("division", div_idx)
        nodes.append({
            "id": div_id,
            "name": div.name,
            "level": "division",
            "parent_id": company_id,
            "level_index": div_idx,
        })

        for dept_idx, dept in enumerate(div.departments):
            dept_id = _node_id("department", div_idx, dept_idx)
            nodes.append({
                "id": dept_id,
                "name": dept.name,
                "level": "department",
                "parent_id": div_id,
                "level_index": dept_idx,
            })

            n_teams = dept.n_teams
            names: Optional[List[str]] = dept.team_names
            if names:
                n_teams = len(names)
            use_min_max = (
                getattr(dept, "n_employees_per_team_min", None) is not None
                and getattr(dept, "n_employees_per_team_max", None) is not None
            )
            min_emp = getattr(dept, "n_employees_per_team_min", 8)
            max_emp = getattr(dept, "n_employees_per_team_max", 8)
            fixed_emp = getattr(dept, "n_employees_per_team", 8)
            for team_idx in range(n_teams):
                if use_min_max and rng is not None:
                    n_employees = int(rng.integers(min_emp, max_emp + 1))
                else:
                    n_employees = fixed_emp
                team_id = _node_id("team", div_idx, dept_idx, team_idx)
                team_name = (names[team_idx]) if names else f"Team {team_idx + 1}"
                nodes.append({
                    "id": team_id,
                    "name": team_name,
                    "level": "team",
                    "parent_id": dept_id,
                    "level_index": team_idx,
                })
                for emp_idx in range(n_employees):
                    emp_id = _node_id("employee", div_idx, dept_idx, team_idx, emp_idx)
                    nodes.append({
                        "id": emp_id,
                        "name": f"Employee {emp_idx + 1}",
                        "level": "employee",
                        "parent_id": team_id,
                        "level_index": emp_idx,
                    })

    return nodes


def generate_hierarchy(config: HierarchyConfig, rng: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Generate flat list of org nodes from config.
    Each node: id, name, level (company|division|department|team), parent_id, level_index.
    """
    if config.use_explicit:
        return _generate_from_explicit(config.explicit, rng=rng)
    return _generate_from_counts(config.counts, rng=rng)


def hierarchy_to_tree(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert flat node list to a single nested tree (by reference).
    Root is the company node with a "children" key; each node may have "children".
    """
    by_id: Dict[str, Dict[str, Any]] = {n["id"]: {**n, "children": []} for n in nodes}
    root: Optional[Dict[str, Any]] = None
    for n in nodes:
        node = by_id[n["id"]]
        if n["parent_id"] is None:
            root = node
            continue
        parent = by_id.get(n["parent_id"])
        if parent:
            parent["children"].append(node)
    if not root:
        raise ValueError("No company root in hierarchy")
    return root


def get_teams(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only team-level nodes (for later latent/score attachment)."""
    return [n for n in nodes if n["level"] == "team"]


def get_employees(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only employee-level nodes (individuals who answer surveys)."""
    return [n for n in nodes if n["level"] == "employee"]


def get_team_size(nodes: List[Dict[str, Any]], team_id: str) -> int:
    """Return number of employees (individuals) in the given team."""
    return sum(1 for n in nodes if n.get("parent_id") == team_id and n.get("level") == "employee")


def summary(nodes: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count by level."""
    counts: Dict[str, int] = {}
    for n in nodes:
        lvl = n["level"]
        counts[lvl] = counts.get(lvl, 0) + 1
    return counts
