"""
Risk assessment and explainability for ORBITGUARD AI.

This module turns a detected conjunction into three things an operator actually
needs: a physically meaningful probability of collision, a 0-100 priority score
for triaging a queue of events, and a breakdown of *why* the event scores the
way it does.

Design notes, since the approach here is deliberate:

**The probability is computed, not predicted.** Pc comes from Foster's 2D method
(see `collision_probability`), the same technique used in operational conjunction
assessment. It is not the output of a classifier. This matters because a number
labelled "probability of collision" will be read as one, and a model confidence
score is not a probability of anything physical.

**The explanation is counterfactual, not attributional.** Rather than running
SHAP over a model, each factor's contribution is measured by recomputing Pc with
that factor reset to a benign baseline and reporting how far the probability
moves. So "ephemeris uncertainty contributes 38%" unpacks to a concrete,
checkable claim: *if both TLEs were fresh, Pc would fall from 2.3e-4 to 8.1e-6.*
That is explainable in a way a feature-importance bar chart over a synthetic
training set is not, and it cannot drift out of agreement with the underlying
physics, because it *is* the underlying physics evaluated twice.

**Urgency is kept separate from probability.** Time to closest approach does not
change how likely a collision is; it changes how much time an operator has to do
something about it. Conflating the two produces a score claiming a distant
conjunction is physically safer than an identical imminent one. Here Pc drives
the score and urgency modulates it, and the distinction is stated in the output.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import numpy as np

from app.core.collision_probability import PcResult, collision_probability
from app.core.uncertainty import (
    TLEUncertaintyModel,
    covariance_for_object,
    hard_body_radius_for,
)

logger = logging.getLogger(__name__)


# Severity thresholds on Pc. These follow common operator practice, where a
# collision probability around 1e-4 is the point at which an avoidance maneuver
# is normally considered. They are policy, not physics, and are stated here in
# one place so they can be argued with directly.
PC_THRESHOLD_CRITICAL = 1e-4
PC_THRESHOLD_HIGH = 1e-5
PC_THRESHOLD_AMBER = 1e-6

# Range over which log10(Pc) is mapped onto the 0-100 score.
_LOG_PC_FLOOR = -9.0  # at or below this, the Pc contribution is zero
_LOG_PC_CEILING = -3.0  # at or above this, the Pc contribution saturates

# Urgency ramp, in hours to closest approach.
_URGENCY_FULL_HOURS = 2.0  # at or inside this, urgency is maximal
_URGENCY_ZERO_HOURS = 72.0  # at or beyond this, urgency contributes nothing

# Floor for reported probabilities. Foster's method will happily return 1e-34
# for a counterfactual twenty sigma into the tail of a Gaussian, but that figure
# is not a credible estimate of anything: it is the assumed shape of the
# distribution extrapolated far past where the assumption holds. Operational
# conjunction assessment does not quote probabilities below roughly 1e-10, so
# anything smaller is reported as "below the floor" rather than as a number.
PC_REPORTING_FLOOR = 1e-12


@dataclass
class ConjunctionInput:
    """
    Everything the risk engine needs about one conjunction.

    All state vectors are inertial (TEME, as returned by SGP4) and evaluated at
    the time of closest approach.
    """

    primary_position_km: np.ndarray
    primary_velocity_kms: np.ndarray
    secondary_position_km: np.ndarray
    secondary_velocity_kms: np.ndarray

    time_to_tca_hours: float
    """Hours from now until closest approach. Drives urgency, not probability."""

    primary_tle_age_days: float = 0.0
    secondary_tle_age_days: float = 0.0

    primary_object_class: str = "typical_leo_satellite"
    secondary_object_class: str = "debris_fragment"

    primary_id: Optional[int] = None
    secondary_id: Optional[int] = None
    tca: Optional[datetime] = None

    def relative_position_km(self) -> np.ndarray:
        return np.asarray(self.primary_position_km, dtype=np.float64) - np.asarray(
            self.secondary_position_km, dtype=np.float64
        )

    def relative_velocity_kms(self) -> np.ndarray:
        return np.asarray(self.primary_velocity_kms, dtype=np.float64) - np.asarray(
            self.secondary_velocity_kms, dtype=np.float64
        )


@dataclass
class FactorContribution:
    """One counterfactual explanation of the risk score."""

    name: str
    display_name: str
    contribution_percent: float
    """Share of the total risk elevation attributable to this factor."""

    counterfactual_pc: float
    """What Pc would be if this factor were at its benign baseline."""

    log10_delta: float
    """log10(Pc_actual) - log10(Pc_counterfactual). Positive means risk-raising."""

    explanation: str
    """A sentence stating the counterfactual in plain language."""

    direction: str = "raises"
    """Whether this factor currently raises or reduces the probability.

    A factor can genuinely reduce it. Large ephemeris uncertainty spreads the
    probability distribution out, and past a point that *lowers* Pc rather than
    raising it -- the dilution effect. Reporting such a factor as a zero
    contribution would hide a real and counterintuitive finding, so it is
    labelled instead.
    """

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "contribution_percent": self.contribution_percent,
            "counterfactual_pc": self.counterfactual_pc,
            "log10_delta": self.log10_delta,
            "direction": self.direction,
            "explanation": self.explanation,
        }


@dataclass
class RiskAssessment:
    """The full risk picture for one conjunction."""

    pc: float
    risk_score: float
    """0-100 operator priority score."""

    severity: str
    """GREEN / AMBER / HIGH / CRITICAL, keyed to Pc thresholds."""

    miss_distance_km: float
    relative_speed_kms: float
    time_to_tca_hours: float
    combined_hbr_m: float

    pc_result: PcResult
    factors: List[FactorContribution] = field(default_factory=list)
    uncertainty_summary: Dict[str, float] = field(default_factory=dict)
    narrative: str = ""
    primary_id: Optional[int] = None
    secondary_id: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "primary_id": self.primary_id,
            "secondary_id": self.secondary_id,
            "collision_probability": self.pc,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "miss_distance_km": self.miss_distance_km,
            "relative_speed_kms": self.relative_speed_kms,
            "time_to_tca_hours": self.time_to_tca_hours,
            "combined_hbr_m": self.combined_hbr_m,
            "factors": [f.to_dict() for f in self.factors],
            "uncertainty": self.uncertainty_summary,
            "narrative": self.narrative,
            "pc_detail": self.pc_result.to_dict(),
        }


def _normalise_log_pc(pc: float) -> float:
    """Map Pc onto [0, 1] through its logarithm."""
    if pc <= 0.0:
        return 0.0
    log_pc = math.log10(pc)
    span = _LOG_PC_CEILING - _LOG_PC_FLOOR
    return float(np.clip((log_pc - _LOG_PC_FLOOR) / span, 0.0, 1.0))


def _normalise_urgency(hours_to_tca: float) -> float:
    """Map time-to-TCA onto [0, 1], with sooner meaning more urgent."""
    hours = max(0.0, float(hours_to_tca))
    if hours <= _URGENCY_FULL_HOURS:
        return 1.0
    if hours >= _URGENCY_ZERO_HOURS:
        return 0.0
    span = _URGENCY_ZERO_HOURS - _URGENCY_FULL_HOURS
    return float((_URGENCY_ZERO_HOURS - hours) / span)


def format_pc(pc: float) -> str:
    """
    Render a probability for display, respecting the reporting floor.

    Values below `PC_REPORTING_FLOOR` are shown as an upper bound rather than a
    figure, because quoting them precisely would imply confidence the method
    does not have that far into the tail.
    """
    if pc < PC_REPORTING_FLOOR:
        return f"below {PC_REPORTING_FLOOR:.0e}"
    return f"{pc:.2e}"


def priority_score(pc: float, time_to_tca_hours: float) -> float:
    """
    The 0-100 operator priority score.

    Pc sets the magnitude; urgency modulates it by up to 25% relative. Urgency
    alone can never manufacture risk where the probability is negligible, which
    is the point of multiplying rather than adding.
    """
    pc_norm = _normalise_log_pc(pc)
    urgency = _normalise_urgency(time_to_tca_hours)
    return float(np.clip(100.0 * pc_norm * (0.80 + 0.20 * urgency), 0.0, 100.0))


def severity_for_pc(pc: float) -> str:
    """Classify a collision probability into an operator-facing severity band."""
    if pc >= PC_THRESHOLD_CRITICAL:
        return "CRITICAL"
    if pc >= PC_THRESHOLD_HIGH:
        return "HIGH"
    if pc >= PC_THRESHOLD_AMBER:
        return "AMBER"
    return "GREEN"


class RiskEngine:
    """
    Computes collision probability, priority score, and counterfactual factors.

    Args:
        uncertainty_model: Model governing how TLE position error grows with
            propagation age. The default is a documented assumption; see
            `app.core.uncertainty` for why one is needed at all.
        benign_miss_distance_km: The miss distance a conjunction is compared
            against when explaining how much proximity contributes.
        benign_combined_hbr_m: The combined hard-body radius used as the "small
            objects" baseline when explaining the size contribution.
    """

    def __init__(
        self,
        uncertainty_model: Optional[TLEUncertaintyModel] = None,
        benign_miss_distance_km: float = 10.0,
        benign_combined_hbr_m: float = 1.0,
    ):
        self.uncertainty_model = uncertainty_model or TLEUncertaintyModel()
        self.benign_miss_distance_km = benign_miss_distance_km
        self.benign_combined_hbr_m = benign_combined_hbr_m
        self.logger = logging.getLogger(__name__)

    # -- core assessment ---------------------------------------------------

    def _pc_for(
        self,
        conjunction: ConjunctionInput,
        *,
        relative_position_km: Optional[np.ndarray] = None,
        primary_age_days: Optional[float] = None,
        secondary_age_days: Optional[float] = None,
        combined_hbr_m: Optional[float] = None,
        method: str = "foster",
    ) -> PcResult:
        """
        Evaluate Pc, optionally overriding one input for a counterfactual.

        Keeping every counterfactual on this single code path is what guarantees
        the explanation stays consistent with the headline number: both come from
        the same calculation with the same assumptions.
        """
        r_rel = (
            conjunction.relative_position_km()
            if relative_position_km is None
            else relative_position_km
        )
        v_rel = conjunction.relative_velocity_kms()

        age_1 = (
            conjunction.primary_tle_age_days
            if primary_age_days is None
            else primary_age_days
        )
        age_2 = (
            conjunction.secondary_tle_age_days
            if secondary_age_days is None
            else secondary_age_days
        )

        cov_1 = covariance_for_object(
            conjunction.primary_position_km,
            conjunction.primary_velocity_kms,
            age_1,
            self.uncertainty_model,
        )
        cov_2 = covariance_for_object(
            conjunction.secondary_position_km,
            conjunction.secondary_velocity_kms,
            age_2,
            self.uncertainty_model,
        )

        if combined_hbr_m is None:
            hbr_1 = hard_body_radius_for(conjunction.primary_object_class)
            hbr_2 = hard_body_radius_for(conjunction.secondary_object_class)
        else:
            # Split the override evenly; only the sum enters the calculation.
            hbr_1 = hbr_2 = combined_hbr_m / 2.0

        return collision_probability(
            r_rel,
            v_rel,
            cov_1,
            cov_2,
            hard_body_radius_1_m=hbr_1,
            hard_body_radius_2_m=hbr_2,
            method=method,
        )

    def probability(self, conjunction: ConjunctionInput, method: str = "foster") -> PcResult:
        """
        Collision probability alone, without scoring or explanation.

        Pass method="chan" when evaluating many hypotheticals, such as a grid of
        maneuver candidates: the analytic series agrees with the quadrature to
        about twelve significant figures and is far cheaper.
        """
        return self._pc_for(conjunction, method=method)

    def assess(self, conjunction: ConjunctionInput) -> RiskAssessment:
        """
        Produce the full risk assessment for one conjunction.

        Args:
            conjunction: State vectors, TLE ages, and object classes at TCA.

        Returns:
            A RiskAssessment carrying Pc, score, severity, factors, narrative.
        """
        pc_result = self._pc_for(conjunction)
        pc = pc_result.pc

        risk_score = priority_score(pc, conjunction.time_to_tca_hours)

        factors = self._explain(conjunction, pc)

        sigma_p = self.uncertainty_model.describe(conjunction.primary_tle_age_days)
        sigma_s = self.uncertainty_model.describe(conjunction.secondary_tle_age_days)

        assessment = RiskAssessment(
            pc=pc,
            risk_score=risk_score,
            severity=severity_for_pc(pc),
            miss_distance_km=pc_result.geometry.miss_distance_km,
            relative_speed_kms=pc_result.geometry.relative_speed_kms,
            time_to_tca_hours=conjunction.time_to_tca_hours,
            combined_hbr_m=pc_result.combined_hbr_m,
            pc_result=pc_result,
            factors=factors,
            uncertainty_summary={
                "primary_tle_age_days": sigma_p["tle_age_days"],
                "primary_sigma_along_track_km": sigma_p["sigma_along_track_km"],
                "secondary_tle_age_days": sigma_s["tle_age_days"],
                "secondary_sigma_along_track_km": sigma_s["sigma_along_track_km"],
            },
            primary_id=conjunction.primary_id,
            secondary_id=conjunction.secondary_id,
        )
        assessment.narrative = self._narrate(assessment)

        self.logger.info(
            "Conjunction %s-%s: Pc=%.3e (%s), score=%.1f",
            conjunction.primary_id,
            conjunction.secondary_id,
            pc,
            assessment.severity,
            risk_score,
        )
        return assessment

    # -- explainability ----------------------------------------------------

    def _explain(
        self, conjunction: ConjunctionInput, actual_pc: float
    ) -> List[FactorContribution]:
        """
        Attribute the risk to its drivers by counterfactual re-evaluation.

        Each factor is reset to a benign baseline and Pc is recomputed. The
        resulting drop in log-probability measures how much that factor is
        responsible for the risk being where it is.
        """
        if actual_pc <= 0.0:
            return []

        log_actual = math.log10(actual_pc)
        raw: List[FactorContribution] = []

        # --- proximity -----------------------------------------------------
        r_rel = conjunction.relative_position_km()
        miss = float(np.linalg.norm(r_rel))
        if 0.0 < miss < self.benign_miss_distance_km:
            scaled = r_rel * (self.benign_miss_distance_km / miss)
            cf = self._pc_for(conjunction, relative_position_km=scaled).pc
            raw.append(
                self._make_factor(
                    "miss_distance",
                    "Miss distance",
                    log_actual,
                    cf,
                    f"At the screening baseline of {self.benign_miss_distance_km:.0f} km "
                    f"rather than the predicted {miss:.2f} km, the probability would be "
                    f"{format_pc(cf)}.",
                )
            )

        # --- ephemeris staleness -------------------------------------------
        max_age = max(
            conjunction.primary_tle_age_days, conjunction.secondary_tle_age_days
        )
        if max_age > 0.0:
            cf = self._pc_for(
                conjunction, primary_age_days=0.0, secondary_age_days=0.0
            ).pc
            raw.append(
                self._make_factor(
                    "tle_staleness",
                    "Ephemeris uncertainty",
                    log_actual,
                    cf,
                    f"With both elements fresh at epoch instead of up to "
                    f"{max_age:.1f} days old, the probability would be {format_pc(cf)}.",
                )
            )

        # --- object size ----------------------------------------------------
        hbr_1 = hard_body_radius_for(conjunction.primary_object_class)
        hbr_2 = hard_body_radius_for(conjunction.secondary_object_class)
        combined = hbr_1 + hbr_2
        if combined > self.benign_combined_hbr_m:
            cf = self._pc_for(conjunction, combined_hbr_m=self.benign_combined_hbr_m).pc
            raw.append(
                self._make_factor(
                    "object_size",
                    "Object size",
                    log_actual,
                    cf,
                    f"For a combined hard-body radius of "
                    f"{self.benign_combined_hbr_m:.1f} m rather than {combined:.1f} m, "
                    f"the probability would be {format_pc(cf)}.",
                )
            )

        # Normalise the risk-raising factors into shares of the total elevation.
        # Risk-reducing factors keep a signed percentage so the UI can show them
        # as what they are rather than silently dropping them to zero.
        elevating = [f for f in raw if f.log10_delta > 0.0]
        total = sum(f.log10_delta for f in elevating)
        if total > 0.0:
            for factor in elevating:
                factor.contribution_percent = 100.0 * factor.log10_delta / total
            for factor in raw:
                if factor.log10_delta <= 0.0:
                    factor.contribution_percent = 100.0 * factor.log10_delta / total

        raw.sort(key=lambda f: f.contribution_percent, reverse=True)
        return raw

    @staticmethod
    def _make_factor(
        name: str,
        display_name: str,
        log_actual: float,
        counterfactual_pc: float,
        explanation: str,
    ) -> FactorContribution:
        # Clamp to the reporting floor before taking the logarithm, so the
        # attribution arithmetic and the displayed figure agree with each other.
        clamped = max(counterfactual_pc, PC_REPORTING_FLOOR)
        log_cf = math.log10(clamped)
        delta = log_actual - log_cf
        return FactorContribution(
            name=name,
            display_name=display_name,
            contribution_percent=0.0,  # filled in during normalisation
            counterfactual_pc=clamped,
            log10_delta=delta,
            direction="raises" if delta > 0.0 else "reduces",
            explanation=explanation,
        )

    # -- narrative ---------------------------------------------------------

    def _narrate(self, assessment: RiskAssessment) -> str:
        """Compose the operator-facing summary sentence."""
        parts = [
            f"Collision probability is {format_pc(assessment.pc)} "
            f"({assessment.severity}), from a predicted miss of "
            f"{assessment.miss_distance_km:.2f} km at a relative velocity of "
            f"{assessment.relative_speed_kms:.1f} km/s."
        ]

        raising = [f for f in assessment.factors if f.direction == "raises"]
        if raising:
            top = raising[0]
            parts.append(
                f"The dominant driver is {top.display_name.lower()} "
                f"({top.contribution_percent:.0f}% of the elevation). {top.explanation}"
            )

        reducing = [f for f in assessment.factors if f.direction == "reduces"]
        if reducing:
            worst = min(reducing, key=lambda f: f.log10_delta)
            parts.append(
                f"Note that {worst.display_name.lower()} is currently lowering the "
                f"probability through uncertainty dilution: {worst.explanation}"
            )

        hours = assessment.time_to_tca_hours
        if hours <= _URGENCY_FULL_HOURS:
            parts.append(
                f"Closest approach is in {hours:.1f} h, leaving little time to act."
            )
        else:
            parts.append(f"Closest approach is in {hours:.1f} h.")

        parts.append(
            "Probability is computed from orbital mechanics; time to closest "
            "approach affects response time, not likelihood."
        )
        return " ".join(parts)

    def retime(self, assessment: RiskAssessment, time_to_tca_hours: float) -> RiskAssessment:
        """
        Update an assessment for the passage of time, without recomputing Pc.

        Time to closest approach does not enter the probability, so as a
        conjunction draws nearer only the urgency-dependent score and the
        narrative change. This avoids re-running the quadrature -- and the
        counterfactual re-evaluations -- every time a dashboard refreshes.
        """
        assessment.time_to_tca_hours = time_to_tca_hours
        assessment.risk_score = priority_score(assessment.pc, time_to_tca_hours)
        assessment.narrative = self._narrate(assessment)
        return assessment

    # -- batch operations --------------------------------------------------

    def assess_many(
        self, conjunctions: Sequence[ConjunctionInput]
    ) -> List[RiskAssessment]:
        """
        Assess a set of conjunctions and rank them by priority.

        Ranking is by risk score, which already folds in urgency, so the head of
        the list is the event an operator should look at first.
        """
        assessments = []
        for conjunction in conjunctions:
            try:
                assessments.append(self.assess(conjunction))
            except (ValueError, np.linalg.LinAlgError) as exc:
                self.logger.error(
                    "Skipping conjunction %s-%s: %s",
                    conjunction.primary_id,
                    conjunction.secondary_id,
                    exc,
                )
        assessments.sort(key=lambda a: a.risk_score, reverse=True)
        return assessments

    def pc_reduction(
        self,
        before: ConjunctionInput,
        after_relative_position_km: np.ndarray,
    ) -> Dict[str, float]:
        """
        Compare Pc before and after a proposed maneuver.

        This is what makes the fuel-versus-risk tradeoff quantitative: the
        optimizer supplies the post-maneuver relative position and gets back the
        probability actually retired by spending that delta-v.

        Args:
            before: The unmitigated conjunction.
            after_relative_position_km: Predicted relative position at TCA once
                the maneuver has been applied.

        Returns:
            Mapping with the before/after probabilities, the absolute reduction,
            and the reduction factor.
        """
        pc_before = self._pc_for(before).pc
        pc_after = self._pc_for(
            before, relative_position_km=after_relative_position_km
        ).pc

        # Clamp the post-maneuver figure to the reporting floor before dividing.
        # Without this the ratio reads as "reduced by a factor of 2e14", which is
        # an artefact of extrapolating a Gaussian tail, not a real result.
        pc_after_reported = max(pc_after, PC_REPORTING_FLOOR)
        return {
            "pc_before": pc_before,
            "pc_after": pc_after_reported,
            "pc_after_below_floor": pc_after < PC_REPORTING_FLOOR,
            "pc_reduction": pc_before - pc_after_reported,
            "reduction_factor": pc_before / pc_after_reported,
        }
