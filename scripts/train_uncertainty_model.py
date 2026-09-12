"""
Train the learned TLE position-uncertainty model.

Measures how far standard element sets drift from operator-ephemeris truth,
fits error growth per regime, validates it on held-out satellites, and writes
models/tle_uncertainty.json -- which the server then uses in place of the
assumed model.

    .venv/Scripts/python.exe scripts/train_uncertainty_model.py            # cached data
    .venv/Scripts/python.exe scripts/train_uncertainty_model.py --refresh  # fetch fresh

Downloads (about 4 MB, mostly Starlink) go to data/training/, which is not
committed. See app/core/uncertainty_learning.py for the method.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

from app.core.tle_source import CelesTrakClient  # noqa: E402
from app.core.uncertainty import LEARNED_MODEL_PATH, REGIME_MANEUVERING, REGIME_PASSIVE  # noqa: E402
from app.core.uncertainty_learning import (  # noqa: E402
    ErrorSamples,
    measure_errors,
    model_document,
    train_regime,
)

REGIMES = {
    REGIME_PASSIVE: {
        "constellations": ["oneweb", "planet"],
        "description": "Objects that do not maneuver between element-set updates. "
                       "Applied to debris, rocket bodies, and quiet satellites.",
    },
    REGIME_MANEUVERING: {
        "constellations": ["starlink"],
        "description": "Satellites that maneuver every few days, so their element "
                       "sets go stale quickly.",
    },
}

# Starlink supplies over ten thousand satellites. A seeded subset keeps
# cross-validation to a couple of minutes without changing the fitted curve
# materially; pass --max-objects 0 to use them all.
DEFAULT_MAX_OBJECTS = 3000


def subsample_objects(samples: ErrorSamples, max_objects: int, seed: int = 11) -> ErrorSamples:
    objects = np.unique(samples.object_id)
    if max_objects <= 0 or len(objects) <= max_objects:
        return samples
    keep = set(np.random.default_rng(seed).choice(objects, size=max_objects, replace=False))
    return samples.subset(np.array([o in keep for o in samples.object_id]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch fresh data from CelesTrak.")
    parser.add_argument("--max-objects", type=int, default=DEFAULT_MAX_OBJECTS,
                        help="Cap satellites per regime (0 = no cap).")
    parser.add_argument("--output", default=os.path.abspath(LEARNED_MODEL_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    client = CelesTrakClient(cache_dir=os.path.join(REPO, "data", "training"))

    results = {}
    for regime, spec in REGIMES.items():
        parts = []
        for name in spec["constellations"]:
            # Training data never expires on its own: the standard and truth sets
            # must come from the same moment, so both are refreshed together or
            # not at all. The network is used only when nothing is cached.
            standard = client.fetch_group(name, allow_network=True,
                                          force_refresh=args.refresh, max_cache_age_hours=1e9)
            truth = client.fetch_group(f"sup-{name}", allow_network=True,
                                       force_refresh=args.refresh, max_cache_age_hours=1e9)
            parts.append(measure_errors(standard.objects, truth.objects, name))

        samples = subsample_objects(ErrorSamples.concatenate(parts), args.max_objects)
        started = time.perf_counter()
        results[regime] = train_regime(samples, spec["description"])
        logging.info("Trained %s in %.1f s.", regime, time.perf_counter() - started)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(model_document(results), handle, indent=2)
        handle.write("\n")

    print_report(results)
    print(f"\nWrote {args.output}")
    return 0


def print_report(results) -> None:
    axes = ("radial", "along_track", "cross_track")
    for regime, r in results.items():
        print("\n" + "=" * 78)
        print(f"{regime.upper()}  --  {r['source']}")
        print("=" * 78)
        sel = r["model_selection"]
        print("Model selection (held-out mean NLL, lower is better): "
              + ", ".join(f"{k} {v['held_out_mean_nll']:.4f} +/- {v['standard_error']:.4f}" for k, v in sel.items())
              + f"  ->  {r['growth_model']} (one-standard-error rule)")
        c = r["coefficients"]
        print(f"Fitted sigma(age) = a + b*age + c*age^2   (outlier fraction {r['outlier_fraction']:.1%})")
        for i, axis in enumerate(axes):
            print(f"  {axis:<12} a {c['epoch_km'][i]:8.4f} km   b {c['growth_km_per_day'][i]:8.4f} km/d"
                  f"   c {c['curvature_km_per_day2'][i]:8.4f} km/d^2")

        print("\nSigma, learned vs assumed (km):")
        for age, row in r["sigma_comparison_km"].items():
            print(f"  {age:<9} " + "   ".join(
                f"{axis[:5]} {row[axis]['learned']:7.3f} vs {row[axis]['assumed']:6.3f}" for axis in axes))

        cv = r["cross_validation"]
        print(f"\nHeld-out calibration ({cv['folds']}-fold, split by satellite)."
              "  Ideal: 68.3% / 95.4% / 99.7%")
        for label, key in (("learned", "coverage_learned"), ("assumed", "coverage_assumed")):
            print(f"  {label}")
            for axis in axes:
                cov = cv[key][axis]
                print(f"    {axis:<12} " + "  ".join(f"{k.replace('_sigma', ' sd')} {v:6.1%}" for k, v in cov.items()))


if __name__ == "__main__":
    raise SystemExit(main())
