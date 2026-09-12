"""
TLE ingestion from CelesTrak for ORBITGUARD AI.

Fetches published element sets from CelesTrak's GP endpoint, caches them on
disk, and parses them into the `TLEData` objects the rest of the engine works
with.

Three design decisions worth stating, because they are the difference between a
demo that works and one that dies on stage:

**Cache first, network second.** Every fetch writes a snapshot to `data/raw/`
alongside a small metadata file recording when it was taken. Subsequent loads
reuse that snapshot until it ages past a threshold. This is partly courtesy --
CelesTrak is a free service run on donated effort and asks clients not to poll
it hard -- and partly self-interest, since a cached catalog is the difference
between a demo that runs on venue wifi and one that does not.

**Degrade rather than fail.** If the network is unavailable and a stale snapshot
exists, the stale snapshot is returned with a loud warning rather than an
exception. A conjunction screen against slightly old elements is far more useful
than a traceback, and the staleness is surfaced in the returned object so the
risk engine can widen its covariance accordingly.

**Handle both TLE layouts.** CelesTrak serves three-line sets: a name line
followed by the two element lines. The bare two-line form also exists. The
parser here detects which it is looking at per record, rather than assuming a
fixed stride and silently desynchronising when it guesses wrong.

Element-set age matters downstream: `TLEUncertaintyModel` grows position
uncertainty with propagation age, so `tle_age_days()` here feeds directly into
the collision probability. Fresh elements produce a tighter covariance and a
sharper Pc.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.core.data_ingestion import TLEData, TLEParser

logger = logging.getLogger(__name__)

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
CELESTRAK_SUPPLEMENTAL_URL = "https://celestrak.org/NORAD/elements/supplemental/sup-gp.php"
SUPPLEMENTAL_PREFIX = "sup-"

# Identify ourselves. CelesTrak's usage guidelines ask clients to send a
# meaningful User-Agent so they can contact operators of misbehaving scripts
# rather than simply blocking them.
USER_AGENT = "ORBITGUARD-AI/0.1 (hackathon prototype; conjunction screening)"

DEFAULT_MAX_CACHE_AGE_HOURS = 8.0
DEFAULT_TIMEOUT_SECONDS = 30

# Groups that make sense for conjunction screening. Debris clouds are included
# deliberately: they are dense, they are what actually threatens active
# satellites, and they produce realistic close approaches rather than contrived
# ones.
USEFUL_GROUPS: Dict[str, str] = {
    "stations": "Crewed stations and modules, including the ISS.",
    "active": "All active satellites. Large -- around 13,000 objects.",
    "cosmos-1408-debris": "Debris from the 2021 Cosmos 1408 ASAT test.",
    "iridium-33-debris": "Debris from the 2009 Iridium 33 / Cosmos 2251 collision.",
    "fengyun-1c-debris": "Debris from the 2007 Fengyun-1C ASAT test.",
    "last-30-days": "Objects launched or catalogued in the last 30 days.",
    "starlink": "Starlink constellation. Very large.",
}


def _repo_root() -> str:
    """Locate the repository root relative to this file."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def default_cache_dir() -> str:
    """Where catalog snapshots live by default."""
    return os.path.join(_repo_root(), "data", "raw")


@dataclass
class CatalogSnapshot:
    """A fetched or cached set of element sets, with provenance attached."""

    group: str
    objects: List[TLEData]
    fetched_at: datetime
    """When the underlying data was retrieved from CelesTrak."""

    from_cache: bool
    source: str = CELESTRAK_GP_URL
    parse_failures: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def age_hours(self) -> float:
        """How long ago the snapshot was taken."""
        return (
            datetime.now(timezone.utc) - self.fetched_at
        ).total_seconds() / 3600.0

    @property
    def is_stale(self) -> bool:
        """Whether the snapshot is older than the default freshness threshold."""
        return self.age_hours > DEFAULT_MAX_CACHE_AGE_HOURS

    def __len__(self) -> int:
        return len(self.objects)

    def summary(self) -> Dict[str, object]:
        return {
            "group": self.group,
            "object_count": len(self.objects),
            "fetched_at": self.fetched_at.isoformat(),
            "age_hours": round(self.age_hours, 2),
            "from_cache": self.from_cache,
            "is_stale": self.is_stale,
            "parse_failures": self.parse_failures,
            "warnings": self.warnings,
        }


