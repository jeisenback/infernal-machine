"""The audit must not call a card playable when part of it is not: a line that is several triggers needs every one of them
understood, and a card with a second face or half the engine can't play is not fully playable."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.report import SECOND_FACE, unsupported_lines
from tests.test_rules_text_81 import real

ENTERS_AND_DRAWS = ("When this creature enters and whenever an opponent draws a card except the first one they draw in each of their draw steps, "
                    "this creature deals 1 damage to any target.")
ENTERS_AND_WEIRD = "When this creature enters and whenever the moon turns purple, this creature deals 1 damage to any target."


def creature(text):
    return real("Test", "{1}", "Creature — Test", text, "1", "1")


class CompoundTriggerTests(unittest.TestCase):
    def test_both_halves_understood_means_both_triggers(self):
        card = creature(ENTERS_AND_DRAWS)
        self.assertEqual(sorted(a.event for a in triggered_abilities(card)), ["enters", "opponent_extra_draw"])
        self.assertEqual(unsupported_lines(card), [])

    def test_one_half_not_understood_is_not_half_a_card(self):
        card = creature(ENTERS_AND_WEIRD)
        self.assertEqual(triggered_abilities(card), ())
        self.assertEqual(unsupported_lines(card), [ENTERS_AND_WEIRD])

    def test_a_single_trigger_is_unchanged(self):
        self.assertEqual(unsupported_lines(creature("When this creature enters, whenever the moon turns purple.")), [
            "When this creature enters, whenever the moon turns purple."])

    def test_several_events_of_the_card_itself_all_have_to_be_known(self):
        known = creature("When this creature enters or dies, you gain 1 life.")
        unknown = creature("When this creature enters or levitates, you gain 1 life.")
        self.assertEqual(sorted(a.event for a in triggered_abilities(known)), ["dies", "enters"])
        self.assertEqual(triggered_abilities(unknown), ())


def scryfall(layout, *faces):
    return {"name": " // ".join(f["name"] for f in faces), "layout": layout, "cmc": 2.0, "id": "x", "color_identity": [],
            "legalities": {"commander": "legal"}, "card_faces": list(faces)}


FRONT = {"name": "Front", "type_line": "Creature — Giant", "mana_cost": "{2}{R}", "oracle_text": "Haste", "power": "3", "toughness": "3"}
SPELL = {"name": "Back Spell", "type_line": "Sorcery — Adventure", "mana_cost": "{1}{R}", "oracle_text": "Draw a card."}
LAND = {"name": "Back Land", "type_line": "Land", "oracle_text": "{T}: Add {R}."}


class SecondFaceTests(unittest.TestCase):
    def test_an_aftermath_half_is_not_played(self):
        card = Card.from_scryfall(scryfall("split", {**FRONT, "type_line": "Sorcery"},
                                           {**SPELL, "type_line": "Sorcery", "oracle_text": "Aftermath (Cast this spell only from your graveyard.)\nDraw a card."}))
        self.assertEqual((card.other_face, card.alternate, unsupported_lines(card)), ("Back Spell", None, [SECOND_FACE]))

    def test_a_modal_card_whose_back_is_a_permanent_is_not_played_as_it(self):
        card = Card.from_scryfall(scryfall("modal_dfc", FRONT, {**FRONT, "name": "Back Giant"}))
        self.assertEqual((card.other_face, unsupported_lines(card)), ("Back Giant", [SECOND_FACE]))

    def test_a_modal_card_whose_back_is_a_land_is_played_as_that_land(self):
        card = Card.from_scryfall(scryfall("modal_dfc", FRONT, LAND))
        self.assertEqual((card.other_face, unsupported_lines(card)), ("", []))

    def test_a_card_with_one_face_has_no_other(self):
        card = Card.from_scryfall({"name": "Front", "layout": "normal", "cmc": 3.0, "type_line": "Creature — Giant", "oracle_text": "Haste",
                                   "legalities": {"commander": "legal"}, "id": "y", "color_identity": []})
        self.assertEqual((card.other_face, unsupported_lines(card)), ("", []))

    def test_the_second_face_is_listed_with_the_card_problems_it_already_has(self):
        card = Card.from_scryfall(scryfall("modal_dfc", {**FRONT, "oracle_text": "Frobnicate the widgets."}, {**FRONT, "name": "Back Giant"}))
        self.assertEqual(unsupported_lines(card), ["Frobnicate the widgets.", SECOND_FACE])

    def test_the_cache_round_trip_keeps_it(self):
        card = Card.from_scryfall(scryfall("modal_dfc", FRONT, {**FRONT, "name": "Back Giant"}))
        self.assertEqual(Card.from_dict(card.to_dict()).other_face, "Back Giant")


class CastTriggerTargetTests(unittest.TestCase):
    """"When you cast this spell, ... target ..." (Artisan of Kozilek) crashed: the trigger went on the stack with no target chosen."""

    def cast(self, graveyard):
        from infernal_machine.game import CAST, Permanent
        from tests.test_effects import lands
        from tests.test_mass_effects import table3
        from tests.test_more_triggers import run_stack
        from tests.test_x_targets import script
        game, _ = table3(script("Bear"))
        a = game.seats[0]
        artisan = real("Artisan", "{1}", "Creature \u2014 Eldrazi",
                       "When you cast this spell, you may return target creature card from your graveyard to the battlefield.", "1", "1")
        a.battlefield, a.hand, a.graveyard = lands(2), [artisan], list(graveyard)
        game._perform(a, CAST + "Artisan")
        run_stack(game)
        return a

    def test_the_target_is_chosen_and_returned(self):
        bear = real("Bear", "{1}", "Creature \u2014 Bear", "", "2", "2")
        a = self.cast([bear])
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Artisan", "Bear"])

    def test_without_a_target_the_spell_is_still_cast(self):
        a = self.cast([])
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], ["Artisan"])


class ManaPaymentSpeedTests(unittest.TestCase):
    """Paying for something that can't be paid for must say so at once (Replicate asks for one more payment than there is mana)."""

    def test_more_mana_than_sources_is_refused_at_once(self):
        import time
        from infernal_machine.mana import Cost, pay
        started = time.time()
        found = pay(Cost(0, tuple(frozenset("UR") for _ in range(14))), [frozenset("WUBRG")] * 12)
        self.assertEqual((found, time.time() - started < 1), (None, True))

    def test_more_symbols_than_sources_is_refused_at_once_even_with_many_sources(self):
        import time
        from infernal_machine.mana import Cost, pay
        started = time.time()
        found = pay(Cost(0, tuple(frozenset("RG") for _ in range(24))), [frozenset("RG")] * 20)
        self.assertEqual((found, time.time() - started < 1), (None, True))

    def test_symbols_that_only_some_sources_can_pay_are_refused_at_once(self):
        import time
        from infernal_machine.mana import Cost, pay
        started = time.time()
        sources = [frozenset("RG")] * 12 + [frozenset("B")] * 8  # thirteen red-or-green symbols, twelve sources that can pay them
        found = pay(Cost(0, tuple(frozenset("RG") for _ in range(13))), sources)
        self.assertEqual((found, time.time() - started < 2), (None, True))

    def test_a_payment_that_works_still_does(self):
        from infernal_machine.mana import Cost, pay
        found = pay(Cost(1, (frozenset("R"), frozenset("G"))), [frozenset("R"), frozenset("G"), frozenset("C")])
        self.assertEqual(sorted(found), [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
