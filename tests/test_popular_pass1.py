"""The first popularity pass: the most played cards still missing a rules line (extra land drops, lands from the graveyard...),
each from the card's own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import rules_statics
from infernal_machine.game import ACTIVATE, CAST, PASS, PLAY_GRAVEYARD, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_lands import spell
from tests.test_effects import BEAR, RAINBOW, SOL_RING, lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_x_targets import script
from tests.test_rules_text_81 import real
from tests.test_triggers_80 import FOREST, PLAINS

EXPLORATION = real("Exploration", "{G}", "Enchantment", "You may play an additional land on each of your turns.")
CRUCIBLE = real("Crucible of Worlds", "{3}", "Artifact", "You may play lands from your graveyard.")
RAMUNAP = real("Ramunap Excavator", "{2}{G}", "Creature — Snake Cleric", "You may play lands from your graveyard.", "2", "3")


def plays(game, seat, prefix=PLAY_LAND):
    return [a.removeprefix(prefix) for a in game.legal_actions(seat) if a.startswith(prefix)]


class LandDropTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table(None)
        self.a, self.b = self.game.seats[0], self.game.seats[1]
        self.a.hand = [FOREST, FOREST, PLAINS]

    def play(self, name):
        self.game._perform(self.a, PLAY_LAND + name)

    def test_one_land_a_turn_without_help(self):
        self.play("Forest")
        self.assertEqual(plays(self.game, self.a), [])

    def test_an_extra_land_drop_allows_a_second_land(self):
        self.a.battlefield.append(Permanent(EXPLORATION))
        self.play("Forest")
        self.assertEqual(plays(self.game, self.a), ["Forest", "Plains"])
        self.play("Forest")
        self.assertEqual(plays(self.game, self.a), [])

    def test_each_extra_land_drop_adds_one(self):
        self.a.battlefield += [Permanent(EXPLORATION), Permanent(EXPLORATION)]
        self.play("Forest")
        self.play("Forest")
        self.assertEqual(plays(self.game, self.a), ["Plains"])
        self.play("Plains")
        self.assertEqual(plays(self.game, self.a), [])

    def test_an_opponents_extra_land_drop_does_not_help(self):
        self.b.battlefield.append(Permanent(EXPLORATION))
        self.play("Forest")
        self.assertEqual(plays(self.game, self.a), [])

    def test_the_drops_reset_each_turn(self):
        self.a.battlefield.append(Permanent(EXPLORATION))
        self.play("Forest")
        self.play("Forest")
        self.a.lands_played = 0
        self.assertEqual(plays(self.game, self.a), ["Plains"])

    def test_it_is_a_fully_playable_card(self):
        self.assertEqual(unsupported_lines(EXPLORATION), [])


class GraveyardLandTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table(None)
        self.a, self.b = self.game.seats[0], self.game.seats[1]
        self.a.graveyard = [FOREST, real("Bear", "{1}{G}", "Creature — Bear", "", "2", "2")]

    def test_a_land_in_the_graveyard_can_be_played(self):
        self.a.battlefield.append(Permanent(CRUCIBLE))
        self.assertEqual(plays(self.game, self.a, PLAY_GRAVEYARD), ["Forest"])
        self.game._perform(self.a, PLAY_GRAVEYARD + "Forest")
        self.assertEqual(([c.name for c in self.a.graveyard], [p.card.name for p in self.a.battlefield], self.a.lands_played),
                         (["Bear"], ["Crucible of Worlds", "Forest"], 1))

    def test_it_uses_the_land_drop(self):
        self.a.battlefield.append(Permanent(CRUCIBLE))
        self.game._perform(self.a, PLAY_GRAVEYARD + "Forest")
        self.assertEqual(plays(self.game, self.a, PLAY_GRAVEYARD), [])

    def test_a_creature_can_give_the_same_permission(self):
        self.a.battlefield.append(Permanent(RAMUNAP))
        self.assertEqual(plays(self.game, self.a, PLAY_GRAVEYARD), ["Forest"])

    def test_nothing_is_offered_without_the_permission(self):
        self.assertEqual(plays(self.game, self.a, PLAY_GRAVEYARD), [])

    def test_an_opponents_permission_does_not_help(self):
        self.b.battlefield.append(Permanent(CRUCIBLE))
        self.assertEqual(plays(self.game, self.a, PLAY_GRAVEYARD), [])

    def test_with_an_extra_drop_two_lands_come_back(self):
        self.a.battlefield += [Permanent(CRUCIBLE), Permanent(EXPLORATION)]
        self.a.graveyard = [FOREST, PLAINS]
        self.game._perform(self.a, PLAY_GRAVEYARD + "Forest")
        self.assertEqual(plays(self.game, self.a, PLAY_GRAVEYARD), ["Plains"])
        self.game._perform(self.a, PLAY_GRAVEYARD + "Plains")
        self.assertEqual(self.a.graveyard, [])

    def test_the_cards_are_fully_playable(self):
        self.assertEqual((unsupported_lines(CRUCIBLE), unsupported_lines(RAMUNAP)), ([], []))


SANGUINE = real("Sanguine Bond", "{3}{B}{B}", "Enchantment", "Whenever you gain life, target opponent loses that much life.")
EXQUISITE = real("Exquisite Blood", "{4}{B}", "Enchantment", "Whenever an opponent loses life, you gain that much life.")
VITO = real("Vito, Thorn of the Dusk Rose", "{2}{B}", "Legendary Creature \u2014 Vampire Cleric",
            "Whenever you gain life, target opponent loses that much life.\n{3}{B}{B}: Creatures you control gain lifelink until end of turn.",
            "1", "3")


class ThatMuchLifeTests(unittest.TestCase):
    def table(self, *answers):
        game, _ = table3(script(*answers))
        return game, *game.seats

    def test_an_opponent_loses_as_much_as_you_gained(self):
        game, a, b, c = self.table("Player: B")
        a.battlefield.append(Permanent(SANGUINE))
        game.change_life(a, 3)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (43, 37, 40))

    def test_the_target_is_the_one_chosen(self):
        game, a, b, c = self.table("Player: C")
        a.battlefield.append(Permanent(SANGUINE))
        game.change_life(a, 5)
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 35))

    def test_it_follows_the_life_actually_gained(self):
        game, a, b, c = self.table("Player: B")
        a.battlefield += [Permanent(SANGUINE), Permanent(real("Boon", "{2}{W}", "Enchantment", "If you would gain life, you gain twice that much life instead."))]
        game.change_life(a, 3)
        run_stack(game)
        self.assertEqual((a.life, b.life), (46, 34))

    def test_losing_life_or_an_opponents_gain_does_nothing(self):
        game, a, b, c = self.table()
        a.battlefield.append(Permanent(SANGUINE))
        game.change_life(a, -3)
        game.change_life(b, 4)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (37, 44, 40))

    def test_a_creature_with_the_same_trigger(self):
        game, a, b, c = self.table("Player: B")
        a.battlefield.append(Permanent(VITO))
        game.change_life(a, 2)
        run_stack(game)
        self.assertEqual(b.life, 38)

    def test_you_gain_as_much_as_an_opponent_lost(self):
        game, a, b, c = self.table()
        a.battlefield.append(Permanent(EXQUISITE))
        game.change_life(b, -4)
        run_stack(game)
        self.assertEqual((a.life, b.life), (44, 36))

    def test_your_own_loss_does_not_count(self):
        game, a, b, c = self.table()
        a.battlefield.append(Permanent(EXQUISITE))
        game.change_life(a, -4)
        run_stack(game)
        self.assertEqual(a.life, 36)

    def test_the_cards_are_fully_playable(self):
        self.assertEqual([unsupported_lines(c) for c in (SANGUINE, VITO, EXQUISITE)], [[], [], []])


MONOLITH = real("Basalt Monolith", "{3}", "Artifact",
                "This artifact doesn't untap during your untap step.\n{T}: Add {C}{C}{C}.\n{3}: Untap this artifact.")
VAULT = real("Mana Vault", "{1}", "Artifact",
             "This artifact doesn't untap during your untap step.\nAt the beginning of your upkeep, you may pay {4}. If you do, untap this "
             "artifact.\nAt the beginning of your draw step, if this artifact is tapped, it deals 1 damage to you.\n{T}: Add {C}{C}{C}.")


def step(game, seat, name):
    game.step = name
    game._turn_based_actions(seat)
    run_stack(game)


class NoUntapTests(unittest.TestCase):
    def test_it_stays_tapped_through_the_untap_step(self):
        game, _, _ = table(None)
        a = game.seats[0]
        monolith = Permanent(MONOLITH, tapped=True)
        sol = Permanent(SOL_RING, tapped=True)
        a.battlefield = [monolith, sol]
        step(game, a, "untap")
        self.assertEqual((monolith.tapped, sol.tapped), (True, False))

    def test_it_untaps_when_something_has_taken_away_its_abilities(self):
        game, _, _ = table(None)
        a = game.seats[0]
        monolith = Permanent(MONOLITH, tapped=True)
        frog = real("Turn to Frog", "{1}{U}", "Enchantment \u2014 Aura", "Enchant creature\nEnchanted creature loses all abilities.")
        a.battlefield = [monolith, Permanent(frog, attached_to=monolith)]
        step(game, a, "untap")
        self.assertFalse(monolith.tapped)

    def test_the_ability_can_untap_it(self):
        game, _, _ = table(pick(ACTIVATE + "Basalt Monolith"))
        a = game.seats[0]
        monolith = Permanent(MONOLITH, tapped=True)
        a.battlefield = [monolith] + lands(3)
        untap = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Untap" in x]
        self.assertEqual(len(untap), 1)
        game._perform(a, untap[0])
        run_stack(game)
        self.assertFalse(monolith.tapped)

    def test_it_cannot_untap_itself_without_the_mana(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(MONOLITH, tapped=True)] + lands(2)
        self.assertEqual([x for x in game.legal_actions(a) if "Untap" in x], [])

    def test_the_upkeep_payment_untaps_a_mana_vault(self):
        game, _, _ = table(pick("Pay {4}"))
        a = game.seats[0]
        vault = Permanent(VAULT, tapped=True)
        a.battlefield = [vault] + lands(4)
        step(game, a, "upkeep")
        self.assertFalse(vault.tapped)

    def test_a_declined_payment_leaves_it_tapped(self):
        game, _, _ = table(pick("Don't pay"))
        a = game.seats[0]
        vault = Permanent(VAULT, tapped=True)
        a.battlefield = [vault] + lands(4)
        step(game, a, "upkeep")
        self.assertTrue(vault.tapped)

    def test_a_tapped_vault_hurts_in_the_draw_step(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(VAULT, tapped=True)]
        step(game, a, "draw")
        self.assertEqual(a.life, 39)

    def test_an_untapped_vault_does_not(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(VAULT)]
        step(game, a, "draw")
        self.assertEqual(a.life, 40)

    def test_the_cards_are_fully_playable(self):
        self.assertEqual((unsupported_lines(MONOLITH), unsupported_lines(VAULT)), ([], []))


DIES = "When Enduring {0} dies, if it was a creature, return it to the battlefield under its owner's control. It's an enchantment. (It's not a creature.)"
TENACITY = real("Enduring Tenacity", "{1}{B}{B}", "Enchantment Creature \u2014 Glimmer",
                "Whenever you gain life, target opponent loses that much life.\n" + DIES.format("Tenacity"), "4", "4")
VITALITY = real("Enduring Vitality", "{1}{G}{G}", "Enchantment Creature \u2014 Elk Glimmer",
                "Vigilance\nCreatures you control have \"{T}: Add one mana of any color.\"\n" + DIES.format("Vitality"), "3", "3")


class EnduringTests(unittest.TestCase):
    def dead(self, card, *answers):
        game, _ = table3(script(*answers))
        a = game.seats[0]
        enduring = Permanent(card)
        a.battlefield = [enduring]
        game.destroy(enduring)
        run_stack(game)
        return game, a

    def test_it_returns_as_an_enchantment_that_is_not_a_creature(self):
        game, a = self.dead(TENACITY)
        self.assertEqual(([p.card.name for p in a.battlefield], a.graveyard), (["Enduring Tenacity"], []))
        back = a.battlefield[0].card
        self.assertEqual((back.type_line, back.power), ("Enchantment", None))

    def test_it_keeps_its_other_abilities(self):
        game, a = self.dead(TENACITY, "Player: B")
        game.change_life(a, 4)
        run_stack(game)
        self.assertEqual(game.seats[1].life, 36)

    def test_destroying_it_again_puts_the_card_in_the_graveyard_for_good(self):
        game, a = self.dead(TENACITY)
        game.destroy(a.battlefield[0])
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], [c.type_line for c in a.graveyard]),
                         ([], ["Enchantment Creature \u2014 Glimmer"]))

    def test_creatures_you_control_can_tap_for_any_color(self):
        game, _ = table3(None)
        a = game.seats[0]
        a.battlefield = [Permanent(VITALITY), Permanent(BEAR)]
        a.battlefield[0].sick = a.battlefield[1].sick = False
        self.assertIsNotNone(game._payment(a, spell("{R}{U}")))

    def test_without_the_card_a_creature_makes_no_mana(self):
        game, _ = table3(None)
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR, sick=False)]
        self.assertIsNone(game._payment(a, spell("{R}")))

    def test_a_summoning_sick_creature_cannot_tap_for_it(self):
        game, _ = table3(None)
        a = game.seats[0]
        a.battlefield = [Permanent(VITALITY, sick=False), Permanent(BEAR, sick=True)]
        self.assertIsNone(game._payment(a, spell("{R}{U}")))

    def test_the_grant_survives_the_card_becoming_an_enchantment(self):
        game, a = self.dead(VITALITY)
        a.battlefield.append(Permanent(BEAR, sick=False))
        self.assertIsNotNone(game._payment(a, spell("{R}")))
        self.assertIsNone(game._payment(a, spell("{R}{U}")))

    def test_the_cards_are_fully_playable(self):
        self.assertEqual((unsupported_lines(TENACITY), unsupported_lines(VITALITY)), ([], []))


LEGEND = real("Legend", "{2}", "Legendary Creature \u2014 Human", "", "2", "2")
SWORD = real("Sword of Eden", "{2}", "Artifact \u2014 Equipment", "Equipped creature gets +10/+0 and has vigilance.\nEquip legendary creature {2}")
REGALIA = real("Regalia", "{2}", "Artifact \u2014 Equipment", "Equipped creature gets +1/+1.\nEquip legendary creature {1}\nEquip {3}")


def equips(game, seat, name):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and name in a and "Equip" in a]


class EquipLegendaryTests(unittest.TestCase):
    def setup(self, card, creatures, n):
        game, _, _ = table(None)
        seat = game.seats[0]
        seat.battlefield = [Permanent(card)] + [Permanent(c) for c in creatures] + lands(n)
        return game, seat

    def test_only_a_legendary_creature_can_be_targeted(self):
        game, seat = self.setup(SWORD, [BEAR, LEGEND], 2)
        self.assertEqual([label for label, _ in game.target_options("legendary creature you control", seat)],
                         ["Legend 2/2 (seat 0, #3)"])

    def test_it_cannot_be_activated_without_a_legendary_creature(self):
        game, seat = self.setup(SWORD, [BEAR], 2)
        self.assertEqual(equips(game, seat, "Sword"), [])

    def test_the_cost_is_paid_in_mana(self):
        game, seat = self.setup(SWORD, [LEGEND], 1)
        self.assertEqual(equips(game, seat, "Sword"), [])
        game, seat = self.setup(SWORD, [LEGEND], 2)
        self.assertEqual(len(equips(game, seat, "Sword")), 1)

    def test_equipping_attaches_it_and_grants_the_bonus(self):
        game, _, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        legend = Permanent(LEGEND)
        seat.battlefield = [Permanent(SWORD), legend] + lands(2)
        game._priority_round(seat)
        self.assertEqual(game.power(legend), 12)

    def test_a_second_plain_equip_line_works_on_any_creature(self):
        game, seat = self.setup(REGALIA, [BEAR], 3)
        self.assertEqual(len(equips(game, seat, "Regalia")), 1)
        game, seat = self.setup(REGALIA, [BEAR], 1)
        self.assertEqual(equips(game, seat, "Regalia"), [])

    def test_with_both_lines_the_legendary_one_is_cheaper(self):
        game, seat = self.setup(REGALIA, [BEAR, LEGEND], 1)
        self.assertEqual(len(equips(game, seat, "Regalia")), 1)
        game, seat = self.setup(REGALIA, [BEAR, LEGEND], 3)
        self.assertEqual(len(equips(game, seat, "Regalia")), 2)

    def test_the_cards_are_fully_playable(self):
        self.assertEqual((unsupported_lines(SWORD), unsupported_lines(REGALIA)), ([], []))


SYNDIC = real("Syndic of Tithes", "{1}{W}", "Creature \u2014 Human Cleric",
              "Extort (Whenever you cast a spell, you may pay {W/B}. If you do, each opponent loses 1 life and you gain that much life.)",
              "2", "2")
SWAMP = Card(name="Swamp", type_line="Basic Land \u2014 Swamp", produced_mana=("B",))
CANTRIP = real("Opt", "{1}", "Instant", "Draw a card.")


class ExtortTests(unittest.TestCase):
    def cast(self, paying, n=2, extorters=1, answer="Pay {W/B}"):
        game, _ = table3(script(answer) if paying else script("Don't pay"))
        a = game.seats[0]
        a.battlefield = [Permanent(SYNDIC) for _ in range(extorters)] + lands(n)
        a.hand, a.library = [CANTRIP], [FOREST] * 5
        game._perform(a, CAST + "Opt")
        run_stack(game)
        return game.seats

    def test_paying_drains_every_opponent(self):
        a, b, c = self.cast(True)
        self.assertEqual((a.life, b.life, c.life), (42, 39, 39))

    def test_not_paying_changes_nothing(self):
        a, b, c = self.cast(False)
        self.assertEqual((a.life, b.life, c.life), (40, 40, 40))

    def test_without_the_mana_it_cannot_be_paid(self):
        a, b, c = self.cast(True, n=1)
        self.assertEqual((a.life, b.life, c.life), (40, 40, 40))

    def test_each_extorter_triggers_on_its_own(self):
        a, b, c = self.cast(True, n=3, extorters=2)
        self.assertEqual((a.life, b.life, c.life), (44, 38, 38))

    def test_black_mana_pays_for_it_too(self):
        game, _ = table3(script("Pay {W/B}"))
        a = game.seats[0]
        a.battlefield = [Permanent(SYNDIC)] + lands(2, SWAMP)
        a.hand, a.library = [CANTRIP], [FOREST] * 5
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual(a.life, 42)

    def test_an_opponents_spell_does_not_trigger_it(self):
        game, _ = table3(script("Pay {W/B}"))
        a, b, c = game.seats
        a.battlefield = [Permanent(SYNDIC)] + lands(2)
        b.battlefield, b.hand, b.library = lands(2), [CANTRIP], [FOREST] * 5
        game.active = 1
        game._perform(b, CAST + "Opt")
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (40, 40, 40))

    def test_it_is_a_supported_keyword(self):
        self.assertEqual(unsupported_lines(SYNDIC), [])


class LookAtTheTopTests(unittest.TestCase):
    def test_the_line_is_understood_and_changes_nothing(self):
        card = real("Seer", "{1}{U}", "Creature \u2014 Human Wizard", "You may look at the top card of your library any time.", "1", "2")
        self.assertEqual((unsupported_lines(card), rules_statics(card)), ([], ("look_top",)))
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(card)]
        top = a.library[0]
        self.assertEqual(game.legal_actions(a), [PASS])
        self.assertIs(a.library[0], top)

    def test_a_card_with_another_line_is_still_not_playable(self):
        card = real("Future", "{2}{U}", "Enchantment", "You may look at the top card of your library any time.\nYou may cast spells from the top of your library.")
        self.assertEqual(unsupported_lines(card), ["You may cast spells from the top of your library."])


if __name__ == "__main__":
    unittest.main()
