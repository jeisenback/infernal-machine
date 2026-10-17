import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.outcomes import CopyChanges, copy_card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, PASS, lands, pick, real, run_stack, table


def attack_all(prompt, options):
    return 1 if prompt.startswith("Attack with") else (options.index(PASS) if PASS in options else 0)

MIIRYM = real("Miirym, Sentinel Wyrm", "{3}{G}{U}{R}", "Legendary Creature — Dragon Spirit",
              "Flying, ward {2}\nWhenever another nontoken Dragon you control enters, create a token that's a copy of it, except the token isn't legendary.",
              "6", "6")
SYNDROME = real("Impostor Syndrome", "{4}{U}{U}", "Enchantment",
                "Whenever a nontoken creature you control deals combat damage to a player, create a token that's a copy of it, except it isn't legendary.")
TYRANT = real("Vaultborn Tyrant", "{5}{G}{G}", "Creature — Dinosaur",
              "Trample\nWhenever this creature or another creature you control with power 4 or greater enters, you gain 3 life and draw a card.\n"
              "When this creature dies, if it's not a token, create a token that's a copy of it, except it's an artifact in addition to its other types.",
              "6", "6")
HELM = real("Helm of the Host", "{4}", "Legendary Artifact — Equipment",
            "At the beginning of combat on your turn, create a token that's a copy of equipped creature, except the token isn't legendary. "
            "That token gains haste.\nEquip {5}")
DUPLICATION = real("Irenicus's Vile Duplication", "{3}{U}", "Sorcery",
                   "Create a token that's a copy of target creature you control, except the token has flying and it isn't legendary.")
RATADRABIK = real("Ratadrabik of Urborg", "{2}{W}{B}", "Legendary Creature — Zombie Wizard",
                  "Vigilance, ward {2}\nOther Zombies you control have vigilance.\nWhenever another legendary creature you control dies, "
                  "create a token that's a copy of that creature, except it's not legendary and it's a 2/2 black Zombie in addition to its "
                  "other colors and types.", "3", "3", colors=("B", "W"))
WHELP = real("Whelp Dragon", "{1}{R}", "Creature — Dragon", "", "2", "2")
HERO = real("Test Hero", "{1}{W}", "Legendary Creature — Human Knight", "Vigilance", "2", "2")


def tokens(seat, name=None):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token") and (name is None or p.card.name == name)]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (MIIRYM, SYNDROME, TYRANT, HELM, DUPLICATION, RATADRABIK):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_except_clause_the_engine_does_not_apply_leaves_the_line_unsupported(self):
        odd = real("Odd Copier", "{2}", "Sorcery",
                   "Create a token that's a copy of target creature you control, except it's a 5/5 black Demon.")
        self.assertNotEqual(unsupported_lines(odd), [])


class CopyCardTests(unittest.TestCase):
    def test_changes_apply_to_a_copy_and_leave_the_rest(self):
        copy = copy_card(HERO, CopyChanges(not_legendary=True, add_types=("Spirit", "Artifact"), power_toughness=("1", "1"), keywords=("flying",)))
        self.assertEqual(copy.type_line, "Token Artifact Creature — Human Knight Spirit")
        self.assertEqual((copy.power, copy.toughness, copy.oracle_text), ("1", "1", "Vigilance\nFlying"))
        self.assertEqual(copy_card(HERO).type_line, "Token Legendary Creature — Human Knight")  # no except clause: all of it kept

    def test_a_type_the_original_already_has_is_not_added_twice(self):
        relic = dataclasses.replace(BEAR, type_line="Artifact Creature — Golem")
        self.assertEqual(copy_card(relic, CopyChanges(add_types=("Artifact", "Golem"))).type_line, "Token Artifact Creature — Golem")

    def test_colors_are_added_to_the_originals(self):
        copy = copy_card(HERO, CopyChanges(add_colors=("B",)))
        self.assertEqual(copy.colors, ("B",))
        self.assertEqual(copy_card(RATADRABIK, CopyChanges(add_colors=("B",))).colors, ("B", "W"))

    def test_the_original_is_not_touched(self):
        copy_card(HERO, CopyChanges(not_legendary=True))
        self.assertIn("Legendary", HERO.type_line)


