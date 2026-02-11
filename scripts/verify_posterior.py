"""
Verify posterior computation: load item_responses.csv and item_bank, run IRT scoring + conjugate update,
print data_mean, data_se, post_mean, post_sd per dimension. Use to check if dashboard should show a visible shift.
Run from repo root: python scripts/verify_posterior.py
"""
import json
import sys
from pathlib import Path

# Repo root = parent of scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.items import irt_scores_from_response_dataset
from src.dimensions import DIMENSION_IDS

# Paths: dashboard_input in repo, responses from Downloads (or override)
BANK_PATH = ROOT / "dashboard_input" / "item_bank.json"
CSV_PATH = Path(r"c:\Users\jenic\Downloads\simulation_datasets(1)\item_responses.csv")

if not CSV_PATH.exists():
    print(f"CSV not found: {CSV_PATH}")
    print("Set CSV_PATH in the script to your item_responses.csv path.")
    sys.exit(1)
if not BANK_PATH.exists():
    print(f"Item bank not found: {BANK_PATH}")
    sys.exit(1)

df = pd.read_csv(CSV_PATH)
with open(BANK_PATH, encoding="utf-8") as f:
    bank = json.load(f)

print("Computing IRT scores (800 x 15)...")
theta_hat = irt_scores_from_response_dataset(df, bank)
n = theta_hat.shape[0]
print(f"Got theta_hat shape {theta_hat.shape}")

prior_prec = 1.0 / (15.0 ** 2)
print("\nDimension               data_mean   data_se   post_mean   post_sd")
print("-" * 65)
for d in range(15):
    data_mean = float(np.mean(theta_hat[:, d]))
    data_std = float(np.std(theta_hat[:, d]))
    data_se = max(data_std / (n ** 0.5), 1e-6)
    data_prec = 1.0 / (data_se ** 2)
    post_prec = prior_prec + data_prec
    post_mean = (prior_prec * 50.0 + data_prec * data_mean) / post_prec
    post_sd = 1.0 / (post_prec ** 0.5)
    print(f"{DIMENSION_IDS[d]:22s}  {data_mean:9.2f}  {data_se:8.3f}  {post_mean:9.2f}  {post_sd:8.3f}")

print("\nIf post_mean is far from 50 and post_sd < 15, the dashboard should show a visible posterior shift.")
print("If post_mean ~ 50 and post_sd ~ 15, the data are not shifting the prior much (or processing issue).")
