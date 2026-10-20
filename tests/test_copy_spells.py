"""Copies of spells and abilities beyond "Copy target instant or sorcery spell": a copy that is red (Fork), twice when cast from a
graveyard (Increasing Vengeance), of a creature or permanent spell (Double Major, Lithoform Engine: the copy becomes a token), of an
activated or triggered ability (Return the Favor, Lithoform Engine), for a payment (Mirari), of the next spell this turn (Doublecast's
wording) and once per earlier instant or sorcery (Thousand-Year Storm). Lines are the cards' own Oracle text."""

import unittest

from infernal_machine.effects import CopySpell, spell_effects
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from infernal_machine.zones import CAST_GRAVEYARD
from tests.helpers import lands, pick, real, run_stack, table

BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")
DIVINATION = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")
HERO = real("Test Hero", "{1}{W}", "Legendary Creature — Human Knight", "Vigilance", "2", "2")
DOUBLECAST = real("Doublecast", "{R}{R}", "Sorcery",
                  "When you cast your next instant or sorcery spell this turn, copy that spell. You may choose new targets for the copy.")
FORK = real("Fork", "{R}{R}", "Instant", "Copy target instant or sorcery spell, except that the copy is red. You may choose new targets for the copy.")
VENGEANCE = real("Increasing Vengeance", "{R}{R}", "Instant",
                 "Copy target instant or sorcery spell you control. If this spell was cast from a graveyard, copy that spell twice instead. "
                 "You may choose new targets for the copies.\nFlashback {3}{R}{R} (You may cast this card from your graveyard for its "
                 "flashback cost. Then exile it.)")
DOUBLE_MAJOR = real("Double Major", "{G}{U}", "Instant",
                    "Copy target creature spell you control, except it isn't legendary if the spell is legendary. (A copy of a creature "
                    "spell becomes a token.)")
RETURN_THE_FAVOR = real("Return the Favor", "{R}{R}", "Instant",
                        "Spree (Choose one or more additional costs.)\n+ {1} — Copy target instant spell, sorcery spell, activated "
                        "ability, or triggered ability. You may choose new targets for the copy.\n+ {1} — Change the target of target "
                        "spell or ability with a single target.")
LITHOFORM = real("Lithoform Engine", "{4}", "Legendary Artifact",
                 "{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.\n{3}, {T}: Copy "
                 "target instant or sorcery spell you control. You may choose new targets for the copy.\n{4}, {T}: Copy target permanent "
                 "spell you control. (The copy becomes a token.)")
MIRARI = real("Mirari", "{5}", "Legendary Artifact",
              "Whenever you cast an instant or sorcery spell, you may pay {3}. If you do, copy that spell. You may choose new targets for the copy.")
STORM = real("Thousand-Year Storm", "{4}{U}{R}", "Enchantment",
             "Whenever you cast an instant or sorcery spell, copy it for each other instant and sorcery spell you've cast before it this "
             "turn. You may choose new targets for the copies.")
HEALER = real("Healing Hall", "{1}{W}", "Creature — Human Cleric", "When this creature enters, you gain 2 life.", "1", "1")


def cast(policy, hand, battlefield=(), n=7):
    game, _, _ = table(policy)
    a = game.seats[0]
    a.hand = list(hand)
    a.battlefield = lands(n) + list(battlefield)
    game._priority_round(a)
    run_stack(game)
    return game, a


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (DOUBLECAST, FORK, VENGEANCE, DOUBLE_MAJOR, RETURN_THE_FAVOR, LITHOFORM, MIRARI, STORM):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_what_the_copies_are(self):
        self.assertEqual(spell_effects(FORK), [CopySpell("instant or sorcery spell", new_targets=True, color="R")])
        self.assertEqual(spell_effects(VENGEANCE), [CopySpell("instant or sorcery spell you control", new_targets=True, twice_from_graveyard=True)])
        odd = real("Odd Fork", "{R}", "Instant", "Copy target instant or sorcery spell, except that the copy is a Goblin.")
        self.assertEqual(len(unsupported_lines(odd)), 1)


