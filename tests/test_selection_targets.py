import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Destroy, Exile, ReturnFromGraveyard, ReturnToHand, SearchLibrary, spell_effects
from infernal_machine.game import CAST, NO_TARGET, SEARCH_CARD_PROMPT, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3

ELF = Card(name="Elf", mana_cost="{G}", type_line="Creature — Elf Druid", power="1", toughness="1")
GOBLIN = Card(name="Goblin", mana_cost="{R}", type_line="Creature — Goblin", power="1", toughness="1")
TOKEN = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")


def sorcery(name, text):
    return Card(name=name, mana_cost="{U}", type_line="Sorcery", oracle_text=text)


def picks(*indexes):
    """Cast the first spell; answer each target prompt with the next index (then the first)."""
    wanted = iter(indexes)
    base = pick(CAST)
    return lambda prompt, options: next(wanted, 0) if prompt.startswith(TARGET_PROMPT) else base(prompt, options)


def prompts(players, start):
    return [o for p, o in players[0].prompts if p.startswith(start)]


class ParseTests(unittest.TestCase):
    def test_up_to_n_targets(self):
        self.assertEqual(spell_effects(sorcery("Bounce", "Return up to two target creatures to their owners' hands.")),
                         [ReturnToHand("creature", optional_target=True), ReturnToHand("creature", optional_target=True, distinct=True)])
        self.assertEqual(len(spell_effects(sorcery("Doom", "Destroy up to three target creatures."))), 3)
        self.assertEqual(spell_effects(sorcery("Banish", "Exile up to two target nonland permanents you don't control."))[1],
                         Exile("nonland permanent you don't control", optional_target=True, distinct=True))
        self.assertEqual(spell_effects(sorcery("Raise", "Return up to two target creature cards from your graveyard to your hand."))[1],
                         ReturnFromGraveyard("graveyard:creature:yours", "hand", optional_target=True, distinct=True))

    def test_up_to_one(self):
        self.assertEqual(spell_effects(sorcery("Doom", "Destroy up to one target creature.")),
                         [Destroy("creature", optional_target=True)])
        self.assertEqual(spell_effects(sorcery("Banish", "Exile up to one target artifact.")),
                         [Exile("artifact", optional_target=True)])

    def test_more_kinds_of_target(self):
        for text in ("Exile target creature token.", "Destroy target tapped creature.", "Exile target attacking creature.",
                     "Destroy target untapped creature an opponent controls.", "Destroy target land.",
                     "Exile target nontoken creature."):
            self.assertEqual(unsupported_lines(sorcery("x", text)), [], text)

    def test_tribal_cards(self):
        self.assertEqual(spell_effects(sorcery("Summon", "Search your library for an Elf card, reveal it, put it into your hand, "
                                                       "then shuffle.")), [SearchLibrary("elf", "hand", True)])
        self.assertEqual(spell_effects(sorcery("Recall", "Return target Goblin card from your graveyard to your hand."))[0].target,
                         "graveyard:goblin:yours")

    def test_unrelated_wording_is_still_unsupported(self):
        self.assertIsNone(spell_effects(sorcery("x", "Return up to two target creatures that share a creature type to their "
                                                    "owners' hands.")))


class UpToTests(unittest.TestCase):
    def setup(self, text, *indexes):
        game, players = table3(picks(*indexes))
        a, b, c = game.seats
        a.hand, a.battlefield = [sorcery("Spell", text)], lands(1)
        b.battlefield = [Permanent(BEAR), Permanent(OGRE)]
        c.battlefield = [Permanent(BEAR)]
        game._priority_round(a)
        return game, players

    def test_two_different_targets(self):
        game, players = self.setup("Return up to two target creatures to their owners' hands.", 0, 0)
        first, second = prompts(players, TARGET_PROMPT)
        self.assertEqual((len(first), len(second)), (4, 3))  # three creatures plus "No target"; the first can't come again
        self.assertEqual(first[-1], NO_TARGET)
        self.assertEqual([len(s.hand) for s in game.seats], [0, 2, 0])  # both of seat 1's creatures

    def test_the_second_can_be_left_out(self):
        game, players = self.setup("Destroy up to two target creatures.", 0, 2)  # Bear, then "No target"
        self.assertEqual([len(s.battlefield) for s in game.seats], [1, 1, 1])

    def test_no_targets_at_all_is_fine(self):
        game, players = self.setup("Destroy up to two target creatures.", 3, 3)
        self.assertEqual([len(s.battlefield) for s in game.seats], [1, 2, 1])
        self.assertEqual(game.stack, [])

    def test_the_same_kind_in_two_effects_may_repeat(self):
        game, players = table3(picks(0, 0))
        a, b, c = game.seats
        a.hand, a.battlefield = [sorcery("Spell", "Destroy target creature. Return target creature to its owner's hand.")], lands(1)
        b.battlefield = [Permanent(BEAR)]
        game._priority_round(a)
        self.assertEqual(len(prompts(players, TARGET_PROMPT)[1]), 1)  # the same Bear is still a legal second target

    def test_graveyard_cards_are_offered_by_name_so_two_picks_are_two_names(self):
        game, players = table3(picks(0, 0))
        a = game.seats[0]
        a.hand, a.battlefield = [sorcery("Raise", "Return up to two target creature cards from your graveyard to your hand.")], lands(1)
        a.graveyard = [BEAR, BEAR, OGRE]
        game._priority_round(a)
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Ogre"])  # the Bear can't be picked twice


