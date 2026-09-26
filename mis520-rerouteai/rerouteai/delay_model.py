"""Layer 2 - machine learning: predict the full arrival-delay distribution of a flight.

Rather than a single yes/no "late" label, the model predicts probabilities for
delay buckets (plus cancellation). From that distribution we can answer the
question the optimizer actually needs: "what is the chance this flight lands
late enough to break a connection with S minutes of slack?"

Features are deliberately *transferable* (time of day, month, weekday, distance,
airport busyness percentile) so a model trained on U.S. BTS history can be
applied, with a stated caveat, to the European scenario airports.
"""

from __future__ import annotations

import pathlib
import pickle
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

MODEL_PATH = pathlib.Path(__file__).resolve().parents[1] / "models" / "delay_model.pkl"

# upper edges of arrival-delay buckets (minutes); last class = cancelled
EDGES = [0, 15, 30, 45, 60, 90, 120, 180, 300]
LABELS = ["early/on time", "0-15", "15-30", "30-45", "45-60", "60-90", "90-120", "120-180", "180-300", "300+",
          "cancelled"]
CANCELLED = len(LABELS) - 1
FEATURES = ["month", "dow", "dep_hour", "distance", "origin_busy", "dest_busy"]


def bucketize(arr_delay: pd.Series, cancelled: pd.Series) -> np.ndarray:
    b = np.searchsorted(EDGES, arr_delay.fillna(0).to_numpy(), side="left")
    return np.where(cancelled.fillna(0).to_numpy() == 1, CANCELLED, b)


def busyness_percentile(df: pd.DataFrame) -> pd.Series:
    """Each airport's departures as a percentile rank among all airports."""
    return df["Origin"].value_counts().rank(pct=True)


def features(df: pd.DataFrame, busy: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "month": df["Month"].astype(int), "dow": df["DayOfWeek"].astype(int),
        "dep_hour": (df["CRSDepTime"] // 100).astype(int), "distance": df["Distance"].astype(float),
        "origin_busy": df["Origin"].map(busy).fillna(0.5), "dest_busy": df["Dest"].map(busy).fillna(0.5),
    })


@dataclass
class DelayModel:
    clf: HistGradientBoostingClassifier
    busy: pd.Series
    source: str

    def predict_buckets(self, X: pd.DataFrame) -> np.ndarray:
        p = np.zeros((len(X), len(LABELS)))
        p[:, self.clf.classes_] = self.clf.predict_proba(X[FEATURES])
        return p

    def predict_flight(self, month: int, dow: int, dep_hour: int, distance: float,
                       origin_busy: float, dest_busy: float) -> np.ndarray:
        X = pd.DataFrame([dict(month=month, dow=dow, dep_hour=dep_hour, distance=distance,
                               origin_busy=origin_busy, dest_busy=dest_busy)])
        return self.predict_buckets(X)[0]


def prob_delay_at_most(p: np.ndarray, minutes: float) -> float:
    """P(flight operates AND arrival delay <= minutes), interpolating inside buckets.
    Early arrivals are treated as 0 delay (conservative)."""
    if minutes < 0:
        return 0.0
    lows = [-np.inf] + EDGES
    highs = EDGES + [480]
    total = 0.0
    for i, (lo, hi) in enumerate(zip(lows, highs)):
        lo = 0 if lo == -np.inf else lo
        if i == 0:
            total += p[0]
        elif minutes >= hi:
            total += p[i]
        elif minutes > lo:
            total += p[i] * (minutes - lo) / (hi - lo)
    return float(min(total, 1 - p[CANCELLED]))


def expected_delay(p: np.ndarray) -> float:
    """Mean arrival delay in minutes given the flight operates (bucket midpoints)."""
    mids = np.array([0, 7.5, 22.5, 37.5, 52.5, 75, 105, 150, 240, 360])
    operate = p[:CANCELLED]
    return float((operate * mids).sum() / max(operate.sum(), 1e-9))


def train(df: pd.DataFrame, source: str) -> DelayModel:
    busy = busyness_percentile(df)
    y = bucketize(df["ArrDelay"], df["Cancelled"])
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=31,
                                         categorical_features=[0, 1], random_state=0)
    clf.fit(features(df, busy), y)
    return DelayModel(clf, busy, source)


def save(m: DelayModel, path: pathlib.Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(m, fh)


def load(path: pathlib.Path = MODEL_PATH) -> DelayModel:
    if path.exists():
        with open(path, "rb") as fh:
            return pickle.load(fh)
    from .bts import get_history
    df, source = get_history()
    m = train(df, source)
    save(m, path)
    return m
