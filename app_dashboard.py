"""
Organizational culture dashboard — view-only.
Loads precomputed results from dashboard_input. Which file is read from dashboard_input/dashboard_config.json
(data_file: "culture_results.json" or "culture_results_sample.json"). If config is missing, uses
culture_results.json if present else culture_results_sample.json.
"""
import base64
import json
from pathlib import Path

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from src.dimensions import (
    DOMAINS,
    DIMENSION_IDS,
    SUPER_SHORT_LABELS,
    get_super_description,
    get_sub_description,
)
from src.bayesian_irt import (
    sample_prior_org_sub,
    get_superfactor_names,
    get_subfactor_names,
)
from src.hierarchical_posterior import sub_to_super_means_sds

from components.sunburst_select import sunburst_select


@st.cache_data(show_spinner=False)
def _cached_drill_hierarchy(div_ids_tuple, div_to_depts_items_tuple, dept_to_teams_items_tuple):
    """Return sunburst ids/parents and _all_ids for drill-down; cache by hierarchy shape only (no by_id = fast)."""
    div_ids = list(div_ids_tuple)
    div_to_depts = dict(div_to_depts_items_tuple)
    dept_to_teams = dict(dept_to_teams_items_tuple)

    sunburst_ids = ["org"]
    sunburst_parents = [""]
    for d in div_ids:
        sunburst_ids.append(d)
        sunburst_parents.append("org")
    all_dept_pairs = []
    for d in div_ids:
        depts = div_to_depts.get(d) or []
        for dept in depts:
            all_dept_pairs.append((d, dept))
            sunburst_ids.append(dept)
            sunburst_parents.append(d)
    for _d, dept in all_dept_pairs:
        teams = dept_to_teams.get(dept) or []
        for t in teams:
            sunburst_ids.append(t)
            sunburst_parents.append(dept)

    _all_ids = ["org"] + list(div_ids)
    for _d in div_ids:
        _all_ids.extend(div_to_depts.get(_d) or [])
    for _d in div_ids:
        for _dept in div_to_depts.get(_d) or []:
            _all_ids.extend(dept_to_teams.get(_dept) or [])

    return sunburst_ids, sunburst_parents, _all_ids


@st.cache_data(show_spinner=False)
def _cached_sunburst_fig_json(level_id, ids_tuple, labels_tuple, parents_tuple):
    """Return Plotly sunburst figure as JSON; cache by (level, ids, labels, parents) to avoid rebuilds."""
    ids = list(ids_tuple)
    labels = list(labels_tuple)
    parents = list(parents_tuple)
    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            branchvalues="total",
            level=level_id if level_id else "",
            marker=dict(colorscale="Blues", cmid=50),
            hovertemplate="%{label}<extra></extra>",
            customdata=ids,
        )
    )
    fig.update_traces(sort=False, selector=dict(type="sunburst"))
    fig.update_layout(
        margin=dict(t=30, b=30, l=30, r=30),
        height=380,
        title_text="Org structure — click a slice to select that unit",
        title_font_size=14,
    )
    return fig.to_json()


# Path to the folder where precomputed results and assets live
DASHBOARD_INPUT_DIR = Path(__file__).resolve().parent / "dashboard_input"
DASHBOARD_CONFIG_PATH = DASHBOARD_INPUT_DIR / "dashboard_config.json"
ORG_HIERARCHY_PATH = DASHBOARD_INPUT_DIR / "org_hierarchy.json"
ITEM_BANK_PATH = DASHBOARD_INPUT_DIR / "item_bank.json"
CULTURE_RESULTS_PATH = DASHBOARD_INPUT_DIR / "culture_results.json"
CULTURE_RESULTS_SAMPLE_PATH = DASHBOARD_INPUT_DIR / "culture_results_sample.json"


