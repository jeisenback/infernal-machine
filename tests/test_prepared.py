import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import BecomePrepared, enters_prepared, triggered_abilities
from infernal_machine.game import CAST_PREPARED, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

STUDY = Card(name="Quick Study", mana_cost="{1}{U}", type_line="Instant", oracle_text="Draw two cards.", cmc=2.0)
RITE = Card(name="Rite of Mending", mana_cost="{2}{W}", type_line="Sorcery", oracle_text="You gain 3 life.", cmc=3.0)
ADEPT = Card(name="Study Adept // Quick Study", mana_cost="{1}{U}", type_line="Creature — Wizard",
             oracle_text="This creature enters prepared. (While it's prepared, you may cast a copy of its spell. "
                         "Doing so unprepares it.)", prepare=STUDY)
RALLIER = Card(name="Rallier // Rite of Mending", mana_cost="{2}{W}", type_line="Creature — Fox",
               oracle_text="Vigilance\nWhenever you attack with two or more creatures, this creature becomes prepared. "
                           "(While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)",
               prepare=RITE)


class ParseTests(unittest.TestCase):
    def test_enters_prepared_and_becomes_prepared(self):
        self.assertTrue(enters_prepared(ADEPT))
        self.assertFalse(enters_prepared(RALLIER))
        [ability] = [a for a in triggered_abilities(RALLIER) if a.event == "attack_with_two"]
        self.assertEqual(ability.effects, (BecomePrepared(),))

    def test_the_report_checks_both_halves(self):
        self.assertEqual(unsupported_lines(ADEPT), [])
        self.assertEqual(unsupported_lines(RALLIER), [])
        broken = Card(name="Broken // Wild Idea", type_line="Creature — Wizard", oracle_text="This creature enters prepared.",
                      prepare=Card(name="Wild Idea", mana_cost="{G}", type_line="Sorcery", oracle_text="Do something strange."))
        self.assertEqual(unsupported_lines(broken), ["Wild Idea: Do something strange."])

    def test_scryfall_prepare_layout_keeps_the_spell_half(self):
        card = Card.from_scryfall({
            "id": "x", "name": "Rallier // Rite of Mending", "layout": "prepare", "cmc": 3.0, "color_identity": ["W"],
            "legalities": {"commander": "legal"},
            "card_faces": [{"name": "Rallier", "mana_cost": "{2}{W}", "type_line": "Creature — Fox",
                            "oracle_text": "Vigilance", "colors": ["W"], "power": "2", "toughness": "2"},
                           {"name": "Rite of Mending", "mana_cost": "{2}{W}", "type_line": "Sorcery",
                            "oracle_text": "You gain 3 life."}]})
        self.assertEqual((card.name, card.power), ("Rallier // Rite of Mending", "2"))
        self.assertEqual((card.prepare.name, card.prepare.cmc, card.prepare.colors), ("Rite of Mending", 3.0, ("W",)))
        self.assertEqual(Card.from_dict(card.to_dict()), card)  # survives the card cache


class PreparedTests(unittest.TestCase):
    def test_enters_prepared(self):
        game, _ = table3()
        a = game.seats[0]
        entered = Permanent(ADEPT)
        game._enter(a, entered)
        self.assertTrue(entered.prepared)

    def test_cast_a_copy_of_the_spell_and_become_unprepared(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        adept = Permanent(ADEPT, prepared=True)
        a.battlefield = [adept, *lands(2)]
        self.assertIn(CAST_PREPARED + "Quick Study", game.legal_actions(a))
        game._perform(a, CAST_PREPARED + "Quick Study")
        run_stack(game)
        self.assertEqual((len(a.hand), adept.prepared), (2, False))
        self.assertEqual((a.graveyard, a.exile), ([], []))  # a copy isn't a card: it just ends
        self.assertNotIn(CAST_PREPARED + "Quick Study", game.legal_actions(a))

    def test_the_copy_counts_as_a_spell_that_was_cast(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(ADEPT, prepared=True), *lands(2)]
        game._perform(a, CAST_PREPARED + "Quick Study")
        self.assertEqual([c.name for turn, c in a.cast_log], ["Quick Study"])

    def test_not_offered_without_mana_or_when_not_prepared(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(ADEPT, prepared=True), *lands(1)]
        self.assertNotIn(CAST_PREPARED + "Quick Study", game.legal_actions(a))
        a.battlefield = [Permanent(ADEPT), *lands(2)]
        self.assertNotIn(CAST_PREPARED + "Quick Study", game.legal_actions(a))

    def test_a_sorcery_spell_waits_for_sorcery_timing(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(RALLIER, prepared=True), *lands(3)]
        self.assertIn(CAST_PREPARED + "Rite of Mending", game.legal_actions(a))
        game.step = "combat"
        self.assertNotIn(CAST_PREPARED + "Rite of Mending", game.legal_actions(a))

    def test_becomes_prepared_from_a_trigger(self):
        game, _ = table3()
        a = game.seats[0]
        rallier = Permanent(RALLIER)
        a.battlefield = [rallier]
        game.trigger("attack_with_two", rallier, a)
        run_stack(game)
        self.assertTrue(rallier.prepared)

    def test_only_creatures_with_a_prepare_spell_can_become_prepared(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game.prepare(bear)
        self.assertFalse(bear.prepared)


if __name__ == "__main__":
    unittest.main()
