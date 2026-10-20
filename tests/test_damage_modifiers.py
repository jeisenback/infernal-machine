"""Static replacement effects that double, triple or add to damage (CR 614.1, 616.1): Furnace of Rath, Angrath's Marauders, City on Fire,
Twinflame Tyrant, Solphim, Tomik, Fiendish Duo, Charging Tuskodon and Gratuitous Violence."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FURNACE, OGRE, pick, real, Table, table3, TOMIK

MARAUDERS = real("Angrath's Marauders", "{5}{R}{R}", "Creature — Human Pirate", "If a source you control would deal damage to a "
                 "permanent or player, it deals double that damage to that permanent or player instead.", "4", "4")
CITY = real("City on Fire", "{5}{R}{R}{R}", "Enchantment", "Convoke (Your creatures can help cast this spell. Each creature you tap while casting "
            "this spell pays for {1} or one mana of that creature's color.)\nIf a source you control would deal damage to a permanent or "
            "player, it deals triple that damage instead.")
TYRANT = real("Twinflame Tyrant", "{3}{R}{R}", "Creature — Dragon", "Flying\nIf a source you control would deal damage to an opponent or a "
              "permanent an opponent controls, it deals double that damage instead.", "3", "5")
SOLPHIM = real("Solphim, Mayhem Dominus", "{2}{R}{R}", "Legendary Creature — Phyrexian Horror", "If a source you control would deal "
               "noncombat damage to an opponent or a permanent an opponent controls, it deals double that damage to that player or permanent "
               "instead.\n{1}{R/P}{R/P}, Discard two cards: Put an indestructible counter on Solphim. ({R/P} can be paid with either {R} or 2 life.)",
               "5", "4")
DUO = real("Fiendish Duo", "{4}{R}{R}", "Creature — Devil", "First strike (This creature deals combat damage before creatures without first "
           "strike.)\nIf a source would deal damage to an opponent, it deals double that damage to that player instead.", "5", "5")
TUSKODON = real("Charging Tuskodon", "{3}{R}{R}", "Creature — Dinosaur", "Trample\nIf this creature would deal combat damage to a player, "
                "it deals double that damage to that player instead.", "4", "4")
VIOLENCE = real("Gratuitous Violence", "{2}{R}{R}{R}", "Enchantment", "If a creature you control would deal damage to a permanent or player, "
                "it deals double that damage instead.")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def setup(*cards, theirs=()):
    """Seat 0 controls `cards` (and an Ogre to deal damage with); seat 1 controls `theirs`; returns (game, a, b, ogre)."""
    game, _ = table3()
    a, b, _ = game.seats
    ogre = Permanent(OGRE)
    a.battlefield = [Permanent(c) for c in cards] + [ogre]
    b.battlefield = [Permanent(c) for c in theirs]
    return game, a, b, ogre


def life_lost(game, seat, amount, source=None, combat=False):
    before = seat.life
    game.damage(seat, amount, source, combat)
    return before - seat.life


class DamageModifierTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (FURNACE, MARAUDERS, CITY, TYRANT, SOLPHIM, TOMIK, DUO, TUSKODON, VIOLENCE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_any_source_doubles_damage_to_everything(self):
        game, a, b, ogre = setup(FURNACE, theirs=[BEAR])
        bear = b.battlefield[0]
        self.assertEqual((life_lost(game, b, 3, ogre), life_lost(game, a, 3, ogre)), (6, 6))
        game.damage(bear, 1, ogre)
        self.assertEqual(bear.damage, 2)

    def test_a_source_you_control_includes_your_spells_but_not_theirs(self):
        t = Table(BOLT, mine=[Permanent(MARAUDERS)], n=1, policy=pick("Player: B"))
        t.cast()
        self.assertEqual(40 - t.b.life, 6)
        game, a, b, _ = setup(MARAUDERS)
        theirs = Permanent(OGRE)
        b.battlefield = [theirs]
        self.assertEqual(life_lost(game, a, 3, theirs), 3)  # an opponent's source is not doubled

    def test_triple(self):
        game, a, b, ogre = setup(CITY)
        self.assertEqual(life_lost(game, b, 3, ogre), 9)

    def test_two_doublers_quadruple(self):
        game, a, b, ogre = setup(FURNACE, MARAUDERS)
        self.assertEqual(life_lost(game, b, 2, ogre), 8)

    def test_only_damage_to_an_opponent_or_their_permanents(self):
        game, a, b, ogre = setup(TYRANT, theirs=[BEAR])
        mine = Permanent(BEAR)
        a.battlefield.append(mine)
        self.assertEqual((life_lost(game, b, 3, ogre), life_lost(game, a, 3, ogre)), (6, 3))
        game.damage(b.battlefield[0], 2, ogre)
        game.damage(mine, 2, ogre)
        self.assertEqual((b.battlefield[0].damage, mine.damage), (4, 2))

    def test_noncombat_only(self):
        game, a, b, ogre = setup(SOLPHIM)
        self.assertEqual((life_lost(game, b, 3, ogre, combat=False), life_lost(game, b, 3, ogre, combat=True)), (6, 3))

    def test_plus_one(self):
        game, a, b, ogre = setup(TOMIK)
        self.assertEqual((life_lost(game, b, 3, ogre), life_lost(game, b, 3, ogre, combat=True), life_lost(game, a, 3, ogre)), (4, 3, 3))

    def test_zero_damage_stays_zero(self):
        game, a, b, ogre = setup(TOMIK)
        self.assertEqual(life_lost(game, b, 0, ogre), 0)

    def test_an_opponent_means_a_player_only(self):
        game, a, b, ogre = setup(DUO, theirs=[BEAR])
        self.assertEqual((life_lost(game, b, 2, ogre), life_lost(game, a, 2, ogre)), (4, 2))  # to its controller: not doubled
        game.damage(b.battlefield[0], 2, ogre)
        self.assertEqual(b.battlefield[0].damage, 2)

    def test_a_creature_that_doubles_its_own_combat_damage_to_players(self):
        game, a, b, ogre = setup(TUSKODON)
        tuskodon = a.battlefield[0]
        self.assertEqual((life_lost(game, b, 3, tuskodon, combat=True), life_lost(game, b, 3, ogre, combat=True),
                          life_lost(game, b, 3, tuskodon, combat=False)), (6, 3, 3))

    def test_a_creature_you_control_but_not_a_spell(self):
        game, a, b, ogre = setup(VIOLENCE)
        self.assertEqual(life_lost(game, b, 2, ogre), 4)
        t = Table(BOLT, mine=[Permanent(VIOLENCE)], n=1, policy=pick("Player: B"))
        t.cast()
        self.assertEqual(40 - t.b.life, 3)


if __name__ == "__main__":
    unittest.main()
