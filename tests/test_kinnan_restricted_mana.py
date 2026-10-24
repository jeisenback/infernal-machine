"""Kinnan's extra mana is not restricted (#542): Delighted Halfling taps for blue that only casts a legendary spell, and the mana Kinnan
adds with it is blue that pays for anything, so Freed from the Real's "{U}: Untap enchanted creature" is paid and the Halfling untaps."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import pick, real, run_stack, table

KINNAN = real("Kinnan, Bonder Prodigy", "{G}{U}", "Legendary Creature — Human Druid", "Whenever you tap a nonland permanent for mana, add one mana "
              "of any type that permanent produced.\n{5}{G}{U}: Look at the top five cards of your library. You may put a non-Human creature card from "
              "among them onto the battlefield. Put the rest on the bottom of your library in a random order.", "2", "2", colors=("G", "U"))
HALFLING = real("Delighted Halfling", "{G}", "Creature — Halfling Citizen", "{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only to "
                "cast a legendary spell, and that spell can't be countered.", "1", "2", colors=("G",))
FREED = real("Freed from the Real", "{2}{U}", "Enchantment — Aura", "Enchant creature\n{U}: Tap enchanted creature.\n{U}: Untap enchanted creature.",
             colors=("U",))
UNTAP = "Untap enchanted creature"


def seat_with(*, kinnan):
    game, _, _ = table(pick("Yes"))
    mine = game.seats[0]
    halfling = Permanent(HALFLING, sick=False)
    mine.battlefield = [halfling, Permanent(FREED, attached_to=halfling)] + ([Permanent(KINNAN, sick=False)] if kinnan else [])
    return game, mine, halfling


def untap_action(game, mine):
    return next((a for a in game.legal_actions(mine) if UNTAP in a), None)


class RestrictedManaWithKinnanTests(unittest.TestCase):
    def test_the_extra_blue_pays_for_the_untap(self):
        game, mine, halfling = seat_with(kinnan=True)
        action = untap_action(game, mine)
        self.assertIsNotNone(action)
        game._perform(mine, action)
        run_stack(game)
        self.assertFalse(halfling.tapped)  # tapped to pay, untapped by the ability

    def test_the_loop_repeats(self):
        game, mine, halfling = seat_with(kinnan=True)
        for _ in range(5):
            game._perform(mine, untap_action(game, mine))
            run_stack(game)
        self.assertFalse(halfling.tapped)

    def test_without_kinnan_the_halflings_blue_cannot_pay(self):
        game, mine, _ = seat_with(kinnan=False)
        self.assertIsNone(untap_action(game, mine))

    def test_a_legendary_spell_is_still_paid_by_the_restricted_blue(self):
        game, mine, _ = seat_with(kinnan=True)
        mine.hand = [KINNAN]  # {G}{U}, legendary: the Halfling's blue and Kinnan's extra pay for it
        self.assertIn("Cast: Kinnan, Bonder Prodigy", game.legal_actions(mine))


if __name__ == "__main__":
    unittest.main()
