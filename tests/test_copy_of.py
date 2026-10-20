"""Every copy is made by `copy_of` (issue #438): what a copy is, and the places that make one (tokens, clones, a creature that becomes a
copy) now agree about it."""

import dataclasses
import unittest

from infernal_machine.effects import CopyChanges, copy_of
from infernal_machine.game import PASS, Permanent
from tests.helpers import BEAR, lands, real, run_stack, table

HERO = real("Test Hero", "{1}{W}", "Legendary Creature — Human Knight", "Vigilance", "2", "2")
PLAIN = dataclasses.replace(BEAR, type_line="Creature")  # a creature with no subtypes


class CopyOfTests(unittest.TestCase):
    def test_a_token_copy_is_a_token_and_the_original_is_not_changed(self):
        copy = copy_of(HERO, as_token=True)
        self.assertEqual(copy.type_line, "Token Legendary Creature — Human Knight")
        self.assertEqual(HERO.type_line, "Legendary Creature — Human Knight")

    def test_a_token_is_not_given_the_prefix_twice(self):
        once = copy_of(HERO, as_token=True)
        self.assertEqual(copy_of(once, as_token=True).type_line, once.type_line)

    def test_a_copy_that_is_not_a_token_is_not_one_even_when_it_copies_a_token(self):
        token = copy_of(HERO, as_token=True)
        self.assertEqual(copy_of(token).type_line, "Legendary Creature — Human Knight")
        self.assertEqual(copy_of(HERO).type_line, HERO.type_line)

    def test_the_except_clause_applies_either_way(self):
        changes = CopyChanges(not_legendary=True, power_toughness=("1", "1"), keywords=("haste",), abilities=("Whenever this attacks, scry 1.",))
        for as_token in (True, False):
            copy = copy_of(HERO, changes, as_token=as_token)
            self.assertEqual((copy.power, copy.toughness), ("1", "1"))
            self.assertEqual(copy.oracle_text, "Vigilance\nHaste\nWhenever this attacks, scry 1.")
            self.assertNotIn("Legendary", copy.type_line)

    def test_a_type_added_to_a_creature_with_no_subtypes_makes_a_subtype_line(self):
        self.assertEqual(copy_of(PLAIN, CopyChanges(add_types=("Spirit",)), as_token=True).type_line, "Token Creature — Spirit")


class NothingMakesACopyByHandTests(unittest.TestCase):
    def test_no_code_outside_copy_of_builds_a_token_copy_or_strips_the_token_word(self):
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent / "infernal_machine"
        pattern = re.compile(r'"Token " \+|removeprefix\("Token')
        for path in root.rglob("*.py"):
            if path.name == "copying.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(pattern.search(line), f"{path.name}:{number}: {line.strip()} (use copy_of)")


# --- the places that make copies, on real cards ---
TWINFLAME = real("Twinflame", "{1}{R}", "Sorcery",
                 "Strive — This spell costs {2}{R} more to cast for each target beyond the first.\nChoose any number of target creatures you control. "
                 "For each of them, create a token that's a copy of that creature, except it has haste. Exile those tokens at the beginning of the next end step.")
LIFE_OF_THE_PARTY = real("Life of the Party", "{3}{R}{R}", "Creature — Elemental",
                         "First strike, trample, haste\nWhenever Life of the Party attacks, it gets +X/+0 until end of turn, where X is the number of creatures you control.\n"
                         "When Life of the Party enters, if it's not a token, each opponent creates a token that's a copy of it. The tokens are goaded for the rest of the game.",
                         "3", "3")


class SiteTests(unittest.TestCase):
    def test_twinflame_makes_token_copies_with_haste(self):
        game, _, _ = table(None)
        a = game.seats[0]
        hero = Permanent(HERO)
        a.battlefield = [hero]
        game.copy_tokens(a, [hero], True, False)
        [made] = [p for p in a.battlefield if p is not hero]
        self.assertEqual((made.card.type_line, made.card.oracle_text), ("Token Legendary Creature — Human Knight", "Vigilance\nHaste"))

    def test_a_copy_of_a_token_copied_by_twinflame_is_still_one_token_prefix(self):
        game, _, _ = table(None)
        a = game.seats[0]
        token = Permanent(copy_of(HERO, as_token=True))
        a.battlefield = [token]
        game.copy_tokens(a, [token], False, False)
        made = [p for p in a.battlefield if p is not token][0]
        self.assertEqual(made.card.type_line, "Token Legendary Creature — Human Knight")

    def test_a_creature_that_becomes_a_copy_until_end_of_turn_is_not_a_token_and_has_the_keyword_line_as_given(self):
        game, _, _ = table(None)
        a, b = game.seats
        me, token = Permanent(BEAR), Permanent(copy_of(HERO, as_token=True))
        a.battlefield, b.battlefield = [me], [token]
        game.become_copy_until_end_of_turn(me, token, "Myriad", a)
        self.assertEqual((me.card.type_line, me.card.oracle_text), ("Legendary Creature — Human Knight", "Vigilance\nMyriad"))
        self.assertEqual(me.original.name, "Bear")

    def test_hofris_spirit_copy_is_a_spirit_with_the_graveyard_return_ability(self):
        game, _, _ = table(None)
        a = game.seats[0]
        dead = Permanent(HERO, owner=a)
        a.graveyard = [HERO]
        game.exile_dead_copy(a, dead, CopyChanges(add_types=("Spirit",), abilities=(
            "When this token leaves the battlefield, return the exiled card to its owner's graveyard.",)))
        [made] = a.battlefield
        self.assertEqual(made.card.type_line, "Token Legendary Creature — Human Knight Spirit")
        self.assertTrue(made.card.oracle_text.endswith("When this token leaves the battlefield, return the exiled card to its owner's graveyard."))

    def test_rionya_style_copies_have_haste_and_lose_legendary_when_asked(self):
        game, _, _ = table(None)
        a = game.seats[0]
        hero = Permanent(HERO)
        a.battlefield = [hero]
        game.copies_of_creature(a, hero, 2, not_legendary=True)
        copies = [p for p in a.battlefield if p is not hero]
        self.assertEqual([(p.card.type_line, p.card.oracle_text) for p in copies], [("Token Creature — Human Knight", "Vigilance\nHaste")] * 2)
        game.copies_of_creature(a, hero, 1, not_legendary=False)
        self.assertEqual([p.card.type_line for p in a.battlefield if p is not hero][-1], "Token Legendary Creature — Human Knight")


if __name__ == "__main__":
    unittest.main()
