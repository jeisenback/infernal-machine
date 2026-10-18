import unittest

from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table

REVERSAL = real("Narset's Reversal", "{U}{U}", "Instant",
                "Copy target instant or sorcery spell, then return it to its owner's hand. You may choose new targets for the copy.")
ARCHMAGE = real("Archmage of Echoes", "{4}{U}", "Creature — Faerie Wizard",
                "Flying, ward {2}\nWhenever you cast a Faerie or Wizard permanent spell, copy it. (The copy becomes a token.)", "4", "4")
DIVINATION = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")
FAERIE = real("Test Faerie", "{1}{U}", "Creature — Faerie", "Flying", "1", "1")
WIZARD_SPELL = real("Test Wizard", "{1}{U}", "Creature — Human Wizard", "", "1", "1")
FAERIE_INSTANT = real("Faerie Trick", "{U}", "Instant — Faerie", "You gain 1 life.")


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (REVERSAL, ARCHMAGE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class NarsetsReversalTests(unittest.TestCase):
    def play(self, spell_name):
        game, _, _ = table(pick(CAST + "Divination", CAST + "Narset's Reversal"))
        a = game.seats[0]
        a.hand = [DIVINATION, REVERSAL]
        a.battlefield = lands(6)
        game._priority_round(a)
        return game, a

    def test_the_copy_resolves_and_the_spell_returns_to_hand_unresolved(self):
        game, a = self.play("Divination")
        self.assertEqual(len(a.hand), 3, "Divination is back in hand; the copy drew two cards")
        self.assertIn("Divination", [c.name for c in a.hand])
        self.assertEqual([c.name for c in a.graveyard], ["Narset's Reversal"], "the original never resolved, so it is not in the graveyard")

    def test_a_spell_that_has_already_left_the_stack_is_not_returned_again(self):
        game, _, _ = table(pick(CAST + "Divination"))
        a = game.seats[0]
        a.hand = [DIVINATION]
        a.battlefield = lands(6)
        game._priority_round(a)  # resolved: it is in the graveyard
        spell = StackItem(DIVINATION, a, [], [])
        game.return_spell_to_hand(spell)  # not on the stack: nothing happens, and nothing raises
        self.assertEqual([c.name for c in a.graveyard], ["Divination"])

    def test_it_needs_an_instant_or_sorcery_to_target(self):
        game, _, _ = table(pick(CAST + "Narset's Reversal"))
        a = game.seats[0]
        a.hand = [REVERSAL]
        a.battlefield = lands(6)
        game._priority_round(a)
        self.assertEqual(len(a.hand), 1, "nothing on the stack to copy: it can't be cast")


class WatchedPermanentCopyTests(unittest.TestCase):
    def cast(self, card):
        game, _, _ = table(pick(CAST + card.name))
        a = game.seats[0]
        a.hand = [card]
        a.battlefield = lands(4) + [Permanent(ARCHMAGE)]
        game._priority_round(a)
        run_stack(game)
        return a

    def test_a_faerie_permanent_spell_is_copied_as_a_token(self):
        a = self.cast(FAERIE)
        made = [p for p in a.battlefield if p.card.name == "Test Faerie"]
        self.assertEqual(sorted(p.card.type_line.startswith("Token") for p in made), [False, True])

    def test_a_wizard_permanent_spell_is_copied(self):
        a = self.cast(WIZARD_SPELL)
        self.assertEqual(sum(p.card.name == "Test Wizard" for p in a.battlefield), 2)

    def test_another_creature_is_not_copied(self):
        a = self.cast(BEAR)
        self.assertEqual(sum(p.card.name == "Bear" for p in a.battlefield), 1)

    def test_an_instant_of_that_type_is_not_a_permanent_spell(self):
        a = self.cast(FAERIE_INSTANT)
        self.assertEqual(a.life, 41, "gained life once: no copy of a spell that isn't a permanent spell")


if __name__ == "__main__":
    unittest.main()