def _get_data_file_path():
    """Which culture results file to load. From dashboard_config.json if present, else default."""
    if DASHBOARD_CONFIG_PATH.exists():
        try:
            with open(DASHBOARD_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            name = cfg.get("data_file") or ""
            if name == "culture_results_sample.json":
                return CULTURE_RESULTS_SAMPLE_PATH if CULTURE_RESULTS_SAMPLE_PATH.exists() else None
            if name == "culture_results.json":
                return CULTURE_RESULTS_PATH if CULTURE_RESULTS_PATH.exists() else None
        except Exception:
            pass
    return CULTURE_RESULTS_PATH if CULTURE_RESULTS_PATH.exists() else (CULTURE_RESULTS_SAMPLE_PATH if CULTURE_RESULTS_SAMPLE_PATH.exists() else None)

st.set_page_config(page_title="Organizational Culture Dashboard", layout="wide", initial_sidebar_state="expanded")

# Paths for dimension icons (5 superfactors)
ICONS_DIR = DASHBOARD_INPUT_DIR / "icons"
SUPERFACTOR_ICON_KEYS = ["momentum", "connection", "leadership", "growth", "traction"]

# -----------------------------------------------------------------------------
# Load from dashboard_input on startup
# -----------------------------------------------------------------------------
def load_org_hierarchy():
    if not ORG_HIERARCHY_PATH.exists():
        return None, f"Not found: {ORG_HIERARCHY_PATH.name}"
    try:
        with open(ORG_HIERARCHY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return None, "Expected a list of nodes"
        return data, None
    except Exception as e:
        return None, str(e)

def load_item_bank():
    if not ITEM_BANK_PATH.exists():
        return None, f"Not found: {ITEM_BANK_PATH.name}"
    try:
        with open(ITEM_BANK_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            return None, "Expected a non-empty list of items"
        return data, None
    except Exception as e:
        return None, str(e)

org_nodes, org_err = load_org_hierarchy()
item_bank, bank_err = load_item_bank()

# -----------------------------------------------------------------------------
# Load precomputed culture results (no stats run in the app)
# -----------------------------------------------------------------------------
def load_precomputed_results():
    """Load the culture results file chosen by dashboard_config.json (or default). Sets session state. Returns True if loaded."""
    path = _get_data_file_path()
    if path is None:
        if "load_error" in st.session_state:
            del st.session_state.load_error
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        st.session_state.hierarchical_result = data.get("hierarchical_result")
        st.session_state.precomputed_summary_stats = data.get("summary_stats") or {}
        st.session_state.posterior_theta_org = np.array(data["posterior_theta_org"]) if data.get("posterior_theta_org") else None
        st.session_state.posterior_theta_sub = np.array(data["posterior_theta_sub"]) if data.get("posterior_theta_sub") else None
        rs = data.get("respondent_scores") or {}
        st.session_state.respondent_scores = rs if rs.get("team_id") else None
        st.session_state.belief_updated = bool(st.session_state.hierarchical_result)
        st.session_state.loaded_data_file = path.name  # which file was loaded (for display)
        if "load_error" in st.session_state:
            del st.session_state.load_error
        return True
    except Exception as e:
        st.session_state.load_error = str(e)
        return False

if "hierarchical_result" not in st.session_state:
    st.session_state.hierarchical_result = None
if "precomputed_summary_stats" not in st.session_state:
    st.session_state.precomputed_summary_stats = None
if "belief_updated" not in st.session_state:
    st.session_state.belief_updated = False
if "posterior_theta_org" not in st.session_state:
    st.session_state.posterior_theta_org = None
if "posterior_theta_sub" not in st.session_state:
    st.session_state.posterior_theta_sub = None

if "respondent_scores" not in st.session_state:
    st.session_state.respondent_scores = None
if "loaded_data_file" not in st.session_state:
    st.session_state.loaded_data_file = None
if "load_error" not in st.session_state:
    st.session_state.load_error = None

# Load results (file chosen by dashboard_config.json or default)
if st.session_state.hierarchical_result is None and _get_data_file_path() is not None:
    load_precomputed_results()

# -----------------------------------------------------------------------------
# Sidebar: Configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Setup")
    if org_err:
        st.warning(f"Org: {org_err}")
    else:
        n_nodes = len(org_nodes)
        levels = {}
        for n in org_nodes:
            lvl = n.get("level", "?")
            levels[lvl] = levels.get(lvl, 0) + 1
        st.success(f"**Org:** {n_nodes} nodes")
    if bank_err:
        st.warning(f"Bank: {bank_err}")
    else:
        st.success(f"**Item bank:** {len(item_bank)} items")
    if st.session_state.loaded_data_file:
        st.success(f"**Data loaded:** {st.session_state.loaded_data_file}")
        if st.session_state.loaded_data_file == "culture_results_sample.json":
            st.caption("From config: **dashboard_input/dashboard_config.json** (sample). Edit `data_file` for full data.")
        else:
            st.caption("To refresh: run `python scripts/prepare_dashboard_data.py` then reload.")
    elif CULTURE_RESULTS_PATH.exists() or CULTURE_RESULTS_SAMPLE_PATH.exists():
        err = st.session_state.get("load_error")
        st.warning("**Precomputed results** file present but failed to load." + (f" Error: {err}" if err else " Check format."))
    else:
        st.warning("**Precomputed results not found.** Run: `python scripts/prepare_dashboard_data.py` or add **culture_results_sample.json**.")
    with st.expander("Dimension guide (click for explanation)"):
        st.caption("Click a dimension to read its description.")
        sub_idx = 0
        for domain_name, dims in DOMAINS:
            st.markdown(f"**{domain_name}**")
            for _, dim_name in dims:
                with st.expander(dim_name):
                    st.write(get_sub_description(sub_idx))
                sub_idx += 1
        st.markdown("---")
        st.markdown("**5 super-dimensions**")
        for k in range(5):
            with st.expander(SUPER_SHORT_LABELS[k]):
                st.write(get_super_description(k))

n_samples_default = 6000
super_names = get_superfactor_names()
colors = ["#2d7d7d", "#c75b7a", "#e8a838", "#50c878", "#7b68a6"]
domain_colors = colors

# Zone bands for horizontal bar charts (goodness/badness): 0–40 low, 40–60 neutral, 60–100 good
def _bar_chart_zone_shapes():
    """Return Plotly shapes for background zones (layer='below')."""
    return [
        dict(type="rect", x0=0, x1=40, y0=0, y1=1, xref="x", yref="paper",
             fillcolor="rgba(235, 160, 160, 0.35)", line=dict(width=0), layer="below"),
        dict(type="rect", x0=40, x1=60, y0=0, y1=1, xref="x", yref="paper",
             fillcolor="rgba(255, 238, 180, 0.45)", line=dict(width=0), layer="below"),
        dict(type="rect", x0=60, x1=100, y0=0, y1=1, xref="x", yref="paper",
             fillcolor="rgba(160, 210, 160, 0.35)", line=dict(width=0), layer="below"),
        dict(type="line", x0=40, x1=40, y0=0, y1=1, xref="x", yref="paper",
             line=dict(color="rgba(180, 120, 120, 0.5)", width=1, dash="dot"), layer="below"),
        dict(type="line", x0=60, x1=60, y0=0, y1=1, xref="x", yref="paper",
             line=dict(color="rgba(120, 160, 120, 0.5)", width=1, dash="dot"), layer="below"),
    ]

# -----------------------------------------------------------------------------
# Main: Title, summary stats, and tabs (Culture at a glance | Statistical detail)
# -----------------------------------------------------------------------------
st.title("Organizational culture")
st.caption("Precomputed culture dimensions (0–100). Refresh by running `python scripts/prepare_dashboard_data.py`.")

hi = st.session_state.hierarchical_result
summary_stats = st.session_state.precomputed_summary_stats or {}

# Summary stats row — from precomputed results
if hi and summary_stats:
    n_respondents = summary_stats.get("n_respondents", 0)
    n_teams = summary_stats.get("n_teams", 0)
    n_departments = summary_stats.get("n_departments", 0)
    n_divisions = summary_stats.get("n_divisions", 0)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Respondents", f"{n_respondents:,}")
    s2.metric("Teams", f"{n_teams:,}")
    s3.metric("Departments", f"{n_departments:,}")
    s4.metric("Divisions", f"{n_divisions:,}")
    overall_val = float(np.mean(hi["org"]["mean_super"])) if hi.get("org") and hi["org"].get("mean_super") is not None else None
    if overall_val is not None:
        s5.metric("Overall culture (0–100)", f"{overall_val:.1f}")
    else:
        s5.metric("Overall culture", "—")
    st.markdown("")  # spacing

    # Find your superstars: top 3 teams or departments (global or by dimension)
    with st.expander("Find your superstars", expanded=False):
        st.caption("Discover top-performing teams or departments — by overall score or by a specific dimension.")
        by_id_star = hi.get("by_id") or {}
        team_means = hi.get("team", {}).get("means") or {}
        team_sds = hi.get("team", {}).get("sds") or {}
        dept_means = hi.get("department", {}).get("means") or {}
        dept_sds = hi.get("department", {}).get("sds") or {}
        dept_to_teams_star = hi.get("department", {}).get("dept_to_teams") or {}
        dept_to_division_star = hi.get("department", {}).get("dept_to_division") or {}
        # team_id -> (dept_id, division_id) for showing department and division for teams
        team_to_dept_div = {}
        for dept_id, tids in dept_to_teams_star.items():
            div_id = dept_to_division_star.get(dept_id)
            for tid in tids:
                team_to_dept_div[tid] = (dept_id, div_id)

        def _name_star(nid):
            return (by_id_star.get(nid) or {}).get("name", nid)

        level_star = st.radio("Level", ["Teams", "Departments"], horizontal=True, key="superstar_level")
        criteria_star = st.radio("Rank by", ["Global (average over 5 super-dimensions)", "By dimension"], horizontal=True, key="superstar_criteria")
        if criteria_star.startswith("By"):
            sub_names_star = []
            for _dn, dims in DOMAINS:
                sub_names_star.extend([dn for _, dn in dims])
            dim_opts_star = [(f"{SUPER_SHORT_LABELS[k]} (super)", "super", k) for k in range(5)]
            dim_opts_star += [(sub_names_star[j], "sub", j) for j in range(15)]
            sel_dim_star = st.selectbox("Dimension", range(len(dim_opts_star)), format_func=lambda i: dim_opts_star[i][0], key="superstar_dim")
            selected_dim_star = dim_opts_star[sel_dim_star]
        else:
            selected_dim_star = ("Global", "global", None)

        def _score_global(mean_15, sd_15):
            if mean_15 is None or sd_15 is None:
                return None
            m, s = np.asarray(mean_15), np.asarray(sd_15)
            super_m, _ = sub_to_super_means_sds(m, s)
            return float(np.mean(super_m))

        def _score_by_dim(mean_15, sd_15, kind, idx):
            if mean_15 is None or sd_15 is None:
                return None
            m, s = np.asarray(mean_15), np.asarray(sd_15)
            if kind == "super":
                super_m, _ = sub_to_super_means_sds(m, s)
                return float(super_m[idx])
            return float(m[idx])

        entities = []
        if level_star == "Teams":
            for eid, m15 in team_means.items():
                s15 = team_sds.get(eid)
                if selected_dim_star[1] == "global":
                    sc = _score_global(m15, s15)
                else:
                    sc = _score_by_dim(m15, s15, selected_dim_star[1], selected_dim_star[2])
                if sc is not None:
                    entities.append((eid, _name_star(eid), sc))
        else:
            for eid, m15 in dept_means.items():
                s15 = dept_sds.get(eid)
                if selected_dim_star[1] == "global":
                    sc = _score_global(m15, s15)
                else:
                    sc = _score_by_dim(m15, s15, selected_dim_star[1], selected_dim_star[2])
                if sc is not None:
                    entities.append((eid, _name_star(eid), sc))

        entities.sort(key=lambda x: -x[2])
        top3 = entities[:3]
        if not top3:
            st.info("No teams or departments with scores in the hierarchy.")
        else:
            for i, (eid, name, score) in enumerate(top3):
                medal = ["🥇", "🥈", "🥉"][i]
                if level_star == "Teams":
                    dept_id, div_id = team_to_dept_div.get(eid, (None, None))
                    dept_name = _name_star(dept_id) if dept_id else "—"
                    div_name = _name_star(div_id) if div_id else "—"
                    st.markdown(f"{medal} **{name}** — {score:.1f}  \n*{dept_name}, {div_name}*")
                else:
                    st.markdown(f"{medal} **{name}** — {score:.1f}")
            st.caption("Top 3 by " + ("overall (mean of 5 super-dimensions)" if selected_dim_star[1] == "global" else selected_dim_star[0]) + ".")

tab_overview, tab_statistical = st.tabs(["Culture at a glance", "Statistical detail"])

with tab_overview:
    if hi is not None and hi.get("org"):
        org = hi["org"]
        mean_super = np.asarray(org.get("mean_super", np.full(5, 50.0)))
        sd_super = np.asarray(org.get("sd_super", np.full(5, 15.0)))
        mean_sub = np.asarray(org.get("mean_sub", np.full(15, 50.0)))
        sd_sub = np.asarray(org.get("sd_sub", np.full(15, 15.0)))
        mean_super = np.clip(mean_super, 0, 100)
        mean_sub = np.clip(mean_sub, 0, 100)
        overall = float(np.mean(mean_super))
        sub_names_15 = []
        for _dn, dims in DOMAINS:
            sub_names_15.extend([dn for _, dn in dims])

        # Icons row: 5 dimension icons with short labels
        short_labels = ["Momentum", "Connection", "Leadership", "Growth", "Traction"]
        icon_cols = st.columns(5)
        for k, (name, key, short) in enumerate(zip(super_names, SUPERFACTOR_ICON_KEYS, short_labels)):
            icon_path = ICONS_DIR / f"{key}.png"
            with icon_cols[k]:
                if icon_path.exists():
                    st.image(str(icon_path), width=52, caption=short)
                else:
                    st.caption(short)

        # Scores at a glance: user chooses Bar charts or Spider; both support optional 95% CrI
        st.subheader("Scores at a glance")
        view_scores_as = st.radio("Show as", ["Bar charts", "Spider"], horizontal=True, key="view_scores_as")
        # 95% CrI: mean ± 1.96*SD, clipped to [0, 100]
        cri_scale = 1.96
        lo_super = np.clip(mean_super - cri_scale * sd_super, 0, 100)
        hi_super = np.clip(mean_super + cri_scale * sd_super, 0, 100)
        err_plus_super = hi_super - mean_super
        err_minus_super = mean_super - lo_super
        lo_sub = np.clip(mean_sub - cri_scale * sd_sub, 0, 100)
        hi_sub = np.clip(mean_sub + cri_scale * sd_sub, 0, 100)
        err_plus_sub = hi_sub - mean_sub
        err_minus_sub = mean_sub - lo_sub

        if view_scores_as == "Bar charts":
            show_cri_bars = st.checkbox("Show 95% credibility intervals in bar charts", value=False, key="show_cri_barchart")
            sub_colors = [domain_colors[i // 3] for i in range(15)]
            # One combined horizontal bar chart: 5 super + spacer + 15 sub, visually separated
            sep_label = " "  # spacer row between super and sub (no bar, visual gap)
            all_y = list(short_labels) + [sep_label] + list(sub_names_15)
            all_x = list(mean_super) + [0] + list(mean_sub)
            all_colors = list(domain_colors) + ["rgba(0,0,0,0)"] + sub_colors
            all_text = [f"{v:.1f}" for v in mean_super] + [""] + [f"{v:.1f}" for v in mean_sub]
            cri_strs = (
                [f"{lo_super[i]:.1f}–{hi_super[i]:.1f}" for i in range(5)]
                + [""]
                + [f"{lo_sub[i]:.1f}–{hi_sub[i]:.1f}" for i in range(15)]
            ) if show_cri_bars else [""] * 21
            all_descriptions = [get_super_description(k) for k in range(5)] + [""] + [get_sub_description(j) for j in range(15)]
            bar_customdata = [[cri_strs[i], all_descriptions[i]] for i in range(21)]
            bar_kw = dict(
                y=all_y,
                x=all_x,
                orientation="h",
                marker_color=all_colors,
                text=all_text,
                textposition="outside",
                textfont=dict(size=10),
                hovertemplate="%{y}: %{x:.1f}" + (" (95%% CrI: %{customdata[0]})" if show_cri_bars else "") + "<br><br>%{customdata[1]}<extra></extra>",
                customdata=bar_customdata,
            )
            if show_cri_bars:
                bar_kw["error_x"] = dict(
                    type="data",
                    array=list(err_plus_super) + [0] + list(err_plus_sub),
                    arrayminus=list(err_minus_super) + [0] + list(err_minus_sub),
                    thickness=1.5,
                    color="rgba(0,0,0,0.5)",
                )
            fig_bars = go.Figure(go.Bar(**bar_kw))
            shapes = _bar_chart_zone_shapes() + [
                dict(type="line", x0=0, x1=105, xref="x", y0=5, y1=5, yref="y",
                     line=dict(color="rgba(0,0,0,0.35)", width=1.5)),
            ]
            for i in [8.5, 11.5, 14.5, 17.5]:
                shapes.append(dict(type="line", x0=0, x1=105, xref="x", y0=i, y1=i, yref="y",
                                    line=dict(color="rgba(0,0,0,0.18)", width=1, dash="dot")))
            fig_bars.update_layout(
                title="Super-dimensions and sub-dimensions (0–100)",
                xaxis=dict(title="Score (0–100)", range=[0, 112], dtick=25),
                yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
                height=580,
                margin=dict(t=64, b=44, l=20),
                template="plotly_white",
                showlegend=False,
                shapes=shapes,
                annotations=[
                    dict(x=20, y=1.02, xref="x", yref="paper", text="Needs attention", showarrow=False,
                         font=dict(size=10, color="rgba(160, 80, 80, 0.9)")),
                    dict(x=50, y=1.02, xref="x", yref="paper", text="Neutral", showarrow=False,
                         font=dict(size=10, color="rgba(140, 120, 50, 0.9)")),
                    dict(x=80, y=1.02, xref="x", yref="paper", text="Good", showarrow=False,
                         font=dict(size=10, color="rgba(60, 120, 60, 0.9)")),
                ],
            )
            st.plotly_chart(fig_bars, use_container_width=True)

        else:
            # Spider (radar): two charts — 5 super-dims (with icons) and 15 sub-dims; optional 95% CrI
            show_cri_spider = st.checkbox("Show 95% credibility intervals on spiders", value=False, key="show_cri_spider")
            n_super, n_sub = 5, 15
            angles_super = np.linspace(0, 360, n_super, endpoint=False)  # 0, 72, 144, 216, 288
            angles_sub = np.linspace(0, 360, n_sub, endpoint=False)     # 24° each

            def _wedge_traces(means, angles_deg, colors, descriptions=None):
                """One filled wedge per axis: (center, value, next center). Returns list of traces."""
                traces = []
                n = len(means)
                for k in range(n):
                    th0, th1 = angles_deg[k], angles_deg[(k + 1) % n]
                    r_wedge = [0, float(means[k]), 0]
                    theta_wedge = [th0, th0, th1]
                    color = colors[k % len(colors)]
                    desc = (descriptions[k] if descriptions and k < len(descriptions) else "") or ""
                    tr = go.Scatterpolar(
                        r=r_wedge,
                        theta=theta_wedge,
                        fill="toself",
                        fillcolor=color,
                        line=dict(color=color, width=1.5),
                        name=str(k),
                        showlegend=False,
                    )
                    if desc:
                        tr.update(customdata=[[desc, desc, desc]], hovertemplate="Score: %{r:.1f}<br><br>%{customdata[0]}<extra></extra>")
                    traces.append(tr)
                return traces

            col_spider_super, col_spider_sub = st.columns(2)
            # ---- Super-dimension spider (5 axes, colored wedges + icons) ----
            fig_super_spider = go.Figure()
            # Neutral reference (single gray polygon)
            r_neutral = [50] * (n_super + 1)
            theta_neutral = list(angles_super) + [angles_super[0]]
            fig_super_spider.add_trace(go.Scatterpolar(
                r=r_neutral,
                theta=theta_neutral,
                fill="toself",
                fillcolor="rgba(200, 200, 200, 0.12)",
                line=dict(color="rgba(120,120,120,0.5)", dash="dot", width=1),
                name="Neutral (50)",
            ))
            if show_cri_spider:
                r_lo = list(lo_super) + [lo_super[0]]
                r_hi = list(hi_super) + [hi_super[0]]
                fig_super_spider.add_trace(go.Scatterpolar(
                    r=r_lo,
                    theta=theta_neutral,
                    fill="none",
                    line=dict(color="rgba(0,0,0,0.2)", width=0.5),
                    name="95% CrI",
                    showlegend=False,
                ))
                fig_super_spider.add_trace(go.Scatterpolar(
                    r=r_hi,
                    theta=theta_neutral,
                    fill="tonext",
                    fillcolor="rgba(100, 140, 140, 0.2)",
                    line=dict(color="rgba(80, 120, 120, 0.4)", width=0.5),
                    name="95% CrI",
                ))
            super_descriptions = [get_super_description(k) for k in range(5)]
            for tr in _wedge_traces(mean_super, angles_super, domain_colors, super_descriptions):
                fig_super_spider.add_trace(tr)
            fig_super_spider.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
                    angularaxis=dict(
                        tickvals=list(angles_super + 360 / n_super / 2),
                        ticktext=short_labels,
                        tickfont=dict(size=11),
                    ),
                ),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=56, b=48, l=48, r=48),
                height=400,
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            # Place 5 dimension icons on a circle around the spider (paper coords)
            for k in range(5):
                icon_path = ICONS_DIR / f"{SUPERFACTOR_ICON_KEYS[k]}.png"
                if icon_path.exists():
                    with open(icon_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    source = f"data:image/png;base64,{b64}"
                    angle_rad = np.deg2rad(angles_super[k] + 360 / n_super / 2)
                    x = 0.5 + 0.42 * np.cos(angle_rad)
                    y = 0.5 + 0.42 * np.sin(angle_rad)
                    fig_super_spider.add_layout_image(dict(
                        source=source,
                        xref="paper", yref="paper",
                        x=x, y=y,
                        sizex=0.14, sizey=0.14,
                        xanchor="center", yanchor="middle",
                        layer="above",
                    ))
            with col_spider_super:
                st.caption("**5 super-dimensions** (icons at each axis)")
                st.plotly_chart(fig_super_spider, use_container_width=True)
            # ---- Sub-dimension spider (15 axes, color-grouped by super) ----
            sub_colors_spider = [domain_colors[i // 3] for i in range(15)]
            fig_sub_spider = go.Figure()
            r_neutral_sub = [50] * (n_sub + 1)
            theta_neutral_sub = list(angles_sub) + [angles_sub[0]]
            fig_sub_spider.add_trace(go.Scatterpolar(
                r=r_neutral_sub,
                theta=theta_neutral_sub,
                fill="toself",
                fillcolor="rgba(200, 200, 200, 0.08)",
                line=dict(color="rgba(120,120,120,0.4)", dash="dot", width=0.5),
                name="Neutral (50)",
            ))
            if show_cri_spider:
                r_lo_sub = list(lo_sub) + [lo_sub[0]]
                r_hi_sub = list(hi_sub) + [hi_sub[0]]
                fig_sub_spider.add_trace(go.Scatterpolar(
                    r=r_lo_sub,
                    theta=theta_neutral_sub,
                    fill="none",
                    line=dict(color="rgba(0,0,0,0.15)", width=0.5),
                    showlegend=False,
                ))
                fig_sub_spider.add_trace(go.Scatterpolar(
                    r=r_hi_sub,
                    theta=theta_neutral_sub,
                    fill="tonext",
                    fillcolor="rgba(100, 120, 120, 0.15)",
                    line=dict(color="rgba(80, 100, 100, 0.3)", width=0.5),
                    name="95% CrI",
                ))
            sub_descriptions = [get_sub_description(j) for j in range(15)]
            for tr in _wedge_traces(mean_sub, angles_sub, sub_colors_spider, sub_descriptions):
                fig_sub_spider.add_trace(tr)
            fig_sub_spider.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9)),
                    angularaxis=dict(
                        tickvals=list(angles_sub + 360 / n_sub / 2),
                        ticktext=sub_names_15,
                        tickfont=dict(size=9),
                    ),
                ),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=80, b=80, l=60, r=60),
                height=520,
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            with col_spider_sub:
                st.caption("**15 sub-dimensions** (grouped by super-dimension color)")
                st.plotly_chart(fig_sub_spider, use_container_width=True)

        # Division comparison (second-highest hierarchy) — how parts of the org compare
        # Use union of division.ids and division_to_depts so overview matches drill-down (all divisions)
        div_info = hi.get("division") or {}
        div_ids_from_division = div_info.get("ids") or []
        div_ids_from_map = list((hi.get("division_to_depts") or {}).keys())
        div_ids = list(dict.fromkeys(div_ids_from_division + [d for d in div_ids_from_map if d not in div_ids_from_division]))
        div_means = div_info.get("means") or {}
        div_sds = div_info.get("sds") or {}
        by_id = hi.get("by_id") or {}
        if div_ids and div_means:
            st.subheader("How divisions compare")
            st.caption("Each division’s profile on the 5 culture dimensions. Compare at a glance.")
            # Dimension options: 5 super + 15 sub (label, kind, index)
            cri_scale = 1.96
            tab_forest_div, tab_spider_div = st.tabs(["Forest plot", "Spider chart"])

            def _org_mean_sd(kind, idx):
                if kind == "super":
                    return float(mean_super[idx]), float(sd_super[idx])
                return float(mean_sub[idx]), float(sd_sub[idx])

            def _div_mean_sd(div_id, kind, idx):
                m = np.asarray(div_means.get(div_id, np.zeros(15)))
                s = np.asarray(div_sds.get(div_id, np.full(15, 10)))
                if kind == "super":
                    ms, ss = sub_to_super_means_sds(m, s)
                    return float(ms[idx]), float(ss[idx])
                return float(m[idx]), float(s[idx])

            div_names = [(by_id.get(d) or {}).get("name", d) for d in div_ids]
            row_labels = ["Organization"] + div_names
            n_rows = len(row_labels)

            with tab_forest_div:
                dim_options = [(f"{short_labels[k]} (super)", "super", k) for k in range(5)]
                dim_options += [(sub_names_15[j], "sub", j) for j in range(15)]
                dim_labels = [d[0] for d in dim_options]
                view_dims = st.radio("Show", ["Single dimension", "Multiple dimensions (grouped)"], horizontal=True, key="div_forest_mode")
                if view_dims.startswith("Single"):
                    selected = st.selectbox("Dimension", range(len(dim_labels)), format_func=lambda i: dim_labels[i], key="div_forest_single")
                    selected_dims = [dim_options[selected]]
                else:
                    selected_multi = st.multiselect("Dimensions to include", options=range(len(dim_labels)), format_func=lambda i: dim_labels[i], default=[0], key="div_forest_multi")
                    selected_dims = [dim_options[i] for i in selected_multi] if selected_multi else [dim_options[0]]
                y_numeric = list(range(n_rows))
                if len(selected_dims) == 1:
                    label, kind, idx = selected_dims[0]
                    org_m, org_s = _org_mean_sd(kind, idx)
                    org_lo = np.clip(org_m - cri_scale * org_s, 0, 100)
                    org_hi = np.clip(org_m + cri_scale * org_s, 0, 100)
                    means = [org_m] + [_div_mean_sd(d, kind, idx)[0] for d in div_ids]
                    los = [org_lo] + [np.clip(_div_mean_sd(d, kind, idx)[0] - cri_scale * _div_mean_sd(d, kind, idx)[1], 0, 100) for d in div_ids]
                    his = [org_hi] + [np.clip(_div_mean_sd(d, kind, idx)[0] + cri_scale * _div_mean_sd(d, kind, idx)[1], 0, 100) for d in div_ids]
                    err_plus = [his[i] - means[i] for i in range(n_rows)]
                    err_minus = [means[i] - los[i] for i in range(n_rows)]
                    fig_forest = go.Figure(go.Scatter(
                        x=means,
                        y=y_numeric,
                        mode="markers",
                        marker=dict(size=10, color="steelblue", symbol="diamond"),
                        error_x=dict(type="data", array=err_plus, arrayminus=err_minus, thickness=1.5, color="steelblue"),
                        name=label,
                        hovertemplate="%{text}: %{x:.1f} (95%% CrI)<extra></extra>",
                        text=row_labels,
                    ))
                    fig_forest.add_vline(x=org_m, line_dash="dot", line_color="gray", line_width=1.5, annotation_text="Org mean")
                    fig_forest.update_layout(
                        title=f"Forest plot — {label}",
                        xaxis=dict(title="Score (0–100)", range=[0, 105]),
                        yaxis=dict(
                            tickmode="array",
                            tickvals=y_numeric,
                            ticktext=row_labels,
                            autorange="reversed",
                            tickfont=dict(size=11),
                        ),
                        height=max(420, 72 * n_rows),
                        margin=dict(l=220),
                        template="plotly_white",
                        showlegend=False,
                    )
                    st.plotly_chart(fig_forest, use_container_width=True)
                else:
                    # Grouped: points within each row (Org/division) close together; clear gap before next row
                    n_dims = len(selected_dims)
                    group_band = 0.28   # y-span for dimension points within one group (tight)
                    gap = 0.72          # gap before next group so "these belong together, these don't"
                    y_per_row = group_band + gap  # 1.0
                    ref_label, ref_kind, ref_idx = selected_dims[0]
                    org_ref_m, _ = _org_mean_sd(ref_kind, ref_idx)
                    fig_forest = go.Figure()
                    for i, (label, kind, idx) in enumerate(selected_dims):
                        org_m, org_s = _org_mean_sd(kind, idx)
                        org_lo = np.clip(org_m - cri_scale * org_s, 0, 100)
                        org_hi = np.clip(org_m + cri_scale * org_s, 0, 100)
                        means = [org_m] + [_div_mean_sd(d, kind, idx)[0] for d in div_ids]
                        los = [org_lo] + [np.clip(_div_mean_sd(d, kind, idx)[0] - cri_scale * _div_mean_sd(d, kind, idx)[1], 0, 100) for d in div_ids]
                        his = [org_hi] + [np.clip(_div_mean_sd(d, kind, idx)[0] + cri_scale * _div_mean_sd(d, kind, idx)[1], 0, 100) for d in div_ids]
                        err_plus = [his[j] - means[j] for j in range(n_rows)]
                        err_minus = [means[j] - los[j] for j in range(n_rows)]
                        color = domain_colors[idx // 3] if kind == "sub" else domain_colors[idx]
                        div_step = (group_band / max(n_dims - 1, 1)) * i
                        y_grouped = [r * y_per_row + div_step for r in range(n_rows)]
                        fig_forest.add_trace(go.Scatter(
                            x=means,
                            y=y_grouped,
                            mode="markers",
                            marker=dict(size=8, color=color, symbol="circle"),
                            error_x=dict(type="data", array=err_plus, arrayminus=err_minus, thickness=1.2, color=color),
                            name=label,
                            hovertemplate="%{text}: %{x:.1f} — " + label + "<extra></extra>",
                            text=row_labels,
                        ))
                    tickvals_grouped = [r * y_per_row + group_band / 2 for r in range(n_rows)]
                    fig_forest.add_vline(x=org_ref_m, line_dash="dot", line_color="gray", line_width=1.5, annotation_text="Org mean")
                    fig_forest.update_layout(
                        title="Forest plot — grouped by dimension",
                        xaxis=dict(title="Score (0–100)", range=[0, 105]),
                        yaxis=dict(
                            tickmode="array",
                            tickvals=tickvals_grouped,
                            ticktext=row_labels,
                            autorange="reversed",
                            tickfont=dict(size=11),
                        ),
                        height=max(420, 72 * n_rows),
                        margin=dict(l=220),
                        template="plotly_white",
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig_forest, use_container_width=True)
                st.caption("Organization at top; dotted line = organization mean. 95% credibility intervals shown.")

            with tab_spider_div:
                spider_view = st.radio("Show", ["Super dimensions (5)", "Subdimensions (15)"], horizontal=True, key="div_spider_view")
                theta_super = short_labels + [short_labels[0]]
                theta_sub = list(sub_names_15) + [sub_names_15[0]]
                if spider_view.startswith("Super"):
                    r_org = [float(mean_super[k]) for k in range(5)] + [float(mean_super[0])]
                    fig_spider = go.Figure(go.Scatterpolar(
                        r=r_org,
                        theta=theta_super,
                        line=dict(color="#2d7d7d", width=2),
                        name="Organization",
                    ))
                    for d in div_ids:
                        r_div = [_div_mean_sd(d, "super", k)[0] for k in range(5)] + [_div_mean_sd(d, "super", 0)[0]]
                        fig_spider.add_trace(go.Scatterpolar(
                            r=r_div,
                            theta=theta_super,
                            line=dict(width=1.5),
                            name=row_labels[div_ids.index(d) + 1],
                        ))
                    fig_spider.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)), angularaxis=dict(tickfont=dict(size=11))),
                        title="Divisions vs Organization — 5 super-dimensions",
                        height=480,
                        margin=dict(t=48, b=24),
                        template="plotly_white",
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig_spider, use_container_width=True)
                else:
                    r_org_sub = [float(mean_sub[j]) for j in range(15)] + [float(mean_sub[0])]
                    fig_spider_sub = go.Figure(go.Scatterpolar(
                        r=r_org_sub,
                        theta=theta_sub,
                        line=dict(color="#2d7d7d", width=2),
                        name="Organization",
                    ))
                    for d in div_ids:
                        r_div_sub = [_div_mean_sd(d, "sub", j)[0] for j in range(15)] + [_div_mean_sd(d, "sub", 0)[0]]
                        fig_spider_sub.add_trace(go.Scatterpolar(
                            r=r_div_sub,
                            theta=theta_sub,
                            line=dict(width=1.2),
                            name=row_labels[div_ids.index(d) + 1],
                        ))
                    fig_spider_sub.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9)), angularaxis=dict(tickfont=dict(size=9))),
                        title="Divisions vs Organization — 15 subdimensions",
                        height=520,
                        margin=dict(t=48, b=24),
                        template="plotly_white",
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig_spider_sub, use_container_width=True)
                st.caption("Spider charts compare each division to the organization on all dimensions at once.")

        # -------------------------------------------------------------------------
        # Drill down (same hierarchy as Statistical tab: Org → Division → Dept → Team)
        # -------------------------------------------------------------------------
        st.header("Drill down")
        by_id_drill = hi.get("by_id") or {}
        div_info_drill = hi.get("division") or {}
        div_ids_from_div = div_info_drill.get("ids") or []
        division_to_depts_drill = hi.get("division_to_depts") or {}
        div_ids_drill = list(dict.fromkeys(div_ids_from_div + [d for d in division_to_depts_drill if d not in div_ids_from_div]))
        dept_to_teams_drill = hi.get("department", {}).get("dept_to_teams") or {}

        def _name_drill(nid):
            return (by_id_drill.get(nid) or {}).get("name", nid)

        # Apply Sunburst click from previous run (before any widget using these keys is created)
        _pending = st.session_state.pop("_sunburst_pending_id", None)
        _applied_sunburst_pending = _pending is not None
        sunburst_ids, sunburst_parents, _all_ids = _cached_drill_hierarchy(
            tuple(div_ids_drill),
            tuple((d, tuple(division_to_depts_drill.get(d) or [])) for d in div_ids_drill),
            tuple((k, tuple(v)) for k, v in dept_to_teams_drill.items()),
        )
        sunburst_labels = ["Organization"] + [_name_drill(i) for i in sunburst_ids[1:]]
        if _pending is not None and _pending in _all_ids:
            if _pending == "org":
                st.session_state["overview_drill_level"] = "Organization"
                # Clear selector indices so no stale division/dept/team selection
                for key in ("overview_sel_division", "overview_sel_div_dept", "overview_sel_dept",
                            "overview_sel_div_team", "overview_sel_dept_team", "overview_sel_team"):
                    st.session_state.pop(key, None)
            elif _pending in div_ids_drill:
                st.session_state["overview_drill_level"] = "Division"
                st.session_state["overview_sel_division"] = div_ids_drill.index(_pending)
            else:
                dept_id_to_div = {}
                for _d in div_ids_drill:
                    for dept in (division_to_depts_drill.get(_d) or []):
                        dept_id_to_div[dept] = _d
                if _pending in dept_id_to_div:
                    _div_sel = dept_id_to_div[_pending]
                    _dept_list = division_to_depts_drill.get(_div_sel) or []
                    st.session_state["overview_drill_level"] = "Department"
                    st.session_state["overview_sel_div_dept"] = div_ids_drill.index(_div_sel)
                    st.session_state["overview_sel_dept"] = _dept_list.index(_pending)
                else:
                    for _div in div_ids_drill:
                        for dept in (division_to_depts_drill.get(_div) or []):
                            if _pending in (dept_to_teams_drill.get(dept) or []):
                                _dept_list_t = division_to_depts_drill.get(_div) or []
                                _team_list_t = dept_to_teams_drill.get(dept) or []
                                st.session_state["overview_drill_level"] = "Team"
                                st.session_state["overview_sel_div_team"] = div_ids_drill.index(_div)
                                st.session_state["overview_sel_dept_team"] = _dept_list_t.index(dept)
                                st.session_state["overview_sel_team"] = _team_list_t.index(_pending)
                                break
                        else:
                            continue
                        break

        st.caption("Choose a unit with the **selector** below or by **clicking a slice in the Sunburst**. When you change the selector, the Sunburst jumps to that level.")
        level_ov = st.radio(
            "Level",
            ["Organization", "Division", "Department", "Team"],
            horizontal=True,
            key="overview_drill_level",
        )
        sel_div_ov = None
        sel_dept_ov = None
        sel_team_ov = None
        if level_ov != "Organization" and not div_ids_drill:
            st.info("No divisions in hierarchy.")
        elif level_ov == "Division" and div_ids_drill:
            sel_idx = st.selectbox("Division", range(len(div_ids_drill)), format_func=lambda i: _name_drill(div_ids_drill[i]), key="overview_sel_division")
            sel_div_ov = div_ids_drill[sel_idx]
        elif level_ov == "Department" and div_ids_drill:
            sel_idx = st.selectbox("Division", range(len(div_ids_drill)), format_func=lambda i: _name_drill(div_ids_drill[i]), key="overview_sel_div_dept")
            sel_div_ov = div_ids_drill[sel_idx]
            dept_ids_ov = division_to_depts_drill.get(sel_div_ov) or []
            if dept_ids_ov:
                sel_d = st.selectbox("Department", range(len(dept_ids_ov)), format_func=lambda i: _name_drill(dept_ids_ov[i]), key="overview_sel_dept")
                sel_dept_ov = dept_ids_ov[sel_d]
            else:
                st.info("No departments in this division.")
        elif level_ov == "Team" and div_ids_drill:
            sel_idx = st.selectbox("Division", range(len(div_ids_drill)), format_func=lambda i: _name_drill(div_ids_drill[i]), key="overview_sel_div_team")
            sel_div_ov = div_ids_drill[sel_idx]
            dept_ids_ov = division_to_depts_drill.get(sel_div_ov) or []
            if dept_ids_ov:
                sel_d = st.selectbox("Department", range(len(dept_ids_ov)), format_func=lambda i: _name_drill(dept_ids_ov[i]), key="overview_sel_dept_team")
                sel_dept_ov = dept_ids_ov[sel_d]
                team_ids_ov = dept_to_teams_drill.get(sel_dept_ov) or []
                if team_ids_ov:
                    sel_t = st.selectbox("Team", range(len(team_ids_ov)), format_func=lambda i: _name_drill(team_ids_ov[i]), key="overview_sel_team")
                    sel_team_ov = team_ids_ov[sel_t]
                else:
                    st.info("No teams in this department.")
            else:
                st.info("No departments in this division.")

        # Current unit id for Sunburst level (so the chart zooms to the selector's choice)
        sunburst_level_id = ""
        if level_ov == "Division" and sel_div_ov:
            sunburst_level_id = sel_div_ov
        elif level_ov == "Department" and sel_dept_ov:
            sunburst_level_id = sel_dept_ov
        elif level_ov == "Team" and sel_team_ov:
            sunburst_level_id = sel_team_ov

        # Org structure: Sunburst (ids/labels/parents and _all_ids from cache above)
        if sunburst_ids:
            fig_sunburst_json = _cached_sunburst_fig_json(
                sunburst_level_id,
                tuple(sunburst_ids),
                tuple(sunburst_labels),
                tuple(sunburst_parents),
            )
            clicked_id = sunburst_select(plot_json=fig_sunburst_json, key="org_sunburst_select", height=380)
            # Store click and rerun so next run applies it before widgets are created.
            # Ignore repeated stale click payloads from component reruns.
            if clicked_id is None:
                st.session_state.pop("_sunburst_last_clicked_id", None)
            elif clicked_id in sunburst_ids and not _applied_sunburst_pending:
                last_clicked = st.session_state.get("_sunburst_last_clicked_id")
                if clicked_id != last_clicked:
                    st.session_state["_sunburst_last_clicked_id"] = clicked_id
                    # Click on center (current root) = go back one level
                    if clicked_id == sunburst_level_id:
                        idx_cur = sunburst_ids.index(sunburst_level_id)
                        parent_id = sunburst_parents[idx_cur] if idx_cur < len(sunburst_parents) else ""
                        if parent_id:  # not at top
                            st.session_state["_sunburst_pending_id"] = parent_id
                            st.rerun()
                    else:
                        st.session_state["_sunburst_pending_id"] = clicked_id
                        st.rerun()

        # Show which unit the dashboard is scoped to (scores and charts below are for this unit)
        if level_ov == "Organization":
            viewing_name = "Organization"
        elif level_ov == "Division" and sel_div_ov:
            viewing_name = _name_drill(sel_div_ov)
        elif level_ov == "Department" and sel_dept_ov:
            viewing_name = _name_drill(sel_dept_ov)
        elif level_ov == "Team" and sel_team_ov:
            viewing_name = _name_drill(sel_team_ov)
        else:
            viewing_name = None
        if viewing_name:
            st.caption(f"**Viewing:** {viewing_name} — scores and comparisons below are for this unit.")

        def get_current_mean_sd_ov():
            org = hi.get("org") or {}
            if level_ov == "Organization":
                m, s = org.get("mean_sub"), org.get("sd_sub")
                return (m, s) if m is not None and s is not None else (None, None)
            if level_ov == "Division" and sel_div_ov:
                div = hi.get("division") or {}
                m = div.get("means", {}).get(sel_div_ov)
                s = div.get("sds", {}).get(sel_div_ov)
                return (m, s) if m is not None and s is not None else (None, None)
            if level_ov == "Department" and sel_dept_ov:
                dept = hi.get("department") or {}
                m = dept.get("means", {}).get(sel_dept_ov)
                s = dept.get("sds", {}).get(sel_dept_ov)
                return (m, s) if m is not None and s is not None else (None, None)
            if level_ov == "Team" and sel_team_ov:
                team = hi.get("team") or {}
                m = team.get("means", {}).get(sel_team_ov)
                s = team.get("sds", {}).get(sel_team_ov)
                return (m, s) if m is not None and s is not None else (None, None)
            return (None, None)

        def get_children_ov():
            if level_ov == "Organization":
                div = hi.get("division") or {}
                means, sds = div.get("means"), div.get("sds")
                return [(cid, means.get(cid), sds.get(cid)) for cid in div_ids_drill if means and sds and cid in means]
            if level_ov == "Division" and sel_div_ov:
                dept_ids_c = division_to_depts_drill.get(sel_div_ov) or []
                dept = hi.get("department") or {}
                means, sds = dept.get("means"), dept.get("sds")
                return [(cid, means.get(cid), sds.get(cid)) for cid in dept_ids_c if means and sds and cid in means]
            if level_ov == "Department" and sel_dept_ov:
                team_ids_c = dept_to_teams_drill.get(sel_dept_ov) or []
                team = hi.get("team") or {}
                means, sds = team.get("means"), team.get("sds")
                return [(cid, means.get(cid), sds.get(cid)) for cid in team_ids_c if means and sds and cid in means]
            if level_ov == "Team" and sel_team_ov:
                rs = st.session_state.respondent_scores
                if rs and rs.get("team_id") and rs.get("theta_sub"):
                    team_ids_rs = rs["team_id"]
                    theta_sub = rs["theta_sub"]
                    idx_team = [i for i, tid in enumerate(team_ids_rs) if str(tid) == str(sel_team_ov)]
                    emp_ids = rs.get("employee_id") or rs.get("respondent_id")
                    out = []
                    for i in idx_team:
                        label = emp_ids[i] if i < len(emp_ids) else str(rs["respondent_id"][i])
                        m15 = theta_sub[i] if i < len(theta_sub) else None
                        if m15 is not None:
                            out.append((label, list(m15), [0.0] * 15))
                    return out
            return []

        cur_m_ov, cur_s_ov = get_current_mean_sd_ov()
        children_ov = get_children_ov()
        cri_scale_ov = 1.96

        # Scores at a glance for current drill-down context (same logic as overview)
        if cur_m_ov is not None and cur_s_ov is not None:
            mean_sub_d = np.asarray(cur_m_ov)
            sd_sub_d = np.asarray(cur_s_ov)
            mean_super_d, sd_super_d = sub_to_super_means_sds(mean_sub_d, sd_sub_d)
            mean_super_d = np.clip(mean_super_d, 0, 100)
            mean_sub_d = np.clip(mean_sub_d, 0, 100)
            lo_super_d = np.clip(mean_super_d - cri_scale_ov * sd_super_d, 0, 100)
            hi_super_d = np.clip(mean_super_d + cri_scale_ov * sd_super_d, 0, 100)
            err_plus_super_d = hi_super_d - mean_super_d
            err_minus_super_d = mean_super_d - lo_super_d
            lo_sub_d = np.clip(mean_sub_d - cri_scale_ov * sd_sub_d, 0, 100)
            hi_sub_d = np.clip(mean_sub_d + cri_scale_ov * sd_sub_d, 0, 100)
            err_plus_sub_d = hi_sub_d - mean_sub_d
            err_minus_sub_d = mean_sub_d - lo_sub_d

            st.subheader(f"Scores at a glance — {viewing_name}")
            view_scores_d = st.radio("Show as", ["Bar charts", "Spider"], horizontal=True, key="overview_drill_scores_as")
            if view_scores_d == "Bar charts":
                if "overview_drill_show_cri_bars" not in st.session_state:
                    st.session_state["overview_drill_show_cri_bars"] = True
                show_cri_bars_d = st.checkbox("Show 95% credibility intervals in bar charts", key="overview_drill_show_cri_bars")
                sub_colors_d = [domain_colors[i // 3] for i in range(15)]
                sep_label_d = " "
                all_y_d = list(short_labels) + [sep_label_d] + list(sub_names_15)
                all_x_d = [float(x) for x in (list(mean_super_d) + [0] + list(mean_sub_d))]
                all_colors_d = list(domain_colors) + ["rgba(0,0,0,0)"] + sub_colors_d
                all_text_d = [f"{v:.1f}" for v in mean_super_d] + [""] + [f"{v:.1f}" for v in mean_sub_d]
                cri_strs_d = (
                    [f"{lo_super_d[i]:.1f}–{hi_super_d[i]:.1f}" for i in range(5)]
                    + [""] + [f"{lo_sub_d[i]:.1f}–{hi_sub_d[i]:.1f}" for i in range(15)]
                ) if show_cri_bars_d else [""] * 21
                all_descriptions_d = [get_super_description(k) for k in range(5)] + [""] + [get_sub_description(j) for j in range(15)]
                bar_customdata_d = [[cri_strs_d[i], all_descriptions_d[i]] for i in range(21)]
                bar_kw_d = dict(
                    y=all_y_d,
                    x=all_x_d,
                    orientation="h",
                    marker_color=all_colors_d,
                    text=all_text_d,
                    textposition="outside",
                    textfont=dict(size=10),
                    hovertemplate="%{y}: %{x:.1f}" + (" (95%% CrI: %{customdata[0]})" if show_cri_bars_d else "") + "<br><br>%{customdata[1]}<extra></extra>",
                    customdata=bar_customdata_d,
                )
                if show_cri_bars_d:
                    err_plus = [float(x) for x in list(err_plus_super_d) + [0] + list(err_plus_sub_d)]
                    err_minus = [float(x) for x in list(err_minus_super_d) + [0] + list(err_minus_sub_d)]
                    bar_kw_d["error_x"] = dict(
                        type="data",
                        array=err_plus,
                        arrayminus=err_minus,
                        thickness=1.5,
                        color="rgba(0,0,0,0.5)",
                    )
                fig_bars_d = go.Figure(go.Bar(**bar_kw_d))
                shapes_d = _bar_chart_zone_shapes() + [
                    dict(type="line", x0=0, x1=105, xref="x", y0=5, y1=5, yref="y", line=dict(color="rgba(0,0,0,0.35)", width=1.5)),
                ]
                for i in [8.5, 11.5, 14.5, 17.5]:
                    shapes_d.append(dict(type="line", x0=0, x1=105, xref="x", y0=i, y1=i, yref="y", line=dict(color="rgba(0,0,0,0.18)", width=1, dash="dot")))
                fig_bars_d.update_layout(
                    title="Current context — super and sub-dimensions (0–100)",
                    xaxis=dict(title="Score (0–100)", range=[0, 112], dtick=25),
                    yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
                    height=580,
                    margin=dict(t=64, b=44, l=20),
                    template="plotly_white",
                    showlegend=False,
                    shapes=shapes_d,
                    annotations=[
                        dict(x=20, y=1.02, xref="x", yref="paper", text="Needs attention", showarrow=False,
                             font=dict(size=10, color="rgba(160, 80, 80, 0.9)")),
                        dict(x=50, y=1.02, xref="x", yref="paper", text="Neutral", showarrow=False,
                             font=dict(size=10, color="rgba(140, 120, 50, 0.9)")),
                        dict(x=80, y=1.02, xref="x", yref="paper", text="Good", showarrow=False,
                             font=dict(size=10, color="rgba(60, 120, 60, 0.9)")),
                    ],
                )
                st.plotly_chart(fig_bars_d, use_container_width=True)
            else:
                show_cri_spider_d = st.checkbox("Show 95% credibility intervals on spiders", value=False, key="overview_drill_show_cri_spider")
                n_super_d, n_sub_d = 5, 15
                angles_super_d = np.linspace(0, 360, n_super_d, endpoint=False)
                angles_sub_d = np.linspace(0, 360, n_sub_d, endpoint=False)

                def _wedge_traces_d(means, angles_deg, colors, descriptions=None):
                    traces = []
                    n = len(means)
                    for k in range(n):
                        th0, th1 = angles_deg[k], angles_deg[(k + 1) % n]
                        r_wedge = [0, float(means[k]), 0]
                        theta_wedge = [th0, th0, th1]
                        color = colors[k % len(colors)]
                        desc = (descriptions[k] if descriptions and k < len(descriptions) else "") or ""
                        tr = go.Scatterpolar(
                            r=r_wedge, theta=theta_wedge, fill="toself", fillcolor=color,
                            line=dict(color=color, width=1.5), name=str(k), showlegend=False,
                        )
                        if desc:
                            tr.update(customdata=[[desc, desc, desc]], hovertemplate="Score: %{r:.1f}<br><br>%{customdata[0]}<extra></extra>")
                        traces.append(tr)
                    return traces

                col_spider_super_d, col_spider_sub_d = st.columns(2)
                fig_super_spider_d = go.Figure()
                r_neutral_d = [50] * (n_super_d + 1)
                theta_neutral_d = list(angles_super_d) + [angles_super_d[0]]
                fig_super_spider_d.add_trace(go.Scatterpolar(
                    r=r_neutral_d, theta=theta_neutral_d, fill="toself",
                    fillcolor="rgba(200, 200, 200, 0.12)",
                    line=dict(color="rgba(120,120,120,0.5)", dash="dot", width=1), name="Neutral (50)",
                ))
                if show_cri_spider_d:
                    r_lo_d = list(lo_super_d) + [lo_super_d[0]]
                    r_hi_d = list(hi_super_d) + [hi_super_d[0]]
                    fig_super_spider_d.add_trace(go.Scatterpolar(r=r_lo_d, theta=theta_neutral_d, fill="none", line=dict(color="rgba(0,0,0,0.2)", width=0.5), showlegend=False))
                    fig_super_spider_d.add_trace(go.Scatterpolar(r=r_hi_d, theta=theta_neutral_d, fill="tonext", fillcolor="rgba(100, 140, 140, 0.2)", line=dict(color="rgba(80, 120, 120, 0.4)", width=0.5), name="95% CrI"))
                super_descriptions_d = [get_super_description(k) for k in range(5)]
                for tr in _wedge_traces_d(mean_super_d, angles_super_d, domain_colors, super_descriptions_d):
                    fig_super_spider_d.add_trace(tr)
                fig_super_spider_d.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
                        angularaxis=dict(tickvals=list(angles_super_d + 360 / n_super_d / 2), ticktext=short_labels, tickfont=dict(size=11)),
                    ),
                    showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(t=56, b=48, l=48, r=48), height=400, template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                for k in range(5):
                    icon_path = ICONS_DIR / f"{SUPERFACTOR_ICON_KEYS[k]}.png"
                    if icon_path.exists():
                        with open(icon_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        source = f"data:image/png;base64,{b64}"
                        angle_rad = np.deg2rad(angles_super_d[k] + 360 / n_super_d / 2)
                        x, y = 0.5 + 0.42 * np.cos(angle_rad), 0.5 + 0.42 * np.sin(angle_rad)
                        fig_super_spider_d.add_layout_image(dict(source=source, xref="paper", yref="paper", x=x, y=y, sizex=0.14, sizey=0.14, xanchor="center", yanchor="middle", layer="above"))
                with col_spider_super_d:
                    st.caption("**5 super-dimensions**")
                    st.plotly_chart(fig_super_spider_d, use_container_width=True)
                sub_colors_spider_d = [domain_colors[i // 3] for i in range(15)]
                fig_sub_spider_d = go.Figure()
                r_neutral_sub_d = [50] * (n_sub_d + 1)
                theta_neutral_sub_d = list(angles_sub_d) + [angles_sub_d[0]]
                fig_sub_spider_d.add_trace(go.Scatterpolar(
                    r=r_neutral_sub_d, theta=theta_neutral_sub_d, fill="toself",
                    fillcolor="rgba(200, 200, 200, 0.08)",
                    line=dict(color="rgba(120,120,120,0.4)", dash="dot", width=0.5), name="Neutral (50)",
                ))
                if show_cri_spider_d:
                    r_lo_sub_d = list(lo_sub_d) + [lo_sub_d[0]]
                    r_hi_sub_d = list(hi_sub_d) + [hi_sub_d[0]]
                    fig_sub_spider_d.add_trace(go.Scatterpolar(r=r_lo_sub_d, theta=theta_neutral_sub_d, fill="none", line=dict(color="rgba(0,0,0,0.15)", width=0.5), showlegend=False))
                    fig_sub_spider_d.add_trace(go.Scatterpolar(r=r_hi_sub_d, theta=theta_neutral_sub_d, fill="tonext", fillcolor="rgba(100, 120, 120, 0.15)", line=dict(color="rgba(80, 100, 100, 0.3)", width=0.5), name="95% CrI"))
                sub_descriptions_d = [get_sub_description(j) for j in range(15)]
                for tr in _wedge_traces_d(mean_sub_d, angles_sub_d, sub_colors_spider_d, sub_descriptions_d):
                    fig_sub_spider_d.add_trace(tr)
                fig_sub_spider_d.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9)),
                        angularaxis=dict(tickvals=list(angles_sub_d + 360 / n_sub_d / 2), ticktext=sub_names_15, tickfont=dict(size=9)),
                    ),
                    showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(t=80, b=80, l=60, r=60), height=520, template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                with col_spider_sub_d:
                    st.caption("**15 sub-dimensions**")
                    st.plotly_chart(fig_sub_spider_d, use_container_width=True)

        # Forest plots: same dimension setup as "How divisions compare"
        st.subheader("Forest plot — compare children")
        # Same dimension setup as "How divisions compare": single vs grouped, pick dimension(s)
        dim_options_ov = [(f"{short_labels[k]} (super)", "super", k) for k in range(5)]
        dim_options_ov += [(sub_names_15[j], "sub", j) for j in range(15)]
        dim_labels_ov = [d[0] for d in dim_options_ov]
        view_dims_ov = st.radio("Show", ["Single dimension", "Multiple dimensions (grouped)"], horizontal=True, key="overview_drill_dim_mode")
        if view_dims_ov.startswith("Single"):
            sel_dim_ov = st.selectbox("Dimension", range(len(dim_labels_ov)), format_func=lambda i: dim_labels_ov[i], key="overview_drill_single_dim")
            selected_dims_ov = [dim_options_ov[sel_dim_ov]]
        else:
            sel_multi_ov = st.multiselect("Dimensions to include", options=range(len(dim_labels_ov)), format_func=lambda i: dim_labels_ov[i], default=[0], key="overview_drill_multi_dim")
            selected_dims_ov = [dim_options_ov[i] for i in sel_multi_ov] if sel_multi_ov else [dim_options_ov[0]]

        def _ref_mean_sd_ov(kind, idx):
            if cur_m_ov is None or cur_s_ov is None:
                return None, None
            m, s = np.asarray(cur_m_ov), np.asarray(cur_s_ov)
            if kind == "super":
                ms, ss = sub_to_super_means_sds(m, s)
                return float(ms[idx]), float(ss[idx])
            return float(m[idx]), float(s[idx])

        def _child_mean_sd_ov(m15, s15, kind, idx):
            if m15 is None or s15 is None:
                return 50.0, 10.0
            m, s = np.asarray(m15), np.asarray(s15)
            if kind == "super":
                ms, ss = sub_to_super_means_sds(m, s)
                return float(ms[idx]), float(ss[idx])
            return float(m[idx]), float(s[idx])

        children_ov_valid = [(cid, m15, s15) for cid, m15, s15 in children_ov if m15 is not None and s15 is not None]
        child_names_ov = [_name_drill(cid) for cid, _, _ in children_ov_valid]
        n_c = len(child_names_ov)
        y_numeric_c = list(range(n_c)) if n_c else []
        ref_available = selected_dims_ov and _ref_mean_sd_ov(selected_dims_ov[0][1], selected_dims_ov[0][2])[0] is not None

        if n_c > 0 or ref_available:
            if len(selected_dims_ov) == 1:
                label_ov, kind_ov, idx_ov = selected_dims_ov[0]
                ref_m, ref_s = _ref_mean_sd_ov(kind_ov, idx_ov)
                means_c = [_child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[0] for _, m15, s15 in children_ov_valid]
                los_c = [np.clip(_child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[0] - cri_scale_ov * _child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[1], 0, 100) for _, m15, s15 in children_ov_valid]
                his_c = [np.clip(_child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[0] + cri_scale_ov * _child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[1], 0, 100) for _, m15, s15 in children_ov_valid]
                err_plus_c = [his_c[i] - means_c[i] for i in range(n_c)]
                err_minus_c = [means_c[i] - los_c[i] for i in range(n_c)]
                show_cri = n_c > 0 and (max(err_plus_c) > 0 or max(err_minus_c) > 0)
                st.subheader("Forest plot — " + label_ov)
                scatter_kw = dict(
                    x=means_c,
                    y=y_numeric_c,
                    mode="markers",
                    marker=dict(size=10, color="steelblue", symbol="diamond"),
                    text=child_names_ov,
                    hovertemplate="%{text}: %{x:.1f}" + (" (95%% CrI)" if show_cri else "") + "<extra></extra>",
                )
                if show_cri:
                    scatter_kw["error_x"] = dict(type="data", array=err_plus_c, arrayminus=err_minus_c, thickness=1.5, color="steelblue")
                fig_drill = go.Figure(go.Scatter(**scatter_kw))
                if ref_m is not None:
                    fig_drill.add_vline(x=ref_m, line_dash="dot", line_color="gray", line_width=1.5, annotation_text="Current level mean")
                fig_drill.update_layout(
                    title=f"Forest plot — {label_ov}",
                    xaxis=dict(title="Score (0–100)", range=[0, 105]),
                    yaxis=dict(tickmode="array", tickvals=y_numeric_c, ticktext=child_names_ov, autorange="reversed", tickfont=dict(size=11)),
                    height=max(420, 72 * max(n_c, 1)),
                    margin=dict(l=220),
                    template="plotly_white",
                    showlegend=False,
                )
                st.plotly_chart(fig_drill, use_container_width=True)
            else:
                # Grouped: same band + gap as overview
                n_dims_ov = len(selected_dims_ov)
                group_band_ov = 0.28
                gap_ov = 0.72
                y_per_row_ov = group_band_ov + gap_ov
                ref_label_ov, ref_kind_ov, ref_idx_ov = selected_dims_ov[0]
                ref_m_gr, _ = _ref_mean_sd_ov(ref_kind_ov, ref_idx_ov)
                st.subheader("Forest plot — grouped by dimension")
                fig_drill = go.Figure()
                for i, (label_ov, kind_ov, idx_ov) in enumerate(selected_dims_ov):
                    means_c = [_child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[0] for _, m15, s15 in children_ov_valid]
                    los_c = [np.clip(_child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[0] - cri_scale_ov * _child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[1], 0, 100) for _, m15, s15 in children_ov_valid]
                    his_c = [np.clip(_child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[0] + cri_scale_ov * _child_mean_sd_ov(m15, s15, kind_ov, idx_ov)[1], 0, 100) for _, m15, s15 in children_ov_valid]
                    err_plus_c = [his_c[j] - means_c[j] for j in range(n_c)]
                    err_minus_c = [means_c[j] - los_c[j] for j in range(n_c)]
                    show_cri_gr = n_c > 0 and (max(err_plus_c) > 0 or max(err_minus_c) > 0)
                    color_ov = domain_colors[idx_ov // 3] if kind_ov == "sub" else domain_colors[idx_ov]
                    div_step_ov = (group_band_ov / max(n_dims_ov - 1, 1)) * i
                    y_grouped_c = [r * y_per_row_ov + div_step_ov for r in range(n_c)]
                    trace_kw = dict(
                        x=means_c,
                        y=y_grouped_c,
                        mode="markers",
                        marker=dict(size=8, color=color_ov, symbol="circle"),
                        name=label_ov,
                        hovertemplate="%{text}: %{x:.1f} — " + label_ov + "<extra></extra>",
                        text=child_names_ov,
                    )
                    if show_cri_gr:
                        trace_kw["error_x"] = dict(type="data", array=err_plus_c, arrayminus=err_minus_c, thickness=1.2, color=color_ov)
                    fig_drill.add_trace(go.Scatter(**trace_kw))
                tickvals_gr_ov = [r * y_per_row_ov + group_band_ov / 2 for r in range(n_c)]
                if ref_m_gr is not None:
                    fig_drill.add_vline(x=ref_m_gr, line_dash="dot", line_color="gray", line_width=1.5, annotation_text="Current level mean")
                fig_drill.update_layout(
                    title="Forest plot — grouped by dimension",
                    xaxis=dict(title="Score (0–100)", range=[0, 105]),
                    yaxis=dict(tickmode="array", tickvals=tickvals_gr_ov, ticktext=child_names_ov, autorange="reversed", tickfont=dict(size=11)),
                    height=max(420, 72 * max(n_c, 1)),
                    margin=dict(l=220),
                    template="plotly_white",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_drill, use_container_width=True)
            st.caption("Current level mean as dotted reference. 95% credibility intervals shown.")

        # Team level: compact profile (forest plot above already shows individuals as rows)
        if level_ov == "Team" and sel_team_ov and cur_m_ov is not None and cur_s_ov is not None:
            st.subheader("Team profile")
            cur_m_sup_t, cur_s_sup_t = sub_to_super_means_sds(np.asarray(cur_m_ov), np.asarray(cur_s_ov))
            lo_t = np.clip(cur_m_sup_t - cri_scale_ov * cur_s_sup_t, 0, 100)
            hi_t = np.clip(cur_m_sup_t + cri_scale_ov * cur_s_sup_t, 0, 100)
            cols_t = st.columns(5)
            for k in range(5):
                with cols_t[k]:
                    st.metric(super_names[k], f"{float(cur_m_sup_t[k]):.1f}", f"95% CrI: {float(lo_t[k]):.1f}–{float(hi_t[k]):.1f}")

    else:
        st.info("No precomputed results. Run **`python scripts/prepare_dashboard_data.py`** to generate **culture_results.json**, then reload this page.")
        super_names_ph = get_superfactor_names()
        fig_ph = go.Figure(go.Scatterpolar(
            r=[50] * 5 + [50],
            theta=super_names_ph + [super_names_ph[0]],
            fill="toself",
            fillcolor="rgba(200, 200, 200, 0.2)",
            line=dict(color="lightgray", dash="dot"),
            name="Neutral (no data yet)",
        ))
        fig_ph.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100]), angularaxis=dict(tickfont=dict(size=12))),
            height=380,
            margin=dict(t=24, b=24),
            template="plotly_white",
            showlegend=False,
        )
        st.plotly_chart(fig_ph, use_container_width=True)

