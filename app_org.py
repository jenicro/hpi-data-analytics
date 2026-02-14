"""
Streamlit app: generate org hierarchy and team-level latent culture scores.
Run: streamlit run app_org.py
"""
import json
from pathlib import Path

import streamlit as st

from src.org_config import (
    HierarchyConfig,
    CountsConfig,
    ExplicitConfig,
    DivisionSpec,
    DepartmentSpec,
    get_suggested_config,
    get_random_explicit_config,
)
from src.org_generator import generate_hierarchy, hierarchy_to_tree, summary, get_teams
from src.latent_config import LatentGenConfig, get_suggested_latent_config
from src.latent_generator import generate_latents
from src.explore_utils import (
    build_hierarchy,
    aggregate_means,
    simulate_individuals,
    get_dimension_display_options,
    get_point_interval_for_selector,
)
from src.items import (
    create_item_bank,
    apply_suggested_parameters,
    build_icc_figure,
    build_icc_figure_by_dimension,
    irt_scores_from_response_dataset,
    simulate_item_responses_from_org,
)
from src.dimensions import DIMENSION_IDS, DOMAINS, dimension_index
from src.efa_utils import (
    true_thetas_and_correlation_from_response_dataset,
    get_efa_factor_scores,
    response_dataset_to_efa,
    run_efa,
    reorder_factors_to_dimensions,
)
import io
import zipfile

import pandas as pd
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Org & latent simulator", layout="wide")


def _build_download_all_zip(nodes, latent_records, item_bank, item_response_dataset):
    """Build ZIP bytes with org (flat + tree), latents, item bank, and item responses when present."""
    if not (nodes or latent_records or item_bank or item_response_dataset is not None):
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if nodes:
            z.writestr("org_hierarchy.json", json.dumps(nodes, indent=2, ensure_ascii=False))
            tree = hierarchy_to_tree(nodes)
            def _to_ser(node):
                return {"id": node["id"], "name": node["name"], "level": node["level"], "children": [_to_ser(ch) for ch in node.get("children", [])]}
            z.writestr("org_tree.json", json.dumps(_to_ser(tree), indent=2, ensure_ascii=False))
        if latent_records:
            z.writestr("team_latents.csv", pd.DataFrame(latent_records).to_csv(index=False))
            z.writestr("team_latents.json", json.dumps(latent_records, indent=2, ensure_ascii=False))
        if item_bank:
            z.writestr("item_bank.json", json.dumps(item_bank, indent=2, ensure_ascii=False))
            z.writestr("item_bank.csv", pd.DataFrame(item_bank).to_csv(index=False))
        if item_response_dataset is not None:
            z.writestr("item_responses.csv", item_response_dataset.to_csv(index=False))
            z.writestr("item_responses.json", item_response_dataset.to_json(orient="records", indent=2))
    buf.seek(0)
    return buf.getvalue()
st.title("Org hierarchy & latent culture simulator")
st.caption("Generate org structure (with employees), then team-level latent scores (15 dimensions, 95% intervals).")

# Session state
if "config" not in st.session_state:
    st.session_state.config = get_suggested_config()
if "nodes" not in st.session_state:
    st.session_state.nodes = []
if "latent_records" not in st.session_state:
    st.session_state.latent_records = []
if "item_bank" not in st.session_state:
    st.session_state.item_bank = []
if "item_response_dataset" not in st.session_state:
    st.session_state.item_response_dataset = None


def apply_quick_generate(n_div, dept_min, dept_max, teams_min, teams_max, team_size_min, team_size_max, company_name, seed):
    """Build random structure from min–max ranges and generate hierarchy."""
    rng = np.random.default_rng(seed if seed else None)
    dept_min, dept_max = max(1, dept_min), max(dept_min, dept_max)
    teams_min, teams_max = max(1, teams_min), max(teams_min, teams_max)
    team_size_min, team_size_max = max(1, team_size_min), max(team_size_min, team_size_max)
    n_depts_per_div = [int(rng.integers(dept_min, dept_max + 1)) for _ in range(n_div)]
    total_depts = sum(n_depts_per_div)
    n_teams_per_dept = [int(rng.integers(teams_min, teams_max + 1)) for _ in range(total_depts)]
    st.session_state.config = HierarchyConfig(
        use_explicit=False,
        counts=CountsConfig(
            n_divisions=n_div,
            n_departments_per_division=n_depts_per_div,
            n_teams_per_department=n_teams_per_dept,
            n_employees_per_team=(team_size_min + team_size_max) // 2,
            n_employees_per_team_min=team_size_min,
            n_employees_per_team_max=team_size_max,
            company_name=company_name,
            division_name_prefix="Division",
            department_name_prefix="Dept",
            team_name_prefix="Team",
            employee_name_prefix="Employee",
        ),
    )
    st.session_state.nodes = generate_hierarchy(st.session_state.config, rng=rng)


