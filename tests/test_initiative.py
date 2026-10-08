import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import TakeInitiative, ThroneOfTheDeadThree, spell_effects, triggered_abilities
from infernal_machine.game import THRONE_PROMPT, VENTURE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.undercity import ROOMS, START
from tests.test_combat import BEAR, creature
from tests.test_effects import FOREST, lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

UNDERCITY_SCOUT = creature("Scout", 2, 2, "When this creature enters, you take the initiative.")
SPELL = Card(name="Seize", mana_cost="{2}", type_line="Sorcery", oracle_text="You take the initiative.")
GIANT = Card(name="Giant", mana_cost="{4}", type_line="Creature — Giant", power="4", toughness="4")


def route(*rooms):
    """Policy: when asked for a room, take the named one; otherwise the first option."""
    wanted = iter(rooms)

    def policy(prompt, options):
        if prompt == VENTURE_PROMPT:
            room = next(wanted, None)
            return options.index(room) if room else 0
        return 0
    return policy


class RoomTests(unittest.TestCase):
    def test_the_exits_are_the_printed_ones(self):
        # The Undercity as printed: 1-2-3-2-1 rooms, twelve connections (checked against the card, issue 50).
        exits = {name: set(room.leads_to) for name, room in ROOMS.items()}
        self.assertEqual(exits, {
            "Secret Entrance": {"Forge", "Lost Well"},
            "Forge": {"Trap!", "Arena"},
            "Lost Well": {"Arena", "Stash"},
            "Trap!": {"Archives"},
            "Arena": {"Archives", "Catacombs"},
            "Stash": {"Catacombs"},
            "Archives": {"Throne of the Dead Three"},
            "Catacombs": {"Throne of the Dead Three"},
            "Throne of the Dead Three": set(),
        })
        self.assertEqual(sum(len(room) for room in exits.values()), 12)

    def test_every_room_is_understood(self):
        from infernal_machine.effects import line_effects
        for name, room in ROOMS.items():
            if room.text:
                self.assertIsNotNone(line_effects(room.text), name)
            for nxt in room.leads_to:
                self.assertIn(nxt, ROOMS)

    def test_parse(self):
        self.assertEqual(spell_effects(SPELL), [TakeInitiative()])
        self.assertEqual(unsupported_lines(SPELL) + unsupported_lines(UNDERCITY_SCOUT), [])


