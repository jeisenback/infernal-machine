"""Matchups: play bot games between decks and report win rates.

    python -m infernal_machine.matchup DECKLIST OPPONENT [OPPONENT ...] [--games N] [--pod N] [--workers N]

The first deck is the one being tested. By default it plays `--games` duels against each opponent deck in turn (the
focus deck alternates seats). With `--pod 4` each game seats the focus deck with three opponents drawn at random from
the list, and the win rate is read against a fair share of 1/4. Every seat is a `BotPlayer`, so the numbers are how the
deck does in the bots' hands: a deck that needs careful play (holding up mana, politics) is under-rated, and
one the bot plays well is over-rated. A combo is not much of that: once its pieces are out the engine plays its
triggers (Edgar Markov's life-drain pair kills the table on its own), and the bot's part is finding the pieces, which
the "tutor" judgment helps with (doubling how often they meet, worth a few points of win rate at most; #490). Compare
builds of one deck against the same opponents rather than reading one win rate as the deck's strength.

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
from .formats import add_format_argument, format_of, house_rules, with_format
from .gauntlet import deck_format, opponent_paths
from .game import BOARD_LIMIT, Game
from .report import unplayable_cards, unplayable_note
from .sequential import MIN_LOOK_PAIRS, confidence, look_z, schedule

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
    cast_names: list[str] = field(default_factory=list)  # every spell it cast, by name (what sideboarding looks at)

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
    ended: str | None = None  # why it stopped without a winner, if the game said ("board_limit")
    reasons: dict[int, str] = field(default_factory=dict)  # seat -> why it lost
    logs: dict[int, SeatLog] = field(default_factory=dict)
    error: str | None = None  # "timeout" or the exception
    seed: int | None = None  # the game's seed (a game replays from its decks, seat and seed), set by `play_one`
    games: list = field(default_factory=list)  # for a match (`match.play_match`), the games of it; then everything above is about the match


def play_one(decks: list[Deck], focus_seat: int, seed: int, max_turns: int = 60, time_limit: float = 120.0,
             bots: list | None = None) -> GameResult:
    """One game of bots, with `decks[focus_seat]` the deck being tested. `bots` makes each seat's player, as
    `bots[seat](name, deck)`; it defaults to `BotPlayer` everywhere (use `functools.partial` so a worker process can run it)."""
    makers = bots or [BotPlayer] * len(decks)
    game = Game([(make(f"P{i}", deck), deck) for i, (make, deck) in enumerate(zip(makers, decks))], seed=seed,
                format=format_of(decks))
    result = GameResult(focus_seat, seed=seed)
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
            logs[event["seat"]].cast_names.append(event["card"])
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
    result.turns, result.starting_seat, result.ended = game.turn, game.starting_seat, game.ended
    return result


def _run(task: tuple) -> GameResult:
    """One planned game, or, when the task carries a `best_of` above one after the six arguments of `play_one`, a match."""
    if len(task) > 6 and task[6] > 1:
        from .match import play_match  # (match.py builds on this module)
        return play_match(*task[:6], best_of=task[6])
    return play_one(*task[:6])


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
    draws: int = 0  # no winner by the turn limit, or because the board passed the limit (counted in `board_limit` too)
    board_limit: int = 0  # games that ended because the board passed BOARD_LIMIT permanents
    errors: int = 0  # crashed or timed out
    first_error: str = ""
    first_error_at: str = ""  # which game it was: its seed and the focus seat, to replay it
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
    best_of: int = 1  # above one, `games`, `wins`... count matches and `game_record` counts the games in them
    game_record: tuple[int, int, int] = (0, 0, 0)  # (won, lost, drawn) over the games of the matches
    z: float = 1.96  # the width of `interval` in standard errors (wider when games were played in rounds and looked at between them)
    planned: int = 0  # games an early-stopping run planned against this opponent (0: it did not stop early)
    stopped: str | None = None  # "better" or "worse" than the fair share, if it stopped before playing every planned game
    looks: int = 1

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.wins, self.games, self.z)


def _record(name: str, results: list[GameResult], pod: int, best_of: int = 1) -> Record:
    done = [r for r in results if r.error is None]
    record = Record(name, len(done), fair_share=1 / pod, errors=len(results) - len(done), best_of=best_of)
    if best_of > 1:
        from .match import game_record  # (match.py builds on this module)
        won = lost = drawn = 0
        for r in done:
            w, l, d = game_record(r)
            won, lost, drawn = won + w, lost + l, drawn + d
        record.game_record = (won, lost, drawn)
    failed = next((r for r in results if r.error), None)
    if failed is not None:
        record.first_error = failed.error or ""
        record.first_error_at = f"seed {failed.seed}, focus seat {failed.focus_seat}" if failed.seed is not None else ""
    lengths = []
    play, draw, stumbled, idle = [0, 0], [0, 0], [0, 0], [0, 0]
    for r in done:
        lengths.append(r.turns)
        won = r.winner == r.focus_seat
        record.wins += won
        record.draws += r.winner is None
        record.board_limit += r.ended == "board_limit"
        record.losses += r.winner is not None and not won
        side = play if r.starting_seat == r.focus_seat else draw
        side[0] += won
        side[1] += 1
        log = r.logs[r.focus_seat]
        for flag, tally in ((log.stumbled, stumbled), (log.idle, idle)):
            if flag:
                tally[0] += 1
                tally[1] += won
        for g in (r.games or [r]):  # a match's reasons are those of its games
            if g.error is not None:
                continue
            if g.focus_seat in g.reasons:
                record.how_lost[g.reasons[g.focus_seat]] += 1
            elif g.winner == g.focus_seat:
                record.how_won.update(reason for seat, reason in g.reasons.items() if seat != g.focus_seat and reason != "opponent_won")
    record.turns = round(sum(lengths) / len(lengths), 1) if lengths else 0.0
    record.on_play, record.on_draw, record.stumbled, record.idle = tuple(play), tuple(draw), tuple(stumbled), tuple(idle)  # type: ignore[assignment]
    return record


def plan_games(focus: Deck, opponents: dict[str, Deck], games: int, pod: int, seed: int, max_turns: int, time_limit: float,
               focus_bot=BotPlayer, opponent_bot=BotPlayer, best_of: int = 1) -> list[tuple[str, list[tuple]]]:
    """The games `matchups` plays, as (opponent or pod, tasks) in order. Game `n` against an opponent is the same seed, seat and
    opponents whatever the focus deck is, so two builds planned with one seed play paired games (see compare.py)."""
    plans: list[tuple[str, list[tuple]]] = []
    if best_of > 1 and pod > 2:
        raise ValueError("A match is between two decks: best-of-three is for duels, not pods")
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
            tasks.append((decks, seat, zlib.crc32(f"{seed}-{name}-{n}".encode()), max_turns, time_limit, bots) + ((best_of,) if best_of > 1 else ()))
        plans.append((name, tasks))
    return plans


def play_plans(plans: list[tuple[str, list[tuple]]], workers: int = 1) -> list[list[GameResult]]:
    """Play every planned game, in parallel with `workers` > 1; one list of results per plan, in the order planned."""
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            return list(_chunk(pool, plans))
    return [[_run(task) for task in tasks] for _, tasks in plans]


def win_stop(wins: int, games: int, fair_share: float, z: float, final: bool) -> str | None:
    """"better" or "worse" when a win rate's interval (widened to `z`) leaves out the fair share, once there are `MIN_LOOK_PAIRS` games;
    None while it is still within noise. The last look never stops early. (A matchup has no "hopeless" stop: resolving a few points of
    win rate takes hundreds of games whatever was planned, so a run that stays within noise just plays its games.)"""
    if final or games < MIN_LOOK_PAIRS:
        return None
    low, high = wilson(wins, games, z)
    return "better" if low > fair_share else "worse" if high < fair_share else None


def _play_matchups_in_rounds(plans: list[tuple[str, list[tuple]]], games: int, pod: int,
                             workers: int) -> tuple[list[list[GameResult]], dict[str, str], int, float]:
    """Play every opponent's games a round at a time and look after each; an opponent whose win rate is clearly away from the fair share
    stops there. Returns (the results per plan, why each stopped, the looks, the interval width)."""
    looks, batch = schedule(games)
    z = look_z(looks)
    fair = 1 / (pod if pod > 2 else 2)
    results: list[list[GameResult]] = [[] for _ in plans]
    active = list(range(len(plans)))
    stopped: dict[str, str] = {}
    for look in range(1, looks + 1):
        lo, hi = (look - 1) * batch, min(games, look * batch)
        for i, new in zip(active, play_plans([(plans[i][0], plans[i][1][lo:hi]) for i in active], workers)):
            results[i] += new
        for i in list(active):
            done = [r for r in results[i] if r.error is None]
            reason = win_stop(sum(r.winner == r.focus_seat for r in done), len(done), fair, z, look == looks)
            if reason:
                stopped[plans[i][0]] = reason
                active.remove(i)
        if not active:
            break
    return results, stopped, looks, z


def matchups(focus: Deck, opponents: dict[str, Deck], games: int = 40, pod: int = 2, seed: int = 0, max_turns: int = 60,
             time_limit: float = 120.0, workers: int = 1, focus_bot=BotPlayer, opponent_bot=BotPlayer, early_stop: bool = False,
             best_of: int = 1) -> list[Record]:
    """Play `games` games for each opponent (a duel), or `games` pod games in all if `pod` is more than 2.
    `focus_bot` and `opponent_bot` make the players, to compare two versions of a bot on the same decks. With `early_stop`, the games are
    played in rounds and an opponent is dropped once the win rate against it is clearly above or below the fair share (see
    `sequential.py` for the rule). With `best_of` above one, each of the `games` is a match of up to that many games with sideboarding
    (`match.py`), and the win rate is the match win rate."""
    plans = plan_games(focus, opponents, games, pod, seed, max_turns, time_limit, focus_bot, opponent_bot, best_of)
    rounds = early_stop and games > 1
    stopped: dict[str, str] = {}
    looks, z = 1, 1.96
    if rounds:
        results, stopped, looks, z = _play_matchups_in_rounds(plans, games, pod, workers)
    else:
        results = play_plans(plans, workers)
    records = [_record(name, rs, pod if pod > 2 else 2, best_of) for (name, _), rs in zip(plans, results)]
    if rounds:
        for record in records:
            record.z, record.looks, record.planned, record.stopped = z, looks, games, stopped.get(record.opponent)
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


def format_matchups(records: list[Record], focus: str = "focus deck", *, focus_warning: bool = True) -> str:
    lines = [f"{focus} against bots. Win rate with its {confidence(records[0].z)} interval (fair share {records[0].fair_share:.0%}); "
             "win rate when going first / second; why it lost.", ""]
    if records[0].focus_bracket is not None:
        ours = records[0].focus_bracket
        lines.insert(1, f"Bracket: the focus deck plays at Bracket {ours} or higher; opponents' floors: "
                        + ", ".join(f"{r.opponent} {'/'.join(map(str, r.bracket)) or '?'}" for r in records) + ".")
        stronger = sorted(r.opponent for r in records if any(b > ours for b in r.bracket))
        if stronger:
            lines.insert(2, f"Warning: {', '.join(stronger)} can only be played at a higher Bracket than the focus deck, so those win rates compare unlike decks.")
    matches = records[0].best_of > 1
    if matches:
        lines.insert(1, f"Best of {records[0].best_of} with sideboarding: W-L-D and the win rate are matches; the games column is the games in them.")
    lines.append(f"{'opponent':<30} {'W-L-D':>9}  {'win rate':<16} {'turns':>5}  " + (f"{'games':>9}  " if matches else "")
                 + f"{'first':<12} {'second':<12} how it lost")
    for r in records:
        low, high = r.interval
        rate = f"{r.win_rate:.0%} ({low:.0%}-{high:.0%})"
        lost = ", ".join(f"{reason} {count}" for reason, count in r.how_lost.most_common()) or "-"
        games = f"{'-'.join(map(str, r.game_record)):>9}  " if matches else ""
        lines.append(f"{r.opponent[:30]:<30} {f'{r.wins}-{r.losses}-{r.draws}':>9}  {rate:<16} {r.turns:>5}  {games}"
                     f"{_pct(r.on_play):<12} {_pct(r.on_draw):<12} {lost}")
    if records[0].planned:  # played in rounds
        lines.append(f"Stopping rule: {records[0].looks} looks; each look's interval is widened to {confidence(records[0].z)} so the chance of a false "
                     "'clearly better or worse' against an opponent whose true win rate is the fair share stays under 5%. An opponent is dropped "
                     f"when its interval leaves out the fair share, after {MIN_LOOK_PAIRS} games at the earliest.")
        lines += [f"{r.opponent}: stopped after {r.games} of {r.planned} planned games: clearly {r.stopped} than the fair share."
                  for r in records if r.stopped]
    if records[0].focus_unplayable and focus_warning:  # (`analyze` says it once, at the top)
        lines.append(unplayable_note(records[0].focus_unplayable, "The focus deck") + " Its win rates are unreliable.")
    for r in records:
        if r.opponent_unplayable:
            lines.append(unplayable_note(r.opponent_unplayable, f"Opponent {r.opponent}") + " Results against it are unreliable.")
    for r in records:
        if r.board_limit:
            lines.append(f"{r.opponent}: {r.board_limit} game(s) ended as draws because the board passed {BOARD_LIMIT} permanents (a token engine "
                         "out of control); they are in the D column.")
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
    parser.add_argument("opponents", nargs="*", help="decklists to play against (default: the saved gauntlet, see gauntlet.py)")
    parser.add_argument("--games", type=int, default=40, help="per opponent (or in total with --pod)")
    parser.add_argument("--pod", type=int, default=2, help="players per game; above 2 draws the opponents at random")
    add_format_argument(parser)
    parser.add_argument("--best-of", type=int, default=1, metavar="N", help="play matches of up to N games with sideboarding (Standard is best of three); duels only")
    parser.add_argument("--max-bracket", type=int, metavar="N", help="leave out opponents that can only be played at a Bracket above N")
    parser.add_argument("--early-stop", action="store_true", help="play in rounds and drop an opponent once its win rate is clearly above or below the fair share")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--time-limit", type=float, default=120.0, help="seconds per game")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    source = BulkSource(args.bulk)

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return with_format(load_deck(f.read(), source), args.format)

    focus = load(args.decklist)
    opponents = {os.path.splitext(os.path.basename(p))[0]: load(p) for p in opponent_paths(args.opponents, args.max_bracket, format=deck_format(focus))}
    if args.max_bracket is not None:
        opponents, left_out = within_bracket(opponents, args.max_bracket)
        for name, floor in left_out.items():
            print(f"Leaving out {name}: it plays at Bracket {floor} or higher.", file=sys.stderr)
        if not opponents:
            print("No opponent is left.", file=sys.stderr)
            return 2
    records = matchups(focus, opponents, args.games, args.pod, args.seed, args.max_turns, args.time_limit, args.workers,
                       early_stop=args.early_stop, best_of=args.best_of)
    if note := house_rules(args).note([focus, *opponents.values()], format_of([focus])):  # #528
        print(note)
    print(format_matchups(records, os.path.splitext(os.path.basename(args.decklist))[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