def parse_tle_text(text: str) -> Tuple[List[TLEData], int]:
    """
    Parse a TLE payload, accepting both the two-line and three-line layouts.

    Records are identified by their line prefixes rather than by position, so a
    malformed entry costs one satellite instead of desynchronising everything
    after it.

    Args:
        text: Raw TLE text as served by CelesTrak.

    Returns:
        Tuple of (parsed objects, count of records that failed to parse). Each
        object carries an `object_name` attribute, taken from the name line when
        the three-line form is used.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    objects: List[TLEData] = []
    failures = 0

    index = 0
    pending_name: Optional[str] = None

    while index < len(lines):
        line = lines[index].strip()

        if not line or line.startswith("#"):
            index += 1
            continue

        if line.startswith("1 ") and len(line) >= 69:
            # An element line. Its partner must be the next non-empty line.
            line1 = line
            line2 = None
            lookahead = index + 1
            while lookahead < len(lines):
                candidate = lines[lookahead].strip()
                if candidate:
                    line2 = candidate
                    break
                lookahead += 1

            if line2 is None or not line2.startswith("2 "):
                logger.warning("Element line 1 at %d has no matching line 2.", index + 1)
                failures += 1
                index += 1
                pending_name = None
                continue

            tle = TLEParser.parse_tle_lines(line1, line2)
            if tle is None:
                failures += 1
            else:
                # The name only exists in the three-line form; the parser has no
                # field for it, so attach it here.
                tle.object_name = pending_name or f"NORAD {tle.satellite_number}"
                objects.append(tle)

            pending_name = None
            index = lookahead + 1
            continue

        if line.startswith("2 "):
            # An orphaned line 2, already consumed or malformed. Skip it.
            index += 1
            continue

        # Anything else at this position is a name line for the record that
        # follows it.
        pending_name = line
        index += 1

    return objects, failures


def tle_epoch_utc(tle: TLEData) -> datetime:
    """
    Compute a TLE's epoch correctly, as a timezone-aware UTC datetime.

    This deliberately does not use `TLEData.epoch`. That field is built by
    `TLEData._calculate_epoch`, which converts day-of-year to a calendar date by
    repeatedly subtracting 31:

        while day > 31:
            day -= 31
            month += 1

    Treating every month as 31 days makes the result drift: it is exact in
    January and roughly six days early by December. Day 255 of 2026 is
    12 September, but that loop returns 7 September.

    The error does not affect SGP4 propagation, because `Satrec.twoline2rv`
    parses the epoch from the raw element lines itself. It does affect anything
    reading `tle.epoch`, including element age -- and since age drives the
    position covariance behind every collision probability, a five-day error
    inflates along-track sigma by several kilometres and skews Pc.

    The correct conversion is simply day-of-year offset from 1 January, which is
    what the TLE format specifies: day 1.0 is the start of 1 January.

    Args:
        tle: The element set.

    Returns:
        Epoch as a timezone-aware UTC datetime.
    """
    year = tle.epoch_year
    # Two-digit TLE years: 57-99 mean 1957-1999, 00-56 mean 2000-2056.
    if year < 57:
        year += 2000
    elif year < 100:
        year += 1900

    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=tle.epoch_day - 1.0
    )


def tle_age_days(tle: TLEData, at_time: Optional[datetime] = None) -> float:
    """
    How far a TLE is being propagated from its own epoch.

    This is the quantity that drives position uncertainty, and therefore the
    collision probability. A TLE propagated three days from epoch carries far
    more along-track error than one propagated three hours.

    Args:
        tle: The element set.
        at_time: Evaluation time. Defaults to now, in UTC.

    Returns:
        Age in days. Always non-negative; propagating backwards degrades
        accuracy just as propagating forwards does.
    """
    at_time = at_time or datetime.now(timezone.utc)
    if at_time.tzinfo is None:
        at_time = at_time.replace(tzinfo=timezone.utc)

    return abs((at_time - tle_epoch_utc(tle)).total_seconds()) / 86400.0


class CelesTrakClient:
    """
    Fetches and caches element sets from CelesTrak.

    Args:
        cache_dir: Where snapshots are written. Defaults to `data/raw/`.
        timeout_seconds: Per-request network timeout.
        user_agent: Sent with every request so CelesTrak can identify us.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = USER_AGENT,
    ):
        self.cache_dir = cache_dir or default_cache_dir()
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        os.makedirs(self.cache_dir, exist_ok=True)

    # -- cache -------------------------------------------------------------

    def _cache_paths(self, group: str) -> Tuple[str, str]:
        safe = group.replace("/", "_")
        return (
            os.path.join(self.cache_dir, f"{safe}.tle"),
            os.path.join(self.cache_dir, f"{safe}.meta.json"),
        )

    def _read_cache(self, group: str) -> Optional[Tuple[str, datetime]]:
        """Return cached text and its fetch time, or None if absent."""
        tle_path, meta_path = self._cache_paths(group)
        if not os.path.exists(tle_path):
            return None

        fetched_at = None
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as handle:
                    meta = json.load(handle)
                fetched_at = datetime.fromisoformat(meta["fetched_at"])
            except (OSError, ValueError, KeyError) as exc:
                self.logger.warning("Unreadable cache metadata for %s: %s", group, exc)

        if fetched_at is None:
            # Fall back to the file's modification time.
            fetched_at = datetime.fromtimestamp(
                os.path.getmtime(tle_path), tz=timezone.utc
            )
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        with open(tle_path, "r", encoding="utf-8") as handle:
            return handle.read(), fetched_at

    def _write_cache(self, group: str, text: str, fetched_at: datetime) -> None:
        tle_path, meta_path = self._cache_paths(group)
        with open(tle_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        meta = {
            "group": group,
            "fetched_at": fetched_at.isoformat(),
            "source": CELESTRAK_GP_URL,
            "bytes": len(text.encode("utf-8")),
        }
        with open(meta_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(meta, handle, indent=2)
            handle.write("\n")
        self.logger.info("Cached %s (%d bytes) to %s", group, len(text), tle_path)

    # -- network -----------------------------------------------------------

    def _download(self, group: str) -> str:
        """
        Retrieve one group from CelesTrak.

        Raises:
            RuntimeError: if requests is unavailable, the request fails, or the
                response does not look like TLE data.
        """
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "The requests package is required for network fetches. "
                "Install it with: pip install -r requirements.txt"
            ) from exc

        # "sup-<file>" selects CelesTrak's Supplemental GP data: element sets fitted
        # to operator-provided ephemerides rather than to radar tracking, and so
        # far more accurate. They serve as near-truth when measuring how badly
        # the standard element sets drift.
        if group.startswith(SUPPLEMENTAL_PREFIX):
            url = CELESTRAK_SUPPLEMENTAL_URL
            params = {"FILE": group[len(SUPPLEMENTAL_PREFIX):], "FORMAT": "tle"}
        else:
            url = CELESTRAK_GP_URL
            params = {"GROUP": group, "FORMAT": "tle"}

        self.logger.info("Fetching %r from CelesTrak.", group)
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"CelesTrak request for {group!r} failed: {exc}") from exc

        text = response.text

        # CelesTrak answers an unknown group with a plain-text error rather than
        # an HTTP error code, so check that the payload is actually TLE data.
        if "No GP data found" in text or not text.strip():
            raise RuntimeError(
                f"CelesTrak returned no data for group {group!r}. "
                f"Known groups: {', '.join(sorted(USEFUL_GROUPS))}"
            )
        if not any(line.startswith("1 ") for line in text.splitlines()):
            raise RuntimeError(
                f"CelesTrak response for {group!r} contains no element lines; "
                f"first 200 characters: {text[:200]!r}"
            )

        return text

    # -- public ------------------------------------------------------------

    def fetch_group(
        self,
        group: str = "stations",
        max_cache_age_hours: float = DEFAULT_MAX_CACHE_AGE_HOURS,
        allow_network: bool = True,
        force_refresh: bool = False,
    ) -> CatalogSnapshot:
        """
        Load one catalog group, preferring cache and degrading gracefully.

        The resolution order is: a fresh cache entry, then the network, then a
        stale cache entry with a warning. Only an absent cache combined with an
        unusable network raises.

        Args:
            group: CelesTrak group name, e.g. "stations" or "active".
            max_cache_age_hours: How old a snapshot may be before a refresh is
                attempted.
            allow_network: Set False to work purely from cache, which is the
                right setting for a demo on untrusted wifi.
            force_refresh: Fetch even if the cache is fresh.

        Returns:
            A CatalogSnapshot with the parsed objects and their provenance.

        Raises:
            RuntimeError: if no data can be obtained from either source.
        """
        warnings: List[str] = []
        cached = self._read_cache(group)

        if cached is not None and not force_refresh:
            text, fetched_at = cached
            age_hours = (
                datetime.now(timezone.utc) - fetched_at
            ).total_seconds() / 3600.0
            if age_hours <= max_cache_age_hours:
                objects, failures = parse_tle_text(text)
                self.logger.info(
                    "Using cached %s: %d objects, %.1f h old.",
                    group, len(objects), age_hours,
                )
                return CatalogSnapshot(
                    group=group, objects=objects, fetched_at=fetched_at,
                    from_cache=True, parse_failures=failures, warnings=warnings,
                )

        if allow_network:
            try:
                text = self._download(group)
                fetched_at = datetime.now(timezone.utc)
                self._write_cache(group, text, fetched_at)
                objects, failures = parse_tle_text(text)
                return CatalogSnapshot(
                    group=group, objects=objects, fetched_at=fetched_at,
                    from_cache=False, parse_failures=failures, warnings=warnings,
                )
            except RuntimeError as exc:
                if cached is None:
                    raise
                message = (
                    f"Network fetch failed ({exc}); falling back to the cached "
                    f"snapshot. Element sets are older than intended, so position "
                    f"uncertainty is correspondingly larger."
                )
                self.logger.warning(message)
                warnings.append(message)

        if cached is None:
            raise RuntimeError(
                f"No cached data for group {group!r} and network access is "
                f"disabled. Run with allow_network=True at least once, or use "
                f"scripts/fetch_catalog.py to populate the cache."
            )

        text, fetched_at = cached
        objects, failures = parse_tle_text(text)
        if not warnings:
            warnings.append(
                "Loaded from cache without a freshness check (network disabled)."
            )
        return CatalogSnapshot(
            group=group, objects=objects, fetched_at=fetched_at,
            from_cache=True, parse_failures=failures, warnings=warnings,
        )

    def fetch_groups(
        self,
        groups: List[str],
        max_cache_age_hours: float = DEFAULT_MAX_CACHE_AGE_HOURS,
        allow_network: bool = True,
        force_refresh: bool = False,
    ) -> List[TLEData]:
        """
        Load several groups and merge them, removing duplicate objects.

        Objects appear in more than one group -- a station is also an active
        satellite -- and screening the same object against itself would produce
        a spurious zero-distance conjunction.

        Returns:
            Deduplicated element sets, keeping the most recent epoch per object.
        """
        by_number: Dict[int, TLEData] = {}
        for group in groups:
            try:
                snapshot = self.fetch_group(
                    group, max_cache_age_hours, allow_network, force_refresh
                )
            except RuntimeError as exc:
                self.logger.error("Skipping group %r: %s", group, exc)
                continue

            for tle in snapshot.objects:
                existing = by_number.get(tle.satellite_number)
                if existing is None or tle.epoch > existing.epoch:
                    by_number[tle.satellite_number] = tle

        merged = list(by_number.values())
        self.logger.info(
            "Merged %d groups into %d unique objects.", len(groups), len(merged)
        )
        return merged


def load_catalog(
    group: str = "stations",
    allow_network: bool = True,
    max_cache_age_hours: float = DEFAULT_MAX_CACHE_AGE_HOURS,
) -> List[TLEData]:
    """
    Convenience wrapper returning just the element sets for one group.

    Args:
        group: CelesTrak group name.
        allow_network: False to work entirely from the committed cache.
        max_cache_age_hours: Freshness threshold before a refresh is attempted.

    Returns:
        Parsed TLEData objects.
    """
    return CelesTrakClient().fetch_group(
        group, max_cache_age_hours=max_cache_age_hours, allow_network=allow_network
    ).objects
