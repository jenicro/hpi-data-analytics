"""
Configuration for latent culture score generation (15 dimensions, hierarchy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .dimensions import N_DIMENSIONS


@dataclass
class LatentGenConfig:
    """Parameters for generating person-level (employee) true latents and point estimates with 95% intervals."""

    # Population mean (15-dim), scale 0–100. Use 50 so item model E[Y]=nu+lam*(theta-50) is balanced (no skew to 100 or 0).
    mu: List[float] = field(default_factory=lambda: [50.0] * N_DIMENSIONS)

    # Variance partition (proportions): measurement (within), individual (within-team), team, department, division. Must sum to 1.
    var_within: float = 0.20   # measurement error
    var_individual: float = 0.45  # person latent (within team)
    var_team: float = 0.18
    var_dept: float = 0.10
    var_division: float = 0.07

    # Total SD per dimension (on 0–100 scale) before partition
    sigma_total: float = 15.0

    # Correlation: within-domain and cross-domain (suggestion 0.6, 0.3)
    r_within_domain: float = 0.6
    r_cross_domain: float = 0.3

    # Measurement: SD of point estimate around true = base_measurement_sd / sqrt(n)
    base_measurement_sd: float = 8.0

    # Optional: full 15x15 correlation matrix override (if set, ignores r_within_domain / r_cross_domain)
    correlation_matrix: Optional[np.ndarray] = None


def get_suggested_latent_config() -> LatentGenConfig:
    """Literature-based defaults for organizational culture simulation."""
    return LatentGenConfig()
