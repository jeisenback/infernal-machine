"""Sentences that only qualify the effect before them, as data (issue #437).

"Draw a card. If you control eight or more lands, draw two cards instead." is one effect: the second sentence is read by a template as a
private marker (`_InsteadDraw`) and folded into the `Draw` before it. That used to be a branch of a `_merge_*` function for every such
sentence; now each is one `Follow` row (the marker, what it may follow, what the effect becomes) in a table, and `Follows` runs a table
as one pass of `outcomes._parse`. A marker with nothing fitting before it rejects the whole line (a lone "instead" has nothing to
change), which is what keeps a line half-understood from being called playable.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Follow:
    """`marker` is an effect (usually a private marker class) that modifies the effect just before it."""
    marker: type | tuple[type, ...]
    after: type | tuple[type, ...]  # what it may follow
    make: Callable[[Any, Any], Any] | None = None  # (the effect before, the marker) -> what replaces the effect before; None: unchanged
    fits: Callable[[Any, Any], bool] | None = None  # (the effect before, the marker) -> whether it applies, beyond the type
    strict: bool = True  # False: a marker that does not fit stays an effect of its own, instead of rejecting the line

    def applies(self, effect: Any) -> bool:
        return isinstance(effect, self.marker)


def set_fields(**getters: Callable[[Any], Any]) -> Callable[[Any, Any], Any]:
    """A `make` that copies the effect before with fields taken from the marker: `set_fields(more=lambda m: m.count)`."""
    def make(previous: Any, marker: Any) -> Any:
        return dataclasses.replace(previous, **{name: get(marker) for name, get in getters.items()})
    return make


class Follows:
    """A pass over a list of effects that folds the markers of its rows into the effects they follow. Callable as a `_merge_*` function:
    the new list, or None if a marker had nothing to follow."""

    def __init__(self, *rows: Follow):
        self.rows = rows

    def step(self, merged: list, effect: Any) -> bool | None:
        """Fold `effect` into the last of `merged` if one of the rows is about it: True if it was folded, False if the line must be
        rejected, None if no row is about it (the caller goes on with it)."""
        for row in self.rows:
            if not row.applies(effect):
                continue
            previous = merged[-1] if merged else None
            if previous is not None and isinstance(previous, row.after) and (row.fits is None or row.fits(previous, effect)):
                if row.make is not None:
                    merged[-1] = row.make(previous, effect)
                return True
            if row.strict:
                return False
            return None
        return None

    def __call__(self, effects: list) -> list | None:
        merged: list = []
        for effect in effects:
            done = self.step(merged, effect)
            if done is False:
                return None
            if done is None:
                merged.append(effect)
        return merged
