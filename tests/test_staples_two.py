import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (ChaosWarp, Counter, Draw, PutSourceOnLibraryTop, activated_abilities, cumulative_upkeep,
                                      spell_effects)
from infernal_machine.game import Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_real_oracle import REAL

LAND = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
BOLT = Card(name="Bolt", mana_cost="{R}", type_line="Instant", oracle_text="Draw a card.")
BLESSING = Card(name="Test Blessing", mana_cost="{1}", type_line="Enchantment — Aura", oracle_text="Enchant creature")
TOKEN = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")


def no_shuffle(game):
    game.rng.shuffle = lambda cards: None  # the card shuffled in goes to the bottom
    return game


def resolve_everything(game):
    game._put_triggers_on_stack()
    while game.stack:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()
    game._check_state()


class ParseTests(unittest.TestCase):
    def test_the_real_texts(self):
        self.assertEqual(spell_effects(REAL["Mana Drain"]), [Counter("spell", delayed_mana=True)])
        self.assertEqual(spell_effects(REAL["Chaos Warp"]), [ChaosWarp()])
        [ability] = activated_abilities(REAL["Sensei's Divining Top"])[1:]
        self.assertEqual(ability.effects, (Draw(1), PutSourceOnLibraryTop()))
        self.assertEqual(cumulative_upkeep(REAL["Mystic Remora"]), "{1}")
        for name in ("Mana Drain", "Chaos Warp", "Sensei's Divining Top", "Mystic Remora"):
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_half_of_a_two_sentence_spell_is_not_understood(self):
        lone = Card(name="x", type_line="Instant", oracle_text="If it's a permanent card, they put it onto the battlefield.")
        self.assertIsNone(spell_effects(lone))
        lone = Card(name="y", type_line="Instant",
                    oracle_text="At the beginning of your next main phase, add an amount of {C} equal to that spell's mana value.")
        self.assertIsNone(spell_effects(lone))


class ManaDrainTests(unittest.TestCase):
    def drain(self, x=0):
        game, _ = table3()
        a, b, _ = game.seats
        item = StackItem(Card(name="Big Spell", mana_cost="{2}{R}", cmc=3.0, type_line="Sorcery"), b, [], [], x=x)
        game.stack.append(item)
        Counter("spell", delayed_mana=True).resolve(game, a, item)
        return game, a, b

    def test_the_mana_arrives_at_your_next_main_phase(self):
        game, a, b = self.drain()
        self.assertEqual((a.delayed_mana, a.mana_pool, [c.name for c in b.graveyard]), (3, [], ["Big Spell"]))
        game.step = "main1"
        game._turn_based_actions(a)
        self.assertEqual((a.delayed_mana, [sorted(unit) for unit in a.mana_pool]), (0, [["C"]] * 3))

    def test_x_counts(self):
        game, a, b = self.drain(x=2)
        self.assertEqual(a.delayed_mana, 5)

    def test_it_is_used_up(self):
        game, a, b = self.drain()
        game.step = "main1"
        game._turn_based_actions(a)
        a.mana_pool.clear()
        game.step = "main2"
        game._turn_based_actions(a)
        self.assertEqual(a.mana_pool, [])


class ChaosWarpTests(unittest.TestCase):
    def warp(self, library, board=None):
        game, _ = table3()
        no_shuffle(game)
        a, b, _ = game.seats
        victim = Permanent(board or BEAR, owner=b)
        b.battlefield = [victim]
        b.library = list(library)
        ChaosWarp().resolve(game, a, victim)
        return game, b

    def test_a_permanent_card_on_top_enters(self):
        game, b = self.warp([LAND, BOLT])
        self.assertEqual([p.card.name for p in b.battlefield], ["Wastes"])
        self.assertEqual([c.name for c in b.library], ["Bolt", "Bear"])  # the warped Bear is shuffled in

    def test_an_instant_stays_in_the_library(self):
        game, b = self.warp([BOLT, LAND])
        self.assertEqual(b.battlefield, [])
        self.assertEqual([c.name for c in b.library], ["Bolt", "Wastes", "Bear"])

    def test_an_aura_stays_too(self):
        game, b = self.warp([BLESSING, LAND])
        self.assertEqual(b.battlefield, [])

    def test_a_token_just_goes_away(self):
        game, b = self.warp([LAND], board=TOKEN)
        self.assertEqual([p.card.name for p in b.battlefield], ["Wastes"])
        self.assertEqual(b.library, [])

    def test_the_owner_is_the_one_who_shuffles_and_reveals(self):
        game, _ = table3()
        no_shuffle(game)
        a, b, _ = game.seats
        a.library = [LAND]
        stolen = Permanent(BEAR, owner=a)  # b controls a's creature
        b.battlefield = [stolen]
        ChaosWarp().resolve(game, b, stolen)
        self.assertEqual([p.card.name for p in a.battlefield], ["Wastes"])  # a is the owner, so a's library
        self.assertEqual(b.battlefield, [])


class TopTests(unittest.TestCase):
    def test_draw_then_put_the_top_on_the_library(self):
        game, _ = table3()
        a = game.seats[0]
        top = Permanent(REAL["Sensei's Divining Top"])
        a.battlefield = [top]
        a.library = [LAND, BOLT]
        [action] = [x for x in game._activations(a, True) if "Draw a card" in x]
        game._perform(a, action)
        resolve_everything(game)
        self.assertEqual([c.name for c in a.hand], ["Wastes"])
        self.assertEqual([c.name for c in a.library], ["Sensei's Divining Top", "Bolt"])
        self.assertEqual(a.battlefield, [])


class UpkeepTests(unittest.TestCase):
    def upkeep(self, game, seat):
        for p in seat.battlefield:
            p.tapped = False
        game.step = "upkeep"
        game._turn_based_actions(seat)

    def test_the_cost_grows_each_turn(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        remora = Permanent(REAL["Mystic Remora"])
        a.battlefield = [remora, *lands(3)]
        for turn, tapped in ((1, 1), (2, 2), (3, 3)):
            self.upkeep(game, a)
            self.assertEqual((remora.counters["age"], sum(p.tapped for p in a.battlefield)), (turn, tapped))
            self.assertIn(remora, a.battlefield)

    def test_it_is_sacrificed_when_you_cannot_pay(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        remora = Permanent(REAL["Mystic Remora"], counters={"age": 2})
        a.battlefield = [remora, *lands(2)]
        self.upkeep(game, a)  # the third counter costs {1}{1}{1}
        self.assertNotIn(remora, a.battlefield)
        self.assertEqual([c.name for c in a.graveyard], ["Mystic Remora"])

    def test_it_is_sacrificed_when_you_decline(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        remora = Permanent(REAL["Mystic Remora"])
        a.battlefield = [remora, *lands(3)]
        self.upkeep(game, a)
        self.assertNotIn(remora, a.battlefield)
        self.assertEqual(sum(p.tapped for p in a.battlefield), 0)

    def test_only_on_your_own_upkeep(self):
        game, _ = table3(pick("Yes"))
        a, b, _ = game.seats
        remora = Permanent(REAL["Mystic Remora"])
        a.battlefield = [remora, *lands(3)]
        game.step = "upkeep"
        game._turn_based_actions(b)  # an opponent's upkeep
        self.assertEqual(remora.counters, {})


if __name__ == "__main__":
    unittest.main()
