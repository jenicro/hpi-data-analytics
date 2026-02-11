"""
Exploratory factor analysis (EFA) sanity check for the item bank.
Simulate responses from item parameters and ground-truth latent structure,
run EFA, and compare loadings and factor correlations to the true dimensions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .dimensions import DIMENSION_IDS, dimension_index
from .items import expected_response


def build_ground_truth_correlation(
    r_within_domain: float = 0.6,
    r_cross_domain: float = 0.3,
) -> np.ndarray:
    """Build 15x15 correlation matrix (within-domain and cross-domain blocks)."""
    from .dimensions import DOMAINS
    N = len(DIMENSION_IDS)
    R = np.ones((N, N)) * r_cross_domain
    idx = 0
    for _domain_name, dims in DOMAINS:
        n = len(dims)
        R[idx : idx + n, idx : idx + n] = r_within_domain
        idx += n
    np.fill_diagonal(R, 1.0)
    return R


def simulate_item_responses(
    bank: List[Dict[str, Any]],
    R_truth: np.ndarray,
    n_respondents: int = 500,
    theta_mean: float = 50.0,
    theta_sd: float = 15.0,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, List[int], List[str]]:
    """
    Simulate response matrix (n_respondents x n_items) from item bank and ground-truth latent correlation.
    Returns (data, dim_index_per_item, item_ids).
    """
    if rng is None:
        rng = np.random.default_rng()
    R = np.array(R_truth, dtype=float)
    # Ensure PD for Cholesky
    min_eig = np.min(np.linalg.eigvalsh(R))
    if min_eig < 1e-8:
        R = R + (1e-8 - min_eig) * np.eye(R.shape[0])
    L = np.linalg.cholesky(R)

    n_items = len(bank)
    dim_index_per_item = [dimension_index(it["dimension_id"]) for it in bank]
    item_ids = [it["item_id"] for it in bank]

    # Respondents: theta (15-dim) ~ MVN(mean, theta_sd^2 * R)
    Z = rng.standard_normal((n_respondents, R.shape[0]))
    thetas = theta_mean + theta_sd * (Z @ L.T)
    thetas = np.clip(thetas, 0, 100)

    # Responses: E[Y] = logistic item model, then Y = E[Y] + N(0, sigma^2), clip to [0,100]
    data = np.zeros((n_respondents, n_items))
    for j, item in enumerate(bank):
        d = dim_index_per_item[j]
        nu, lam, sig = item["nu"], item["lambda"], item["sigma"]
        mu = expected_response(nu, lam, thetas[:, d])
        data[:, j] = np.clip(mu + rng.standard_normal(n_respondents) * sig, 0, 100)

    return data, dim_index_per_item, item_ids


def true_thetas_and_correlation_from_response_dataset(
    response_df: Any,
    latent_records: List[Dict[str, Any]],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build true theta matrix (n_people x 15) and 15x15 correlation from the data-generating process,
    in the same row order as response_df. Uses true_latent (or point) from latent_records.
    Returns (R_truth, theta_matrix).
    """
    from collections import defaultdict
    by_employee: Dict[str, Dict[str, float]] = defaultdict(dict)
    for rec in latent_records:
        eid = rec.get("employee_id")
        if eid is None:
            continue
        dim_id = rec["dimension_id"]
        val = rec.get("true_latent", rec.get("point", 50.0))
        by_employee[str(eid)][dim_id] = float(val)
    theta_list = []
    for eid in response_df["employee_id"]:
        key = str(eid)
        row = [by_employee.get(key, {}).get(dim_id, 50.0) for dim_id in DIMENSION_IDS]
        theta_list.append(row)
    theta_matrix = np.array(theta_list, dtype=float)
    theta_matrix = np.clip(theta_matrix, 0, 100)
    n_dim = len(DIMENSION_IDS)
    if theta_matrix.shape[0] < 2:
        R = np.eye(n_dim)
    else:
        R = np.corrcoef(theta_matrix.T)
    return R, theta_matrix


def get_efa_factor_scores(
    model: Any,
    data: np.ndarray,
    factor_for_dim: List[int],
    n_dimensions: int,
) -> np.ndarray:
    """
    Get factor scores (n_people x n_dimensions) in dimension order.
    model is fitted FactorAnalyzer or PCA with .transform(X).
    factor_for_dim[d] = original factor index assigned to dimension d.
    """
    if "factor_analyzer" in type(model).__module__:
        import factor_analyzer.factor_analyzer as _fa_mod
        _orig_check = _fa_mod.check_array
        def _patched_check(*args, force_all_finite=None, **kwargs):
            if force_all_finite is not None and "ensure_all_finite" not in kwargs:
                kwargs["ensure_all_finite"] = force_all_finite
            kwargs.pop("force_all_finite", None)
            return _orig_check(*args, **kwargs)
        try:
            _fa_mod.check_array = _patched_check
            scores = model.transform(data)
        finally:
            _fa_mod.check_array = _orig_check
    else:
        scores = model.transform(data)
    n = data.shape[0]
    out = np.zeros((n, n_dimensions), dtype=float)
    for d in range(n_dimensions):
        f = factor_for_dim[d] if d < len(factor_for_dim) else -1
        if f >= 0 and f < scores.shape[1]:
            out[:, d] = scores[:, f]
    return out


