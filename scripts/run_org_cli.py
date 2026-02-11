"""
CLI to generate org hierarchy: use suggestion or load config from YAML/JSON.
Usage:
  python scripts/run_org_cli.py                    # use suggested config, print summary + write JSON
  python scripts/run_org_cli.py --config path.yaml
  python scripts/run_org_cli.py --suggest-explicit
  python scripts/run_org_cli.py --out data/org.json
"""
import argparse
import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.org_config import (
    HierarchyConfig,
    CountsConfig,
    ExplicitConfig,
    DivisionSpec,
    DepartmentSpec,
    get_suggested_config,
    get_suggested_explicit_config,
)
from src.org_generator import generate_hierarchy, hierarchy_to_tree, summary


def load_config(path: Path) -> HierarchyConfig:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(text)
        except ImportError:
            raise RuntimeError("PyYAML required for YAML config. pip install pyyaml")
    else:
        data = json.loads(text)

    return _dict_to_config(data)


def _dict_to_config(data: dict) -> HierarchyConfig:
    use_explicit = data.get("use_explicit", False)
    counts = CountsConfig(
        n_divisions=data.get("counts", {}).get("n_divisions", 5),
        n_departments_per_division=data.get("counts", {}).get("n_departments_per_division", 6),
        n_teams_per_department=data.get("counts", {}).get("n_teams_per_department", 4),
        n_employees_per_team=data.get("counts", {}).get("n_employees_per_team", 8),
        company_name=data.get("counts", {}).get("company_name", "Company"),
        division_name_prefix=data.get("counts", {}).get("division_name_prefix", "Division"),
        department_name_prefix=data.get("counts", {}).get("department_name_prefix", "Department"),
        team_name_prefix=data.get("counts", {}).get("team_name_prefix", "Team"),
        employee_name_prefix=data.get("counts", {}).get("employee_name_prefix", "Employee"),
    )
    explicit = ExplicitConfig(company_name=data.get("explicit", {}).get("company_name", "Company"))
    if use_explicit and "explicit" in data and "divisions" in data["explicit"]:
        for d in data["explicit"]["divisions"]:
            depts = [
                DepartmentSpec(
                    name=dept.get("name", "Dept"),
                    n_teams=dept.get("n_teams", 4),
                    team_names=dept.get("team_names"),
                    n_employees_per_team=dept.get("n_employees_per_team", 8),
                )
                for dept in d.get("departments", [])
            ]
            explicit.divisions.append(DivisionSpec(name=d.get("name", "Division"), departments=depts))
    return HierarchyConfig(use_explicit=use_explicit, counts=counts, explicit=explicit)


def save_config(config: HierarchyConfig, path: Path) -> None:
    """Write config to YAML (or JSON) for later edit."""
    data: dict = {
        "use_explicit": config.use_explicit,
        "counts": {
            "n_divisions": config.counts.n_divisions,
            "n_departments_per_division": config.counts.n_departments_per_division,
            "n_teams_per_department": config.counts.n_teams_per_department,
            "n_employees_per_team": config.counts.n_employees_per_team,
            "company_name": config.counts.company_name,
            "division_name_prefix": config.counts.division_name_prefix,
            "department_name_prefix": config.counts.department_name_prefix,
            "team_name_prefix": config.counts.team_name_prefix,
            "employee_name_prefix": config.counts.employee_name_prefix,
        },
        "explicit": {
            "company_name": config.explicit.company_name,
            "divisions": [
                {
                    "name": div.name,
                    "departments": [
                        {
                            "name": d.name,
                            "n_teams": d.n_teams,
                            "team_names": getattr(d, "team_names", None),
                            "n_employees_per_team": getattr(d, "n_employees_per_team", 8),
                        }
                        for d in div.departments
                    ],
                }
                for div in config.explicit.divisions
            ],
        },
    }
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        except ImportError:
            path.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate organizational hierarchy (latent simulator – org only)")
    ap.add_argument("--config", "-c", type=Path, help="Path to YAML/JSON config (overrides suggest)")
    ap.add_argument("--suggest-explicit", action="store_true", help="Use suggested explicit tree (auto manufacturer names)")
    ap.add_argument("--out", "-o", type=Path, default=Path("data/org.json"), help="Output path for hierarchy JSON")
    ap.add_argument("--out-tree", type=Path, help="Optional: also write nested tree JSON")
    ap.add_argument("--save-config", type=Path, help="Write current config to file (e.g. for editing)")
    args = ap.parse_args()

    if args.config:
        config = load_config(args.config)
        print("Loaded config from", args.config)
    elif args.suggest_explicit:
        config = get_suggested_explicit_config()
        print("Using suggested explicit config (large auto manufacturer)")
    else:
        config = get_suggested_config()
        print("Using suggested counts config (large auto manufacturer)")

    if args.save_config:
        save_config(config, args.save_config)
        print("Saved config to", args.save_config)

    nodes = generate_hierarchy(config)
    counts = summary(nodes)
    print("Summary:", counts)

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    # Write flat list (no "children" in each node for JSON serialization of flat list)
    out.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Wrote", len(nodes), "nodes to", out)

    if args.out_tree:
        tree = hierarchy_to_tree(nodes)
        # Remove recursive refs for JSON: keep only id, name, level, children (list of same shape)
        def to_serializable(node: dict) -> dict:
            return {
                "id": node["id"],
                "name": node["name"],
                "level": node["level"],
                "children": [to_serializable(ch) for ch in node.get("children", [])],
            }
        args.out_tree.parent.mkdir(parents=True, exist_ok=True)
        args.out_tree.write_text(json.dumps(to_serializable(tree), indent=2, ensure_ascii=False), encoding="utf-8")
        print("Wrote tree to", args.out_tree)


if __name__ == "__main__":
    main()
