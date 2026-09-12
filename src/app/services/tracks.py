"""
Object tracks for ORBITGUARD AI.

A track answers one question -- where is this object, and how fast is it moving,
at a given time? -- behind a single interface, whatever produces the answer.
Screening and maneuver planning work entirely in terms of tracks, so they never
need to know which kind of object they are handling.

Three kinds exist:

  * `TLETrack` -- a catalogued object propagated by SGP4 from its element set.
  * `TwoBodyTrack` -- an object defined by a single state vector and propagated
    under point-mass gravity. Used for the constructed demonstration scenario,
    whose secondary has no published element set.
  * `ManeuveredTrack` -- another track with an impulsive burn applied, its
    post-burn motion obtained from the Clohessy-Wiltshire equations.

Times are passed as split Julian dates (`jd`, `fr`), the convention SGP4 itself
uses. Keeping the whole and fractional parts separate preserves sub-millisecond
precision, which matters when objects close at kilometres per second.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import numpy as np
from scipy.integrate import solve_ivp
from sgp4.api import Satrec, jday

MU_EARTH_KM3_S2 = 398600.4418
_J2000_JD = 2451545.0
_J2000_UTC = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def to_jd(moment: datetime) -> Tuple[float, float]:
    """Convert a datetime to a split Julian date. Naive datetimes are taken as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return jday(
        moment.year, moment.month, moment.day,
        moment.hour, moment.minute,
        moment.second + moment.microsecond / 1e6,
    )


def from_jd(jd: float, fr: float) -> datetime:
    """Convert a split Julian date back to a timezone-aware UTC datetime."""
    return _J2000_UTC + timedelta(days=(jd - _J2000_JD) + fr)


def seconds_between(jd_a: float, fr_a: float, jd_b, fr_b):
    """Seconds from (jd_a, fr_a) to (jd_b, fr_b). Accepts arrays for the second time."""
    return ((jd_b - jd_a) + (fr_b - fr_a)) * 86400.0


@dataclass(frozen=True)
class TimeGrid:
    """A uniform sequence of times, anchored at a start instant."""

    jd0: float
    fr0: float
    offsets_s: np.ndarray

    @classmethod
    def build(cls, start: datetime, duration_s: float, step_s: float) -> "TimeGrid":
        jd0, fr0 = to_jd(start)
        count = int(math.floor(duration_s / step_s)) + 1
        return cls(jd0, fr0, np.arange(count, dtype=np.float64) * step_s)

    @property
    def jd(self) -> np.ndarray:
        return np.full(self.offsets_s.shape, self.jd0)

    @property
    def fr(self) -> np.ndarray:
        return self.fr0 + self.offsets_s / 86400.0

    def at(self, offset_s: float) -> Tuple[float, float]:
        return self.jd0, self.fr0 + offset_s / 86400.0


# ---------------------------------------------------------------------------
# Orbital frame
# ---------------------------------------------------------------------------


def rtn_basis(position_km: np.ndarray, velocity_kms: np.ndarray) -> np.ndarray:
    """
    Radial / along-track / cross-track unit vectors as the columns of a 3x3 matrix.

    Works on a single state, shape (3,), or a stack of states, shape (n, 3), in
    which case the result has shape (n, 3, 3).
    """
    r = np.asarray(position_km, dtype=np.float64)
    v = np.asarray(velocity_kms, dtype=np.float64)
    u_r = r / np.linalg.norm(r, axis=-1, keepdims=True)
    h = np.cross(r, v)
    u_n = h / np.linalg.norm(h, axis=-1, keepdims=True)
    u_t = np.cross(u_n, u_r)
    return np.stack([u_r, u_t, u_n], axis=-1)


# ---------------------------------------------------------------------------
# Tracks
# ---------------------------------------------------------------------------


