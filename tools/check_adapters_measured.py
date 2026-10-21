"""Fail when an Adapter launcher is absent from the combined coverage data.

Coverage reports an extension-less file only when something ran it, so an Adapter that no test runs would
otherwise be missing from the report and `fail_under = 100` would stay green.
"""

import json
import sys
from pathlib import Path

DATA = Path(".cov/coverage.json")


def main() -> int:
    measured = set(json.loads(DATA.read_text())["files"])
    launchers = [p for p in sorted(Path("adapters").iterdir()) if p.is_file() and not p.suffix]
    missing = [str(p) for p in launchers if str(p) not in measured]
    for path in missing:
        print(f"{path}: no test ran this Adapter", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
