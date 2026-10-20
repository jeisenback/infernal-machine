"""Watch qualifiers, cast qualifiers, draw-step, opponent-turn and conditional triggers of the real cards in issue #71."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.game import Permanent, StackItem
from tests.real import REAL
from tests.helpers import BEAR, run_stack, table3


def creature(name="Creature", power=2, toughness=2, colors=()):
    return Card(name=name, type_line="Creature — Test", power=str(power), toughness=str(toughness), colors=colors)


class QualifiedWatchTests(unittest.TestCase):
    def test_a_creature_with_power_four_or_greater_entering_draws_a_card(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield, a.library = [Permanent(REAL["Kiora, Behemoth Beckoner"])], [BEAR] * 5
        for entering, seat in ((creature(power=3), a), (creature(power=4), b), (creature(power=4), a), (creature(power=6), a)):
            game._enter(seat, Permanent(entering))
        run_stack(game)
        self.assertEqual(len(a.hand), 2)  # the 4- and the 6-power ones of mine, not the 3 or the opponent's

    def test_a_creature_with_toughness_four_or_greater_dying_drains(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Kheru Bloodsucker"])]
        small, big = Permanent(creature(toughness=3)), Permanent(creature(toughness=5))
        a.battlefield += [small, big]
        game.destroy(small)
        run_stack(game)
        self.assertEqual((a.life, b.life), (40, 40))
        game.destroy(big)
        run_stack(game)
        self.assertEqual((a.life, b.life), (42, 38))

    def test_a_creature_with_a_counter_dying_draws_a_card(self):
        for name in ("Skyclave Shadowcat", "Meltstrider Eulogist"):
            game, _ = table3()
            a = game.seats[0]
            a.battlefield, a.library = [Permanent(REAL[name])], [BEAR] * 3
            plain, marked = Permanent(BEAR), Permanent(BEAR, counters={"+1/+1": 1})
            a.battlefield += [plain, marked]
            game.destroy(plain)
            run_stack(game)
            self.assertEqual(len(a.hand), 0, name)
            game.destroy(marked)
            run_stack(game)
            self.assertEqual(len(a.hand), 1, name)

    def test_raid_bombardment_hits_what_a_small_creature_attacks(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Attack Player: B")), 0))
        a, b, _c = game.seats
        small, big = Permanent(creature(power=2)), Permanent(creature(power=3))
        a.battlefield = [Permanent(REAL["Raid Bombardment"]), small, big]
        big.tapped = True
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(b.life, 39)
        big.tapped = False
        small.tapped = True
        game.combat.attacks = []
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(b.life, 39)  # the 3-power one is too big


class CastQualifierTests(unittest.TestCase):
    MULTI = Card(name="Gold Spell", mana_cost="{W}{B}", cmc=2.0, type_line="Instant", colors=("W", "B"), oracle_text="Draw a card.")
    MONO = Card(name="Plain Spell", mana_cost="{W}", cmc=1.0, type_line="Instant", colors=("W",), oracle_text="Draw a card.")

    def cast(self, game, seat, card):
        seat.cast_log.append((game.turn, card))
        game._observe("cast", card, seat, spell=StackItem(card, seat, []))
        run_stack(game)

    def test_multicolored_spells_only(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield, a.library = [Permanent(REAL["Tome of the Guildpact"]), Permanent(REAL["Mage Tower Referee"])], [BEAR] * 3
        self.cast(game, a, self.MONO)
        self.assertEqual((len(a.hand), a.battlefield[1].counters), (0, {}))
        self.cast(game, a, self.MULTI)
        self.assertEqual((len(a.hand), a.battlefield[1].counters), (1, {"+1/+1": 1}))
        self.cast(game, b, self.MULTI)  # an opponent's
        self.assertEqual(len(a.hand), 1)

    def test_mana_cannons_deals_one_damage_for_each_color(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Player: B")), 0))
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Mana Cannons"])]
        self.cast(game, a, self.MULTI)
        self.assertEqual(b.life, 38)

    def test_aven_shrine_gains_life_for_the_cards_with_the_same_name(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Aven Shrine"])]
        a.graveyard, b.graveyard = [self.MONO, BEAR], [self.MONO]
        self.cast(game, b, self.MONO)
        self.assertEqual((a.life, b.life), (40, 42))  # the caster gains 2: one in each graveyard
        self.cast(game, b, self.MULTI)
        self.assertEqual(b.life, 42)


class DrawStepTests(unittest.TestCase):
    def draw_step(self, game, seat):
        game.step = "draw"
        game.turn = 5
        game._turn_based_actions(seat)
        run_stack(game)

    def test_well_of_ideas_draws_two_for_you_and_one_for_each_other_player(self):
        game, _ = table3()
        a, b, c = game.seats
        for seat in game.seats:
            seat.library = [BEAR] * 9
        a.battlefield = [Permanent(REAL["Well of Ideas"])]
        self.draw_step(game, a)
        self.assertEqual((len(a.hand), len(b.hand), len(c.hand)), (1 + 2, 0, 0))
        a.hand = []
        self.draw_step(game, b)
        self.assertEqual((len(a.hand), len(b.hand), len(c.hand)), (0, 2, 0))  # b draws for the turn and the Well gives b another

    def test_overbeing_of_myth_is_as_big_as_your_hand_and_draws_extra(self):
        game, _ = table3()
        a = game.seats[0]
        overbeing = Permanent(REAL["Overbeing of Myth"])
        a.battlefield, a.library, a.hand = [overbeing], [BEAR] * 9, [BEAR] * 2
        self.assertEqual((game.power(overbeing), game.toughness(overbeing)), (2, 2))
        self.draw_step(game, a)
        self.assertEqual((len(a.hand), game.power(overbeing)), (2 + 1 + 1, 4))

    def test_midnight_oil_draws_extra_loses_counters_and_limits_the_hand(self):
        game, _ = table3()
        a = game.seats[0]
        oil = Permanent(REAL["Midnight Oil"], counters={"hour": 7})
        a.battlefield, a.library = [oil], [BEAR] * 9
        self.draw_step(game, a)
        self.assertEqual((len(a.hand), oil.counters), (2, {"hour": 5}))
        a.hand = [BEAR] * 9
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual(len(a.hand), 5)  # the maximum hand size is the number of hour counters
        oil.counters = {}
        a.hand = [BEAR] * 3
        game._turn_based_actions(a)
        self.assertEqual(len(a.hand), 0)


class OpponentTurnTests(unittest.TestCase):
    def step(self, game, seat, name):
        game.step = name
        game._turn_based_actions(seat)
        run_stack(game)

    def test_predatory_advantage_only_if_that_player_cast_no_creature_spell(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(REAL["Predatory Advantage"])]
        b.cast_log.append((game.turn, BEAR))
        self.step(game, b, "end")
        self.assertEqual(len(a.battlefield), 1)  # b cast a creature spell
        self.step(game, c, "end")
        self.assertEqual([p.card.name for p in a.battlefield], ["Predatory Advantage", "Lizard"])
        self.step(game, a, "end")  # not an opponent's end step
        self.assertEqual(len(a.battlefield), 2)

    def test_price_of_knowledge_hurts_by_the_cards_in_their_hand(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Price of Knowledge"])]
        b.hand = [BEAR] * 5
        self.step(game, b, "upkeep")
        self.assertEqual(b.life, 35)
        self.step(game, a, "upkeep")
        self.assertEqual(a.life, 40)
        b.hand = [BEAR] * 9
        game.step = "cleanup"
        game._turn_based_actions(b)
        self.assertEqual(len(b.hand), 9)  # players have no maximum hand size

    def test_viseling_hurts_by_the_cards_beyond_four(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(REAL["Viseling"])]
        b.hand, c.hand = [BEAR] * 7, [BEAR] * 3
        self.step(game, b, "upkeep")
        self.step(game, c, "upkeep")
        self.assertEqual((b.life, c.life), (37, 40))


class ConditionalTriggerTests(unittest.TestCase):
    def hit(self, game, attacker, victim):
        game.combat.attacks = [Attack(attacker, game.seats[0], victim)]
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)

    def test_lone_revenant_only_when_you_control_no_other_creatures(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, _c = game.seats
        revenant = Permanent(REAL["Lone Revenant"])
        a.battlefield, a.library = [revenant, Permanent(BEAR)], [BEAR] * 6
        self.hit(game, revenant, b)
        self.assertEqual(len(a.hand), 0)
        a.battlefield = [revenant]
        self.hit(game, revenant, b)
        self.assertEqual(len(a.hand), 1)

    def test_mangara_needs_two_or_more_attackers_aimed_at_you(self):
        game, _ = table3(None, lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Attack Player: A")), 0))
        a, b, c = game.seats
        a.battlefield, a.library = [Permanent(REAL["Mangara, the Diplomat"])], [BEAR] * 3
        b.battlefield = [Permanent(BEAR)]
        game.combat.declare_attackers(b)
        run_stack(game)
        self.assertEqual(len(a.hand), 0)  # one attacker
        b.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        game.combat.attacks = []
        game.combat.declare_attackers(b)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)
        game.combat.attacks = []
        game.combat.declare_attackers(c)  # c has no creatures: no attack at all
        run_stack(game)
        self.assertEqual(len(a.hand), 1)
