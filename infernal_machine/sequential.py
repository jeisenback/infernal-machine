"""Looking at a result more than once without fooling yourself (issues #393 and #410).

`compare`, `impact` and `matchup` can play their games in rounds and stop when the answer is settled. Stopping the first time an ordinary 95%
interval excludes the null (zero difference, or the fair share) would call equal things different far more than one time in twenty, so each
look uses an interval widened for the number of looks planned: each look gets 5% / looks of the error (a Bonferroni bound), which keeps the
chance that any look is falsely "clear" at 5% or less. Nothing stops before `MIN_LOOK_PAIRS` games: with fewer the spread is a guess, and a
few alike pairs give an interval of no width. The last look never stops early; it is simply the end of the plan.
"""

from __future__ import annotations

import math
from statistics import NormalDist

Z = 1.96  # for a 95% interval
MAX_LOOKS = 10  # rounds an early-stopping run is played in
MIN_LOOK_PAIRS = 30  # games before anything is said: the spread of fewer is a guess
MIN_DIFFERING = 8  # fewer differing pairs than this and the spread of the differences, and so a pairs-needed estimate, rests on too few events
HOPELESS_FACTOR = 3  # "hopeless" when separating the target difference takes more than this many times the games planned


def look_z(looks: int) -> float:
    """The interval width that keeps the chance of a false "clear" over `looks` looks at 5% or less: each look gets 5% / looks."""
    return Z if looks <= 1 else NormalDist().inv_cdf(1 - 0.05 / (2 * looks))


def schedule(games: int) -> tuple[int, int]:
    """(the looks, the games between looks) for `games` games per opponent: up to `MAX_LOOKS` equal rounds."""
    looks = min(MAX_LOOKS, games)
    batch = math.ceil(games / looks)
    return math.ceil(games / batch), batch


def confidence(z: float) -> str:
    """The width of an interval of `z` standard errors, for printing: "95%" or "99.5%"."""
    return "95%" if z == Z else f"{(2 * NormalDist().cdf(z) - 1) * 100:.1f}%"
