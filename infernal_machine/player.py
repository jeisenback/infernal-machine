"""The interface the engine uses to talk to a player, wherever that player lives."""

from __future__ import annotations

from typing import Protocol, Sequence


class Player(Protocol):
    name: str

    def notify(self, event: dict) -> None:
        """Tell the player something happened (card drawn, spell cast, ...)."""

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        """Ask the player to pick one of `options`; returns its index."""
