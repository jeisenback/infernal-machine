"""Token copies, from the cards' real Oracle text: Relm's Sketching (of target artifact, creature, or land), Saheeli, the Sun's Brilliance
(of another creature or artifact you control, an artifact too, with haste, sacrificed at the next end step), Rhys the Redeemed (a copy of
each creature token you control) and Lazotep Quarry (exile a creature card with mana value X; a 4/4 black Zombie copy of it)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, SPIRIT, activate, end_turn, lands, pick, real, run_stack, table3

SKETCHING = real("Relm's Sketching", "{2}{U}{U}", "Sorcery", "Create a token that's a copy of target artifact, creature, or land.", colors=("U",))
SAHEELI = real("Saheeli, the Sun's Brilliance", "{U}{R}", "Legendary Creature — Human Artificer", "{U}{R}, {T}: Create a token that's a copy "
               "of another target creature or artifact you control, except it's an artifact in addition to its other types. It gains haste. "
               "Sacrifice it at the beginning of the next end step.", "2", "2", colors=("R", "U"))
RHYS = real("Rhys the Redeemed", "{G/W}", "Legendary Creature — Elf Warrior", "{2}{G/W}, {T}: Create a 1/1 green and white Elf Warrior "
            "creature token.\n{4}{G/W}{G/W}, {T}: For each creature token you control, create a token that's a copy of that creature.", "1", "1",
            colors=("G", "W"))
QUARRY = real("Lazotep Quarry", "", "Land — Desert", "{T}: Add {C}.\n{T}, Sacrifice a creature: Add one mana of any color.\n{X}{2}, {T}, "
              "Sacrifice a Desert: Exile target creature card with mana value X from your graveyard. Create a token that's a copy of it, "
              "except it's a 4/4 black Zombie. Activate only as a sorcery.")
CARDS = (SKETCHING, SAHEELI, RHYS, QUARRY)

GIANT = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3", colors=("R",))  # mana value 4
COURSER = real("Centaur Courser", "{2}{G}", "Creature — Centaur Warrior", "", "3", "3", colors=("G",))  # mana value 3


def tokens(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.type_line.startswith("Token"))


class TokenCopiesBatchTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_relms_sketching_copies_a_land_but_not_an_enchantment(self):
        game, _ = table3(pick("Forest"))
        a = game.seats[0]
        a.battlefield, a.hand = [Permanent(FOREST)] + lands(4), [SKETCHING]
        game._perform(a, CAST + SKETCHING.name)
        run_stack(game)
        self.assertEqual(tokens(a), ["Forest"])
        offered = []
        game, _ = table3(lambda prompt, options: offered.append(options) or 0)
        a = game.seats[0]
        a.battlefield, a.hand = [Permanent(real("Glorious Anthem", "{1}{W}{W}", "Enchantment", "Creatures you control get +1/+1."))] + lands(4), \
            [SKETCHING]
        game._perform(a, CAST + SKETCHING.name)
        self.assertFalse(any(o.startswith("Glorious Anthem") for options in offered for o in options))  # an enchantment is no target

    def test_saheeli_copies_another_creature_as_a_hasty_artifact_until_the_end_step(self):
        game, _ = table3(pick("Ogre"))
        a = game.seats[0]
        a.battlefield = [Permanent(SAHEELI), Permanent(OGRE)] + lands(2)
        activate(game, a, "Create a token")
        copy = next(p for p in a.battlefield if p.card.type_line.startswith("Token"))
        self.assertEqual((copy.card.name, "Artifact" in copy.card.type_line, game.has_keyword(copy, "haste")), ("Ogre", True, True))
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(tokens(a), [])

    def test_rhys_copies_each_creature_token_and_nothing_else(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(RHYS), Permanent(SPIRIT), Permanent(SPIRIT), Permanent(BEAR)] + lands(6)
        activate(game, a, "For each creature token")
        self.assertEqual(tokens(a), ["Spirit"] * 4)  # the Bear isn't a token: it isn't copied

    def test_lazotep_quarry_makes_a_zombie_copy_of_a_card_with_mana_value_x(self):
        game, _ = table3(pick("3", "Hill Giant", "Centaur Courser"))  # X is 3: the Giant (mana value 4) would be taken if it could be
        a = game.seats[0]
        quarry = Permanent(QUARRY)
        a.battlefield, a.graveyard = [quarry] + lands(5), [GIANT, COURSER]
        activate(game, a, "Exile target creature card")
        zombie = next(p for p in a.battlefield if p.card.type_line.startswith("Token"))
        self.assertEqual((zombie.card.name, zombie.card.power, "Zombie" in zombie.card.type_line, [c.name for c in a.exile],
                          any(p is quarry for p in a.battlefield)), ("Centaur Courser", "4", True, ["Centaur Courser"], False))


if __name__ == "__main__":
    unittest.main()
