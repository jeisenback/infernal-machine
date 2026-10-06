"""Play four-player bot games and report how many finished with a winner.

    python tools/bot_games.py DECKLIST [--games 100] [--cache examples/demo_cards.json]

Every seat plays the same deck. A game that hits the turn cap counts as unfinished.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import CachedSource, ScryfallSource, load_deck
from infernal_machine.game import Game


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--cache", default=".cache/cards.json")
    args = parser.parse_args()

    deck = load_deck(Path(args.decklist).read_text(), CachedSource(ScryfallSource(), args.cache))
    finished, turns = 0, 0
    for seed in range(args.games):
        seats = [(BotPlayer(f"P{i}", deck), deck) for i in range(4)]
        game = Game(seats, seed=seed)
        if game.play(max_turns=args.max_turns) is not None:
            finished += 1
            turns += game.turn
    average = turns / finished if finished else 0
    print(f"{finished}/{args.games} games finished with a winner (avg {average:.1f} turns)")
    return 0 if finished == args.games else 1


if __name__ == "__main__":
    sys.exit(main())