class TriggeredCopyTests(unittest.TestCase):
    def cast(self, card, battlefield):
        game, _, _ = table(pick(CAST, card.name))
        seat = game.seats[0]
        seat.hand = [card]
        seat.battlefield = lands(4) + battlefield
        game._priority_round(seat)
        run_stack(game)
        return game, seat

    def test_a_dragon_entering_is_copied_without_being_legendary(self):
        legend = dataclasses.replace(WHELP, name="Old Wyrm", type_line="Legendary Creature — Dragon")
        game, seat = self.cast(legend, [Permanent(MIIRYM)])
        [token] = tokens(seat, "Old Wyrm")
        self.assertNotIn("Legendary", token.card.type_line)
        self.assertEqual(sum(p.card.name == "Old Wyrm" for p in seat.battlefield), 2)

    def test_something_that_is_not_a_dragon_is_not_copied(self):
        game, seat = self.cast(BEAR, [Permanent(MIIRYM)])
        self.assertEqual(tokens(seat), [])

    def test_a_token_dragon_is_not_copied(self):
        game, seat = self.cast(WHELP, [Permanent(MIIRYM)])
        self.assertEqual(len(tokens(seat, "Whelp Dragon")), 1)  # the cast one made one; its copy is a token and made no more

    def hit(self, attacker):
        game, _, _ = table(attack_all)
        seat = game.seats[0]
        seat.battlefield = [Permanent(SYNDROME), attacker]
        game.combat.declare_attackers(seat)
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        return seat

    def test_combat_damage_by_a_nontoken_creature_is_copied(self):
        seat = self.hit(Permanent(HERO))
        [token] = tokens(seat, "Test Hero")
        self.assertNotIn("Legendary", token.card.type_line)
        self.assertEqual(len(tokens(seat)), 1, "the copy is a token and was not itself a nontoken creature that dealt damage")

    def test_combat_damage_by_a_token_is_not_copied(self):
        seat = self.hit(Permanent(dataclasses.replace(HERO, type_line="Token Creature — Human Knight")))
        self.assertEqual(len(tokens(seat)), 1, "only the attacking token itself")

    def test_a_creature_that_died_is_copied_as_an_artifact(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        tyrant = Permanent(TYRANT)
        seat.battlefield = [tyrant]
        game.destroy(tyrant)
        run_stack(game)
        [token] = tokens(seat, "Vaultborn Tyrant")
        self.assertIn("Artifact", token.card.type_line)
        game.destroy(token)  # a token that dies does not copy itself again
        run_stack(game)
        self.assertEqual(tokens(seat), [])


    def test_another_legendary_creature_dying_is_copied_as_a_black_zombie(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        hero, plain = Permanent(HERO), Permanent(BEAR)
        seat.battlefield = [Permanent(RATADRABIK), hero, plain]
        game.destroy(plain)  # not legendary: no copy
        run_stack(game)
        self.assertEqual(tokens(seat), [])
        game.destroy(hero)
        run_stack(game)
        [token] = tokens(seat, "Test Hero")
        self.assertEqual((token.card.type_line, token.card.power, token.card.toughness), ("Token Creature — Human Knight Zombie", "2", "2"))
        self.assertEqual(token.card.colors, ("B",))

    def test_the_watcher_itself_dying_is_not_copied(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        ratadrabik = Permanent(RATADRABIK)
        seat.battlefield = [ratadrabik]
        game.destroy(ratadrabik)
        run_stack(game)
        self.assertEqual(tokens(seat), [])


class TargetedAndHostCopyTests(unittest.TestCase):
    def test_the_copy_has_flying_and_is_not_legendary(self):
        game, _, _ = table(pick(CAST, "Irenicus's Vile Duplication", "Test Hero"))
        seat = game.seats[0]
        seat.hand = [DUPLICATION]
        seat.battlefield = lands(4) + [Permanent(HERO)]
        game._priority_round(seat)
        [token] = tokens(seat, "Test Hero")
        self.assertNotIn("Legendary", token.card.type_line)
        self.assertIn("Flying", token.card.oracle_text)
        self.assertIn("Legendary", seat.battlefield[4].card.type_line, "the original stays legendary")

    def test_the_equipped_creature_is_copied_with_haste(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        hero = Permanent(HERO)
        helm = Permanent(HELM, attached_to=hero)
        seat.battlefield = [hero, helm]
        game.trigger("combat", helm, seat)
        run_stack(game)
        [token] = tokens(seat, "Test Hero")
        self.assertEqual(token.card.type_line, "Token Creature — Human Knight")
        self.assertEqual(token.card.oracle_text, "Vigilance\nHaste")

    def test_an_equipment_attached_to_nothing_copies_nothing(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        helm = Permanent(HELM)
        seat.battlefield = [Permanent(HERO), helm]
        game.trigger("combat", helm, seat)
        run_stack(game)
        self.assertEqual(tokens(seat), [])


if __name__ == "__main__":
    unittest.main()
