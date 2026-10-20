"""The eight Lorehold sacrifice-and-return creatures of the precon decks that no test named (issue #156), each played from its
real Oracle text, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import (
    attack_all,
    battlefield_names,
    BEAR,
    BIG,
    FOREST,
    lands,
    OGRE,
    pick,
    PLAINS,
    real,
    RELIC,
    run_stack,
    script,
    SHRINE,
    table,
    Table,
    table3,
)

BREEDING_POOL = Card(name="Breeding Pool", type_line="Land — Forest Island", produced_mana=("G", "U"))
BLACK_BEAR = real("Black Bear", "{1}{B}", "Creature — Bear", "", "2", "2", colors=("B",))
GREEN_BEAR = real("Green Bear", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
BLACK_BOLT = real("Black Bolt", "{B}", "Instant", "Black Bolt deals 3 damage to target creature.", colors=("B",))
RED_BOLT = real("Red Bolt", "{R}", "Instant", "Red Bolt deals 3 damage to target creature.", colors=("R",))
CHEAP = real("Cheap Creature", "{2}", "Creature — Test", "", "1", "1")        # mana value 2
THREE = real("Three Creature", "{3}", "Creature — Test", "", "3", "3")        # mana value 3
FOUR = real("Four Creature", "{4}", "Creature — Test", "", "4", "4")          # mana value 4
LEGEND = real("Old King", "{2}{W}", "Legendary Creature — Human", "", "2", "2")
HISTORIC_ARTIFACT = real("Relic", "{1}", "Artifact", "")
PLAIN_SPELL = real("Plain Draw", "{1}", "Instant", "Draw a card.")
CURSE = real("Curse", "{1}", "Enchantment", "")


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


KARMIC = real("Karmic Guide", "{3}{W}{W}", "Creature — Angel Spirit",
              "Flying, protection from black\nEcho {3}{W}{W} (At the beginning of your upkeep, if this came under your control since the "
              "beginning of your last upkeep, sacrifice it unless you pay its echo cost.)\nWhen this creature enters, return target "
              "creature card from your graveyard to the battlefield.", "2", "2")


class KarmicGuideTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(KARMIC), [])

    def test_entering_it_returns_a_creature_card_from_your_graveyard(self):
        t = Table(KARMIC, "Ogre", graveyard=[RELIC, BEAR, OGRE]).cast()
        self.assertEqual(battlefield_names(t.a), ["Karmic Guide", "Ogre"])
        self.assertEqual(sorted(c.name for c in t.a.graveyard), ["Bear", "Relic"])

    def test_noncreature_cards_and_other_graveyards_are_not_choices(self):
        t = Table(KARMIC, graveyard=[RELIC, SHRINE])
        t.b.graveyard = [OGRE]
        t.cast()
        self.assertEqual(battlefield_names(t.a), ["Karmic Guide"])
        self.assertEqual([c.name for c in t.b.graveyard], ["Ogre"])

    def upkeep(self, pays, n=5):
        game, _ = table3(script("Yes" if pays else "No"))
        a = game.seats[0]
        guide = Permanent(KARMIC, echo_pending=True)
        a.battlefield = [guide, *lands(n)]
        game._pay_upkeep_costs(a)
        return game, a, guide

    def test_echo_paid_keeps_it_and_taps_five_lands(self):
        game, a, guide = self.upkeep(True)
        self.assertIn(guide, a.battlefield)
        self.assertEqual(sum(p.tapped for p in a.battlefield), 5)

    def test_echo_declined_sacrifices_it(self):
        game, a, guide = self.upkeep(False)
        self.assertNotIn(guide, a.battlefield)
        self.assertEqual([c.name for c in a.graveyard], ["Karmic Guide"])

    def test_echo_unaffordable_sacrifices_it(self):
        game, a, guide = self.upkeep(True, n=4)
        self.assertNotIn(guide, a.battlefield)

    def test_echo_is_paid_only_once(self):
        game, a, guide = self.upkeep(True)
        for p in a.battlefield:
            p.tapped = False
        game._pay_upkeep_costs(a)
        self.assertIn(guide, a.battlefield)
        self.assertEqual(sum(p.tapped for p in a.battlefield), 0)

    def blocked_by(self, blocker):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(KARMIC, sick=False)]
        b.battlefield = [Permanent(blocker, sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        return bool(game.combat.attacks[0].blockers)

    def test_protection_from_black_a_black_flyer_cannot_block_it_and_a_green_flyer_can(self):
        flyer_black = real("Black Flyer", "{2}{B}", "Creature — Bird", "Flying", "2", "2", colors=("B",))
        flyer_green = real("Green Flyer", "{2}{G}", "Creature — Bird", "Flying", "2", "2", colors=("G",))
        self.assertFalse(self.blocked_by(flyer_black))
        self.assertTrue(self.blocked_by(flyer_green))

    def test_a_black_spell_cannot_target_it_and_a_red_one_can(self):
        for bolt, expected in ((BLACK_BOLT, False), (RED_BOLT, True)):
            t = Table(bolt, n=1, theirs=[Permanent(KARMIC)])
            self.assertEqual(any(a.startswith(CAST + bolt.name) for a in t.game.legal_actions(t.a)), expected, bolt.name)


CLERIC = real("Remorseful Cleric", "{1}{W}", "Creature — Spirit Cleric", "Flying\nSacrifice this creature: Exile target player's graveyard.",
              "2", "1")


class RemorsefulClericTests(unittest.TestCase):
    def sacrifice(self, target):
        game, _ = table3(pick(target))
        a, b, c = game.seats
        cleric = Permanent(CLERIC, sick=True)  # no {T} in the cost
        a.battlefield = [cleric]
        a.graveyard, b.graveyard, c.graveyard = [BEAR], [OGRE, RELIC], [SHRINE]
        activate(game, a, "Sacrifice this creature")
        return a, b, c

    def test_parse(self):
        self.assertEqual(unsupported_lines(CLERIC), [])

    def test_it_exiles_the_chosen_players_graveyard_and_only_that_one(self):
        a, b, c = self.sacrifice("Player: B")
        self.assertEqual((b.graveyard, [x.name for x in b.exile]), ([], ["Ogre", "Relic"]))
        self.assertEqual(([x.name for x in c.graveyard], [x.name for x in a.graveyard]), (["Shrine"], ["Bear", "Remorseful Cleric"]))

    def test_it_may_target_your_own_graveyard(self):
        a, b, c = self.sacrifice("Player: A")
        self.assertEqual(a.graveyard, [])  # the Cleric was sacrificed first, so it is exiled with the rest
        self.assertEqual(sorted(x.name for x in a.exile), ["Bear", "Remorseful Cleric"])


SPIRIT = real("Selfless Spirit", "{1}{W}", "Creature — Spirit Cleric",
              "Flying\nSacrifice this creature: Creatures you control gain indestructible until end of turn.", "2", "1")


class SelflessSpiritTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.spirit, self.mine, self.theirs = Permanent(SPIRIT), Permanent(OGRE), Permanent(BEAR)
        a.battlefield = [self.spirit, self.mine]
        b.battlefield = [self.theirs]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(SPIRIT), [])

    def test_your_creatures_survive_destruction_after_it_is_sacrificed(self):
        game, a, b = self.table()
        activate(game, a, "Sacrifice this creature")
        game.destroy(self.mine)
        game.destroy(self.theirs)
        run_stack(game)
        self.assertEqual((battlefield_names(a), battlefield_names(b)), (["Ogre"], []))

    def test_without_it_they_die(self):
        game, a, b = self.table()
        game.destroy(self.mine)
        self.assertEqual(battlefield_names(a), ["Selfless Spirit"])

    def test_it_wears_off_at_end_of_turn(self):
        game, a, b = self.table()
        activate(game, a, "Sacrifice this creature")
        end_turn(game, a)
        game.destroy(self.mine)
        self.assertEqual(battlefield_names(a), [])

    def test_creatures_that_arrive_later_are_not_covered(self):
        game, a, b = self.table()
        activate(game, a, "Sacrifice this creature")
        late = Permanent(BEAR)
        a.battlefield.append(late)
        game.destroy(late)
        self.assertNotIn(late, a.battlefield)


TITAN = real("Sun Titan", "{4}{W}{W}", "Creature — Giant",
             "Vigilance\nWhenever this creature enters or attacks, you may return target permanent card with mana value 3 or less from your "
             "graveyard to the battlefield.", "6", "6")


class SunTitanTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(TITAN), [])

    def test_entering_it_returns_a_permanent_card_with_mana_value_three_or_less(self):
        t = Table(TITAN, "Three Creature", "Yes", graveyard=[FOUR, THREE, PLAIN_SPELL], n=6).cast()
        self.assertEqual(battlefield_names(t.a), ["Sun Titan", "Three Creature"])

    def test_a_card_with_greater_mana_value_or_a_nonpermanent_is_not_a_choice(self):
        t = Table(TITAN, "Yes", n=6, graveyard=[FOUR, PLAIN_SPELL]).cast()
        self.assertEqual(battlefield_names(t.a), ["Sun Titan"])

    def test_it_may_decline(self):
        t = Table(TITAN, "Three Creature", "No", n=6, graveyard=[THREE]).cast()
        self.assertEqual(battlefield_names(t.a), ["Sun Titan"])

    def test_attacking_does_it_again(self):
        game, _ = table3(script("Attack", "Cheap Creature", "Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(TITAN, sick=False)]
        a.graveyard = [CHEAP]
        game.active = 0
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(battlefield_names(a), ["Cheap Creature", "Sun Titan"])

    def test_other_graveyards_are_not_offered(self):
        t = Table(TITAN, "Yes", n=6)
        t.b.graveyard = [CHEAP]
        t.cast()
        self.assertEqual(battlefield_names(t.a), ["Sun Titan"])


PHANTOM = real("White Orchid Phantom", "{W}{W}", "Creature — Spirit Knight",
               "Flying, first strike\nWhen this creature enters, destroy up to one target nonbasic land. Its controller may search their library "
               "for a basic land card, put it onto the battlefield tapped, then shuffle.", "2", "2")
BAZAAR = Card(name="Bazaar", type_line="Land", produced_mana=("C",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))


class WhiteOrchidPhantomTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PHANTOM), [])

    def test_it_destroys_a_nonbasic_land_and_its_controller_fetches_a_basic_tapped(self):
        t = Table(PHANTOM, "Bazaar", theirs=[Permanent(BAZAAR)])
        t.b.player.policy = pick("Yes", "Mountain")
        t.b.library = [MOUNTAIN, FOREST]
        t.cast()
        self.assertEqual(battlefield_names(t.b), ["Mountain"])
        self.assertTrue(t.b.battlefield[0].tapped)
        self.assertEqual([c.name for c in t.b.graveyard], ["Bazaar"])

    def test_its_controller_may_decline_to_search(self):
        t = Table(PHANTOM, "Bazaar", theirs=[Permanent(BAZAAR)])
        t.b.player.policy = pick("No")
        t.b.library = [MOUNTAIN]
        t.cast()
        self.assertEqual((battlefield_names(t.b), len(t.b.library)), ([], 1))

    def test_a_basic_land_is_not_a_target(self):
        t = Table(PHANTOM, theirs=[Permanent(FOREST)])
        t.cast()
        self.assertEqual(battlefield_names(t.b), ["Forest"])

    def test_it_may_destroy_nothing(self):
        t = Table(PHANTOM, "No target", theirs=[Permanent(BAZAAR)])
        t.cast()
        self.assertEqual(battlefield_names(t.b), ["Bazaar"])

    def test_it_can_destroy_my_own_nonbasic_land(self):
        t = Table(PHANTOM, "Breeding Pool", mine=[Permanent(BREEDING_POOL)])
        t.a.player.policy = pick("Breeding Pool", "No")
        t.a.library = [FOREST]
        t.cast()
        self.assertNotIn("Breeding Pool", battlefield_names(t.a))


KAMI = real("Kami of Ancient Law", "{1}{W}", "Creature — Spirit", "Sacrifice this creature: Destroy target enchantment.", "2", "2")


class KamiOfAncientLawTests(unittest.TestCase):
    def sacrifice(self, theirs):
        game, _ = table3(pick("Shrine"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(KAMI, sick=True)]
        b.battlefield = [Permanent(c) for c in theirs]
        activate(game, a, "Sacrifice this creature")
        return a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(KAMI), [])

    def test_it_destroys_a_target_enchantment(self):
        a, b = self.sacrifice([SHRINE, RELIC])
        self.assertEqual((battlefield_names(b), [c.name for c in a.graveyard]), (["Relic"], ["Kami of Ancient Law"]))

    def test_without_an_enchantment_it_is_not_offered(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(KAMI, sick=True)]
        b.battlefield = [Permanent(RELIC), Permanent(OGRE)]
        self.assertFalse(any(x.startswith(ACTIVATE) and "Sacrifice" in x for x in game.legal_actions(a)))


TESHAR = real("Teshar, Ancestor's Apostle", "{3}{W}", "Legendary Creature — Bird Cleric",
              "Flying\nWhenever you cast a historic spell, return target creature card with mana value 3 or less from your graveyard to the "
              "battlefield. (Artifacts, legendaries, and Sagas are historic.)", "2", "2")


class TesharTests(unittest.TestCase):
    def cast(self, spell, graveyard=(THREE,), opponent=False):
        t = Table(spell, "Three Creature", "Cheap Creature", mine=[Permanent(TESHAR)], graveyard=list(graveyard))
        if opponent:
            t.b.hand, t.b.battlefield = [spell], lands(6)
            t.a.hand = []
            t.game._perform(t.b, CAST + spell.name)
            run_stack(t.game)
            return t
        return t.cast()

    def test_parse(self):
        self.assertEqual(unsupported_lines(TESHAR), [])

    def test_a_historic_spell_returns_a_creature_with_mana_value_three_or_less(self):
        for spell in (HISTORIC_ARTIFACT, LEGEND):
            t = self.cast(spell)
            self.assertIn("Three Creature", battlefield_names(t.a), spell.name)

    def test_a_nonhistoric_spell_does_nothing(self):
        for spell in (PLAIN_SPELL, CURSE):
            t = self.cast(spell)
            self.assertNotIn("Three Creature", battlefield_names(t.a), spell.name)

    def test_a_creature_with_mana_value_four_is_not_a_choice(self):
        t = self.cast(HISTORIC_ARTIFACT, graveyard=(FOUR,))
        self.assertNotIn("Four Creature", battlefield_names(t.a))

    def test_an_opponents_historic_spell_does_nothing(self):
        t = self.cast(HISTORIC_ARTIFACT, opponent=True)
        self.assertNotIn("Three Creature", battlefield_names(t.a))

    def test_each_historic_spell_triggers_it_again(self):
        t = Table(HISTORIC_ARTIFACT, "Three Creature", "Cheap Creature", mine=[Permanent(TESHAR)], graveyard=[THREE, CHEAP])
        t.a.hand.append(LEGEND)
        t.cast()
        t.game._perform(t.a, CAST + "Old King")
        run_stack(t.game)
        self.assertEqual(sorted(battlefield_names(t.a)), ["Cheap Creature", "Old King", "Relic", "Teshar, Ancestor's Apostle", "Three Creature"])


SQUEE = real("Squee, Goblin Nabob", "{2}{R}", "Legendary Creature — Goblin", "At the beginning of your upkeep, you may return this card from your "
                                                                          "graveyard to your hand.", "1", "1")


class SqueeTests(unittest.TestCase):
    def upkeep(self, answer, in_graveyard=True, on_battlefield=False, active=0):
        game, _ = table3(pick(answer))
        a, b, _ = game.seats
        a.graveyard = [SQUEE] if in_graveyard else []
        if on_battlefield:
            a.battlefield = [Permanent(SQUEE)]
        game.active = active
        game.step = "upkeep"
        game._turn_based_actions(game.seats[active])
        run_stack(game)
        return a

    def test_parse(self):
        self.assertEqual(unsupported_lines(SQUEE), [])

    def test_at_your_upkeep_it_may_return_from_the_graveyard_to_your_hand(self):
        a = self.upkeep("Yes")
        self.assertEqual(([c.name for c in a.hand], a.graveyard), (["Squee, Goblin Nabob"], []))

    def test_it_may_stay_in_the_graveyard(self):
        a = self.upkeep("No")
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), ([], ["Squee, Goblin Nabob"]))

    def test_only_at_your_own_upkeep(self):
        a = self.upkeep("Yes", active=1)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), ([], ["Squee, Goblin Nabob"]))

    def test_it_does_nothing_from_the_battlefield(self):
        a = self.upkeep("Yes", in_graveyard=False, on_battlefield=True)
        self.assertEqual(([c.name for c in a.hand], battlefield_names(a)), ([], ["Squee, Goblin Nabob"]))
