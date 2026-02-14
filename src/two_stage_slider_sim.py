"""
Two-stage generative model for 0-100 slider survey data.

Stage 1 – True psychological judgment (measurement model):
  N persons, P items, K latent factors.
  F (N×K) = latent traits, Lambda (P×K) = item loadings.
  E_ij ~ Normal(0, noise_sd²). Z = F @ Lambda.T + E.
  X_star = 100 * plogis(base_shift + base_scale * Z)  [strictly (0, 100), no clipping].

Stage 2 – Slider reporting behavior (heaping / gravity model):
  y = X_star + Normal(leniency_mean, leniency_sd); clamp y to [0, 100].
  Attractors: Strong {0, 50, 100}, Mid {25, 75}, Tens {0,10,...,100}, Fives {5,15,...,95}.
  bump(y, a, s) = exp(-0.5 * ((y - a) / s)^2). Weighted mass → p_snap = min(1, alpha * mass).
  If snap: select attractor proportional to pull; set y to that value.
  With probability round_prob, round y to nearest integer. Clamp to [0, 100]. Return integers.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


def plogis(z: np.ndarray) -> np.ndarray:
    """Logistic CDF: 1 / (1 + exp(-z)). Bounded in (0, 1)."""
    z = np.clip(np.asarray(z, dtype=float), -500, 500)
    return 1.0 / (1.0 + np.exp(-z))


# ---------------------------------------------------------------------------
# Stage 1: True psychological judgment (measurement model)
# ---------------------------------------------------------------------------


def stage1_latent_utilities(
    F: np.ndarray,
    Lambda: np.ndarray,
    noise_sd: float,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Z = F @ Lambda.T + E.
    F: (N, K), Lambda: (P, K) -> Z: (N, P).
    E_ij ~ Normal(0, noise_sd^2).
    """
    if rng is None:
        rng = np.random.default_rng()
    N, K = F.shape
    P = Lambda.shape[0]
    E = rng.normal(0, noise_sd, size=(N, P))
    Z = F @ Lambda.T + E
    return Z


def stage1_bounded_intentions(
    Z: np.ndarray,
    base_shift: float,
    base_scale: float,
) -> np.ndarray:
    """
    X_star = 100 * plogis(base_shift + base_scale * Z).
    Strictly in (0, 100); no clipping.
    """
    return 100.0 * plogis(base_shift + base_scale * Z)


