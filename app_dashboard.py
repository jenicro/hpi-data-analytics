"""
Results dashboard: Bayesian IRT prior (and later posterior) by organization level.
Run: streamlit run app_dashboard.py
     To start without pre-loaded data: set env HPI_START_WITH_DATA=0 (or false) before running.

Loads org_hierarchy.json and item_bank.json from the dashboard_input folder on startup.
Optional: loads dashboard_input/item_responses.csv by default so you can click "Update belief" right away.
"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from src.dimensions import DOMAINS, DIMENSION_IDS
from src.bayesian_irt import (
    sample_prior_org_sub,
    get_superfactor_names,
    get_subfactor_names,
)
from src.items import irt_scores_from_response_dataset
from src.hierarchical_posterior import compute_hierarchical_posterior, sub_to_super_means_sds

# Path to the folder where org_hierarchy.json and item_bank.json live
DASHBOARD_INPUT_DIR = Path(__file__).resolve().parent / "dashboard_input"
ORG_HIERARCHY_PATH = DASHBOARD_INPUT_DIR / "org_hierarchy.json"
ITEM_BANK_PATH = DASHBOARD_INPUT_DIR / "item_bank.json"
DEFAULT_RESPONSES_PATH = DASHBOARD_INPUT_DIR / "item_responses.csv"
# Start with data loaded by default; set HPI_START_WITH_DATA=0 or false to start empty
START_WITH_DATA = os.environ.get("HPI_START_WITH_DATA", "true").lower() in ("true", "1", "yes")

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
# Sidebar: Configuration and data
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Setup & data")
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
    st.caption("Default data from `item_responses.csv`. Set **HPI_START_WITH_DATA=0** to start empty.")
    if "response_data" not in st.session_state:
        st.session_state.response_data = None
        if START_WITH_DATA and DEFAULT_RESPONSES_PATH.exists():
            try:
                _df = pd.read_csv(DEFAULT_RESPONSES_PATH)
                if not _df.empty:
                    st.session_state.response_data = _df
            except Exception:
                pass
    uploaded = st.file_uploader("Upload response data (CSV/JSON)", type=["csv", "json"], key="response_upload")
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_json(uploaded)
            if not df.empty:
                prev = st.session_state.get("response_data")
                is_new = prev is None or len(prev) != len(df)
                st.session_state.response_data = df
                if is_new:
                    st.session_state.belief_updated = False
                    st.session_state.posterior_theta_org = None
                    st.session_state.posterior_theta_sub = None
                    st.session_state.hierarchical_result = None
                st.success(f"**{len(df)}** rows loaded")
        except Exception as e:
            st.error(str(e))
    if st.session_state.response_data is not None:
        st.caption(f"Using **{len(st.session_state.response_data)}** rows")
    with st.expander("Dimensions (5 × 3)"):
        for domain_name, dims in DOMAINS:
            st.markdown(f"**{domain_name}:** {', '.join(dn for _, dn in dims)}")

# -----------------------------------------------------------------------------
# Session state and auto posterior
# -----------------------------------------------------------------------------
if "belief_updated" not in st.session_state:
    st.session_state.belief_updated = False
if "posterior_theta_org" not in st.session_state:
    st.session_state.posterior_theta_org = None
if "posterior_theta_sub" not in st.session_state:
    st.session_state.posterior_theta_sub = None
if "hierarchical_result" not in st.session_state:
    st.session_state.hierarchical_result = None

n_samples_default = 6000
super_names = get_superfactor_names()
colors = ["#2d7d7d", "#c75b7a", "#e8a838", "#50c878", "#7b68a6"]
domain_colors = colors

def _compute_posterior(n_samp=n_samples_default):
    if st.session_state.response_data is None or not item_bank or not org_nodes:
        return False
    try:
        rng = np.random.default_rng(42)
        theta_hat = irt_scores_from_response_dataset(st.session_state.response_data, item_bank)
        hi = compute_hierarchical_posterior(org_nodes, st.session_state.response_data, theta_hat)
        st.session_state.hierarchical_result = hi
        org = hi["org"]
        post_org = rng.normal(org["mean_super"], np.maximum(org["sd_super"], 0.1), size=(n_samp, len(super_names)))
        post_sub = rng.normal(org["mean_sub"], np.maximum(org["sd_sub"], 0.1), size=(n_samp, len(DIMENSION_IDS)))
        post_org = np.clip(post_org, 0, 100)
        post_sub = np.clip(post_sub, 0, 100)
        st.session_state.posterior_theta_org = post_org
        st.session_state.posterior_theta_sub = post_sub
        st.session_state.belief_updated = True
        return True
    except Exception:
        return False

if (st.session_state.response_data is not None and item_bank and org_nodes and st.session_state.hierarchical_result is None):
    _compute_posterior(n_samples_default)

# -----------------------------------------------------------------------------
# Main: Title, summary stats, and tabs (Culture at a glance | Statistical detail)
# -----------------------------------------------------------------------------
st.title("Organizational culture")
st.caption("One view of where your organization stands across culture dimensions (0–100). Load data to see your profile.")

response_data = st.session_state.response_data
hi = st.session_state.hierarchical_result

# Summary stats row — epic metric cards when we have data
if response_data is not None and not response_data.empty:
    n_respondents = len(response_data)
    if hi and hi.get("team") and hi["team"].get("means"):
        n_teams = len(hi["team"]["means"])
    else:
        n_teams = response_data["team_id"].nunique() if "team_id" in response_data.columns else 0
    if hi and hi.get("department") and hi["department"].get("means"):
        n_departments = len(hi["department"]["means"])
    else:
        n_departments = 0
    if hi and hi.get("division") and hi["division"].get("ids"):
        n_divisions = len(hi["division"]["ids"])
    else:
        n_divisions = 0
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Respondents", f"{n_respondents:,}")
    s2.metric("Teams", f"{n_teams:,}")
    s3.metric("Departments", f"{n_departments:,}")
    s4.metric("Divisions", f"{n_divisions:,}")
    overall_val = float(np.mean(hi["org"]["mean_super"])) if hi and hi.get("org") and hi["org"].get("mean_super") is not None else None
    if overall_val is not None:
        s5.metric("Overall culture (0–100)", f"{overall_val:.1f}")
    else:
        s5.metric("Overall culture", "—")
    st.markdown("")  # spacing

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

        # Radar: 5 superfactors
        r_vals = list(mean_super) + [mean_super[0]]
        theta_labels = super_names
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=r_vals,
            theta=theta_labels + [theta_labels[0]],
            fill="toself",
            fillcolor="rgba(45, 125, 125, 0.4)",
            line=dict(color="#2d7d7d", width=2),
            name="Your culture",
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=[50] * 5 + [50],
            theta=theta_labels + [theta_labels[0]],
            fill="toself",
            fillcolor="rgba(150, 150, 150, 0.08)",
            line=dict(color="rgba(100,100,100,0.5)", dash="dot"),
            name="Neutral (50)",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=11)), angularaxis=dict(tickfont=dict(size=12))),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=40, b=40),
            height=420,
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # Division comparison (second-highest hierarchy) — how parts of the org compare
        div_info = hi.get("division") or {}
        div_ids = div_info.get("ids") or []
        div_means = div_info.get("means") or {}
        div_sds = div_info.get("sds") or {}
        by_id = hi.get("by_id") or {}
        if div_ids and div_means:
            st.subheader("How divisions compare")
            st.caption("Each division’s profile on the 5 culture dimensions. Compare at a glance.")
            div_names = [(by_id.get(d) or {}).get("name", d) for d in div_ids]
            # Heatmap: rows = divisions, cols = 5 superfactors
            z_div = np.array([sub_to_super_means_sds(np.asarray(div_means[d]), np.asarray(div_sds.get(d, np.full(15, 10))))[0] for d in div_ids])
            z_div = np.clip(z_div, 0, 100)
            fig_div = go.Figure(go.Heatmap(
                z=z_div,
                x=short_labels,
                y=div_names,
                colorscale="RdYlGn",
                zmin=0,
                zmax=100,
                showscale=True,
                colorbar=dict(title="Score", len=0.5, thickness=14),
                hovertemplate="%{y} — %{x}: %{z:.1f}<extra></extra>",
            ))
            fig_div.update_layout(
                height=max(220, 50 * len(div_ids)),
                margin=dict(t=24, b=24),
                xaxis=dict(tickangle=0),
                template="plotly_white",
            )
            st.plotly_chart(fig_div, use_container_width=True)

        # 15-dim strip: one row heatmap
        st.subheader("All 15 sub-dimensions")
        z = mean_sub.reshape(1, -1)
        fig_strip = go.Figure(go.Heatmap(
            z=z,
            x=sub_names_15,
            y=[""],
            colorscale="RdYlGn",
            zmin=0,
            zmax=100,
            showscale=True,
            colorbar=dict(title="Score", len=0.4, thickness=12),
            hovertemplate="%{x}: %{z:.1f}<extra></extra>",
        ))
        fig_strip.update_layout(
            title="Green = higher, red = lower",
            height=140,
            margin=dict(t=36, b=80, l=20),
            xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
            yaxis=dict(visible=False),
            template="plotly_white",
        )
        st.plotly_chart(fig_strip, use_container_width=True)

        # Sub-dimension cards: mean and 95% CrI per dimension
        st.caption("**Scores and 95% credibility intervals** (mean ± 1.96×SD) for each sub-dimension.")
        lo_cri = np.clip(mean_sub - 1.96 * sd_sub, 0, 100)
        hi_cri = np.clip(mean_sub + 1.96 * sd_sub, 0, 100)
        card_cols = st.columns(5)
        for j, name in enumerate(sub_names_15):
            with card_cols[j % 5]:
                st.metric(name, f"{mean_sub[j]:.1f}", f"95% CrI: {lo_cri[j]:.1f}–{hi_cri[j]:.1f}")
        st.markdown(f"**Overall culture strength:** {overall:.1f} (mean across 5 superfactors). For full Bayesian detail, open the **Statistical detail** tab.")
    else:
        st.info("Load response data in the sidebar to see your **organizational culture profile** (radar, division comparison, and 15-dim strip) here.")
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

    recompute_clicked = st.button("Recompute belief", key="update_belief", use_container_width=True)
    if recompute_clicked:
        st.session_state.hierarchical_result = None
        st.session_state.belief_updated = False
        st.session_state.posterior_theta_org = None
        st.session_state.posterior_theta_sub = None
    if recompute_clicked and st.session_state.response_data is not None and item_bank and org_nodes:
        if _compute_posterior(n_samples):
            st.success("Belief recomputed. Culture profile above updated.")
            st.rerun()
        else:
            st.error("Recompute failed. Check response data and item bank.")
    elif recompute_clicked:
        st.warning("Load response data and ensure item bank and org hierarchy are present.")

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
        div_ids = hi.get("division", {}).get("ids") or []
        division_to_depts = hi.get("division_to_depts") or {}
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
