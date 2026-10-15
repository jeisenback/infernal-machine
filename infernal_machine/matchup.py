"""Matchups: play bot games between decks and report win rates.

    python -m infernal_machine.matchup DECKLIST OPPONENT [OPPONENT ...] [--games N] [--pod N] [--workers N]

The first deck is the one being tested. By default it plays `--games` duels against each opponent deck in turn (the
focus deck alternates seats). With `--pod 4` each game seats the focus deck with three opponents drawn at random from
the list, and the win rate is read against a fair share of 1/4. Every seat is a `BotPlayer`, so the numbers are how the
deck does in the bots' hands: a deck that needs careful play (combos, holding up mana, politics) is under-rated, and
one the bot plays well is over-rated. Compare builds of one deck against the same opponents rather than reading one
win rate as the deck's strength.

A game that crashes or runs past `--time-limit` seconds is counted apart (and the first error shown), not as a result.
"""

from __future__ import annotations

import ctypes
import io
import math
import random
import sys
import threading
import time
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from .bot import BotPlayer
from .brackets import analyze
from .cards import Deck
from .formats import format_of
from .game import Game
from .report import unplayable_cards, unplayable_note

EARLY_TURNS = 4  # the first turns of a seat, whose lands and spells say whether it stumbled


class _TimedOut(Exception):
    pass


@dataclass
class SeatLog:
    turns: int = 0
    lands: int = 0
    casts: int = 0
    lands_early: int | None = None  # lands played before the seat's turn EARLY_TURNS + 1, if it got that far
    casts_early: int | None = None

    @property
    def stumbled(self) -> bool:
        """Two lands or fewer after its first four turns."""
        return self.lands_early is not None and self.lands_early <= 2

    @property
    def idle(self) -> bool:
        """Three lands or more but at most one spell after its first four turns."""
        return self.casts_early is not None and (self.lands_early or 0) >= 3 and self.casts_early <= 1


@dataclass
class GameResult:
    focus_seat: int
    winner: int | None = None  # seat index; None for no winner by the turn limit
    turns: int = 0
    starting_seat: int = 0
    reasons: dict[int, str] = field(default_factory=dict)  # seat -> why it lost
    logs: dict[int, SeatLog] = field(default_factory=dict)
    error: str | None = None  # "timeout" or the exception


def play_one(decks: list[Deck], focus_seat: int, seed: int, max_turns: int = 60, time_limit: float = 120.0,
             bots: list | None = None) -> GameResult:
    """One game of bots, with `decks[focus_seat]` the deck being tested. `bots` makes each seat's player, as
    `bots[seat](name, deck)`; it defaults to `BotPlayer` everywhere (use `functools.partial` so a worker process can run it)."""
    makers = bots or [BotPlayer] * len(decks)
    game = Game([(make(f"P{i}", deck), deck) for i, (make, deck) in enumerate(zip(makers, decks))], seed=seed,
                format=format_of(decks))
    result = GameResult(focus_seat)
    logs = result.logs = {i: SeatLog() for i in range(len(decks))}
    deadline = time.monotonic() + time_limit
    forward = game.broadcast

    def tap(event: dict, skip=None) -> None:
        kind = event.get("event")
        if kind == "turn":
            log = logs[event["seat"]]
            if log.turns == EARLY_TURNS:
                log.lands_early, log.casts_early = log.lands, log.casts
            log.turns += 1
        elif kind == "play_land":
            logs[event["seat"]].lands += 1
        elif kind == "cast":
            logs[event["seat"]].casts += 1
        elif kind == "player_lost":
            result.reasons[event["seat"]] = event["reason"]
        if time.monotonic() > deadline:
            raise _TimedOut
        forward(event, skip)

    game.broadcast = tap  # type: ignore[method-assign]
    me = threading.get_ident()
    # A game stuck inside the engine sends no events, so the check in `tap` never runs: a timer raises in this thread instead.
    # It may only post that exception while the game is running. Posted earlier it lands inside `Thread.start()` (which waits on an
    # event, and then never wakes: a hung test run), posted later it lands in the clean-up; so it is armed once `start()` has
    # returned and disarmed, under the same lock the timer posts under, before the clean-up. A limit of zero starts no timer at all:
    # the check in `tap` ends the game at its first event.
    gate = threading.Lock()
    armed = False

    def expire() -> None:
        with gate:
            if armed:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(me), ctypes.py_object(_TimedOut))

    watchdog = threading.Timer(time_limit, expire)
    watchdog.daemon = True
    try:  # the outer try catches an exception posted just before the timer was disarmed
        try:
            if time_limit > 0:
                watchdog.start()
                armed = True
            winner = game.play(max_turns=max_turns)
            result.winner = winner.index if winner else None
        except _TimedOut:
            result.error = "timeout"
        except Exception as error:  # noqa: BLE001 - an engine crash is a finding, not a reason to stop the batch
            result.error = f"{type(error).__name__}: {error}"[:200]
        finally:
            with gate:
                armed = False
            watchdog.cancel()
    except _TimedOut:
        result.error = result.error or "timeout"
    result.turns, result.starting_seat = game.turn, game.starting_seat
    return result


