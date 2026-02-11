"""
Item bank for IRT-style slider items (0-100): definition and suggested parameters.
Logistic (S-shaped) model: E[Y] = 100 * logistic(alpha + lambda*(theta-50)/50), alpha = logit(nu/100).
Bounded in (0, 100) by construction; nu = E[Y] at theta=50, lambda = discrimination.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .dimensions import DIMENSION_IDS, dimension_index


def create_item_bank(
    items_per_dimension: int,
    *,
    nu: float = 50.0,
    lam: float = 1.0,
    sigma: float = 10.0,
) -> List[Dict[str, Any]]:
    """Create one item bank: N items per dimension with default or given parameters."""
    bank: List[Dict[str, Any]] = []
    for dim_id in DIMENSION_IDS:
        for k in range(items_per_dimension):
            item_id = f"{dim_id}_item{k + 1}"
            bank.append({
                "item_id": item_id,
                "dimension_id": dim_id,
                "nu": nu,
                "lambda": lam,
                "sigma": sigma,
            })
    return bank


# Ranges for realistic item-pool suggestion (literature-style)
NU_LO, NU_HI = 22.0, 78.0
LAM_WEAK_LO, LAM_WEAK_HI = 0.5, 0.78
LAM_STRONG_LO, LAM_STRONG_HI = 1.15, 1.5
SIGMA_LOW_LO, SIGMA_LOW_HI = 5.0, 9.0
SIGMA_HIGH_LO, SIGMA_HIGH_HI = 13.0, 18.0


def suggest_item_parameters(rng=None) -> tuple:
    """Return (nu, lambda, sigma) with literature-based realistic spreads (single draw)."""
    import numpy as np
    if rng is None:
        rng = np.random.default_rng()
    nu = float(np.clip(rng.normal(50, 12), 20, 80))
    lam = float(np.clip(rng.normal(1.0, 0.25), 0.5, 1.5))
    sigma = float(np.clip(rng.uniform(6, 14), 5, 15))
    return (nu, lam, sigma)


def apply_suggested_parameters(
    bank: List[Dict[str, Any]],
    rng=None,
    *,
    quality_bias: float = 0.5,
) -> None:
    """
    Fill each item in bank with suggested (nu, lambda, sigma) per dimension.
    Per dimension: spread of difficulties (nu), loadings (lambda), residual (sigma).
    quality_bias in [0, 1]: 0 = more likely weak lambda / high sigma, 1 = more likely strong lambda / low sigma.
    Mutates bank in place.
    """
    import numpy as np
    from collections import defaultdict

    if rng is None:
        rng = np.random.default_rng()
    quality_bias = max(0.0, min(1.0, float(quality_bias)))

    by_dim: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in bank:
        by_dim[item["dimension_id"]].append(item)

    for dim_id, dim_items in by_dim.items():
        K = len(dim_items)
        if K == 0:
            continue

        # nu: spread of difficulties (easy / medium / hard), no quality bias
        nus = [NU_LO + (NU_HI - NU_LO) * (i + 0.5) / K for i in range(K)]
        nus = [float(np.clip(nu + rng.uniform(-3, 3), NU_LO, NU_HI)) for nu in nus]

        # lambda: weak vs strong; quality_bias = prob of drawing from strong band
        lams = []
        for _ in range(K):
            if rng.random() < quality_bias:
                lam = float(rng.uniform(LAM_STRONG_LO, LAM_STRONG_HI))
            else:
                lam = float(rng.uniform(LAM_WEAK_LO, LAM_WEAK_HI))
            lams.append(lam)

        # sigma: low (precise) vs high (noisy); quality_bias = prob of drawing low
        sigmas = []
        for _ in range(K):
            if rng.random() < quality_bias:
                sig = float(rng.uniform(SIGMA_LOW_LO, SIGMA_LOW_HI))
            else:
                sig = float(rng.uniform(SIGMA_HIGH_LO, SIGMA_HIGH_HI))
            sigmas.append(sig)

        # Shuffle assignment so (nu, lam, sigma) pairs are randomized
        perm = rng.permutation(K)
        for i in range(K):
            j = int(perm[i])
            dim_items[i]["nu"] = nus[j]
            dim_items[i]["lambda"] = lams[j]
            dim_items[i]["sigma"] = sigmas[j]


def _logistic(z: Any) -> Any:
    """1 / (1 + exp(-z)), stable for large |z|. Accepts scalar or array."""
    import numpy as np
    return 1.0 / (1.0 + np.exp(-np.clip(np.asarray(z, dtype=float), -500, 500)))


def expected_response(nu: float, lam: float, theta: Any) -> Any:
    """E[Y] = 100 * logistic(alpha + lam*(theta-50)/50) with alpha = logit(nu/100). S-shaped, bounded in (0, 100). theta can be scalar or array."""
    import numpy as np
    p0 = np.clip(nu / 100.0, 1e-4, 1.0 - 1e-4)
    alpha = np.log(p0 / (1.0 - p0))
    th = np.asarray(theta, dtype=float)
    z = alpha + lam * (th - 50.0) / 50.0
    out = 100.0 * _logistic(z)
    return float(out) if np.isscalar(theta) else out


def simulate_item_responses_from_org(
    latent_records: List[Dict[str, Any]],
    item_bank: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    *,
    rng: Optional[Any] = None,
) -> Any:
    """
    Simulate item responses using person-level (employee) latent scores.
    Each employee has a 15-dim theta; their item responses are Y = nu + lambda*theta_dim + N(0, sigma^2).
    Returns a pandas DataFrame: employee_id, team_id, then one column per item (item_id). One row per employee.
    """
    import numpy as np
    import pandas as pd
    from collections import defaultdict

    if rng is None:
        rng = np.random.default_rng()
    # Build employee_id -> 15-dim theta (use true_latent if present else point)
    by_employee: Dict[str, Dict[str, float]] = defaultdict(dict)
    for rec in latent_records:
        eid = rec.get("employee_id")
        if eid is None:
            continue
        dim_id = rec["dimension_id"]
        val = rec.get("true_latent", rec.get("point", 50.0))
        by_employee[eid][dim_id] = float(val)
    # Preserve order: list of (employee_id, team_id) from latent_records (first occurrence per employee)
    seen = set()
    employee_list: List[tuple] = []
    for rec in latent_records:
        eid = rec.get("employee_id")
        if eid is None or eid in seen:
            continue
        seen.add(eid)
        employee_list.append((eid, rec["team_id"]))
    if not employee_list:
        raise ValueError("No employee-level latent records (need employee_id in each record).")
    rows = []
    for idx, (eid, tid) in enumerate(employee_list):
        arr = np.array([by_employee[eid].get(dim_id, 50.0) for dim_id in DIMENSION_IDS], dtype=float)
        theta = np.clip(arr, 0, 100)
        row = {"respondent_id": idx + 1, "employee_id": eid, "team_id": tid}
        for item in item_bank:
            d = dimension_index(item["dimension_id"])
            nu, lam, sig = item["nu"], item["lambda"], item["sigma"]
            mu = expected_response(nu, lam, theta[d])
            y = mu + rng.normal(0, sig)
            row[item["item_id"]] = float(np.clip(y, 0, 100))
        rows.append(row)
    return pd.DataFrame(rows)


def irt_scores_from_response_dataset(
    response_df: Any,
    item_bank: List[Dict[str, Any]],
) -> Any:
    """
    Estimate 15-dim theta per person from item responses using the logistic IRT model (ML).
    For each dimension, items measuring that dimension and their (nu, lambda, sigma) define
    the likelihood; theta is estimated by maximizing likelihood over [0, 100].
    Returns (n_people x 15) numpy array, same row order as response_df.
    """
    import numpy as np
    from scipy.optimize import minimize_scalar

    n_people = len(response_df)
    n_dim = len(DIMENSION_IDS)
    # Items per dimension: list of (item_id, nu, lam, sigma) for dim d
    items_by_dim: List[List[tuple]] = [[] for _ in range(n_dim)]
    for it in item_bank:
        d = dimension_index(it["dimension_id"])
        items_by_dim[d].append((it["item_id"], it["nu"], it["lambda"], it["sigma"]))

    theta_hat = np.full((n_people, n_dim), 50.0, dtype=float)
    for d in range(n_dim):
        item_specs = items_by_dim[d]
        if not item_specs:
            continue
        item_ids = [x[0] for x in item_specs]
        # Only rows that have these columns
        if not all(c in response_df.columns for c in item_ids):
            continue
        Y = np.asarray(response_df[item_ids], dtype=float)  # (n_people, n_items_dim_d)

        def neg_log_lik(theta: float, y: np.ndarray, specs: List[tuple]) -> float:
            out = 0.0
            for j, (_id, nu, lam, sig) in enumerate(specs):
                mu = expected_response(nu, lam, theta)
                resid = (y[j] - mu) / max(sig, 1e-6)
                out += 0.5 * resid * resid
            return out

        for i in range(n_people):
            y_row = Y[i, :]
            try:
                res = minimize_scalar(
                    neg_log_lik,
                    bounds=(0.0, 100.0),
                    method="bounded",
                    args=(y_row, item_specs),
                )
                if res.success:
                    theta_hat[i, d] = float(np.clip(res.x, 0, 100))
            except Exception:
                pass
    return theta_hat


def build_icc_figure(
    items: List[Dict[str, Any]],
    theta_range: tuple = (0, 100),
    n_points: int = 101,
) -> Any:
    """Plot expected response vs theta for each item (ICC-style). Returns Plotly figure."""
    import numpy as np
    import plotly.graph_objects as go

    theta = np.linspace(theta_range[0], theta_range[1], n_points)
    fig = go.Figure()
    for item in items:
        nu, lam = item["nu"], item["lambda"]
        mu = expected_response(nu, lam, theta)  # already in (0, 100)
        name = f"{item['item_id']} (dim: {item['dimension_id']})"
        fig.add_trace(go.Scatter(x=theta.tolist(), y=mu.tolist(), mode="lines", name=name))
    fig.update_layout(
        title="Item characteristic curves (expected response vs latent trait)",
        xaxis_title="Latent trait θ (0–100)",
        yaxis_title="Expected response E[Y] (0–100)",
        xaxis_range=[0, 100],
        yaxis_range=[0, 100],
        height=max(400, 20 * len(items)),
        margin=dict(l=80),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left"),
    )
    fig.add_vline(x=50, line_dash="dot", line_color="gray")
    return fig


def build_icc_figure_by_dimension(
    items: List[Dict[str, Any]],
    dimension_id: str,
    theta_range: tuple = (0, 100),
    n_points: int = 101,
) -> Any:
    """One ICC figure for a single dimension's items."""
    import numpy as np
    import plotly.graph_objects as go

    sub = [i for i in items if i["dimension_id"] == dimension_id]
    if not sub:
        return go.Figure()
    theta = np.linspace(theta_range[0], theta_range[1], n_points)
    fig = go.Figure()
    for item in sub:
        nu, lam, sig = item["nu"], item["lambda"], item["sigma"]
        mu = expected_response(nu, lam, theta)  # already in (0, 100)
        fig.add_trace(go.Scatter(x=theta.tolist(), y=mu.tolist(), mode="lines", name=item["item_id"]))
    fig.update_layout(
        title=f"Items for dimension: {dimension_id}",
        xaxis_title="Latent trait θ (0–100)",
        yaxis_title="Expected response E[Y] (0–100)",
        xaxis_range=[0, 100],
        yaxis_range=[0, 100],
        height=400,
    )
    fig.add_vline(x=50, line_dash="dot", line_color="gray")
    return fig
