"""Issue #802: Assist, "(Another player can pay up to {N} of this spell's cost.)" (CR 702.132a), from the cards' real Oracle text. All ten
cards whose only gap it was are fully playable. Casting Charging Binox ({7}{G}): its caster may choose another player, who pays any amount
of the generic mana up to what they can and what is left of it, and the caster pays the rest; with no one chosen the caster pays it all,
and a spell without assist asks no one."""

import unittest

from infernal_machine.game import ASSIST_PAY_PROMPT, ASSIST_PROMPT, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Bloodborn Scoundrels", "Charging Binox", "Huddle Up", "Lava-Field Overlord", "Magma Hellion", "Play of the Game", "Skystreamer",
         "Spellweaver Duo"]
NEED_A_TARGET = ["Bring Down", "Out of Bounds"]  # (a creature with power 4 or greater, a spell: the smoke table has none, so only read)
BINOX = REAL["Charging Binox"]
ZIGGURAT = real("Ancient Ziggurat", "", "Land", "{T}: Add one mana of any color. Spend this mana only to cast a creature spell.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_assist).
MUTATIONS = [
    ("infernal_machine/casting.py", "        if not generic or not others or not has_assist(card):\n            return 0",
     "        if not generic or not others:\n            return 0", "only a spell with assist"),
    ("infernal_machine/casting.py", 'most = next(n for n in range(generic, -1, -1) if not n or self.game._pay_cost(helper, cost_of("{%d}" % n)) is not None)',
     "most = generic", "the helper pays only what they can"),
    ("infernal_machine/casting.py", "        with self.game._paying_for(seat, card):  # (their mana is spent on this spell",
     "        if True:  # (their mana is spent on this spell", "the helper's mana is spent on this spell"),
    ("infernal_machine/casting.py", "delve=delve + sacrificing + harmonized + assisted))", "delve=delve + sacrificing + harmonized))",
     "the caster pays only the rest"),
]


def helped_by(seat_index):
    """The caster's policy: ask seat `seat_index` (None: no one)."""
    def policy(prompt, options):
        if ASSIST_PROMPT.matches(prompt):
            return 0 if seat_index is None else next(i for i, o in enumerate(options) if f"(seat {seat_index})" in o)
        return 0
    return policy


def pays_most(prompt, options):
    return len(options) - 1 if ASSIST_PAY_PROMPT.matches(prompt) else 0


def cast(card, helper=1, mine=8, theirs=3):
    """Seat 0, with `mine` lands, casts `card` asking seat `helper`, who has `theirs` lands and pays all it may."""
    game, players = table3(helped_by(helper), pays_most)
    a, b, _ = game.seats
    a.hand, a.battlefield, b.battlefield = [card], lands(mine), lands(theirs)
    game._perform(a, CAST + card.name)
    run_stack(game)
    untapped = lambda seat: sum(not p.tapped for p in seat.battlefield if "Land" in p.card.type_line)
    return game, players, untapped(a), untapped(b)


class AssistTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        for name in NEED_A_TARGET:
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_another_player_pays_what_they_can_and_the_caster_the_rest(self):
        game, players, mine, theirs = cast(BINOX)
        self.assertIn("Charging Binox", [p.card.name for p in game.seats[0].battlefield])
        self.assertEqual((mine, theirs), (3, 0))  # they paid {3} of the {7}, the caster {4} and {G}
        (asked,) = [options for prompt, options in players[1].prompts if ASSIST_PAY_PROMPT.matches(prompt)]
        self.assertEqual(asked, ["0", "1", "2", "3"])

    def test_no_more_than_the_generic_mana(self):
        _, players, mine, theirs = cast(BINOX, theirs=10)
        (asked,) = [options for prompt, options in players[1].prompts if ASSIST_PAY_PROMPT.matches(prompt)]
        self.assertEqual((asked[-1], mine, theirs), ("7", 7, 3))

    def test_mana_the_helper_may_spend_only_on_such_a_spell_counts(self):
        game, players = table3(helped_by(1), pays_most)
        a, b, _ = game.seats
        a.hand, a.battlefield, b.battlefield = [BINOX], lands(8), [Permanent(ZIGGURAT), Permanent(ZIGGURAT)]
        game._perform(a, CAST + "Charging Binox")
        (asked,) = [options for prompt, options in players[1].prompts if ASSIST_PAY_PROMPT.matches(prompt)]
        self.assertEqual((asked, [p.tapped for p in b.battlefield]), (["0", "1", "2"], [True, True]))

    def test_with_no_one_chosen_the_caster_pays_it_all(self):
        _, players, mine, theirs = cast(BINOX, helper=None)
        self.assertEqual((mine, theirs, [p for p, _ in players[1].prompts if ASSIST_PAY_PROMPT.matches(p)]), (0, 3, []))

    def test_a_spell_without_assist_asks_no_one(self):
        _, players, _, theirs = cast(BEAR, mine=2)
        self.assertEqual(([p for p, _ in players[0].prompts if ASSIST_PROMPT.matches(p)], theirs), ([], 3))


if __name__ == "__main__":
    unittest.main()
