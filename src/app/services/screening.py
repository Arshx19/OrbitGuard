"""
Conjunction screening for ORBITGUARD AI.

Finds close approaches between tracks over a time window and reports each one
with a refined time of closest approach, miss distance, and the full state
vectors the risk engine needs.

The method is the standard filter-then-refine pipeline:

  1. **Coarse propagation.** Every track is sampled on a uniform time grid.
  2. **Proximity filter.** At each sampled instant, a KD-tree over every
     track's position that instant finds the pairs that are actually near
     each other right then. A pair that is never near each other at any
     sampled instant cannot conjunct, and is discarded before any per-pair
     work.
  3. **Local minima.** For each pair the filter did flag, the sampled
     instants it was flagged at are grouped into separate encounters (two
     objects on crossing orbits meet at both nodes, so one pair can have two
     encounters in a day), and the closest sample within each becomes a
     starting guess for refinement.
  4. **Refinement.** Each starting guess is refined by bounded scalar
     minimisation of the exact separation, to sub-millisecond precision.

Step 4 is not optional. At a relative speed of 12 km/s, two samples 30 seconds
apart are 360 km apart along the relative track, so the smallest sampled
distance can overstate the true miss by hundreds of kilometres. Reporting the
sampled minimum -- as `app.core.conjunction.ConjunctionDetector` currently does
-- makes every downstream number an artefact of the step size. This module is
the replacement for that path; the older detector is left in place for its
owner to retire.

Step 2 used to be a 1-D radial-band check (do the two orbits' altitude ranges
ever overlap?) followed by computing the *full* sampled separation curve for
every pair that passed. That is correct, but it does not discriminate well --
two objects at the same altitude pass the band check regardless of how far
apart their orbital planes are, so most pairs in a real catalog survived it --
and computing a full separation curve per survivor is O(pairs x samples). On a
~2,000-object debris cloud that is millions of pairs times thousands of
samples: it did not finish in a reasonable time. The KD-tree check is exact
per instant (no plane is special-cased away) and turns the same test into
O(samples x n log n), which is why it both filters harder and runs faster.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial import cKDTree

from app.services.tracks import TimeGrid, Track, from_jd

logger = logging.getLogger(__name__)

# The fastest relative speed two Earth-orbiting objects can plausibly have is a
# little over 15 km/s (head-on, in high LEO). It bounds how far apart two
# samples of a close pass can be, and so how generous the proximity filter and
# the refinement bracket around each starting guess must be.
_MAX_RELATIVE_SPEED_KMS = 16.0

# Samples flagged by the proximity filter that are this many grid steps apart
# or fewer are treated as the same encounter; a bigger gap means a separate
# one (e.g. the other node of a crossing pair, half an orbit away).
_ENCOUNTER_GAP_SAMPLES = 2


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


def _find_proximate_pairs(
    positions: np.ndarray, coarse_km: float
) -> Dict[Tuple[int, int], List[int]]:
    """
    For every sampled instant, find the track pairs within `coarse_km` of each
    other right then, using a KD-tree over that instant's positions.

    Returns:
        Map from (i, j), i < j, to the sorted list of sample indices at which
        that pair was within range. A pair absent from the map was never
        close enough at any sampled instant.
    """
    n_tracks, n_steps, _ = positions.shape
    valid = np.isfinite(positions).all(axis=2)  # (n_tracks, n_steps)

    hits: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for t in range(n_steps):
        idx = np.nonzero(valid[:, t])[0]
        if len(idx) < 2:
            continue
        tree = cKDTree(positions[idx, t, :])
        for a, b in tree.query_pairs(r=coarse_km, output_type="ndarray"):
            i, j = int(idx[a]), int(idx[b])
            hits[(i, j) if i < j else (j, i)].append(t)
    return hits


def _encounters(sample_indices: List[int], gap: int = _ENCOUNTER_GAP_SAMPLES) -> List[List[int]]:
    """Split a pair's flagged samples into separate encounters by time gap."""
    ordered = sorted(sample_indices)
    groups: List[List[int]] = [[ordered[0]]]
    for t in ordered[1:]:
        if t - groups[-1][-1] <= gap:
            groups[-1].append(t)
        else:
            groups.append([t])
    return groups


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

    coarse_km = report_km + _MAX_RELATIVE_SPEED_KMS * step_s
    primary_ids = {t.object_id for t in primaries} if primaries else None

    pair_hits = _find_proximate_pairs(positions, coarse_km)
    total_pairs = len(tracks) * (len(tracks) - 1) // 2
    logger.info(
        "Screening %d tracks over %.1f h at %.0f s: %d of %d pairs come within "
        "%.0f km of each other at some sampled instant.",
        len(tracks), duration_hours, step_s, len(pair_hits), total_pairs, coarse_km,
    )

    approaches: List[CloseApproach] = []
    for (i, j), sample_indices in pair_hits.items():
        a, b = tracks[i], tracks[j]
        if primary_ids is not None and a.object_id not in primary_ids and b.object_id not in primary_ids:
            continue
        if a.body_key is not None and a.body_key == b.body_key:
            continue  # modules of one physical body

        for encounter in _encounters(sample_indices):
            k = min(encounter, key=lambda t: float(np.linalg.norm(positions[i, t] - positions[j, t])))
            offset, miss = refine_tca(a, b, grid, k, step_s)
            if miss > report_km:
                continue

            tca_jd, tca_fr = grid.at(offset)
            primary, secondary = (b, a) if (b.maneuverable and not a.maneuverable) else (a, b)
            rp, vp = primary.state(tca_jd, tca_fr)
            rs, vs = secondary.state(tca_jd, tca_fr)
            approaches.append(
                CloseApproach(
                    primary=primary, secondary=secondary, tca_jd=tca_jd, tca_fr=tca_fr,
                    miss_distance_km=miss,
                    primary_position_km=rp, primary_velocity_kms=vp,
                    secondary_position_km=rs, secondary_velocity_kms=vs,
                    coarse_distance_km=float(np.linalg.norm(positions[i, k] - positions[j, k])),
                )
            )

    approaches.sort(key=lambda c: c.miss_distance_km)
    logger.info("Screening found %d close approaches within %.1f km.", len(approaches), report_km)
    return approaches
