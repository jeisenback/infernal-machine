"""Bargain: "You may sacrifice an artifact, enchantment, or token as you cast this spell." An optional additional cost, so a bargained spell is a
kicked one: "if this spell was bargained" and "if it was bargained" read as the kicker conditions (CR 702.166). Candy Grapple, Kellan's
Lightblades, Archon's Glory, High Fae Negotiator, Tenacious Tomeseeker, Troublemaker Ouphe, Realm-Scorcher Hellkite, Agatha's Champion."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import KICKER_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.combat import Attack
from tests.helpers import BEAR, Table, creature, lands, real, run_stack

BARGAIN = "Bargain (You may sacrifice an artifact, enchantment, or token as you cast this spell.)\n"
GRAPPLE = real("Candy Grapple", "{1}{B}", "Instant", BARGAIN + "Target creature gets -3/-3 until end of turn. If this spell was bargained, that "
               "creature gets -5/-5 until end of turn instead.", colors=("B",))
LIGHTBLADES = real("Kellan's Lightblades", "{W}", "Instant", BARGAIN + "Kellan's Lightblades deals 3 damage to target attacking or blocking "
                   "creature. If this spell was bargained, destroy that creature instead.", colors=("W",))
GLORY = real("Archon's Glory", "{1}{W}", "Instant", BARGAIN + "Target creature gets +2/+2 until end of turn. If this spell was bargained, that "
             "creature also gains flying and lifelink until end of turn.", colors=("W",))
NEGOTIATOR = real("High Fae Negotiator", "{2}{U}{B}", "Creature — Faerie Warlock", BARGAIN + "Flying\nWhen this creature enters, if it was "
                  "bargained, each opponent loses 3 life and you gain 3 life.", "3", "3", colors=("U", "B"))
HELLKITE = real("Realm-Scorcher Hellkite", "{2}{R}{R}", "Creature — Dragon", BARGAIN + "Flying, haste\nWhen this creature enters, if it was "
                "bargained, add four mana in any combination of colors.\n{1}{R}: This creature deals 1 damage to any target.", "4", "4",
                colors=("R",))
CHAMPION = real("Agatha's Champion", "{2}{G}", "Creature — Human Knight", BARGAIN + "Trample\nWhen this creature enters, if it was bargained, it "
                "fights up to one target creature you don't control. (Each deals damage equal to its power to the other.)", "3", "3", colors=("G",))
OUPHE = real("Troublemaker Ouphe", "{1}{G}", "Creature \u2014 Ouphe", BARGAIN + "When this creature enters, if it was bargained, exile target "
             "artifact or enchantment an opponent controls.", "3", "2", colors=("G",))
MURASA = real("Might of Murasa", "{1}{G}", "Instant", "Kicker {2}{G} (You may pay an additional {2}{G} as you cast this spell.)\nTarget creature gets "
              "+3/+3 until end of turn. If this spell was kicked, that creature gets +5/+5 until end of turn instead.", colors=("G",))
MAMMOTH = real("Thorn Mammoth", "{5}{G}{G}", "Creature \u2014 Elephant", "Trample\nWhenever this creature or another creature you control enters, this "
               "creature fights up to one target creature you don't control.", "6", "6", colors=("G",))
TROPHY = real("Trophy", "{2}", "Artifact", "")
SHRINE = real("Shrine", "{2}", "Enchantment", "")
GIANT = creature("Giant", 5, 5)
RABBIT = Card(name="Rabbit", type_line="Token Creature — Rabbit", power="1", toughness="1")


def bargain(yes, give="Trophy", target="Giant"):
    """Policy: answer the bargain question, sacrifice `give`, aim at `target`, pass otherwise."""
    def policy(prompt, options):
        if KICKER_PROMPT.matches(prompt):
            return 0 if yes else 1
        wanted = give if "sacrifice" in prompt else target
        for i, option in enumerate(options):
            if option.startswith(wanted):
                return i
        return options.index("Pass") if "Pass" in options else 0
    return policy


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name != "City of Brass")


class BargainTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GRAPPLE, LIGHTBLADES, GLORY, NEGOTIATOR, HELLKITE, CHAMPION):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_without_the_sacrifice_the_plain_effect(self):
        t = Table(GRAPPLE, policy=bargain(False), n=4, mine=[Permanent(TROPHY)], theirs=[Permanent(GIANT)]).cast()
        self.assertEqual(t.game.power(t.b.battlefield[0]), 2)  # 5/5 gets -3/-3
        self.assertIn("Trophy", names(t.a))

    def test_the_sacrifice_makes_it_stronger(self):
        t = Table(GRAPPLE, policy=bargain(True), n=4, mine=[Permanent(TROPHY)], theirs=[Permanent(GIANT)]).cast()
        self.assertEqual(names(t.b), [])  # the Giant dies to -5/-5
        self.assertNotIn("Trophy", names(t.a))

    def test_an_enchantment_or_a_token_can_be_sacrificed_too(self):
        for give, part in (("Shrine", SHRINE), ("Rabbit", RABBIT)):
            t = Table(GRAPPLE, policy=bargain(True, give=give), n=4, mine=[Permanent(part)], theirs=[Permanent(GIANT)]).cast()
            self.assertNotIn(give, names(t.a), give)

    def test_a_creature_is_not_a_bargain(self):
        t = Table(GRAPPLE, policy=bargain(True, give="Bear"), n=4, mine=[Permanent(BEAR)], theirs=[Permanent(GIANT)])
        t.cast()
        asked = [prompt for prompt, _ in t.a.player.prompts if KICKER_PROMPT.matches(prompt)]
        self.assertEqual(asked, [])  # nothing to sacrifice: it is not even offered
        self.assertIn("Bear", names(t.a))

    def test_destroy_instead_of_damage(self):
        for yes, left in ((True, []), (False, ["Giant"])):
            attacker = Permanent(GIANT)
            t = Table(LIGHTBLADES, policy=bargain(yes), n=4, mine=[Permanent(TROPHY)], theirs=[attacker])
            t.game.combat.attacks.append(Attack(attacker, t.b, t.a))
            t.cast()
            self.assertEqual(names(t.b), left, yes)  # destroyed, or only dealt 3 damage

    def test_the_trigger_asks_whether_it_was_bargained(self):
        for yes, loss in ((True, 3), (False, 0)):
            t = Table(NEGOTIATOR, policy=bargain(yes), n=6, mine=[Permanent(TROPHY)]).cast()
            self.assertEqual(40 - t.b.life, loss, yes)
            self.assertEqual(t.a.life - 40, loss, yes)

    def test_four_mana_of_any_colors(self):
        t = Table(HELLKITE, policy=bargain(True), n=4, mine=[Permanent(TROPHY)]).cast()
        self.assertEqual(len(t.a.mana_pool), 4)
        t = Table(HELLKITE, policy=bargain(False), n=4, mine=[Permanent(TROPHY)]).cast()
        self.assertEqual(len(t.a.mana_pool), 0)

    def test_it_fights_when_bargained(self):
        t = Table(CHAMPION, policy=bargain(True), n=3, mine=[Permanent(TROPHY)], theirs=[Permanent(GIANT)]).cast()
        self.assertEqual(t.b.battlefield[0].damage, 3)  # the 3/3 fought the Giant
        t = Table(CHAMPION, policy=bargain(False), n=3, mine=[Permanent(TROPHY)], theirs=[Permanent(GIANT)]).cast()
        self.assertEqual(t.b.battlefield[0].damage, 0)

    def test_exile_an_artifact_or_enchantment_when_bargained(self):
        t = Table(OUPHE, policy=bargain(True, target="Shrine"), n=4, mine=[Permanent(TROPHY)], theirs=[Permanent(SHRINE), Permanent(GIANT)]).cast()
        self.assertEqual(names(t.b), ["Giant"])
        t = Table(OUPHE, policy=bargain(False, target="Shrine"), n=4, mine=[Permanent(TROPHY)], theirs=[Permanent(SHRINE), Permanent(GIANT)]).cast()
        self.assertEqual(names(t.b), ["Giant", "Shrine"])

    def test_a_mana_kicker_replaces_the_effect_the_same_way(self):
        for yes, power in ((True, 7), (False, 5)):
            t = Table(MURASA, policy=bargain(yes, target="Bear"), n=6, mine=[Permanent(BEAR)]).cast()
            self.assertEqual(t.game.power(t.a.battlefield[0]), power, yes)  # 2/2 plus +5/+5 or +3/+3

    def test_a_creature_that_fights_when_another_enters(self):
        mammoth = Permanent(MAMMOTH, sick=False)
        t = Table(BEAR, policy=bargain(False, target="Giant"), n=6, mine=[mammoth], theirs=[Permanent(GIANT)]).cast()
        self.assertEqual(names(t.b), [])  # the Mammoth (6/6) fought the Giant (5/5) and killed it
        self.assertEqual(mammoth.damage, 5)

    def test_archon_glory_grants_flying_and_lifelink(self):
        t = Table(GLORY, policy=bargain(True), n=4, mine=[Permanent(TROPHY), Permanent(BEAR)]).cast()
        bear = next(p for p in t.a.battlefield if p.card.name == "Bear")
        self.assertTrue(t.game.has_keyword(bear, "flying") and t.game.has_keyword(bear, "lifelink"))


if __name__ == "__main__":
    unittest.main()
