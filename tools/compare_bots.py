"""Play one version of the bot against another on the same decks, to see whether a change makes it win more (#354).

    python tools/compare_bots.py [--features timing,attack,...] [--against ""] [--games 40] [--workers 6] DECKLIST DECKLIST ...

The candidate (`--features`, default every judgment) plays the baseline (`--against`, default none: the plain bot) in
duels between each deck and the next one in the list, the candidate alternating seats. Each deck pair is played
once with each deck as the focus, so both sides of a pair are tried. Prints the candidate's win rate with its 95%
interval; a result whose interval holds 50% is not a difference. Run it from the repository root.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from functools import partial

sys.path.insert(0, os.getcwd())

from infernal_machine.bot import FEATURES, BotPlayer  # noqa: E402
from infernal_machine.cards import BulkSource, load_deck  # noqa: E402
from infernal_machine.matchup import matchups, wilson  # noqa: E402


def features(text: str) -> frozenset[str]:
    names = frozenset(part for part in text.split(",") if part)
    unknown = names - FEATURES
    if unknown:
        raise SystemExit(f"unknown features: {', '.join(sorted(unknown))} (known: {', '.join(sorted(FEATURES))})")
    return names


def save(path: str | None, args: argparse.Namespace, wins: int, games: int, errors: int) -> None:
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"features": args.features, "against": args.against, "pod": args.pod, "seed": args.seed,
                       "wins": wins, "games": games, "errors": errors}, f)


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decks", nargs="+")
    parser.add_argument("--features", default=",".join(sorted(FEATURES)))
    parser.add_argument("--against", default="")
    parser.add_argument("--games", type=int, default=40, help="per deck pair and direction (per deck with --pod)")
    parser.add_argument("--pod", type=int, default=2, help="players per game; above 2 the candidate sits with opponents drawn from the other decks")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--time-limit", type=float, default=60.0, help="seconds per game")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    parser.add_argument("--json", metavar="FILE", help="also write the totals here, for tools/bot_strength_summary.py")
    args = parser.parse_args()
    source = BulkSource(args.bulk)
    decks = {os.path.splitext(os.path.basename(p))[0]: load_deck(open(p, encoding="utf-8").read(), source) for p in args.decks}
    names = list(decks)
    candidate = partial(BotPlayer, features=features(args.features))
    baseline = partial(BotPlayer, features=features(args.against))
    wins = games = errors = 0
    if args.pod > 2:  # each deck takes a turn as the candidate's, against bots with the baseline features in the others' decks
        for name in names:
            others = {n: d for n, d in decks.items() if n != name}
            record, = matchups(decks[name], others, args.games, args.pod, args.seed, 120, args.time_limit, args.workers, candidate, baseline)
            wins, games, errors = wins + record.wins, games + record.games, errors + record.errors
            print(f"{name[:24]:<24} in a pod of {args.pod}: {record.wins}-{record.losses}-{record.draws}"
                  + (f"  [{record.errors} errors: {record.first_error}]" if record.errors else ""), flush=True)
        low, high = wilson(wins, games)
        print(f"\ncandidate [{args.features or 'plain'}] vs baseline [{args.against or 'plain'}] in pods of {args.pod}: {wins}/{games} = "
              f"{wins / games:.1%} (95% interval {low:.1%}-{high:.1%}; a fair share is {1 / args.pod:.0%}); {errors} crashed or timed out")
        save(args.json, args, wins, games, errors)
        return 0
    for i, name in enumerate(names):
        other = names[(i + 1) % len(names)]
        for focus, opponent in ((name, other), (other, name)):
            record, = matchups(decks[focus], {opponent: decks[opponent]}, args.games, 2, args.seed, 60, args.time_limit, args.workers, candidate, baseline)
            wins, games, errors = wins + record.wins, games + record.games, errors + record.errors
            print(f"{focus[:24]:<24} vs {opponent[:24]:<24} {record.wins}-{record.losses}-{record.draws}"
                  + (f"  [{record.errors} errors: {record.first_error}]" if record.errors else ""), flush=True)
    low, high = wilson(wins, games)
    print(f"\ncandidate [{args.features or 'plain'}] vs baseline [{args.against or 'plain'}]: {wins}/{games} = {wins / games:.1%} "
          f"(95% interval {low:.1%}-{high:.1%}); {errors} crashed or timed out")
    save(args.json, args, wins, games, errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