def _run(task: tuple) -> GameResult:
    return play_one(*task)


def wilson(wins: int, games: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% interval for a win rate (it behaves at small counts and at 0% and 100%, unlike mean +- error)."""
    if games == 0:
        return 0.0, 1.0
    p = wins / games
    denominator = 1 + z * z / games
    centre = (p + z * z / (2 * games)) / denominator
    margin = z * math.sqrt(p * (1 - p) / games + z * z / (4 * games * games)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


@dataclass
class Record:
    opponent: str
    games: int  # finished games: wins + losses + draws
    wins: int = 0
    losses: int = 0
    draws: int = 0  # no winner by the turn limit
    errors: int = 0  # crashed or timed out
    first_error: str = ""
    fair_share: float = 0.5
    turns: float = 0.0  # average length of the finished games
    on_play: tuple[int, int] = (0, 0)  # (wins, games) when the focus deck went first
    on_draw: tuple[int, int] = (0, 0)
    how_lost: Counter = field(default_factory=Counter)  # the reason the focus deck lost
    how_won: Counter = field(default_factory=Counter)  # the reason the opponents lost, when the focus deck won
    stumbled: tuple[int, int] = (0, 0)  # (games, of which the focus deck won) with two lands or fewer after four turns
    idle: tuple[int, int] = (0, 0)  # likewise for three-plus lands but at most one spell
    focus_unplayable: tuple[tuple[str, int], ...] = ()  # (card, copies) in the focus deck that the engine can't fully play
    opponent_unplayable: tuple[tuple[str, int], ...] = ()  # likewise in the opponent deck(s) this record was played against
    bracket: tuple[int, ...] = ()  # the Commander Bracket floors of the opponent decks it was played against (none for decks without a commander)
    focus_bracket: int | None = None  # the focus deck's

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.wins, self.games)


def _record(name: str, results: list[GameResult], pod: int) -> Record:
    done = [r for r in results if r.error is None]
    record = Record(name, len(done), fair_share=1 / pod, errors=len(results) - len(done))
    record.first_error = next((r.error for r in results if r.error), "") or ""
    lengths = []
    play, draw, stumbled, idle = [0, 0], [0, 0], [0, 0], [0, 0]
    for r in done:
        lengths.append(r.turns)
        won = r.winner == r.focus_seat
        record.wins += won
        record.draws += r.winner is None
        record.losses += r.winner is not None and not won
        side = play if r.starting_seat == r.focus_seat else draw
        side[0] += won
        side[1] += 1
        log = r.logs[r.focus_seat]
        for flag, tally in ((log.stumbled, stumbled), (log.idle, idle)):
            if flag:
                tally[0] += 1
                tally[1] += won
        if r.focus_seat in r.reasons:
            record.how_lost[r.reasons[r.focus_seat]] += 1
        elif won:
            record.how_won.update(reason for seat, reason in r.reasons.items() if seat != r.focus_seat and reason != "opponent_won")
    record.turns = round(sum(lengths) / len(lengths), 1) if lengths else 0.0
    record.on_play, record.on_draw, record.stumbled, record.idle = tuple(play), tuple(draw), tuple(stumbled), tuple(idle)  # type: ignore[assignment]
    return record


def matchups(focus: Deck, opponents: dict[str, Deck], games: int = 40, pod: int = 2, seed: int = 0, max_turns: int = 60,
             time_limit: float = 120.0, workers: int = 1, focus_bot=BotPlayer, opponent_bot=BotPlayer) -> list[Record]:
    """Play `games` games for each opponent (a duel), or `games` pod games in all if `pod` is more than 2.
    `focus_bot` and `opponent_bot` make the players, to compare two versions of a bot on the same decks."""
    plans: list[tuple[str, list[tuple]]] = []
    if pod <= 2:
        groups = [(name, [deck]) for name, deck in opponents.items()]
    else:
        groups = [(f"pod of {pod}", None)]
    for name, fixed in groups:
        tasks = []
        for n in range(games):
            rng = random.Random(f"{seed}-{name}-{n}")
            others = fixed if fixed is not None else [opponents[k] for k in rng.choices(list(opponents), k=pod - 1)]
            seat = n % (len(others) + 1)
            decks = others[:seat] + [focus] + others[seat:]
            bots = [opponent_bot] * seat + [focus_bot] + [opponent_bot] * (len(others) - seat)
            tasks.append((decks, seat, zlib.crc32(f"{seed}-{name}-{n}".encode()), max_turns, time_limit, bots))
        plans.append((name, tasks))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(_chunk(pool, plans))
    else:
        results = [[_run(task) for task in tasks] for _, tasks in plans]
    records = [_record(name, rs, pod if pod > 2 else 2) for (name, _), rs in zip(plans, results)]
    focus_cards = _unplayable(focus)
    by_opponent = {name: _unplayable(deck) for name, deck in opponents.items()}
    everyone = tuple(sorted({item for cards in by_opponent.values() for item in cards}))  # a pod draws from all of them
    for record in records:
        record.focus_unplayable = focus_cards
        record.opponent_unplayable = everyone if pod > 2 else by_opponent.get(record.opponent, ())
    if focus.commanders:
        floor = {name: analyze(deck).floor for name, deck in opponents.items() if deck.commanders}
        for record in records:
            record.focus_bracket = analyze(focus).floor
            record.bracket = tuple(sorted({floor[n] for n in ([record.opponent] if pod <= 2 else opponents) if n in floor}))
    return records


def _unplayable(deck: Deck) -> tuple[tuple[str, int], ...]:
    return tuple((name, copies) for name, copies, _ in unplayable_cards(deck))


def within_bracket(opponents: dict[str, Deck], highest: int) -> tuple[dict[str, Deck], dict[str, int]]:
    """The opponents whose Bracket floor is at most `highest`, and the floors of the ones left out."""
    floors = {name: analyze(deck).floor for name, deck in opponents.items()}
    return ({n: d for n, d in opponents.items() if floors[n] <= highest}, {n: f for n, f in floors.items() if f > highest})


def _chunk(pool, plans):
    """Submit every game of every opponent before waiting, so all workers stay busy."""
    futures = [[pool.submit(_run, task) for task in tasks] for _, tasks in plans]
    for group in futures:
        yield [f.result() for f in group]


def _pct(wins_games: tuple[int, int]) -> str:
    wins, games = wins_games
    return f"{wins / games:.0%} of {games}" if games else "-"


def format_matchups(records: list[Record], focus: str = "focus deck") -> str:
    lines = [f"{focus} against bots. Win rate with its 95% interval (fair share {records[0].fair_share:.0%}); "
             "win rate when going first / second; why it lost.", ""]
    if records[0].focus_bracket is not None:
        ours = records[0].focus_bracket
        lines.insert(1, f"Bracket: the focus deck plays at Bracket {ours} or higher; opponents' floors: "
                        + ", ".join(f"{r.opponent} {'/'.join(map(str, r.bracket)) or '?'}" for r in records) + ".")
        stronger = sorted(r.opponent for r in records if any(b > ours for b in r.bracket))
        if stronger:
            lines.insert(2, f"Warning: {', '.join(stronger)} can only be played at a higher Bracket than the focus deck, so those win rates compare unlike decks.")
    lines.append(f"{'opponent':<30} {'W-L-D':>9}  {'win rate':<16} {'turns':>5}  {'first':<12} {'second':<12} how it lost")
    for r in records:
        low, high = r.interval
        rate = f"{r.win_rate:.0%} ({low:.0%}-{high:.0%})"
        lost = ", ".join(f"{reason} {count}" for reason, count in r.how_lost.most_common()) or "-"
        lines.append(f"{r.opponent[:30]:<30} {f'{r.wins}-{r.losses}-{r.draws}':>9}  {rate:<16} {r.turns:>5}  "
                     f"{_pct(r.on_play):<12} {_pct(r.on_draw):<12} {lost}")
    if records[0].focus_unplayable:
        lines.append(unplayable_note(records[0].focus_unplayable, "The focus deck") + " Its win rates are unreliable.")
    for r in records:
        if r.opponent_unplayable:
            lines.append(unplayable_note(r.opponent_unplayable, f"Opponent {r.opponent}") + " Results against it are unreliable.")
    total = sum(r.games for r in records)
    if total:
        stumbled = [sum(r.stumbled[i] for r in records) for i in (0, 1)]
        idle = [sum(r.idle[i] for r in records) for i in (0, 1)]
        overall = sum(r.wins for r in records)
        lines += ["", f"Overall {overall}/{total} ({overall / total:.0%})."]
        if stumbled[0]:
            lines.append(f"Stumbled on lands (two or fewer after four turns) in {stumbled[0] / total:.0%} of games, winning {stumbled[1] / stumbled[0]:.0%} of them.")
        if idle[0]:
            lines.append(f"Had the lands but cast at most one spell in four turns in {idle[0] / total:.0%} of games, winning {idle[1] / idle[0]:.0%} of them.")
    for r in records:
        if r.errors:
            lines.append(f"{r.opponent}: {r.errors} game(s) crashed or timed out and are not counted. First: {r.first_error}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse
    import os

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist", help="the deck being tested")
    parser.add_argument("opponents", nargs="+", help="decklists to play against")
    parser.add_argument("--games", type=int, default=40, help="per opponent (or in total with --pod)")
    parser.add_argument("--pod", type=int, default=2, help="players per game; above 2 draws the opponents at random")
    parser.add_argument("--max-bracket", type=int, metavar="N", help="leave out opponents that can only be played at a Bracket above N")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--time-limit", type=float, default=120.0, help="seconds per game")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    source = BulkSource(args.bulk)

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return load_deck(f.read(), source)

    opponents = {os.path.splitext(os.path.basename(p))[0]: load(p) for p in args.opponents}
    if args.max_bracket is not None:
        opponents, left_out = within_bracket(opponents, args.max_bracket)
        for name, floor in left_out.items():
            print(f"Leaving out {name}: it plays at Bracket {floor} or higher.", file=sys.stderr)
        if not opponents:
            print("No opponent is left.", file=sys.stderr)
            return 2
    records = matchups(load(args.decklist), opponents, args.games, args.pod, args.seed, args.max_turns, args.time_limit, args.workers)
    print(format_matchups(records, os.path.splitext(os.path.basename(args.decklist))[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
