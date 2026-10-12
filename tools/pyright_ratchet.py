"""The pyright error count may fall but not rise (issue #309).

    python -m pyright > pyright.txt; python tools/pyright_ratchet.py pyright.txt [--baseline .github/pyright-baseline]

Reads pyright's output, finds its last line ("398 errors, 0 warnings, 0 informations"), and compares the count with the number in
the baseline file. Exits 1 if the count is higher than the baseline, or if no count can be read (a pyright that did not run must not
pass). A lower count passes and says to lower the baseline. When the baseline is 0 this is a plain "no type errors" check.
Writes its line to the GitHub step summary when `GITHUB_STEP_SUMMARY` is set.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

_SUMMARY = re.compile(r"^(\d+) errors?, \d+ warnings?, \d+ informations?", re.M)


def count_errors(output: str) -> int | None:
    """The error count on pyright's summary line, or None if the output has none."""
    found = _SUMMARY.findall(output)
    return int(found[-1]) if found else None


def check(count: int | None, baseline: int) -> tuple[bool, str]:
    """Whether the count passes the ratchet, and the line to print."""
    if count is None:
        return False, "pyright printed no summary line, so its error count is unknown"
    if count > baseline:
        return False, f"pyright: {count} errors, {count - baseline} more than the baseline of {baseline}"
    if count < baseline:
        return True, f"pyright: {count} errors, below the baseline of {baseline}: lower .github/pyright-baseline to {count}"
    return True, f"pyright: {count} errors, the baseline"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="a file with pyright's output")
    parser.add_argument("--baseline", default=".github/pyright-baseline")
    args = parser.parse_args(argv)
    with open(args.output, encoding="utf-8") as f:
        count = count_errors(f.read())
    with open(args.baseline, encoding="utf-8") as f:
        baseline = int(f.read().strip())
    ok, line = check(count, baseline)
    print(line)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
