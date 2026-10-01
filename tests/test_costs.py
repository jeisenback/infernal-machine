import unittest

from infernal_machine.cards import Card
from infernal_machine.client import Narrator
from infernal_machine.effects import (AdditionalCost, AlternativeCost, Draw, IfKicked, ReturnToHand, additional_costs,
                                      alternative_costs, cost_reductions, kicker_cost, spell_effects)
from infernal_machine.game import (CAST, CAST_COMMANDER, COST_PROMPT, KICKER_PROMPT, SACRIFICE_COST_PROMPT, Game,
                                   Permanent, StackItem)
from infernal_machine.report import unsupported_lines
from tests.test_effects import pick, table

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", type_line="Creature — Bear", colors=("G",), power="2",
            toughness="2")
EMERALD = Card(name="Emerald Medallion", mana_cost="{2}", type_line="Artifact",
               oracle_text="Green spells you cast cost {1} less to cast.")
COMMANDER = Card(name="Omnath", mana_cost="{G}", type_line="Legendary Creature — Elemental", colors=("G",),
                 power="1", toughness="1")
ROLLICK = Card(name="Deadly Rollick", mana_cost="{3}{B}", type_line="Instant", colors=("B",),
               oracle_text="If you control a commander, you may cast this spell without paying its mana cost.\n"
                           "Exile target creature.")
FORCE = Card(name="Force of Will", mana_cost="{3}{U}{U}", type_line="Instant", colors=("U",),
             oracle_text="You may pay 1 life and exile a blue card from your hand rather than pay this spell's mana "
                         "cost.\nCounter target spell.")
NEGATION = Card(name="Force of Negation", mana_cost="{1}{U}{U}", type_line="Instant", colors=("U",),
                oracle_text="If it's not your turn, you may exile a blue card from your hand rather than pay this "
                            "spell's mana cost.\nCounter target noncreature spell.")
OPT = Card(name="Opt", mana_cost="{U}", type_line="Instant", colors=("U",), oracle_text="Scry 1.\nDraw a card.")
ROIL = Card(name="Into the Roil", mana_cost="{1}{U}", type_line="Instant", colors=("U",),
            oracle_text="Kicker {1}{U} (You may pay an additional {1}{U} as you cast this spell.)\n"
                        "Return target nonland permanent to its owner's hand. If this spell was kicked, draw a card.")
RITES = Card(name="Village Rites", mana_cost="{B}", type_line="Instant", colors=("B",),
             oracle_text="As an additional cost to cast this spell, sacrifice a creature.\nDraw two cards.")
THRILL = Card(name="Thrill of Possibility", mana_cost="{1}{R}", type_line="Instant", colors=("R",),
              oracle_text="As an additional cost to cast this spell, discard a card.\nDraw two cards.")
BARGAIN = Card(name="Bargain", mana_cost="{B}", type_line="Sorcery", colors=("B",),
               oracle_text="As an additional cost to cast this spell, pay 3 life.\nDraw two cards.")

KAVU = Card(name="Untamed Kavu", mana_cost="{1}{G}", type_line="Creature — Kavu", colors=("G",), power="2",
            toughness="2", oracle_text="Vigilance, trample\nKicker {3} (You may pay an additional {3} as you cast "
            "this spell.)\nIf Untamed Kavu was kicked, it enters with three +1/+1 counters on it.")
JOSU = Card(name="Josu Vess, Lich Knight", mana_cost="{2}{B}{B}", type_line="Legendary Creature — Zombie Knight",
            colors=("B",), power="4", toughness="5",
            oracle_text="Kicker {5}{B}\nMenace\nWhen Josu Vess enters, if it was kicked, create eight 2/2 black "
                        "Zombie Knight creature tokens with menace.")