# -----------------------------------------------------------------------------
# Tab: Statistical detail — prior & posterior distributions, drill-down
# -----------------------------------------------------------------------------
with tab_statistical:
    st.header("Prior & posterior distributions")
    st.markdown("Belief and uncertainty. When data is loaded, the posterior is computed automatically.")

    view_mode = st.radio(
        "Show as",
        ["Distribution curves", "Violin plots"],
        horizontal=True,
        key="prior_view",
    )
    n_samples = st.slider("Prior samples", min_value=2000, max_value=15000, value=n_samples_default, step=1000, key="n_prior_samples")
    st.caption("Posterior from precomputed **culture_results.json**. To refresh, run `python scripts/prepare_dashboard_data.py`.")

    if st.session_state.belief_updated and st.session_state.posterior_theta_org is not None:
        _pm = np.mean(st.session_state.posterior_theta_org, axis=0)
        st.caption(f"**Prior** (lighter) vs **posterior** (darker). Posterior means: {', '.join(f'{x:.1f}' for x in _pm)}.")

    rng = np.random.default_rng(42)
    theta_org, theta_sub = sample_prior_org_sub(n_samples=n_samples, rng=rng)
    post_org = st.session_state.posterior_theta_org
    post_sub = st.session_state.posterior_theta_sub
    show_posterior = st.session_state.belief_updated and post_org is not None and post_sub is not None
    grid = np.linspace(0, 100, 200)

    def kde_on_grid(samples, grid):
        """KDE evaluated on grid; returns non-negative density (clip and renormalize for display)."""
        samples = np.asarray(samples, dtype=float).ravel()
        samples = samples[np.isfinite(samples)]
        if len(samples) < 2:
            return np.zeros_like(grid)
        try:
            kde = stats.gaussian_kde(samples, bw_method="scott")
            dens = kde(grid)
            dens = np.clip(dens, 0, None)
            if np.sum(dens) > 0:
                dens = dens / (np.sum(dens) * (grid[1] - grid[0]))
            return dens
        except Exception:
            return np.zeros_like(grid)

    if view_mode == "Distribution curves":
        # ---- 5 superfactors: 1 row × 5 columns of density curves (prior + optional posterior) ----
        st.subheader("Organization level — 5 superfactors")
        fig_super = make_subplots(rows=1, cols=5, subplot_titles=super_names, shared_xaxes=True, shared_yaxes=False)
        for k, name in enumerate(super_names):
            dens_prior = kde_on_grid(theta_org[:, k], grid)
            dens_post = kde_on_grid(post_org[:, k], grid) if show_posterior else np.zeros_like(grid)
            y_max = float(np.max(np.concatenate([dens_prior, dens_post])) * 1.15) or 0.01
            fig_super.add_trace(
                go.Scatter(
                    x=grid, y=dens_prior, fill="tozeroy",
                    line=dict(color=colors[k % len(colors)], dash="dash", width=1.5),
                    opacity=0.5, name="Prior",
                ),
                row=1, col=k + 1,
            )
            if show_posterior:
                fig_super.add_trace(
                    go.Scatter(
                        x=grid, y=dens_post, fill="tozeroy",
                        line=dict(color=colors[k % len(colors)], width=2), name="Posterior",
                    ),
                    row=1, col=k + 1,
                )
            # Median and 95% CrI for prior
            med_p = np.median(theta_org[:, k])
            lo_p, hi_p = np.percentile(theta_org[:, k], [2.5, 97.5])
            fig_super.add_vline(x=med_p, line_dash="dot", line_color="gray", opacity=0.7, row=1, col=k + 1)
            fig_super.add_vline(x=lo_p, line_dash="dot", line_color="gray", opacity=0.4, row=1, col=k + 1)
            fig_super.add_vline(x=hi_p, line_dash="dot", line_color="gray", opacity=0.4, row=1, col=k + 1)
            if show_posterior:
                med_po = np.median(post_org[:, k])
                lo_po, hi_po = np.percentile(post_org[:, k], [2.5, 97.5])
                fig_super.add_vline(x=med_po, line_dash="solid", line_color=colors[k % len(colors)], row=1, col=k + 1)
                fig_super.add_vline(x=lo_po, line_dash="solid", line_color=colors[k % len(colors)], opacity=0.6, row=1, col=k + 1)
                fig_super.add_vline(x=hi_po, line_dash="solid", line_color=colors[k % len(colors)], opacity=0.6, row=1, col=k + 1)
            fig_super.update_yaxes(range=[0, y_max], row=1, col=k + 1)
        fig_super.update_xaxes(title_text="Score (0–100)", range=[0, 100])
        fig_super.update_yaxes(title_text="Density")
        fig_super.update_layout(
            title_text="Prior and posterior (after Update belief)" if show_posterior else "Prior distribution of each superfactor",
            height=380,
            template="plotly_white",
            showlegend=show_posterior,
            margin=dict(t=80),
        )
        st.plotly_chart(fig_super, use_container_width=True)

        # ---- 15 subfactors: 5 rows × 3 columns of density curves ----
        st.subheader("Subfactors (3 per superfactor)")
        subplot_titles = []
        for _domain_name, dims in DOMAINS:
            subplot_titles.extend([dn for _, dn in dims])
        fig_sub = make_subplots(rows=5, cols=3, subplot_titles=subplot_titles, shared_xaxes=True, shared_yaxes=False)
        idx = 0
        for k, (domain_name, dims) in enumerate(DOMAINS):
            for d, (did, dn) in enumerate(dims):
                j = DIMENSION_IDS.index(did)
                dens_prior = kde_on_grid(theta_sub[:, j], grid)
                dens_post = kde_on_grid(post_sub[:, j], grid) if show_posterior else np.zeros_like(grid)
                y_max = float(np.max(np.concatenate([dens_prior, dens_post])) * 1.15) or 0.01
                row, col = idx // 3 + 1, (idx % 3) + 1
                fig_sub.add_trace(
                    go.Scatter(
                        x=grid, y=dens_prior, fill="tozeroy",
                        line=dict(color=domain_colors[k], dash="dash", width=1.5), opacity=0.5, name="Prior",
                    ),
                    row=row, col=col,
                )
                if show_posterior:
                    fig_sub.add_trace(
                        go.Scatter(
                            x=grid, y=dens_post, fill="tozeroy",
                            line=dict(color=domain_colors[k], width=2), name="Posterior",
                        ),
                        row=row, col=col,
                    )
                med_p = np.median(theta_sub[:, j])
                lo_p, hi_p = np.percentile(theta_sub[:, j], [2.5, 97.5])
                fig_sub.add_vline(x=med_p, line_dash="dot", line_color="gray", opacity=0.5, row=row, col=col)
                fig_sub.add_vline(x=lo_p, line_dash="dot", line_color="gray", opacity=0.3, row=row, col=col)
                fig_sub.add_vline(x=hi_p, line_dash="dot", line_color="gray", opacity=0.3, row=row, col=col)
                if show_posterior:
                    med_po = np.median(post_sub[:, j])
                    lo_po, hi_po = np.percentile(post_sub[:, j], [2.5, 97.5])
                    fig_sub.add_vline(x=med_po, line_dash="solid", line_color=domain_colors[k], row=row, col=col)
                    fig_sub.add_vline(x=lo_po, line_dash="solid", line_color=domain_colors[k], opacity=0.6, row=row, col=col)
                    fig_sub.add_vline(x=hi_po, line_dash="solid", line_color=domain_colors[k], opacity=0.6, row=row, col=col)
                fig_sub.update_yaxes(range=[0, y_max], row=row, col=col)
                idx += 1
        fig_sub.update_xaxes(title_text="Score (0–100)", range=[0, 100])
        fig_sub.update_yaxes(title_text="Density")
        fig_sub.update_layout(
            title_text="Prior and posterior (after Update belief)" if show_posterior else "Prior distribution of each subfactor",
            height=700,
            template="plotly_white",
            showlegend=show_posterior,
            margin=dict(t=80),
        )
        st.plotly_chart(fig_sub, use_container_width=True)

    else:
        # ---- Violin: 5 superfactors (prior + optional posterior) ----
        st.subheader("Organization level — 5 superfactors")
        fig_super = go.Figure()
        for k, name in enumerate(super_names):
            fig_super.add_trace(
                go.Violin(
                    x=theta_org[:, k],
                    name=f"{name} (prior)" if show_posterior else name,
                    line_color=colors[k % len(colors)],
                    box_visible=True,
                    meanline_visible=True,
                    opacity=0.5,
                )
            )
            if show_posterior:
                fig_super.add_trace(
                    go.Violin(
                        x=post_org[:, k],
                        name=f"{name} (posterior)",
                        line_color=colors[k % len(colors)],
                        box_visible=True,
                        meanline_visible=True,
                    )
                )
        fig_super.update_layout(
            title="Prior and posterior (after Update belief)" if show_posterior else "Prior distribution of each superfactor",
            xaxis_title="Score (0–100)",
            xaxis_range=[0, 100],
            yaxis_title="",
            height=420,
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(t=80),
        )
        st.plotly_chart(fig_super, use_container_width=True)

        # ---- Violin: 15 subfactors (5 figures) ----
        st.subheader("Subfactors (3 per superfactor)")
        for k, (domain_name, dims) in enumerate(DOMAINS):
            indices = [DIMENSION_IDS.index(did) for did, _ in dims]
            names = [dn for _, dn in dims]
            fig_d = go.Figure()
            for i, (idx, nm) in enumerate(zip(indices, names)):
                fig_d.add_trace(
                    go.Violin(
                        x=theta_sub[:, idx],
                        name=f"{nm} (prior)" if show_posterior else nm,
                        line_color=domain_colors[k],
                        box_visible=True,
                        meanline_visible=True,
                        opacity=0.5,
                    )
                )
                if show_posterior:
                    fig_d.add_trace(
                        go.Violin(
                            x=post_sub[:, idx],
                            name=f"{nm} (posterior)",
                            line_color=domain_colors[k],
                            box_visible=True,
                            meanline_visible=True,
                        )
                    )
            fig_d.update_layout(
                title=domain_name + (" — prior & posterior" if show_posterior else ""),
                xaxis_title="Score (0–100)",
                xaxis_range=[0, 100],
                height=320,
                template="plotly_white",
                showlegend=True,
                margin=dict(t=60),
            )
            st.plotly_chart(fig_d, use_container_width=True)

    st.caption("These are the prior distributions—the same model with no data. When you upload response data, the posterior (next step) will update these.")

    # -----------------------------------------------------------------------------
    # Drill down: level selector, context, forest plot, and current-context distribution
    # -----------------------------------------------------------------------------
    if st.session_state.hierarchical_result is not None:
        hi = st.session_state.hierarchical_result
        by_id = hi.get("by_id") or {}
        # Same division list as overview: union of division.ids and division_to_depts keys
        div_ids_from_division = hi.get("division", {}).get("ids") or []
        division_to_depts = hi.get("division_to_depts") or {}
        div_ids_from_map = list(division_to_depts.keys())
        div_ids = list(dict.fromkeys(div_ids_from_division + [d for d in div_ids_from_map if d not in div_ids_from_division]))
        dept_to_teams = hi.get("department", {}).get("dept_to_teams") or {}
        dept_to_division = hi.get("department", {}).get("dept_to_division") or {}

        def _name(nid):
            return (by_id.get(nid) or {}).get("name", nid)

        st.header("Drill down")
        st.markdown("Select a level and (optionally) an entity to see children as a forest plot and the current context mean as reference.")

        level = st.radio(
            "Level",
            ["Organization", "Division", "Department", "Team"],
            horizontal=True,
            key="drill_level",
        )

        selected_division_id = None
        selected_dept_id = None
        selected_team_id = None

        if level == "Division":
            if div_ids:
                div_options = [_name(d) for d in div_ids]
                sel_idx = st.selectbox("Division", range(len(div_ids)), format_func=lambda i: div_options[i], key="sel_division")
                selected_division_id = div_ids[sel_idx]
            else:
                st.info("No divisions in hierarchy.")
        elif level == "Department":
            if div_ids:
                div_options = [_name(d) for d in div_ids]
                sel_div_idx = st.selectbox("Division", range(len(div_ids)), format_func=lambda i: div_options[i], key="sel_div_dept")
                selected_division_id = div_ids[sel_div_idx]
                dept_ids = division_to_depts.get(selected_division_id) or []
                if dept_ids:
                    dept_options = [_name(d) for d in dept_ids]
                    sel_dept_idx = st.selectbox("Department", range(len(dept_ids)), format_func=lambda i: dept_options[i], key="sel_dept")
                    selected_dept_id = dept_ids[sel_dept_idx]
                else:
                    st.info("No departments in this division.")
            else:
                st.info("No divisions in hierarchy.")
        elif level == "Team":
            if div_ids:
                div_options = [_name(d) for d in div_ids]
                sel_div_idx = st.selectbox("Division", range(len(div_ids)), format_func=lambda i: div_options[i], key="sel_div_team")
                selected_division_id = div_ids[sel_div_idx]
                dept_ids = division_to_depts.get(selected_division_id) or []
                if dept_ids:
                    dept_options = [_name(d) for d in dept_ids]
                    sel_dept_idx = st.selectbox("Department", range(len(dept_ids)), format_func=lambda i: dept_options[i], key="sel_dept_team")
                    selected_dept_id = dept_ids[sel_dept_idx]
                    team_ids = dept_to_teams.get(selected_dept_id) or []
                    if team_ids:
                        team_options = [_name(t) for t in team_ids]
                        sel_team_idx = st.selectbox("Team", range(len(team_ids)), format_func=lambda i: team_options[i], key="sel_team")
                        selected_team_id = team_ids[sel_team_idx]
                    else:
                        st.info("No teams in this department.")
                else:
                    st.info("No departments in this division.")
            else:
                st.info("No divisions in hierarchy.")

        # Note: We do not write back to overview_* from here — those keys are bound to widgets
        # in the Culture at a glance tab, and Streamlit forbids modifying widget state after creation.
        # Sunburst/Overview → Statistical sync still applies when you select in Culture at a glance.

        # Resolve current context mean/sd (15-dim) and super (5-dim) for reference
        def get_current_mean_sd():
            org = hi.get("org") or {}
            if level == "Organization":
                m = org.get("mean_sub")
                s = org.get("sd_sub")
                return (m, s) if m is not None and s is not None else (None, None)
            if level == "Division" and selected_division_id:
                div = hi.get("division") or {}
                m = div.get("means", {}).get(selected_division_id)
                s = div.get("sds", {}).get(selected_division_id)
                return (m, s) if m is not None and s is not None else (None, None)
            if level == "Department" and selected_dept_id:
                dept = hi.get("department") or {}
                m = dept.get("means", {}).get(selected_dept_id)
                s = dept.get("sds", {}).get(selected_dept_id)
                return (m, s) if m is not None and s is not None else (None, None)
            if level == "Team" and selected_team_id:
                team = hi.get("team") or {}
                m = team.get("means", {}).get(selected_team_id)
                s = team.get("sds", {}).get(selected_team_id)
                return (m, s) if m is not None and s is not None else (None, None)
            return (None, None)

        # Children for forest plot: list of (id, mean_15, sd_15)
        def get_children():
            if level == "Organization":
                div = hi.get("division") or {}
                means, sds = div.get("means"), div.get("sds")
                return [(cid, means.get(cid), sds.get(cid)) for cid in div_ids if means and sds and cid in means]
            if level == "Division" and selected_division_id:
                dept_ids_c = division_to_depts.get(selected_division_id) or []
                dept = hi.get("department") or {}
                means, sds = dept.get("means"), dept.get("sds")
                return [(cid, means.get(cid), sds.get(cid)) for cid in dept_ids_c if means and sds and cid in means]
            if level == "Department" and selected_dept_id:
                team_ids_c = dept_to_teams.get(selected_dept_id) or []
                team = hi.get("team") or {}
                means, sds = team.get("means"), team.get("sds")
                return [(cid, means.get(cid), sds.get(cid)) for cid in team_ids_c if means and sds and cid in means]
            return []

        cur_mean_15, cur_sd_15 = get_current_mean_sd()
        children = get_children()

        # Forest plot: one dimension (first superfactor). Child intervals = mean ± 1.96*sd; reference = current mean (super 0).
        super_idx = 0  # first superfactor for forest
        if cur_mean_15 is not None and cur_sd_15 is not None:
            cur_m_sup, cur_s_sup = sub_to_super_means_sds(np.asarray(cur_mean_15), np.asarray(cur_sd_15))
            ref_mean = float(cur_m_sup[super_idx])
        else:
            ref_mean = None

        if children or ref_mean is not None:
            # Build child stats for first superfactor (index 0)
            child_names = []
            child_means = []
            child_lo = []
            child_hi = []
            for cid, m15, s15 in children:
                if m15 is None or s15 is None:
                    continue
                m_sup, s_sup = sub_to_super_means_sds(np.asarray(m15), np.asarray(s15))
                mu = float(m_sup[super_idx])
                sd = float(s_sup[super_idx])
                child_names.append(_name(cid))
                child_means.append(mu)
                child_lo.append(mu - 1.96 * sd)
                child_hi.append(mu + 1.96 * sd)

            if child_names or ref_mean is not None:
                st.subheader("Forest plot (first superfactor: " + super_names[super_idx] + ")")
                fig_f = go.Figure()
                if child_names:
                    # Horizontal segments: 95% CrI (lo–hi) and point at mean
                    for i in range(len(child_names)):
                        fig_f.add_trace(
                            go.Scatter(
                                x=[child_lo[i], child_hi[i]],
                                y=[i, i],
                                mode="lines",
                                line=dict(color="#4a90d9", width=6),
                                showlegend=(i == 0),
                                name="95% CrI",
                            )
                        )
                    fig_f.add_trace(
                        go.Scatter(
                            x=child_means,
                            y=list(range(len(child_names))),
                            mode="markers",
                            marker=dict(symbol="diamond", size=12, color="#2d5a87", line=dict(width=1, color="white")),
                            name="Mean",
                        )
                    )
                    fig_f.update_yaxes(tickvals=list(range(len(child_names))), ticktext=child_names, title="")
                if ref_mean is not None:
                    fig_f.add_vline(x=ref_mean, line_dash="dash", line_color="gray", line_width=2, annotation_text="Reference (current level mean)")
                fig_f.update_xaxes(title_text="Score (0–100)", range=[0, 100])
                fig_f.update_layout(
                    title="Lower-level units (95% CrI) and current level mean as reference",
                    height=max(280, 40 * len(child_names)),
                    template="plotly_white",
                    showlegend=True,
                    margin=dict(t=60),
                )
                st.plotly_chart(fig_f, use_container_width=True)

        # Current-context distribution: show median and 95% CrI for selected entity (5 superfactors)
        if cur_mean_15 is not None and cur_sd_15 is not None:
            st.subheader("Current context — distribution (median and 95% CrI)")
            cur_m_sup, cur_s_sup = sub_to_super_means_sds(np.asarray(cur_mean_15), np.asarray(cur_sd_15))
            n_samp = 4000
            rng_drill = np.random.default_rng(43)
            samples_cur = rng_drill.normal(cur_m_sup, np.maximum(cur_s_sup, 0.1), size=(n_samp, 5))
            samples_cur = np.clip(samples_cur, 0, 100)
            fig_cur = make_subplots(rows=1, cols=5, subplot_titles=super_names, shared_xaxes=True, shared_yaxes=False)
            for k in range(5):
                dens = kde_on_grid(samples_cur[:, k], grid)
                y_max = float(np.max(dens) * 1.15) or 0.01
                fig_cur.add_trace(
                    go.Scatter(x=grid, y=dens, fill="tozeroy", line=dict(color=colors[k], width=2), name=super_names[k]),
                    row=1, col=k + 1,
                )
                med = np.median(samples_cur[:, k])
                lo, hi = np.percentile(samples_cur[:, k], [2.5, 97.5])
                fig_cur.add_vline(x=med, line_dash="solid", line_color=colors[k], row=1, col=k + 1)
                fig_cur.add_vline(x=lo, line_dash="dot", line_color=colors[k], opacity=0.6, row=1, col=k + 1)
                fig_cur.add_vline(x=hi, line_dash="dot", line_color=colors[k], opacity=0.6, row=1, col=k + 1)
                fig_cur.update_yaxes(range=[0, y_max], row=1, col=k + 1)
            fig_cur.update_xaxes(title_text="Score (0–100)", range=[0, 100])
            fig_cur.update_layout(height=360, template="plotly_white", margin=dict(t=60))
            st.plotly_chart(fig_cur, use_container_width=True)
            meds = np.median(samples_cur, axis=0)
            los, his = np.percentile(samples_cur, [2.5, 97.5], axis=0)
            st.caption("Median and 95% CrI for selected context. " + " | ".join(f"{super_names[k]}: {meds[k]:.1f} [{los[k]:.1f}–{his[k]:.1f}]" for k in range(5)))
