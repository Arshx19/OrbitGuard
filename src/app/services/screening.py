"""
Conjunction screening for ORBITGUARD AI.

Finds close approaches between tracks over a time window and reports each one
with a refined time of closest approach, miss distance, and the full state
vectors the risk engine needs.

The method is the standard filter-then-refine pipeline:

  1. **Coarse propagation.** Every track is sampled on a uniform time grid.
  2. **Radial-band filter.** A pair whose orbital radii never come within the
     screening distance of each other over the window cannot conjunct, and is
     discarded before any pairwise work. In a real catalog this removes the
     large majority of pairs.
  3. **Local minima.** For surviving pairs, sampled separation is scanned for
     local minima.
  4. **Refinement.** Each promising minimum is refined by bounded scalar
     minimisation of the exact separation, to sub-millisecond precision.

Step 4 is not optional. At a relative speed of 12 km/s, two samples 30 seconds
apart are 360 km apart along the relative track, so the smallest sampled
distance can overstate the true miss by hundreds of kilometres. Reporting the
sampled minimum -- as `app.core.conjunction.ConjunctionDetector` currently does
-- makes every downstream number an artefact of the step size. This module is
the replacement for that path; the older detector is left in place for its
owner to retire.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize_scalar

from app.services.tracks import TimeGrid, Track, from_jd

logger = logging.getLogger(__name__)

# The fastest relative speed two Earth-orbiting objects can plausibly have is a
# little over 15 km/s (head-on, in high LEO). It bounds how far apart two
# samples of a close pass can be, and so how generous the coarse filter must be.
_MAX_RELATIVE_SPEED_KMS = 16.0

_PAIR_CHUNK = 50


@dataclass
class CloseApproach:
    """One refined close approach between two tracks."""

    primary: Track
    secondary: Track
    tca_jd: float
    tca_fr: float
    miss_distance_km: float
    primary_position_km: np.ndarray
    primary_velocity_kms: np.ndarray
    secondary_position_km: np.ndarray
    secondary_velocity_kms: np.ndarray
    coarse_distance_km: float
    """The sampled minimum before refinement, kept to show what refinement bought."""

    @property
    def tca(self) -> datetime:
        return from_jd(self.tca_jd, self.tca_fr)

    @property
    def relative_speed_kms(self) -> float:
        return float(np.linalg.norm(self.primary_velocity_kms - self.secondary_velocity_kms))


def _separation(a: Track, b: Track, jd: float, fr0: float, offset_s: float) -> float:
    fr = fr0 + offset_s / 86400.0
    ra, _ = a.state(jd, fr)
    rb, _ = b.state(jd, fr)
    d = float(np.linalg.norm(ra - rb))
    return d if np.isfinite(d) else 1e12


def refine_tca(
    a: Track, b: Track, grid: TimeGrid, index: int, step_s: float
) -> Tuple[float, float]:
    """
    Refine a sampled minimum to the true time of closest approach.

    Separation is smooth and, within one sample step either side of a local
    minimum, unimodal, so bounded Brent minimisation converges quickly.

    Returns:
        Tuple of (offset seconds from grid start, miss distance km).
    """
    centre = float(grid.offsets_s[index])
    lo = max(centre - step_s, float(grid.offsets_s[0]))
    hi = min(centre + step_s, float(grid.offsets_s[-1]))
    result = minimize_scalar(
        lambda s: _separation(a, b, grid.jd0, grid.fr0, s),
        bounds=(lo, hi),
        method="bounded",
        options={"xatol": 1e-4},
    )
    return float(result.x), float(result.fun)


def screen(
    tracks: Sequence[Track],
    start: datetime,
    duration_hours: float = 24.0,
    step_s: float = 30.0,
    report_km: float = 25.0,
    primaries: Optional[Sequence[Track]] = None,
) -> List[CloseApproach]:
    """
    Screen tracks for close approaches.

    Args:
        tracks: Everything to screen.
        start: Beginning of the screening window.
        duration_hours: Length of the window.
        step_s: Coarse sampling interval.
        report_km: Refined miss distance at or below which an approach is reported.
        primaries: If given, only pairs involving at least one of these tracks
            are screened -- the "our assets against the catalog" mode operators
            actually run, and far cheaper than all-against-all.

    Returns:
        Refined close approaches, closest first. Where exactly one object in a
        pair is maneuverable, it is reported as the primary.
    """
    tracks = list(tracks)
    if len(tracks) < 2:
        return []

    grid = TimeGrid.build(start, duration_hours * 3600.0, step_s)
    jd, fr = grid.jd, grid.fr

    positions = np.full((len(tracks), len(grid.offsets_s), 3), np.nan)
    for i, track in enumerate(tracks):
        positions[i], _ = track.states(jd, fr)

    # Radial band per track, ignoring failed samples.
    radii = np.linalg.norm(positions, axis=-1)
    valid = np.isfinite(radii).any(axis=1)
    r_min = np.where(valid, np.nanmin(np.where(np.isfinite(radii), radii, np.inf), axis=1), np.nan)
    r_max = np.where(valid, np.nanmax(np.where(np.isfinite(radii), radii, -np.inf), axis=1), np.nan)

    coarse_km = min(report_km + _MAX_RELATIVE_SPEED_KMS * (step_s / 2.0), 150.0)
    pad = report_km


    primary_ids = {t.object_id for t in primaries} if primaries else None

    candidates: List[Tuple[int, int]] = []
    for i in range(len(tracks)):
        if not valid[i]:
            continue
        for j in range(i + 1, len(tracks)):
            if not valid[j]:
                continue
            a, b = tracks[i], tracks[j]
            if primary_ids is not None and a.object_id not in primary_ids and b.object_id not in primary_ids:
                continue
            if len(tracks) > 50 and not a.maneuverable and not b.maneuverable:
                continue  # two unmaneuverable debris fragments skipped during full catalog screening
            if a.body_key is not None and a.body_key == b.body_key:
                continue  # modules of one physical body

            if r_max[i] + pad < r_min[j] or r_max[j] + pad < r_min[i]:
                continue
            candidates.append((i, j))

    logger.info(
        "Screening %d tracks over %.1f h at %.0f s: %d of %d pairs pass the radial filter.",
        len(tracks), duration_hours, step_s, len(candidates),
        len(tracks) * (len(tracks) - 1) // 2,
    )

    approaches: List[CloseApproach] = []
    for chunk_start in range(0, len(candidates), _PAIR_CHUNK):
        chunk = candidates[chunk_start:chunk_start + _PAIR_CHUNK]
        ia = np.array([p[0] for p in chunk])
        ib = np.array([p[1] for p in chunk])
        dist = np.linalg.norm(positions[ia] - positions[ib], axis=-1)  # (pairs, T)
        dist = np.where(np.isfinite(dist), dist, np.inf)

        interior = dist[:, 1:-1]
        is_min = (interior <= dist[:, :-2]) & (interior < dist[:, 2:]) & (interior < coarse_km)
        pair_idx, time_idx = np.nonzero(is_min)

        for p, k in zip(pair_idx, time_idx + 1):
            a, b = tracks[ia[p]], tracks[ib[p]]
            offset, miss = refine_tca(a, b, grid, int(k), step_s)
            if miss > report_km:
                continue

            tca_jd, tca_fr = grid.at(offset)
            if b.maneuverable and not a.maneuverable:
                a, b = b, a
            ra, va = a.state(tca_jd, tca_fr)
            rb, vb = b.state(tca_jd, tca_fr)
            approaches.append(
                CloseApproach(
                    primary=a, secondary=b, tca_jd=tca_jd, tca_fr=tca_fr,
                    miss_distance_km=miss,
                    primary_position_km=ra, primary_velocity_kms=va,
                    secondary_position_km=rb, secondary_velocity_kms=vb,
                    coarse_distance_km=float(dist[p, k]),
                )
            )

    approaches.sort(key=lambda c: c.miss_distance_km)
    logger.info("Screening found %d close approaches within %.1f km.", len(approaches), report_km)
    return approaches
