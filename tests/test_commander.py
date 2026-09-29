import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.commander import copy_limit, deck_problems, valid_pair


def legend(name, identity=(), text="", type_line="Legendary Creature — Human"):
    return Card(name=name, type_line=type_line, oracle_text=text, color_identity=tuple(identity))


FOREST = Card(name="Forest", type_line="Basic Land — Forest", color_identity=("G",))
WASTES = Card(name="Wastes", type_line="Basic Land")
SOL_RING = Card(name="Sol Ring", type_line="Artifact")


def deck(commanders, *others):
    main = list(others)
    main += [WASTES] * (100 - len(commanders) - len(main))
    return Deck(commanders=list(commanders), main=main, sideboard=[])


class DeckProblemsTests(unittest.TestCase):
    def test_legal_deck(self):
        self.assertEqual(deck_problems(deck([legend("Omnath", "G")], SOL_RING, FOREST, FOREST)), [])

    def test_wrong_size(self):
        d = deck([legend("Omnath", "G")])
        d.main.pop()
        self.assertIn("99 cards", deck_problems(d)[0])

    def test_commander_must_be_legendary_creature(self):
        bear = Card(name="Grizzly Bears", type_line="Creature — Bear", color_identity=("G",))
        self.assertEqual(deck_problems(deck([bear])), ["Grizzly Bears can't be your commander"])

    def test_can_be_your_commander_text(self):
        teferi = legend("Teferi", "U", "Teferi can be your commander.", "Legendary Planeswalker — Teferi")
        island = Card(name="Island", type_line="Basic Land — Island", color_identity=("U",))
        self.assertEqual(deck_problems(Deck([teferi], [island] * 99, [])), [])

    def test_singleton(self):
        problems = deck_problems(deck([legend("Omnath", "G")], SOL_RING, SOL_RING))
        self.assertEqual(problems, ["Sol Ring: 2 copies, limit is 1"])

    def test_color_identity(self):
        bolt = Card(name="Lightning Bolt", type_line="Instant", color_identity=("R",))
        problems = deck_problems(deck([legend("Omnath", "G")], bolt))
        self.assertEqual(problems, ["Lightning Bolt is outside the commander's color identity (R)"])

    def test_banned_card(self):
        banned = Card(name="Mana Crypt", type_line="Artifact", commander_legal=False)
        self.assertEqual(deck_problems(deck([legend("Omnath", "G")], banned)), ["Mana Crypt is not legal in Commander"])

    def test_partners_combine_identity(self):
        partner = "Partner (You can have two commanders if both have partner.)"
        a, b = legend("Thrasios", "GU", partner), legend("Tymna", "WB", partner)
        island = Card(name="Island", type_line="Basic Land — Island", color_identity=("U",))
        self.assertEqual(deck_problems(deck([a, b], island)), [])

    def test_two_commanders_need_to_pair(self):
        problems = deck_problems(deck([legend("Omnath", "G"), legend("Titania", "G")]))
        self.assertEqual(problems, ["Omnath and Titania can't be commanders together"])


class PairingTests(unittest.TestCase):
    def test_partner_with_must_name_each_other(self):
        pir = legend("Pir, Imaginative Rascal", text="Partner with Toothy, Imaginary Friend (When this...)")
        toothy = legend("Toothy, Imaginary Friend", text="Partner with Pir, Imaginative Rascal")
        other = legend("Someone Else", text="Partner")
        self.assertTrue(valid_pair(pir, toothy))
        self.assertFalse(valid_pair(pir, other))

    def test_partner_variants_must_match(self):
        a = legend("A", text="Partner—Survivors")
        self.assertTrue(valid_pair(a, legend("B", text="Partner—Survivors")))
        self.assertFalse(valid_pair(a, legend("C", text="Partner")))

    def test_background(self):
        creature = legend("Wilson", text="Choose a Background (You can have a Background as a second commander.)")
        background = Card(name="Raised by Giants", type_line="Legendary Enchantment — Background")
        self.assertTrue(valid_pair(background, creature))
        self.assertEqual(deck_problems(deck([creature, background])), [])

    def test_doctors_companion(self):
        companion = legend("Rose Tyler", text="Doctor's companion")
        doctor = legend("The Tenth Doctor", type_line="Legendary Creature — Time Lord Doctor")
        self.assertTrue(valid_pair(companion, doctor))


class CopyLimitTests(unittest.TestCase):
    def test_limits(self):
        self.assertIsNone(copy_limit(FOREST))
        self.assertEqual(copy_limit(SOL_RING), 1)
        rats = Card(name="Relentless Rats", oracle_text="A deck can have any number of cards named Relentless Rats.")
        self.assertIsNone(copy_limit(rats))
        dwarves = Card(name="Seven Dwarves", oracle_text="A deck can have up to seven cards named Seven Dwarves.")
        self.assertEqual(copy_limit(dwarves), 7)


if __name__ == "__main__":
    unittest.main()
