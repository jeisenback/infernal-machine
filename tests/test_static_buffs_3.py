"""Aura grants and other static buffs from the real cards in issue #75."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import attached_abilities
from infernal_machine.game import CHOOSE_TYPE_PROMPT, SACRIFICE_COST_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

RELIC = Card(name="Relic", type_line="Artifact")


class EldraziConscriptionTests(unittest.TestCase):
    def test_it_is_understood(self):
        card = REAL["Eldrazi Conscription"]
        self.assertEqual(unsupported_lines(card), [])
        [buff] = attached_abilities(card)
        self.assertEqual((buff.modifier.power, buff.modifier.keywords), (10, frozenset({"trample", "annihilator 2"})))

    def test_the_enchanted_creature_has_annihilator_2(self):
        game, _ = table3(pick("Attack Player: B"))
        a, b, _c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(REAL["Eldrazi Conscription"], attached_to=bear)]
        b.battlefield = [Permanent(RELIC) for _ in range(5)]
        self.assertEqual((game.power(bear), game.annihilator(bear)), (12, 2))
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 3)  # two sacrificed

    def test_no_annihilator_without_the_aura(self):
        game, _ = table3(pick("Attack Player: B"))
        a, b, _c = game.seats
        a.battlefield = [Permanent(BEAR)]
        b.battlefield = [Permanent(RELIC)]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 1)


class AngelicDestinyTests(unittest.TestCase):
    def test_it_pumps_gives_keywords_and_makes_the_creature_an_angel(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        lord = Card(name="Angel Lord", type_line="Creature " + chr(0x2014) + " Angel", power="1", toughness="1",
                    oracle_text="Angels you control get +1/+1.")
        a.battlefield = [bear, Permanent(lord)]
        self.assertEqual(game.power(bear), 2)
        a.battlefield.append(Permanent(REAL["Angelic Destiny"], attached_to=bear))
        self.assertEqual((game.power(bear), game.toughness(bear)), (2 + 4 + 1, 2 + 4 + 1))  # +4/+4, and the Angel lord's +1/+1
        self.assertEqual((game.has_keyword(bear, "flying"), game.has_keyword(bear, "first strike")), (True, True))
        self.assertIn("Angel", game.subtypes(bear))
        self.assertEqual(game.power(a.battlefield[1]), 1 + 1)  # the lord itself is an Angel too


class FallenIdealTests(unittest.TestCase):
    def test_flying_a_sacrifice_ability_and_it_returns_to_hand(self):
        def policy(prompt, options):  # sacrifice the last creature listed, the spare Bear
            return len(options) - 1 if SACRIFICE_COST_PROMPT.matches(prompt) else pick("Activate")(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        bear, fodder = Permanent(BEAR), Permanent(BEAR)
        ideal = Permanent(REAL["Fallen Ideal"], attached_to=bear)
        a.battlefield = [bear, fodder, ideal]
        self.assertTrue(game.has_keyword(bear, "flying"))
        [action] = [x for x in game._activations(a, True) if "Sacrifice a creature" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((game.power(bear), game.toughness(bear)), (2 + 2, 2 + 1))
        self.assertEqual(len(a.battlefield) - 1, 1)  # one Bear was the cost
        game._leave_battlefield(ideal, "destroyed")
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Fallen Ideal"])


class PatchworkBannerTests(unittest.TestCase):
    def test_it_names_the_most_common_type_and_pumps_it(self):
        game, _ = table3()
        a = game.seats[0]
        wolf = Card(name="Wolf", type_line="Creature " + chr(0x2014) + " Wolf", power="2", toughness="2")
        bear = Card(name="Bear", type_line="Creature " + chr(0x2014) + " Bear", power="2", toughness="2")
        a.library = [wolf, wolf, wolf, bear]
        a.battlefield = [Permanent(wolf), Permanent(bear)]
        banner = Permanent(REAL["Patchwork Banner"])
        game._enter(a, banner)
        self.assertEqual(banner.chosen_type, "Wolf")
        self.assertEqual((game.power(a.battlefield[0]), game.power(a.battlefield[1])), (3, 2))

    def test_the_player_chooses(self):
        game, players = table3(lambda prompt, options: options.index("Bear") if CHOOSE_TYPE_PROMPT.matches(prompt) else 0)
        a = game.seats[0]
        wolf = Card(name="Wolf", type_line="Creature " + chr(0x2014) + " Wolf", power="2", toughness="2")
        bear = Card(name="Bear", type_line="Creature " + chr(0x2014) + " Bear", power="2", toughness="2")
        a.library = [wolf, bear]
        a.battlefield = [Permanent(bear)]
        game._enter(a, Permanent(REAL["Patchwork Banner"]))
        self.assertEqual(game.power(a.battlefield[0]), 3)


SPIRIT = Card(name="Spirit", type_line="Token Creature " + chr(0x2014) + " Spirit", power="1", toughness="1")


class VanguardOfTheRestlessTests(unittest.TestCase):
    VANGUARD = REAL["Vanguard of the Restless"]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.VANGUARD), [])

    def test_spirits_grow_with_each_commander_cast(self):
        game, _ = table3()
        a = game.seats[0]
        spirit = Permanent(SPIRIT)
        a.battlefield = [Permanent(self.VANGUARD), spirit, Permanent(BEAR)]
        self.assertEqual(game.power(spirit), 1)
        a.commander_casts = {"Omnath": 2, "Other": 1}
        self.assertEqual((game.power(spirit), game.power(a.battlefield[2])), (1 + 3, 2))  # only Spirits; the Vanguard is one too
        self.assertEqual(game.power(a.battlefield[0]), 2 + 3)

    def test_it_comes_back_from_the_graveyard_when_a_spirit_enters_and_you_pay(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard, a.battlefield = [self.VANGUARD], lands(3)
        game._enter(a, Permanent(SPIRIT))
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Spirit", "Vanguard of the Restless"])
        self.assertEqual(a.graveyard, [])

    def test_it_stays_if_you_cannot_pay_or_a_non_spirit_enters(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard, a.battlefield = [self.VANGUARD], lands(2)
        game._enter(a, Permanent(SPIRIT))
        run_stack(game)
        a.battlefield = lands(3)
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertEqual(a.graveyard, [self.VANGUARD])


class VeyranTests(unittest.TestCase):
    VEYRAN = REAL["Veyran, Voice of Duality"]
    STUDY = Card(name="Study", mana_cost="{1}", type_line="Instant", oracle_text="Draw a card.")

    def cast(self, game, seat, card):
        seat.cast_log.append((game.turn, card))
        game._observe("cast", card, seat)
        run_stack(game)

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.VEYRAN), [])

    def test_magecraft_triggers_twice_for_an_instant_you_cast(self):
        game, _ = table3()
        a = game.seats[0]
        veyran = Permanent(self.VEYRAN)
        a.battlefield = [veyran]
        self.cast(game, a, self.STUDY)
        self.assertEqual((game.power(veyran), game.toughness(veyran)), (2 + 2, 2 + 2))

    def test_a_creature_spell_or_an_opponents_spell_does_not_double(self):
        game, _ = table3()
        a, b, _c = game.seats
        veyran = Permanent(self.VEYRAN)
        a.battlefield = [veyran]
        self.cast(game, a, BEAR)
        self.assertEqual(game.power(veyran), 2)  # not an instant or sorcery: no magecraft at all
        self.cast(game, b, self.STUDY)
        self.assertEqual(game.power(veyran), 2)  # magecraft only watches your own spells
