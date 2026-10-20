import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (DrawThenPutBack, Draw, PutBackTop, activated_abilities, mana_per_count,
                                      self_cost_reduction, spell_effects)
from infernal_machine.game import PUT_BACK_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import FOREST, lands, pick
from tests.test_lands import SWAMP, spell
from tests.test_mass_effects import table3
from tests.real import REAL

TOP = REAL["Sensei's Divining Top"]
FLOCKING = REAL["Cryptic Serpent"]
BOLT = Card(name="Bolt", mana_cost="{R}", type_line="Instant", oracle_text="Draw a card.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
COUNTED = [Card(name=f"Card {n}", type_line="Sorcery") for n in range(4)]


def library(*names):
    return [Card(name=n, type_line="Creature — Bear", power="1", toughness="1") for n in names]


class ParseTests(unittest.TestCase):
    def test_brainstorm_and_ponder(self):
        self.assertEqual(spell_effects(REAL["Brainstorm"]), [DrawThenPutBack(3, 2)])
        self.assertEqual(spell_effects(REAL["Ponder"]), [PutBackTop(3, shuffle=True), Draw(1)])

    def test_a_lone_may_shuffle_is_not_understood(self):
        self.assertIsNone(spell_effects(Card(name="x", type_line="Sorcery", oracle_text="You may shuffle.")))

    def test_tops_first_ability(self):
        ability = activated_abilities(TOP)[0]
        self.assertEqual((ability.mana_cost, ability.effects), ("{1}", (PutBackTop(3),)))

    def test_cost_reductions(self):
        self.assertEqual(self_cost_reduction(REAL["Blasphemous Act"]), (1, "creature"))
        self.assertEqual(self_cost_reduction(FLOCKING), (1, "instant or sorcery"))

    def test_mana_for_each(self):
        self.assertEqual(mana_per_count(REAL["Gaea's Cradle"]), ("", "G", "creature"))
        self.assertEqual(mana_per_count(REAL["Cabal Coffers"]), ("{2}", "B", "Swamp"))
        self.assertEqual(mana_per_count(REAL["Elvish Archdruid"]), ("", "G", "Elf"))

    def test_the_report_understands_them(self):
        for card in (TOP, FLOCKING):
            self.assertEqual([l for l in unsupported_lines(card) if "Draw a card" not in l], [], card.name)


class LibraryTests(unittest.TestCase):
    def test_brainstorm_puts_two_cards_back_in_the_order_chosen(self):
        def policy(prompt, options):  # put back the first two cards in the hand, then order them last one first
            return 0 if PUT_BACK_PROMPT.matches(prompt) else len(options) - 1

        game, _ = table3(policy)
        a = game.seats[0]
        a.hand = library("A")
        a.library = library("C", "D", "E", "F")
        spell_effects(REAL["Brainstorm"])[0].resolve(game, a, None)  # draws C, D and E, then puts A and C back
        self.assertEqual(sorted(c.name for c in a.hand), ["D", "E"])
        self.assertEqual([c.name for c in a.library], ["C", "A", "F"])  # C was chosen to go on top

    def test_brainstorm_with_a_short_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = library("C", "D", "E")
        spell_effects(REAL["Brainstorm"])[0].resolve(game, a, None)
        self.assertEqual((len(a.hand), len(a.library)), (1, 2))

    def test_ponder_reorders_the_top_three(self):
        game, _ = table3(pick("C", "A"))  # first asked goes on top: C, then of A and B the first (A)
        a = game.seats[0]
        a.library = library("A", "B", "C", "D")
        PutBackTop(3).resolve(game, a, None)
        self.assertEqual([c.name for c in a.library], ["C", "A", "B", "D"])

    def test_ponder_may_shuffle(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.library = library(*"ABCDEFGHIJKLMNOP")
        PutBackTop(3, shuffle=True).resolve(game, a, None)
        self.assertNotEqual([c.name for c in a.library], list("ABCDEFGHIJKLMNOP"))
        self.assertEqual(sorted(c.name for c in a.library), sorted("ABCDEFGHIJKLMNOP"))
        game, _ = table3(pick("No"))
        a = game.seats[0]
        a.library = library(*"ABCDEFGHIJKLMNOP")
        PutBackTop(3, shuffle=True).resolve(game, a, None)
        self.assertEqual([c.name for c in a.library][3:], list("DEFGHIJKLMNOP"))  # unshuffled below the top three


class CostTests(unittest.TestCase):
    def test_blasphemous_act_costs_one_less_for_each_creature(self):
        game, _ = table3()
        a, b, _ = game.seats
        act = REAL["Blasphemous Act"]  # {8}{R}
        a.battlefield = [Permanent(MOUNTAIN), *[Permanent(BEAR) for _ in range(4)]]
        b.battlefield = [Permanent(BEAR) for _ in range(3)]  # any player's creatures count
        self.assertIsNone(game._payment(a, act))  # seven creatures: {1}{R}, and only one Mountain
        b.battlefield.append(Permanent(BEAR))
        self.assertIsNotNone(game._payment(a, act))  # eight creatures: {R}

    def test_it_never_costs_less_than_its_colors(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(FOREST), *[Permanent(BEAR) for _ in range(12)]]
        self.assertIsNone(game._payment(a, REAL["Blasphemous Act"]))  # still needs {R}

    def test_costs_less_for_instants_and_sorceries_in_your_graveyard(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(MOUNTAIN)] * 1 + lands(1)
        a.graveyard = [BOLT, BOLT, COUNTED[0], BEAR]  # three count; the creature card does not
        self.assertEqual(game.cost_reduction(a, FLOCKING), 3)


class ManaForEachTests(unittest.TestCase):
    def sources(self, game, seat, permanent):
        return [s for s in game._mana_sources(seat) if s.permanent is permanent]

    def test_gaeas_cradle_makes_mana_for_each_creature(self):
        game, _ = table3()
        a = game.seats[0]
        cradle = Permanent(Card(name="Gaea's Cradle", type_line="Legendary Land", oracle_text=REAL["Gaea's Cradle"].oracle_text))
        a.battlefield = [cradle]
        self.assertEqual(self.sources(game, a, cradle), [])
        a.battlefield += [Permanent(BEAR) for _ in range(3)]
        self.assertEqual([s.types for s in self.sources(game, a, cradle)], [frozenset("G")] * 3)
        self.assertIsNotNone(game._payment(a, spell("{G}{G}{G}")))
        self.assertIsNone(game._payment(a, spell("{G}{G}{G}{G}")))

    def test_cabal_coffers_adds_black_for_each_swamp(self):
        game, _ = table3()
        a = game.seats[0]
        coffers = Permanent(Card(name="Cabal Coffers", type_line="Land", oracle_text=REAL["Cabal Coffers"].oracle_text))
        swamps = [Permanent(SWAMP) for _ in range(3)]
        a.battlefield = [*swamps, Permanent(FOREST), Permanent(FOREST)]
        four_black = spell("{B}{B}{B}{B}")
        self.assertIsNone(game._payment(a, four_black))  # three Swamps make three
        a.battlefield.append(coffers)
        self.assertIsNotNone(game._payment(a, four_black))  # Coffers pays {2} and makes one B for each Swamp

    def test_coffers_makes_nothing_without_swamps(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(Card(name="Cabal Coffers", type_line="Land", oracle_text=REAL["Cabal Coffers"].oracle_text)),
                         Permanent(FOREST), Permanent(FOREST)]
        self.assertIsNone(game._payment(a, spell("{B}")))

    def test_a_creature_that_made_this_turn_cannot_tap(self):
        game, _ = table3()
        a = game.seats[0]
        elf_card = Card(name="Archdruid", type_line="Creature — Elf Druid", power="2", toughness="2",
                        oracle_text="{T}: Add {G} for each Elf you control.")
        elf = Permanent(elf_card, sick=True)
        a.battlefield = [elf]
        self.assertEqual(self.sources(game, a, elf), [])
        elf.sick = False
        self.assertEqual(len(self.sources(game, a, elf)), 1)


if __name__ == "__main__":
    unittest.main()
