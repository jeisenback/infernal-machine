"""The nine Lorehold graveyard, Treasure and equipment cards of the precon decks that no test named (issue #157), each played from
its real Oracle text, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, CAST_EXILE, CAST_GRAVEYARD, PLAY_EXILE, GraveyardTarget, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, battlefield_names, real
from tests.test_triggers_80 import BIG, FOREST, PLAINS, RELIC, SHRINE
from tests.test_x_targets import script

CHEAP = real("Cheap Creature", "{2}", "Creature — Test", "", "1", "1")      # mana value 2
FOUR = real("Four Creature", "{4}", "Creature — Test", "", "4", "4")        # mana value 4
ONE_DROP = real("One Drop", "{1}", "Creature — Test", "", "1", "1")
SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")
BOLT = real("Bolt", "{R}", "Instant", "Draw a card.", colors=("R",))


def end_step(game, seat, active=None):
    game.active = seat.index if active is None else active
    game.step = "end"
    game._turn_based_actions(game.seats[game.active])
    run_stack(game)


def leave_graveyard(game, seat, *cards):
    seat.graveyard = list(cards)
    for card in cards:
        game.exile_from_graveyard(GraveyardTarget(card, seat))
    run_stack(game)


def treasures(seat):
    return [p for p in seat.battlefield if p.card.name == "Treasure"]


def fight(game, seat):
    game.active = seat.index
    game.combat.declare_attackers(seat)
    run_stack(game)
    game.combat.declare_blockers()
    run_stack(game)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


RETRIEVER = real("Relic Retriever", "{1}{R}", "Creature — Spirit Monkey",
                 "First strike\nAt the beginning of each end step, if a card left your graveyard this turn, create a Treasure token. (It's "
                 "an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")", "2", "1")


class RelicRetrieverTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(RETRIEVER)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(RETRIEVER), [])

    def test_a_treasure_at_the_end_step_after_a_card_left_your_graveyard(self):
        game, a, b = self.table()
        leave_graveyard(game, a, BEAR)
        end_step(game, a)
        self.assertEqual(len(treasures(a)), 1)

    def test_none_when_no_card_left_your_graveyard(self):
        game, a, b = self.table()
        end_step(game, a)
        self.assertEqual(len(treasures(a)), 0)

    def test_none_when_the_card_left_an_opponents_graveyard(self):
        game, a, b = self.table()
        leave_graveyard(game, b, BEAR)
        end_step(game, a)
        self.assertEqual(len(treasures(a)), 0)

    def test_it_also_works_at_an_opponents_end_step(self):
        game, a, b = self.table()
        leave_graveyard(game, a, BEAR)
        end_step(game, a, active=1)
        self.assertEqual(len(treasures(a)), 1)

    def test_one_treasure_for_several_cards_and_none_the_next_turn(self):
        game, a, b = self.table()
        leave_graveyard(game, a, BEAR, OGRE)
        end_step(game, a)
        self.assertEqual(len(treasures(a)), 1)
        game.turn += 1
        end_step(game, a)
        self.assertEqual(len(treasures(a)), 1)


CAVALRY = real("Moonshaker Cavalry", "{5}{W}{W}{W}", "Creature — Spirit Knight",
               "Flying\nWhen this creature enters, creatures you control gain flying and get +X/+X until end of turn, where X is the number of "
               "creatures you control.", "6", "6")


class MoonshakerCavalryTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(CAVALRY), [])

    def test_your_creatures_fly_and_get_plus_x_where_x_counts_the_cavalry(self):
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        t = Table(CAVALRY, n=8, mine=[bear, ogre]).cast()
        cavalry = next(p for p in t.a.battlefield if p.card.name == "Moonshaker Cavalry")
        self.assertEqual((t.game.power(bear), t.game.power(ogre), t.game.power(cavalry)), (5, 6, 9))  # X = 3
        self.assertTrue(all(t.game.has_keyword(p, "flying") for p in (bear, ogre)))

    def test_opposing_creatures_are_unchanged(self):
        theirs = Permanent(BEAR)
        t = Table(CAVALRY, n=8, theirs=[theirs]).cast()
        self.assertEqual((t.game.power(theirs), t.game.has_keyword(theirs, "flying")), (2, False))

    def test_it_wears_off_at_end_of_turn(self):
        bear = Permanent(BEAR)
        t = Table(CAVALRY, n=8, mine=[bear]).cast()
        end_turn(t.game, t.a)
        self.assertEqual((t.game.power(bear), t.game.has_keyword(bear, "flying")), (2, False))

    def test_noncreature_permanents_do_not_count(self):
        bear = Permanent(BEAR)
        t = Table(CAVALRY, n=8, mine=[bear, Permanent(RELIC), Permanent(SHRINE)]).cast()
        self.assertEqual(t.game.power(bear), 4)  # X = 2: the Bear and the Cavalry


WELCOME = real("Tocasia's Welcome", "{2}{W}", "Enchantment",
               "Whenever one or more creatures you control with mana value 3 or less enter, draw a card. This ability triggers only once each "
               "turn.")


class TocasiasWelcomeTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(WELCOME)]
        a.library = [FOREST] * 10
        b.library = [FOREST] * 10
        return game, a, b

    def enter(self, game, seat, card):
        game._enter(seat, Permanent(card))
        run_stack(game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(WELCOME), [])

    def test_a_cheap_creature_entering_draws_a_card(self):
        game, a, b = self.table()
        self.enter(game, a, CHEAP)
        self.assertEqual(len(a.hand), 1)

    def test_a_creature_with_mana_value_four_does_not(self):
        game, a, b = self.table()
        self.enter(game, a, FOUR)
        self.assertEqual(len(a.hand), 0)

    def test_a_token_has_mana_value_zero_and_counts(self):
        game, a, b = self.table()
        self.enter(game, a, SPIRIT)
        self.assertEqual(len(a.hand), 1)

    def test_an_opponents_creature_does_not(self):
        game, a, b = self.table()
        self.enter(game, b, CHEAP)
        self.assertEqual(len(a.hand), 0)

    def test_a_noncreature_permanent_does_not(self):
        game, a, b = self.table()
        self.enter(game, a, RELIC)
        self.assertEqual(len(a.hand), 0)

    def test_only_once_each_turn_and_again_the_next(self):
        game, a, b = self.table()
        self.enter(game, a, CHEAP)
        self.enter(game, a, ONE_DROP)
        self.assertEqual(len(a.hand), 1)
        game.turn += 1
        self.enter(game, a, ONE_DROP)
        self.assertEqual(len(a.hand), 2)


ATSUSHI = real("Atsushi, the Blazing Sky", "{2}{R}{R}", "Legendary Creature — Dragon Spirit",
               "Flying, trample\nWhen Atsushi dies, choose one —\n• Exile the top two cards of your library. Until the end of your next turn, "
               "you may play those cards.\n• Create three Treasure tokens.", "4", "4")


class AtsushiTests(unittest.TestCase):
    def die(self, mode, library=(FOREST, BOLT, PLAINS)):
        game, _ = table3(pick(mode))
        a = game.seats[0]
        atsushi = Permanent(ATSUSHI)
        a.battlefield = [atsushi]
        a.library = list(library)
        game.destroy(atsushi)
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(ATSUSHI), [])

    def test_the_treasure_mode_makes_three_treasures(self):
        game, a = self.die("Create three Treasure tokens")
        self.assertEqual((len(treasures(a)), [c.name for c in a.graveyard]), (3, ["Atsushi, the Blazing Sky"]))

    def test_the_exile_mode_exiles_two_and_lets_you_play_them(self):
        game, a = self.die("Exile the top two")
        self.assertEqual(sorted(c.name for c in a.exile), ["Bolt", "Forest"])
        self.assertEqual(len(a.library), 1)
        actions = game.legal_actions(a)
        self.assertIn(PLAY_EXILE + "Forest", actions)

    def test_the_permission_lasts_through_the_end_of_your_next_turn(self):
        game, a = self.die("Exile the top two")  # it died on my turn (2); the table has three players, so my next turn is 5
        self.assertEqual({until for c, until in a.exile_play}, {5})
        game.turn = 5
        self.assertIn(PLAY_EXILE + "Forest", game.legal_actions(a))
        game.turn = 6
        self.assertNotIn(PLAY_EXILE + "Forest", game.legal_actions(a))

    def test_dying_on_an_opponents_turn_the_next_turn_is_sooner(self):
        game, _ = table3(pick("Exile the top two"))
        a = game.seats[0]
        atsushi = Permanent(ATSUSHI)
        a.battlefield = [atsushi]
        a.library = [FOREST, BOLT, PLAINS]
        game.active = 1  # the second player's turn (2): mine is the third player's, then mine at 4
        game.destroy(atsushi)
        run_stack(game)
        self.assertEqual({until for c, until in a.exile_play}, {4})

    def test_a_dying_atsushi_triggers_only_when_it_dies(self):
        game, _ = table3(pick("Create three Treasure tokens"))
        a = game.seats[0]
        atsushi = Permanent(ATSUSHI)
        a.battlefield = [atsushi]
        game.exile(atsushi)
        run_stack(game)
        self.assertEqual(len(treasures(a)), 0)


BITTERTHORN = real("Bitterthorn, Nissa's Animus", "{3}", "Legendary Artifact — Equipment",
                   "Living weapon (When this Equipment enters, create a 0/0 black Phyrexian Germ creature token, then attach this to it.)\n"
                   "Equipped creature gets +1/+1.\nWhenever equipped creature attacks, you may search your library for a basic land card, put it "
                   "onto the battlefield tapped, then shuffle.\nEquip {3}")


class BitterthornTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(BITTERTHORN), [])

    def test_a_germ_enters_with_it_attached_and_is_a_one_one(self):
        t = Table(BITTERTHORN).cast()
        germ = next(p for p in t.a.battlefield if "Germ" in p.card.name)
        equipment = next(p for p in t.a.battlefield if p.card.name.startswith("Bitterthorn"))
        self.assertIs(equipment.attached_to, germ)
        self.assertEqual((t.game.power(germ), t.game.toughness(germ)), (1, 1))

    def test_the_germ_dying_leaves_the_equipment_behind(self):
        t = Table(BITTERTHORN).cast()
        germ = next(p for p in t.a.battlefield if "Germ" in p.card.name)
        t.game.destroy(germ)
        self.assertEqual(battlefield_names(t.a), ["Bitterthorn, Nissa's Animus"])

    def attack(self, answer, library):
        game, _ = table3(pick("Attack", answer))
        a = game.seats[0]
        carrier = Permanent(BEAR, sick=False)
        a.battlefield = [carrier, Permanent(BITTERTHORN, attached_to=carrier)]
        a.library = list(library)
        fight(game, a)
        return a

    def test_attacking_it_may_fetch_a_basic_land_tapped(self):
        a = self.attack("Yes", [FOREST, BEAR])
        land = next(p for p in a.battlefield if p.card.name == "Forest")
        self.assertTrue(land.tapped)

    def test_it_may_decline(self):
        a = self.attack("No", [FOREST])
        self.assertNotIn("Forest", battlefield_names(a))

    def test_an_unequipped_attacker_fetches_nothing(self):
        game, _ = table3(pick("Attack", "Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR, sick=False), Permanent(BITTERTHORN)]
        a.library = [FOREST]
        fight(game, a)
        self.assertNotIn("Forest", battlefield_names(a))

    def test_the_equipped_creature_gets_plus_one_plus_one(self):
        game, _ = table3(pick())
        a = game.seats[0]
        carrier = Permanent(BEAR)
        a.battlefield = [carrier, Permanent(BITTERTHORN, attached_to=carrier)]
        self.assertEqual((game.power(carrier), game.toughness(carrier)), (3, 3))

    def test_equip_three_moves_it_to_another_creature(self):
        game, _ = table3(pick("Ogre"))
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        equipment = Permanent(BITTERTHORN, attached_to=bear)
        a.battlefield = [bear, ogre, equipment, *lands(3)]
        action = next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Equip" in x)
        game._perform(a, action)
        run_stack(game)
        self.assertIs(equipment.attached_to, ogre)


RESEARCH = real("Primary Research", "{4}{W}", "Enchantment",
                "When this enchantment enters, return target nonland permanent card with mana value 3 or less from your graveyard to the "
                "battlefield.\nAt the beginning of your end step, if a card left your graveyard this turn, draw a card.")


class PrimaryResearchTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(RESEARCH), [])

    def test_it_returns_a_nonland_permanent_with_mana_value_three_or_less_and_draws_at_the_end_step(self):
        t = Table(RESEARCH, "Cheap Creature", graveyard=[CHEAP, FOUR, FOREST]).cast()
        self.assertEqual(battlefield_names(t.a), ["Cheap Creature", "Primary Research"])
        t.a.library = [FOREST] * 5
        end_step(t.game, t.a)
        self.assertEqual(len(t.a.hand), 1)  # the returned card left the graveyard this turn

    def test_a_land_or_a_bigger_permanent_is_not_a_choice(self):
        t = Table(RESEARCH, graveyard=[FOUR, FOREST]).cast()
        self.assertEqual(battlefield_names(t.a), ["Primary Research"])

    def test_no_card_left_the_graveyard_no_draw(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(RESEARCH)]
        a.library = [FOREST] * 5
        end_step(game, a)
        self.assertEqual(len(a.hand), 0)

    def test_only_at_your_own_end_step(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(RESEARCH)]
        a.library = [FOREST] * 5
        leave_graveyard(game, a, BEAR)
        end_step(game, a, active=1)
        self.assertEqual(len(a.hand), 0)


LOOTING = real("Faithless Looting", "{R}", "Sorcery",
               "Draw two cards, then discard two cards.\nFlashback {2}{R} (You may cast this card from your graveyard for its flashback cost. "
               "Then exile it.)")


class FaithlessLootingTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(LOOTING), [])

    def test_it_draws_two_then_discards_two(self):
        t = Table(LOOTING, "Plains", "Forest", library=[PLAINS, FOREST, BEAR, BEAR])
        t.a.hand.append(RELIC)
        t.cast()
        self.assertEqual([c.name for c in t.a.hand], ["Relic"])  # drew Plains and Forest, discarded both
        self.assertEqual(sorted(c.name for c in t.a.graveyard), ["Faithless Looting", "Forest", "Plains"])

    def test_it_may_discard_cards_that_were_already_in_hand(self):
        t = Table(LOOTING, "Relic", "Plains", library=[PLAINS, FOREST])
        t.a.hand.append(RELIC)
        t.cast()
        self.assertEqual([c.name for c in t.a.hand], ["Forest"])

    def test_flashback_for_two_red_and_a_generic_exiles_it(self):
        t = Table(LOOTING, "Plains", "Forest", n=3, graveyard=[LOOTING], library=[PLAINS, FOREST, BEAR])
        t.a.hand = []
        t.game._perform(t.a, CAST_GRAVEYARD + "Faithless Looting")
        run_stack(t.game)
        self.assertEqual([c.name for c in t.a.exile], ["Faithless Looting"])
        self.assertNotIn("Faithless Looting", [c.name for c in t.a.graveyard if c.name == "Faithless Looting"])

    def test_flashback_needs_three_mana(self):
        t = Table(LOOTING, n=2, graveyard=[LOOTING])
        t.a.hand = []
        self.assertNotIn(CAST_GRAVEYARD + "Faithless Looting", t.game.legal_actions(t.a))


QUINTORIUS = real("Quintorius, Field Historian", "{3}{R}{W}", "Legendary Creature — Elephant Cleric",
                  "Spirits you control get +1/+0.\nWhenever one or more cards leave your graveyard, create a 3/2 red and white Spirit creature "
                  "token.", "2", "4")


class QuintoriusFieldHistorianTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(QUINTORIUS)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(QUINTORIUS), [])

    def test_a_card_leaving_your_graveyard_makes_a_spirit_with_plus_one_power(self):
        game, a, b = self.table()
        leave_graveyard(game, a, BEAR)
        spirit = next(p for p in a.battlefield if p.card.name == "Spirit")
        self.assertEqual((game.power(spirit), game.toughness(spirit)), (4, 2))

    def test_one_spirit_for_several_cards_leaving_together(self):
        game, a, b = self.table()
        a.graveyard = [BEAR, OGRE, RELIC]
        game.shuffle_into_library(a, [GraveyardTarget(c, a) for c in list(a.graveyard)])
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Spirit" for p in a.battlefield), 1)

    def test_an_opponents_graveyard_does_not(self):
        game, a, b = self.table()
        leave_graveyard(game, b, BEAR)
        self.assertEqual(sum(p.card.name == "Spirit" for p in a.battlefield), 0)

    def test_it_only_boosts_spirits_you_control(self):
        game, a, b = self.table()
        mine, theirs, other = Permanent(SPIRIT), Permanent(SPIRIT), Permanent(BEAR)
        a.battlefield += [mine, other]
        b.battlefield = [theirs]
        self.assertEqual((game.power(mine), game.power(theirs), game.power(other)), (2, 1, 2))


CONSTRUCT = real("Containment Construct", "{2}", "Artifact Creature — Construct",
                 "Whenever you discard a card, you may exile that card from your graveyard. If you do, you may play that card this turn.",
                 "2", "1")


class ContainmentConstructTests(unittest.TestCase):
    def discard(self, card, *answers, seat=0):
        game, _ = table3(script(*answers), None, None)
        a = game.seats[0]
        a.battlefield = [Permanent(CONSTRUCT), *lands(3)]
        game.seats[seat].hand = [card]
        game.discard(game.seats[seat], 1)
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(CONSTRUCT), [])

    def test_you_may_exile_the_discarded_card_and_play_it_this_turn(self):
        game, a = self.discard(FOREST, "Forest", "Yes")
        self.assertEqual(([c.name for c in a.exile], a.graveyard), (["Forest"], []))
        self.assertIn(PLAY_EXILE + "Forest", game.legal_actions(a))

    def test_a_spell_can_be_cast_from_exile(self):
        game, a = self.discard(BOLT, "Bolt", "Yes")
        self.assertIn(CAST_EXILE + "Bolt", game.legal_actions(a))

    def test_it_may_leave_the_card_in_the_graveyard(self):
        game, a = self.discard(FOREST, "Forest", "No")
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Forest"], []))

    def test_the_permission_ends_with_the_turn(self):
        game, a = self.discard(FOREST, "Forest", "Yes")
        game.turn += 1
        self.assertNotIn(PLAY_EXILE + "Forest", game.legal_actions(a))

    def test_an_opponents_discard_does_nothing(self):
        game, a = self.discard(FOREST, seat=1)
        self.assertEqual(a.exile, [])