class ParseTests(unittest.TestCase):
    def test_cost_reductions(self):
        self.assertEqual(cost_reductions(EMERALD), [("G", 1)])
        text = "Instant and sorcery spells you cast cost {1} less to cast."
        self.assertEqual(cost_reductions(Card(name="Baral", oracle_text=text)), [("instant and sorcery", 1)])
        self.assertEqual(cost_reductions(Card(name="Helm", oracle_text="Spells you cast cost {1} less to cast.")),
                         [("spell", 1)])

    def test_alternative_costs(self):
        self.assertEqual(alternative_costs(ROLLICK), [AlternativeCost("Cast without paying its mana cost", commander=True)])
        self.assertEqual(alternative_costs(FORCE), [AlternativeCost("Pay 1 life and exile a blue card", life=1,
                                                                    exile_color="U")])
        self.assertEqual(alternative_costs(NEGATION), [AlternativeCost("Exile a blue card", not_your_turn=True,
                                                                       exile_color="U")])

    def test_additional_costs(self):
        self.assertEqual(additional_costs(RITES), [AdditionalCost(sacrifice="creature")])
        self.assertEqual(additional_costs(THRILL), [AdditionalCost(discard=True)])
        self.assertEqual(additional_costs(BARGAIN), [AdditionalCost(life=3)])

    def test_pay_x_life_is_not_supported(self):
        deluge = Card(name="Toxic Deluge", mana_cost="{2}{B}", type_line="Sorcery", colors=("B",),
                      oracle_text="As an additional cost to cast this spell, pay X life.\n"
                                  "All creatures get -X/-X until end of turn.")
        self.assertEqual(additional_costs(deluge), [])
        self.assertIn("As an additional cost to cast this spell, pay X life.", unsupported_lines(deluge))
        game, _, _ = table()
        game.seats[0].hand = [deluge]
        game.seats[0].battlefield = battlefield(SWAMP, SWAMP, SWAMP)
        game.legal_actions(game.seats[0])  # used to crash adding "X" to a number

    def test_casting_cost_lines_are_not_effects(self):
        self.assertEqual(spell_effects(RITES), [Draw(2)])
        self.assertEqual(kicker_cost(ROIL), "{1}{U}")
        self.assertEqual(spell_effects(ROIL), [ReturnToHand("nonland permanent"), IfKicked(Draw(1))])

    def test_kicked_effects_that_target_are_not_supported(self):
        card = Card(name="Kicked Bolt", type_line="Instant", oracle_text="Kicker {R}\nDraw a card. If this spell was "
                    "kicked, it deals 2 damage to any target.")
        self.assertIsNone(spell_effects(card))

    def test_report(self):
        for card in (EMERALD, ROLLICK, FORCE, ROIL, RITES, THRILL, BARGAIN):
            self.assertEqual(unsupported_lines(card), [], card.name)
        for card in (KAVU, JOSU):
            self.assertEqual(unsupported_lines(card), [], card.name)


def battlefield(*cards):
    return [Permanent(c) for c in cards]


