import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import line_effects, spell_effects, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature
from tests.test_effects import table

LIFEBLOOD = creature("Lifeblood Hydra", 4, 4, "When this creature dies, you gain life and draw cards equal to its power.")
MYCOLOTH = creature("Mycoloth", 0, 0, "At the beginning of your upkeep, create a 1/1 green Saproling creature token for "
                                     "each +1/+1 counter on this creature.")
HANGARBACK = Card(name="Hangarback Walker", mana_cost="{X}{X}", type_line="Artifact Creature — Construct", power="0",
                  toughness="0", oracle_text="When this creature dies, create a 1/1 colorless Thopter artifact creature "
                                             "token with flying for each +1/+1 counter on this creature.")
ERIETTE = creature("Eriette", 2, 4, "At the beginning of your end step, each opponent loses X life and you gain X life, "
                                    "where X is the number of Auras you control.")
DAEMOGOTH = creature("Daemogoth", 6, 6, "At the beginning of your end step, each opponent loses X life, where X is the "
                                        "amount of life you gained this turn.")
CHAIN = Card(name="Chain Reaction", mana_cost="{2}{R}{R}", type_line="Sorcery", colors=("R",),
             oracle_text="Chain Reaction deals X damage to each creature, where X is the number of creatures on the "
                         "battlefield.")
SCHOLAR = Card(name="Scholar", mana_cost="{U}", type_line="Enchantment",
               oracle_text="At the beginning of your end step, draw a card for each spell you've cast this turn.")
ROOTHA = Card(name="Rootha", mana_cost="{U}", type_line="Enchantment",
              oracle_text="At the beginning of your end step, you gain X life, where X is the greatest mana value among "
                          "instant and sorcery spells you've cast this turn.")
ROOTHA_COMMANDER = Card(name="Rootha, Mastering the Moment", mana_cost="{3}{U}{R}", type_line="Legendary Creature",
                        power="3", toughness="3",
                        oracle_text="At the beginning of combat on your turn, if you've cast an instant or sorcery spell "
                                    "this turn, create an X/X blue and red Elemental creature token with flying and haste, "
                                    "where X is the greatest mana value among instant and sorcery spells you've cast this "
                                    "turn.")
AURA = Card(name="Aura", mana_cost="{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature")
SPELL = Card(name="Spell", mana_cost="{2}{U}", cmc=3, type_line="Instant", oracle_text="Draw a card.")
BIG_SPELL = Card(name="Big Spell", mana_cost="{4}{U}", cmc=5, type_line="Sorcery", oracle_text="Draw a card.")


def run(game, seat, step):
    game.step = step
    game._turn_based_actions(seat)
    game._priority_round(seat)


class ParseTests(unittest.TestCase):
    def test_all_parse(self):
        for card in (LIFEBLOOD, MYCOLOTH, HANGARBACK, ERIETTE, DAEMOGOTH, SCHOLAR, ROOTHA):
            self.assertTrue(triggered_abilities(card), card.name)
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertIsNotNone(spell_effects(CHAIN))

    def test_unknown_amounts_stay_unsupported(self):
        self.assertIsNone(line_effects("Draw a card for each time you've sneezed."))
        self.assertIsNone(line_effects("You gain X life, where X is the number of stars in the sky."))
        self.assertIsNone(line_effects("Destroy target creature for each Aura you control."))


class AmountTests(unittest.TestCase):
    def test_equal_to_its_power_uses_last_known_power(self):
        game, _, _ = table()
        a = game.seats[0]
        hydra = Permanent(LIFEBLOOD, counters={"+1/+1": 2})
        a.battlefield = [hydra]
        a.library = [BEAR] * 10
        game.destroy(hydra)
        game._priority_round(a)
        self.assertEqual((a.life, len(a.hand)), (46, 6))

    def test_for_each_counter_on_this_creature(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(MYCOLOTH, counters={"+1/+1": 3})]
        run(game, a, "upkeep")
        self.assertEqual([p.card.name for p in a.battlefield].count("Saproling"), 3)

    def test_counters_on_a_creature_that_died(self):
        game, _, _ = table()
        a = game.seats[0]
        walker = Permanent(HANGARBACK, counters={"+1/+1": 2})
        a.battlefield = [walker]
        game.destroy(walker)
        game._priority_round(a)
        self.assertEqual([p.card.name for p in a.battlefield].count("Thopter"), 2)

    def test_number_you_control(self):
        game, _, _ = table()
        a, b = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(ERIETTE), bear, Permanent(AURA, attached_to=bear), Permanent(AURA, attached_to=bear)]
        run(game, a, "end")
        self.assertEqual((a.life, b.life), (42, 38))

    def test_life_gained_this_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DAEMOGOTH)]
        game.change_life(a, 2)
        game.change_life(a, 3)
        game.change_life(a, -1)
        run(game, a, "end")
        self.assertEqual(b.life, 35)
        game.turn += 1
        run(game, a, "end")
        self.assertEqual(b.life, 35)  # nothing gained this turn

    def test_creatures_on_the_battlefield(self):
        game, _, _ = table()
        a, b = game.seats
        ogre = creature("Ogre", 5, 5)
        a.battlefield = [Permanent(ogre)]
        b.battlefield = [Permanent(ogre), Permanent(BEAR)]
        from infernal_machine.game import StackItem
        game._apply_effects(StackItem(CHAIN, a, spell_effects(CHAIN)))
        game._check_state()
        self.assertEqual([p.card.name for p in a.battlefield + b.battlefield], ["Ogre", "Ogre"])
        self.assertEqual(a.battlefield[0].damage, 3)

    def test_spells_cast_this_turn(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(SCHOLAR)]
        a.library = [BEAR] * 5
        a.cast_log = [(game.turn - 1, SPELL), (game.turn, SPELL), (game.turn, BEAR)]
        run(game, a, "end")
        self.assertEqual(len(a.hand), 2)

    def test_greatest_mana_value_among_instants_and_sorceries(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ROOTHA)]
        a.cast_log = [(game.turn, SPELL), (game.turn, BIG_SPELL), (game.turn - 1, BIG_SPELL), (game.turn, BEAR)]
        run(game, a, "end")
        self.assertEqual(a.life, 45)


    def test_x_by_x_tokens(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ROOTHA_COMMANDER)]
        self.assertEqual(unsupported_lines(ROOTHA_COMMANDER), [])
        a.cast_log = [(game.turn, SPELL), (game.turn, BIG_SPELL)]
        run(game, a, "beginning_of_combat")
        token = a.battlefield[-1]
        self.assertEqual((token.card.name, game.power(token), game.toughness(token)), ("Elemental", 5, 5))
        self.assertTrue(game.has_keyword(token, "haste"))


if __name__ == "__main__":
    unittest.main()
