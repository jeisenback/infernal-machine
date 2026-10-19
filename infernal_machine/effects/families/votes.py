"""Effects of the "votes" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class PastOrPresentVote:
    """Fateful Tempest: each player votes for past or present. You mill a card for each past vote, then it deals damage to each
    opponent equal to the total mana value of the cards milled; you exile the top card for each present vote and may play
    those cards until the end of your next turn."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        past, present = game.vote(controller, ["past", "present"])
        milled = sum(int(card.cmc) for card in game.mill(controller, past))
        if milled:
            for opponent in game.opponents(controller):
                game.damage(opponent, milled)
        if present:
            game.exile_top(controller, present, "next turn")


@dataclass(frozen=True)
class VoteStart:
    """ "Starting with you, each player votes for X or Y." (options), or for a nonland permanent (None). Only ever a
    step of a Vote or VoteToExile (see _merge_votes)."""
    options: tuple[str, str] | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone vote is never built")


@dataclass(frozen=True)
class VoteOutcome:
    """ "For each X vote, ..." (each) or "If X gets more votes [or the vote is tied], ..." (more): what happens."""
    kind: str  # "each" or "more"
    option: str
    effects: tuple
    tie: bool = False  # "or the vote is tied"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone vote outcome is never built")


@dataclass(frozen=True)
class ExileMostVoted:
    """ "Exile each permanent with the most votes or tied for most votes." Only ever the end of a permanent vote."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone exile of the most voted is never built")


@dataclass(frozen=True)
class Vote:
    """Each player votes for one of two words; the outcomes follow the votes (the effects need no target)."""
    options: tuple[str, str]
    outcomes: tuple[VoteOutcome, ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        counts = dict(zip(self.options, game.vote(controller, list(self.options))))
        for outcome in self.outcomes:
            if outcome.kind == "each":
                times = counts[outcome.option]
            else:
                other = next(o for o in self.options if o != outcome.option)
                times = int(counts[outcome.option] > counts[other]
                            or (outcome.tie and counts[outcome.option] == counts[other]))
            for _ in range(times):
                for effect in outcome.effects:
                    effect.resolve(game, controller, None)


@dataclass(frozen=True)
class VoteToExile:
    """Council's Judgment."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.vote_to_exile(controller)


@dataclass(frozen=True)
class ThroneOfTheDeadThree:
    """The last room of the Undercity; the engine puts it on the stack itself."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.throne_of_the_dead_three(controller)
