"""Play bot games between the precon decks and report any that crash (issue #25).

    python tools/bot_games.py [--games 20] [--start 0] [--turns 200] [--bulk .cache/oracle_bulk.json]

Game `g` is seeded with `g` (the seed also picks which four decks play), so a failing seed can be replayed with
`--start SEED --games 1`. Exits 1 if any game raised. Run it from the repository root; shards of the same run
use different `--start` values.
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import random
import sys
import time
import traceback

sys.path.insert(0, os.getcwd())

from infernal_machine.bot import BotPlayer  # noqa: E402
from infernal_machine.cards import BulkSource, load_deck  # noqa: E402
from infernal_machine.game import BOARD_LIMIT, Game  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--start", type=int, default=0, help="seed of the first game")
    parser.add_argument("--turns", type=int, default=200, help="a game still going after this many turns is a draw")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)

    source = BulkSource(args.bulk)
    decks = [(os.path.basename(path).split("_")[0], load_deck(open(path).read(), source))
             for path in sorted(glob.glob("examples/precons/*.txt"))]
    wins: collections.Counter = collections.Counter()
    crashes: list[tuple[int, list[str], str]] = []
    limited: list[int] = []  # games that ended because the board passed the permanent limit: a runaway, not a crash
    looped: list[int] = []  # games drawn by a loop of mandatory actions whose state came back (CR 104.4b)
    limit = BOARD_LIMIT
    started = time.time()
    for seed in range(args.start, args.start + args.games):
        picks = random.Random(seed).sample(decks, 4)
        game = Game([(BotPlayer(name, deck), deck) for name, deck in picks], seed=seed)
        try:
            winner = game.play(max_turns=args.turns)
        except Exception:
            crashes.append((seed, [name for name, _ in picks], traceback.format_exc()))
        else:
            if winner is not None:
                wins[winner.player.name] += 1
            if game.ended == "board_limit":
                limited.append(seed)
                limit = game.board_limit or BOARD_LIMIT
            elif game.ended == "loop":
                looped.append(seed)
    print(f"games {args.start}..{args.start + args.games - 1}: {args.games - len(crashes)} finished, "
          f"{len(crashes)} crashed, wins {dict(wins)}, {time.time() - started:.0f}s")
    if limited:
        print(f"{len(limited)} ended as draws at the board limit ({limit} permanents), seeds {limited}: a token engine out of control. "
              "Replay one with --start SEED --games 1.")
    if looped:
        print(f"{len(looped)} ended as draws by a loop, seeds {looped}. Replay one with --start SEED --games 1.")
    for seed, names, trace in crashes:
        print(f"\nseed {seed} ({', '.join(names)}):\n{trace}")
    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
