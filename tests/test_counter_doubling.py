"""Doubling the counters you put, proliferating twice, and doubling the counters a permanent has (#203, the Atraxa list's counters
engine): Vorinclex, Monstrous Raider; Innkeeper's Talent at level 3; Tekuthal, Inquiry Dominus; Contagion Engine; Ezuri, Stalker of
Spheres; Deepglow Skate. Each from its real Oracle text; the cards that put the counters are probes."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import class_view
from infernal_machine.game import NO_TARGET, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, activate, enter, lands, pick, real, run_stack, script, table

VORINCLEX = real("Vorinclex, Monstrous Raider", "{4}{G}{G}", "Legendary Creature — Phyrexian Praetor",
                 "Trample, haste\n"
                 "If you would put one or more counters on a permanent or player, put twice that many of each of those kinds of counters "
                 "on that permanent or player instead.\n"
                 "If an opponent would put one or more counters on a permanent or player, they put half that many of each of those kinds "
                 "of counters on that permanent or player instead, rounded down.", "6", "6", colors=("G",))
TALENT = real("Innkeeper's Talent", "{1}{G}", "Enchantment — Class",
              "(Gain the next level as a sorcery to add its ability.)\n"
              "At the beginning of combat on your turn, put a +1/+1 counter on target creature you control.\n"
              "{G}: Level 2\n"
              "Permanents you control with counters on them have ward {1}.\n"
              "{3}{G}: Level 3\n"
              "If you would put one or more counters on a permanent or player, put twice that many of each of those kinds of counters on "
              "that permanent or player instead.", colors=("G",))
TEKUTHAL = real("Tekuthal, Inquiry Dominus", "{2}{U}{U}", "Legendary Creature — Phyrexian Horror",
                "Flying\nIf you would proliferate, proliferate twice instead.\n"
                "{1}{U/P}{U/P}, Remove three counters from among other artifacts, creatures, and planeswalkers you control: Put an "
                "indestructible counter on Tekuthal. ({U/P} can be paid with either {U} or 2 life.)", "3", "5", colors=("U",))
ENGINE = real("Contagion Engine", "{6}", "Artifact",
              "When this artifact enters, put a -1/-1 counter on each creature target player controls.\n"
              "{4}, {T}: Proliferate twice. (Choose any number of permanents and/or players, then give each another counter of each kind "
              "already there. Then do it again.)")
EZURI = real("Ezuri, Stalker of Spheres", "{2}{G}{U}", "Legendary Creature — Phyrexian Elf Warrior",
             "When Ezuri enters, you may pay {3}. If you do, proliferate twice.\nWhenever you proliferate, draw a card.", "3", "3",
             colors=("G", "U"))
SKATE = real("Deepglow Skate", "{4}{U}", "Creature — Fish",
             "When this creature enters, double the number of each kind of counter on any number of target permanents.", "3", "3",
             colors=("U",))

SPIKE = Card(name="Spike", mana_cost="{G}", cmc=1, type_line="Creature — Spike", power="1", toughness="1",
             oracle_text="When this creature enters, put a +1/+1 counter on target creature.")
TRIPLE_SPIKE = Card(name="Triple Spike", mana_cost="{G}", cmc=1, type_line="Creature — Spike", power="1", toughness="1",
                    oracle_text="When this creature enters, put three +1/+1 counters on target creature.")
INFECTOR = Card(name="Infector", mana_cost="{B}", cmc=1, type_line="Creature — Phyrexian", power="1", toughness="1",
                oracle_text="When this creature enters, each opponent gets a poison counter.")
SPREADER = Card(name="Spreader", mana_cost="{U}", cmc=1, type_line="Creature — Phyrexian", power="1", toughness="1",
                oracle_text="When this creature enters, proliferate.")
SEEDLING = Card(name="Seedling", mana_cost="{G}", cmc=1, type_line="Creature — Plant", power="0", toughness="0",
                oracle_text="This creature enters with a +1/+1 counter on it.")
FILLER = Card(name="Filler", type_line="Land")


def leveled(card, level):
    """A Class on the battlefield at `level`, as Game.level_up leaves it."""
    return Permanent(class_view(card, level), real_card=card, level=level)


class ParseTests(unittest.TestCase):
    def test_the_lines_are_read(self):
        for card in (VORINCLEX, EZURI, SKATE):
            self.assertEqual(unsupported_lines(card), [], card.name)
        # the Talent's level 2 ward and Tekuthal's activated ability are other work; their replacement lines are read
        self.assertEqual(unsupported_lines(TALENT), ["Permanents you control with counters on them have ward {1}."])
        self.assertNotIn("If you would proliferate, proliferate twice instead.", unsupported_lines(TEKUTHAL))
        self.assertNotIn("{4}, {T}: Proliferate twice.", unsupported_lines(ENGINE))


class CountersYouPutTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table(pick("Bear"), pick("Bear"))
        self.a, self.b = self.game.seats
        self.bear = Permanent(BEAR)
        self.b.battlefield = [self.bear]  # the opponent's Bear is what the probes aim at

    def test_vorinclex_doubles_the_counters_its_controller_puts_on_anything(self):
        self.a.battlefield = [Permanent(VORINCLEX)]
        enter(self.game, self.a, SPIKE)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 2})

    def test_without_vorinclex_one_counter_is_one(self):
        enter(self.game, self.a, SPIKE)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 1})

    def test_vorinclex_halves_what_an_opponent_puts_rounded_down(self):
        self.a.battlefield = [Permanent(VORINCLEX)]
        enter(self.game, self.b, TRIPLE_SPIKE)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 1})
        enter(self.game, self.b, SPIKE)  # one counter halves to none
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 1})

    def test_vorinclex_doubles_poison_counters_too(self):
        self.a.battlefield = [Permanent(VORINCLEX)]
        enter(self.game, self.a, INFECTOR)
        run_stack(self.game)
        self.assertEqual(self.b.player_counters.get("poison"), 2)

    def test_the_counters_a_permanent_enters_with_are_put_by_its_controller(self):
        self.a.battlefield = [Permanent(VORINCLEX)]
        mine = enter(self.game, self.a, SEEDLING)
        theirs = enter(self.game, self.b, SEEDLING)  # one counter, halved: none
        self.assertEqual((mine.counters, theirs.counters), ({"+1/+1": 2}, {}))

    def test_the_talent_doubles_only_at_level_three(self):
        self.a.battlefield = [leveled(TALENT, 3)]
        enter(self.game, self.a, SPIKE)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 2})
        self.a.battlefield = [leveled(TALENT, 2)]
        enter(self.game, self.a, SPIKE)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 3})


class ProliferateTwiceTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table(pick("Bear", "Pay"), pick("Bear"))
        self.a, self.b = self.game.seats
        self.bear = Permanent(BEAR, counters={"+1/+1": 1})

    def test_tekuthal_makes_a_proliferate_happen_twice(self):
        self.a.battlefield = [Permanent(TEKUTHAL), self.bear]
        enter(self.game, self.a, SPREADER)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 3})

    def test_tekuthal_does_not_change_an_opponents_proliferate(self):
        self.a.battlefield = [Permanent(TEKUTHAL)]
        self.b.battlefield = [self.bear]
        enter(self.game, self.b, SPREADER)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 2})

    def test_contagion_engine_proliferates_twice(self):
        self.a.battlefield = [Permanent(ENGINE), self.bear] + lands(4)
        activate(self.game, self.a, "Proliferate twice")
        self.assertEqual(self.bear.counters, {"+1/+1": 3})

    def test_ezuri_pays_three_to_proliferate_twice_and_draws_for_each(self):
        self.a.battlefield = [self.bear] + lands(3)
        self.a.library = [FILLER, FILLER, FILLER]
        enter(self.game, self.a, EZURI)
        run_stack(self.game)
        self.assertEqual(self.bear.counters, {"+1/+1": 3})
        self.assertEqual(len(self.a.hand), 2)

    def test_ezuri_does_not_draw_when_an_opponent_proliferates(self):
        self.a.battlefield = [Permanent(EZURI)]
        self.a.library = [FILLER, FILLER]
        self.b.battlefield = [self.bear]
        enter(self.game, self.b, SPREADER)
        run_stack(self.game)
        self.assertEqual(len(self.a.hand), 0)


class DoubleCountersTests(unittest.TestCase):
    def test_deepglow_skate_doubles_the_counters_on_the_chosen_permanents(self):
        game, _, _ = table(script("Bear 4/4", "Ogre", NO_TARGET))  # the Bear with counters, the Ogre, then stop
        a, b = game.seats
        bear = Permanent(BEAR, counters={"+1/+1": 2})
        ogre = Permanent(OGRE, counters={"+1/+1": 1, "charge": 3})
        plain = Permanent(BEAR)
        a.battlefield = [bear, plain]
        b.battlefield = [ogre]
        enter(game, a, SKATE)
        run_stack(game)
        self.assertEqual((bear.counters, ogre.counters, plain.counters), ({"+1/+1": 4}, {"+1/+1": 2, "charge": 6}, {}))

    def test_the_skate_may_choose_none(self):
        game, _, _ = table(pick(NO_TARGET))
        a, _ = game.seats
        bear = Permanent(BEAR, counters={"+1/+1": 2})
        a.battlefield = [bear]
        enter(game, a, SKATE)
        run_stack(game)
        self.assertEqual(bear.counters, {"+1/+1": 2})


if __name__ == "__main__":
    unittest.main()
