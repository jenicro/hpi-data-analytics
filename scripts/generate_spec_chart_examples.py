"""
Generate example chart images for DASHBOARD_SPEC.md.
Requires: pip install plotly kaleido
Run from project root: python scripts/generate_spec_chart_examples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "dashboard_spec_images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def save_png(fig, name: str, width=700, height=400) -> None:
    path = OUT_DIR / f"{name}.png"
    try:
        fig.write_image(str(path), width=width, height=height, scale=2)
        print(f"Wrote {path}")
    except Exception as e:
        print(f"Skip {name}: {e} (install kaleido: pip install kaleido)")


# Example data
SUPER_LABELS = ["Momentum", "Connection", "Leadership", "Growth", "Traction"]
np.random.seed(42)
mean_super = np.clip(50 + np.random.randn(5) * 8, 35, 75)
mean_sub = np.clip(50 + np.random.randn(15) * 10, 25, 80)
sub_labels = [
    "Zuversicht", "Richtung", "Energie",
    "Authent. Verb.", "Vertr. Zus.", "Teamspirit",
    "Entwicklung", "Inspiration", "Anerkennung",
    "Neugier", "Good Fightclub", "Grit",
    "Ownership", "Fokus", "Konsequenz",
]
colors = ["#2d7d7d", "#c75b7a", "#e8a838", "#50c878", "#7b68a6"]
domain_colors = [colors[i // 3] for i in range(15)]


def chart_scores_bar():
    all_y = list(SUPER_LABELS) + [" "] + list(sub_labels)
    all_x = list(mean_super) + [0] + list(mean_sub)
    bar_colors = list(colors) + ["rgba(0,0,0,0)"] + domain_colors
    fig = go.Figure(go.Bar(
        y=all_y, x=all_x, orientation="h",
        marker_color=bar_colors,
        text=[f"{x:.0f}" for x in all_x if x > 0] + [""] * 16,
        textposition="outside",
    ))
    fig.update_layout(
        title="Scores at a glance (example) — bar chart",
        xaxis=dict(title="Score (0–100)", range=[0, 105]),
        yaxis=dict(autorange="reversed"),
        template="plotly_white",
        height=500,
        margin=dict(l=140),
    )
    save_png(fig, "scores-bar", height=500)


def chart_spider_5():
    n = 5
    angles = np.linspace(0, 360, n, endpoint=False)
    r = list(mean_super) + [mean_super[0]]
    theta = list(angles + 360 / n / 2) + [angles[0] + 360 / n / 2]
    fig = go.Figure(go.Scatterpolar(
        r=r, theta=SUPER_LABELS + [SUPER_LABELS[0]],
        fill="toself", fillcolor="rgba(45,125,125,0.4)",
        line=dict(color="#2d7d7d", width=2),
    ))
    fig.add_trace(go.Scatterpolar(
        r=[50] * 6, theta=SUPER_LABELS + [SUPER_LABELS[0]],
        fill="toself", fillcolor="rgba(200,200,200,0.15)",
        line=dict(color="gray", dash="dot"),
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 100])),
        title="5 super-dimensions (example) — spider",
        template="plotly_white",
        height=420,
    )
    save_png(fig, "spider-5", height=420)


def chart_spider_15():
    n = 15
    r = list(mean_sub) + [mean_sub[0]]
    theta_deg = np.linspace(0, 360, n, endpoint=False) + 360 / n / 2
    theta_labels = sub_labels + [sub_labels[0]]
    fig = go.Figure(go.Scatterpolar(
        r=r, theta=theta_labels,
        fill="toself", fillcolor="rgba(100,140,140,0.25)",
        line=dict(color="#4a9090", width=1.5),
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 100])),
        title="15 sub-dimensions (example) — spider",
        template="plotly_white",
        height=480,
        margin=dict(t=60),
    )
    save_png(fig, "spider-15", height=480)


def chart_spider_5_compare():
    # Comparison mode: two teams + org benchmark on same spider
    np.random.seed(10)
    team_a = np.clip(mean_super + np.random.randn(5) * 6, 35, 80)
    team_b = np.clip(mean_super + np.random.randn(5) * 6, 35, 80)
    org_bench = list(mean_super)  # benchmark
    theta_closed = SUPER_LABELS + [SUPER_LABELS[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=list(team_a) + [team_a[0]], theta=theta_closed,
        fill="toself", fillcolor="rgba(45,125,125,0.25)",
        line=dict(color="#2d7d7d", width=2),
        name="Team Alpha",
    ))
    fig.add_trace(go.Scatterpolar(
        r=list(team_b) + [team_b[0]], theta=theta_closed,
        fill="toself", fillcolor="rgba(199,91,122,0.25)",
        line=dict(color="#c75b7a", width=2),
        name="Team Beta",
    ))
    fig.add_trace(go.Scatterpolar(
        r=org_bench + [org_bench[0]], theta=theta_closed,
        fill="toself", fillcolor="rgba(150,150,150,0.1)",
        line=dict(color="#555", width=2, dash="dash"),
        name="Organization (benchmark)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 100])),
        title="Spider comparison — teams vs benchmark (example)",
        template="plotly_white",
        height=440,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    save_png(fig, "spider-5-compare", height=440)


def chart_forest():
    row_labels = ["Organization", "Division A", "Division B", "Division C"]
    means = [58.0, 62.0, 54.0, 61.0]
    err = [3.0, 4.0, 5.0, 3.5]
    fig = go.Figure(go.Scatter(
        x=means, y=list(range(4)),
        mode="markers",
        marker=dict(symbol="diamond", size=12, color="steelblue"),
        error_x=dict(type="data", array=err, arrayminus=err, thickness=2),
        text=row_labels,
    ))
    fig.add_vline(x=58, line_dash="dot", line_color="gray", annotation_text="Org mean")
    fig.update_layout(
        title="How divisions compare (example) — forest plot",
        xaxis=dict(title="Score (0–100)", range=[0, 105]),
        yaxis=dict(tickvals=list(range(4)), ticktext=row_labels, autorange="reversed"),
        template="plotly_white",
        height=320,
        margin=dict(l=120),
    )
    save_png(fig, "forest-plot", height=320)


# Sunburst: high-contrast colors (dark on white) — one per level for visibility
_SUNBURST_ROOT = "#0d47a1"      # dark blue (center)
_SUNBURST_LEVEL1 = "#1565c0"   # divisions
_SUNBURST_LEVEL2 = "#1976d2"   # departments
_SUNBURST_LEVEL3 = "#1e88e5"   # teams


def chart_sunburst():
    # Full org: 3 divisions, multiple depts per division, multiple teams per dept
    ids = [
        "org",
        "div1", "div2", "div3",
        "d1a", "d1b", "d2a", "d2b", "d3a", "d3b",
        "t1a1", "t1a2", "t1b1", "t2a1", "t2a2", "t2b1", "t3a1", "t3b1", "t3b2",
    ]
    labels = [
        "Organization",
        "Division A", "Division B", "Division C",
        "Sales", "Marketing", "Engineering", "Product", "HR", "Finance",
        "Team 1", "Team 2", "Team 3", "Team 4", "Team 5", "Team 6", "Team 7", "Team 8", "Team 9",
    ]
    parents = [
        "",
        "org", "org", "org",
        "div1", "div1", "div2", "div2", "div3", "div3",
        "d1a", "d1a", "d1b", "d2a", "d2a", "d2b", "d3a", "d3b", "d3b",
    ]
    # Explicit colors per node for contrast: root, then level 1, 2, 3
    sunburst_colors = (
        [_SUNBURST_ROOT]
        + [_SUNBURST_LEVEL1] * 3
        + [_SUNBURST_LEVEL2] * 6
        + [_SUNBURST_LEVEL3] * 9
    )
    fig = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents,
        branchvalues="total",
        marker=dict(colors=sunburst_colors, line=dict(color="white", width=1)),
    ))
    fig.update_layout(
        title="Org structure — sunburst (before click)",
        margin=dict(t=40),
        height=420,
        paper_bgcolor="white",
    )
    save_png(fig, "sunburst", height=420)


def chart_sunburst_after_click():
    # After user clicks "Division A": context is Division A, center shows its children
    ids = ["div1", "d1a", "d1b", "t1a1", "t1a2", "t1b1"]
    labels = ["Division A", "Sales", "Marketing", "Team 1", "Team 2", "Team 3"]
    parents = ["", "div1", "div1", "d1a", "d1a", "d1b"]
    sunburst_colors = (
        [_SUNBURST_ROOT]
        + [_SUNBURST_LEVEL2] * 2
        + [_SUNBURST_LEVEL3] * 3
    )
    fig = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents,
        branchvalues="total",
        marker=dict(colors=sunburst_colors, line=dict(color="white", width=1)),
    ))
    fig.update_layout(
        title="After clicking Division A — context is Division A",
        margin=dict(t=40),
        height=420,
        paper_bgcolor="white",
    )
    save_png(fig, "sunburst-after-click", height=420)


def chart_density_curves():
    # Prior = wide (little data); posterior = narrow (more data). Varied means per dimension.
    grid = np.linspace(0, 100, 200)
    # Different means per super-dimension (not all 50)
    prior_means = [42, 55, 51, 47, 61]
    prior_sig = 18   # wide: high uncertainty before data
    post_means = [45, 57, 49, 50, 58]   # posterior: shifted and tightened by data
    post_sig = 6    # narrow: more data reduces uncertainty
    fig = make_subplots(rows=1, cols=5, subplot_titles=SUPER_LABELS, shared_yaxes=False)
    for k in range(5):
        prior_dens = np.exp(-0.5 * ((grid - prior_means[k]) / prior_sig) ** 2)
        prior_dens = prior_dens / (prior_dens.sum() * (grid[1] - grid[0]))
        post_dens = np.exp(-0.5 * ((grid - post_means[k]) / post_sig) ** 2)
        post_dens = post_dens / (post_dens.sum() * (grid[1] - grid[0]))
        fig.add_trace(
            go.Scatter(
                x=grid, y=prior_dens, fill="tozeroy",
                line=dict(color=colors[k], width=1.5, dash="dash"),
                fillcolor="rgba(128,128,128,0.15)",
                name="Prior (before data)",
                legendgroup="prior",
                showlegend=(k == 0),
            ),
            row=1, col=k + 1,
        )
        fig.add_trace(
            go.Scatter(
                x=grid, y=post_dens, fill="tozeroy",
                line=dict(color=colors[k], width=2),
                fillcolor=colors[k],
                name="Posterior (after data)",
                legendgroup="posterior",
                showlegend=(k == 0),
            ),
            row=1, col=k + 1,
        )
    fig.update_xaxes(range=[0, 100], title_text="Score")
    fig.update_layout(
        title_text="Prior vs posterior — more data tightens and can shift the distribution",
        template="plotly_white",
        height=340,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    save_png(fig, "density-curves", width=900, height=340)


def main():
    chart_scores_bar()
    chart_spider_5()
    chart_spider_15()
    chart_spider_5_compare()
    chart_forest()
    chart_sunburst()
    chart_sunburst_after_click()
    chart_density_curves()
    print(f"Done. Images in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