class CopiedSpellTests(unittest.TestCase):
    def test_doublecast_copies_the_next_instant_or_sorcery_this_turn(self):
        game, a = cast(pick(CAST + "Doublecast", CAST + "Divination"), [DOUBLECAST, DIVINATION])
        self.assertEqual(len(a.hand), 4)

    def test_forks_copy_is_red(self):
        game, _, _ = table()
        a = game.seats[0]
        original = StackItem(DIVINATION, a, spell_effects(DIVINATION), [])
        game.stack.append(original)
        CopySpell("instant or sorcery spell", color="R").resolve(game, a, original)
        self.assertEqual((game.stack[-1].card.colors, game.stack[-1].is_copy), (("R",), True))
        self.assertEqual(DIVINATION.colors, ())  # the original is not touched

    def test_increasing_vengeance_copies_once_from_the_hand_and_twice_from_the_graveyard(self):
        game, a = cast(pick(CAST + "Divination", CAST + "Increasing Vengeance"), [DIVINATION, VENGEANCE])
        self.assertEqual(len(a.hand), 4)
        game, _, _ = table(pick(CAST + "Divination", CAST_GRAVEYARD + "Increasing Vengeance"))
        a = game.seats[0]
        a.hand, a.graveyard, a.battlefield = [DIVINATION], [VENGEANCE], lands(9)
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(len(a.hand), 6)
        self.assertEqual([c.name for c in a.exile], ["Increasing Vengeance"])

    def test_double_major_makes_a_nonlegendary_token_of_a_creature_spell(self):
        game, a = cast(pick(CAST + "Test Hero", CAST + "Double Major"), [HERO, DOUBLE_MAJOR])
        heroes = [p for p in a.battlefield if p.card.name == "Test Hero"]
        self.assertEqual(sorted(p.card.type_line for p in heroes), ["Legendary Creature — Human Knight", "Token Creature — Human Knight"])

    def test_mirari_copies_a_spell_for_three_mana(self):
        game, a = cast(pick(CAST + "Divination", "Pay"), [DIVINATION], [Permanent(MIRARI)])
        self.assertEqual(len(a.hand), 4)
        game, a = cast(pick(CAST + "Divination", "Don't pay"), [DIVINATION], [Permanent(MIRARI)])
        self.assertEqual(len(a.hand), 2)

    def test_thousand_year_storm_copies_once_per_earlier_instant_or_sorcery_this_turn(self):
        game, a = cast(pick(CAST + "Lightning Bolt", CAST + "Divination", "Player: B"), [BOLT, DIVINATION], [Permanent(STORM)], n=9)
        b = game.seats[1]
        self.assertEqual(b.life, 37)  # the first spell this turn: no copies
        self.assertEqual(len(a.hand), 4)  # the second: one copy
        game, a = cast(pick(CAST + "Divination"), [DIVINATION], [Permanent(STORM)])
        self.assertEqual(len(a.hand), 2)


class CopiedAbilityTests(unittest.TestCase):
    def test_return_the_favor_copies_a_triggered_ability_or_a_spell(self):
        game, _, _ = table()
        a = game.seats[0]
        copy = CopySpell("instant spell, sorcery spell, activated ability, or triggered ability", new_targets=False)
        trigger = StackItem(HEALER, a, spell_effects(DIVINATION), [], ability=object())
        game.stack.append(trigger)
        self.assertEqual(len(game.target_options(copy.target, a)), 1)
        copy.resolve(game, a, trigger)
        self.assertEqual(len(game.stack), 2)
        game.stack.clear()
        spell = StackItem(DIVINATION, a, spell_effects(DIVINATION), [])
        game.stack.append(spell)
        copy.resolve(game, a, spell)
        self.assertEqual((len(game.stack), game.stack[-1].is_copy), (2, True))

    def test_lithoform_engine_copies_an_ability_you_control_and_a_permanent_spell(self):
        game, _, _ = table()
        a, b = game.seats
        mine, theirs = StackItem(HEALER, a, [], [], ability=object()), StackItem(HEALER, b, [], [], ability=object())
        game.stack += [mine, theirs]
        self.assertEqual([i for _, i in game.target_options("activated or triggered ability you control", a)], [mine])
        game.stack.clear()
        game.stack.append(StackItem(HERO, a, [], []))
        self.assertEqual(len(game.target_options("permanent spell you control", a)), 1)
        self.assertEqual(game.target_options("permanent spell you control", b), [])
        a.battlefield = lands(4) + [Permanent(LITHOFORM)]
        [action] = [x for x in game._activations(a, True) if "permanent spell" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual(sorted(p.card.type_line for p in a.battlefield if p.card.name == "Test Hero"),
                         ["Legendary Creature — Human Knight", "Token Legendary Creature — Human Knight"])


if __name__ == "__main__":
    unittest.main()
