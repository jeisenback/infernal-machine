import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import CopySpell, clone_kind, spell_effects
from infernal_machine.game import CAST, CLONE_PROMPT, NOT_A_COPY, StackItem, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import BOLT, DIVINATION, FOREST, lands, pick, table

CLONE = REAL["Clone"]
MIRROR = Card(name="Mirror", mana_cost="{2}{U}", type_line="Creature — Shapeshifter", power="0", toughness="0",
              oracle_text="You may have Mirror enter the battlefield as a copy of a creature you control.")
HEALER = creature("Healer", 2, 2, "When CARDNAME enters, you gain 2 life.")
TWINCAST = Card(name="Twincast", mana_cost="{U}{U}", type_line="Instant",
                oracle_text="Copy target instant or sorcery spell. You may choose new targets for the copy.")
REVERB = Card(name="Reverb", mana_cost="{U}{U}", type_line="Instant",
              oracle_text="Copy target instant or sorcery spell you control. You may choose new targets for the copy.")


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if "Creature" in p.card.type_line)


class CloneTests(unittest.TestCase):
    def cast(self, card, mine=(), theirs=(), policy=None):
        game, player, _ = table(policy or pick(CAST))
        a, b = game.seats
        a.hand = [card]
        a.battlefield = lands(5) + [Permanent(c) for c in mine]
        b.battlefield = [Permanent(c) for c in theirs]
        game._priority_round(a)
        return game, a, b, player

    def test_parse(self):
        self.assertEqual(clone_kind(CLONE), ("creature", False))
        self.assertEqual(clone_kind(MIRROR), ("creature", True))
        self.assertIsNone(clone_kind(BEAR))
        for card in (CLONE, MIRROR):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_it_enters_as_a_copy_of_a_creature(self):
        game, a, b, _ = self.cast(CLONE, theirs=[OGRE])
        copy = next(p for p in a.battlefield if "Creature" in p.card.type_line)
        self.assertEqual((copy.card.name, game.power(copy), game.toughness(copy)), ("Ogre", 3, 3))
        self.assertEqual(copy.real_card, CLONE)
        self.assertEqual(names(b), ["Ogre"])  # the original is untouched

    def test_the_copy_triggers_enters_abilities(self):
        game, a, _, _ = self.cast(CLONE, theirs=[HEALER])
        self.assertEqual(a.life, 42)

    def test_it_can_copy_nothing_and_then_dies_as_a_0_0(self):
        game, a, _, _ = self.cast(CLONE, theirs=[OGRE], policy=lambda prompt, options: (
            len(options) - 1 if CLONE_PROMPT.matches(prompt) else
            next(i for i, o in enumerate(options) if o.startswith(CAST)) if any(o.startswith(CAST) for o in options)
            else options.index("Pass")))
        self.assertEqual(names(a), [])
        self.assertEqual([c.name for c in a.graveyard], ["Clone"])

    def test_with_nothing_to_copy_it_is_a_0_0(self):
        game, a, _, _ = self.cast(CLONE)
        self.assertEqual(names(a), [])

    def test_it_goes_to_the_graveyard_as_itself(self):
        game, a, _, _ = self.cast(CLONE, theirs=[OGRE])
        game.destroy(next(p for p in a.battlefield if p.card.name == "Ogre"))
        self.assertEqual([c.name for c in a.graveyard], ["Clone"])

    def test_counters_and_damage_are_not_copied(self):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        big = Permanent(OGRE)
        big.counters = {"+1/+1": 2}
        big.damage = 1
        b.battlefield = [big]
        a.hand = [CLONE]
        a.battlefield = lands(5)
        game._priority_round(a)
        copy = next(p for p in a.battlefield if p.card.name == "Ogre")
        self.assertEqual((copy.counters, copy.damage), ({}, 0))

    def test_a_copy_of_a_token_is_not_a_token(self):
        token = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1")
        game, a, _, _ = self.cast(CLONE, theirs=[token])
        copy = next(p for p in a.battlefield if p.card.name == "Soldier")
        self.assertFalse(copy.card.type_line.startswith("Token"))
        game.destroy(copy)
        self.assertEqual([c.name for c in a.graveyard], ["Clone"])  # the Clone card, not a vanished token

    def test_only_creatures_you_control_when_it_says_so(self):
        game, _, _, player = self.cast(MIRROR, mine=[BEAR], theirs=[OGRE])
        offered = next(options for prompt, options in player.prompts if CLONE_PROMPT.matches(prompt))
        self.assertEqual(len(offered), 2)  # the Bear, and "don't copy"
        self.assertEqual(sorted(p.card.name for p in game.seats[0].battlefield if "Creature" in p.card.type_line),
                         ["Bear", "Bear"])

    def test_the_bot_copies_the_biggest_creature(self):
        bot = BotPlayer("A", Deck([FOREST], [CLONE], []))
        options = ["Bear 2/2 (seat 1, #1)", "Ogre 3/3 (seat 1, #2)", NOT_A_COPY]
        self.assertEqual(bot.choose(CLONE_PROMPT + "Clone", options), 1)
        self.assertEqual(bot.choose(CLONE_PROMPT + "Clone", [NOT_A_COPY]), 0)


class CopySpellTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(TWINCAST), [CopySpell("instant or sorcery spell", new_targets=True)])
        self.assertEqual(spell_effects(REVERB), [CopySpell("instant or sorcery spell you control", new_targets=True)])
        self.assertEqual(spell_effects(Card(name="x", oracle_text="Copy target instant spell.")),
                         [CopySpell("instant spell")])
        self.assertIsNone(spell_effects(Card(name="x", oracle_text="You may choose new targets for the copy.")))
        for card in (TWINCAST, REVERB):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_copy_resolves_too(self):
        game, _, _ = table(pick(CAST + "Divination", CAST + "Twincast"))
        a = game.seats[0]
        a.hand = [DIVINATION, TWINCAST]
        a.battlefield = lands(5)
        game._priority_round(a)
        self.assertEqual(len(a.hand), 4)  # two cards for the spell and two for its copy
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Divination", "Twincast"])  # the copy is not a card
        self.assertEqual(len(a.cast_log), 2)  # and was not cast

    def test_the_copy_can_have_a_new_target(self):
        picks = iter([1, 0, 0])  # the bolt hits player B, Twincast picks the bolt, the copy hits player A

        def policy(prompt, options):
            if prompt.startswith("Choose a target"):
                return next(picks)
            for i, option in enumerate(options):
                if option.startswith(CAST + "Lightning Bolt") or option.startswith(CAST + "Twincast"):
                    return i
            return options.index("Pass")
        game, _, _ = table(policy)
        a, b = game.seats
        a.hand = [BOLT, TWINCAST]
        a.battlefield = lands(5)
        game._priority_round(a)
        self.assertEqual((a.life, b.life), (37, 37))

    def test_a_countered_copy_just_ends(self):
        game, _, _ = table()
        a = game.seats[0]
        original = StackItem(DIVINATION, a, spell_effects(DIVINATION), [])
        game.stack.append(original)
        game.copy_spell(original, a)
        copy = game.stack[-1]
        self.assertTrue(copy.is_copy)
        game.counter(copy)
        self.assertEqual(a.graveyard, [])

    def test_you_control_means_only_your_spells(self):
        game, _, _ = table()
        a, b = game.seats
        game.stack.append(StackItem(DIVINATION, a, spell_effects(DIVINATION), []))
        game.stack.append(StackItem(DIVINATION, b, spell_effects(DIVINATION), []))
        self.assertEqual(len(game.target_options("instant or sorcery spell", a)), 2)
        self.assertEqual(len(game.target_options("instant or sorcery spell you control", a)), 1)

    def test_an_ability_cannot_be_copied(self):
        game, _, _ = table()
        a = game.seats[0]
        ability = StackItem(DIVINATION, a, [], [], ability=object())
        game.stack.append(ability)
        game.copy_spell(ability, a)
        self.assertEqual(len(game.stack), 1)


if __name__ == "__main__":
    unittest.main()
