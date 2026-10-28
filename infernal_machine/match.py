"""Best-of-three matches with sideboarding (issue #412): the way Standard is played.

A match is up to `best_of` games between two decks. Between games each side sideboards by one simple rule (`sideboard`), and the player
who lost the last game plays first in the next (CR 103.2: the loser chooses, and chooses to play; after a drawn game the one who chose
last time chooses again, so the deck that started the draw starts again). The match is won by the first side to
win a majority of the games; if neither does (games drawn by the turn limit) it is drawn. `matchup --best-of 3` plays matches and
reports the match win rate as well as the game win rate.

The sideboarding rule is a rule, not skill: after a game, a side takes out the cards of its main deck that it never cast in it (the most
expensive first) and brings in cards from its sideboard in the colors its main deck leans on (the cheapest first), up to `SWAPS` cards,
one for one so the deck keeps its size. It starts from the deck as registered each time, not from the deck of the last game. Whether it
helps is measured, not assumed: `play_match(..., sideboarding=False)` plays the same match with every side keeping its deck, or `(True, False)` with only the first
sideboarding.
"""

from __future__ import annotations

import random
import zlib
from collections import Counter
from collections.abc import Iterable
from dataclasses import replace

from .analysis import color_pips, is_land
from .cards import Deck
from .matchup import GameResult, play_one

SWAPS = 3  # most cards a side swaps between games
LEANS = 3  # colored symbols a color needs in the main deck to count as one the deck plays


def _colors_played(deck: Deck) -> set[str]:
    pips: Counter[str] = Counter()
    for card in deck.main:
        if not is_land(card):
            pips.update(color_pips(card.mana_cost))
    return {color for color, n in pips.items() if n >= LEANS}


def sideboard(deck: Deck, cast: Iterable[str], swaps: int = SWAPS) -> tuple[Deck, list[tuple[str, str]]]:
    """The deck after sideboarding, and the (card out, card in) swaps made. `cast` are the names of the cards the deck cast in the last
    game: a nonland card of the main deck not among them is a candidate to come out (most expensive first, then by name); a nonland
    sideboard card whose colored symbols are all in colors the main deck plays is a candidate to come in (cheapest first, then by name).
    A deck with no sideboard, or nothing to take out, is returned as it is."""
    cast = set(cast)
    colors = _colors_played(deck)
    out = sorted((c for c in deck.main if not is_land(c) and c.name not in cast), key=lambda c: (-c.cmc, c.name))
    into = sorted((c for c in deck.sideboard if not is_land(c) and set(color_pips(c.mana_cost)) <= colors), key=lambda c: (c.cmc, c.name))
    n = min(swaps, len(out), len(into))
    if n == 0:
        return deck, []
    leaving, arriving = out[:n], into[:n]
    main, side = list(deck.main), list(deck.sideboard)
    for card in leaving:
        main.remove(card)
        side.append(card)
    for card in arriving:
        side.remove(card)
        main.append(card)
    return replace(deck, main=main, sideboard=side), [(a.name, b.name) for a, b in zip(leaving, arriving)]


def game_seed(seed: int, game: int) -> int:
    """The seed of game `game` (from 0) of a match: the first is the match's own, so a one-game match is the same game."""
    return seed if game == 0 else zlib.crc32(f"{seed}-game-{game}".encode())


def _by_deck(game: GameResult, seat_of: list[int], focus: int) -> GameResult:
    """A game played with decks in the seats of `seat_of` (deck -> seat), read in terms of the decks: whose focus, who won, who started."""
    deck_of = {seat: deck for deck, seat in enumerate(seat_of)}
    game.focus_seat = focus
    game.winner = deck_of[game.winner] if game.winner is not None else None
    game.starting_seat = deck_of[game.starting_seat]
    game.logs = {deck: game.logs[seat] for deck, seat in enumerate(seat_of)} if game.logs else {}
    game.reasons = {deck_of[seat]: reason for seat, reason in game.reasons.items()}
    return game


def play_match(decks: list[Deck], focus_seat: int, seed: int, max_turns: int = 60, time_limit: float = 120.0, bots: list | None = None,
               best_of: int = 3, sideboarding: bool | tuple[bool, bool] = True) -> GameResult:
    """A match of up to `best_of` games between `decks` (two of them), `decks[focus_seat]` being the deck tested; the first game seats
    them as given. Returned as a `GameResult` for the match: `winner` is the index in `decks` of the side that won it (None for a drawn
    match), `games` holds the games (also read by deck), `turns` adds up their turns, and `error` is set if a game crashed or timed out
    (the match is then not counted). `sideboarding` says whether the decks sideboard between games: one flag for both, or one for each
    deck (to measure the rule: one side sideboards, the other keeps its deck)."""
    if len(decks) != 2:
        raise ValueError("A match is between two decks")
    sides = (sideboarding, sideboarding) if isinstance(sideboarding, bool) else sideboarding
    need = best_of // 2 + 1
    wins = [0, 0]
    played: list[GameResult] = []
    current = list(decks)
    seat_of = [0, 1]  # the seat each deck sits in this game
    for k in range(best_of):
        if k:  # the engine starts the player in seat `first`; the loser of the last game takes it. CR 103.2: after a draw, the player
            # who chose in that game chooses again, and that was its starting player (the chooser plays), so the same deck starts.
            first = random.Random(game_seed(seed, k)).randrange(2)
            last = played[-1]
            starter = (1 - last.winner) if last.winner is not None else last.starting_seat
            seat_of = [first, 1 - first] if starter == 0 else [1 - first, first]
        ordered = [current[deck] for deck in sorted((0, 1), key=lambda d: seat_of[d])]
        game = _by_deck(play_one(ordered, seat_of[focus_seat], game_seed(seed, k), max_turns, time_limit, bots), seat_of, focus_seat)
        played.append(game)
        if game.error is not None:
            break
        if game.winner is not None:
            wins[game.winner] += 1
            if wins[game.winner] >= need:
                break
        current = [sideboard(decks[d], game.logs[d].cast_names)[0] if sides[d] else decks[d] for d in (0, 1)]
    result = GameResult(focus_seat, turns=sum(g.turns for g in played), starting_seat=played[0].starting_seat)
    result.games = played
    result.logs = played[0].logs
    result.ended = played[-1].ended
    errors = [g.error for g in played if g.error]
    if errors:
        result.error = errors[0]
    elif wins[0] != wins[1]:
        result.winner = 0 if wins[0] > wins[1] else 1
    return result


def game_record(match: GameResult) -> tuple[int, int, int]:
    """(games won, lost, drawn) by the focus deck over a match's games."""
    games = [g for g in match.games if g.error is None]
    won = sum(g.winner == match.focus_seat for g in games)
    drawn = sum(g.winner is None for g in games)
    return won, len(games) - won - drawn, drawn
