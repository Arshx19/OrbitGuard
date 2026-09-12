"""
Tests for CelesTrak ingestion.

None of these touch the network. They run against the catalog snapshots
committed in `data/raw/`, which is the same path a demo takes on bad wifi, so
the offline behaviour is exercised rather than assumed.
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from app.core.tle_source import (  # noqa: E402
    CelesTrakClient,
    load_catalog,
    parse_tle_text,
    tle_age_days,
    tle_epoch_utc,
)

THREE_LINE = """ISS (ZARYA)
1 25544U 98067A   26255.20788499  .00004954  00000+0  97729-4 0  9996
2 25544  51.6305 229.4056 0004952 131.3152 228.8264 15.49086570585247
POISK
1 36086U 09060A   26255.20788499  .00004954  00000+0  97729-4 0  9994
2 36086  51.6305 229.4056 0004952 131.3152 228.8264 15.49086570586106
"""

TWO_LINE = """1 25544U 98067A   26255.20788499  .00004954  00000+0  97729-4 0  9996
2 25544  51.6305 229.4056 0004952 131.3152 228.8264 15.49086570585247
"""


class TestParsing:
    def test_three_line_format(self):
        objects, failures = parse_tle_text(THREE_LINE)
        assert len(objects) == 2
        assert failures == 0
        assert objects[0].object_name == "ISS (ZARYA)"
        assert objects[0].satellite_number == 25544
        assert objects[1].object_name == "POISK"

    def test_two_line_format(self):
        objects, failures = parse_tle_text(TWO_LINE)
        assert len(objects) == 1
        assert failures == 0
        assert objects[0].satellite_number == 25544
        # No name line available, so a stable fallback is used.
        assert "25544" in objects[0].object_name

    def test_blank_lines_and_comments_are_skipped(self):
        noisy = "# a comment\n\n" + THREE_LINE + "\n\n# trailing\n"
        objects, failures = parse_tle_text(noisy)
        assert len(objects) == 2
        assert failures == 0

    def test_a_malformed_record_does_not_desynchronise_the_rest(self):
        # This is the failure mode of a fixed-stride parser: one bad record and
        # every subsequent object is misread. Records are found by prefix here,
        # so the damage stays local.
        corrupted = (
            "JUNK OBJECT\n"
            "1 this is not a valid element line\n"
            + THREE_LINE
        )
        objects, _ = parse_tle_text(corrupted)
        assert len(objects) == 2
        assert {o.satellite_number for o in objects} == {25544, 36086}

    def test_every_object_gets_an_sgp4_record(self):
        objects, _ = parse_tle_text(THREE_LINE)
        assert all(o.satrec is not None for o in objects)

    def test_empty_input(self):
        objects, failures = parse_tle_text("")
        assert objects == []
        assert failures == 0


class TestEpoch:
    """
    Regression guard for the day-of-year conversion.

    TLEData._calculate_epoch converts day-of-year by subtracting 31 repeatedly,
    which treats every month as 31 days. It is exact in January and drifts to
    roughly six days by December. Element age feeds the position covariance
    behind every collision probability, so this has to stay correct.
    """

    def test_day_255_of_2026_is_12_september(self):
        objects, _ = parse_tle_text(THREE_LINE)
        epoch = tle_epoch_utc(objects[0])
        assert (epoch.year, epoch.month, epoch.day) == (2026, 9, 12)

    def test_epoch_is_timezone_aware_utc(self):
        objects, _ = parse_tle_text(THREE_LINE)
        assert tle_epoch_utc(objects[0]).tzinfo is timezone.utc

    def test_fractional_day_becomes_time_of_day(self):
        objects, _ = parse_tle_text(THREE_LINE)
        epoch = tle_epoch_utc(objects[0])
        # 0.20788499 of a day is 4h 59m 21s.
        assert (epoch.hour, epoch.minute) == (4, 59)

    @pytest.mark.parametrize(
        "day_of_year,expected_month,expected_day",
        [(1.0, 1, 1), (32.0, 2, 1), (60.0, 3, 1), (255.0, 9, 12), (365.0, 12, 31)],
    )
    def test_known_day_of_year_boundaries(self, day_of_year, expected_month, expected_day):
        # 2026 is not a leap year, so day 60 is 1 March.
        objects, _ = parse_tle_text(THREE_LINE)
        tle = objects[0]
        tle.epoch_day = day_of_year
        epoch = tle_epoch_utc(tle)
        assert (epoch.month, epoch.day) == (expected_month, expected_day)

    def test_age_is_never_negative(self):
        objects, _ = parse_tle_text(THREE_LINE)
        long_past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert tle_age_days(objects[0], long_past) > 0


class TestOfflineOperation:
    """The committed cache must be enough to run with no network at all."""

    def test_loads_from_committed_cache(self):
        objects = load_catalog("stations", allow_network=False)
        assert len(objects) > 0
        assert all(o.satrec is not None for o in objects)

    def test_snapshot_reports_its_provenance(self):
        client = CelesTrakClient()
        snapshot = client.fetch_group("stations", allow_network=False)
        assert snapshot.from_cache is True
        assert snapshot.age_hours >= 0
        assert snapshot.group == "stations"

    def test_a_stale_offline_read_warns(self):
        # Forcing the freshness threshold to zero drives the fall-through path:
        # the cache is considered out of date, the network is unavailable, and
        # the snapshot is returned anyway with the staleness declared rather
        # than silently passed off as current.
        client = CelesTrakClient()
        snapshot = client.fetch_group(
            "stations", max_cache_age_hours=0.0, allow_network=False
        )
        assert snapshot.from_cache is True
        assert snapshot.objects, "stale data is still better than no data"
        assert snapshot.warnings, "staleness must be surfaced, not hidden"

    def test_missing_group_offline_raises_clearly(self):
        client = CelesTrakClient()
        with pytest.raises(RuntimeError, match="No cached data"):
            client.fetch_group("no-such-group-exists", allow_network=False)

    def test_merging_groups_deduplicates(self):
        # Requesting the same group twice must not double the objects, or
        # screening would pair every object against itself at zero distance.
        client = CelesTrakClient()
        once = client.fetch_groups(["stations"], allow_network=False)
        twice = client.fetch_groups(["stations", "stations"], allow_network=False)
        assert len(once) == len(twice)

    def test_cached_objects_carry_usable_names(self):
        objects = load_catalog("stations", allow_network=False)
        names = {o.object_name for o in objects}
        assert any("ISS" in name for name in names)