def apply_quick_generate_with_names(n_div, dept_min, dept_max, teams_min, teams_max, team_size_min, team_size_max, company_name, seed):
    """Build random structure with division/department names from catalogue."""
    rng = np.random.default_rng(seed if seed else None)
    st.session_state.config = get_random_explicit_config(
        n_divisions=n_div,
        n_departments_per_division_min=max(1, dept_min),
        n_departments_per_division_max=max(dept_min, dept_max),
        n_teams_per_department_min=max(1, teams_min),
        n_teams_per_department_max=max(teams_min, teams_max),
        team_size_min=max(1, team_size_min),
        team_size_max=max(team_size_min, team_size_max),
        company_name=company_name,
        rng=rng,
        seed=seed,
    )
    st.session_state.nodes = generate_hierarchy(st.session_state.config, rng=rng)


with st.sidebar:
    st.header("Config")
    st.subheader("Quick start")
    # Defaults = former "suggested" style (6 divs, 3–6 depts, 2–6 teams, 4–12 team size)
    n_div = st.number_input("Number of divisions", min_value=1, max_value=20, value=6, key="qs_n_div")
    dept_min = st.number_input("Departments per division (min)", min_value=1, max_value=15, value=3, key="qs_dept_min")
    dept_max = st.number_input("Departments per division (max)", min_value=1, max_value=15, value=6, key="qs_dept_max")
    teams_min = st.number_input("Teams per department (min)", min_value=1, max_value=20, value=2, key="qs_teams_min")
    teams_max = st.number_input("Teams per department (max)", min_value=1, max_value=20, value=6, key="qs_teams_max")
    team_size_min = st.number_input("Team size (min)", min_value=1, max_value=50, value=4, key="qs_team_min")
    team_size_max = st.number_input("Team size (max)", min_value=1, max_value=50, value=12, key="qs_team_max")
    st.caption(f"**Average team size:** {(team_size_min + team_size_max) / 2:.1f}")
    use_names = st.checkbox("Use names from catalogue", value=True, key="qs_use_names", help="Division and department names from a realistic catalogue (e.g. Production, R&D, Body Shop, Marketing). Uncheck for Division 1, Dept 1.1, …")
    company_name = st.text_input("Company name", value="AutoCorp", key="qs_company")
    seed = st.number_input("Random seed (0 = new each time)", min_value=0, value=0, key="qs_seed")
    if st.button("Generate", type="primary", use_container_width=True, key="qs_generate"):
        if use_names:
            apply_quick_generate_with_names(n_div, dept_min, dept_max, teams_min, teams_max, team_size_min, team_size_max, company_name, seed if seed else None)
        else:
            apply_quick_generate(n_div, dept_min, dept_max, teams_min, teams_max, team_size_min, team_size_max, company_name, seed if seed else None)
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

    st.divider()
    st.subheader("Download all datasets")
    zip_bytes = _build_download_all_zip(
        st.session_state.nodes,
        st.session_state.latent_records,
        st.session_state.item_bank,
        st.session_state.get("item_response_dataset"),
    )
    if zip_bytes is not None:
        st.download_button("Download all as ZIP", data=zip_bytes, file_name="simulation_datasets.zip", mime="application/zip", key="dl_all_zip", use_container_width=True)
    else:
        st.caption("Generate org (and optionally latents, item bank, item responses) to enable download.")

nodes = st.session_state.nodes
if not nodes:
    st.warning("No hierarchy generated. Set parameters in the sidebar and click **Generate**.")
    st.stop()

tab_org, tab_latent, tab_explore, tab_items = st.tabs(["Org hierarchy", "Latent scores", "Explore", "Items / IRT"])

