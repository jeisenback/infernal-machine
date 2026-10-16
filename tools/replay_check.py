"""Record bot games, then check that a change left play untouched and see how much faster it is (issue #392).

    python tools/replay_check.py record FILE [--seeds 0-23] [--workers 6]
    python tools/replay_check.py check FILE [--workers 6]

`record` plays the four-player precon games of `tools/bot_games.py` (seed `g` is game `g`) and saves, for each seed, a hash of every
event the game broadcast, plus the winner, the turn it ended on, the final life totals and permanent counts, and the CPU seconds it
took. `check` replays the same seeds with the code as it is now and compares: one different event anywhere in a game changes its hash,
so "identical" means the game was played the same move for move, which is far stricter than the same winner. It then prints the speed
before and after (the median game and the total), from CPU time, which a busy machine disturbs less than the clock. Exits 1 if any game
differs. Run it from the repository root; it needs `.cache/oracle_bulk.json`.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.getcwd())

from infernal_machine.bot import BotPlayer  # noqa: E402
from infernal_machine.cards import BulkSource, load_deck  # noqa: E402
from infernal_machine.game import Game  # noqa: E402

_DECKS: list = []


def _load(bulk: str) -> None:
    source = BulkSource(bulk)
    _DECKS[:] = [(os.path.basename(path).split("_")[0], load_deck(open(path, encoding="utf-8").read(), source))
                 for path in sorted(glob.glob("examples/precons/*.txt"))]


def play(args: tuple[int, int]) -> dict:
    """One game: its fingerprint and how long it took in CPU seconds."""
    seed, max_turns = args
    picks = random.Random(seed).sample(_DECKS, 4)
    game = Game([(BotPlayer(name, deck), deck) for name, deck in picks], seed=seed)
    digest, events = hashlib.sha256(), [0]
    forward = game.broadcast

    def tap(event: dict, skip=None) -> None:
        digest.update(repr(sorted(event.items())).encode())
        events[0] += 1
        forward(event, skip)

    game.broadcast = tap  # type: ignore[method-assign]
    started = time.process_time()
    winner = game.play(max_turns=max_turns)
    return {"seed": seed, "winner": winner.index if winner else None, "turn": game.turn, "ended": game.ended,
            "life": [s.life for s in game.seats], "permanents": [len(s.battlefield) for s in game.seats],
            "events": events[0], "hash": digest.hexdigest(), "cpu": round(time.process_time() - started, 3)}


def parse_seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        low, _, high = part.partition("-")
        seeds += range(int(low), int(high or low) + 1)
    return seeds


def run(seeds: list[int], max_turns: int, workers: int, bulk: str) -> list[dict]:
    with ProcessPoolExecutor(max_workers=workers, initializer=_load, initargs=(bulk,)) as pool:
        return list(pool.map(play, [(seed, max_turns) for seed in seeds], chunksize=1))


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def speed(label: str, games: list[dict]) -> str:
    cpu = [g["cpu"] for g in games]
    return f"{label}: median game {statistics.median(cpu):.1f} s, total {sum(cpu):.0f} s over {len(cpu)} games"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("mode", choices=["record", "check"])
    parser.add_argument("file")
    parser.add_argument("--seeds", default="0-23", help="seeds to record, like 0-23 or 3,9,40-45 (record only)")
    parser.add_argument("--turns", type=int, default=200, help="a game still going after this many turns is a draw")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    if args.mode == "record":
        games = run(parse_seeds(args.seeds), args.turns, args.workers, args.bulk)
        with open(args.file, "w", encoding="utf-8") as f:
            json.dump({"commit": commit(), "turns": args.turns, "games": games}, f)
        print(f"recorded {len(games)} games at {commit() or 'an unknown commit'}. {speed('now', games)}")
        return 0
    with open(args.file, encoding="utf-8") as f:
        saved = json.load(f)
    now = run([g["seed"] for g in saved["games"]], saved["turns"], args.workers, args.bulk)
    keys = ("winner", "turn", "ended", "life", "permanents", "events", "hash")
    different = [(a, b) for a, b in zip(saved["games"], now) if any(a[k] != b[k] for k in keys)]
    for before, after in different:
        what = [k for k in keys if before[k] != after[k]]
        print(f"seed {before['seed']} DIFFERS in {', '.join(what)}: " + "; ".join(f"{k} {before[k]} -> {after[k]}" for k in what if k != "hash"))
    print(f"{len(now) - len(different)} of {len(now)} games played identically (recorded at {saved['commit'] or '?'}, now {commit() or '?'}).")
    before_cpu, after_cpu = [g["cpu"] for g in saved["games"]], [g["cpu"] for g in now]
    print(speed("before", saved["games"]))
    print(speed("after ", now))
    print(f"median game {statistics.median(before_cpu) / statistics.median(after_cpu):.2f}x, total {sum(before_cpu) / sum(after_cpu):.2f}x")
    return 1 if different else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
