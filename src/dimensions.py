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


def dimension_index(dim_id: str) -> int:
    return DIMENSION_IDS.index(dim_id)
