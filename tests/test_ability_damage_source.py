"""Damage dealt by a permanent's ability is dealt by that permanent (#539, CR 120.3): "Whenever enchanted creature deals damage to
an opponent" (Curiosity, Ophidian Eye) answers to Niv-Mizzet's "deals 1 damage to any target", which closes the draw loop, and
does not answer to a spell's damage or to another creature's."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, lands, pick, real, run_stack, table

NIV = real("Niv-Mizzet, Parun", "{U}{U}{U}{R}{R}{R}", "Legendary Creature — Dragon Wizard", "This spell can't be countered.\nFlying\n"
           "Whenever you draw a card, Niv-Mizzet deals 1 damage to any target.\nWhenever a player casts an instant or sorcery spell, you draw a card.",
           "5", "5")
CURIOSITY = real("Curiosity", "{U}", "Enchantment — Aura", "Enchant creature\nWhenever enchanted creature deals damage to an opponent, "
                 "you may draw a card.")
EYE = real("Ophidian Eye", "{2}{U}", "Enchantment — Aura", "Flash\nEnchant creature\nWhenever enchanted creature deals damage to an opponent, "
           "you may draw a card.")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def loop_table(aura, onto):
    """Niv-Mizzet and the aura on `onto` ("niv" or "bear"), a big library, and the player answering "Player: B" and "Yes"."""
    game, _, _ = table(pick("Player: B", "Yes"), library=(FOREST,) * 20)
    mine, theirs = game.seats
    niv = Permanent(NIV, sick=False)
    bear = Permanent(BEAR, sick=False)
    mine.battlefield = [niv, bear]
    mine.battlefield.append(Permanent(aura, attached_to=niv if onto == "niv" else bear))
    mine.library = [FOREST] * 80
    return game, mine, theirs


class AbilityDamageTests(unittest.TestCase):
    def test_nivmizzet_with_curiosity_draws_until_the_opponent_is_dead(self):
        game, mine, theirs = loop_table(CURIOSITY, "niv")
        game.draw(mine, 1)
        run_stack(game)
        game._check_state()
        self.assertEqual((theirs.lost, theirs.life <= 0), (True, True))

    def test_nivmizzet_with_ophidian_eye_the_same(self):
        game, mine, theirs = loop_table(EYE, "niv")
        game.draw(mine, 1)
        run_stack(game)
        game._check_state()
        self.assertTrue(theirs.lost)

    def test_the_aura_on_another_creature_does_not_answer(self):
        game, mine, theirs = loop_table(CURIOSITY, "bear")
        game.draw(mine, 1)
        run_stack(game)
        game._check_state()
        self.assertEqual((theirs.life, len(mine.library)), (39, 79))  # Niv-Mizzet's one point, and no second draw

    def test_a_spells_damage_does_not_answer(self):
        game, mine, theirs = loop_table(CURIOSITY, "bear")
        mine.battlefield = [p for p in mine.battlefield if p.card is not NIV] + lands(1)
        mine.hand = [BOLT]
        game._perform(mine, "Cast: Lightning Bolt")  # a spell: no permanent deals its damage
        run_stack(game)
        self.assertEqual((theirs.life, len(mine.library)), (37, 80))


if __name__ == "__main__":
    unittest.main()