class CostReductionTests(unittest.TestCase):
    def test_medallion_reduces_generic_mana(self):
        game, _, _ = table(pick(CAST + BEAR.name))
        seat = game.seats[0]
        seat.hand = [BEAR]
        seat.battlefield = battlefield(EMERALD, FOREST)
        game._priority_round(seat)
        self.assertIn("Grizzly Bears", [p.card.name for p in seat.battlefield])

    def test_colored_mana_is_not_reduced(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [BEAR]
        seat.battlefield = battlefield(EMERALD, EMERALD, ISLAND)
        self.assertNotIn(CAST + BEAR.name, game.legal_actions(seat))

    def test_other_colors_are_not_reduced(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [ROIL]
        seat.battlefield = battlefield(EMERALD, ISLAND, BEAR)
        self.assertNotIn(CAST + ROIL.name, game.legal_actions(seat))

    def test_commander_tax_is_reduced(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.command_zone, seat.commander_names = [COMMANDER], {COMMANDER.name}
        seat.commander_casts[COMMANDER.name] = 1
        seat.battlefield = battlefield(EMERALD, EMERALD, FOREST)
        self.assertIn(CAST_COMMANDER + COMMANDER.name, game.legal_actions(seat))


class AlternativeCostTests(unittest.TestCase):
    def test_free_with_a_commander(self):
        game, a, _ = table(pick(CAST + ROLLICK.name, "Cast without paying its mana cost", "Grizzly Bears"))
        seat, other = game.seats
        seat.hand = [ROLLICK]
        seat.commander_names = {COMMANDER.name}
        seat.battlefield = battlefield(COMMANDER)
        other.battlefield = battlefield(BEAR)
        game._priority_round(seat)
        self.assertEqual(other.battlefield, [])
        cast = next(e for e in a.events if e["event"] == "cast")
        self.assertEqual(cast["alternative"], "Cast without paying its mana cost")
        self.assertEqual(cast["tapped"], [])

    def test_not_free_without_a_commander(self):
        game, _, _ = table()
        seat, other = game.seats
        seat.hand = [ROLLICK]
        seat.commander_names = {COMMANDER.name}
        other.battlefield = battlefield(BEAR)
        self.assertNotIn(CAST + ROLLICK.name, game.legal_actions(seat))

    def test_choice_offered_when_both_are_payable(self):
        game, a, _ = table(pick(CAST + ROLLICK.name, "Pay {3}{B}", "Grizzly Bears"))
        seat, other = game.seats
        seat.hand = [ROLLICK]
        seat.commander_names = {COMMANDER.name}
        seat.battlefield = battlefield(COMMANDER, SWAMP, SWAMP, SWAMP, SWAMP)
        other.battlefield = battlefield(BEAR)
        game._priority_round(seat)
        prompt = next(options for prompt, options in a.prompts if prompt == COST_PROMPT + ROLLICK.name)
        self.assertEqual(prompt, ["Pay {3}{B}", "Cast without paying its mana cost"])
        self.assertEqual(sum(p.tapped for p in seat.battlefield), 4)

    def test_force_of_will_pays_life_and_exiles_a_blue_card(self):
        game, a, b = table(pick(CAST + BEAR.name), pick(CAST + FORCE.name, "Opt"))
        seat, other = game.seats
        seat.hand = [BEAR]
        seat.battlefield = battlefield(FOREST, FOREST)
        other.hand = [FORCE, OPT, FORCE]
        game._priority_round(seat)
        self.assertEqual(seat.graveyard, [BEAR])
        self.assertEqual(other.life, 39)
        self.assertEqual(other.exile, [OPT])
        self.assertEqual(other.hand, [FORCE])

    def test_force_can_exile_another_force_but_not_itself(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [FORCE]
        game.stack.append(game_item(game, seat))
        self.assertNotIn(CAST + FORCE.name, game.legal_actions(seat))
        seat.hand = [FORCE, FORCE]
        self.assertIn(CAST + FORCE.name, game.legal_actions(seat))

    def test_force_of_negation_only_on_opponents_turn(self):
        game, _, _ = table()
        seat, other = game.seats
        seat.hand, other.hand = [NEGATION, OPT], [NEGATION, OPT]
        game.stack.append(game_item(game, seat))
        self.assertNotIn(CAST + NEGATION.name, game.legal_actions(seat))
        self.assertIn(CAST + NEGATION.name, game.legal_actions(other))


    def test_fierce_guardianship_counters_a_noncreature_spell_for_free(self):
        guardianship = Card(name="Fierce Guardianship", mana_cost="{2}{U}", type_line="Instant", colors=("U",),
                            oracle_text="If you control a commander, you may cast this spell without paying its mana "
                                        "cost.\nCounter target noncreature spell.")
        game, _, _ = table(pick(CAST + OPT.name), pick(CAST + guardianship.name, "Cast without"))
        seat, other = game.seats
        seat.hand, seat.library = [OPT], [BEAR]
        seat.battlefield = battlefield(ISLAND)
        other.hand, other.commander_names = [guardianship], {COMMANDER.name}
        other.battlefield = battlefield(COMMANDER)
        game._priority_round(seat)
        self.assertEqual(seat.hand, [])
        self.assertEqual(seat.graveyard, [OPT])
        self.assertEqual(other.graveyard, [guardianship])

    def test_noncreature_counter_cant_target_a_creature_spell(self):
        game, _, _ = table()
        seat, other = game.seats
        other.hand = [NEGATION, OPT]
        game.stack.append(StackItem(BEAR, seat, []))
        self.assertNotIn(CAST + NEGATION.name, game.legal_actions(other))
        game.stack.append(game_item(game, seat))
        self.assertIn(CAST + NEGATION.name, game.legal_actions(other))


def game_item(game: Game, seat):
    return StackItem(OPT, seat, spell_effects(OPT))


class KickerTests(unittest.TestCase):
    def test_kicked_spell_does_the_extra_effect(self):
        game, a, _ = table(pick(CAST + ROIL.name, "Grizzly Bears", "Yes"))
        seat, other = game.seats
        seat.hand = [ROIL]
        seat.library = [OPT]
        seat.battlefield = battlefield(ISLAND, ISLAND, ISLAND, ISLAND)
        other.battlefield = battlefield(BEAR)
        game._priority_round(seat)
        self.assertEqual(other.hand, [BEAR])
        self.assertEqual(seat.hand, [OPT])
        self.assertTrue(next(e for e in a.events if e["event"] == "cast")["kicked"])

    def test_unkicked_spell_skips_it(self):
        game, _, _ = table(pick(CAST + ROIL.name, "Grizzly Bears", "No"))
        seat, other = game.seats
        seat.hand = [ROIL]
        seat.library = [OPT]
        seat.battlefield = battlefield(ISLAND, ISLAND, ISLAND, ISLAND)
        other.battlefield = battlefield(BEAR)
        game._priority_round(seat)
        self.assertEqual(other.hand, [BEAR])
        self.assertEqual(seat.hand, [])
        self.assertEqual(sum(p.tapped for p in seat.battlefield), 2)

    def test_kicker_not_offered_when_unaffordable(self):
        game, a, _ = table(pick(CAST + ROIL.name, "Grizzly Bears"))
        seat, other = game.seats
        seat.hand = [ROIL]
        seat.battlefield = battlefield(ISLAND, ISLAND)
        other.battlefield = battlefield(BEAR)
        game._priority_round(seat)
        self.assertFalse(any(prompt == KICKER_PROMPT + ROIL.name for prompt, _ in a.prompts))

    def test_kicked_creature_enters_with_counters(self):
        for answer, counters in (("Yes", {"+1/+1": 3}), ("No", {})):
            game, _, _ = table(pick(CAST + KAVU.name, answer))
            seat = game.seats[0]
            seat.hand = [KAVU]
            seat.battlefield = battlefield(*[FOREST] * 5)
            game._priority_round(seat)
            kavu = next(p for p in seat.battlefield if p.card is KAVU)
            self.assertEqual(kavu.counters, counters, answer)
            self.assertEqual(kavu.kicked, answer == "Yes")

    def test_kicked_enters_trigger(self):
        for answer, tokens in (("Yes", 8), ("No", 0)):
            game, _, _ = table(pick(CAST + JOSU.name, answer))
            seat = game.seats[0]
            seat.hand = [JOSU]
            seat.battlefield = battlefield(*[SWAMP] * 10)
            game._priority_round(seat)
            self.assertEqual(sum(p.card.name == "Zombie Knight" for p in seat.battlefield), tokens, answer)


class AdditionalCostTests(unittest.TestCase):
    def test_sacrifice_a_creature(self):
        game, a, _ = table(pick(CAST + RITES.name, "Grizzly Bears"))
        seat = game.seats[0]
        seat.hand = [RITES]
        seat.library = [OPT, OPT]
        seat.battlefield = battlefield(SWAMP, BEAR)
        game._priority_round(seat)
        self.assertEqual(seat.graveyard, [BEAR, RITES])
        self.assertEqual(seat.hand, [OPT, OPT])
        self.assertTrue(any(prompt == SACRIFICE_COST_PROMPT + RITES.name for prompt, _ in a.prompts))

    def test_needs_something_to_sacrifice(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [RITES]
        seat.battlefield = battlefield(SWAMP)
        self.assertNotIn(CAST + RITES.name, game.legal_actions(seat))

    def test_discard_a_card(self):
        game, _, _ = table(pick(CAST + THRILL.name, "Opt"))
        seat = game.seats[0]
        seat.hand = [THRILL]
        seat.battlefield = battlefield(Card(name="Rainbow", type_line="Land", produced_mana=tuple("WUBRG")),
                                       FOREST)
        self.assertNotIn(CAST + THRILL.name, game.legal_actions(seat))
        seat.hand = [THRILL, OPT]
        seat.library = [BEAR, BEAR]
        game._priority_round(seat)
        self.assertEqual(seat.graveyard, [OPT, THRILL])
        self.assertEqual(seat.hand, [BEAR, BEAR])

    def test_pay_life(self):
        game, _, _ = table(pick(CAST + BARGAIN.name))
        seat = game.seats[0]
        seat.hand = [BARGAIN]
        seat.library = [OPT, OPT]
        seat.battlefield = battlefield(SWAMP)
        game._priority_round(seat)
        self.assertEqual(seat.life, 37)
        seat.life, seat.hand = 2, [BARGAIN]
        seat.battlefield = battlefield(SWAMP)
        self.assertNotIn(CAST + BARGAIN.name, game.legal_actions(seat))


class NarrationTests(unittest.TestCase):
    def test_cast_mentions_kicker_and_alternative_cost(self):
        narrator = Narrator()
        line = narrator.narrate({"event": "cast", "seat": 0, "card": "Force of Will", "targets": [], "x": 0,
                                  "alternative": "Pay 1 life and exile a blue card"})
        self.assertIn("(pay 1 life and exile a blue card)", line)
        line = narrator.narrate({"event": "cast", "seat": 0, "card": "Into the Roil", "targets": [], "x": 0,
                                  "kicked": True})
        self.assertIn("Into the Roil kicked", line)


if __name__ == "__main__":
    unittest.main()
