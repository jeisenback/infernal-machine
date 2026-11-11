"""Damage prevention, second slice (#235), from the cards' real Oracle text (CR 615): the Circles of Protection ("The next time a red source of
your choice would deal damage to you this turn, prevent that damage.", CR 615.7), and statics that prevent part of the damage: Gisela's half,
rounded up, Guardian Seraph's 1 and Temple Altisaur's all but 1."""

import unittest

from infernal_machine.game import Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, activate, lands, pick, real, table3

CIRCLE = real("Circle of Protection: Red", "{1}{W}", "Enchantment", "{1}: The next time a red source of your choice would deal damage to "
              "you this turn, prevent that damage.", colors=("W",))
ARTIFACTS = real("Circle of Protection: Artifacts", "{1}{W}", "Enchantment", "{2}: The next time an artifact source of your choice would "
                 "deal damage to you this turn, prevent that damage.", colors=("W",))
STORY = real("Story Circle", "{1}{W}{W}", "Enchantment", "As this enchantment enters, choose a color.\n{W}: The next time a source of your "
             "choice of the chosen color would deal damage to you this turn, prevent that damage.", colors=("W",))
GISELA = real("Gisela, Blade of Goldnight", "{4}{R}{W}{W}", "Legendary Creature — Angel", "Flying, first strike\nIf a source would deal "
              "damage to an opponent or a permanent an opponent controls, that source deals double that damage to that player or permanent "
              "instead.\nIf a source would deal damage to you or a permanent you control, prevent half that damage, rounded up.", "5", "5",
              colors=("R", "W"))
SERAPH = real("Guardian Seraph", "{2}{W}{W}", "Creature — Angel", "Flying\nIf a source an opponent controls would deal damage to you, "
              "prevent 1 of that damage.", "3", "4", colors=("W",))
ALTISAUR = real("Temple Altisaur", "{4}{W}", "Creature — Dinosaur", "If a source would deal damage to another Dinosaur you control, prevent "
                "all but 1 of that damage.", "3", "4", colors=("W",))
BALOTH = real("Frenzied Baloth", "{G}{G}", "Creature — Beast", "This spell can't be countered.\nTrample, haste\nCreature spells you control "
              "can't be countered.\nCombat damage can't be prevented.", "3", "2", colors=("G",))
CARDS = (CIRCLE, ARTIFACTS, STORY, GISELA, SERAPH, ALTISAUR)

GOBLIN = real("Raging Goblin", "{R}", "Creature — Goblin Berserker", "Haste", "1", "1", colors=("R",))
OGRE = real("Gray Ogre", "{2}{R}", "Creature — Ogre", "", "2", "2", colors=("R",))
BLUE = real("Wind Drake", "{2}{U}", "Creature — Drake", "Flying", "2", "2", colors=("U",))
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.", colors=("R",))
RAPTOR = real("Ripjaw Raptor", "{2}{G}{G}", "Creature — Dinosaur", "Enrage — Whenever this creature is dealt damage, draw a card.", "4", "5",
              colors=("G",))


class DamagePrevention2Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_circle_prevents_the_next_damage_of_the_red_source_chosen(self):
        game, _ = table3(pick("Gray Ogre"))
        a, b, _ = game.seats
        ogre, goblin = Permanent(OGRE), Permanent(GOBLIN)
        a.battlefield, b.battlefield = [Permanent(CIRCLE)] + lands(1), [goblin, ogre, Permanent(BLUE)]
        activate(game, a, "The next time a red source")
        game.damage(a, 1, source=goblin)  # not the source chosen
        game.damage(a, 2, source=ogre)
        game.damage(a, 2, source=ogre)  # only the next time
        self.assertEqual(a.life, 37)

    def test_a_circle_does_not_stop_combat_damage_that_cant_be_prevented(self):
        game, _ = table3(pick("Gray Ogre"))
        a, b, _ = game.seats
        ogre = Permanent(OGRE)
        a.battlefield, b.battlefield = [Permanent(CIRCLE)] + lands(1), [ogre, Permanent(BALOTH)]
        activate(game, a, "The next time a red source")
        game.damage(a, 2, source=ogre, combat=True)
        self.assertEqual(a.life, 38)

    def test_the_choice_is_only_among_sources_of_that_color(self):
        asked = []

        def policy(prompt, options):
            asked.append(options)
            return 0
        game, _ = table3(policy)
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(CIRCLE)] + lands(1), [Permanent(OGRE), Permanent(BLUE)]
        activate(game, a, "The next time a red source")
        self.assertTrue(any(any("Gray Ogre" in o for o in options) and not any("Wind Drake" in o for o in options) for options in asked))

    def test_a_circle_can_choose_a_red_spell_on_the_stack(self):
        game, _ = table3()
        a, b, _ = game.seats
        circle = Permanent(CIRCLE)
        a.battlefield = [circle]
        bolt = StackItem(BOLT, b)
        game.stack = [bolt]
        game.shield_from_source(a, "R", circle)
        game.stack = []
        game.resolving_item = bolt  # as the Bolt resolves, its damage has no permanent for a source
        game.damage(a, 3)
        game.resolving_item = None
        self.assertEqual(a.life, 40)

    def test_story_circle_uses_the_color_it_chose(self):
        game, _ = table3(pick("Wind Drake"))
        a, b, _ = game.seats
        story = Permanent(STORY)
        story.chosen_color = "U"
        drake = Permanent(BLUE)
        a.battlefield, b.battlefield = [story] + lands(1), [Permanent(OGRE), drake]
        activate(game, a, "The next time a source of your choice")
        game.damage(a, 2, source=drake)
        self.assertEqual(a.life, 40)

    def test_gisela_halves_damage_to_you_and_doubles_it_to_opponents(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        a.battlefield, b.battlefield = [Permanent(GISELA), bear], [Permanent(OGRE)]
        game.damage(a, 3, source=b.battlefield[0])  # half of 3, rounded up, is prevented: 1 is dealt
        game.damage(bear, 1, source=b.battlefield[0])  # half of 1, rounded up, is 1: none is dealt
        game.damage(b, 2, source=bear)
        self.assertEqual((a.life, bear.damage, b.life), (39, 0, 36))

    def test_combat_damage_that_cant_be_prevented_is_not_halved(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(GISELA)], [Permanent(OGRE), Permanent(BALOTH)]
        game.damage(a, 4, source=b.battlefield[0], combat=True)
        self.assertEqual(a.life, 36)

    def test_guardian_seraph_prevents_1_from_an_opponents_source(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine = Permanent(OGRE)
        a.battlefield, b.battlefield = [Permanent(SERAPH), mine], [Permanent(OGRE)]
        game.damage(a, 3, source=b.battlefield[0])
        game.damage(a, 3, source=mine)
        self.assertEqual(a.life, 40 - 2 - 3)

    def test_temple_altisaur_lets_1_through_to_another_dinosaur(self):
        game, _ = table3()
        a, b, _ = game.seats
        altisaur, raptor, bear = Permanent(ALTISAUR), Permanent(RAPTOR), Permanent(BEAR)
        a.battlefield, b.battlefield = [altisaur, raptor, bear], [Permanent(OGRE)]
        for creature in (raptor, altisaur, bear):
            game.damage(creature, 3, source=b.battlefield[0])
        self.assertEqual((raptor.damage, altisaur.damage, bear.damage), (1, 3, 3))


if __name__ == "__main__":
    unittest.main()
