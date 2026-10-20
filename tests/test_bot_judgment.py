import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.combat import ATTACK_PROMPT, BLOCK_PROMPT
from infernal_machine.game import CAST, CAST_COMMANDER, PASS, PLAY_LAND, TARGET_PROMPT

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
TAPPED = Card(name="Tapped Peaks", type_line="Land", produced_mana=("R",), oracle_text="This land enters tapped.\n{T}: Add {R}.")
BOLT = Card(name="Lightning Bolt", mana_cost="{R}", cmc=1, type_line="Instant", oracle_text="Lightning Bolt deals 3 damage to any target.")
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
THREE = Card(name="Three Drop", mana_cost="{2}{R}", cmc=3, type_line="Creature — Imp", power="2", toughness="2")
TWO_A = Card(name="Two Drop A", mana_cost="{1}{R}", cmc=2, type_line="Creature — Imp", power="1", toughness="1")
TWO_B = Card(name="Two Drop B", mana_cost="{1}{R}", cmc=2, type_line="Creature — Imp", power="1", toughness="1")
FLIER = Card(name="Skyknight", mana_cost="{1}{W}", cmc=2, type_line="Creature — Knight", power="2", toughness="2", oracle_text="Flying")
FOUR = Card(name="Four Drop", mana_cost="{3}{R}", cmc=4, type_line="Creature — Imp", power="2", toughness="2")
FIVE = Card(name="Five Drop", mana_cost="{4}{R}", cmc=5, type_line="Creature — Imp", power="3", toughness="3")
COMMANDER = Card(name="Boss", mana_cost="{3}{R}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3")
DECK = Deck([COMMANDER], [MOUNTAIN, PLAINS, TAPPED, BOLT, BEAR, THREE, TWO_A, TWO_B, FLIER, FOUR, FIVE], [])


def permanent(name, kind="Creature", power=None, toughness=None, tapped=False, sick=False):
    return {"name": name, "type": kind, "tapped": tapped, "sick": sick, "power": power, "toughness": toughness}


def bot(mine, theirs=(), hand=(), life=20, their_life=20, features=FEATURES):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": life})
    b.notify({"event": "state", "hand": list(hand), "seats": [
        {"seat": 0, "lost": False, "life": life, "mana_pool": [], "battlefield": list(mine)},
        {"seat": 1, "lost": False, "life": their_life, "mana_pool": [], "battlefield": list(theirs)}]})
    return b


def lands(n, name="Mountain"):
    return [permanent(name, "Basic Land") for _ in range(n)]


def attack_choice(b, creature="Grizzly Bears 2/2 (seat 0, #5)"):
    return b.choose(ATTACK_PROMPT(creature), ["Don't attack", "Attack Player: Foe (seat 1)"])


class TimingTests(unittest.TestCase):
    OPTIONS = [PASS, "Activate: Mind Stone (seat 0, #2): {T}: Draw a card."]

    def test_a_tapping_ability_waits_for_the_second_main_phase(self):
        self.assertEqual(bot(lands(3)).choose("Priority: upkeep", self.OPTIONS), 0)
        self.assertEqual(bot(lands(3)).choose("Priority: main1", self.OPTIONS), 0)
        self.assertEqual(bot(lands(3)).choose("Priority: main2", self.OPTIONS), 1)

    def test_a_loyalty_ability_may_go_in_the_first_main_phase(self):
        options = [PASS, "Activate: Jace (seat 0, #2): +1: Draw a card."]
        self.assertEqual(bot(lands(3)).choose("Priority: main1", options), 1)
        self.assertEqual(bot(lands(3)).choose("Priority: upkeep", options), 0)

    def test_without_the_feature_it_taps_whenever(self):
        self.assertEqual(bot(lands(3), features=frozenset()).choose("Priority: upkeep", self.OPTIONS), 1)