with tab_org:
    counts = summary(nodes)
    st.subheader("Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Company", counts.get("company", 0))
    col2.metric("Divisions", counts.get("division", 0))
    col3.metric("Departments", counts.get("department", 0))
    col4.metric("Teams", counts.get("team", 0))
    col5.metric("Employees", counts.get("employee", 0))

    # Adjust structure (explicit only): edit names/counts then regenerate
    if st.session_state.config.use_explicit and st.session_state.config.explicit.divisions:
        st.subheader("Adjust structure")
        st.caption("Edit division/department names, number of teams, and team size (min–max). Then regenerate.")
        explicit = st.session_state.config.explicit
        with st.form("adjust_explicit_form"):
            company_adj = st.text_input("Company name", value=explicit.company_name, key="adj_company")
            div_names_adj = []
            dept_names_adj = []
            n_teams_adj = []
            tmin_adj = []
            tmax_adj = []
            for i, div in enumerate(explicit.divisions):
                with st.expander(f"Division: {div.name}", expanded=(i < 2)):
                    div_names_adj.append(st.text_input("Division name", value=div.name, key=f"adj_div_name_{i}"))
                    for j, dept in enumerate(div.departments):
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            dept_names_adj.append(st.text_input("Department", value=dept.name, key=f"adj_dept_name_{i}_{j}"))
                        with c2:
                            n_teams_adj.append(st.number_input("Teams", min_value=1, max_value=50, value=dept.n_teams, key=f"adj_n_teams_{i}_{j}"))
                        tmin = getattr(dept, "n_employees_per_team_min", None) or dept.n_employees_per_team
                        tmax = getattr(dept, "n_employees_per_team_max", None) or dept.n_employees_per_team
                        with c3:
                            tmin_adj.append(st.number_input("Team size min", 1, 50, value=int(tmin), key=f"adj_tmin_{i}_{j}"))
                        with c4:
                            tmax_adj.append(st.number_input("Team size max", 1, 50, value=int(tmax), key=f"adj_tmax_{i}_{j}"))
            if st.form_submit_button("Regenerate from this structure"):
                new_divisions = []
                flat = 0
                for i, div in enumerate(explicit.divisions):
                    depts = []
                    for j in range(len(div.departments)):
                        idx = flat + j
                        depts.append(DepartmentSpec(
                            name=dept_names_adj[idx],
                            n_teams=int(n_teams_adj[idx]),
                            n_employees_per_team=(tmin_adj[idx] + tmax_adj[idx]) // 2,
                            n_employees_per_team_min=tmin_adj[idx],
                            n_employees_per_team_max=tmax_adj[idx],
                        ))
                    flat += len(div.departments)
                    new_divisions.append(DivisionSpec(name=div_names_adj[i], departments=depts))
                st.session_state.config = HierarchyConfig(
                    use_explicit=True,
                    explicit=ExplicitConfig(company_name=company_adj, divisions=new_divisions),
                )
                rng = np.random.default_rng()
                st.session_state.nodes = generate_hierarchy(st.session_state.config, rng=rng)
                try:
                    st.rerun()
                except Exception:
                    st.experimental_rerun()

    st.subheader("Tree preview")
    tree = hierarchy_to_tree(nodes)

    def tree_md(node: dict, indent: int = 0) -> str:
        pre = "  " * indent + "- "
        name = node.get("name", node.get("id", ""))
        level = node.get("level", "")
        n_children = len(node.get("children", []))
        if indent < 2:
            rest = "\n".join(tree_md(ch, indent + 1) for ch in node.get("children", []))
            return f"{pre}**{name}** ({level}) {f'({n_children} children)' if n_children else ''}\n{rest}"
        if n_children:
            return f"{pre}**{name}** ({level}) — {n_children} children (collapsed)"
        return f"{pre}{name} ({level})"

    st.markdown(tree_md(tree))

    st.subheader("Export")
    out_flat = json.dumps(nodes, indent=2, ensure_ascii=False)
    st.download_button("Download hierarchy (flat JSON)", data=out_flat, file_name="org_hierarchy.json", mime="application/json", key="dl_flat")

    def to_serializable(node: dict) -> dict:
        return {
            "id": node["id"],
            "name": node["name"],
            "level": node["level"],
            "children": [to_serializable(ch) for ch in node.get("children", [])],
        }
    out_tree = json.dumps(to_serializable(tree), indent=2, ensure_ascii=False)
    st.download_button("Download hierarchy (nested tree JSON)", data=out_tree, file_name="org_tree.json", mime="application/json", key="dl_tree")

    with st.expander("Show raw flat list (first 20 nodes)"):
        st.json(nodes[:20])

