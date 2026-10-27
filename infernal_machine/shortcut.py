"""A shortcut: a player names a loop and how many times to go round it, and the game plays it out (the rules let a player propose
this and give the other players a chance to respond; here nobody does, since nothing yet proposes one but a script).

A `Shortcut` is the actions of one round, in order, and the answers its player gives to the questions they raise. Each step is a piece
of the action's text: the first legal action that contains it is taken. "A until B" takes A again and again until B is offered. The
stack resolves after each action. It stops when a step is not offered, when the game is over, or after the number of rounds asked.

It does not make "infinite" of anything: the result of N rounds is N rounds' worth, and a round that grows the board meets the board
limit (`BoardLimitReached`) or, if its whole state comes back, `LoopDraw`; both propagate to `Game.play`, which ends the game.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .game import Game, Seat
from .player import Player

UNTIL_LIMIT = 80  # actions one "A until B" step may take before it gives up


@dataclass(frozen=True)
class Shortcut:
    steps: tuple[str, ...]
    answers: tuple[str, ...] = ()  # "wanted", or "about~wanted" for a question that contains "about": the first option that contains it


@dataclass(frozen=True)
class ShortcutResult:
    rounds: int  # whole rounds played; when the game ended in the middle of one, the number of that round
    stopped: str | None  # why it stopped before the rounds asked for, else None
    over: bool  # the game has a winner or a player has lost


def pick(answers: Sequence[str], prompt: str, options: Sequence[str]) -> int | None:
    """The option the answers choose for this question, or None if none of them applies."""
    for want in answers:
        about, _, wanted = want.rpartition("~")
        if about not in str(prompt):
            continue
        for i, option in enumerate(options):
            if wanted in option:
                return i
    return None


class _Declared:
    """A player whose answers are the shortcut's where it has one, and their own where it does not."""

    def __init__(self, player: Player, answers: Sequence[str]) -> None:
        self._player, self._answers = player, answers
        self.name = player.name

    def notify(self, event: dict) -> None:
        self._player.notify(event)

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        chosen = pick(self._answers, prompt, options)
        return self._player.choose(prompt, options) if chosen is None else chosen

    def __getattr__(self, name: str):  # (anything else the real player has: the bot's features, a scripted player's prompts)
        return getattr(self._player, name)


def take(game: Game, seat: Seat, shortcut: Shortcut, times: int, keep_pool: bool = False) -> ShortcutResult:
    """Go round `shortcut` up to `times` times as `seat`. With `keep_pool` the loop pays from its permanents before the mana pool, so
    that what a round makes over what it pays builds up in the pool (a player may pay with either; the game ordinarily spends the pool
    first, which keeps the pool where it was)."""
    original, pool_last = seat.player, game.pool_last
    seat.player = _Declared(original, shortcut.answers)
    game.pool_last = keep_pool or pool_last
    done = 0
    try:
        for number in range(1, times + 1):
            for step in shortcut.steps:
                action, _, until = step.partition(" until ")
                for _ in range(UNTIL_LIMIT if until else 1):
                    if until and any(until in a for a in game.legal_actions(seat)):
                        break
                    offered = [a for a in game.legal_actions(seat) if action in a]
                    if not offered:
                        return ShortcutResult(done, f'round {number}: "{action}" is not offered' + (f' before "{until}"' if until else ""), _over(game))
                    game._perform(seat, offered[0])
                    game.resolve_stack()
                    if _over(game):
                        return ShortcutResult(number, None, True)
            done = number
    finally:
        seat.player = original
        game.pool_last = pool_last
    return ShortcutResult(done, None, _over(game))


def _over(game: Game) -> bool:
    return game.winner() is not None or any(s.lost for s in game.seats)
