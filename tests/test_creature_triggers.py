"""Popular creatures whose last missing line was a trigger or a small rule (Azusa, Seedborn Muse, Orcish Bowmasters, Scute Swarm,
Mirkwood Bats ...), each from its own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import RAINBOW, lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_triggers_80 import FOREST, PLAINS
from tests.test_x_targets import script

EXPLORATION = real("Exploration", "{G}", "Enchantment", "You may play an additional land on each of your turns.")
AZUSA = real("Azusa, Lost but Seeking", "{2}{G}", "Legendary Creature — Human Monk",
             "You may play two additional lands on each of your turns.", "1", "2")
MUSE = real("Seedborn Muse", "{3}{G}{G}", "Creature — Spirit", "Untap all permanents you control during each other player's untap step.", "2", "4")
ARBOR = real("Arbor Elf", "{G}", "Creature — Elf Druid", "{T}: Untap target Forest.", "1", "1")
WELCOMING = real("Welcoming Vampire", "{2}{W}", "Creature — Vampire",
                 "Flying\nWhenever one or more other creatures you control with power 2 or less enter, draw a card. This ability triggers only once each turn.",
                 "2", "3")
ANARCHOMANCER = real("Goblin Anarchomancer", "{R}{G}", "Creature — Goblin Shaman", "Each spell you cast that's red or green costs {1} less to cast.", "2", "2")
AVENGER = real("Avenger of Zendikar", "{5}{G}{G}", "Creature — Elemental",
               "When this creature enters, create a 0/1 green Plant creature token for each land you control.\n"
               "Landfall — Whenever a land you control enters, you may put a +1/+1 counter on each Plant creature you control.", "5", "5")
PROVISIONER = real("Tireless Provisioner", "{2}{G}", "Creature — Elf Scout",
                   "Landfall — Whenever a land you control enters, create a Food token or a Treasure token.", "3", "2")
SCUTE = real("Scute Swarm", "{2}{G}", "Creature — Insect",
             "Landfall — Whenever a land you control enters, create a 1/1 green Insect creature token. If you control six or more lands, "
             "create a token that's a copy of this creature instead.", "1", "1", colors=("G",))
BATS = real("Mirkwood Bats", "{3}{B}", "Creature — Bat", "Flying\nWhenever you create or sacrifice a token, each opponent loses 1 life.", "2", "3")
BOWMASTERS = real("Orcish Bowmasters", "{1}{B}", "Creature — Orc Archer",
                  "Flash\nWhen this creature enters and whenever an opponent draws a card except the first one they draw in each of their draw steps, "
                  "this creature deals 1 damage to any target. Then amass Orcs 1.", "1", "1")
PLAGUECRAFTER = real("Plaguecrafter", "{2}{B}", "Creature — Human Horror",
                     "When this creature enters, each player sacrifices a creature or planeswalker of their choice. Each player who can't discards a card.", "3", "2")
MARAUDER = real("Accursed Marauder", "{1}{B}", "Creature — Zombie Warrior",
                "When this creature enters, each player sacrifices a nontoken creature of their choice.", "2", "1")
SHEOLDRED = real("Sheoldred, Whispering One", "{5}{B}{B}", "Legendary Creature — Phyrexian Praetor",
                 "Swampwalk\nAt the beginning of your upkeep, return target creature card from your graveyard to the battlefield.\n"
                 "At the beginning of each opponent's upkeep, that player sacrifices a creature of their choice.", "6", "6")
MANIAC = real("Laboratory Maniac", "{2}{U}", "Creature — Human Wizard",
              "If you would draw a card while your library has no cards in it, you win the game instead.", "2", "2")
LOTHO = real("Lotho, Corrupt Shirriff", "{2}{R}", "Legendary Creature — Halfling Rogue",
             "Whenever a player casts their second spell each turn, you lose 1 life and create a Treasure token.", "3", "3")
TRACKER = real("Tireless Tracker", "{2}{G}", "Creature — Human Scout",
               "Landfall — Whenever a land enters under your control, investigate.\nWhenever you sacrifice a Clue, put a +1/+1 counter on this creature.", "3", "2")

BEAR = real("Bear", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
BIG = real("Big", "{4}{G}", "Creature — Giant", "", "4", "4", colors=("G",))
TOKEN_BEAR = Card(name="Bear Token", type_line="Token Creature — Bear", power="2", toughness="2")
PLANT = Card(name="Plant", type_line="Token Creature — Plant", power="0", toughness="1", colors=("G",))
FOREST_DUAL = Card(name="Stomping Ground", type_line="Land — Mountain Forest", produced_mana=("R", "G"))
CANTRIP = real("Opt", "{1}", "Instant", "You gain 1 life.")
WALKER = real("Walker", "{3}", "Legendary Planeswalker — Test", "")


def board(*answers, theirs=()):
    game, _ = table3(script(*answers), script(*theirs))
    return game, *game.seats


def plays(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(PLAY_LAND)]


class LandDropTests(unittest.TestCase):
    def test_two_additional_lands_make_three_drops(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(AZUSA)]
        a.hand = [FOREST, FOREST, FOREST, FOREST]
        for _ in range(3):
            self.assertTrue(plays(game, a))
            game._perform(a, PLAY_LAND + "Forest")
        self.assertEqual(plays(game, a), [])

    def test_with_another_source_it_is_four(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(AZUSA), Permanent(EXPLORATION)]
        a.hand = [FOREST] * 5
        for _ in range(4):
            game._perform(a, PLAY_LAND + "Forest")
        self.assertEqual(plays(game, a), [])


class UntapTests(unittest.TestCase):
    def test_seedborn_muse_untaps_everything_in_other_players_untap_steps(self):
        game, a, b, c = board()
        tapped = [Permanent(MUSE), Permanent(FOREST, tapped=True), Permanent(BEAR, tapped=True)]
        a.battlefield = tapped
        game.active, game.step = 1, "untap"
        game._turn_based_actions(b)
        self.assertEqual([p.tapped for p in tapped], [False, False, False])

    def test_without_it_they_stay_tapped(self):
        game, a, b, c = board()
        tapped = [Permanent(FOREST, tapped=True)]
        a.battlefield = tapped
        game.active, game.step = 1, "untap"
        game._turn_based_actions(b)
        self.assertTrue(tapped[0].tapped)

    def test_an_opponents_muse_does_not_help_you(self):
        game, a, b, c = board()
        land = Permanent(FOREST, tapped=True)
        a.battlefield = [land]
        b.battlefield = [Permanent(MUSE)]
        game.active, game.step = 1, "untap"
        game._turn_based_actions(b)
        self.assertTrue(land.tapped)

    def test_it_does_not_override_a_permanent_that_does_not_untap(self):
        game, a, b, c = board()
        monolith = real("Basalt Monolith", "{3}", "Artifact", "This artifact doesn't untap during your untap step.\n{T}: Add {C}{C}{C}.")
        stays = Permanent(monolith, tapped=True)
        a.battlefield = [Permanent(MUSE), stays]
        game.active, game.step = 0, "untap"
        game._turn_based_actions(a)
        self.assertTrue(stays.tapped)

    def test_it_does_nothing_once_its_abilities_are_gone(self):
        game, a, b, c = board()
        muse = Permanent(MUSE)
        frog = real("Turn to Frog", "{1}{U}", "Enchantment \u2014 Aura", "Enchant creature\nEnchanted creature loses all abilities.")
        land = Permanent(FOREST, tapped=True)
        a.battlefield = [muse, Permanent(frog, attached_to=muse), land]
        game.active, game.step = 1, "untap"
        game._turn_based_actions(b)
        self.assertTrue(land.tapped)

    def test_arbor_elf_untaps_a_forest(self):
        game, a, b, c = board("Forest")
        elf, forest, plains = Permanent(ARBOR, sick=False), Permanent(FOREST, tapped=True), Permanent(PLAINS, tapped=True)
        a.battlefield = [elf, forest, plains]
        [action] = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Arbor Elf" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((forest.tapped, plains.tapped, elf.tapped), (False, True, True))

    def test_only_a_forest_can_be_chosen(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(PLAINS, tapped=True), Permanent(FOREST_DUAL, tapped=True), Permanent(FOREST, tapped=True)]
        labels = [label for label, _ in game.target_options("forest", a)]
        self.assertEqual(len(labels), 2)


class CostTests(unittest.TestCase):
    def test_red_and_green_spells_cost_one_less(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(ANARCHOMANCER)]
        red, green = real("Red", "{2}{R}", "Sorcery", "", colors=("R",)), real("Green", "{2}{G}", "Sorcery", "", colors=("G",))
        both, blue = real("Both", "{R}{G}", "Sorcery", "", colors=("R", "G")), real("Blue", "{2}{U}", "Sorcery", "", colors=("U",))
        self.assertEqual([game.cost_reduction(a, x) for x in (red, green, both, blue)], [1, 1, 1, 0])


class LandfallTests(unittest.TestCase):
    def land_enters(self, game, seat):
        game._enter(seat, Permanent(FOREST))
        run_stack(game)

    def test_avenger_grows_every_plant(self):
        game, a, b, c = board("Yes")
        plants = [Permanent(PLANT), Permanent(PLANT)]
        other = Permanent(BEAR)
        a.battlefield = [Permanent(AVENGER), other] + plants
        self.land_enters(game, a)
        self.assertEqual(([p.counters.get("+1/+1") for p in plants], other.counters.get("+1/+1")), ([1, 1], None))

    def test_avenger_may_decline(self):
        game, a, b, c = board("No")
        plant = Permanent(PLANT)
        a.battlefield = [Permanent(AVENGER), plant]
        self.land_enters(game, a)
        self.assertEqual(plant.counters, {})

    def test_provisioner_makes_the_token_you_choose(self):
        for choice in ("Food", "Treasure"):
            game, a, b, c = board(choice)
            a.battlefield = [Permanent(PROVISIONER)]
            self.land_enters(game, a)
            self.assertEqual([p.card.name for p in a.battlefield if "Token" in p.card.type_line], [choice])

    def test_scute_swarm_makes_an_insect_with_few_lands(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(SCUTE)] + lands(4)
        self.land_enters(game, a)
        tokens = [p for p in a.battlefield if "Token" in p.card.type_line]
        self.assertEqual([(p.card.name, p.card.power) for p in tokens], [("Insect", "1")])

    def test_scute_swarm_copies_itself_with_six_lands(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(SCUTE)] + lands(5)
        self.land_enters(game, a)
        tokens = [p for p in a.battlefield if "Token" in p.card.type_line]
        self.assertEqual([p.card.name for p in tokens], ["Scute Swarm"])

    def test_scute_swarm_keeps_multiplying(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(SCUTE)] + lands(5)
        self.land_enters(game, a)
        self.land_enters(game, a)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Scute Swarm"]), 4)

    def test_tracker_grows_when_a_clue_is_sacrificed(self):
        game, a, b, c = board()
        from infernal_machine.effects import CLUE
        tracker, clue = Permanent(TRACKER), Permanent(CLUE)
        a.battlefield = [tracker, clue]
        game._leave_battlefield(clue, "sacrificed")
        run_stack(game)
        self.assertEqual(tracker.counters.get("+1/+1"), 1)

    def test_tracker_ignores_a_food_though_it_is_an_artifact_too(self):
        from infernal_machine.effects import FOOD
        game, a, b, c = board()
        tracker, food = Permanent(TRACKER), Permanent(FOOD)
        a.battlefield = [tracker, food]
        game._leave_battlefield(food, "sacrificed")
        run_stack(game)
        self.assertEqual(tracker.counters, {})

    def test_tracker_ignores_other_sacrifices(self):
        game, a, b, c = board()
        tracker, bear = Permanent(TRACKER), Permanent(BEAR)
        a.battlefield = [tracker, bear]
        game._leave_battlefield(bear, "sacrificed")
        run_stack(game)
        self.assertEqual(tracker.counters, {})


class WelcomingVampireTests(unittest.TestCase):
    def enter(self, *cards):
        game, a, b, c = board()
        a.library = [FOREST] * 5
        a.battlefield = [Permanent(WELCOMING)]
        for card in cards:
            game._enter(a, Permanent(card))
        run_stack(game)
        return a

    def test_a_small_creature_draws(self):
        self.assertEqual(len(self.enter(BEAR).hand), 1)

    def test_a_big_one_does_not(self):
        self.assertEqual(self.enter(BIG).hand, [])

    def test_only_once_each_turn(self):
        self.assertEqual(len(self.enter(BEAR, BEAR, BEAR).hand), 1)

    def test_it_does_not_count_itself(self):
        game, a, b, c = board()
        a.library = [FOREST] * 5
        game._enter(a, Permanent(WELCOMING))
        run_stack(game)
        self.assertEqual(a.hand, [])


class BatsTests(unittest.TestCase):
    def test_creating_a_token_drains_each_opponent(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BATS)]
        game.create_tokens(a, TOKEN_BEAR, 1)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (40, 39, 39))

    def test_sacrificing_a_token_drains_each_opponent(self):
        game, a, b, c = board()
        token = Permanent(TOKEN_BEAR)
        a.battlefield = [Permanent(BATS), token]
        game._leave_battlefield(token, "sacrificed")
        run_stack(game)
        self.assertEqual((b.life, c.life), (39, 39))

    def test_a_card_does_not(self):
        game, a, b, c = board()
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(BATS), bear]
        game._leave_battlefield(bear, "sacrificed")
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 40))

    def test_an_opponents_token_does_not(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BATS)]
        game.create_tokens(b, TOKEN_BEAR, 1)
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 40))


class BowmastersTests(unittest.TestCase):
    def test_it_shoots_and_amasses_as_it_enters(self):
        game, a, b, c = board("Player: B")
        game._enter(a, Permanent(BOWMASTERS))
        run_stack(game)
        army = next(p for p in a.battlefield if "Army" in p.card.type_line)
        self.assertEqual((b.life, army.counters.get("+1/+1"), "Orc" in army.card.type_line, game.power(army)), (39, 1, True, 1))

    def test_an_extra_draw_by_an_opponent_triggers_it(self):
        game, a, b, c = board("Player: B")
        a.battlefield = [Permanent(BOWMASTERS)]
        b.library = [FOREST] * 5
        game.draw(b, 1)
        run_stack(game)
        self.assertEqual(b.life, 39)

    def test_so_does_every_one_after_the_first(self):
        game, a, b, c = board("Player: B", "Player: B")
        a.battlefield = [Permanent(BOWMASTERS)]
        b.library = [FOREST] * 5
        game.draw(b, 2)
        run_stack(game)
        self.assertEqual(b.life, 38)

    def test_the_draw_step_draw_does_not(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BOWMASTERS)]
        b.library = [FOREST] * 5
        game.active, game.step, game.turn = 1, "draw", 3
        game._turn_based_actions(b)
        run_stack(game)
        self.assertEqual((b.life, len(b.hand), [p.card.name for p in a.battlefield if "Army" in p.card.type_line]), (40, 1, []))

    def test_your_own_draws_do_not(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BOWMASTERS)]
        a.library = [FOREST] * 5
        game.draw(a, 2)
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 40))

    def test_a_second_amass_adds_to_the_same_army(self):
        game, a, b, c = board("Player: B", "Player: B")
        game._enter(a, Permanent(BOWMASTERS))
        game._enter(a, Permanent(BOWMASTERS))
        run_stack(game)
        armies = [p for p in a.battlefield if "Army" in p.card.type_line]
        self.assertEqual([p.counters.get("+1/+1") for p in armies], [2])


class EdictTests(unittest.TestCase):
    def test_plaguecrafter_makes_each_player_sacrifice_or_discard(self):
        game, a, b, c = board("Plaguecrafter", theirs=("Bear",))
        b.battlefield = [Permanent(BEAR)]
        a.hand = [FOREST]
        c.hand = [PLAINS]
        game._enter(a, Permanent(PLAGUECRAFTER))
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], [p.card.name for p in b.battlefield], [x.name for x in a.hand],
                          [x.name for x in c.hand], [x.name for x in c.graveyard]), ([], [], ["Forest"], [], ["Plains"]))

    def test_the_marauder_only_takes_nontoken_creatures(self):
        game, a, b, c = board("Accursed", theirs=("Bear",))
        b.battlefield = [Permanent(BEAR), Permanent(TOKEN_BEAR)]
        game._enter(a, Permanent(MARAUDER))
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Bear Token"])

    def test_the_marauder_sacrifices_itself_if_it_is_the_only_one(self):
        game, a, b, c = board("Accursed")
        game._enter(a, Permanent(MARAUDER))
        run_stack(game)
        self.assertEqual(a.battlefield, [])

    def test_sheoldred_makes_each_opponent_sacrifice_in_their_upkeep(self):
        game, a, b, c = board(theirs=("Bear",))
        a.battlefield = [Permanent(SHEOLDRED)]
        b.battlefield = [Permanent(BEAR), Permanent(BIG)]
        game.active, game.step = 1, "upkeep"
        game._turn_based_actions(b)
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Big"])


class SmallRuleTests(unittest.TestCase):
    def test_the_maniac_wins_instead_of_losing_to_an_empty_library(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(MANIAC)]
        a.library = []
        game.draw(a, 1)
        game._check_state()
        self.assertEqual((a.lost, b.lost, c.lost, game.winner() is a), (False, True, True, True))

    def test_without_it_an_empty_library_loses(self):
        game, a, b, c = board()
        a.library = []
        game.draw(a, 1)
        game._check_state()
        self.assertEqual((a.lost, b.lost), (True, False))

    def test_the_maniac_does_nothing_while_there_are_cards(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(MANIAC)]
        a.library = [FOREST]
        game.draw(a, 1)
        game._check_state()
        self.assertEqual((a.wins_game, b.lost, len(a.hand)), (False, False, 1))

    def cast(self, caster, *spells):
        game, a, b, c = board()
        a.battlefield = [Permanent(LOTHO)]
        seat = game.seats[caster]
        seat.battlefield += lands(4)
        seat.hand = list(spells)
        game.active = caster
        for spell in spells:
            game._perform(seat, CAST + spell.name)
            run_stack(game)
        return game

    def test_lotho_triggers_on_the_second_spell_of_any_player(self):
        for caster in (0, 1):
            game = self.cast(caster, CANTRIP, real("Opt Two", "{1}", "Instant", "You gain 1 life."))
            a = game.seats[0]
            self.assertEqual((a.life - (2 if caster == 0 else 0), len([p for p in a.battlefield if p.card.name == "Treasure"])), (39, 1), caster)

    def test_lotho_ignores_the_first_spell(self):
        game = self.cast(1, CANTRIP)
        self.assertEqual((game.seats[0].life, [p for p in game.seats[0].battlefield if p.card.name == "Treasure"]), (40, []))


class CardsTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        cards = (AZUSA, MUSE, ARBOR, WELCOMING, ANARCHOMANCER, AVENGER, PROVISIONER, SCUTE, BATS, BOWMASTERS, PLAGUECRAFTER, MARAUDER, SHEOLDRED, MANIAC,
                 LOTHO, TRACKER)
        self.assertEqual({c.name: unsupported_lines(c) for c in cards if unsupported_lines(c)}, {})


if __name__ == "__main__":
    unittest.main()
