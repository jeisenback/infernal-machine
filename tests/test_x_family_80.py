"""The cards of issue #80 whose lines depend on X (Fractal Harness, Kinetic Ooze, Lattice Library, Brass Infiniscope, Open the
Way, Animist's Awakening, Unbound Flourishing, Oversimplify). Lines are the cards' own Oracle text from Scryfall; each has cases
where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire
from tests.test_x_targets import script
from tests.test_triggers_80 import FOREST, PLAINS, RELIC, SHRINE, card

HARNESS = Card(name="Fractal Harness", mana_cost="{X}{2}{G}", type_line="Artifact — Equipment",
               oracle_text="When this Equipment enters, create a 0/0 green and blue Fractal creature token. Put X +1/+1 counters on "
                           "it and attach this Equipment to it.\nWhenever equipped creature attacks, double the number of +1/+1 "
                           "counters on it.\nEquip {2}")


class FractalHarnessTests(unittest.TestCase):
    def enter(self, x):
        game, _ = table3(pick())
        a = game.seats[0]
        harness = Permanent(HARNESS, sick=True)
        game._enter(a, harness, x=x)
        run_stack(game)
        game._check_state()
        fractal = next((p for p in a.battlefield if p.card.name == "Fractal"), None)
        return game, a, harness, fractal

    def test_parse(self):
        self.assertEqual(unsupported_lines(HARNESS), [])

    def test_the_fractal_comes_in_with_x_counters_and_the_harness_attached(self):
        game, a, harness, fractal = self.enter(3)
        self.assertEqual((fractal.counters.get("+1/+1"), game.power(fractal)), (3, 3))
        self.assertIs(harness.attached_to, fractal)

    def test_x_of_zero_makes_a_fractal_that_dies(self):
        game, a, harness, fractal = self.enter(0)
        self.assertIsNone(fractal)  # 0/0 with no counters

    def test_each_cast_uses_its_own_x(self):
        game, a, harness, fractal = self.enter(2)
        other = Permanent(HARNESS, sick=True)
        game._enter(a, other, x=5)
        run_stack(game)
        self.assertEqual(sorted(p.counters.get("+1/+1", 0) for p in a.battlefield if p.card.name == "Fractal"), [2, 5])


OOZE = Card(name="Kinetic Ooze", mana_cost="{X}{G}", type_line="Creature — Ooze", power="0", toughness="0",
            oracle_text="This creature enters with X +1/+1 counters on it.\nWhen this creature enters, destroy up to one target "
                        "artifact or enchantment with mana value X or less. If X is 5 or more, you draw a card. If X is 10 or more, "
                        "double the number of +1/+1 counters on any number of other target creatures.")
IDOL3 = Card(name="Idol", mana_cost="{3}", cmc=3.0, type_line="Artifact")
SHRINE6 = Card(name="Big Shrine", mana_cost="{4}{W}{W}", cmc=6.0, type_line="Enchantment")


class KineticOozeTests(unittest.TestCase):
    def enter(self, x, *choices, mine=(), theirs=()):
        game, _ = table3(pick(*choices))
        a, b, _ = game.seats
        a.library = [FOREST] * 10
        ooze = Permanent(OOZE, sick=True)
        a.battlefield = list(mine)
        b.battlefield = list(theirs)
        game._enter(a, ooze, x=x)
        run_stack(game)
        return game, a, b, ooze

    def test_parse(self):
        self.assertEqual(unsupported_lines(OOZE), [])

    def test_it_enters_with_x_counters(self):
        game, a, b, ooze = self.enter(3)
        self.assertEqual(ooze.counters.get("+1/+1"), 3)

    def test_it_destroys_an_artifact_or_enchantment_with_mana_value_x_or_less(self):
        idol = Permanent(IDOL3)
        game, a, b, ooze = self.enter(3, "Idol", theirs=[idol])
        self.assertEqual(b.battlefield, [])

    def test_not_one_with_a_greater_mana_value(self):
        shrine = Permanent(SHRINE6)
        game, a, b, ooze = self.enter(3, "Big Shrine", theirs=[shrine])
        self.assertEqual(b.battlefield, [shrine])

    def test_it_may_destroy_nothing(self):
        idol = Permanent(IDOL3)
        game, a, b, ooze = self.enter(3, "No target", theirs=[idol])
        self.assertEqual(b.battlefield, [idol])

    def test_x_of_five_draws_a_card_and_x_of_four_does_not(self):
        self.assertEqual(len(self.enter(5)[1].hand), 1)
        self.assertEqual(len(self.enter(4)[1].hand), 0)

    def test_x_of_ten_doubles_counters_on_any_number_of_other_creatures(self):
        grown = Permanent(BEAR, counters={"+1/+1": 3})
        theirs = Permanent(OGRE, counters={"+1/+1": 2})
        plain = Permanent(BEAR)
        game, a, b, ooze = self.enter(10, "Bear", "Ogre", mine=[grown, plain], theirs=[theirs])
        self.assertEqual((grown.counters.get("+1/+1"), theirs.counters.get("+1/+1"), plain.counters.get("+1/+1")), (6, 4, None))
        self.assertEqual(ooze.counters.get("+1/+1"), 10)  # "other" creatures only

    def test_below_ten_nothing_is_doubled(self):
        grown = Permanent(BEAR, counters={"+1/+1": 3})
        game, a, b, ooze = self.enter(9, "Bear", mine=[grown])
        self.assertEqual(grown.counters.get("+1/+1"), 3)


LIBRARY = Card(name="Lattice Library", mana_cost="{X}{G}{G}", type_line="Enchantment",
               oracle_text="This enchantment enters with X study counters on it.\nWhen this enchantment enters and whenever you cast "
                           "your first spell with {X} in its mana cost each turn, create a 0/0 green and blue Fractal creature "
                           "token. Put a number of +1/+1 counters on it equal to the number of study counters on this enchantment.")
X_SPELL = Card(name="Blast", mana_cost="{X}{R}", type_line="Sorcery")
X_SPELL2 = Card(name="Blast Two", mana_cost="{X}{U}", type_line="Instant")
FLAT_SPELL = Card(name="Flat", mana_cost="{2}{R}", cmc=3.0, type_line="Sorcery")


class LatticeLibraryTests(unittest.TestCase):
    def enter(self, x):
        game, _ = table3(pick())
        a = game.seats[0]
        library = Permanent(LIBRARY, sick=True)
        game._enter(a, library, x=x)
        run_stack(game)
        return game, a, library

    def fractals(self, seat):
        return sorted(p.counters.get("+1/+1", 0) for p in seat.battlefield if p.card.name == "Fractal")

    def cast(self, game, seat, spell):
        seat.cast_log.append((game.turn, spell))
        game._observe("cast", spell, seat)
        run_stack(game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(LIBRARY), [])

    def test_it_enters_with_study_counters_and_makes_a_fractal_of_that_size(self):
        game, a, library = self.enter(3)
        self.assertEqual((library.counters.get("study"), self.fractals(a)), (3, [3]))

    def test_the_first_x_spell_each_turn_makes_another(self):
        game, a, library = self.enter(2)
        self.cast(game, a, X_SPELL)
        self.assertEqual(self.fractals(a), [2, 2])

    def test_the_second_x_spell_the_same_turn_does_not(self):
        game, a, library = self.enter(2)
        self.cast(game, a, X_SPELL)
        self.cast(game, a, X_SPELL2)
        self.assertEqual(self.fractals(a), [2, 2])

    def test_the_next_turn_counts_again(self):
        game, a, library = self.enter(2)
        self.cast(game, a, X_SPELL)
        game.turn += 1
        self.cast(game, a, X_SPELL2)
        self.assertEqual(self.fractals(a), [2, 2, 2])

    def test_a_spell_without_x_does_not(self):
        game, a, library = self.enter(2)
        self.cast(game, a, FLAT_SPELL)
        self.assertEqual(self.fractals(a), [2])

    def test_an_opponents_x_spell_does_not(self):
        game, a, library = self.enter(2)
        self.cast(game, game.seats[1], X_SPELL)
        self.assertEqual(self.fractals(a), [2])

    def test_the_fractal_is_as_big_as_the_study_counters_now(self):
        game, a, library = self.enter(2)
        library.counters["study"] = 5
        self.cast(game, a, X_SPELL)
        self.assertEqual(self.fractals(a), [2, 5])


INFINISCOPE = Card(name="Brass Infiniscope", mana_cost="{4}", cmc=4.0, type_line="Artifact",
                   oracle_text="{T}: Add {C}{C}. When you next cast a spell with {X} in its mana cost this turn, you draw a card and "
                               "gain half X life, rounded down.")
BLAST = Card(name="Blast", mana_cost="{X}{1}", type_line="Sorcery", oracle_text="Draw a card.")


class BrassInfiniscopeTests(unittest.TestCase):
    def play(self, spell, x, lands_in_play=3, scopes=1, tap_scope=True):
        game, _ = table3(script(str(x)))
        a = game.seats[0]
        a.battlefield = [Permanent(INFINISCOPE) for _ in range(scopes)] + lands(lands_in_play)
        a.library = [FOREST] * 10
        a.hand = [spell]
        life = a.life
        game._perform(a, CAST + spell.name)
        run_stack(game)
        return game, a, a.life - life

    def test_parse(self):
        self.assertEqual(unsupported_lines(INFINISCOPE), [])

    def test_it_makes_two_colorless_mana(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(INFINISCOPE)]
        self.assertEqual(len(game._mana_sources(a)), 2)

    def test_casting_an_x_spell_with_its_mana_draws_and_gains_half_x(self):
        game, a, gained = self.play(BLAST, 4, lands_in_play=3)  # X=4 and {R} take five mana: the scope's two and three lands
        self.assertEqual(gained, 2)
        self.assertEqual(len(a.hand), 2)  # the rider's card and the spell's own

    def test_half_x_is_rounded_down(self):
        game, a, gained = self.play(BLAST, 3, lands_in_play=2)
        self.assertEqual(gained, 1)

    def test_a_spell_without_x_does_not_trigger_it(self):
        game, a, gained = self.play(Card(name="Flat", mana_cost="{1}{R}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card."), 0)
        self.assertEqual((gained, len(a.hand)), (0, 1))

    def test_paying_with_lands_alone_does_not_arm_it(self):
        game, a, gained = self.play(BLAST, 1, lands_in_play=3, scopes=0)
        self.assertEqual((gained, len(a.hand)), (0, 1))

    def test_it_is_only_for_the_next_x_spell(self):
        game, a, gained = self.play(BLAST, 1, lands_in_play=3)
        a.hand.append(Card(name="Blast Two", mana_cost="{X}{1}", type_line="Sorcery", oracle_text="Draw a card."))
        before = (a.life, len(a.hand))
        for p in a.battlefield:
            p.tapped = p.card.name == "Brass Infiniscope"  # only the lands are untapped: the scope arms nothing again
        game._perform(a, CAST + "Blast Two")
        run_stack(game)
        self.assertEqual((a.life, len(a.hand)), (before[0], before[1] - 1 + 1))  # the spell's own card, no rider card

    def test_a_trigger_set_up_on_an_earlier_turn_is_forgotten(self):
        game, a, gained = self.play(Card(name="Flat", mana_cost="{4}", cmc=4.0, type_line="Sorcery", oracle_text="Draw a card."), 0, lands_in_play=2)
        game.turn += 1
        for p in a.battlefield:
            p.tapped = False
        a.hand = [BLAST]
        a.library = [FOREST] * 10
        a.life = 40
        game._perform(a, CAST + "Blast")
        run_stack(game)
        self.assertEqual((a.life - 40, len(a.hand)), (0, 2))  # the spell's own card and one rider card; a leftover trigger would add another


OPEN_THE_WAY = Card(name="Open the Way", mana_cost="{X}{G}{G}", type_line="Sorcery",
                    oracle_text="X can't be greater than the number of players in the game.\nReveal cards from the top of your "
                                "library until you reveal X land cards. Put those land cards onto the battlefield tapped and the "
                                "rest on the bottom of your library in a random order.")
AWAKENING = Card(name="Animist's Awakening", mana_cost="{X}{G}", type_line="Sorcery",
                 oracle_text="Reveal the top X cards of your library. Put all land cards from among them onto the battlefield "
                             "tapped and the rest on the bottom of your library in a random order.\nSpell mastery — If there "
                             "are two or more instant and/or sorcery cards in your graveyard, untap those lands.")
INSTANT_CARD = Card(name="Shock", mana_cost="{R}", type_line="Instant")
SORCERY_CARD = Card(name="Ritual", mana_cost="{B}", type_line="Sorcery")


class RevealLandsTests(unittest.TestCase):
    def cast(self, spell, x, library, graveyard=()):
        game, _ = table3(script(str(x)))
        a = game.seats[0]
        a.battlefield = lands(spell.mana_cost.count("{") - 1 + x)  # exactly what the spell costs
        a.hand = [spell]
        a.library = list(library) + [BEAR] * 5
        a.graveyard = list(graveyard)
        game._perform(a, CAST + spell.name)
        run_stack(game)
        return game, a

    def entered(self, seat):
        return [p for p in seat.battlefield if p.card.name in ("Forest", "Plains")]

    def test_parse(self):
        self.assertEqual(unsupported_lines(OPEN_THE_WAY), [])
        self.assertEqual(unsupported_lines(AWAKENING), [])

    def test_open_the_way_stops_at_the_xth_land_and_puts_the_rest_underneath(self):
        game, a = self.cast(OPEN_THE_WAY, 2, [RELIC, FOREST, RELIC, PLAINS, FOREST])
        lands_in = self.entered(a)
        self.assertEqual(sorted(p.card.name for p in lands_in), ["Forest", "Plains"])
        self.assertTrue(all(p.tapped for p in lands_in))
        names = [c.name for c in a.library]
        self.assertEqual(names[0], "Forest")  # the third land was never revealed: it is still on top
        self.assertEqual(names.count("Relic"), 2)  # the revealed non-lands went underneath

    def test_open_the_way_with_too_few_lands_takes_what_there_is(self):
        game, a = self.cast(OPEN_THE_WAY, 2, [RELIC, FOREST])
        self.assertEqual(len(self.entered(a)), 1)

    def test_animists_awakening_puts_every_land_among_the_top_x(self):
        game, a = self.cast(AWAKENING, 4, [FOREST, RELIC, PLAINS, RELIC, FOREST])
        self.assertEqual(sorted(p.card.name for p in self.entered(a)), ["Forest", "Plains"])
        self.assertTrue(all(p.tapped for p in self.entered(a)))

    def test_animists_awakening_only_looks_at_x_cards(self):
        game, a = self.cast(AWAKENING, 2, [RELIC, FOREST, PLAINS])
        self.assertEqual(len(self.entered(a)), 1)

    def test_spell_mastery_untaps_those_lands(self):
        game, a = self.cast(AWAKENING, 3, [FOREST, PLAINS, RELIC], graveyard=[INSTANT_CARD, SORCERY_CARD])
        self.assertEqual([p.tapped for p in self.entered(a)], [False, False])

    def test_without_two_instants_or_sorceries_the_lands_stay_tapped(self):
        game, a = self.cast(AWAKENING, 3, [FOREST, PLAINS, RELIC], graveyard=[INSTANT_CARD, RELIC])
        self.assertEqual([p.tapped for p in self.entered(a)], [True, True])

    def test_spell_mastery_untaps_only_the_lands_it_put_onto_the_battlefield(self):
        game, a = self.cast(AWAKENING, 1, [FOREST], graveyard=[INSTANT_CARD, SORCERY_CARD])
        others = [p for p in a.battlefield if p.card.name != "Forest"]
        self.assertTrue(all(p.tapped for p in others))  # they paid for the spell
