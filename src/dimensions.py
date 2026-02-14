"""
15 culture dimensions in 5 domains for latent score generation.
"""
from __future__ import annotations

from typing import List, Tuple

# Domain name -> (dimension_id, dimension_name)
DOMAINS: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("Positive Momentum", [
        ("zuversicht", "Zuversicht"),
        ("richtung", "Richtung"),
        ("energie", "Energie"),
    ]),
    ("Human Connection", [
        ("authentische_verbundenheit", "Authentische Verbundenheit"),
        ("vertrauensvolle_zusammenarbeit", "Vertrauensvolle Zusammenarbeit"),
        ("teamspirit", "Teamspirit"),
    ]),
    ("Positive Leadership", [
        ("entwicklung", "Entwicklung"),
        ("inspiration", "Inspiration"),
        ("anerkennung", "Anerkennung"),
    ]),
    ("Growth Mindset", [
        ("neugier", "Neugier"),
        ("good_fightclub", "Good Fightclub"),
        ("grit", "Grit"),
    ]),
    ("Business Traction", [
        ("ownership", "Ownership"),
        ("fokus", "Fokus"),
        ("konsequenz", "Konsequenz"),
    ]),
]

DIMENSION_IDS: List[str] = []
DIMENSION_NAMES: List[str] = []
for _domain, dims in DOMAINS:
    for dim_id, dim_name in dims:
        DIMENSION_IDS.append(dim_id)
        DIMENSION_NAMES.append(dim_name)

N_DIMENSIONS = len(DIMENSION_IDS)

# Short labels for the 5 super-dimensions (used in dashboard)
SUPER_SHORT_LABELS = ["Momentum", "Connection", "Leadership", "Growth", "Traction"]

# Descriptions for hover and click (5 super, then 15 sub in DOMAINS order)
SUPER_DESCRIPTIONS = [
    "**Positive Momentum** — The organization’s sense of direction, confidence and energy. "
    "High scores indicate clarity of purpose, optimism and sustained drive.",
    "**Human Connection** — Quality of relationships, trust and psychological safety. "
    "High scores suggest strong collaboration, authenticity and a sense of belonging.",
    "**Positive Leadership** — How leaders enable development, inspire and recognise people. "
    "High scores point to supportive, visible and appreciative leadership.",
    "**Growth Mindset** — Openness to learning, constructive conflict and perseverance. "
    "High scores reflect curiosity, resilience and a culture of continuous improvement.",
    "**Business Traction** — Ownership, focus and follow-through on outcomes. "
    "High scores indicate clear accountability, prioritisation and execution.",
]

SUB_DESCRIPTIONS = [
    "**Zuversicht** — Confidence and optimism that the team and organisation can succeed.",
    "**Richtung** — Clarity of direction and alignment on where the organisation is heading.",
    "**Energie** — Level of energy and drive that people bring to their work.",
    "**Authentische Verbundenheit** — Genuine connection and psychological safety among people.",
    "**Vertrauensvolle Zusammenarbeit** — Trust-based collaboration and reliable cooperation.",
    "**Teamspirit** — Sense of belonging, mutual support and shared identity in the team.",
    "**Entwicklung** — Support for personal and professional development and growth.",
    "**Inspiration** — Leaders and environment that inspire and motivate people.",
    "**Anerkennung** — Recognition and appreciation of contributions and achievements.",
    "**Neugier** — Curiosity, openness to new ideas and willingness to experiment.",
    "**Good Fightclub** — Constructive debate and productive conflict that improve decisions.",
    "**Grit** — Perseverance, resilience and commitment to long-term goals.",
    "**Ownership** — Sense of ownership and responsibility for outcomes.",
    "**Fokus** — Ability to focus on priorities and avoid distraction.",
    "**Konsequenz** — Consistency and follow-through in execution and decisions.",
]


def get_super_description(index: int) -> str:
    """Return description for super-dimension 0–4."""
    if 0 <= index < len(SUPER_DESCRIPTIONS):
        return SUPER_DESCRIPTIONS[index]
    return ""


def get_sub_description(index: int) -> str:
    """Return description for sub-dimension 0–14 (same order as DIMENSION_IDS)."""
    if 0 <= index < len(SUB_DESCRIPTIONS):
        return SUB_DESCRIPTIONS[index]
    return ""


def dimension_index(dim_id: str) -> int:
    return DIMENSION_IDS.index(dim_id)
