"""
Populate the local TLE cache from CelesTrak.

Run this once before a demo so the screening pipeline never depends on venue
wifi. Snapshots land in `data/raw/` and are committed to the repository, so a
fresh clone can screen conjunctions with no network at all.

    .venv/Scripts/python.exe scripts/fetch_catalog.py                 # default set
    .venv/Scripts/python.exe scripts/fetch_catalog.py --groups active
    .venv/Scripts/python.exe scripts/fetch_catalog.py --list
    .venv/Scripts/python.exe scripts/fetch_catalog.py --offline       # verify cache

Please do not run this in a loop. CelesTrak is a free service and element sets
are only regenerated a few times a day, so refetching more often than that costs
them bandwidth and gains you nothing.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.tle_source import (  # noqa: E402
    USEFUL_GROUPS,
    CelesTrakClient,
    tle_age_days,
)

# A small default set: crewed stations as recognisable primaries, plus two dense
# debris clouds that generate genuine close approaches rather than contrived
# ones. Around 2,000 objects in total -- enough to be a real screening problem,
# small enough to propagate quickly during a demo.
DEFAULT_GROUPS = ["stations", "iridium-33-debris", "cosmos-1408-debris"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--groups", nargs="+", default=DEFAULT_GROUPS,
        help=f"CelesTrak groups to fetch. Default: {' '.join(DEFAULT_GROUPS)}",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Do not touch the network; report on what is already cached.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Refetch even when the cached snapshot is still fresh.",
    )
    parser.add_argument(
        "--list", action="store_true", help="List the known groups and exit."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

    if args.list:
        print("\nCelesTrak groups useful for conjunction screening:\n")
        for name, description in sorted(USEFUL_GROUPS.items()):
            print(f"  {name:<22} {description}")
        print()
        return 0

    client = CelesTrakClient()
    now = datetime.now(timezone.utc)
    total = 0
    failed = []

    print()
    for group in args.groups:
        try:
            snapshot = client.fetch_group(
                group, allow_network=not args.offline, force_refresh=args.force
            )
        except RuntimeError as exc:
            print(f"  {group:<22} FAILED: {exc}")
            failed.append(group)
            continue

        ages = [tle_age_days(tle, now) for tle in snapshot.objects]
        median_age = sorted(ages)[len(ages) // 2] if ages else float("nan")
        origin = "cache" if snapshot.from_cache else "network"

        print(
            f"  {group:<22} {len(snapshot):>6} objects  "
            f"({origin}, snapshot {snapshot.age_hours:5.1f} h old, "
            f"median element age {median_age:.2f} d)"
        )
        if snapshot.parse_failures:
            print(f"  {'':<22} {snapshot.parse_failures} record(s) failed to parse")
        for warning in snapshot.warnings:
            print(f"  {'':<22} WARNING: {warning}")
        total += len(snapshot)

    print(f"\n  {'TOTAL':<22} {total:>6} objects across {len(args.groups)} group(s)")
    if failed:
        print(f"  Failed groups: {', '.join(failed)}")
    print(f"  Cache directory: {client.cache_dir}\n")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
