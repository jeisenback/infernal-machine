"""The Undercity dungeon (the initiative): rooms, what each does, and where it leads. Room texts are read by the same
templates as spell text, except the last room, which the engine does itself (effects.ThroneOfTheDeadThree)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Room:
    text: str  # what the room does; "" for the Throne, which is an effect of its own
    leads_to: tuple[str, ...]


START = "Secret Entrance"
ROOMS = {
    "Secret Entrance": Room("Search your library for a basic land card, reveal it, put it into your hand, then shuffle.",
                            ("Forge", "Lost Well")),
    "Forge": Room("Put two +1/+1 counters on target creature.", ("Trap!", "Arena")),
    "Lost Well": Room("Scry 2.", ("Arena", "Stash")),
    "Trap!": Room("Target player loses 5 life.", ("Archives",)),
    "Arena": Room("Goad target creature.", ("Archives", "Throne of the Dead Three")),
    "Stash": Room("Create a Treasure token.", ("Archives", "Catacombs")),
    "Archives": Room("Draw a card.", ("Throne of the Dead Three",)),
    "Catacombs": Room("Create a 4/1 black Skeleton creature token with menace.", ("Throne of the Dead Three",)),
    "Throne of the Dead Three": Room("", ()),
}

HELPS_ITS_TARGET = {"Forge"}  # rooms whose target is meant to be one of your own creatures
