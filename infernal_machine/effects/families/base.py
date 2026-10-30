"""The two small types that effects of every family share: an Amount and a Condition (split from outcomes.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataclasses import dataclass

if TYPE_CHECKING:
    from ...game import Game


@dataclass(frozen=True)
class Amount:
    """A number that depends on the game, worked out when the effect resolves: "its power",
    "the number of Auras you control", "the amount of life you gained this turn", ..."""
    kind: str  # see Game.evaluate
    what: str = ""  # a type ("Aura"), a counter ("+1/+1") or a spell kind ("instant or sorcery spell")


@dataclass(frozen=True)
class Condition:
    """An intervening "if" clause, checked when the ability triggers and again when it resolves."""
    kind: str  # "graveyard_left", "gained_life", "opponent_more_lands", "opponent_more_creatures", "spell_mv_at_least", "target_power_at_least", "opponent_dealt_noncombat_damage", "cast_this_turn", "control_at_least",
    #            "control_none", "control_none_token", "kicked", "your_turn", "monarch", "hand_at_least", "hand_none", "no_counter",
    #            "gained_life_at_least", "creatures_died", "control_color_at_least", "not_prepared", "not_renowned", "foretold", "discarded_nonland", "no_spell_cast_turn", "delirium", "each_life_at_most", "source_equipped", "no_spells_last_turn", "two_spells_last_turn", "day", "night", "subject_greater", "citys_blessing", "graveyard_at_least", "any_hand_at_most", "opponent_more_cards", "land_entered", "lands_prime", "attackers_at_most", "defender_more_life", "player_more_lands", "x_at_least", "has_exiled_with", "in_graveyard"
    count: int = 0
    what: str = ""  # a spell kind ("instant or sorcery spell") or a type ("Plains", "Snake", "creature")
    also: "Condition | None" = None  # "if A and B": this one and that one must both hold
    otherwise: "Condition | None" = None  # "if A or if B": this one or that one must hold (Gleaming Bastion)
