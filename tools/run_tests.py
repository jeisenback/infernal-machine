"""Run the test suite in parallel processes (issue #441): python tools/run_tests.py [--jobs N] [MODULE ...]

The same tests as `python -m unittest discover -s tests -t .`, which takes about seven minutes in one process; CI runs this script instead (#519),
on the runner's four cores, with the times file restored from the last run. This
splits the test modules across processes (balanced by how long each took last time, kept in `.cache/test_times.json`, else by file
size) and prints the same kind of summary: the tests run, the failures with their tracebacks, and the time. Exit code 1 if anything failed.
Name modules (`tests.test_zone_plays`) to run only those.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.getcwd())  # (run from the repository root, as unittest discover is)

TIMES = os.path.join(".cache", "test_times.json")


def modules() -> list[str]:
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join("tests", "test_*.py")))


def balance(names: list[str], jobs: int, times: dict[str, float]) -> list[list[str]]:
    """Split `names` into `jobs` lists with about the same total time (the slowest first onto the lightest list)."""
    def cost(name: str) -> float:
        return times.get(name) or os.path.getsize(os.path.join("tests", name + ".py")) / 20000  # (a guess, in seconds, for a new module)

    shards: list[list[str]] = [[] for _ in range(jobs)]
    loads = [0.0] * jobs
    for name in sorted(names, key=cost, reverse=True):
        lightest = loads.index(min(loads))
        shards[lightest].append(name)
        loads[lightest] += cost(name)
    return [s for s in shards if s]


def worker(names: list[str]) -> int:
    """Run these test modules one after another; print one JSON line per module."""
    for name in names:
        stream = io.StringIO()
        start = time.time()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(unittest.defaultTestLoader.loadTestsFromName("tests." + name))
        print(json.dumps({"module": name, "run": result.testsRun, "seconds": round(time.time() - start, 2),
                          "bad": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses),
                          "output": stream.getvalue() if not result.wasSuccessful() else ""}), flush=True)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("modules", nargs="*", help="test modules to run (tests.test_x or test_x), default all")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--worker", nargs="+", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.worker)
    names = [m.removeprefix("tests.") for m in args.modules] or modules()
    try:
        with open(TIMES, encoding="utf-8") as f:
            times = json.load(f)
    except (OSError, ValueError):
        times = {}
    start = time.time()
    processes = [subprocess.Popen([sys.executable, __file__, "--worker", *shard], stdout=subprocess.PIPE, text=True, encoding="utf-8")
                 for shard in balance(names, args.jobs, times)]
    run = bad = 0
    report: list[str] = []
    for process in processes:
        out, _ = process.communicate()
        for line in out.splitlines():
            if not line.startswith("{"):
                continue
            row = json.loads(line)
            run += row["run"]
            bad += row["bad"]
            times[row["module"]] = row["seconds"]
            if row["bad"]:
                report.append(f"== {row['module']}\n{row['output']}")
        if process.returncode:
            bad += 1
            report.append(f"a worker exited with code {process.returncode}")
    os.makedirs(os.path.dirname(TIMES), exist_ok=True)
    with open(TIMES, "w", encoding="utf-8") as f:
        json.dump(times, f, indent=1, sort_keys=True)
    print("\n".join(report))
    print("-" * 70)
    print(f"Ran {run} tests in {time.time() - start:.1f}s across {len(processes)} processes")
    print("OK" if not bad else f"FAILED ({bad} module problems)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
