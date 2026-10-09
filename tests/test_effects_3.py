"""Effects of the real cards in issue #72: populate, copies, half life, doubling counters, returns, puts from hand."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, Permanent
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

TOKEN = Card(name="Goblin", type_line="Token Creature — Goblin", power="1", toughness="1", colors=("R",))


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


class PopulateTests(unittest.TestCase):
    def test_horncallers_chant_makes_a_rhino_then_copies_a_token(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [REAL["Horncaller's Chant"]], lands(8)
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(names(a), ["Rhino", "Rhino"])

    def test_coursers_accord_and_the_rhino_has_no_stray_text(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [REAL["Coursers' Accord"]], lands(6)
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(names(a), ["Centaur", "Centaur"])

    def test_populate_with_no_token_does_nothing(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [REAL["Wake the Reflections"]], [Permanent(BEAR), *lands(1)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(names(a), [BEAR.name])


class CopyOfAnotherCreatureTests(unittest.TestCase):
    def test_orthion_copies_another_creature_with_haste_and_sacrifices_it(self):
        game, _ = table3(pick("Activate", "Bear"))
        a = game.seats[0]
        orthion, bear = Permanent(REAL["Orthion, Hero of Lavabrink"]), Permanent(BEAR)
        a.battlefield = [orthion, bear, *lands(2)]
        [action] = [x for x in game._activations(a, True) if "Create a token that's a copy" in x]
        game._perform(a, action)
        run_stack(game)
        tokens = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual(len(tokens), 1)
        self.assertEqual((tokens[0].card.name, game.has_keyword(tokens[0], "haste")), (BEAR.name, True))
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual([p for p in a.battlefield if p.card.type_line.startswith("Token")], [])

    def test_it_cannot_copy_itself(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Orthion, Hero of Lavabrink"]), *lands(2)]
        self.assertEqual([x for x in game._activations(a, True) if "Create a token that's a copy" in x], [])

    def test_the_big_ability_makes_five(self):
        game, _ = table3(pick("Activate: Orthion", "Bear"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(REAL["Orthion, Hero of Lavabrink"]), bear, *lands(9)]
        [action] = [x for x in game._activations(a, True) if "Create five tokens" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in a.battlefield), 5)

    def test_tempestra_makes_a_nonlegendary_copy_for_an_artifact(self):
        game, _ = table3(pick("Activate", "Mighty", "Relic"))
        a = game.seats[0]
        legend = Card(name="Mighty One", type_line="Legendary Creature — Test", power="3", toughness="3")
        relic = Permanent(Card(name="Relic", type_line="Artifact"))
        a.battlefield = [Permanent(REAL["Tempestra, Dame of Games"]), Permanent(legend), relic, *lands(3)]
        [action] = [x for x in game._activations(a, True) if "Create a token that's a copy" in x]
        game._perform(a, action)
        run_stack(game)
        [token] = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertNotIn("Legendary", token.card.type_line)
        self.assertNotIn(relic, a.battlefield)  # sacrificed as the cost


class HalfLifeTests(unittest.TestCase):
    def hit(self, life):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Attack Player: B")), 0))
        a, b, _c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(REAL["Quietus Spike"], attached_to=bear)]
        b.life = life
        game.combat.declare_attackers(a)
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        return b.life

    def test_quietus_spike_halves_their_life_rounded_up(self):
        self.assertEqual(self.hit(41), 41 - 2 - 20)  # the Bear's 2 damage, then half of 39 rounded up (20)
        self.assertEqual(self.hit(10), 10 - 2 - 4)  # half of 8

    def test_peer_into_the_abyss(self):
        game, _ = table3(pick(CAST, "Player: B"))
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Peer into the Abyss"]], lands(7)
        b.library, b.life = [BEAR] * 5, 9
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((len(b.hand), b.life), (3, 4))  # half of 5 rounded up, half of 9 rounded up lost


class DoubleCountersTests(unittest.TestCase):
    def test_tanazir_doubles_the_counters_on_a_creature_and_resizes_the_others(self):
        game, _ = table3()
        a = game.seats[0]
        marked = Permanent(BEAR, counters={"+1/+1": 3})
        tanazir = Permanent(REAL["Tanazir Quandrix"], counters={"+1/+1": 2})
        a.battlefield = [marked]
        game._enter(a, tanazir)
        run_stack(game)
        self.assertEqual(marked.counters, {"+1/+1": 6})  # (the first creature offered)
        small = Permanent(BEAR)
        a.battlefield.append(small)
        for trigger in [t for t in triggered_abilities(tanazir.card) if t.event == "attacks"]:
            game._queue(trigger, tanazir, a)
        run_stack(game)
        self.assertEqual((game.power(small), game.toughness(small)), (game.power(tanazir), game.toughness(tanazir)))

    def test_seismic_tutelage_gives_a_counter_then_doubles_it_each_attack(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Attack Player: B")), 0))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game._enter(a, Permanent(REAL["Seismic Tutelage"], attached_to=bear))
        run_stack(game)
        self.assertEqual(bear.counters, {"+1/+1": 1})
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(bear.counters, {"+1/+1": 2})


class ReturnTests(unittest.TestCase):
    def test_phytotitan_returns_tapped_at_its_owners_next_upkeep(self):
        game, _ = table3()
        a = game.seats[0]
        titan = Permanent(REAL["Phytotitan"])
        a.battlefield = [titan]
        game.destroy(titan)
        run_stack(game)
        self.assertEqual((names(a), len(a.graveyard)), ([], 1))
        game.turn += 1
        game.step = "upkeep"
        game._turn_based_actions(a)
        self.assertEqual(names(a), ["Phytotitan"])
        self.assertTrue(a.battlefield[0].tapped)

    def test_it_does_not_return_in_the_same_turns_upkeep(self):
        game, _ = table3()
        a = game.seats[0]
        titan = Permanent(REAL["Phytotitan"])
        a.battlefield = [titan]
        game.destroy(titan)
        run_stack(game)
        game.step = "upkeep"
        game._turn_based_actions(a)  # still the turn it died
        self.assertEqual(names(a), [])

    def test_sudden_reclamation_returns_a_creature_and_a_land_to_hand(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        land = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
        a.hand, a.battlefield = [REAL["Sudden Reclamation"]], lands(4)
        a.library, a.graveyard = [BEAR, land, land, BEAR, BEAR], []
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.hand), [BEAR.name, "Forest"])
        self.assertEqual(len(a.graveyard), 4 - 2 + 1)  # four milled, two returned, plus the spell

    def test_tomb_fortress_and_port_of_karfell_return_a_creature_to_the_battlefield(self):
        for name, tapped in (("Tomb Fortress", False), ("Port of Karfell", True)):
            game, _ = table3(lambda prompt, options: 0)
            a = game.seats[0]
            fortress = Permanent(REAL[name])
            a.battlefield = [fortress, *lands(7)]
            a.library = [BEAR] * 6
            [action] = [x for x in game._activations(a, True) if "Mill" in x]
            game._perform(a, action)
            run_stack(game)
            self.assertNotIn(fortress, a.battlefield, name)
            [creature] = [p for p in a.battlefield if "Creature" in p.card.type_line]
            self.assertEqual(creature.tapped, tapped, name)


class FlashTests(unittest.TestCase):
    BIG = Card(name="Big One", mana_cost="{3}{G}{G}", type_line="Creature — Test", power="5", toughness="5")

    def test_it_stays_if_you_pay_the_reduced_cost(self):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        a.hand, a.battlefield = [REAL["Flash"], self.BIG], lands(5)
        game.stack.clear()
        game._perform(a, CAST + "Flash")
        run_stack(game)
        self.assertIn("Big One", names(a))
        self.assertEqual(sum(p.tapped for p in a.battlefield), 2 + 3)  # Flash's {1}{U}, then {1}{G}{G}

    def test_it_is_sacrificed_if_you_cannot_pay(self):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        a.hand, a.battlefield = [REAL["Flash"], self.BIG], lands(2)
        game._perform(a, CAST + "Flash")
        run_stack(game)
        self.assertEqual((names(a), [c.name for c in a.graveyard]), ([], ["Big One", "Flash"]))


class LifeOfThePartyTests(unittest.TestCase):
    CARD = REAL["Life of the Party"]

    def test_it_gets_plus_x_when_it_attacks(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Attack Player: B")), 0))
        a = game.seats[0]
        party = Permanent(self.CARD)
        party.sick = False
        a.battlefield = [party, Permanent(BEAR), Permanent(BEAR)]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(game.power(party), 0 + 3)

    def test_each_opponent_gets_a_goaded_copy_but_a_token_does_not_trigger_it_again(self):
        game, _ = table3()
        a, b, c = game.seats
        game._enter(a, Permanent(self.CARD))
        run_stack(game)
        copies = [p for s in (b, c) for p in s.battlefield]
        self.assertEqual(len(copies), 2)
        self.assertTrue(all(game.goader_of(p) is a for p in copies))
        self.assertEqual(len(a.battlefield), 1)  # the copies' own enters triggers did nothing more


class SoulgorgerOrggTests(unittest.TestCase):
    def test_lose_all_but_one_and_gain_it_back_when_it_leaves(self):
        game, _ = table3()
        a = game.seats[0]
        orgg = Permanent(REAL["Soulgorger Orgg"])
        game._enter(a, orgg)
        run_stack(game)
        self.assertEqual(a.life, 1)
        a.life = 5  # gained and lost meanwhile: it gains what it made you lose
        game.destroy(orgg)
        run_stack(game)
        self.assertEqual(a.life, 5 + 39)
