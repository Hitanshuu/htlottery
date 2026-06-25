"""Walk-forward validation and honest model selection.

Log-loss is computed only over draws whose actual pattern is ABC (all
distinct digits) -- the only outcomes inside the Any-6 / 120-set model
space. Non-distinct draws (AAA/AAB) fall outside that space by
definition and always result in a loss for Any-6 play; they are excluded
from log-loss scoring but still counted correctly by the win/loss tracker.
"""
import logging
import math
from typing import Type

import numpy as np

from src import config, models

logger = logging.getLogger(__name__)

MIN_TRAIN_SIZE = config.ML_LAG_DRAWS + 2

CANDIDATE_MODEL_CLASSES: dict[str, Type] = {
    "UniformBaseline": models.UniformBaseline,
    "PerPositionFrequency": models.PerPositionFrequency,
    "MarkovOrder1": models.MarkovOrder1,
    "MarkovOrder2": models.MarkovOrder2,
    "MLClassifier": models.MLClassifier,
}

_EPSILON = 1e-12


def walk_forward_scores(history: list[dict], model_class: Type, min_train_size: int = MIN_TRAIN_SIZE) -> dict:
    """Expanding-window walk-forward validation for one model class.

    Returns per-draw log-loss and top-1 hit indicators, scored only on
    ABC-pattern test draws.
    """
    logloss_per_draw = []
    hit_per_draw = []
    for i in range(min_train_size, len(history)):
        test_row = history[i]
        if test_row["pattern"] != "ABC":
            continue
        model = model_class()
        model.fit(history[:i])
        dist = model.predict_dist(test_row["draw_date"])
        actual_set = tuple(sorted((test_row["d1"], test_row["d2"], test_row["d3"])))
        prob = max(dist.get(actual_set, 0.0), _EPSILON)
        logloss_per_draw.append(-math.log(prob))
        best_set = max(dist, key=dist.get)
        hit_per_draw.append(best_set == actual_set)
    return {
        "logloss_per_draw": logloss_per_draw,
        "hit_per_draw": hit_per_draw,
        "n_scored": len(logloss_per_draw),
    }


def compare_models(history: list[dict], min_train_size: int = MIN_TRAIN_SIZE) -> dict:
    """Run walk-forward validation for every candidate model and summarize."""
    table = {}
    for name, model_class in CANDIDATE_MODEL_CLASSES.items():
        result = walk_forward_scores(history, model_class, min_train_size=min_train_size)
        n = result["n_scored"]
        mean_logloss = sum(result["logloss_per_draw"]) / n if n else float("nan")
        hit_rate = sum(result["hit_per_draw"]) / n if n else float("nan")
        table[name] = {
            "mean_logloss": mean_logloss,
            "top1_hit_rate": hit_rate,
            "n_scored": n,
            "logloss_per_draw": result["logloss_per_draw"],
        }
        logger.info("%s: mean_logloss=%.4f top1_hit_rate=%.4f n_scored=%d", name, mean_logloss, hit_rate, n)
    return table


def select_model(history: list[dict], min_train_size: int = MIN_TRAIN_SIZE) -> tuple[str, dict, str]:
    """Select the best model only if it beats UniformBaseline by more than
    ~1 standard error of the per-draw log-loss difference. Otherwise (the
    honest, expected outcome) select UniformBaseline."""
    table = compare_models(history, min_train_size=min_train_size)
    baseline = table["UniformBaseline"]

    if baseline["n_scored"] < 2:
        return "UniformBaseline", table, "insufficient data to validate any candidate -- defaulting to chance"

    candidates = {
        name: stats for name, stats in table.items()
        if name != "UniformBaseline" and stats["n_scored"] == baseline["n_scored"] and stats["n_scored"] >= 2
    }
    if not candidates:
        return "UniformBaseline", table, "no candidate had enough scored draws -- defaulting to chance"

    best_name = min(candidates, key=lambda n: candidates[n]["mean_logloss"])
    best_stats = candidates[best_name]

    diffs = np.array(best_stats["logloss_per_draw"]) - np.array(baseline["logloss_per_draw"])
    n = len(diffs)
    improvement = -diffs.mean()  # positive means candidate is better than baseline
    standard_error = diffs.std(ddof=1) / math.sqrt(n) if n >= 2 else float("inf")

    if improvement > standard_error and standard_error > 0:
        return best_name, table, f"{best_name} beat UniformBaseline by {improvement:.4f} nats (> 1 SE = {standard_error:.4f})"
    return "UniformBaseline", table, "no candidate beat chance by more than 1 standard error -- defaulting to UniformBaseline"
