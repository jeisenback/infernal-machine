"""Rules text of issue #81 that was still unsupported: counters, mass effects, charm and command modes, cost reductions,
combat restrictions and a few replacement effects.

The lines are the issue's own; a card's other lines are not written here.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import spell_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIRD, creature, lands, OGRE, pick, run_stack, script, table, table3

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
RELIC = Card(name="Relic", type_line="Artifact", mana_cost="{1}", cmc=1.0)
SHRINE = Card(name="Shrine", type_line="Enchantment", mana_cost="{2}", cmc=2.0)
GEM = Card(name="Gem", type_line="Artifact", mana_cost="{4}", cmc=4.0)
WALKER = Card(name="Walker", type_line="Legendary Planeswalker — Test", loyalty="4")


def supported(test, card):
    test.assertEqual(unsupported_lines(card), [], card.oracle_text)


def spell(text, name="Spell", type_line="Sorcery", mana_cost="{1}", **fields):
    return Card(name=name, mana_cost=mana_cost, type_line=type_line, oracle_text=text, **fields)


def caster(*answers):
    """A policy that casts once when it first gets priority, passes after that, and answers every other prompt in turn."""
    queue, cast_once = iter(answers), []

    def policy(prompt, options):
        if prompt.startswith("Priority"):
            if cast_once:
                return options.index("Pass")
            cast_once.append(True)
            return pick(CAST)(prompt, options)
        return pick(next(queue, "Pass"))(prompt, options)
    return policy


def cast(card, *answers, setup=None, hand_extra=()):
    """The first player casts `card` (answering the prompts that follow) and the stack resolves."""
    game, _ = table3(caster(*answers))
    a = game.seats[0]
    a.hand = [card, *hand_extra]
    a.battlefield = lands(8)
    if setup:
        setup(game, a, *game.seats[1:])
    game._priority_round(a)
    run_stack(game)
    return game, a


def on_battlefield(seat, name):
    return [p for p in seat.battlefield if p.card.name == name]


class CounterUnlessPaysTests(unittest.TestCase):
    TEXT = "Counter target spell unless its controller pays {2}."

    def test_parse(self):
        self.assertEqual(spell_effects(spell(self.TEXT, type_line="Instant"))[0].unless, "{2}")
        self.assertEqual(spell_effects(spell("Counter target artifact or enchantment spell.", type_line="Instant"))[0].target,
                         "artifact or enchantment spell")
        self.assertEqual(spell_effects(spell("Counter target noncreature spell unless its controller pays {3}.",
                                             type_line="Instant"))[0].unless, "{3}")

    def counter_a_spell(self, pays):
        game, _ = table3(script(CAST), pick("Pay" if pays else "Don't"))
        a, b, _ = game.seats
        a.hand = [spell(self.TEXT, "Quash", "Instant")]
        a.battlefield = lands(2)
        b.battlefield = lands(3)
        shock = spell("You gain 3 life.", "Gain", "Instant", "{1}")
        b.hand = [shock]
        # the second player casts first; then the first player counters it
        game.active = 1
        game._perform(b, CAST + "Gain")
        game.active = 0
        game._perform(a, CAST + "Quash")
        run_stack(game)
        return game, b

    def test_it_is_countered_when_the_controller_does_not_pay(self):
        game, b = self.counter_a_spell(False)
        self.assertEqual(b.life, 40)

    def test_it_resolves_when_the_controller_pays(self):
        game, b = self.counter_a_spell(True)
        self.assertEqual(b.life, 43)


class TargetKindTests(unittest.TestCase):
    def test_artifact_enchantment_or_planeswalker(self):
        fracture = spell("Destroy target artifact, enchantment, or planeswalker.")
        supported(self, fracture)
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(RELIC), Permanent(SHRINE), Permanent(WALKER, loyalty=4), Permanent(OGRE)]
        self.assertEqual(len(game.target_options("artifact, enchantment, or planeswalker", a)), 3)

    def test_exactly_six_targets(self):
        gale = spell("Return six target nonland permanents to their owners' hands.")
        supported(self, gale)
        effects = spell_effects(gale)
        self.assertEqual(len(effects), 6)
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(BEAR)] * 5
        self.assertFalse(game._targets_exist(a, effects))  # only five to choose from
        b.battlefield = [Permanent(BEAR) for _ in range(6)]
        self.assertTrue(game._targets_exist(a, effects))

    def test_a_creature_with_mana_value_x(self):
        melody = spell("Gain control of target creature with mana value X.", mana_cost="{X}{U}{U}")
        supported(self, melody)
        dear = Card(name="Dear", mana_cost="{3}", cmc=3.0, type_line="Creature — Test", power="3", toughness="3")
        cheap = Card(name="Cheap", mana_cost="{1}", cmc=1.0, type_line="Creature — Test", power="1", toughness="1")

        def setup(game, a, b, c):
            b.battlefield = [Permanent(cheap), Permanent(dear)]
        game, a = cast(melody, "3", "Dear", setup=setup)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], ["Dear"])

    def test_non_pilot_style_kinds_stay_working(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR), Permanent(RELIC)]
        self.assertEqual(len(game.target_options("noncreature, nonland permanent", a)), 1)


class PumpAndFightTests(unittest.TestCase):
    def test_gets_x_and_gains_hexproof_and_indestructible(self):
        stand = spell("Target creature you control gets +X/+X and gains hexproof and indestructible until end of turn.",
                      mana_cost="{X}{W}", type_line="Instant")
        supported(self, stand)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR)]
        game, a = cast(stand, "2", "Bear", setup=setup)
        bear = on_battlefield(a, "Bear")[0]
        self.assertEqual((game.power(bear), game.toughness(bear), game.has_keyword(bear, "hexproof"),
                          game.has_keyword(bear, "indestructible")), (4, 4, True, True))

    def test_pump_then_fight_up_to_one_creature(self):
        might = spell("Target creature you control gets +X/+X until end of turn. Then it fights up to one target creature you "
                      "don't control.", mana_cost="{X}{G}")
        supported(self, might)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR)]
            b.battlefield = [Permanent(OGRE)]
        game, a = cast(might, "2", "Bear", "Ogre", setup=setup)
        self.assertEqual(on_battlefield(game.seats[1], "Ogre"), [])  # the 4/4 Bear kills the 3/3 Ogre
        self.assertEqual(on_battlefield(a, "Bear")[0].damage, 3)

    def test_the_fight_may_be_left_out(self):
        might = spell("Target creature you control gets +X/+X until end of turn. Then it fights up to one target creature you "
                      "don't control.", mana_cost="{X}{G}")

        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR)]
            b.battlefield = [Permanent(OGRE)]
        game, a = cast(might, "1", "Bear", "No target", setup=setup)
        self.assertEqual(len(on_battlefield(game.seats[1], "Ogre")), 1)

    def test_a_fight_with_nothing_pumped_before_it_is_not_understood(self):
        self.assertIsNone(spell_effects(spell("Then it fights up to one target creature you don't control.")))


class CountersAndLibraryTests(unittest.TestCase):
    def test_proliferate_x_times(self):
        algorithm = spell("Proliferate X times.", mana_cost="{X}{U}")
        supported(self, algorithm)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR, counters={"+1/+1": 1})]
        game, a = cast(algorithm, "3", "Bear", "Bear", "Bear", setup=setup)
        self.assertEqual(on_battlefield(a, "Bear")[0].counters, {"+1/+1": 4})

    def test_look_at_seven_take_two(self):
        dig = spell("Look at the top seven cards of your library. Put two of them into your hand and the rest on the bottom of "
                    "your library in any order.", type_line="Instant")
        supported(self, dig)

        def setup(game, a, b, c):
            a.library = [RELIC, SHRINE, GEM, BEAR, OGRE, BIRD, FOREST, FOREST, FOREST]
        game, a = cast(dig, "Gem", "Relic", setup=setup)
        self.assertEqual(sorted(c.name for c in a.hand), ["Gem", "Relic"])
        self.assertEqual([c.name for c in a.library[:2]], ["Forest", "Forest"])  # the ones below the seven stay on top
        self.assertEqual(len(a.library), 7)

    def test_x_cards_plus_one_for_each_commander_cast(self):
        insight = spell("Target player draws X cards plus an additional card for each time they've cast a commander from the "
                        "command zone this game.", mana_cost="{X}{U}", type_line="Instant")
        supported(self, insight)

        def setup(game, a, b, c):
            a.commander_casts = {"Omnath": 2}
        game, a = cast(insight, "1", "Player: A", setup=setup)
        self.assertEqual(len(a.hand), 3)


class MassEffectTests(unittest.TestCase):
    def test_culling_ritual_destroys_cheap_permanents_and_adds_mana(self):
        ritual = spell("Destroy each nonland permanent with mana value 2 or less. Add {B} or {G} for each permanent destroyed "
                       "this way.")
        supported(self, ritual)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(RELIC)]
            b.battlefield = [Permanent(SHRINE), Permanent(GEM), Permanent(FOREST)]
        game, a = cast(ritual, setup=setup)
        self.assertEqual((on_battlefield(a, "Relic"), [p.card.name for p in game.seats[1].battlefield]), ([], ["Gem", "Forest"]))
        self.assertEqual([sorted(unit) for unit in a.mana_pool], [["B", "G"], ["B", "G"]])

    def test_mana_geyser_counts_tapped_lands_of_opponents(self):
        geyser = spell("Add {R} for each tapped land your opponents control.")
        supported(self, geyser)

        def setup(game, a, b, c):
            b.battlefield = [Permanent(FOREST, tapped=True), Permanent(FOREST)]
            c.battlefield = [Permanent(FOREST, tapped=True)]
        game, a = cast(geyser, setup=setup)
        self.assertEqual(len(a.mana_pool), 2)

    def test_biomass_mutation_sets_base_power_and_toughness(self):
        mutation = spell("Creatures you control have base power and toughness X/X until end of turn.", mana_cost="{X}{G}",
                         type_line="Instant")
        supported(self, mutation)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR), Permanent(OGRE)]
            b.battlefield = [Permanent(BEAR)]
        game, a = cast(mutation, "5", setup=setup)
        self.assertEqual([(game.power(p), game.toughness(p)) for p in a.battlefield if "Creature" in p.card.type_line], [(5, 5), (5, 5)])
        self.assertEqual(game.power(game.seats[1].battlefield[0]), 2)

    def test_wave_of_reckoning_every_creature_hurts_itself(self):
        wave = spell("Each creature deals damage to itself equal to its power.", mana_cost="{4}{W}{W}")
        supported(self, wave)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR), Permanent(OGRE)]
            b.battlefield = [Permanent(creature("Wall", 0, 4))]
        game, a = cast(wave, setup=setup)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], [])  # a 3/3 with 3 damage dies too
        self.assertEqual(len(game.seats[1].battlefield), 1)

    def test_winds_of_rath_spares_enchanted_creatures(self):
        winds = spell("Destroy all creatures that aren't enchanted. They can't be regenerated.", mana_cost="{3}{W}")
        supported(self, winds)
        aura = Card(name="Blessing", type_line="Enchantment — Aura", oracle_text="Enchant creature")

        def setup(game, a, b, c):
            ogre = Permanent(OGRE)
            a.battlefield += [Permanent(BEAR), ogre, Permanent(aura, attached_to=ogre)]
        game, a = cast(winds, setup=setup)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name in ("Bear", "Ogre")), ["Ogre"])

    def test_volcanic_torrent_hits_opponents_creatures_and_planeswalkers(self):
        torrent = spell("CARDNAME deals X damage to each creature and planeswalker your opponents control, where X is the number "
                        "of spells you've cast this turn.", mana_cost="{3}{R}")
        supported(self, torrent)

        def setup(game, a, b, c):
            a.cast_log.append((game.turn, torrent))  # one spell already cast this turn (and this one makes two)
            a.battlefield += [Permanent(BEAR)]
            b.battlefield = [Permanent(BEAR), Permanent(WALKER, loyalty=4)]
        game, a = cast(torrent, setup=setup)
        self.assertEqual(len(on_battlefield(a, "Bear")), 1)
        self.assertEqual(game.seats[1].battlefield, [b for b in game.seats[1].battlefield if b.card.name == "Walker"])
        self.assertEqual(game.seats[1].battlefield[0].loyalty, 2)


class DamageModesTests(unittest.TestCase):
    def test_one_or_two_targets(self):
        charm = spell("CARDNAME deals 1 damage to each of one or two targets.", type_line="Instant")
        supported(self, charm)
        game, a = cast(charm, "Player: B", "Player: C")
        self.assertEqual((game.seats[1].life, game.seats[2].life), (39, 39))

    def test_the_second_target_may_be_left_out(self):
        charm = spell("CARDNAME deals 1 damage to each of one or two targets.", type_line="Instant")
        game, a = cast(charm, "Player: B", "No target")
        self.assertEqual((game.seats[1].life, game.seats[2].life), (39, 40))

    def test_six_damage_to_each_of_up_to_two_creatures_and_or_planeswalkers(self):
        salvo = spell("CARDNAME deals 6 damage to each of up to two target creatures and/or planeswalkers.", type_line="Instant")
        supported(self, salvo)

        def setup(game, a, b, c):
            b.battlefield = [Permanent(OGRE), Permanent(WALKER, loyalty=4), Permanent(BEAR)]
        game, a = cast(salvo, "Ogre", "Walker", setup=setup)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Bear"])


class CommandModeTests(unittest.TestCase):
    def test_draw_two_then_discard_two(self):
        command = spell("Target player draws two cards, then discards two cards.")
        supported(self, command)

        def setup(game, a, b, c):
            a.library = [RELIC, SHRINE, GEM] + a.library
        game, a = cast(command, "Player: A", "Relic", "Shrine", setup=setup)
        self.assertEqual(len(a.hand), 0)
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Relic", "Shrine", "Spell"])  # and the sorcery itself

    def test_mill_three_then_return_a_land(self):
        command = spell("Target player mills three cards, then you return a land card from your graveyard to your hand.")
        supported(self, command)

        def setup(game, a, b, c):
            a.graveyard = [FOREST]
        game, a = cast(command, "Player: B", setup=setup)
        self.assertEqual(([c.name for c in a.hand], len(game.seats[1].graveyard)), (["Forest"], 3))

    def test_each_opponent_sacrifices_a_nontoken_artifact(self):
        charm = spell("Each opponent sacrifices a nontoken artifact of their choice.", type_line="Instant")
        supported(self, charm)
        treasure = Card(name="Treasure", type_line="Token Artifact — Treasure")

        def setup(game, a, b, c):
            b.battlefield = [Permanent(treasure), Permanent(RELIC)]
            c.battlefield = [Permanent(treasure)]
        game, a = cast(charm, setup=setup)
        self.assertEqual(([p.card.name for p in game.seats[1].battlefield], [p.card.name for p in game.seats[2].battlefield]),
                         (["Treasure"], ["Treasure"]))

    def test_you_may_sacrifice_a_permanent_to_draw_two(self):
        charm = spell("You may sacrifice a permanent. If you do, draw two cards.", type_line="Instant")
        supported(self, charm)

        def setup(game, a, b, c):
            a.battlefield += [Permanent(RELIC)]
        game, a = cast(charm, "Yes", "Relic", setup=setup)
        self.assertEqual((len(a.hand), on_battlefield(a, "Relic")), (2, []))

    def test_declining_the_sacrifice_draws_nothing(self):
        charm = spell("You may sacrifice a permanent. If you do, draw two cards.", type_line="Instant")

        def setup(game, a, b, c):
            a.battlefield += [Permanent(RELIC)]
        game, a = cast(charm, "No", setup=setup)
        self.assertEqual((len(a.hand), len(on_battlefield(a, "Relic"))), (0, 1))


class SacrificeXTests(unittest.TestCase):
    def bargain(self):
        return Card(name="Bargain", mana_cost="{X}{B}{B}", type_line="Sorcery",
                    oracle_text="As an additional cost to cast this spell, sacrifice X creatures.\nDestroy X target nonland permanents.")

    def test_parse(self):
        supported(self, self.bargain())

    def test_sacrifice_x_creatures_and_destroy_x_permanents(self):
        def setup(game, a, b, c):
            a.battlefield += [Permanent(BEAR), Permanent(OGRE), Permanent(BIRD)]
            b.battlefield = [Permanent(GEM), Permanent(RELIC), Permanent(SHRINE)]
        game, a = cast(self.bargain(), "2", "Gem", "Shrine", "Bear", "Ogre", setup=setup)
        self.assertEqual(([p.card.name for p in a.battlefield if "Creature" in p.card.type_line],
                          [p.card.name for p in game.seats[1].battlefield]), (["Bird"], ["Relic"]))

    def test_x_is_limited_by_the_creatures_you_can_sacrifice(self):
        seen = []

        def policy(prompt, options):
            if prompt.startswith("Choose X"):
                seen.append(list(options))
            return pick(CAST)(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        a.hand = [self.bargain()]
        a.battlefield = lands(6) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(GEM), Permanent(RELIC), Permanent(SHRINE)]
        game._priority_round(a)
        self.assertEqual(seen[0], ["0", "1"])

    def test_open_the_way_x_is_at_most_the_number_of_players(self):
        way = Card(name="Way", mana_cost="{X}{G}", type_line="Sorcery",
                   oracle_text="X can't be greater than the number of players in the game.\nYou gain 1 life.")
        supported(self, way)
        seen = []

        def policy(prompt, options):
            if prompt.startswith("Choose X"):
                seen.append(list(options))
            return pick(CAST)(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        a.hand = [way]
        a.battlefield = lands(8)
        game._priority_round(a)
        self.assertEqual(seen[0], ["0", "1", "2", "3"])  # a table of three


class CostReductionTests(unittest.TestCase):
    def cost(self, card, setup=None):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = []
        if setup:
            setup(game, a)
        return game.cost_reduction(a, card)

    def test_mortality_spear_costs_two_less_after_gaining_life(self):
        spear = spell("This spell costs {2} less to cast if you gained life this turn.\nDestroy target creature.",
                      mana_cost="{2}{B}{G}", type_line="Instant")
        supported(self, spear)
        self.assertEqual(self.cost(spear), 0)
        self.assertEqual(self.cost(spear, lambda game, a: game.change_life(a, 1)), 2)

    def test_volcanic_salvo_costs_x_less_for_the_total_power(self):
        salvo = spell("This spell costs {X} less to cast, where X is the total power of creatures you control.", mana_cost="{5}{R}{R}",
                      type_line="Instant")
        supported(self, salvo)
        self.assertEqual(self.cost(salvo, lambda game, a: a.battlefield.extend([Permanent(BEAR), Permanent(OGRE)])), 5)

    def test_aura_spells_cost_one_less(self):
        envoy = Card(name="Envoy", type_line="Creature — Test", power="1", toughness="1",
                     oracle_text="Aura spells you cast cost {1} less to cast.")
        supported(self, envoy)
        aura = Card(name="Blessing", mana_cost="{1}{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature")
        self.assertEqual(self.cost(aura, lambda game, a: a.battlefield.append(Permanent(envoy))), 1)
        self.assertEqual(self.cost(spell("Draw a card."), lambda game, a: a.battlefield.append(Permanent(envoy))), 0)

    def test_spells_that_target_a_creature_cost_two_less(self):
        killian = Card(name="Killian", type_line="Creature — Test", power="2", toughness="2",
                       oracle_text="Spells you cast that target a creature cost {2} less to cast.")
        supported(self, killian)
        kill = spell("Destroy target creature.", mana_cost="{2}{B}")
        draw = spell("Draw a card.", mana_cost="{2}{U}")
        aura = Card(name="Blessing", mana_cost="{1}{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature")
        put = lambda game, a: a.battlefield.append(Permanent(killian))
        self.assertEqual((self.cost(kill, put), self.cost(draw, put), self.cost(aura, put)), (2, 0, 2))

    def test_enchantment_spells_have_affinity_for_auras(self):
        ear = Card(name="Pearl-Ear", type_line="Creature — Test", power="1", toughness="1",
                   oracle_text="Enchantment spells you cast have affinity for Auras.")
        supported(self, ear)
        aura = Card(name="Blessing", mana_cost="{1}{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature")

        def setup(game, a):
            a.battlefield.extend([Permanent(ear), Permanent(aura), Permanent(aura)])
        self.assertEqual(self.cost(Card(name="Shrine", mana_cost="{3}", type_line="Enchantment"), setup), 2)
        self.assertEqual(self.cost(Card(name="Relic", mana_cost="{3}", type_line="Artifact"), setup), 0)


class SacrificeCostTests(unittest.TestCase):
    def test_sacrifice_another_creature_or_artifact(self):
        zealot = Card(name="Zealot", mana_cost="{1}", type_line="Creature — Test", power="1", toughness="1",
                      oracle_text="Sacrifice another creature or artifact: Surveil 1.")
        supported(self, zealot)
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(zealot)]
        self.assertFalse([x for x in game.legal_actions(a) if "Sacrifice another" in x])  # nothing else to sacrifice
        a.battlefield.append(Permanent(RELIC))
        self.assertTrue([x for x in game.legal_actions(a) if "Sacrifice another" in x])


class FromTheGraveyardTests(unittest.TestCase):
    def test_flashback_with_a_life_payment(self):
        analysis = Card(name="Analysis", mana_cost="{3}{U}", type_line="Sorcery", oracle_text="Draw two cards.\nFlashback—{1}{U}, Pay 3 life.")
        supported(self, analysis)
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.graveyard = [analysis]
        a.battlefield = [Permanent(Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))) for _ in range(2)]
        game._perform(a, "Cast from graveyard: Analysis")
        run_stack(game)
        self.assertEqual((a.life, len(a.hand), [c.name for c in a.exile]), (37, 2, ["Analysis"]))

    def test_cast_from_the_graveyard_by_paying_another_cost(self):
        guidance = Card(name="Guidance", mana_cost="{4}{W}", type_line="Sorcery", oracle_text="You gain 4 life.\nYou may cast this card from "
                        "your graveyard by paying {2}{W} rather than paying its mana cost.")
        supported(self, guidance)
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [guidance]
        a.battlefield = [Permanent(Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))) for _ in range(3)]
        self.assertIn("Cast from graveyard: Guidance", game.legal_actions(a))
        game._perform(a, "Cast from graveyard: Guidance")
        run_stack(game)
        self.assertEqual((a.life, [c.name for c in a.graveyard]), (44, ["Guidance"]))  # it goes back to the graveyard


class CombatRestrictionTests(unittest.TestCase):
    def attackers(self, attacker, defender_cards, attacker_mana=0):
        game, _, _ = table(lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0)
        a, b = game.seats
        a.battlefield = [Permanent(attacker), *lands(attacker_mana)]
        b.battlefield = defender_cards
        game.combat.declare_attackers(a)
        return game, a, b

    def test_ghostly_prison_taxes_each_attacker(self):
        prison = Card(name="Prison", mana_cost="{2}{W}", type_line="Enchantment", oracle_text="Creatures can't attack you unless their "
                      "controller pays {2} for each creature they control that's attacking you.")
        supported(self, prison)
        game, a, b = self.attackers(BEAR, [Permanent(prison)], attacker_mana=1)
        self.assertEqual(game.combat.attacks, [])  # one mana cannot pay {2}
        game, a, b = self.attackers(BEAR, [Permanent(prison)], attacker_mana=3)
        self.assertEqual(len(game.combat.attacks), 1)
        self.assertEqual(sum(p.tapped for p in a.battlefield if "Land" in p.card.type_line), 2)  # {2} for the one attacker

    def test_inklings_cannot_attack_you(self):
        calligrapher = Card(name="Calligrapher", mana_cost="{2}", type_line="Creature — Test", power="1", toughness="1",
                            oracle_text="Inklings can't attack you or planeswalkers you control.")
        supported(self, calligrapher)
        inkling = Card(name="Inkling", type_line="Token Creature — Inkling", power="1", toughness="1")
        game, a, b = self.attackers(inkling, [Permanent(calligrapher)])
        self.assertEqual(game.combat.attacks, [])
        game, a, b = self.attackers(BEAR, [Permanent(calligrapher)])
        self.assertEqual(len(game.combat.attacks), 1)

    def test_a_creature_enchanted_by_your_aura_cannot_attack_you(self):
        eriette = Card(name="Eriette", mana_cost="{1}{W}{U}", type_line="Legendary Creature — Test", power="1", toughness="1",
                       oracle_text="Each creature that's enchanted by an Aura you control can't attack you or planeswalkers you control.")
        supported(self, eriette)
        aura = Card(name="Blessing", type_line="Enchantment — Aura", oracle_text="Enchant creature")
        game, _, _ = table(lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0)
        a, b = game.seats
        bear, free = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [bear, free]
        b.battlefield = [Permanent(eriette), Permanent(aura, attached_to=bear)]
        game.combat.declare_attackers(a)
        self.assertEqual([x.attacker.card.name for x in game.combat.attacks], ["Ogre"])

    def blocked_by(self, blocker, attacker):
        policy = lambda prompt, options: 1 if prompt.startswith(("Attack", "Block")) and len(options) > 1 else 0
        game, _, _ = table(policy, policy)
        a, b = game.seats
        a.battlefield = [Permanent(attacker)]
        b.battlefield = [Permanent(blocker)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        return bool(game.combat.attacks[0].blockers)

    def test_can_block_only_creatures_with_flying(self):
        borrower = Card(name="Borrower", mana_cost="{1}{U}", type_line="Creature — Test", power="3", toughness="1", oracle_text="Flash\nFlying\n"
                        "This creature can block only creatures with flying.")
        supported(self, borrower)
        self.assertFalse(self.blocked_by(borrower, BEAR))
        self.assertTrue(self.blocked_by(borrower, BIRD))

    def test_weaker_creatures_cannot_block_it(self):
        otter = Card(name="Otter", mana_cost="{1}{U}", type_line="Creature — Test", power="3", toughness="1",
                     oracle_text="Creatures with power less than this creature's power can't block it.")
        supported(self, otter)
        self.assertFalse(self.blocked_by(BEAR, otter))
        self.assertTrue(self.blocked_by(OGRE, otter))


class ReplacementAndStaticTests(unittest.TestCase):
    def test_pest_rescuer_adds_one_to_each_life_gain(self):
        rescuer = Card(name="Rescuer", mana_cost="{1}{W}", type_line="Creature — Test", power="1", toughness="1",
                       oracle_text="If you would gain life, you gain that much life plus 1 instead.")
        supported(self, rescuer)
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(rescuer)]
        game.change_life(a, 3)
        game.change_life(b, 3)
        game.change_life(a, -2)
        self.assertEqual((a.life, b.life), (42, 43))

    def test_haste_while_an_opponent_is_at_ten_or_less_life(self):
        ghast = Card(name="Ghast", mana_cost="{2}{B}", type_line="Creature — Vampire", power="2", toughness="1",
                     oracle_text="This creature has haste as long as an opponent has 10 or less life.")
        supported(self, ghast)
        game, _ = table3()
        a, b, c = game.seats
        permanent = Permanent(ghast)
        a.battlefield = [permanent]
        self.assertFalse(game.has_keyword(permanent, "haste"))
        c.life = 10
        self.assertTrue(game.has_keyword(permanent, "haste"))


class DelayedDrawTests(unittest.TestCase):
    TEXT = ("Counter target spell. Its controller may draw up to two cards at the beginning of the next turn's upkeep.\n"
            "You draw a card at the beginning of the next turn's upkeep.")

    def test_parse(self):
        supported(self, spell(self.TEXT, type_line="Instant"))

    def test_both_players_draw_at_the_next_upkeep(self):
        game, _ = table3(script(CAST), pick("2"))
        a, b, _ = game.seats
        a.hand = [spell(self.TEXT, "Denial", "Instant")]
        a.battlefield = lands(2)
        b.hand = [spell("You gain 1 life.", "Gain", "Instant")]
        b.battlefield = lands(2)
        game.active = 1
        game._perform(b, CAST + "Gain")
        game._perform(a, CAST + "Denial")
        run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand)), (0, 0))  # nothing yet
        game.turn += 1
        game.step = "upkeep"
        game._turn_based_actions(a)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 2))


if __name__ == "__main__":
    unittest.main()
