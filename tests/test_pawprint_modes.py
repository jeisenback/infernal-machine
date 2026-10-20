"""Pawprint modes (a Season): "Choose up to five {P} worth of modes. You may choose the same mode more than once." and modes written
"{P}{P} — ...": the cost of each mode comes out of the five pawprints. Season of Gathering, Season of Loss and Season of Weaving."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import DONE_MODES, MODE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, creature, pick, real, script

HEADER = "Choose up to five {P} worth of modes. You may choose the same mode more than once.\n"
GATHERING = real("Season of Gathering", "{4}{G}{G}", "Sorcery", HEADER + "{P} — Put a +1/+1 counter on a creature you control. It gains "
                 "vigilance and trample until end of turn.\n{P}{P} — Choose artifact or enchantment. Destroy all permanents of the chosen "
                 "type.\n{P}{P}{P} — Draw cards equal to the greatest power among creatures you control.", colors=("G",))
LOSS = real("Season of Loss", "{3}{B}{B}", "Sorcery", HEADER + "{P} — Each player sacrifices a creature of their choice.\n{P}{P} — Draw a "
            "card for each creature that died under your control this turn.\n{P}{P}{P} — Each opponent loses X life, where X is the number of "
            "creature cards in your graveyard.", colors=("B",))
WEAVING = real("Season of Weaving", "{4}{U}{U}", "Sorcery", HEADER + "{P} — Draw a card.\n{P}{P} — Choose an artifact or creature you "
               "control. Create a token that's a copy of it.\n{P}{P}{P} — Return each nonland, nontoken permanent to its owner's hand.",
               colors=("U",))
BURROW = real("Season of the Burrow", "{3}{W}{W}", "Sorcery", HEADER + "{P} \u2014 Create a 1/1 white Rabbit creature token.\n{P}{P} \u2014 Exile target "
              "nonland permanent. Its controller draws a card.\n{P}{P}{P} \u2014 Return target permanent card with mana value 3 or less from your "
              "graveyard to the battlefield with an indestructible counter on it.", colors=("W",))
TROPHY = real("Trophy", "{2}", "Artifact", "")
SHRINE = real("Shrine", "{2}", "Enchantment", "")
LIBRARY = [Card(name=f"Card {i}", type_line="Land") for i in range(12)]


def modes_asked(table):
    return [options for prompt, options in table.a.player.prompts if MODE_PROMPT.matches(prompt)]


class PawprintTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GATHERING, LOSS, WEAVING):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_five_one_pawprint_modes(self):
        t = Table(WEAVING, policy=pick("{P} — Draw"), n=8, library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 5)
        self.assertEqual(len(modes_asked(t)), 5)

    def test_each_mode_costs_what_it_says_and_the_budget_runs_out(self):
        t = Table(WEAVING, policy=script("{P}{P}{P}", "{P}{P} — Choose"), n=8, library=LIBRARY, mine=[Permanent(OGRE)])
        t.cast()
        asked = modes_asked(t)
        self.assertEqual([len(options) for options in asked], [4, 3])  # all three modes and Done; then, with 2 left, no three-pawprint mode
        self.assertTrue(all(DONE_MODES in options for options in asked))
        self.assertTrue(all(not option.startswith("{P}{P}{P}") for option in asked[1]))
        # all five spent, so no third question; in printed order the copy is made first and then every nontoken permanent is returned
        self.assertEqual((sorted(c.name for c in t.a.hand), [p.card.type_line.startswith("Token") for p in t.a.battlefield][-1]), (["Ogre"], True))

    def test_done_stops_early(self):
        t = Table(WEAVING, policy=script("{P} — Draw", "Done"), n=8, library=LIBRARY).cast()
        self.assertEqual((len(t.a.hand), len(modes_asked(t))), (1, 2))

    def test_choose_artifact_or_enchantment_destroys_all_of_the_chosen_type(self):
        t = Table(GATHERING, policy=script("{P}{P}", "Done", "Artifact"), n=8, mine=[Permanent(TROPHY), Permanent(SHRINE)],
                  theirs=[Permanent(TROPHY), Permanent(SHRINE)]).cast()
        left = sorted(p.card.name for s in (t.a, t.b) for p in s.battlefield if "Land" not in p.card.type_line)
        self.assertEqual(left, ["Shrine", "Shrine"])

    def test_draw_cards_equal_to_the_greatest_power(self):
        t = Table(GATHERING, policy=script("{P}{P}{P}", "Done"), n=8, mine=[Permanent(OGRE), Permanent(BEAR)], library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 3)

    def test_draw_for_each_creature_that_died_under_your_control(self):
        ogre, bear = Permanent(OGRE), Permanent(BEAR)
        t = Table(LOSS, policy=script("{P}{P}", "Done"), n=8, mine=[ogre, bear], theirs=[Permanent(OGRE)], library=LIBRARY)
        t.game._leave_battlefield(ogre, "sacrificed")
        t.game._leave_battlefield(bear, "destroyed")
        t.game._leave_battlefield(t.b.battlefield[0], "destroyed")  # theirs does not count
        t.cast()
        self.assertEqual(len(t.a.hand), 2)

    def test_none_died_this_turn_draws_nothing(self):
        t = Table(LOSS, policy=script("{P}{P}", "Done"), n=8, library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 0)

    def test_creatures_that_died_on_an_earlier_turn_do_not_count(self):
        t = Table(LOSS, policy=script("{P}{P}", "Done"), n=8, library=LIBRARY)
        t.a.died, t.a.died_turn = 3, t.game.turn - 1
        t.cast()
        self.assertEqual(len(t.a.hand), 0)

    def test_each_opponent_loses_life_for_the_creature_cards_in_your_graveyard(self):
        t = Table(LOSS, policy=script("{P}{P}{P}", "Done"), n=8, graveyard=[creature("A", 1, 1), creature("B", 1, 1), TROPHY]).cast()
        self.assertEqual((t.b.life, t.c.life), (38, 38))

    def test_a_chosen_artifact_or_creature_is_copied(self):
        t = Table(WEAVING, policy=script("{P}{P} — Choose", "Done", "Ogre"), n=8, mine=[Permanent(OGRE), Permanent(BEAR)]).cast()
        tokens = [p for p in t.a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual([p.card.name for p in tokens], ["Ogre"])

    def test_return_each_nonland_nontoken_permanent(self):
        t = Table(WEAVING, policy=script("{P}{P}{P}", "{P}{P} — Choose", "Ogre"), n=8, mine=[Permanent(OGRE)], theirs=[Permanent(BEAR)]).cast()
        self.assertEqual((sorted(c.name for c in t.a.hand), sorted(c.name for c in t.b.hand)), (["Ogre"], ["Bear"]))
        self.assertEqual([p.card.type_line.startswith("Token") for p in t.a.battlefield if "Land" not in p.card.type_line], [True])  # the token stays


class SeasonOfTheBurrowTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(BURROW), [])

    def test_exile_a_nonland_permanent_and_its_controller_draws(self):
        t = Table(BURROW, policy=script("{P}{P} \u2014 Exile", "Done", "Ogre"), n=8, theirs=[Permanent(OGRE)], library=LIBRARY)
        t.b.library = list(LIBRARY)
        t.cast()
        self.assertEqual((t.b.battlefield, [c.name for c in t.b.exile], len(t.b.hand), len(t.a.hand)), ([], ["Ogre"], 1, 0))

    def test_your_own_permanent_draws_for_you(self):
        t = Table(BURROW, policy=script("{P}{P} \u2014 Exile", "Done", "Ogre"), n=8, mine=[Permanent(OGRE)], library=LIBRARY).cast()
        self.assertEqual((len(t.a.hand), [c.name for c in t.a.exile]), (1, ["Ogre"]))

    def test_a_token_exiled_still_draws(self):
        token = Permanent(Card(name="Rabbit", type_line="Token Creature \u2014 Rabbit", power="1", toughness="1"))
        t = Table(BURROW, policy=script("{P}{P} \u2014 Exile", "Done", "Rabbit"), n=8, theirs=[token])
        t.b.library = list(LIBRARY)
        t.cast()
        self.assertEqual((t.b.battlefield, len(t.b.hand)), ([], 1))

    def test_return_a_cheap_permanent_with_an_indestructible_counter(self):
        cheap, dear = creature("Cheap", 2, 2), real("Dear", "{3}{G}", "Creature \u2014 Bear", "", "4", "4")
        t = Table(BURROW, policy=script("{P}{P}{P}", "Done", "Cheap"), n=8, graveyard=[cheap, dear]).cast()
        (back,) = [p for p in t.a.battlefield if p.card.name == "Cheap"]
        self.assertEqual((back.counters, t.game.has_keyword(back, "indestructible"), "Dear" in [c.name for c in t.a.graveyard]), ({"indestructible": 1}, True, True))
        t.game.destroy(back)
        self.assertIn(back, t.a.battlefield)  # it survives

    def test_a_permanent_that_costs_too_much_is_not_a_target(self):
        t = Table(BURROW, policy=script("{P}{P}{P}", "Done"), n=8, graveyard=[real("Dear", "{3}{G}", "Creature \u2014 Bear", "", "4", "4")])
        t.cast()
        asked = modes_asked(t)
        self.assertTrue(all(not option.startswith("{P}{P}{P}") for option in asked[0]))  # nothing to return: the mode is not offered

    def test_three_pawprints_and_two_fill_the_budget(self):
        cheap = creature("Cheap", 2, 2)
        t = Table(BURROW, policy=script("{P}{P}{P}", "{P}{P} \u2014 Exile", "Cheap", "Ogre"), n=8, graveyard=[cheap], theirs=[Permanent(OGRE)])
        t.b.library = list(LIBRARY)
        t.cast()
        self.assertEqual(len(modes_asked(t)), 2)  # five pawprints spent: no third question
        self.assertEqual(([p.card.name for p in t.a.battlefield if "Land" not in p.card.type_line], [c.name for c in t.b.exile]), (["Cheap"], ["Ogre"]))


if __name__ == "__main__":
    unittest.main()
