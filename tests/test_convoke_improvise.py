"""Convoke and Improvise (#198, #205 of the audit): creatures (artifacts) tapped to help pay for the spell."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.mana import parse_cost
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, PLAINS, real, Table

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


def spell(cost, text, name="Spell"):
    return real(name, cost, "Sorcery", text + "\nDraw a card.")


def creature(name, colors=(), sick=False, text=""):
    card = Card(name=name, mana_cost="{1}", type_line="Creature — Bear", oracle_text=text, power="2", toughness="2", colors=colors)
    return Permanent(card, sick=sick)


def artifact(name, creature_too=False):
    kind = "Artifact Creature — Golem" if creature_too else "Artifact"
    return Permanent(Card(name=name, mana_cost="{1}", type_line=kind, power="1" if creature_too else None,
                          toughness="1" if creature_too else None))


class Cast:
    """Seat 0 with `battlefield` (and `n` Forests unless `mine` lands are given) and `card` in hand."""

    def __init__(self, card, battlefield=(), lands_=()):
        self.t = Table(card, n=0, mine=list(battlefield))
        self.t.a.battlefield += [Permanent(land) for land in lands_]
        self.game, self.seat, self.card = self.t.game, self.t.a, card

    def castable(self):
        return CAST + self.card.name in self.game.legal_actions(self.seat)

    def tapped(self):
        return sorted(p.card.name for p in self.seat.battlefield if p.tapped)

    def cast(self):
        self.t.cast()
        return self


CONVOKE = spell("{2}{G}", "Convoke")


class ConvokeTests(unittest.TestCase):
    def test_creatures_alone_can_pay_if_one_of_them_is_green(self):
        c = Cast(CONVOKE, [creature("Elf", "G"), creature("Bear"), creature("Cat", "W")])
        self.assertTrue(c.castable())
        c.cast()
        self.assertEqual(c.tapped(), ["Bear", "Cat", "Elf"])
        self.assertEqual(len(c.seat.hand), 1)  # the Draw a card resolved (the spell itself is gone)

    def test_a_colored_requirement_needs_a_creature_of_that_color(self):
        c = Cast(CONVOKE, [creature("Elf", "W"), creature("Bear"), creature("Cat", "U")])
        self.assertFalse(c.castable())  # three creatures, but none can pay for {G}

    def test_a_multicolored_creature_pays_for_either_color(self):
        c = Cast(spell("{1}{W}", "Convoke"), [creature("Knight", "GW"), creature("Bear")])
        self.assertTrue(c.castable())
        c = Cast(spell("{1}{G}", "Convoke"), [creature("Knight", "GW"), creature("Bear")])
        self.assertTrue(c.castable())
        c = Cast(spell("{1}{U}", "Convoke"), [creature("Knight", "GW"), creature("Bear")])
        self.assertFalse(c.castable())

    def test_a_summoning_sick_creature_can_convoke(self):
        c = Cast(spell("{G}", "Convoke"), [creature("Elf", "G", sick=True)])
        self.assertTrue(c.castable())
        self.assertEqual(c.cast().tapped(), ["Elf"])

    def test_a_tapped_creature_cannot(self):
        elf = creature("Elf", "G")
        elf.tapped = True
        self.assertFalse(Cast(spell("{G}", "Convoke"), [elf]).castable())

    def test_creatures_and_lands_together_cover_the_cost(self):
        c = Cast(spell("{3}{G}", "Convoke"), [creature("Elf", "G"), creature("Bear")], [FOREST, FOREST])
        self.assertTrue(c.castable())
        c.cast()
        self.assertEqual(c.tapped(), ["Bear", "Elf", "Forest", "Forest"])

    def test_only_as_many_are_tapped_as_the_cost_needs(self):
        c = Cast(spell("{1}{G}", "Convoke"), [creature("A", "G"), creature("B", "G"), creature("C", "G")])
        c.cast()
        self.assertEqual(len(c.tapped()), 2)

    def test_without_convoke_creatures_do_not_help(self):
        c = Cast(spell("{G}", ""), [creature("Elf", "G")])
        self.assertFalse(c.castable())

    def test_a_creature_that_makes_mana_is_tapped_once(self):
        dork = creature("Llanowar Elves", "G", text="{T}: Add {G}.")
        self.assertFalse(Cast(spell("{G}{G}", "Convoke"), [dork]).castable())  # one permanent, one payment
        c = Cast(spell("{G}{G}", "Convoke"), [dork, creature("Elf", "G")])
        self.assertTrue(c.castable())
        self.assertEqual(c.cast().tapped(), ["Elf", "Llanowar Elves"])

    def test_a_colorless_creature_cannot_pay_for_a_colorless_symbol(self):
        c = Cast(spell("{C}", "Convoke"), [creature("Bear")])
        self.assertFalse(c.castable())  # it pays for generic mana only, not for {C}

    def test_creatures_do_not_help_pay_for_anything_but_the_spell(self):
        c = Cast(spell("{1}", "Convoke"), [creature("Bear")])
        self.assertIsNone(c.game._pay_cost(c.seat, parse_cost("{1}")))

    def test_a_noncreature_permanent_does_not_convoke(self):
        self.assertFalse(Cast(spell("{1}", "Convoke"), [artifact("Relic")]).castable())

    def test_the_x_in_the_cost_can_be_paid_by_creatures(self):
        card = spell("{X}{G}", "Convoke")
        c = Cast(card, [creature("A", "G"), creature("B"), creature("C")])
        game, seat = c.game, c.seat
        self.assertIsNotNone(game._payment(seat, card, x=2))
        self.assertIsNone(game._payment(seat, card, x=3))


class ImproviseTests(unittest.TestCase):
    def test_artifacts_pay_for_generic_mana(self):
        card = spell("{2}{U}", "Improvise")
        c = Cast(card, [artifact("Relic"), artifact("Idol")], [ISLAND])
        self.assertTrue(c.castable())
        self.assertEqual(c.cast().tapped(), ["Idol", "Island", "Relic"])

    def test_an_artifact_cannot_pay_for_a_colored_symbol(self):
        c = Cast(spell("{U}{U}", "Improvise"), [artifact("Relic")], [ISLAND])
        self.assertFalse(c.castable())

    def test_an_artifact_creature_improvises_but_a_plain_creature_does_not(self):
        c = Cast(spell("{1}", "Improvise"), [artifact("Golem", creature_too=True)])
        self.assertTrue(c.castable())
        self.assertFalse(Cast(spell("{1}", "Improvise"), [creature("Bear")]).castable())

    def test_improvise_does_not_let_creatures_help(self):
        c = Cast(spell("{1}", "Improvise"), [creature("Elf", "G")])
        self.assertFalse(c.castable())

    def test_convoke_does_not_let_artifacts_help(self):
        self.assertFalse(Cast(spell("{1}", "Convoke"), [artifact("Relic")]).castable())


class ReportTests(unittest.TestCase):
    def test_the_keywords_are_supported(self):
        for text in ("Convoke", "Improvise", "Flash, convoke", "Convoke (Your creatures can help cast this spell.)"):
            with self.subTest(text):
                self.assertEqual(unsupported_lines(real("Test", "{3}", "Sorcery", text + "\nDraw a card.")), [])


if __name__ == "__main__":
    unittest.main()