def stage1(
    F: np.ndarray,
    Lambda: np.ndarray,
    noise_sd: float,
    base_shift: float,
    base_scale: float,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Stage 1: True psychological judgment.
    Returns X_star (N x P), strictly in (0, 100).
    """
    Z = stage1_latent_utilities(F, Lambda, noise_sd, rng)
    return stage1_bounded_intentions(Z, base_shift, base_scale)


# ---------------------------------------------------------------------------
# Stage 2: Slider reporting behavior (heaping / gravity model)
# ---------------------------------------------------------------------------

STRONG_ATTRACTORS = np.array([0.0, 50.0, 100.0])
MID_ATTRACTORS = np.array([25.0, 75.0])
TENS_ATTRACTORS = np.array([0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
FIVES_ATTRACTORS = np.array([5.0, 15.0, 35.0, 45.0, 55.0, 65.0, 85.0, 95.0])


def bump(y: float, a: float, s: float) -> float:
    """Gaussian pull toward attractor a: exp(-0.5 * ((y - a) / s)^2)."""
    return float(np.exp(-0.5 * ((y - a) / max(s, 1e-9)) ** 2))


def _attraction_mass(
    y: float,
    s: float,
    w_strong: float,
    w_mid: float,
    w_10: float,
    w_5: float,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """Total attraction mass and per-attractor weights. Returns (total_mass, values, weights)."""
    weights = []
    values = []
    for a in STRONG_ATTRACTORS:
        b = bump(y, a, s)
        weights.append(w_strong * b)
        values.append(a)
    for a in MID_ATTRACTORS:
        b = bump(y, a, s)
        weights.append(w_mid * b)
        values.append(a)
    for a in TENS_ATTRACTORS:
        b = bump(y, a, s)
        weights.append(w_10 * b)
        values.append(a)
    for a in FIVES_ATTRACTORS:
        b = bump(y, a, s)
        weights.append(w_5 * b)
        values.append(a)
    values = np.array(values)
    weights = np.array(weights, dtype=float)
    total_mass = float(np.sum(weights))
    return total_mass, values, weights


def stage2_single_response(
    y: float,
    gravity_sd: float,
    w_strong: float,
    w_mid: float,
    w_10: float,
    w_5: float,
    alpha: float,
    round_prob: float,
    rng: np.random.Generator,
) -> int:
    """Apply heaping/gravity to one response. Returns integer in [0, 100]."""
    total_mass, values, weights = _attraction_mass(
        y, gravity_sd, w_strong, w_mid, w_10, w_5
    )
    p_snap = min(1.0, alpha * total_mass)
    if rng.random() < p_snap and np.sum(weights) > 0:
        probs = weights / np.sum(weights)
        idx = rng.choice(len(values), p=probs)
        y = values[idx]
    if rng.random() < round_prob:
        y = round(y)
    y = float(np.clip(y, 0, 100))
    return int(round(y))


def stage2(
    X_star: np.ndarray,
    leniency_mean: float,
    leniency_sd: float,
    gravity_sd: float,
    w_strong: float,
    w_mid: float,
    w_10: float,
    w_5: float,
    alpha: float,
    round_prob: float,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Stage 2: Leniency noise, then per-response attractor snap and rounding.
    Returns integer matrix X (N x P) in [0, 100].
    """
    if rng is None:
        rng = np.random.default_rng()
    y = X_star + rng.normal(leniency_mean, leniency_sd, size=X_star.shape)
    y = np.clip(y, 0, 100)
    N, P = y.shape
    X = np.zeros((N, P), dtype=np.int64)
    for i in range(N):
        for j in range(P):
            X[i, j] = stage2_single_response(
                float(y[i, j]),
                gravity_sd, w_strong, w_mid, w_10, w_5,
                alpha, round_prob, rng,
            )
    return X


def simulate_slider_survey(
    F: np.ndarray,
    Lambda: np.ndarray,
    noise_sd: float,
    base_shift: float,
    base_scale: float,
    leniency_mean: float = 0.0,
    leniency_sd: float = 2.0,
    gravity_sd: float = 8.0,
    w_strong: float = 1.0,
    w_mid: float = 0.6,
    w_10: float = 0.4,
    w_5: float = 0.2,
    alpha: float = 0.015,
    round_prob: float = 0.5,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Full two-stage simulation. Returns (X_star, X).
    X_star: true intentions in (0, 100). X: observed integers in [0, 100].
    """
    if rng is None:
        rng = np.random.default_rng()
    X_star = stage1(F, Lambda, noise_sd, base_shift, base_scale, rng)
    X = stage2(
        X_star, leniency_mean, leniency_sd, gravity_sd,
        w_strong, w_mid, w_10, w_5, alpha, round_prob, rng,
    )
    return X_star, X


if __name__ == "__main__":
    import numpy as np
    rng = np.random.default_rng(42)
    N, K, P = 100, 5, 30
    F = rng.normal(0, 1, (N, K))
    Lambda = rng.normal(0, 0.8, (P, K))
    X_star, X = simulate_slider_survey(
        F, Lambda, noise_sd=1.0, base_shift=0.0, base_scale=0.5, rng=rng
    )
    print("Stage 1 X_star: strictly (0, 100)", X_star.min(), X_star.max())
    print("Stage 2 X: integer [0, 100]", X.min(), X.max(), "dtype", X.dtype)
    print("Sample row:", X[0])


if __name__ == "__main__":
    import numpy as np
    rng = np.random.default_rng(42)
    N, K, P = 100, 5, 30
    F = rng.normal(0, 1, (N, K))
    Lambda = rng.normal(0, 0.8, (P, K))
    X_star, X = simulate_slider_survey(
        F, Lambda, noise_sd=1.0, base_shift=0.0, base_scale=0.5, rng=rng
    )
    print("Stage 1 X_star: strictly (0, 100)", X_star.min(), X_star.max())
    print("Stage 2 X: integer [0, 100]", X.min(), X.max(), "dtype", X.dtype)
    print("Sample row:", X[0])