@dataclass
class Track:
    """Base class. Subclasses implement `_propagate`."""

    object_id: str
    name: str
    object_type: str
    """Display category: 'Active Satellite', 'Debris', 'Rocket Body'."""

    object_class: str
    """Hard-body class understood by `app.core.uncertainty`."""

    maneuverable: bool = False
    body_key: Optional[str] = None
    """Objects sharing a body_key are one physical body (e.g. ISS modules)."""

    simulated: bool = False

    uncertainty_regime: Optional[str] = None
    """Learned error-growth regime for this object's ephemeris (see app.core.uncertainty)."""

    def _propagate(self, jd: np.ndarray, fr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def states(self, jd: np.ndarray, fr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Positions and velocities, shape (n, 3) each. Failed samples are NaN."""
        jd = np.atleast_1d(np.asarray(jd, dtype=np.float64))
        fr = np.atleast_1d(np.asarray(fr, dtype=np.float64))
        return self._propagate(jd, fr)

    def state(self, jd: float, fr: float) -> Tuple[np.ndarray, np.ndarray]:
        """Position and velocity at one time, shape (3,) each."""
        r, v = self.states(np.array([jd]), np.array([fr]))
        return r[0], v[0]

    def tle_age_days(self, jd: float, fr: float) -> float:
        """Propagation age of the underlying ephemeris. Zero if there is none."""
        return 0.0


@dataclass
class TLETrack(Track):
    """A catalogued object propagated by SGP4."""

    satrec: Satrec = field(default=None, repr=False)
    norad_id: int = 0

    def _propagate(self, jd, fr):
        errors, r, v = self.satrec.sgp4_array(jd, fr)
        r = np.asarray(r, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        bad = np.asarray(errors) != 0
        if bad.any():
            r[bad] = np.nan
            v[bad] = np.nan
        return r, v

    def tle_age_days(self, jd: float, fr: float) -> float:
        # jdsatepoch/jdsatepochF come straight from the element lines, so this
        # does not depend on TLEData.epoch (see app.core.tle_source).
        return abs((jd - self.satrec.jdsatepoch) + (fr - self.satrec.jdsatepochF))


@dataclass
class TwoBodyTrack(Track):
    """
    An object defined by one state vector, propagated under point-mass gravity.

    Point-mass motion ignores J2 and drag, which over the few hours a
    conjunction scenario spans is a negligible difference. This track exists
    for objects that have no element set, and its trajectory is *defined* by
    two-body motion, so there is no truth for it to deviate from.
    """

    epoch_jd: float = 0.0
    epoch_fr: float = 0.0
    position_km: np.ndarray = field(default=None, repr=False)
    velocity_kms: np.ndarray = field(default=None, repr=False)
    span_s: float = 3.0 * 86400.0

    def __post_init__(self):
        y0 = np.concatenate([self.position_km, self.velocity_kms]).astype(np.float64)

        def gravity(_t, y):
            r = y[:3]
            return np.concatenate([y[3:], -MU_EARTH_KM3_S2 * r / np.linalg.norm(r) ** 3])

        options = dict(method="DOP853", rtol=1e-11, atol=1e-9, dense_output=True)
        self._forward = solve_ivp(gravity, (0.0, self.span_s), y0, **options).sol
        self._backward = solve_ivp(gravity, (0.0, -self.span_s), y0, **options).sol

    def _propagate(self, jd, fr):
        t = seconds_between(self.epoch_jd, self.epoch_fr, jd, fr)
        out = np.full((t.size, 6), np.nan)
        ahead = (t >= 0) & (t <= self.span_s)
        behind = (t < 0) & (t >= -self.span_s)
        if ahead.any():
            out[ahead] = self._forward(t[ahead]).T
        if behind.any():
            out[behind] = self._backward(t[behind]).T
        return out[:, :3], out[:, 3:]


def clohessy_wiltshire(
    delta_v_rtn_kms: np.ndarray, mean_motion_rad_s: float, elapsed_s: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Relative motion after an impulsive burn, from the Clohessy-Wiltshire equations.

    Linearised motion about a circular reference orbit, starting from zero
    offset. Accurate for the small burns and time spans of collision avoidance.
    The secular along-track term, -3 * dv_T * t, is the one that matters most:
    raising the orbit lengthens the period, so the spacecraft falls steadily
    behind where it would otherwise have been.

    Args:
        delta_v_rtn_kms: Impulse in the RTN frame, km/s.
        mean_motion_rad_s: Mean motion of the reference orbit.
        elapsed_s: Time since the burn; entries before the burn yield zero.

    Returns:
        Tuple of (displacement km, velocity change km/s), each shape (n, 3) in RTN.
    """
    vr, vt, vn = np.asarray(delta_v_rtn_kms, dtype=np.float64)
    n = mean_motion_rad_s
    t = np.maximum(np.atleast_1d(np.asarray(elapsed_s, dtype=np.float64)), 0.0)
    s, c = np.sin(n * t), np.cos(n * t)

    x = (vr / n) * s + (2.0 * vt / n) * (1.0 - c)
    y = (2.0 * vr / n) * (c - 1.0) + (vt / n) * (4.0 * s - 3.0 * n * t)
    z = (vn / n) * s

    vx = vr * c + 2.0 * vt * s
    vy = -2.0 * vr * s + vt * (4.0 * c - 3.0)
    vz = vn * c

    started = (np.atleast_1d(elapsed_s) >= 0).astype(np.float64)[:, None]
    return np.stack([x, y, z], axis=-1) * started, np.stack([vx, vy, vz], axis=-1) * started


@dataclass
class ManeuveredTrack(Track):
    """A base track with an impulsive burn applied at `burn_jd`/`burn_fr`."""

    base: Track = field(default=None, repr=False)
    burn_jd: float = 0.0
    burn_fr: float = 0.0
    delta_v_rtn_kms: np.ndarray = field(default=None, repr=False)

    def __post_init__(self):
        r, v = self.base.state(self.burn_jd, self.burn_fr)
        radius = float(np.linalg.norm(r))
        self._mean_motion = math.sqrt(MU_EARTH_KM3_S2 / radius**3)

    def _propagate(self, jd, fr):
        r_base, v_base = self.base.states(jd, fr)
        elapsed = seconds_between(self.burn_jd, self.burn_fr, jd, fr)
        dr_rtn, dv_rtn = clohessy_wiltshire(self.delta_v_rtn_kms, self._mean_motion, elapsed)

        # CW velocities are relative to the rotating Hill frame. The inertial
        # velocity of the displaced point also carries the frame's rotation,
        # omega x dr, with omega = n along the orbit normal.
        n = self._mean_motion
        rotation = np.stack(
            [-n * dr_rtn[:, 1], n * dr_rtn[:, 0], np.zeros(len(dr_rtn))], axis=-1
        )

        basis = rtn_basis(r_base, v_base)  # (n, 3, 3), columns R, T, N
        return (
            r_base + np.einsum("nij,nj->ni", basis, dr_rtn),
            v_base + np.einsum("nij,nj->ni", basis, dv_rtn + rotation),
        )

    def tle_age_days(self, jd: float, fr: float) -> float:
        return self.base.tle_age_days(jd, fr)
