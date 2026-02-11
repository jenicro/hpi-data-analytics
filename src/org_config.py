"""
Configuration schema for organizational hierarchy generation.
Supports: suggestion (large auto manufacturer), counts-based, or explicit tree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Union


# ---------------------------------------------------------------------------
# Counts-based config: specify how many units at each level
# ---------------------------------------------------------------------------

@dataclass
class CountsConfig:
    """Specify hierarchy by counts. Counts can be uniform or per-parent."""

    n_divisions: int = 5
    """Number of divisions under company."""

    n_departments_per_division: Union[int, List[int]] = 6
    """Departments per division. int = same for all; list = one value per division (length = n_divisions)."""

    n_teams_per_department: Union[int, List[int]] = 4
    """Teams per department. int = same for all; list = one value per department (flattened order)."""

    n_employees_per_team: Union[int, List[int]] = 8
    """Employees (individuals) per team. int = same for all; list = one value per team (flattened order)."""

    company_name: str = "Company"
    division_name_prefix: str = "Division"
    department_name_prefix: str = "Department"
    team_name_prefix: str = "Team"
    employee_name_prefix: str = "Employee"

    def get_departments_per_division(self) -> List[int]:
        if isinstance(self.n_departments_per_division, int):
            return [self.n_departments_per_division] * self.n_divisions
        if len(self.n_departments_per_division) >= self.n_divisions:
            return list(self.n_departments_per_division[: self.n_divisions])
        # Pad or truncate
        base = list(self.n_departments_per_division)
        while len(base) < self.n_divisions:
            base.append(base[-1] if base else 4)
        return base[: self.n_divisions]

    def get_teams_per_department(self) -> List[int]:
        """Returns list of team counts: one per department in flattened order (div0_dept0, div0_dept1, ...)."""
        depts_per_div = self.get_departments_per_division()
        total_depts = sum(depts_per_div)
        if isinstance(self.n_teams_per_department, int):
            return [self.n_teams_per_department] * total_depts
        if len(self.n_teams_per_department) >= total_depts:
            return list(self.n_teams_per_department[: total_depts])
        base = list(self.n_teams_per_department)
        while len(base) < total_depts:
            base.append(base[-1] if base else 4)
        return base[: total_depts]

    def get_employees_per_team(self) -> List[int]:
        """Returns list of employee counts: one per team in flattened order."""
        teams_per_dept = self.get_teams_per_department()
        total_teams = sum(teams_per_dept)
        if isinstance(self.n_employees_per_team, int):
            return [self.n_employees_per_team] * total_teams
        if len(self.n_employees_per_team) >= total_teams:
            return list(self.n_employees_per_team[: total_teams])
        base = list(self.n_employees_per_team)
        while len(base) < total_teams:
            base.append(base[-1] if base else 8)
        return base[: total_teams]


# ---------------------------------------------------------------------------
# Explicit config: full tree with names (e.g. from organigram)
# ---------------------------------------------------------------------------

@dataclass
class DivisionSpec:
    name: str
    departments: List["DepartmentSpec"] = field(default_factory=list)


@dataclass
class DepartmentSpec:
    name: str
    n_teams: int = 4
    team_names: List[str] | None = None
    """If set, use these names and len(team_names) overrides n_teams."""
    n_employees_per_team: int = 8
    """Number of employees (individuals) in each team in this department."""


@dataclass
class ExplicitConfig:
    """Fully specified tree: divisions with names, each with departments, each with team count or names."""

    company_name: str = "Company"
    divisions: List[DivisionSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Unified config: one of the above
# ---------------------------------------------------------------------------

@dataclass
class HierarchyConfig:
    """Top-level config: use either counts or explicit tree."""

    use_explicit: bool = False
    counts: CountsConfig = field(default_factory=CountsConfig)
    explicit: ExplicitConfig = field(default_factory=ExplicitConfig)


# ---------------------------------------------------------------------------
# Suggestion: large automobile manufacturer
# ---------------------------------------------------------------------------

def get_suggested_config() -> HierarchyConfig:
    """
    Suggested hierarchy for a large automobile manufacturer.
    You can replace this config entirely or adjust counts/names from the UI or config file.
    """
    return HierarchyConfig(
        use_explicit=False,
        counts=CountsConfig(
            n_divisions=6,
            n_departments_per_division=[8, 6, 10, 5, 4, 6],  # per division
            n_teams_per_department=5,  # uniform
            n_employees_per_team=8,
            company_name="AutoCorp",
            division_name_prefix="Division",
            department_name_prefix="Dept",
            team_name_prefix="Team",
            employee_name_prefix="Employee",
        ),
    )


def get_suggested_explicit_config() -> HierarchyConfig:
    """
    Same scale as suggestion but with realistic division/department names
    for a large automobile manufacturer (organigram-style).
    """
    return HierarchyConfig(
        use_explicit=True,
        explicit=ExplicitConfig(
            company_name="AutoCorp",
            divisions=[
                DivisionSpec("Production", [
                    DepartmentSpec("Body Shop", 6),
                    DepartmentSpec("Paint", 4),
                    DepartmentSpec("Assembly", 8),
                    DepartmentSpec("Powertrain", 5),
                    DepartmentSpec("Quality", 4),
                ]),
                DivisionSpec("R&D", [
                    DepartmentSpec("Vehicle Development", 6),
                    DepartmentSpec("E-Mobility", 5),
                    DepartmentSpec("Testing", 4),
                    DepartmentSpec("Simulation", 3),
                ]),
                DivisionSpec("Sales & Marketing", [
                    DepartmentSpec("Sales Ops", 5),
                    DepartmentSpec("Marketing", 4),
                    DepartmentSpec("After Sales", 6),
                    DepartmentSpec("Digital Sales", 3),
                ]),
                DivisionSpec("Procurement & Supply Chain", [
                    DepartmentSpec("Purchasing", 5),
                    DepartmentSpec("Logistics", 6),
                    DepartmentSpec("Supplier Quality", 4),
                ]),
                DivisionSpec("HR & Organization", [
                    DepartmentSpec("HR Business Partners", 4),
                    DepartmentSpec("Recruiting", 3),
                    DepartmentSpec("Learning", 3),
                ]),
                DivisionSpec("Finance & IT", [
                    DepartmentSpec("Controlling", 4),
                    DepartmentSpec("IT", 5),
                    DepartmentSpec("Finance Ops", 3),
                ]),
            ],
        ),
    )
