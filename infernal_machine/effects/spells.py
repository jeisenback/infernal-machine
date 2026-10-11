"""The effects of an instant or sorcery's text, and of one line of it."""

from __future__ import annotations

import dataclasses

from ..cards import Card

from .common import _split_sentences, rules_lines
from .outcomes import _MODAL_COMMANDER, _MODAL_HEADER, _SPELL_MASTERY, _parse, _parse_modal
from .activated import _ACTIVATED, _channel_body, _cost_fields
from .costs import is_casting_cost_line


def spell_effects(card: Card) -> list | None:
    """Effects of an instant or sorcery, in order; None if any sentence isn't understood. A modal spell
    ("Choose one — ...") gives a single Modal effect."""
    lines = [line for line in rules_lines(card) if not is_casting_cost_line(line) and not is_hand_ability_line(line)]
    if lines and (m := _MODAL_HEADER.fullmatch(lines[0])):
        return _parse_modal(m[1].lower(), lines[1:])
    if lines and _MODAL_COMMANDER.fullmatch(lines[0]):
        modal = _parse_modal("one", lines[1:])
        return [dataclasses.replace(modal[0], commander_both=True)] if modal else None
    return _parse(_split_sentences("\n".join(_SPELL_MASTERY.sub("", line) for line in lines)))


def is_hand_ability_line(line: str) -> bool:
    """Magma Opus's "{U/R}{U/R}, Discard this card: ...": an ability of the card, not a sentence of the spell."""
    m = _ACTIVATED.fullmatch(_channel_body(line)[0])
    return m is not None and bool((fields := _cost_fields(m[1]) or {}).get("discard_self") or fields.get("exile_from_hand"))


def line_effects(line: str) -> list | None:
    """Effects of one line of spell text (from rules_lines); None if not understood."""
    return _parse(_split_sentences(_SPELL_MASTERY.sub("", line)))
