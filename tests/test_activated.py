import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Damage, Draw, activated_abilities
from infernal_machine.game import ACTIVATE, Permanent
from tests.test_effects import COUNTERSPELL, FOREST, lands, pick, table

MIND_STONE = Card(name="Mind Stone", mana_cost="{2}", type_line="Artifact",
                  oracle_text="{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.")
SORCERER = Card(name="Prodigal Sorcerer", mana_cost="{2}{U}", type_line="Creature — Human Wizard", power="1",
                toughness="1", oracle_text="{T}: Prodigal Sorcerer deals 1 damage to any target.")
WALKER = Card(name="Walker", mana_cost="{3}", type_line="Legendary Planeswalker — Test", loyalty="3",
              oracle_text="+1: Draw a card.\n−3: Destroy target creature.")
SHRINE = Card(name="Shrine", mana_cost="{1}", type_line="Artifact",
              oracle_text="{2}, Pay 2 life: Draw two cards. Activate only as a sorcery.")
ONCE = Card(name="Once", mana_cost="{1}", type_line="Artifact",
            oracle_text="{1}: You gain 1 life. Activate only once each turn.")
BEAR = Card(name="Bear", mana_cost="{1}", type_line="Creature — Bear", power="2", toughness="2")


def activation(game, seat, starts):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and starts in a]


class ParseTests(unittest.TestCase):
    def test_costs(self):
        [ability] = activated_abilities(MIND_STONE)
        self.assertEqual((ability.mana_cost, ability.tap, ability.sacrifice, ability.effects),
                         ("{1}", True, True, (Draw(1),)))
        [ping] = activated_abilities(SORCERER)
        self.assertEqual(ping.effects, (Damage(1, "any"),))
        plus, minus = activated_abilities(WALKER)
        self.assertEqual((plus.loyalty, minus.loyalty, plus.sorcery_speed), (1, -3, True))
        [shrine] = activated_abilities(SHRINE)
        self.assertEqual((shrine.life, shrine.sorcery_speed), (2, True))
        self.assertTrue(activated_abilities(ONCE)[0].once_per_turn)

    def test_unsupported_costs_or_effects_are_left_out(self):
        for text in ("{4}: Scry 1.", "Sacrifice a creature: Draw a card.", "{1}, {T}: Add {W}{U}."):
            self.assertEqual(activated_abilities(Card(name="x", oracle_text=text)), (), text)


class ActivationTests(unittest.TestCase):
    def test_mind_stone_cannot_pay_for_itself(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(MIND_STONE)]
        self.assertEqual(activation(game, seat, "Mind Stone"), [])
        seat.battlefield.append(Permanent(FOREST))
        [action] = activation(game, seat, "Mind Stone")
        self.assertTrue(action.endswith(": {1}, {T}, Sacrifice this artifact: Draw a card."))

    def test_sacrifice_and_resolve(self):
        game, a, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        seat.battlefield = [Permanent(MIND_STONE), Permanent(FOREST)]
        game._priority_round(seat)
        self.assertEqual(seat.graveyard, [MIND_STONE])
        self.assertEqual(len(seat.hand), 1)
        self.assertTrue(seat.battlefield[0].tapped)
        events = [e["event"] for e in a.events if e["event"] in ("activate", "sacrificed", "resolve")]
        self.assertEqual(events, ["activate", "sacrificed", "resolve"])

    def test_tap_ability_needs_no_summoning_sickness(self):
        game, _, _ = table()
        seat = game.seats[0]
        sorcerer = Permanent(SORCERER, sick=True)
        seat.battlefield = [sorcerer]
        self.assertEqual(activation(game, seat, "Prodigal"), [])
        sorcerer.sick = False
        self.assertEqual(len(activation(game, seat, "Prodigal")), 1)

    def test_instant_speed_on_opponents_turn_with_targets(self):
        game, _, b = table(None, pick(ACTIVATE, "Player: A"))
        game.seats[1].battlefield = [Permanent(SORCERER)]
        game.step = "end"
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].life, 39)
        self.assertTrue(game.seats[1].battlefield[0].tapped)

    def test_loyalty_abilities(self):
        game, _, _ = table(pick(ACTIVATE + "Walker"))
        seat = game.seats[0]
        walker = Permanent(WALKER, loyalty=3)
        seat.battlefield = [walker]
        game.seats[1].battlefield = [Permanent(BEAR)]
        self.assertEqual(len(activation(game, seat, "Walker")), 2)
        game._priority_round(seat)  # activates the first: +1
        self.assertEqual((walker.loyalty, len(seat.hand)), (4, 1))
        self.assertEqual(activation(game, seat, "Walker"), [])  # one loyalty ability per turn
        game.turn += 1
        game.step = "beginning_of_combat"
        self.assertEqual(activation(game, seat, "Walker"), [])  # sorcery speed only

    def test_loyalty_cannot_go_below_zero(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(WALKER, loyalty=2)]
        game.seats[1].battlefield = [Permanent(BEAR)]
        self.assertEqual([a.rsplit(": ", 1)[1] for a in activation(game, seat, "Walker")], ["Draw a card."])

    def test_minus_ability_that_empties_loyalty(self):
        game, _, _ = table(pick(ACTIVATE + "Walker (seat 0, #1): −3", "Bear"))
        seat = game.seats[0]
        seat.battlefield = [Permanent(WALKER, loyalty=3)]
        game.seats[1].battlefield = [Permanent(BEAR)]
        game._priority_round(seat)
        self.assertEqual(game.seats[1].battlefield, [])  # the ability still resolves
        self.assertEqual(seat.graveyard, [WALKER])  # the walker died at 0 loyalty

    def test_pay_life_and_sorcery_speed(self):
        game, _, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        seat.battlefield = [Permanent(SHRINE)] + lands(2)
        game._priority_round(seat)
        self.assertEqual((seat.life, len(seat.hand)), (38, 2))
        seat.life = 1
        for land in seat.battlefield:
            land.tapped = False
        self.assertEqual(activation(game, seat, "Shrine"), [])

    def test_once_each_turn(self):
        game, _, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        seat.battlefield = [Permanent(ONCE)] + lands(3)
        game._priority_round(seat)
        self.assertEqual(seat.life, 41)  # not 43, though there was mana for three

    def test_counterspell_cannot_counter_abilities(self):
        game, _, _ = table(None, pick("Cast"))
        game.seats[1].hand = [COUNTERSPELL]
        game.seats[1].battlefield = lands(2)
        game.seats[0].battlefield = [Permanent(SORCERER)]
        game.seats[0].player.policy = pick(ACTIVATE, "Player: B")
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].life, 39)
        self.assertEqual(game.seats[1].hand, [COUNTERSPELL])


if __name__ == "__main__":
    unittest.main()
