"""Token-making text of the real cards in issue #77.

The cards are module-level constants so `tools/audit_real_text.py` compares them with Scryfall's text. Scryfall could not
be reached while they were written: the lines the issue quotes are the report's own output, and the sentences the issue
cuts off with "..." were completed from memory (marked "completed from memory" below).
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (CopyToken, CreateTokens, DestroyAll, Draw, ExileAll, GiveBack, MassFilter,
                                      ReturnAllToHand, TREASURE, TargetControllerCreatesTokens, spell_effects,
                                      static_abilities)
from infernal_machine.game import CAST, Permanent
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
