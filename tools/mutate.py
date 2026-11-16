"""Check guards by mutation: undo a guard, run the tests, see one fail (issue #810).

    python tools/mutate.py FILE OLD NEW --test tests.test_x [--test ...]   # one mutation
    python tools/mutate.py tests.test_x [tests.test_y ...]                 # the mutations a test module lists

A test module lists its mutations as `MUTATIONS = [(file, old, new), ...]` (or `(file, old, new, label)`), the guards its tests are
there to catch; the second form applies each in turn and runs that module's tests against it.

For each mutation the file's `old` text must occur exactly once, or the mutation is refused (an edit that would not apply is an
error, never a pass). The edit is applied, the tests run, and the file is put back from the bytes read before, whatever happens (never
through git, so nothing else in the working tree is touched). A mutation is caught when a test fails, and survived when none does; the tests are run once
without it first, and a mutation whose tests do not pass then (a misspelled module, a test already failing) is refused.
Exit 0 if every mutation was caught, 1 if one survived, 2 if one was refused.
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutation:
    file: str
    old: str
    new: str
    label: str = ""

    def name(self) -> str:
        return self.label or f"{self.file}: {self.old.strip().splitlines()[0][:60]}"


class Refused(Exception):
    """A mutation that cannot be applied as written."""


def apply(mutation: Mutation, root: Path) -> tuple[Path, bytes]:
    """Write the mutated file: (its path, its original bytes, to put back). Nothing is written if it is refused."""
    path = root / mutation.file
    if not path.is_file():
        raise Refused(f"{mutation.file}: no such file")
    original = path.read_bytes()
    text = original.decode("utf-8")
    count = text.count(mutation.old)
    if count != 1:
        raise Refused(f"{mutation.name()}: the text to replace occurs {count} times in {mutation.file}, not once")
    if mutation.old == mutation.new:
        raise Refused(f"{mutation.name()}: the replacement is the same text")
    path.write_bytes(text.replace(mutation.old, mutation.new, 1).encode("utf-8"))
    return path, original


def passes(tests: list[str], root: Path = ROOT, timeout: int = 600) -> bool:
    """Run `tests` (unittest module names) as the files stand: whether they all pass."""
    # A fresh, empty bytecode cache for each run: a mutation of the same size written within the same second would otherwise load
    # the cached code of the file before it, or of the mutation before it, and be reported for the wrong code.
    with tempfile.TemporaryDirectory() as cache:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": cache}
        run = subprocess.run([sys.executable, "-m", "unittest", "-q", *tests], cwd=root, capture_output=True, timeout=timeout, env=env)
        return run.returncode == 0


def caught(mutation: Mutation, tests: list[str], root: Path = ROOT, timeout: int = 600) -> bool:
    """Apply `mutation`, run `tests` and put the file back: whether a test failed."""
    path, original = apply(mutation, root)
    try:
        return not passes(tests, root, timeout)
    except subprocess.TimeoutExpired:
        return True  # (a test that hangs on the mutation has noticed it)
    finally:
        path.write_bytes(original)


def listed(module: str) -> list[Mutation]:
    """The mutations a test module lists in `MUTATIONS`."""
    found = getattr(importlib.import_module(module), "MUTATIONS", None)
    if not found:
        raise Refused(f"{module} lists no MUTATIONS")
    return [Mutation(*entry) for entry in found]


def run(plan: list[tuple[Mutation, list[str]]], root: Path = ROOT, out=sys.stdout) -> int:
    """Run each (mutation, tests) of the plan and report: the exit code."""
    survived = refused = 0
    baseline: dict[tuple[str, ...], bool] = {}
    for mutation, tests in plan:
        key = tuple(tests)
        if key not in baseline:
            baseline[key] = passes(tests, root)
        try:
            # A test run that fails without the mutation (a misspelled module, a test already failing) would count any mutation as caught.
            if not baseline[key]:
                raise Refused(f"{mutation.name()}: {' '.join(tests)} do not pass without the mutation")
            ok = caught(mutation, tests, root)
        except Refused as reason:
            refused += 1
            print(f"refused   {reason}", file=out)
            continue
        survived += not ok
        print(f"{'caught  ' if ok else 'SURVIVED'}  {mutation.name()}", file=out)
    print(f"{len(plan) - survived - refused} of {len(plan)} caught" + (f", {survived} survived" if survived else "")
          + (f", {refused} refused" if refused else ""), file=out)
    return 2 if refused else 1 if survived else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("args", nargs="+", help="FILE OLD NEW, or test modules that list MUTATIONS")
    parser.add_argument("--test", action="append", default=[], help="a test module to run (with FILE OLD NEW)")
    options = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    if options.test:
        if len(options.args) != 3:
            parser.error("with --test, give FILE OLD NEW")
        plan = [(Mutation(*options.args), options.test)]
    else:
        try:
            plan = [(mutation, [module]) for module in options.args for mutation in listed(module)]
        except Refused as reason:
            print(f"refused   {reason}")
            return 2
    return run(plan)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
