"""
The in-memory world ORBITGUARD AI serves.

On startup the server loads the catalog, screens it for close approaches,
assesses every approach with the risk engine, and holds the results here. The
API layer only ever reads from this object.

Two kinds of event are served, and they are never confused:

  * **Screened events** come from running the real screening pipeline over the
    real catalog. Every number on them is computed.
  * **The simulated event** is a constructed conjunction against the ISS, placed
    so that a demo always has a critical, maneuverable event to walk through.
    The ISS and its state vector are real; the secondary object is not. It is
    marked `simulated: true` everywhere it appears, and the frontend shows a
    SIMULATION badge on it -- as the frontend specification requires.

Configuration comes from environment variables, so a demo can be tuned without
code changes:

  ORBITGUARD_GROUPS          CelesTrak groups to load (comma separated)
  ORBITGUARD_ALLOW_NETWORK   "1" to refresh stale catalog snapshots from CelesTrak
  ORBITGUARD_WINDOW_HOURS    screening window length (default 24)
  ORBITGUARD_REPORT_KM       miss distance at or below which to report (default 25)
  ORBITGUARD_SIMULATION      "0" to omit the simulated event
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np

from app.core.risk_engine import ConjunctionInput, RiskAssessment, RiskEngine
from app.core.tle_source import CelesTrakClient
from app.services.maneuvers import ManeuverPlanner
from app.services.screening import CloseApproach, screen
from app.services.tracks import TLETrack, Track, TwoBodyTrack, seconds_between, to_jd

logger = logging.getLogger(__name__)

DEFAULT_GROUPS = ("stations", "iridium-33-debris", "cosmos-1408-debris")
TIMELINE_HOURS = (-48, -36, -24, -12, -6, 0)

SIMULATED_MISS_KM = 0.42
SIMULATED_LEAD_HOURS = 4.2
SIMULATED_PRIMARY_NORAD = 25544  # ISS (ZARYA)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def classify(name: str, group: str = "") -> Dict[str, object]:
    """Infer display type, hard-body class, and maneuverability from a catalog name."""
    upper = (name or "").upper()
    if group.endswith("-debris"):
        # Everything in a debris group is debris, including intact but dead
        # hulks such as "IRIDIUM 33" whose names carry no DEB marker.
        return {"object_type": "Debris", "object_class": "debris_fragment", "maneuverable": False}
    if " DEB" in upper or upper.endswith("DEB") or "DEBRIS" in upper:
        return {"object_type": "Debris", "object_class": "debris_fragment", "maneuverable": False}
    if "R/B" in upper or "ROCKET" in upper:
        return {"object_type": "Rocket Body", "object_class": "rocket_body", "maneuverable": False}
    if group == "stations" or any(token in upper for token in ("ISS", "CSS", "TIANHE")):
        return {"object_type": "Active Satellite", "object_class": "large_satellite", "maneuverable": True}
    return {"object_type": "Active Satellite", "object_class": "typical_leo_satellite", "maneuverable": True}


def geometry_label(v1: np.ndarray, v2: np.ndarray) -> str:
    """Describe the encounter by the angle between the two velocity vectors."""
    cosine = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
    if angle < 20:
        return "Parallel"
    if angle < 60:
        return "Near-crossing"
    if angle < 150:
        return "Crossing"
    return "Head-on"


@dataclass
class Event:
    event_id: str
    approach: CloseApproach
    assessment: RiskAssessment
    simulated: bool
    geometry: str
    timeline: List[Dict[str, float]]
    maneuver_cache: Optional[Dict[str, object]] = field(default=None, repr=False)
    maneuver_cached_at: float = 0.0


class World:
    """Catalog, screening results, and risk assessments, built once and served."""

    def __init__(self):
        self.engine = RiskEngine()
        self.tracks: List[Track] = []
        self.events: Dict[str, Event] = {}
        self.built_at: Optional[datetime] = None
        self.build_seconds = 0.0
        self.catalog_snapshots: List[Dict[str, object]] = []
        self.config: Dict[str, object] = {}
        self.planner: Optional[ManeuverPlanner] = None
        self._lock = threading.RLock()

    # -- construction --------------------------------------------------------

    def build(self) -> "World":
        with self._lock:
            started = time.perf_counter()
            now = datetime.now(timezone.utc)

            groups = [g.strip() for g in os.environ.get(
                "ORBITGUARD_GROUPS", ",".join(DEFAULT_GROUPS)).split(",") if g.strip()]
            allow_network = os.environ.get("ORBITGUARD_ALLOW_NETWORK", "0") == "1"
            window_hours = _env_float("ORBITGUARD_WINDOW_HOURS", 24.0)
            report_km = _env_float("ORBITGUARD_REPORT_KM", 25.0)
            with_simulation = os.environ.get("ORBITGUARD_SIMULATION", "1") != "0"
            self.config = {
                "groups": groups, "allow_network": allow_network,
                "window_hours": window_hours, "report_km": report_km,
                "simulation": with_simulation,
            }

            self.tracks = self._load_tracks(groups, allow_network)
            self.planner = ManeuverPlanner(self.engine, self.tracks)

            events: Dict[str, Event] = {}
            if with_simulation:
                simulated = self._simulated_event(now)
                if simulated is not None:
                    events[simulated.event_id] = simulated

            approaches = screen(self.tracks, now, duration_hours=window_hours,
                                step_s=30.0, report_km=report_km)
            screened = [self._make_event(f"CJ-{i + 1:03d}", a, now, simulated=False)
                        for i, a in enumerate(approaches)]
            screened.sort(key=lambda e: e.assessment.risk_score, reverse=True)
            for index, event in enumerate(screened):
                event.event_id = f"CJ-{index + 1:03d}"
                events[event.event_id] = event

            self.events = events
            self.built_at = now
            self.build_seconds = time.perf_counter() - started
            logger.info("World built in %.1f s: %d tracks, %d events.",
                        self.build_seconds, len(self.tracks), len(self.events))
            return self

    def _load_tracks(self, groups: List[str], allow_network: bool) -> List[Track]:
        client = CelesTrakClient()
        self.catalog_snapshots = []
        seen: Dict[int, Track] = {}
        for group in groups:
            try:
                snapshot = client.fetch_group(group, allow_network=allow_network)
            except RuntimeError as exc:
                logger.error("Catalog group %r unavailable: %s", group, exc)
                continue
            self.catalog_snapshots.append(snapshot.summary())
            for tle in snapshot.objects:
                if tle.satrec is None or tle.satellite_number in seen:
                    continue
                traits = classify(tle.object_name, group)
                # Modules of one station share an element set; treat them as a
                # single body so they are not screened against each other.
                body_key = tle.line1[18:32] + tle.line2[8:63]
                seen[tle.satellite_number] = TLETrack(
                    object_id=str(tle.satellite_number),
                    name=tle.object_name.strip(),
                    body_key=body_key,
                    satrec=tle.satrec,
                    norad_id=tle.satellite_number,
                    **traits,
                )
        return list(seen.values())

    def _simulated_event(self, now: datetime) -> Optional[Event]:
        primary = next((t for t in self.tracks
                        if isinstance(t, TLETrack) and t.norad_id == SIMULATED_PRIMARY_NORAD), None)
        if primary is None:
            logger.warning("ISS not in catalog; simulated event omitted.")
            return None

        tca = now + timedelta(hours=SIMULATED_LEAD_HOURS)
        jd, fr = to_jd(tca)
        r, v = primary.state(jd, fr)

        v_hat = v / np.linalg.norm(v)
        offset = np.cross(v_hat, r / np.linalg.norm(r))
        offset /= np.linalg.norm(offset)
        speed = float(np.linalg.norm(v))

        secondary = TwoBodyTrack(
            object_id="SIM-DEB-1", name="SIMULATED DEBRIS", object_type="Debris",
            object_class="debris_fragment", maneuverable=False, simulated=True,
            epoch_jd=jd, epoch_fr=fr,
            position_km=r + offset * SIMULATED_MISS_KM,
            velocity_kms=speed * (-0.55 * v_hat + 0.835 * offset),
        )

        found = screen([primary, secondary], tca - timedelta(minutes=30),
                       duration_hours=1.0, step_s=10.0, report_km=5.0)
        if not found:
            logger.warning("Simulated conjunction did not screen as expected.")
            return None
        return self._make_event("SIM-001", found[0], now, simulated=True)

    def _make_event(self, event_id: str, approach: CloseApproach, now: datetime, simulated: bool) -> Event:
        now_jd, now_fr = to_jd(now)
        hours = seconds_between(now_jd, now_fr, approach.tca_jd, approach.tca_fr) / 3600.0
        jd, fr = approach.tca_jd, approach.tca_fr

        assessment = self.engine.assess(ConjunctionInput(
            primary_position_km=approach.primary_position_km,
            primary_velocity_kms=approach.primary_velocity_kms,
            secondary_position_km=approach.secondary_position_km,
            secondary_velocity_kms=approach.secondary_velocity_kms,
            time_to_tca_hours=hours,
            primary_tle_age_days=approach.primary.tle_age_days(jd, fr),
            secondary_tle_age_days=approach.secondary.tle_age_days(jd, fr),
            primary_object_class=approach.primary.object_class,
            secondary_object_class=approach.secondary.object_class,
            tca=approach.tca,
        ))

        timeline = []
        for offset_h in TIMELINE_HOURS:
            t_fr = fr + offset_h / 24.0
            a, _ = approach.primary.state(jd, t_fr)
            b, _ = approach.secondary.state(jd, t_fr)
            distance = float(np.linalg.norm(a - b))
            timeline.append({
                "t": f"T{offset_h:+d}" if offset_h else "T-0",
                "hours": offset_h,
                "distance_km": round(distance, 3) if offset_h else round(approach.miss_distance_km, 3),
            })

        return Event(
            event_id=event_id, approach=approach, assessment=assessment, simulated=simulated,
            geometry=geometry_label(approach.primary_velocity_kms, approach.secondary_velocity_kms),
            timeline=timeline,
        )

    # -- reads ---------------------------------------------------------------

    def now_jd(self):
        return to_jd(datetime.now(timezone.utc))

    def event_payload(self, event: Event) -> Dict[str, object]:
        """Serialise an event, refreshing the time-dependent fields."""
        now_jd, now_fr = self.now_jd()
        a = event.approach
        hours = seconds_between(now_jd, now_fr, a.tca_jd, a.tca_fr) / 3600.0
        self.engine.retime(event.assessment, hours)

        payload = event.assessment.to_dict()
        payload.pop("pc_detail", None)
        payload.update({
            "conjunction_id": event.event_id,
            "primary_id": a.primary.object_id,
            "secondary_id": a.secondary.object_id,
            "primary_name": a.primary.name,
            "secondary_name": a.secondary.name,
            "primary_type": a.primary.object_type,
            "secondary_type": a.secondary.object_type,
            "maneuverable": a.primary.maneuverable,
            "simulated": event.simulated,
            "tca": a.tca.isoformat(),
            "geometry": event.geometry,
            "timeline": event.timeline,
            "coarse_distance_km": a.coarse_distance_km,
        })
        return payload

    def active_events(self) -> List[Event]:
        """Events whose closest approach is still ahead, highest priority first."""
        now_jd, now_fr = self.now_jd()
        upcoming = [e for e in self.events.values()
                    if seconds_between(now_jd, now_fr, e.approach.tca_jd, e.approach.tca_fr) > 0]
        for e in upcoming:
            a = e.approach
            self.engine.retime(e.assessment, seconds_between(now_jd, now_fr, a.tca_jd, a.tca_fr) / 3600.0)
        return sorted(upcoming, key=lambda e: (not e.simulated, -e.assessment.risk_score))

    def stats(self) -> Dict[str, object]:
        active = self.active_events()
        return {
            "objects_tracked": len(self.tracks),
            "active_conjunctions": len(active),
            "high_risk_events": sum(1 for e in active if e.assessment.severity in ("HIGH", "CRITICAL")),
            "satellites_monitored": sum(1 for t in self.tracks if t.maneuverable),
        }

    def maneuvers(self, event: Event, max_age_s: float = 300.0) -> Dict[str, object]:
        with self._lock:
            if event.maneuver_cache is None or time.time() - event.maneuver_cached_at > max_age_s:
                now_jd, now_fr = self.now_jd()
                event.maneuver_cache = self.planner.optimize(event.approach, now_jd, now_fr)
                event.maneuver_cached_at = time.time()
            return event.maneuver_cache

    def validate(self, event: Event, candidate_id: str) -> Dict[str, object]:
        now_jd, now_fr = self.now_jd()
        return self.planner.validate(event.approach, candidate_id, now_jd, now_fr)


_world: Optional[World] = None
_world_lock = threading.Lock()


def get_world() -> World:
    """The process-wide world, built on first use."""
    global _world
    with _world_lock:
        if _world is None:
            _world = World().build()
        return _world


def rebuild_world() -> World:
    global _world
    with _world_lock:
        _world = World().build()
        return _world
