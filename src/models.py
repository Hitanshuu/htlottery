"""Candidate models predicting a distribution over the 120 Any-6 distinct-digit sets.

Every model shares the interface `.fit(history)` / `.predict_dist(target_date)`.
`history` is a chronologically-sorted list of dict-like rows with d1, d2, d3, draw_date.
`predict_dist` returns a dict mapping each of the 120 sorted 3-digit tuples to a
probability; the dict always sums to 1 and never assigns exactly zero (Laplace
smoothing guarantees this), so log-loss scoring is always well-defined.
"""
import datetime as dt
import itertools
import logging
import warnings
from collections import Counter
from typing import Optional

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)

ALL_SETS: list[tuple[int, int, int]] = sorted(itertools.combinations(range(10), 3))
_PERMS_FOR_SET = {s: list(itertools.permutations(s)) for s in ALL_SETS}
_UNIFORM_DIST = {s: 1.0 / len(ALL_SETS) for s in ALL_SETS}


def _smoothed_freq(counts: dict, alpha: float = 1.0) -> dict:
    """Laplace-smoothed P(digit) for digits 0-9 given a digit->count mapping."""
    total = sum(counts.values()) + alpha * 10
    return {d: (counts.get(d, 0) + alpha) / total for d in range(10)}


def _combine_positions_to_sets(p1: dict, p2: dict, p3: dict) -> dict:
    """Combine three independent per-position digit distributions into a
    distribution over the 120 distinct-digit sets, renormalized."""
    raw = {}
    for s in ALL_SETS:
        total = 0.0
        for perm in _PERMS_FOR_SET[s]:
            total += p1[perm[0]] * p2[perm[1]] * p3[perm[2]]
        raw[s] = total
    norm = sum(raw.values())
    if norm <= 0:
        return dict(_UNIFORM_DIST)
    return {s: v / norm for s, v in raw.items()}


class UniformBaseline:
    """1/120 for every set -- the ground truth to beat."""

    def fit(self, history: list[dict]) -> None:
        pass

    def predict_dist(self, target_date: Optional[dt.date] = None) -> dict:
        return dict(_UNIFORM_DIST)


class PerPositionFrequency:
    """Laplace-smoothed empirical per-position digit frequency, combined over the 120 sets."""

    def fit(self, history: list[dict]) -> None:
        self._counts = [Counter(), Counter(), Counter()]
        for row in history:
            self._counts[0][row["d1"]] += 1
            self._counts[1][row["d2"]] += 1
            self._counts[2][row["d3"]] += 1

    def predict_dist(self, target_date: Optional[dt.date] = None) -> dict:
        p1, p2, p3 = (_smoothed_freq(c) for c in self._counts)
        return _combine_positions_to_sets(p1, p2, p3)


class MarkovOrder1:
    """Per-position transition P(digit_t | digit_{t-1}), combined over the 120 sets."""

    def fit(self, history: list[dict]) -> None:
        self._transitions = [{}, {}, {}]
        for prev, curr in zip(history, history[1:]):
            for pos, key in enumerate(("d1", "d2", "d3")):
                bucket = self._transitions[pos].setdefault(prev[key], Counter())
                bucket[curr[key]] += 1
        self._last_digits = (history[-1]["d1"], history[-1]["d2"], history[-1]["d3"]) if history else None

    def predict_dist(self, target_date: Optional[dt.date] = None) -> dict:
        if self._last_digits is None:
            return dict(_UNIFORM_DIST)
        dists = []
        for pos in range(3):
            counts = self._transitions[pos].get(self._last_digits[pos], {})
            dists.append(_smoothed_freq(counts))
        return _combine_positions_to_sets(*dists)


class MarkovOrder2:
    """Per-position P(digit_t | digit_{t-1}, digit_{t-2}), combined over the 120 sets."""

    def fit(self, history: list[dict]) -> None:
        self._transitions = [{}, {}, {}]
        for prev2, prev1, curr in zip(history, history[1:], history[2:]):
            for pos, key in enumerate(("d1", "d2", "d3")):
                ctx = (prev2[key], prev1[key])
                bucket = self._transitions[pos].setdefault(ctx, Counter())
                bucket[curr[key]] += 1
        if len(history) >= 2:
            self._last2_digits = (
                (history[-2]["d1"], history[-2]["d2"], history[-2]["d3"]),
                (history[-1]["d1"], history[-1]["d2"], history[-1]["d3"]),
            )
        else:
            self._last2_digits = None

    def predict_dist(self, target_date: Optional[dt.date] = None) -> dict:
        if self._last2_digits is None:
            return dict(_UNIFORM_DIST)
        prev2_digits, prev1_digits = self._last2_digits
        dists = []
        for pos in range(3):
            ctx = (prev2_digits[pos], prev1_digits[pos])
            counts = self._transitions[pos].get(ctx, {})
            dists.append(_smoothed_freq(counts))
        return _combine_positions_to_sets(*dists)


class MLClassifier:
    """Per-position multiclass classifier on lagged digits + day-of-week.

    Falls back to uniform (never raises) when there isn't enough history to
    fit a meaningful classifier -- this is the honest, expected outcome on
    i.i.d. data.
    """

    def __init__(self, n_lags: int = 5):
        self.n_lags = n_lags
        self._fitted = False
        self._history: list[dict] = []
        self._classifiers: list[Optional[LogisticRegression]] = [None, None, None]

    def _features_for(self, window: list[dict], target_date: dt.date) -> list:
        features = []
        for row in window:
            features.extend([row["d1"], row["d2"], row["d3"]])
        features.append(target_date.weekday())
        return features

    def fit(self, history: list[dict]) -> None:
        self._history = list(history)
        self._fitted = False
        if len(history) <= self.n_lags:
            return

        X = []
        ys = [[], [], []]
        for i in range(self.n_lags, len(history)):
            window = history[i - self.n_lags : i]
            X.append(self._features_for(window, history[i]["draw_date"]))
            ys[0].append(history[i]["d1"])
            ys[1].append(history[i]["d2"])
            ys[2].append(history[i]["d3"])

        X = np.array(X)
        try:
            classifiers = []
            for pos in range(3):
                y = np.array(ys[pos])
                if len(set(y)) < 2:
                    raise ValueError("need at least 2 classes to fit a classifier")
                clf = LogisticRegression(max_iter=1000)
                with warnings.catch_warnings():
                    # On i.i.d. data there's no real signal to converge to;
                    # the classifier still fits (just poorly), which is the
                    # honest expected outcome -- not a correctness issue.
                    warnings.simplefilter("ignore", category=ConvergenceWarning)
                    clf.fit(X, y)
                classifiers.append(clf)
            self._classifiers = classifiers
            self._fitted = True
        except ValueError as exc:
            logger.info("MLClassifier: falling back to uniform, fit failed: %s", exc)
            self._fitted = False

    def predict_dist(self, target_date: Optional[dt.date] = None) -> dict:
        if not self._fitted or len(self._history) < self.n_lags or target_date is None:
            return dict(_UNIFORM_DIST)
        window = self._history[-self.n_lags :]
        features = np.array([self._features_for(window, target_date)])
        dists = []
        for pos in range(3):
            clf = self._classifiers[pos]
            proba = clf.predict_proba(features)[0]
            counts = {int(cls): float(p) * 1000 for cls, p in zip(clf.classes_, proba)}
            dists.append(_smoothed_freq(counts, alpha=0.01))
        return _combine_positions_to_sets(*dists)
