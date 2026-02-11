"""
Simplified Bayesian IRT prior for the results dashboard.
Hierarchical Normal: org-level 5 superfactors, then 15 subfactors (3 per superfactor).
Conjugate structure so we can add data later and update in closed form.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np

from .dimensions import DOMAINS, DIMENSION_IDS, N_DIMENSIONS

# Prior hyperparameters (scale 0–100)
MU_ORG = 50.0
SIGMA_ORG = 15.0
SIGMA_WITHIN = 10.0


def sample_prior_org_sub(
    n_samples: int = 5000,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sample from the hierarchical prior: 5 superfactors at org level, 15 subfactors.
    theta_org[k] ~ Normal(MU_ORG, SIGMA_ORG)
    theta_sub[j] | theta_org[k] ~ Normal(theta_org[k], SIGMA_WITHIN) for j in domain k.
    Returns (theta_org, theta_sub) with shapes (n_samples, 5) and (n_samples, 15), clipped to [0, 100].
    """
    if rng is None:
        rng = np.random.default_rng()
    # Superfactors: (n_samples, 5)
    theta_org = rng.normal(MU_ORG, SIGMA_ORG, size=(n_samples, len(DOMAINS)))
    theta_org = np.clip(theta_org, 0, 100)
    # Subfactors: for each sample, for each domain k, draw 3 subfactors from N(theta_org[s,k], SIGMA_WITHIN)
    theta_sub = np.zeros((n_samples, N_DIMENSIONS), dtype=float)
    idx = 0
    for k, (_domain_name, dims) in enumerate(DOMAINS):
        n_dims = len(dims)
        theta_sub[:, idx : idx + n_dims] = (
            theta_org[:, k : k + 1]
            + rng.normal(0, SIGMA_WITHIN, size=(n_samples, n_dims))
        )
        idx += n_dims
    theta_sub = np.clip(theta_sub, 0, 100)
    return theta_org, theta_sub


def get_superfactor_names() -> list:
    """Return list of 5 superfactor (domain) names."""
    return [name for name, _ in DOMAINS]


def get_subfactor_names() -> list:
    """Return list of 15 subfactor (dimension) display names, in order."""
    from .dimensions import DIMENSION_NAMES
    return list(DIMENSION_NAMES)


def get_domain_for_dimension_index(d: int) -> int:
    """Return domain index (0..4) for subfactor index d (0..14)."""
    idx = 0
    for k, (_name, dims) in enumerate(DOMAINS):
        if d < idx + len(dims):
            return k
        idx += len(dims)
    return 0


def compute_posterior_org_sub(
    response_df: Any,
    item_bank: list,
    n_samples: int = 5000,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Conjugate normal update: use IRT score estimates per person per dimension as data,
    then posterior per dimension (independent normals), sample and aggregate to superfactors.
    Returns (theta_org_posterior, theta_sub_posterior) with shapes (n_samples, 5) and (n_samples, 15).
    """
    from .items import irt_scores_from_response_dataset
    if rng is None:
        rng = np.random.default_rng()
    theta_hat = irt_scores_from_response_dataset(response_df, item_bank)  # (n_people, 15)
    n_people = theta_hat.shape[0]
    prior_mean = MU_ORG
    prior_precision = 1.0 / (SIGMA_ORG ** 2)
    theta_sub_post = np.zeros((n_samples, N_DIMENSIONS), dtype=float)
    for d in range(N_DIMENSIONS):
        data_mean = float(np.mean(theta_hat[:, d]))
        data_std = float(np.std(theta_hat[:, d]))
        data_se = max(data_std / (n_people ** 0.5), 1e-6)
        data_precision = 1.0 / (data_se ** 2)
        post_precision = prior_precision + data_precision
        post_mean = (prior_precision * prior_mean + data_precision * data_mean) / post_precision
        post_sd = 1.0 / (post_precision ** 0.5)
        theta_sub_post[:, d] = rng.normal(post_mean, post_sd, size=n_samples)
    theta_sub_post = np.clip(theta_sub_post, 0, 100)
    theta_org_post = np.zeros((n_samples, len(DOMAINS)), dtype=float)
    idx = 0
    for k, (_name, dims) in enumerate(DOMAINS):
        n_dims = len(dims)
        theta_org_post[:, k] = np.mean(theta_sub_post[:, idx : idx + n_dims], axis=1)
        idx += n_dims
    theta_org_post = np.clip(theta_org_post, 0, 100)
    return theta_org_post, theta_sub_post
