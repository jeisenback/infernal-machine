"""What a branch changes against main, as the sections of its pull request (the checks CI does not run).

    python tools/branch_report.py [--base origin/main] [--no-replay]

Checks the base out in a temporary worktree (sharing this checkout's `.cache`), runs the same measurements in both, and prints
markdown to paste into the pull request:

- the coverage audit's headline and its top-1000 row, before and after;
- the tracked decks of every format (`examples/decks` and its format folders), before and after;
- the template audit's lines that only one side prints (a template no sentence reaches, two templates reading a sentence
  differently), template numbers left out so a template added above another does not show every line as changed;
- the replay check: 24 four-player games recorded on the base and replayed on the branch (a change to play shows here; a speed
  pass or refactor must leave all 24 identical).

CI runs the tests, the type check, the tracked decks against their baselines, the misparse audit and the bot games; this does not
repeat them. It exits 1 if the replay differs, so a refactor can gate on it; for a change meant to alter play that is expected.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

FORMATS = ("", "standard", "pauper", "pioneer", "modern", "legacy", "vintage")  # "": the Commander decks in examples/decks
CACHE = ("oracle_bulk.json", "commander_pool.json", "cards.json")


def run(cwd: str, *args: str) -> str:
    done = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True)
    return done.stdout + done.stderr


def measure(cwd: str) -> dict[str, list[str]]:
    """The lines of each measurement that the report compares."""
    audit = run(cwd, "tools/coverage_audit.py", "--top", "1")
    found = {"coverage": [line.removeprefix("## Coverage audit: ") for line in audit.splitlines() if line.startswith("## Coverage audit")]
             + [f"top 1000: {m[1]}" for line in audit.splitlines() if (m := re.fullmatch(r"\| top 1000 \| (.+) \|", line))]}
    for name in FORMATS:
        folder = os.path.join("examples/decks", name)
        decks = sorted(os.path.join(folder, f) for f in os.listdir(os.path.join(cwd, folder)) if f.endswith(".txt"))
        out = run(cwd, "tools/coverage_audit.py", "--decks", *decks)
        found[name or "commander"] = [line.removeprefix("## Coverage for ") for line in out.splitlines() if line.startswith("## Coverage for")]
    templates = run(cwd, "tools/template_audit.py", "--top", "1000")
    found["templates"] = [re.sub(r"#\d+", "#", line) for line in templates.splitlines() if line.startswith(("- ", "| "))]
    return found


def report(base: dict[str, list[str]], branch: dict[str, list[str]], replay: str | None) -> str:
    lines = ["## Coverage", ""]
    for key in ("coverage", *(name or "commander" for name in FORMATS)):
        before, after = " / ".join(base[key]), " / ".join(branch[key])
        label = "pool" if key == "coverage" else f"{key} decks"
        lines.append(f"- {label}: {before}" + ("" if before == after else f"\n  -> {after}"))
    gone = [line for line in base["templates"] if line not in branch["templates"]]
    new = [line for line in branch["templates"] if line not in base["templates"]]
    lines += ["", "## Template audit", ""]
    lines += [f"- new: {line}" for line in new] + [f"- gone: {line}" for line in gone] or ["- no line differs from the base"]
    if replay is not None:
        lines += ["", "## Replay", "", *(f"    {line}" for line in replay.strip().splitlines()[-4:])]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main", help="the ref to compare with")
    parser.add_argument("--no-replay", action="store_true", help="leave out the replay check (about three minutes)")
    args = parser.parse_args(argv[1:])
    here = os.getcwd()
    with tempfile.TemporaryDirectory() as scratch:
        tree = os.path.join(scratch, "base")
        subprocess.run(["git", "worktree", "add", "--detach", "-q", tree, args.base], check=True)
        try:
            os.makedirs(os.path.join(tree, ".cache"), exist_ok=True)
            for name in CACHE:
                if os.path.exists(os.path.join(here, ".cache", name)):
                    os.symlink(os.path.join(here, ".cache", name), os.path.join(tree, ".cache", name))
            with ThreadPoolExecutor(2) as pool:  # each side's tools use the processors themselves; two sides at once still overlap
                base, branch = pool.map(measure, (tree, here))
            replay = None
            if not args.no_replay:
                record = os.path.join(scratch, "replay.json")
                run(tree, "tools/replay_check.py", "record", record)
                replay = run(here, "tools/replay_check.py", "check", record)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", tree], check=False)
    print(report(base, branch, replay))
    return 1 if replay is not None and not re.search(r"(\d+) of \1 games played identically", replay) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