class VentureTests(unittest.TestCase):
    def test_taking_it_enters_the_first_room_and_runs_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 3
        game.take_initiative(a)
        run_stack(game)
        self.assertEqual((game.initiative, a.undercity_room), (a, START))
        self.assertEqual([c.name for c in a.hand], ["Forest"])  # Secret Entrance fetched a basic land

    def test_a_creature_that_takes_it_when_it_enters(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 3
        game._enter(a, Permanent(UNDERCITY_SCOUT))
        run_stack(game)
        run_stack(game)  # the room's ability follows the trigger
        self.assertIs(game.initiative, a)
        self.assertEqual(len(a.hand), 1)

    def test_already_having_it_does_not_venture_again(self):
        game, _ = table3()
        a = game.seats[0]
        game.take_initiative(a)
        game.take_initiative(a)
        self.assertEqual(len(game.pending), 1)

    def test_the_next_room_is_chosen_from_the_exits(self):
        game, players = table3(route("Lost Well"))
        a = game.seats[0]
        game.take_initiative(a)
        game.venture(a)
        self.assertEqual(a.undercity_room, "Lost Well")
        options = next(o for p, o in players[0].prompts if p == VENTURE_PROMPT)
        self.assertEqual(options, ["Forge", "Lost Well"])

    def test_leaving_forge_leads_to_trap_first(self):
        game, _ = table3(route("Forge"))
        a = game.seats[0]
        game.take_initiative(a)
        game.venture(a)
        self.assertEqual(a.undercity_room, "Forge")
        game.venture(a)  # Forge's exits are Trap! and Arena; the policy takes the first
        self.assertEqual(a.undercity_room, "Trap!")

    def test_the_whole_dungeon_and_starting_again(self):
        game, _ = table3(route("Lost Well", "Stash", "Catacombs"))
        a = game.seats[0]
        a.library = [FOREST] * 5
        game.take_initiative(a)
        for _ in range(4):
            game.venture(a)
        self.assertEqual(a.undercity_room, "Throne of the Dead Three")
        game.venture(a)  # leaving the last room completes it; a new venture starts at the entrance
        self.assertEqual(a.undercity_room, START)
        self.assertTrue(any(e["event"] == "dungeon_completed" for e in game.seats[1].player.events))


class RoomEffectTests(unittest.TestCase):
    def enter(self, room, policy=None):
        game, players = table3(policy)
        a = game.seats[0]
        a.undercity_room = {"Forge": START, "Stash": "Lost Well", "Catacombs": "Stash", "Archives": "Stash",
                            "Trap!": "Forge", "Arena": "Forge"}[room]
        game.initiative = a
        game.venture(a)
        return game, a

    def test_forge(self):
        game, a = self.enter("Forge", route("Forge"))
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        run_stack(game)
        self.assertEqual(bear.counters, {"+1/+1": 2})

    def test_trap_makes_a_player_lose_five(self):
        game, a = self.enter("Trap!", route("Trap!"))
        run_stack(game)
        self.assertEqual(sorted(s.life for s in game.seats), [35, 40, 40])

    def test_stash_and_catacombs_make_tokens(self):
        game, a = self.enter("Stash", route("Stash"))
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Treasure"])
        game, a = self.enter("Catacombs", route("Catacombs"))
        run_stack(game)
        self.assertEqual([(p.card.name, p.card.power) for p in a.battlefield], [("Skeleton", "4")])

    def test_arena_goads(self):
        game, a = self.enter("Arena", route("Arena"))
        theirs = Permanent(BEAR)
        game.seats[1].battlefield = [theirs]
        run_stack(game)
        self.assertIs(theirs.goaded_by, a)

    def test_throne_puts_a_creature_in_with_counters_and_hexproof(self):
        game, players = table3()
        a = game.seats[0]
        a.library = [FOREST, GIANT, BEAR, FOREST] + [FOREST] * 10
        ThroneOfTheDeadThree().resolve(game, a, None)
        giant = a.battlefield[0]
        self.assertEqual((giant.card.name, giant.counters, game.power(giant)), ("Giant", {"+1/+1": 3}, 7))
        self.assertTrue(game.has_keyword(giant, "hexproof"))
        self.assertEqual(next(o for p, o in players[0].prompts if p == THRONE_PROMPT), ["Giant", "Bear"])
        self.assertEqual(len(a.library), 13)
        game.step = "untap"
        game._turn_based_actions(a)  # the hexproof lasts only until their next turn begins
        self.assertFalse(game.has_keyword(giant, "hexproof"))

    def test_throne_with_no_creature_just_shuffles(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 12
        ThroneOfTheDeadThree().resolve(game, a, None)
        self.assertEqual((a.battlefield, len(a.library)), ([], 12))


class InitiativeRulesTests(unittest.TestCase):
    def test_the_holder_ventures_at_their_upkeep(self):
        game, _ = table3()
        a = game.seats[0]
        game.initiative = a
        game.step = "upkeep"
        game._turn_based_actions(a)
        self.assertEqual(a.undercity_room, START)
        game._turn_based_actions(game.seats[1])  # not their upkeep
        self.assertIsNone(game.seats[1].undercity_room)

    def test_combat_damage_to_the_holder_takes_it(self):
        game, _ = table3()
        a, b, c = game.seats
        game.initiative = b
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game.damage(c, 2, bear, combat=True)  # not the holder
        self.assertIs(game.initiative, b)
        game.damage(b, 2, bear, combat=True)
        self.assertIs(game.initiative, a)
        self.assertEqual(a.undercity_room, START)

    def test_noncombat_damage_does_not(self):
        game, _ = table3()
        a, b, _ = game.seats
        game.initiative = b
        game.damage(b, 2, Permanent(BEAR))
        self.assertIs(game.initiative, b)

    def test_the_active_player_takes_it_when_the_holder_loses(self):
        game, _ = table3()
        a, b, c = game.seats
        game.initiative = b
        b.life = 0
        game._check_state()
        self.assertIs(game.initiative, a)
        self.assertEqual(a.undercity_room, START)

    def test_bots_put_forge_counters_on_their_own_creature(self):
        bot = BotPlayer("A", Deck([FOREST], [], []))
        self.assertTrue(bot._is_buff_aura("Forge"))
