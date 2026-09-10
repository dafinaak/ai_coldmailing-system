"""Print the source report for every zone, or for one (Jira AP-215).

Usage:
    .venv/bin/python werkzeuge/zone-source-report.py            all zones
    .venv/bin/python werkzeuge/zone-source-report.py --zone=36  one zone

Read-only: it reads the collection folders under laeufe/leadquellen/ and
changes nothing. What the numbers mean: pipeline/zone_sources.py.
"""
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline import zonen  # noqa: E402
from pipeline.zone_sources import format_report, zone_source_report  # noqa: E402


def main():
    zones = sorted(zonen.ZONEN)
    for arg in sys.argv[1:]:
        if arg.startswith("--zone="):
            zones = [arg.split("=", 1)[1]]
        else:
            sys.exit(f"Unknown argument: {arg}")
    for zone in zones:
        print(format_report(zone_source_report(zone)))
        print()


if __name__ == "__main__":
    main()
