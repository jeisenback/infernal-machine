"""The channel lands of Neon Dynasty (Boseiju, Eiganjo, Otawara, Sokenzan, Takenuma), from their own Oracle text: an ability
from the hand that discards the land and costs {1} less for each legendary creature you control."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.game import ACTIVATE_HAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, BIRD, OGRE
from tests.test_effects import RAINBOW, lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_triggers_80 import FOREST, PLAINS, RELIC, SHRINE
from tests.test_x_targets import script

LESS = " This ability costs {1} less to activate for each legendary creature you control."
BOSEIJU = real("Boseiju, Who Endures", "", "Legendary Land",
               "{T}: Add {G}.\nChannel — {1}{G}, Discard this card: Destroy target artifact, enchantment, or nonbasic land an opponent "
               "controls. That player may search their library for a land card with a basic land type, put it onto the battlefield, then "
               "shuffle." + LESS)
EIGANJO = real("Eiganjo, Seat of the Empire", "", "Legendary Land",
               "{T}: Add {W}.\nChannel — {2}{W}, Discard this card: It deals 4 damage to target attacking or blocking creature." + LESS)
OTAWARA = real("Otawara, Soaring City", "", "Legendary Land",
               "{T}: Add {U}.\nChannel — {3}{U}, Discard this card: Return target artifact, creature, enchantment, or planeswalker to "
               "its owner's hand." + LESS)
SOKENZAN = real("Sokenzan, Crucible of Defiance", "", "Legendary Land",
                "{T}: Add {R}.\nChannel — {3}{R}, Discard this card: Create two 1/1 colorless Spirit creature tokens. They gain haste "
                "until end of turn." + LESS)
TAKENUMA = real("Takenuma, Abandoned Mire", "", "Legendary Land",
                "{T}: Add {B}.\nChannel — {3}{B}, Discard this card: Mill three cards, then return a creature or planeswalker card "
                "from your graveyard to your hand." + LESS)
LEGEND = real("Legend", "{1}", "Legendary Creature — Human", "", "1", "1")
STOMPING = Card(name="Stomping Ground", type_line="Land — Mountain Forest", produced_mana=("R", "G"))
WALKER = real("Walker", "{3}", "Legendary Planeswalker — Test", "")
TREASURE = real("Relic", "{1}", "Artifact", "")


def board(land, mana=4, legends=0, *answers, theirs=()):
    game, _ = table3(script(*answers), script(*theirs))
    a, b, c = game.seats
    a.hand = [land]
    a.battlefield = lands(mana) + [Permanent(LEGEND) for _ in range(legends)]
    return game, a, b, c


def channel(game, a, land):
    game._perform(a, ACTIVATE_HAND + land.name)
    run_stack(game)
    game._check_state()


def offered(game, a, land):
    return ACTIVATE_HAND + land.name in game.legal_actions(a)


class ParseTests(unittest.TestCase):
    def test_every_channel_land_is_fully_playable(self):
        for land in (BOSEIJU, EIGANJO, OTAWARA, SOKENZAN, TAKENUMA):
            self.assertEqual(unsupported_lines(land), [], land.name)


class CostTests(unittest.TestCase):
    def test_a_channel_ability_without_the_discount_costs_what_it_says(self):
        plain = real("Spirit", "{1}{G}", "Legendary Creature \u2014 Spirit",
                     "Channel \u2014 {2}{G}, Discard this card: You gain 3 life.", "2", "2")
        self.assertEqual(unsupported_lines(plain), [])
        game, a, b, _ = board(plain, 2, 3)
        self.assertFalse(offered(game, a, plain))
        a.battlefield += lands(1)
        self.assertTrue(offered(game, a, plain))

    def test_the_full_cost_needs_all_its_mana(self):
        game, a, b, _ = board(OTAWARA, mana=3)
        b.battlefield = [Permanent(BEAR)]
        self.assertFalse(offered(game, a, OTAWARA))
        a.battlefield += lands(1)
        self.assertTrue(offered(game, a, OTAWARA))

    def test_each_legendary_creature_makes_it_cheaper_by_one(self):
        for legends, mana in ((1, 3), (2, 2), (3, 1)):
            game, a, b, _ = board(OTAWARA, mana, legends)
            b.battlefield = [Permanent(BEAR)]
            self.assertTrue(offered(game, a, OTAWARA), legends)
            game, a, b, _ = board(OTAWARA, mana - 1, legends)
            b.battlefield = [Permanent(BEAR)]
            self.assertFalse(offered(game, a, OTAWARA), legends)

    def test_only_the_generic_part_gets_cheaper(self):
        game, a, b, _ = board(OTAWARA, 0, 4)
        b.battlefield = [Permanent(BEAR)]
        a.battlefield += lands(1)  # {U} still has to be paid
        self.assertTrue(offered(game, a, OTAWARA))
        a.battlefield = [p for p in a.battlefield if p.card is not RAINBOW]
        self.assertFalse(offered(game, a, OTAWARA))

    def test_a_nonlegendary_creature_does_not_help(self):
        game, a, b, _ = board(OTAWARA, 3)
        a.battlefield.append(Permanent(BEAR))
        b.battlefield = [Permanent(OGRE)]
        self.assertFalse(offered(game, a, OTAWARA))

    def test_an_opponents_legendary_creature_does_not_help(self):
        game, a, b, _ = board(OTAWARA, 3)
        b.battlefield = [Permanent(LEGEND)]
        self.assertFalse(offered(game, a, OTAWARA))

    def test_the_land_is_discarded_as_the_cost(self):
        game, a, b, _ = board(OTAWARA, 4, 0, "Ogre")
        b.battlefield = [Permanent(OGRE)]
        channel(game, a, OTAWARA)
        self.assertEqual(([c.name for c in a.graveyard], a.hand, sum(p.tapped for p in a.battlefield)), (["Otawara, Soaring City"], [], 4))

    def test_it_is_not_offered_without_a_target(self):
        game, a, b, _ = board(OTAWARA, 4)
        self.assertFalse(offered(game, a, OTAWARA))


class BoseijuTests(unittest.TestCase):
    def test_it_destroys_an_artifact_enchantment_or_nonbasic_land_and_that_player_may_search(self):
        for target in (TREASURE, SHRINE, STOMPING):
            game, a, b, c = board(BOSEIJU, 2, 0, "Relic" if target is TREASURE else target.name, theirs=("Yes", "Stomping Ground"))
            b.battlefield = [Permanent(target)]
            b.library = [FOREST, STOMPING, PLAINS]
            channel(game, a, BOSEIJU)
            self.assertEqual(([p.card.name for p in b.battlefield], [c.name for c in b.graveyard]),
                             (["Stomping Ground"], [target.name]) if target is not STOMPING else (["Stomping Ground"], ["Stomping Ground"]),
                             target.name)

    def test_the_land_arrives_untapped_and_is_a_dual_if_chosen(self):
        game, a, b, _ = board(BOSEIJU, 2, 0, "Shrine", theirs=("Yes", "Stomping Ground"))
        b.battlefield = [Permanent(SHRINE)]
        b.library = [FOREST, STOMPING]
        channel(game, a, BOSEIJU)
        self.assertEqual([(p.card.name, p.tapped) for p in b.battlefield], [("Stomping Ground", False)])

    def test_that_player_may_decline(self):
        game, a, b, _ = board(BOSEIJU, 2, 0, "Shrine", theirs=("No",))
        b.battlefield = [Permanent(SHRINE)]
        b.library = [FOREST]
        channel(game, a, BOSEIJU)
        self.assertEqual((b.battlefield, len(b.library)), ([], 1))

    def test_a_basic_land_a_creature_and_your_own_permanents_cannot_be_targeted(self):
        game, a, b, _ = board(BOSEIJU, 2)
        b.battlefield = [Permanent(FOREST), Permanent(BEAR)]
        a.battlefield.append(Permanent(SHRINE))
        self.assertFalse(offered(game, a, BOSEIJU))

    def test_a_nonland_card_in_the_library_cannot_be_found(self):
        game, a, b, _ = board(BOSEIJU, 2, 0, "Shrine", theirs=("Yes",))
        b.battlefield = [Permanent(SHRINE)]
        b.library = [BEAR]
        channel(game, a, BOSEIJU)
        self.assertEqual(b.battlefield, [])


class EiganjoTests(unittest.TestCase):
    def fight(self):
        game, a, b, c = board(EIGANJO, 3, 0, "Ogre")
        attacker, blocker, bystander = Permanent(OGRE), Permanent(BIRD), Permanent(BEAR)
        b.battlefield = [attacker, blocker, bystander]
        game.step = "declare_blockers"
        game.combat.attacks = [Attack(attacker, b, a, blockers=[blocker])]
        return game, a, b, attacker, blocker, bystander

    def test_four_damage_to_an_attacking_creature(self):
        game, a, b, attacker, blocker, bystander = self.fight()
        channel(game, a, EIGANJO)
        self.assertEqual([p.card.name for p in b.battlefield], ["Bird", "Bear"])

    def test_a_blocking_creature_is_a_target_too(self):
        game, a, b, attacker, blocker, bystander = self.fight()
        game.seats[0].player.policy = script("Bird")
        channel(game, a, EIGANJO)
        self.assertEqual([p.card.name for p in b.battlefield], ["Ogre", "Bear"])

    def test_a_creature_in_neither_role_is_not_a_target(self):
        game, a, b, attacker, blocker, bystander = self.fight()
        labels = [label for label, _ in game.target_options("attacking or blocking creature", a)]
        self.assertEqual(sorted(labels), sorted([game.label(attacker), game.label(blocker)]))

    def test_it_cannot_be_used_with_no_combat(self):
        game, a, b, c = board(EIGANJO, 3)
        b.battlefield = [Permanent(OGRE)]
        self.assertFalse(offered(game, a, EIGANJO))


class OtawaraTests(unittest.TestCase):
    def test_it_returns_each_kind_of_permanent_to_its_owners_hand(self):
        for target in (TREASURE, SHRINE, BEAR, WALKER):
            game, a, b, _ = board(OTAWARA, 4, 0, target.name)
            b.battlefield = [Permanent(target)]
            channel(game, a, OTAWARA)
            self.assertEqual(([p.card.name for p in b.battlefield], [c.name for c in b.hand]), ([], [target.name]), target.name)

    def test_a_land_is_not_a_target(self):
        game, a, b, _ = board(OTAWARA, 4)
        b.battlefield = [Permanent(FOREST)]
        self.assertFalse(offered(game, a, OTAWARA))


class SokenzanTests(unittest.TestCase):
    def test_two_hasty_spirits(self):
        game, a, b, _ = board(SOKENZAN, 4)
        channel(game, a, SOKENZAN)
        spirits = [p for p in a.battlefield if "Spirit" in p.card.type_line]
        self.assertEqual(([(p.card.power, p.card.toughness) for p in spirits], [game.has_keyword(p, "haste") for p in spirits]),
                         ([("1", "1"), ("1", "1")], [True, True]))

    def test_the_haste_is_only_for_the_tokens_it_made(self):
        game, a, b, _ = board(SOKENZAN, 4)
        bear = Permanent(BEAR, sick=True)
        a.battlefield.append(bear)
        channel(game, a, SOKENZAN)
        self.assertFalse(game.has_keyword(bear, "haste"))


class TakenumaTests(unittest.TestCase):
    def test_it_mills_three_then_returns_a_creature_or_planeswalker(self):
        game, a, b, _ = board(TAKENUMA, 4, 0, "Walker")
        a.library = [BEAR, WALKER, SHRINE, FOREST, FOREST]
        channel(game, a, TAKENUMA)
        self.assertEqual(([c.name for c in a.hand], len(a.library), sorted(c.name for c in a.graveyard)),
                         (["Walker"], 2, ["Bear", "Shrine", "Takenuma, Abandoned Mire"]))

    def test_it_can_return_a_card_it_just_milled_or_one_already_there(self):
        game, a, b, _ = board(TAKENUMA, 4, 0, "Ogre")
        a.graveyard = [OGRE]
        a.library = [SHRINE, FOREST, FOREST, FOREST]
        channel(game, a, TAKENUMA)
        self.assertEqual([c.name for c in a.hand], ["Ogre"])

    def test_a_noncreature_nonplaneswalker_is_not_returned(self):
        game, a, b, _ = board(TAKENUMA, 4)
        a.library = [SHRINE, TREASURE, FOREST, FOREST]
        channel(game, a, TAKENUMA)
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