with tab_latent:
    st.subheader("Person-level (employee) latent culture scores")
    st.markdown("Uses the **current org structure**. Each **employee** gets a 15-dim latent (person latent: the rater’s own culture view). Hierarchy: division → department → team → **individual** variance. One row = one employee × one dimension.")
    n_teams = len(get_teams(nodes))
    if n_teams == 0:
        st.info("No teams in the current org. Generate an org with at least one team first.")
    else:
        if "latent_config" not in st.session_state:
            st.session_state.latent_config = get_suggested_latent_config()
        cfg = st.session_state.latent_config
        with st.expander("Latent generation parameters (optional)", expanded=False):
            st.markdown("**Population mean per dimension (0–100)**")
            st.caption("Set the mean for each of the 15 culture dimensions. Use **Randomize means** below to draw all 15 around a global mean, or edit individually.")
            r1, r2, r3 = st.columns([1, 1, 1])
            with r1:
                global_mean = st.number_input("Global mean", min_value=0.0, max_value=100.0, value=50.0, key="lat_global_mean", help="Target mean over all 15 dimensions when randomizing")
            with r2:
                mu_spread = st.number_input("Spread (SD around global)", min_value=0.0, max_value=25.0, value=8.0, key="lat_mu_spread", help="How much each dimension mean varies around the global mean (0 = all equal)")
            with r3:
                st.write("")
                st.write("")
                if st.button("Randomize means", key="lat_randomize_mu"):
                    rng_mu = np.random.default_rng()
                    mu_new = np.clip(global_mean + rng_mu.normal(0, mu_spread, 15), 0.0, 100.0)
                    st.session_state.latent_config.mu = mu_new.tolist()
                    st.session_state["lat_mu_revision"] = st.session_state.get("lat_mu_revision", 0) + 1
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
            mu_rev = st.session_state.get("lat_mu_revision", 0)
            mu_list = []
            mu_cols = st.columns(5)
            for col_idx, (domain_name, dims) in enumerate(DOMAINS):
                with mu_cols[col_idx]:
                    st.caption(f"**{domain_name}**")
                    for dim_id, dim_name in dims:
                        idx = dimension_index(dim_id)
                        current = float(cfg.mu[idx]) if cfg.mu and idx < len(cfg.mu) else 50.0
                        val = st.number_input(dim_name, min_value=0.0, max_value=100.0, value=current, key=f"lat_mu_{idx}_{mu_rev}", format="%.1f")
                        mu_list.append(val)
            st.session_state.latent_config.mu = mu_list
            st.markdown("**Correlation structure (15 dimensions)**")
            st.caption("**True correlation in the entire population.** Data from a single company or sample will look more random (weaker observed correlations).")
            r_within = st.slider("Within-domain correlation", 0.0, 0.95, float(cfg.r_within_domain), key="lat_rw", help="True population correlation between dimensions in the same domain (e.g. Zuversicht, Richtung, Energie)")
            r_cross = st.slider("Cross-domain correlation", 0.0, 0.95, float(cfg.r_cross_domain), key="lat_rb", help="True population correlation between dimensions in different domains")
            st.session_state.latent_config.r_within_domain = r_within
            st.session_state.latent_config.r_cross_domain = r_cross
            st.markdown("**Variance partition (measurement / individual / team / department / division)**")
            st.caption("Proportions of variance at each level. Should sum to 1 (will be normalized).")
            vw = st.slider("Measurement (noise)", 0.0, 1.0, float(getattr(cfg, "var_within", 0.2)), key="lat_vw")
            v_ind = st.slider("Individual (within-team person latent)", 0.0, 1.0, float(getattr(cfg, "var_individual", 0.45)), key="lat_vind")
            vt = st.slider("Team", 0.0, 1.0, float(cfg.var_team), key="lat_vt")
            vd = st.slider("Department", 0.0, 1.0, float(cfg.var_dept), key="lat_vd")
            vdiv = st.slider("Division", 0.0, 1.0, float(cfg.var_division), key="lat_vdiv")
            total_var = vw + v_ind + vt + vd + vdiv
            if total_var > 0:
                st.session_state.latent_config.var_within = vw / total_var
                st.session_state.latent_config.var_individual = v_ind / total_var
                st.session_state.latent_config.var_team = vt / total_var
                st.session_state.latent_config.var_dept = vd / total_var
                st.session_state.latent_config.var_division = vdiv / total_var
            st.session_state.latent_config.sigma_total = st.number_input("Total SD (scale of variation, 0–100)", 5.0, 30.0, float(cfg.sigma_total), key="lat_sigma", help="Overall standard deviation per dimension before partition")
            st.session_state.latent_config.base_measurement_sd = st.number_input("Base measurement SD (÷ √n for interval width)", 0.1, 20.0, float(cfg.base_measurement_sd), key="lat_bmsd")
        if st.button("Generate latent scores", type="primary", key="gen_latent"):
            st.session_state.latent_records = generate_latents(nodes, st.session_state.latent_config, include_true_latent=True)
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()
        recs = st.session_state.latent_records
        if recs:
            import pandas as pd
            df = pd.DataFrame(recs)
            st.metric("Records", len(recs))
            st.dataframe(df.head(60), use_container_width=True)
            st.caption("First 60 rows. One row = one employee × one dimension (employee_id, team_id, point, lower_95, upper_95, true_latent).")
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download latents (CSV)", data=csv_bytes, file_name="team_latents.csv", mime="text/csv", key="dl_latent_csv")
            st.download_button("Download latents (JSON)", data=json.dumps(recs, indent=2, ensure_ascii=False), file_name="team_latents.json", mime="application/json", key="dl_latent_json")
        else:
            st.info("Click **Generate latent scores** to create person-level (employee) culture profiles from the current org.")

