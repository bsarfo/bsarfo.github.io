"""Historical flight-performance data in U.S. BTS On-Time Performance format.

Real data (use this for the final project):
  TranStats > Aviation > Airline On-Time Performance Data >
  "Reporting Carrier On-Time Performance (1987-present)"
  https://www.transtats.bts.gov/  (monthly zip files; one CSV per month)
  Put the CSVs in data/bts/ and call load_bts().

Synthetic data (so the pipeline runs anywhere, and for unit tests):
  generate_synthetic_bts() produces the same columns with realistic patterns
  (delays build up through the day, summer/December peaks, busier airports are
  worse, ~1.5% cancellations). It is a stand-in, not evidence: every result
  shown in class must be re-run on the real BTS files.
"""

from __future__ import annotations

import glob
import pathlib

import numpy as np
import pandas as pd

DATA_DIR = pathlib.Path(__file__).resolve().parents[1] / "data"

# Columns we use from the BTS file (names exactly as BTS publishes them)
BTS_COLUMNS = ["FlightDate", "Year", "Month", "DayofMonth", "DayOfWeek", "Reporting_Airline",
               "Origin", "Dest", "CRSDepTime", "CRSArrTime", "DepDelay", "ArrDelay", "ArrDel15",
               "Cancelled", "Diverted", "Distance"]


def load_bts(pattern: str | None = None) -> pd.DataFrame:
    """Load one or more monthly BTS CSVs (only the columns we need)."""
    pattern = pattern or str(DATA_DIR / "bts" / "*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No BTS files match {pattern}. See the module docstring for the download link.")
    frames = [pd.read_csv(f, usecols=lambda c: c in BTS_COLUMNS, low_memory=False) for f in files]
    return pd.concat(frames, ignore_index=True)


def generate_synthetic_bts(n: int = 250_000, seed: int = 7, n_airports: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    codes = [f"A{i:02d}" for i in range(n_airports)]
    weight = rng.pareto(1.2, n_airports) + 0.2          # a few big hubs, many small airports
    weight /= weight.sum()
    carriers = ["AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9"]
    carrier_effect = dict(zip(carriers, rng.normal(0, 0.25, len(carriers))))

    origin = rng.choice(codes, n, p=weight)
    dest = rng.choice(codes, n, p=weight)
    same = origin == dest
    dest[same] = rng.choice(codes, same.sum())
    carrier = rng.choice(carriers, n, p=[.18, .18, .16, .2, .07, .06, .08, .07])
    date = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 366, n), unit="D")
    dep_min = np.clip(rng.normal(13 * 60, 4.2 * 60, n), 5 * 60, 23 * 60 + 30).astype(int)
    distance = np.clip(rng.lognormal(6.5, 0.6, n), 80, 2800).round()
    block = (distance / 8 + 35 + rng.normal(0, 8, n)).astype(int)
    arr_min = (dep_min + block) % (24 * 60)

    vol = pd.Series(weight, index=codes)
    busy_o, busy_d = vol[origin].to_numpy() * n_airports, vol[dest].to_numpy() * n_airports
    month, dow = date.month.to_numpy(), date.dayofweek.to_numpy() + 1

    # log-odds that this flight is disrupted, and how badly
    z = (-1.55 + 0.11 * (dep_min / 60 - 13)                   # delays propagate through the day
         + np.isin(month, [6, 7, 8, 12]) * 0.35 + np.isin(month, [9, 10, 11]) * -0.25
         + np.isin(dow, [5, 7]) * 0.12
         + 0.18 * np.log1p(busy_o) + 0.10 * np.log1p(busy_d)
         + np.vectorize(carrier_effect.get)(carrier))
    disrupted = rng.random(n) < 1 / (1 + np.exp(-z))
    severity = rng.exponential(np.where(z > -1, 55, 38))
    dep_delay = np.where(disrupted, 15 + severity, rng.normal(-3, 7, n)).round()
    arr_delay = (dep_delay + rng.normal(-4, 9, n)).round()
    cancelled = rng.random(n) < 1 / (1 + np.exp(-(z - 2.6)))

    df = pd.DataFrame({
        "FlightDate": date.strftime("%Y-%m-%d"), "Year": date.year, "Month": month,
        "DayofMonth": date.day, "DayOfWeek": dow, "Reporting_Airline": carrier,
        "Origin": origin, "Dest": dest,
        "CRSDepTime": (dep_min // 60) * 100 + dep_min % 60, "CRSArrTime": (arr_min // 60) * 100 + arr_min % 60,
        "DepDelay": np.where(cancelled, np.nan, dep_delay), "ArrDelay": np.where(cancelled, np.nan, arr_delay),
        "Cancelled": cancelled.astype(float), "Diverted": 0.0, "Distance": distance,
    })
    df["ArrDel15"] = np.where(cancelled, np.nan, (df["ArrDelay"] >= 15).astype(float))
    return df


def get_history(prefer_real: bool = True) -> tuple[pd.DataFrame, str]:
    """Real BTS data if present in data/bts/, otherwise synthetic."""
    if prefer_real:
        try:
            return load_bts(), "BTS on-time performance (real)"
        except FileNotFoundError:
            pass
    return generate_synthetic_bts(), "synthetic BTS-format data (stand-in)"
