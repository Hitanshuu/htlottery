"""Deterministic, seeded pick generation from a fitted model's distribution.

We sample (not argmax) from the selected model's distribution over the 120
sets, seeded deterministically by target_draw_id so the pick is reproducible
and auditable. Sampling rather than argmax avoids implying false authority
when UniformBaseline is selected (the expected, honest outcome): argmax of
a near-uniform distribution would just be an arbitrary-looking "set #1".
"""
import datetime as dt
import logging
import random

logger = logging.getLogger(__name__)


def _seed_from_draw_id(draw_id: str) -> int:
    return int(draw_id)


def generate_pick(model, target_draw_id: str, target_date: dt.date) -> dict:
    """Sample one Any-6-eligible pick from model's distribution, seeded by target_draw_id."""
    dist = model.predict_dist(target_date)
    rng = random.Random(_seed_from_draw_id(target_draw_id))

    sets = list(dist.keys())
    weights = list(dist.values())
    chosen = rng.choices(sets, weights=weights, k=1)[0]

    digits = list(chosen)
    assert len(set(digits)) == 3, f"sampled set {chosen} is not Any-6 eligible (3 distinct digits)"

    display_order = list(digits)
    rng.shuffle(display_order)

    sorted_digits = tuple(sorted(digits))
    return {
        "d1": display_order[0],
        "d2": display_order[1],
        "d3": display_order[2],
        "predicted_combo": "-".join(str(d) for d in display_order),
        "predicted_digits_sorted": "-".join(str(d) for d in sorted_digits),
    }
