"""Token-making text of the real cards in issue #77.

The cards are module-level constants so `tools/audit_real_text.py` compares them with Scryfall's text. Scryfall could not
be reached while they were written: the lines the issue quotes are the report's own output, and the sentences the issue
cuts off with "..." were completed from memory (marked "completed from memory" below).
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Amount, AttackingTokens, CopyToken, CreateTokens, DefineX, DestroyAll, Draw, ExileAll, GiveBack,
                                      MassFilter, PreventCombatDamageToYou, ReturnAllToHand, TREASURE, TargetControllerCreatesTokens,
                                      spell_effects, static_abilities, triggered_abilities)
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

BIG_SCORE = Card(name="Big Score", mana_cost="{3}{R}", type_line="Instant", colors=("R",), cmc=4,
                 oracle_text="As an additional cost to cast this spell, discard a card.\n"
                             "Draw two cards and create two Treasure tokens.")
SEIZE_THE_SPOILS = Card(name="Seize the Spoils", mana_cost="{2}{R}", type_line="Sorcery", colors=("R",), cmc=3,
                        oracle_text="As an additional cost to cast this spell, discard a card.\n"
                                    "Draw two cards and create a Treasure token.")
BRUDICLAD = Card(  # the trigger's text is completed from memory
    name="Brudiclad, Telchor Engineer", mana_cost="{4}{U}{R}", type_line="Legendary Artifact Creature — Phyrexian Artificer",
    power="4", toughness="4", colors=("U", "R"), cmc=6,
    oracle_text="Creature tokens you control have haste.\n"
                "At the beginning of combat on your turn, create a 2/1 blue Myr artifact creature token. Then you may choose "
                "a token you control. If you do, each other token you control becomes a copy of that token until end of turn.")
RITE_OF_REPLICATION = Card(name="Rite of Replication", mana_cost="{2}{U}{U}", type_line="Sorcery", colors=("U",), cmc=4,
                           oracle_text="Kicker {5}\nCreate a token that's a copy of target creature. If this spell was "
                                       "kicked, create five of those tokens instead.")
RAPID_HYBRIDIZATION = Card(name="Rapid Hybridization", mana_cost="{U}", type_line="Instant", colors=("U",), cmc=1,
                           oracle_text="Destroy target creature. It can't be regenerated. That creature's controller "
                                       "creates a 3/3 green Frog Lizard creature token.")
RESCULPT = Card(name="Resculpt", mana_cost="{1}{U}", type_line="Instant", colors=("U",), cmc=2,
                oracle_text="Exile target artifact or creature. Its controller creates a 4/4 blue and red Elemental "
                            "creature token.")
PERPLEXING_TEST = Card(name="Perplexing Test", mana_cost="{4}{U}", type_line="Sorcery", colors=("U",), cmc=5,
                       oracle_text="Choose one —\n• Return all creature tokens to their owners' hands.\n"
                                   "• Return all nontoken creatures to their owners' hands.")
CEASELESS_CONFLICT = Card(name="Ceaseless Conflict", mana_cost="{3}{R}{W}", type_line="Sorcery", colors=("R", "W"), cmc=5,
                          oracle_text="Destroy all creatures. Then create a 3/2 red and white Spirit creature token for "
                                      "each nontoken creature you controlled that was destroyed this way.")
OVERSIMPLIFY = Card(name="Oversimplify", mana_cost="{3}{G}{U}", type_line="Sorcery", colors=("G", "U"), cmc=5,
                    oracle_text="Exile all creatures. Each player creates a 0/0 green and blue Fractal creature token and "
                                "puts a number of +1/+1 counters on it equal to the total power of the creatures they "
                                "controlled that were exiled this way.")
DEEKAH = Card(  # the trigger's second sentence is completed from memory
    name="Deekah, Fractal Theorist", mana_cost="{3}{U}", type_line="Legendary Creature — Human Wizard", power="2",
    toughness="4", colors=("U",), cmc=4,
    oracle_text="Magecraft \u2014 Whenever you cast or copy an instant or sorcery spell, create a 0/0 green and blue "
                "Fractal creature token. Put X +1/+1 counters on it, where X is the amount of mana spent to cast that "
                "spell.\n{3}{U}: Target creature token can't be blocked this turn.")
FURYGALE_FLOCKING = Card(  # the second sentence ends "un..." in the issue; the rest is completed from memory
    name="Furygale Flocking", mana_cost="{3}{U}{R}", type_line="Sorcery", colors=("U", "R"), cmc=5,
    oracle_text="For each opponent, create two 3/3 blue and red Elemental creature tokens with flying that attack that "
                "opponent this turn if able. They gain haste until end of turn. Exile them at the beginning of the next "
                "end step.")
INKSHIELD = Card(  # the second sentence ends "wi..." in the issue; the rest is completed from memory
    name="Inkshield", mana_cost="{3}{W}{B}", type_line="Instant", colors=("W", "B"), cmc=5,
    oracle_text="Prevent all combat damage that would be dealt to you this turn. For each 1 damage prevented this way, "
                "create a 2/1 white and black Inkling creature token with flying.")
STORM_KILN_ARTIST = Card(name="Storm-Kiln Artist", mana_cost="{3}{R}", type_line="Creature — Dwarf Shaman", power="2",
                         toughness="2", colors=("R",), cmc=4,
                         oracle_text="This creature gets +1/+0 for each artifact you control.\nMagecraft — Whenever you "
                                     "cast or copy an instant or sorcery spell, create a Treasure token.")

MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))
TOKEN_BEAR = Card(name="Bear", type_line="Token Creature — Bear", power="2", toughness="2")


def count(seat, name):
    return sum(p.card.name == name for p in seat.battlefield)


class DrawAndCreateTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(BIG_SCORE), [Draw(2), CreateTokens(2, TREASURE)])
        self.assertEqual(spell_effects(SEIZE_THE_SPOILS), [Draw(2), CreateTokens(1, TREASURE)])
        self.assertEqual(unsupported_lines(BIG_SCORE), [])
        self.assertEqual(unsupported_lines(SEIZE_THE_SPOILS), [])

    def test_big_score_discards_draws_and_makes_treasures(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [BIG_SCORE, BEAR], lands(4)
        game._priority_round(a)
        self.assertEqual((len(a.hand), count(a, "Treasure"), a.graveyard), (2, 2, [BEAR, BIG_SCORE]))


class TokenStaticTests(unittest.TestCase):
    def test_creature_tokens_you_control_have_haste(self):
        [buff] = static_abilities(BRUDICLAD)
        self.assertEqual((buff.modifier.keywords, buff.token), (frozenset({"haste"}), True))
        game, _ = table3()
        a, b, _c = game.seats
        token, card, theirs = Permanent(TOKEN_BEAR), Permanent(BEAR), Permanent(TOKEN_BEAR)
        a.battlefield, b.battlefield = [Permanent(BRUDICLAD), token, card], [theirs]
        self.assertEqual([game.has_keyword(p, "haste") for p in (token, card, theirs)], [True, False, False])


class CopyCountTests(unittest.TestCase):
    def test_kicked_rite_makes_five_copies(self):
        self.assertEqual(spell_effects(RITE_OF_REPLICATION)[0], CopyToken("creature"))
        self.assertEqual(unsupported_lines(RITE_OF_REPLICATION), [])
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        CopyToken("creature", count=5).resolve(game, a, bear)
        self.assertEqual(count(a, "Bear"), 6)


class ThatCreaturesControllerTests(unittest.TestCase):
    def test_rapid_hybridization_gives_the_frog_to_the_creatures_controller(self):
        self.assertEqual(spell_effects(RAPID_HYBRIDIZATION)[-1],
                         TargetControllerCreatesTokens(1, Card(name="Frog Lizard", type_line="Token Creature — Frog Lizard",
                                                               colors=("G",), power="3", toughness="3")))
        self.assertEqual(unsupported_lines(RAPID_HYBRIDIZATION), [])
        self.assertEqual(unsupported_lines(RESCULPT), [])
        game, _ = table3(pick(CAST))
        a, b, _c = game.seats
        a.hand, a.battlefield = [RAPID_HYBRIDIZATION], lands(1)
        b.battlefield = [Permanent(BEAR)]
        game._priority_round(a)
        self.assertEqual((count(b, "Bear"), count(b, "Frog Lizard"), count(a, "Frog Lizard")), (0, 1, 0))


class ReturnAllTokensTests(unittest.TestCase):
    def test_parse(self):
        [modal] = spell_effects(PERPLEXING_TEST)
        self.assertEqual(list(modal.modes),
                         [(ReturnAllToHand("creature", MassFilter(token=True)),),
                          (ReturnAllToHand("creature", MassFilter(token=False)),)])
        self.assertEqual(unsupported_lines(PERPLEXING_TEST), [])

    def test_only_tokens_or_only_cards_go_back(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(TOKEN_BEAR), Permanent(BEAR)]
        b.battlefield = [Permanent(TOKEN_BEAR), Permanent(BEAR)]
        ReturnAllToHand("creature", MassFilter(token=True)).resolve(game, a, None)
        self.assertEqual(([p.card.name for p in a.battlefield], [p.card.name for p in b.battlefield]), (["Bear"], ["Bear"]))
        self.assertEqual((a.hand, b.hand), ([], []))  # a token that leaves is gone
        ReturnAllToHand("creature", MassFilter(token=False)).resolve(game, a, None)
        self.assertEqual((a.battlefield, b.battlefield, a.hand, b.hand), ([], [], [BEAR], [BEAR]))


class StormKilnArtistTests(unittest.TestCase):
    def test_it_is_playable_and_makes_a_treasure_on_each_spell(self):
        self.assertEqual(unsupported_lines(STORM_KILN_ARTIST), [])
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [SEIZE_THE_SPOILS, BEAR], lands(3) + [Permanent(STORM_KILN_ARTIST)]
        game._priority_round(a)
        self.assertEqual(count(a, "Treasure"), 2)  # one from the spell, one from the artist
        self.assertEqual(game.power(next(p for p in a.battlefield if p.card.name == "Storm-Kiln Artist")), 4)


SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", colors=("R", "W"), power="3", toughness="2")
FRACTAL = Card(name="Fractal", type_line="Token Creature — Fractal", colors=("G", "U"), power="0", toughness="0")
OGRE = Card(name="Ogre", mana_cost="{2}{R}", type_line="Creature — Ogre", power="3", toughness="3")
INDESTRUCTIBLE = Card(name="Darksteel", mana_cost="{3}", type_line="Artifact Creature — Myr", oracle_text="Indestructible",
                      power="0", toughness="1")


class WipeGiftTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(CEASELESS_CONFLICT),
                         [DestroyAll("creature", gives=GiveBack(1, SPIRIT, who="you", nontoken=True))])
        self.assertEqual(spell_effects(OVERSIMPLIFY),
                         [ExileAll("creature", gives=GiveBack(1, FRACTAL, who="each player", power_counters=True))])
        self.assertEqual(unsupported_lines(CEASELESS_CONFLICT), [])
        self.assertEqual(unsupported_lines(OVERSIMPLIFY), [])

    def test_ceaseless_conflict_pays_you_for_your_own_nontoken_creatures_only(self):
        game, _ = table3(pick(CAST))
        a, b, _c = game.seats
        a.hand = [CEASELESS_CONFLICT]
        a.battlefield = lands(5) + [Permanent(BEAR), Permanent(OGRE), Permanent(TOKEN_BEAR), Permanent(INDESTRUCTIBLE)]
        b.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        game._priority_round(a)
        self.assertEqual((count(a, "Spirit"), count(b, "Spirit"), count(a, "Darksteel"), count(b, "Bear")), (2, 0, 1, 0))

    def test_oversimplify_gives_each_player_a_fractal_as_big_as_what_they_lost(self):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        a.hand = [OVERSIMPLIFY]
        a.battlefield = lands(5) + [Permanent(BEAR), Permanent(OGRE)]
        b.battlefield = [Permanent(TOKEN_BEAR, counters={"+1/+1": 1})]
        game._priority_round(a)
        fractals = {seat: [p for p in seat.battlefield if p.card.name == "Fractal"] for seat in (a, b, c)}
        self.assertEqual(([p.counters for p in fractals[a]], [p.counters for p in fractals[b]]),
                         ([{"+1/+1": 5}], [{"+1/+1": 3}]))
        self.assertEqual((fractals[c], [p.card.name for p in a.battlefield if "Creature" in p.card.type_line]),
                         ([], ["Fractal"]))  # a 0/0 with no counters dies; the exiled creatures are gone


class DeekahTests(unittest.TestCase):
    def test_parse(self):
        [magecraft] = triggered_abilities(DEEKAH)
        self.assertEqual(magecraft.effects, (DefineX(Amount("mana_spent")), CreateTokens(1, FRACTAL, ("X", "+1/+1"))))
        self.assertEqual(unsupported_lines(DEEKAH), [])

    def test_the_fractal_is_as_big_as_the_mana_spent_and_a_copy_spends_none(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [SEIZE_THE_SPOILS, BEAR], lands(3) + [Permanent(DEEKAH)]
        game._priority_round(a)
        [fractal] = [p for p in a.battlefield if p.card.name == "Fractal"]
        self.assertEqual((fractal.counters, game.power(fractal)), ({"+1/+1": 3}, 3))
        a.hand = [SEIZE_THE_SPOILS, BEAR]
        a.battlefield += lands(3)
        game._priority_round(a)  # a second one: its own cost, not the first spell's
        self.assertEqual(sorted(p.counters["+1/+1"] for p in a.battlefield if p.card.name == "Fractal"), [3, 3])
        item = StackItem(SEIZE_THE_SPOILS, a, [], [], mana_spent=3)
        game.stack.append(item)
        game.copy_spell(item, a)
        run_stack(game)
        game._check_state()
        self.assertEqual(count(a, "Fractal"), 2)  # the copy's Fractal came in 0/0 with no counters and died


ELEMENTAL = Card(name="Elemental", type_line="Token Creature — Elemental", colors=("U", "R"), power="3", toughness="3",
                 oracle_text="Flying")


class FurygaleFlockingTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(FURYGALE_FLOCKING), [AttackingTokens(2, ELEMENTAL, haste=True, exile_at_end=True)])
        self.assertEqual(unsupported_lines(FURYGALE_FLOCKING), [])
        half = Card(name="Half", type_line="Sorcery", oracle_text="They gain haste until end of turn.")
        self.assertIsNone(spell_effects(half))  # "they" has no tokens to mean

    def test_two_hasty_flyers_per_opponent_that_must_attack_them_and_are_exiled_at_end_of_turn(self):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        a.hand, a.battlefield = [FURYGALE_FLOCKING], lands(5)
        game._priority_round(a)
        elementals = [p for p in a.battlefield if p.card.name == "Elemental"]
        self.assertEqual([p.must_attack for p in elementals], [b, b, c, c])
        self.assertTrue(all(game.has_keyword(p, "haste") and game.has_keyword(p, "flying") for p in elementals))
        game.step = "declare_attackers"
        game._turn_based_actions(a)
        self.assertEqual(sorted((att.attacker.card.name, att.defender.index) for att in game.combat.attacks),
                         [("Elemental", 1), ("Elemental", 1), ("Elemental", 2), ("Elemental", 2)])
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual((count(a, "Elemental"), a.graveyard, a.exile), (0, [FURYGALE_FLOCKING], []))  # tokens just stop existing


INKLING = Card(name="Inkling", type_line="Token Creature — Inkling", colors=("W", "B"), power="2", toughness="1",
               oracle_text="Flying")


class InkshieldTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(INKSHIELD), [PreventCombatDamageToYou(INKLING)])
        self.assertEqual(unsupported_lines(INKSHIELD), [])
        half = Card(name="Half", type_line="Instant", oracle_text="For each 1 damage prevented this way, create a Treasure token.")
        self.assertIsNone(spell_effects(half))

    def test_combat_damage_to_you_this_turn_becomes_inklings(self):
        game, _ = table3()
        a, b, _c = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        PreventCombatDamageToYou(INKLING).resolve(game, a, None)
        game.damage(a, 3, source=bear, combat=True)
        self.assertEqual((a.life, count(a, "Inkling")), (40, 3))
        self.assertTrue(game.has_keyword(a.battlefield[0], "flying"))
        game.damage(a, 2, source=bear)  # not combat damage
        game.damage(b, 2, source=bear, combat=True)  # not you
        self.assertEqual((a.life, b.life), (38, 38))
        game.turn += 1
        game.damage(a, 2, source=bear, combat=True)
        self.assertEqual((a.life, count(a, "Inkling")), (36, 3))
