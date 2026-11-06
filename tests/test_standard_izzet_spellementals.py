"""Standard's Izzet Spellementals deck, from its cards' real Oracle text: Get Out ("Counter target creature or enchantment spell." / "Return
one or two target creatures and/or enchantments you own to your hand."), Sunderflock (cheaper by the greatest mana value among your
Elementals; "return all non-Elemental creatures") and Hydro-Man, Fluid Felon (until your next turn, he becomes a land)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, OGRE, enter, lands, pick, real, run_stack, table3

GET_OUT = real("Get Out", "{U}{U}", "Instant", "Choose one —\n• Counter target creature or enchantment spell.\n• Return one or two target "
               "creatures and/or enchantments you own to your hand.", colors=("U",))
SUNDERFLOCK = real("Sunderflock", "{7}{U}{U}", "Creature — Elemental", "This spell costs {X} less to cast, where X is the greatest mana value "
                   "among Elementals you control.\nFlying\nWhen this creature enters, if you cast it, return all non-Elemental creatures to "
                   "their owners' hands.", "5", "5", colors=("U",))
HYDRO_MAN = real("Hydro-Man, Fluid Felon", "{U}{U}", "Legendary Creature — Elemental Villain", "Whenever you cast a blue spell, if "
                 "Hydro-Man is a creature, he gets +1/+1 until end of turn.\nAt the beginning of your end step, untap Hydro-Man. Until your "
                 "next turn, he becomes a land and gains \"{T}: Add {U}.\" (He's not a creature during that time.)", "2", "2", colors=("U",))
ELEMENTAL = real("Big Elemental", "{4}{U}", "Creature — Elemental", "", "4", "4", colors=("U",))
BOLT = real("Bolt", "{R}", "Instant", "Bolt deals 3 damage to any target.", colors=("R",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


def recorded(*labels):
    asked = []
    policy = pick(*labels)
    return asked, lambda prompt, options: asked.append(list(options)) or policy(prompt, options)


class StandardIzzetSpellementalsTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GET_OUT, SUNDERFLOCK, HYDRO_MAN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_get_out_counters_a_creature_spell_but_cannot_target_an_instant(self):
        asked, policy = recorded("Counter", "Bear")
        game, _ = table3(policy)
        a, b, _ = game.seats
        a.battlefield, a.hand = lands(2, ISLAND), [GET_OUT]
        game.stack += [StackItem(BEAR, b), StackItem(BOLT, b)]
        game._perform(a, CAST + "Get Out")
        run_stack(game)
        self.assertEqual((game.stack, b.graveyard), ([], [BEAR, BOLT]))  # (the Bolt resolved)
        self.assertEqual([o for options in asked for o in options if "Bolt" in o], [])

    def test_get_out_returns_two_creatures_its_caster_owns(self):
        asked, policy = recorded("Return", "Bear", "Ogre")
        game, _ = table3(policy)
        a, b, _ = game.seats
        bear, ogre, theirs = Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)
        a.battlefield, a.hand, b.battlefield = [*lands(2, ISLAND), bear, ogre], [GET_OUT], [theirs]
        game._perform(a, CAST + "Get Out")
        run_stack(game)
        self.assertEqual((sorted(c.name for c in a.hand), b.battlefield), (["Bear", "Ogre"], [theirs]))
        self.assertFalse(any("seat 1" in o for options in asked for o in options))

    def test_sunderflock_costs_less_by_the_greatest_elemental_and_bounces_the_rest(self):
        game, _ = table3()
        a, b, _ = game.seats
        big = Permanent(BIG)  # mana value 5, but not an Elemental
        a.battlefield, a.hand = [*lands(4, ISLAND), big], [SUNDERFLOCK]
        self.assertNotIn(CAST + "Sunderflock", game.legal_actions(a))
        elemental, bear, theirs = Permanent(ELEMENTAL), Permanent(BEAR), Permanent(OGRE)
        a.battlefield += [elemental, bear]
        b.battlefield = [theirs]
        game._perform(a, CAST + "Sunderflock")  # {7}{U}{U} less 5: {2}{U}{U}
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Creature" in p.card.type_line), ["Big Elemental", "Sunderflock"])
        self.assertEqual((sorted(c.name for c in a.hand), [c.name for c in b.hand]), (["Bear", "Big"], ["Ogre"]))

    def test_sunderflock_put_onto_the_battlefield_bounces_nothing(self):
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(OGRE)]
        enter(game, a, SUNDERFLOCK)
        run_stack(game)
        self.assertEqual(b.hand, [])

    def test_hydro_man_grows_as_a_creature_and_is_a_land_until_his_controllers_next_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        hydro = Permanent(HYDRO_MAN, tapped=True)
        a.battlefield, a.hand, a.library = [*lands(2, ISLAND), hydro], [OPT, OPT], [ISLAND] * 5
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual(game.power(hydro), 3)
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual((hydro.tapped, hydro.card.type_line), (False, "Legendary Land"))
        self.assertIn(hydro, [m.permanent for m in game._mana_sources(a)])
        pumps = len(hydro.until_end_of_turn)
        game._perform(a, CAST + "Opt")  # paid with Hydro-Man's {U}: a land is not pumped
        run_stack(game)
        self.assertEqual(len(hydro.until_end_of_turn), pumps)
        game.step = "untap"
        game._turn_based_actions(b)  # an opponent's turn: still a land
        self.assertEqual(hydro.card.type_line, "Legendary Land")
        game._turn_based_actions(a)
        self.assertEqual(hydro.card, HYDRO_MAN)
        game._leave_battlefield(hydro, "destroyed")
        self.assertEqual(a.graveyard[-1], HYDRO_MAN)


if __name__ == "__main__":
    unittest.main()