class TargetKindTests(unittest.TestCase):
    def options(self, text, setup):
        game, players = table3(pick(CAST))
        a, b, _ = game.seats
        a.hand, a.battlefield = [sorcery("Spell", text)], lands(1)
        setup(game, a, b)
        game._priority_round(a)
        return game, prompts(players, TARGET_PROMPT)

    def test_only_tokens(self):
        game, shown = self.options("Exile target creature token.", lambda g, a, b: setattr(b, "battlefield", [Permanent(BEAR), Permanent(TOKEN)]))
        self.assertEqual(len(shown[0]), 1)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Bear"])

    def test_nontoken_creatures(self):
        game, shown = self.options("Exile target nontoken creature.", lambda g, a, b: setattr(b, "battlefield", [Permanent(TOKEN), Permanent(BEAR)]))
        self.assertEqual(len(shown[0]), 1)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Spirit"])

    def test_tapped_and_untapped(self):
        def setup(g, a, b):
            b.battlefield = [Permanent(BEAR, tapped=True), Permanent(OGRE)]
        game, shown = self.options("Destroy target tapped creature.", setup)
        self.assertEqual(len(shown[0]), 1)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Ogre"])
        game, shown = self.options("Destroy target untapped creature.", setup)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Bear"])

    def test_attacking(self):
        from infernal_machine.combat import Attack

        def setup(g, a, b):
            attacker, idle = Permanent(BEAR), Permanent(OGRE)
            b.battlefield = [attacker, idle]
            g.combat.attacks = [Attack(attacker, b, a)]
        game, shown = self.options("Exile target attacking creature.", setup)
        self.assertEqual(len(shown[0]), 1)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Ogre"])

    def test_lands(self):
        game, shown = self.options("Destroy target land.", lambda g, a, b: setattr(b, "battlefield", lands(1) + [Permanent(BEAR)]))
        self.assertEqual(len(shown[0]), 2)  # their land and your own


class TribalTests(unittest.TestCase):
    def test_a_tribal_tutor(self):
        game, players = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [sorcery("Summon", "Search your library for an Elf card, reveal it, put it into your hand, then shuffle.")], lands(1)
        a.library = [GOBLIN, ELF, BEAR]
        game._priority_round(a)
        self.assertEqual(prompts(players, SEARCH_CARD_PROMPT), [["Elf"]])
        self.assertEqual([c.name for c in a.hand], ["Elf"])

    def test_tribal_recursion(self):
        game, players = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [sorcery("Recall", "Return target Goblin card from your graveyard to your hand.")], lands(1)
        a.graveyard = [ELF, GOBLIN]
        game._priority_round(a)
        self.assertEqual([c.name for c in a.hand], ["Goblin"])


class RemovedAttackerTests(unittest.TestCase):
    def test_an_attacker_that_leaves_before_blocks_is_removed_from_combat(self):
        from infernal_machine.combat import Attack
        game, _ = table3()
        a, b, _ = game.seats
        attacker = Permanent(BEAR)
        a.battlefield = [attacker]
        game.combat.attacks = [Attack(attacker, a, b)]
        game.exile(attacker)
        self.assertEqual(game.combat.attacks, [])
        game.combat.declare_blockers()  # used to crash asking for the label of the gone attacker
