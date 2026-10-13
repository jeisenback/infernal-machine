"""Epic Confrontation, Hunt the Weak, Chelonian Tackle, Swift Kick ...: "Target creature you control gets +1/+2 until end of turn. It fights target creature you
don't control." The creature that got the pump or the counters is the one that fights (Each deals damage equal to its power to the other);
a creature with no sentence before it ("When this creature enters, it fights up to one target creature ...") is the source fighting."""

import unittest

from infernal_machine.effects.outcomes import _parse, _split_sentences
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, creature, real, script

CONFRONTATION = real("Epic Confrontation", "{1}{G}", "Sorcery", "Target creature you control gets +1/+2 until end of turn. It fights target creature "
                     "you don't control. (Each deals damage equal to its power to the other.)", colors=("G",))
HUNT = real("Hunt the Weak", "{3}{G}", "Sorcery", "Put a +1/+1 counter on target creature you control. Then that creature fights target creature "
            "you don't control. (Each deals damage equal to its power to the other.)", colors=("G",))
TACKLE = real("Chelonian Tackle", "{2}{G}", "Sorcery", "Target creature you control gets +0/+10 until end of turn. Then it fights up to one target "
              "creature an opponent controls. (Each deals damage equal to its power to the other.)", colors=("G",))
KICK = real("Swift Kick", "{3}{R}", "Instant", "Target creature you control gets +1/+0 until end of turn. It fights target creature you don't "
            "control.", colors=("R",))
BRAWLER = real("Pheres-Band Brawler", "{4}{G}{G}", "Creature — Centaur Warrior", "When this creature enters, it fights up to one target creature "
               "you don't control. (Each deals damage equal to its power to the other.)", "4", "4", colors=("G",))
WOLF = creature("Wolf", 2, 2)
GIANT = creature("Giant", 5, 5)


class FightItTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (CONFRONTATION, HUNT, TACKLE, KICK, BRAWLER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_pumped_creature_fights(self):
        bear = Permanent(BEAR)
        t = Table(CONFRONTATION, policy=script("Bear", "Ogre"), n=4, mine=[bear], theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(t.b.battlefield, [])  # a 3/4 Bear dealt 3 to the 3/3 Ogre
        self.assertEqual(bear.damage, 3)
        self.assertIn(bear, t.a.battlefield)  # and survived the 3 it took

    def test_a_creature_that_was_not_chosen_does_not_fight(self):
        bear, wolf = Permanent(BEAR), Permanent(WOLF)
        t = Table(CONFRONTATION, policy=script("Bear", "Ogre"), n=4, mine=[wolf, bear], theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(wolf.damage, 0)

    def test_a_counter_makes_it_bigger_before_it_fights(self):
        bear = Permanent(BEAR)
        t = Table(HUNT, policy=script("Bear", "Wolf"), n=5, mine=[bear], theirs=[Permanent(WOLF)]).cast()
        self.assertEqual(t.b.battlefield, [])  # a 3/3 Bear kills the 2/2 Wolf
        self.assertEqual(bear.damage, 2)

    def test_it_can_only_fight_a_creature_you_do_not_control(self):
        t = Table(HUNT, policy=script("Bear", "Ogre"), n=5, mine=[Permanent(BEAR), Permanent(WOLF)], theirs=[Permanent(OGRE)]).cast()
        targets = [options for prompt, options in t.a.player.prompts if prompt.startswith("Choose a target")]
        self.assertEqual([[o.split(" ")[0] for o in options] for options in targets], [["Bear", "Wolf"], ["Ogre"]])

    def test_it_after_an_effect_that_picks_no_creature_is_not_understood(self):
        # two real sentences from different cards: "it" would have nothing to mean
        self.assertIsNone(_parse(_split_sentences("Draw a card. It fights target creature you don't control.")))

    def test_up_to_one_can_be_left_out(self):
        bear = Permanent(BEAR)
        t = Table(TACKLE, policy=script("Bear", "No target"), n=4, mine=[bear], theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(bear.damage, 0)
        self.assertEqual(t.game.toughness(bear), 12)  # the pump happened

    def test_an_instant_works_too(self):
        bear = Permanent(BEAR)
        t = Table(KICK, policy=script("Bear", "Wolf"), n=5, mine=[bear], theirs=[Permanent(WOLF)]).cast()
        self.assertEqual(t.b.battlefield, [])

    def test_a_creature_that_enters_fights_itself(self):
        t = Table(BRAWLER, policy=script("Giant"), n=6, theirs=[Permanent(GIANT)]).cast()
        self.assertEqual([p.card.name for p in t.a.battlefield if "Creature" in p.card.type_line], [])  # the 4/4 took 5 and died
        self.assertEqual(t.b.battlefield[0].damage, 4)  # the Giant took 4


if __name__ == "__main__":
    unittest.main()
