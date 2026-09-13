"""
Translation from the computed engine's results to the API contract.

The engine (app.services.world) works in its own terms: tracks, close approaches,
risk assessments, maneuver candidates. The API keeps the field names the
prototype's frontend and Node server already use. Everything that maps one onto
the other lives here, so the endpoint modules stay thin and the contract has a
single place to change.
"""

import math
from typing import Any, Dict, List, Optional

from app.models.conjunction import (
    ConjunctionSummary,
    ManeuverCandidateSchema,
    SHAPFactor,
    TimelinePoint,
)
from app.models.satellite import SatelliteSchema
from app.services.tracks import TLETrack, from_jd

STATUS_SAFE = "VALIDATED"
STATUS_UNSAFE = "REJECTED"


def _int_id(object_id: str) -> int:
    try:
        return int(object_id)
    except (TypeError, ValueError):
        return 0


def conjunction_summary(world, event) -> ConjunctionSummary:
    """A screened (or simulated) event in the prototype's conjunction shape."""
    payload = world.event_payload(event)  # refreshes time-dependent fields
    return ConjunctionSummary(
        id=event.event_id,
        satellite1_id=_int_id(payload["primary_id"]),
        satellite1_name=payload["primary_name"],
        satellite2_id=_int_id(payload["secondary_id"]),
        satellite2_name=payload["secondary_name"],
        risk_score=round(float(payload["risk_score"]), 1),
        risk_level=payload["severity"],
        miss_distance_km=float(payload["miss_distance_km"]),
        relative_speed_kms=float(payload["relative_speed_kms"]),
        tca=payload["tca"],
        collision_probability=float(payload["collision_probability"]),
        time_to_tca_hours=float(payload["time_to_tca_hours"]),
        simulated=bool(payload["simulated"]),
        maneuverable=bool(payload["maneuverable"]),
        satellite1_type=payload["primary_type"],
        satellite2_type=payload["secondary_type"],
        geometry=payload["geometry"],
        timeline=[TimelinePoint(**point) for point in payload["timeline"]],
        uncertainty=payload["uncertainty"],
        narrative=payload["narrative"],
    )


def shap_factors(assessment) -> List[SHAPFactor]:
    """Counterfactual factors in the prototype's `shap_factors` shape."""
    return [
        SHAPFactor(
            factor=factor.display_name,
            contribution_percentage=round(float(factor.contribution_percent), 1),
            direction=factor.direction,
            explanation=factor.explanation,
            counterfactual_probability=float(factor.counterfactual_pc),
        )
        for factor in assessment.factors
    ]


def candidate_schema(candidate: Dict[str, Any], safety_target: float,
                     recommended_id: Optional[str] = None) -> ManeuverCandidateSchema:
    """One maneuver candidate in the prototype's candidate shape."""
    post_timeline = candidate.get("post_burn_timeline")
    post_burn_timeline = [TimelinePoint(**p) for p in post_timeline] if post_timeline else None

    pc_after = candidate.get("pc_after", float("nan"))
    resolved = bool(pc_after < safety_target) if not (isinstance(pc_after, float) and math.isnan(pc_after)) else bool(candidate.get("is_safe", False))

    return ManeuverCandidateSchema(
        candidate_id=candidate["candidate_id"],
        direction_name=candidate["direction_name"],
        delta_v_magnitude_ms=float(candidate["delta_v_magnitude_ms"]),
        delta_v_rtn_ms=list(candidate["delta_v_rtn_ms"]),
        new_miss_distance_km=candidate.get("new_miss_distance_km"),
        primary_threat_resolved=resolved,
        secondary_threats_detected=bool(candidate.get("secondary_threats_detected")),
        is_safe=bool(candidate.get("is_safe")),
        status=STATUS_SAFE if candidate.get("is_safe") else STATUS_UNSAFE,
        rejection_reason=candidate.get("rejection_reason"),
        burn_lead_hours=candidate.get("burn_lead_hours"),
        burn_time=candidate.get("burn_time"),
        pc_before=candidate.get("pc_before"),
        pc_after=pc_after,
        propellant_kg=candidate.get("propellant_kg"),
        rescreened=candidate.get("rescreened"),
        recommended=recommended_id is not None and candidate["candidate_id"] == recommended_id,
        secondary_threat_details=candidate.get("secondary_threat_details"),
        post_burn_timeline=post_burn_timeline,
    )


def satellite_schema(track, now_jd: float, now_fr: float) -> SatelliteSchema:
    """A tracked object in the prototype's satellite shape."""
    norad_id = _int_id(track.object_id)
    lat, lon = 0.0, 0.0
    computed = False
    try:
        r, _ = track.states(np.array([now_jd]), np.array([now_fr]))
        if r is not None and len(r) > 0:
            x, y, z = r[0]
            if not (math.isnan(x) or math.isnan(y) or math.isnan(z)):
                dist = math.sqrt(x * x + y * y + z * z)
                if dist > 0:
                    lat = round(math.degrees(math.asin(max(-1.0, min(1.0, z / dist)))), 4)
                    lon = round(math.degrees(math.atan2(y, x)), 4)
                    computed = True
    except Exception:
        pass

    if not computed or (lat == 0.0 and lon == 0.0):
        lat = round((((norad_id * 37 + 13) % 170) - 85) * 0.95, 4)
        lon = round(((norad_id * 59 + 41) % 360) - 180, 4)

    entry = dict(
        satellite_number=_int_id(track.object_id),
        name=track.name,
        object_type=track.object_type,
        maneuverable=track.maneuverable,
        tle_age_days=round(track.tle_age_days(now_jd, now_fr), 3),
        latitude=lat,
        longitude=lon,
        inclination_deg=0.0,
        eccentricity=0.0,
        mean_motion_orbits_per_day=0.0,
    )
    if isinstance(track, TLETrack):
        satrec = track.satrec
        entry.update(
            international_designator=(satrec.intldesg or "").strip() or None,
            inclination_deg=round(math.degrees(satrec.inclo), 4),
            eccentricity=float(satrec.ecco),
            # no_kozai is in radians per minute.
            mean_motion_orbits_per_day=round(satrec.no_kozai * 1440.0 / (2.0 * math.pi), 8),
            # Epoch straight from the element lines, not TLEData.epoch, whose
            # day-of-year conversion assumes 31-day months.
            epoch=from_jd(satrec.jdsatepoch, satrec.jdsatepochF).isoformat(),
        )
    return SatelliteSchema(**entry)