class AttackTests(unittest.TestCase):
    def test_stays_home_when_a_bigger_blocker_would_kill_it(self):
        b = bot([permanent("Grizzly Bears", power=2, toughness=2), permanent("Other", power=2, toughness=2, sick=True)],
                [permanent("Ogre", power=3, toughness=3)])
        self.assertEqual(attack_choice(b), 0)

    def test_attacks_when_no_one_can_block(self):
        self.assertEqual(attack_choice(bot([permanent("Grizzly Bears", power=2, toughness=2)], [])), 1)

    def test_attacks_into_a_blocker_it_trades_with_or_beats(self):
        b = bot([permanent("Grizzly Bears", power=2, toughness=2)], [permanent("Wall", power=0, toughness=4), permanent("Cub", power=2, toughness=2)])
        self.assertEqual(attack_choice(b), 1)

    def test_attacks_for_lethal_whatever_blocks(self):
        b = bot([permanent("Grizzly Bears", power=2, toughness=2)], [permanent("Ogre", power=3, toughness=3)], their_life=2)
        self.assertEqual(attack_choice(b), 1)

    def test_a_flier_attacks(self):
        b = bot([permanent("Skyknight", power=2, toughness=2)], [permanent("Ogre", power=3, toughness=3)])
        self.assertEqual(attack_choice(b, "Skyknight 2/2 (seat 0, #5)"), 1)

    def test_stays_home_when_the_opponents_board_threatens_lethal(self):
        b = bot([permanent("Grizzly Bears", power=2, toughness=2)], [permanent("Giant", power=4, toughness=1, tapped=True)], life=4)
        self.assertEqual(attack_choice(b), 0)

    def test_without_the_feature_it_always_attacks(self):
        b = bot([permanent("Grizzly Bears", power=2, toughness=2)], [permanent("Ogre", power=3, toughness=3)], features=frozenset())
        self.assertEqual(attack_choice(b), 1)


class LandTests(unittest.TestCase):
    def test_plays_the_land_whose_color_the_hand_needs(self):
        options = [PASS, PLAY_LAND + "Plains", PLAY_LAND + "Mountain"]
        self.assertEqual(bot(lands(2, "Plains"), hand=["Plains", "Mountain", "Three Drop"]).choose("Priority: main1", options), 2)
        self.assertEqual(bot(lands(2, "Mountain"), hand=["Plains", "Mountain", "Skyknight"]).choose("Priority: main1", options), 1)

    def test_prefers_an_untapped_land_when_colors_tie(self):
        options = [PASS, PLAY_LAND + "Tapped Peaks", PLAY_LAND + "Mountain"]
        self.assertEqual(bot([], hand=["Tapped Peaks", "Mountain", "Lightning Bolt"]).choose("Priority: main1", options), 2)


class TargetTests(unittest.TestCase):
    def test_removal_goes_on_the_biggest_opposing_creature(self):
        options = ["Wall 0/4 (seat 1, #3)", "Ogre 5/5 (seat 1, #4)", "Bears 2/2 (seat 0, #5)"]
        self.assertEqual(bot(lands(1)).choose(TARGET_PROMPT(BOLT.name), options), 1)

    def test_other_targets_keep_the_first_choice(self):
        options = ["Wall 0/4 (seat 1, #3)", "Ogre 5/5 (seat 1, #4)"]
        self.assertEqual(bot(lands(1)).choose(TARGET_PROMPT(BEAR.name), options), 0)


class ManaTests(unittest.TestCase):
    def test_casts_the_combination_that_spends_the_most(self):
        options = [PASS, CAST + THREE.name, CAST + TWO_A.name, CAST + TWO_B.name]
        self.assertIn(bot(lands(4)).choose("Priority: main1", options), (2, 3))  # two 2-drops spend 4; the 3-drop spends 3
        self.assertEqual(bot(lands(3)).choose("Priority: main1", options), 1)  # three mana: the 3-drop spends all of it
        self.assertEqual(bot(lands(4), features=frozenset()).choose("Priority: main1", options), 1)

    def test_falls_back_to_the_biggest_when_it_cannot_count_the_mana(self):
        options = [PASS, CAST + THREE.name, CAST + TWO_A.name]
        self.assertEqual(bot([]).choose("Priority: main1", options), 1)  # no lands seen, yet the game says it can cast