with tab_explore:
    st.subheader("Fractal drill-down: org → division → department → team → individuals")
    recs = st.session_state.latent_records
    if not recs or not nodes:
        st.info("Generate an **org** and then **latent scores** first. Then return here to explore.")
    else:
        if "explore_path" not in st.session_state:
            st.session_state.explore_path = []
        if "explore_selector" not in st.session_state:
            st.session_state.explore_selector = "dim:zuversicht"
        path = st.session_state.explore_path
        opts = get_dimension_display_options()
        valid_opts = [(v, l) for v, l in opts if v != "---"]
        idx = next((i for i, (v, _) in enumerate(valid_opts) if v == st.session_state.explore_selector), 0)
        sel = st.selectbox(
            "Dimension or domain",
            range(len(valid_opts)),
            format_func=lambda i: valid_opts[i][1],
            index=idx,
            key="explore_sel",
        )
        st.session_state.explore_selector = valid_opts[sel][0]
        selector = st.session_state.explore_selector

        hier = build_hierarchy(nodes)
        by_id = hier["by_id"]
        ag = aggregate_means(recs, hier, selector)
        org_mean = ag["org_mean"]
        div_means = ag["division_means"]
        dept_means = ag["department_means"]
        team_vals = ag["team_values"]

        # Breadcrumb: click a segment to go back to that level
        bc_parts = ["Org"]
        if path:
            bc_parts.append(by_id.get(path[0], {}).get("name", path[0]))
        if len(path) >= 2:
            bc_parts.append(by_id.get(path[1], {}).get("name", path[1]))
        if len(path) >= 3:
            bc_parts.append(by_id.get(path[2], {}).get("name", path[2]))
        nbc = len(bc_parts)
        cols = st.columns([1] * (nbc * 2 - 1))
        for i in range(nbc):
            with cols[i * 2]:
                if st.button(bc_parts[i], key=f"bc_{i}", type="primary" if i == len(path) else "secondary"):
                    st.session_state.explore_path = path[:i]
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
            if i < nbc - 1:
                with cols[i * 2 + 1]:
                    st.write(" › ")
        st.caption("Click a level to go back.")

        # Forest plot by level: point estimates + horizontal intervals where available
        ref_mean = org_mean
        lowers = None
        uppers = None
        if len(path) == 0:
            ref_mean = org_mean
            labels = [by_id.get(did, {}).get("name", did) for did in hier["division_ids"]]
            values = [div_means.get(did, org_mean) for did in hier["division_ids"]]
            title = "Divisions vs org mean"
        elif len(path) == 1:
            div_id = path[0]
            ref_mean = div_means.get(div_id, org_mean)
            dept_ids = hier["dept_ids_per_div"].get(div_id, [])
            labels = [by_id.get(did, {}).get("name", did) for did in dept_ids]
            values = [dept_means.get(did, ref_mean) for did in dept_ids]
            title = f"Departments vs division mean ({by_id.get(div_id, {}).get('name', div_id)})"
        elif len(path) == 2:
            dept_id = path[1]
            ref_mean = dept_means.get(dept_id, org_mean)
            team_ids = hier["team_ids_per_dept"].get(dept_id, [])
            labels = [by_id.get(tid, {}).get("name", tid) for tid in team_ids]
            points_and_ints = [get_point_interval_for_selector(recs, tid, selector) for tid in team_ids]
            values = [p for p, _, _ in points_and_ints]
            lowers = [lo if lo is not None else p for p, lo, hi in points_and_ints]
            uppers = [hi if hi is not None else p for p, lo, hi in points_and_ints]
            title = f"Teams vs department mean ({by_id.get(dept_id, {}).get('name', dept_id)})"
        else:
            team_id = path[2]
            ref_mean = team_vals.get(team_id, org_mean)
            ind_vals = simulate_individuals(team_id, recs, nodes, selector, within_sd=10.0)
            n = len(ind_vals)
            labels = [f"Individual {i+1}" for i in range(n)]
            values = ind_vals
            title = f"Individuals vs team mean ({by_id.get(team_id, {}).get('name', team_id)}) — person latents"

        fig = go.Figure()
        fig.add_vline(x=ref_mean, line_dash="dash", line_color="gray", annotation_text="Reference mean")
        if values:
            err_minus = None
            err_plus = None
            if lowers is not None and uppers is not None:
                err_minus = [max(0, v - lo) for v, lo in zip(values, lowers)]
                err_plus = [max(0, hi - v) for v, hi in zip(values, uppers)]
            fig.add_trace(
                go.Scatter(
                    x=values,
                    y=labels,
                    mode="markers",
                    marker=dict(size=10, color="steelblue", symbol="diamond"),
                    error_x=dict(
                        type="data",
                        symmetric=False,
                        array=err_plus if err_plus else [0] * len(values),
                        arrayminus=err_minus if err_minus else [0] * len(values),
                        thickness=1.5,
                        color="steelblue",
                    ),
                    name="Estimate",
                )
            )
        fig.update_layout(
            title=title,
            xaxis_title="Score (0–100)",
            xaxis_range=[0, 100],
            yaxis=dict(autorange="reversed"),
            height=max(400, 50 * len(labels)),
            margin=dict(l=150),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Drill-down selector
        if len(path) == 0:
            div_options = hier["division_ids"]
            if div_options:
                chosen = st.selectbox(
                    "Drill into division",
                    range(len(div_options)),
                    format_func=lambda i: by_id.get(div_options[i], {}).get("name", div_options[i]),
                    key="drill_div",
                )
                if st.button("Go to division", key="go_div"):
                    st.session_state.explore_path = [div_options[chosen]]
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
        elif len(path) == 1:
            dept_ids = hier["dept_ids_per_div"].get(path[0], [])
            if dept_ids:
                chosen = st.selectbox(
                    "Drill into department",
                    range(len(dept_ids)),
                    format_func=lambda i: by_id.get(dept_ids[i], {}).get("name", dept_ids[i]),
                    key="drill_dept",
                )
                if st.button("Go to department", key="go_dept"):
                    st.session_state.explore_path = [path[0], dept_ids[chosen]]
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
        elif len(path) == 2:
            team_ids = hier["team_ids_per_dept"].get(path[1], [])
            if team_ids:
                chosen = st.selectbox(
                    "Drill into team",
                    range(len(team_ids)),
                    format_func=lambda i: by_id.get(team_ids[i], {}).get("name", team_ids[i]),
                    key="drill_team",
                )
                if st.button("Go to team", key="go_team"):
                    st.session_state.explore_path = [path[0], path[1], team_ids[chosen]]
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
        if len(path) >= 3:
            st.caption("At team level: individuals show actual person-level latents (one per employee).")

with tab_items:
    st.subheader("Item bank & IRT (sliders 0–100)")
    st.markdown("Define an **item bank** with **logistic** (S-shaped) item model: E[Y] = 100·logistic(α + λ·(θ−50)/50), α = logit(ν/100). Bounded in (0,100). Each item has ν (expected score at θ=50), λ (discrimination), and residual SD (σ).")
    import numpy as np

    n_per_dim = st.number_input("Items per dimension", min_value=1, max_value=10, value=4, key="items_per_dim")
    quality_bias = st.slider(
        "Item pool quality (0 = more weak/noisy items, 1 = more strong/precise items)",
        0.0, 1.0, 0.5, 0.05, key="item_quality_bias",
        help="Shifts the likelihood of drawing good vs bad items; pool still has a mix.",
    )
    col_gen, col_sug = st.columns(2)
    with col_gen:
        if st.button("Generate item bank", type="primary", key="gen_bank"):
            st.session_state.item_bank = create_item_bank(n_per_dim)
            st.session_state.item_bank_revision = 0
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()
    with col_sug:
        if st.session_state.item_bank and st.button("Suggest parameters (literature-based)", key="suggest_params"):
            apply_suggested_parameters(
                st.session_state.item_bank,
                rng=np.random.default_rng(),
                quality_bias=quality_bias,
            )
            # Bump revision so widget keys change and inputs show updated bank (no stale state)
            st.session_state.item_bank_revision = st.session_state.get("item_bank_revision", 0) + 1
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

    bank = st.session_state.item_bank
    if not bank:
        st.info("Set **Items per dimension** and click **Generate item bank** to create items for all 15 dimensions.")
    else:
        st.metric("Total items", len(bank))
        # Edit parameters first so ICC plot uses current values
        st.subheader("Edit item parameters")
        _rev = st.session_state.get("item_bank_revision", 0)
        with st.expander("Per-item ν, λ, σ (editable)", expanded=True):
            for i, item in enumerate(bank):
                with st.container():
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nu = st.number_input("ν (intercept)", min_value=0.0, max_value=100.0, value=float(item["nu"]), key=f"nu_{i}_{_rev}", format="%.1f")
                    with c2:
                        lam = st.number_input("λ (slope)", min_value=0.1, max_value=3.0, value=float(item["lambda"]), key=f"lam_{i}_{_rev}", format="%.2f")
                    with c3:
                        sig = st.number_input("σ (residual SD)", min_value=0.1, max_value=30.0, value=float(item["sigma"]), key=f"sig_{i}_{_rev}", format="%.1f")
                    item["nu"] = nu
                    item["lambda"] = lam
                    item["sigma"] = sig
                    st.caption(f"**{item['item_id']}** — dimension: {item['dimension_id']}")

        st.subheader("ICC plot (expected response vs latent θ)")
        dim_filter = st.selectbox("Show all items or one dimension", ["All dimensions"] + DIMENSION_IDS, key="icc_dim_filter")
        if dim_filter == "All dimensions":
            fig = build_icc_figure(bank)
        else:
            fig = build_icc_figure_by_dimension(bank, dim_filter)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Generate item response dataset")
        st.markdown("Use **person-level (employee) latent scores** to generate item responses. Each employee’s 15-dim theta drives their item responses via the **logistic** item model (S-shaped, bounded 0–100). One row per employee. Then run **factor analysis** on this dataset (section below).")
        recs_items = st.session_state.latent_records
        nodes_items = st.session_state.nodes
        if not recs_items or not nodes_items:
            st.info("Generate **Org hierarchy** and **Latent scores** (person-level) first, then return here to generate the item response dataset.")
        else:
            if st.button("Generate item response dataset", type="primary", key="gen_item_resp"):
                try:
                    df_resp = simulate_item_responses_from_org(
                        recs_items, bank, nodes_items, rng=np.random.default_rng(),
                    )
                    st.session_state.item_response_dataset = df_resp
                    for k in ("efa_done", "efa_loadings", "efa_item_labels", "efa_factor_corr", "efa_R_truth", "efa_theta_true", "efa_factor_scores", "efa_irt_scores"):
                        st.session_state.pop(k, None)
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
                except Exception as e:
                    st.error(str(e))
            if st.session_state.item_response_dataset is not None:
                df_resp = st.session_state.item_response_dataset
                st.metric("Respondents (employees)", len(df_resp))
                st.dataframe(df_resp.head(30), use_container_width=True)
                st.caption("First 30 rows. Columns: respondent_id, employee_id, team_id, then one column per item.")
                csv_resp = df_resp.to_csv(index=False).encode("utf-8")
                st.download_button("Download item responses (CSV)", data=csv_resp, file_name="item_responses.csv", mime="text/csv", key="dl_item_resp_csv")
                st.download_button("Download item responses (JSON)", data=df_resp.to_json(orient="records", indent=2), file_name="item_responses.json", mime="application/json", key="dl_item_resp_json")

        st.subheader("Factor analysis & sanity check (before export)")
        resp_dataset = st.session_state.get("item_response_dataset")
        if resp_dataset is None:
            st.info("Generate the **item response dataset** (section above) first. Then run factor analysis and sanity checks here.")
        else:
            st.markdown("Run **EFA** on the item response dataset (**%d individuals** × items). Ground truth is taken from the **data-generating process** (true latent correlation and thetas)." % len(resp_dataset))
            if st.button("Run factor analysis on dataset", type="primary", key="run_efa"):
                try:
                    data, dim_index_per_item, item_ids = response_dataset_to_efa(resp_dataset, bank)
                except Exception as e:
                    st.error(str(e))
                    data = None
                if data is not None:
                    recs = st.session_state.get("latent_records") or []
                    R_truth, theta_true = true_thetas_and_correlation_from_response_dataset(resp_dataset, recs)
                    n_dim = len(DIMENSION_IDS)
                    loadings, factor_corr, fa_model = run_efa(data, n_factors=n_dim, rotation="promax")
                    loadings_reord, factor_corr_reord, factor_for_dim = reorder_factors_to_dimensions(loadings, dim_index_per_item, n_dim, factor_corr)
                    order_items = sorted(range(len(item_ids)), key=lambda i: (dim_index_per_item[i], item_ids[i]))
                    loadings_plot = loadings_reord[order_items, :n_dim]
                    item_labels = [f"{item_ids[i]} ({DIMENSION_IDS[dim_index_per_item[i]]})" for i in order_items]
                    factor_scores = get_efa_factor_scores(fa_model, data, factor_for_dim, n_dim)
                    irt_scores = irt_scores_from_response_dataset(resp_dataset, bank)
                    st.session_state.efa_loadings = loadings_plot
                    st.session_state.efa_item_labels = item_labels
                    st.session_state.efa_factor_corr = factor_corr_reord
                    st.session_state.efa_R_truth = R_truth
                    st.session_state.efa_theta_true = theta_true
                    st.session_state.efa_factor_scores = factor_scores
                    st.session_state.efa_irt_scores = irt_scores
                    st.session_state.efa_done = True
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()

        if st.session_state.get("efa_done") and "efa_loadings" in st.session_state:
            loadings_plot = st.session_state.efa_loadings
            item_labels = st.session_state.efa_item_labels
            factor_corr_plot = st.session_state.efa_factor_corr
            R_truth = st.session_state.efa_R_truth
            theta_true = st.session_state.get("efa_theta_true")
            factor_scores = st.session_state.get("efa_factor_scores")
            irt_scores = st.session_state.get("efa_irt_scores")
            n_dim = len(DIMENSION_IDS)

            def _corr(a: np.ndarray, b: np.ndarray) -> float:
                if np.std(a) < 1e-8 or np.std(b) < 1e-8:
                    return 0.0
                c = np.corrcoef(a, b)[0, 1]
                return float(c) if not np.isnan(c) else 0.0

            st.success("Sanity check: EFA loadings, factor correlation vs true latent correlation, factor scores vs true thetas, and IRT scores vs true thetas.")
            # Loadings heatmap
            fig_load = go.Figure(data=go.Heatmap(
                z=loadings_plot,
                x=[DIMENSION_IDS[j] for j in range(loadings_plot.shape[1])],
                y=item_labels,
                colorscale="RdBu",
                zmid=0,
                zmin=-0.5,
                zmax=1,
            ))
            fig_load.update_layout(
                title="EFA loadings (items × dimension factor) — items ordered by true dimension",
                xaxis_title="Factor (matched to dimension)",
                yaxis_title="Item",
                height=max(400, 24 * len(item_labels)),
                margin=dict(l=180),
            )
            st.plotly_chart(fig_load, use_container_width=True)
            # Factor correlation vs true latent correlation (from DGP)
            st.markdown("**1. Factor correlation vs true latent correlation (from data-generating process)**")
            c1, c2 = st.columns(2)
            with c1:
                if factor_corr_plot is not None:
                    fig_fc = go.Figure(data=go.Heatmap(
                        z=factor_corr_plot,
                        x=DIMENSION_IDS,
                        y=DIMENSION_IDS,
                        colorscale="RdBu",
                        zmid=0,
                        zmin=-0.2,
                        zmax=1,
                    ))
                    fig_fc.update_layout(title="EFA factor correlation (reordered to dimensions)", height=450, margin=dict(l=120))
                    st.plotly_chart(fig_fc, use_container_width=True)
                else:
                    st.info("Factor correlation not available (PCA fallback uses orthogonal factors). Install factor_analyzer for oblique rotation.")
            with c2:
                fig_gt = go.Figure(data=go.Heatmap(
                    z=R_truth,
                    x=DIMENSION_IDS,
                    y=DIMENSION_IDS,
                    colorscale="RdBu",
                    zmid=0,
                    zmin=-0.2,
                    zmax=1,
                ))
                fig_gt.update_layout(title="True latent correlation (from DGP)", height=450, margin=dict(l=120))
                st.plotly_chart(fig_gt, use_container_width=True)
            if factor_corr_plot is not None:
                diff = np.abs(factor_corr_plot - R_truth)
                mean_diff = float(np.mean(diff))
                max_diff = float(np.max(diff))
                st.caption(f"Mean |EFA − true latent| = {mean_diff:.3f}, max = {max_diff:.3f}. Lower is better.")
            # 2. Factor scores vs true thetas
            if theta_true is not None and factor_scores is not None and theta_true.shape == factor_scores.shape:
                st.markdown("**2. EFA factor scores vs true thetas (from DGP)**")
                corr_efa = np.array([_corr(theta_true[:, d], factor_scores[:, d]) for d in range(n_dim)])
                fig_efa = go.Figure(data=go.Bar(x=DIMENSION_IDS, y=corr_efa, marker_color="steelblue"))
                fig_efa.update_layout(title="Correlation (EFA factor score vs true theta) per dimension", xaxis_tickangle=-45, height=380, yaxis_range=[-0.05, 1.05])
                st.plotly_chart(fig_efa, use_container_width=True)
                st.caption("Higher bars = EFA recovers the true latent dimension better.")
            # 3. IRT scores vs true thetas
            if theta_true is not None and irt_scores is not None and theta_true.shape == irt_scores.shape:
                st.markdown("**3. IRT-based scores vs true thetas (from DGP)**")
                corr_irt = np.array([_corr(theta_true[:, d], irt_scores[:, d]) for d in range(n_dim)])
                fig_irt = go.Figure(data=go.Bar(x=DIMENSION_IDS, y=corr_irt, marker_color="darkgreen"))
                fig_irt.update_layout(title="Correlation (IRT score vs true theta) per dimension", xaxis_tickangle=-45, height=380, yaxis_range=[-0.05, 1.05])
                st.plotly_chart(fig_irt, use_container_width=True)
                st.caption("Higher bars = IRT model recovers the true latent dimension better.")

        st.subheader("Export item bank")
        out_json = json.dumps(bank, indent=2, ensure_ascii=False)
        st.download_button("Download item bank (JSON)", data=out_json, file_name="item_bank.json", mime="application/json", key="dl_items_json")
        df_items = pd.DataFrame(bank)
        csv_bytes = df_items.to_csv(index=False).encode("utf-8")
        st.download_button("Download item bank (CSV)", data=csv_bytes, file_name="item_bank.csv", mime="text/csv", key="dl_items_csv")

        st.subheader("Download all")
        st.markdown("One archive with org hierarchy (flat + tree), latent scores, item bank, and item response dataset (when generated).")
        zip_all = _build_download_all_zip(
            st.session_state.nodes,
            st.session_state.latent_records,
            bank,
            st.session_state.get("item_response_dataset"),
        )
        if zip_all is not None:
            st.download_button("Download all as ZIP", data=zip_all, file_name="simulation_datasets.zip", mime="application/zip", key="dl_all_zip_items", type="primary")
        else:
            st.info("Generate **Org hierarchy** and optionally **Latent scores**, then create an **item bank** to enable Download all.")
