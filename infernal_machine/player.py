"""The interface the engine uses to talk to a player, wherever that player lives."""

from __future__ import annotations

from typing import Protocol, Sequence


class Player(Protocol):
    name: str

    def notify(self, event: dict) -> None:
        """Tell the player something happened (card drawn, spell cast, ...)."""

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        """Ask the player to pick one of `options`; returns its index. The prompt is a `prompts.Prompt` when it comes from the game: the
        text, and what kind of question it is (`prompt.kind`, `KIND.matches(prompt)`) and about (`prompt.subject`); a plain string
        (over the wire, or a test's own) works as the text."""
        ...