def response_dataset_to_efa(
    response_df: Any,
    item_bank: List[Dict[str, Any]],
) -> Tuple[np.ndarray, List[int], List[str]]:
    """
    Extract (data, dim_index_per_item, item_ids) from an individual-level response DataFrame
    for EFA. response_df has columns: respondent_id, employee_id, team_id, and one per item (item_id).
    Returns (n_individuals x n_items matrix, dimension index per item, list of item_id column names).
    """
    import pandas as pd
    bank_ids = {it["item_id"] for it in item_bank}
    item_cols = [c for c in response_df.columns if c in bank_ids]
    if not item_cols:
        raise ValueError("No item columns found in response dataset (column names must match item_id in bank).")
    data = np.asarray(response_df[item_cols], dtype=float)
    by_id = {it["item_id"]: dimension_index(it["dimension_id"]) for it in item_bank}
    dim_index_per_item = [by_id[c] for c in item_cols]
    return data, dim_index_per_item, item_cols


def run_efa(
    data: np.ndarray,
    n_factors: int,
    rotation: str = "promax",
) -> Tuple[np.ndarray, Optional[np.ndarray], Any]:
    """
    Run EFA on response data. Returns (loadings, factor_corr, model).
    factor_corr is None if rotation is orthogonal.
    """
    try:
        from factor_analyzer import FactorAnalyzer
    except ImportError:
        # Fallback: PCA as loading approximation (factors uncorrelated)
        from sklearn.decomposition import PCA
        pca = PCA(n_components=min(n_factors, data.shape[1], data.shape[0] - 1))
        loadings = pca.fit_transform(data.T).T  # (n_components, n_items) -> we want (n_items, n_factors)
        loadings = loadings.T  # (n_items, n_components)
        if loadings.shape[1] < n_factors:
            pad = np.zeros((loadings.shape[0], n_factors - loadings.shape[1]))
            loadings = np.hstack([loadings, pad])
        return loadings, None, pca

    fa = FactorAnalyzer(n_factors=n_factors, rotation=rotation)
    # factor_analyzer imports check_array and uses force_all_finite=; sklearn 1.5+ uses ensure_all_finite=
    # Patch the reference inside factor_analyzer's module so fa.fit() uses our wrapper
    import factor_analyzer.factor_analyzer as _fa_module
    _orig_check = _fa_module.check_array
    def _patched_check(*args, force_all_finite=None, **kwargs):
        if force_all_finite is not None and "ensure_all_finite" not in kwargs:
            kwargs["ensure_all_finite"] = force_all_finite
        kwargs.pop("force_all_finite", None)
        return _orig_check(*args, **kwargs)
    try:
        _fa_module.check_array = _patched_check
        fa.fit(data)
    finally:
        _fa_module.check_array = _orig_check
    loadings = fa.loadings_  # (n_items, n_factors)
    factor_corr = getattr(fa, "phi_", None)  # (n_factors, n_factors) for promax
    return loadings, factor_corr, fa


def reorder_factors_to_dimensions(
    loadings: np.ndarray,
    dim_index_per_item: List[int],
    n_dimensions: int,
    factor_corr: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Optional[np.ndarray], List[int]]:
    """
    Reorder loadings so column j = factor that best represents dimension j.
    Returns (loadings_reordered, factor_corr_reordered, factor_for_dim).
    factor_for_dim[d] = original factor index that was assigned to dimension d.
    """
    n_items, n_factors = loadings.shape
    score = np.zeros((n_factors, n_dimensions))
    for d in range(n_dimensions):
        rows = [i for i in range(n_items) if dim_index_per_item[i] == d]
        if rows:
            for f in range(n_factors):
                score[f, d] = np.mean(np.abs(loadings[rows, f]))
    factor_for_dim: List[int] = [-1] * n_dimensions
    used_f = set()
    for _ in range(n_dimensions):
        best_f, best_d, best_s = -1, -1, -1.0
        for f in range(n_factors):
            if f in used_f:
                continue
            for d in range(n_dimensions):
                if factor_for_dim[d] >= 0:
                    continue
                if score[f, d] > best_s:
                    best_s = score[f, d]
                    best_f, best_d = f, d
        if best_f >= 0 and best_d >= 0:
            factor_for_dim[best_d] = best_f
            used_f.add(best_f)
    reordered = np.zeros((n_items, n_factors))
    for d in range(n_dimensions):
        f = factor_for_dim[d]
        if f >= 0:
            reordered[:, d] = loadings[:, f]
    unused = [f for f in range(n_factors) if f not in used_f]
    for i, f in enumerate(unused):
        if n_dimensions + i < n_factors:
            reordered[:, n_dimensions + i] = loadings[:, f]

    corr_reordered = None
    if factor_corr is not None and factor_corr.shape[0] >= n_dimensions:
        # Reorder factor_corr rows and columns by factor_for_dim (dimension order)
        idx = [factor_for_dim[d] for d in range(n_dimensions) if factor_for_dim[d] >= 0]
        if len(idx) == n_dimensions:
            corr_reordered = factor_corr[np.ix_(idx, idx)]

    return reordered, corr_reordered, factor_for_dim