def pod(mine, tax=0, damage_to_me=(), damage_dealt=0, life=40):
    """A bot (seat 0) in a three-player pod: seat 1 has taken `damage_dealt` from the bot's commander, seat 2 is on less life."""
    b = BotPlayer("Bot", DECK)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": life})
    b.notify({"event": "seat", "seat": 1, "name": "Foe", "life": 30})
    b.notify({"event": "seat", "seat": 2, "name": "Bar", "life": 12})
    b.notify({"event": "state", "hand": [], "seats": [
        {"seat": 0, "lost": False, "life": life, "mana_pool": [], "battlefield": list(mine), "command_zone": [{"name": "Boss", "tax": tax}],
         "commander_damage": list(damage_to_me)},
        {"seat": 1, "lost": False, "life": 30, "mana_pool": [], "battlefield": [], "command_zone": [],
         "commander_damage": [{"from_seat": 0, "commander": "Boss", "damage": damage_dealt}] if damage_dealt else []},
        {"seat": 2, "lost": False, "life": 12, "mana_pool": [], "battlefield": [], "command_zone": [], "commander_damage": []}]})
    return b


class CommanderTests(unittest.TestCase):
    CASTS = [PASS, CAST_COMMANDER + "Boss", CAST + FIVE.name, CAST + FOUR.name]

    def test_a_cheap_commander_is_cast_first(self):
        self.assertEqual(pod(lands(9), tax=2).choose("Priority: main1", self.CASTS), 1)
        self.assertEqual(pod(lands(9), tax=0).choose("Priority: main1", self.CASTS), 1)

    def test_an_expensive_commander_competes_with_the_rest(self):
        # Nine mana: the commander at tax 4 costs 8, the five-drop and four-drop together spend all nine.
        self.assertEqual(pod(lands(9), tax=4).choose("Priority: main1", self.CASTS), 2)
        self.assertEqual(pod(lands(9), tax=4).features & {"commander"}, {"commander"})

    def test_without_the_feature_it_always_casts_the_commander_first(self):
        b = pod(lands(9), tax=4)
        b.features = b.features - {"commander"}
        self.assertEqual(b.choose("Priority: main1", self.CASTS), 1)

    def test_the_commander_attacks_the_player_it_can_finish(self):
        options = ["Don't attack", "Attack Player: Foe (seat 1)", "Attack Player: Bar (seat 2)"]
        boss = permanent("Boss", power=3, toughness=3)
        self.assertEqual(pod([boss], damage_dealt=18).choose(ATTACK_PROMPT + "Boss 3/3 (seat 0, #5)", options), 1)  # 18 + 3 = 21
        self.assertEqual(pod([boss], damage_dealt=10).choose(ATTACK_PROMPT + "Boss 3/3 (seat 0, #5)", options), 2)  # not enough: the lowest life
        self.assertEqual(pod([boss, permanent("Imp", power=2, toughness=2)], damage_dealt=18).choose(ATTACK_PROMPT + "Imp 2/2 (seat 0, #6)", options), 2)

    def test_it_blocks_the_commander_that_would_kill_it(self):
        options = ["Don't block", "Foe Boss 3/3 (seat 1, #9)", "Other 2/2 (seat 1, #8)"]
        hurt = [{"from_seat": 1, "commander": "Foe Boss", "damage": 19}]
        self.assertEqual(pod([], damage_to_me=hurt).choose(BLOCK_PROMPT + "Wall 0/2 (seat 0, #3)", options), 1)
        fine = [{"from_seat": 1, "commander": "Foe Boss", "damage": 5}]  # nowhere near 21, and the wall would die: no block
        self.assertEqual(pod([], damage_to_me=fine).choose(BLOCK_PROMPT + "Wall 0/2 (seat 0, #3)", options), 0)


if __name__ == "__main__":
    unittest.main()
