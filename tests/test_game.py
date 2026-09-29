import json
import socket
import threading
import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.game import PASS, STARTING_LIFE, Game
from infernal_machine.tcp import accept_players, listen

LAND = Card(name="Wastes", type_line="Basic Land")
SPELL = Card(name="Sol Ring", type_line="Artifact")


class ScriptedPlayer:
    """Answers prompts from a policy function and records every event."""

    def __init__(self, name, policy=None):
        self.name = name
        self.events = []
        self.prompts = []
        self.policy = policy or (lambda prompt, options: 0)

    def notify(self, event):
        self.events.append(event)

    def choose(self, prompt, options):
        self.prompts.append((prompt, list(options)))
        return self.policy(prompt, options)


def deck(lands=40, spells=59):
    commander = Card(name="Commander", type_line="Legendary Creature — Golem")
    return Deck(commanders=[commander], main=[LAND] * lands + [SPELL] * spells, sideboard=[])


def play_lands(prompt, options):
    """Keep, then play a land whenever possible, otherwise pass."""
    for i, option in enumerate(options):
        if option.startswith("Play land"):
            return i
    return 0


class GameTests(unittest.TestCase):
    def test_setup(self):
        a, b, c = ScriptedPlayer("A"), ScriptedPlayer("B"), ScriptedPlayer("C")
        game = Game([(p, deck()) for p in (a, b, c)], seed=1)
        game.setup()
        for seat in game.seats:
            self.assertEqual(seat.life, STARTING_LIFE)
            self.assertEqual([card.name for card in seat.command_zone], ["Commander"])
            self.assertEqual(len(seat.hand), 7)
            self.assertEqual(len(seat.library), 92)
        self.assertEqual(a.events[0]["event"], "seat")

    def test_first_mulligan_is_free_in_multiplayer(self):
        answers = iter([1, 1, 0, 0])  # mulligan, mulligan, keep, bottom one card
        mull = ScriptedPlayer("A", lambda prompt, options: next(answers))
        others = [ScriptedPlayer("B"), ScriptedPlayer("C")]
        game = Game([(p, deck()) for p in (mull, *others)], seed=1)
        game.setup()
        self.assertEqual(len(game.seats[0].hand), 6)
        self.assertEqual(len(game.seats[0].library), 93)

    def test_no_free_mulligan_in_two_player(self):
        answers = iter([1, 0, 0])  # mulligan, keep, bottom one card
        game = Game([(ScriptedPlayer("A", lambda p, o: next(answers)), deck()), (ScriptedPlayer("B"), deck())], seed=1)
        game.setup()
        self.assertEqual(len(game.seats[0].hand), 6)

    def test_one_land_per_turn_only_for_active_player_in_main_phase(self):
        a, b = ScriptedPlayer("A", play_lands), ScriptedPlayer("B", play_lands)
        game = Game([(a, deck(lands=99, spells=0)), (b, deck(lands=99, spells=0))], seed=3)
        game.play(max_turns=4)
        plays = [e for e in a.events if e["event"] == "play_land"]
        self.assertEqual(len(plays), 4)
        for seat in game.seats:
            self.assertEqual(len(seat.battlefield), 2)
        land_prompts = [p for p in a.prompts + b.prompts if any(o.startswith("Play land") for o in p[1])]
        self.assertTrue(all(prompt in ("Priority: main1", "Priority: main2") for prompt, _ in land_prompts))

    def test_first_player_skips_draw_only_in_two_player(self):
        for count, expected_draws in ((2, 0), (3, 1)):
            players = [ScriptedPlayer(str(i)) for i in range(count)]
            game = Game([(p, deck()) for p in players], seed=5)
            game.play(max_turns=1)
            first = game.seats[next(e["seat"] for e in players[0].events if e["event"] == "starting_player")]
            draws = [e for e in first.player.events if e["event"] == "draw"]
            self.assertEqual(len(draws), expected_draws, f"{count} players")

    def test_cleanup_discards_to_hand_size(self):
        players = [ScriptedPlayer(str(i)) for i in range(3)]
        game = Game([(p, deck()) for p in players], seed=5)
        game.play(max_turns=1)
        first = game.seats[next(e["seat"] for e in players[0].events if e["event"] == "starting_player")]
        self.assertEqual(len(first.hand), 7)
        self.assertEqual(len(first.graveyard), 1)

    def test_decking_loses_and_last_player_wins(self):
        a, b = ScriptedPlayer("A"), ScriptedPlayer("B")
        game = Game([(a, deck(lands=7, spells=0)), (b, deck())], seed=2)
        winner = game.play()
        self.assertEqual(winner.name, "B")
        lost = next(e for e in b.events if e["event"] == "player_lost")
        self.assertEqual((lost["seat"], lost["reason"]), (0, "empty_library"))

    def test_other_players_do_not_see_drawn_cards(self):
        a, b = ScriptedPlayer("A"), ScriptedPlayer("B")
        Game([(a, deck()), (b, deck())], seed=4).play(max_turns=3)
        for player in (a, b):
            for event in player.events:
                if event["event"] == "drew":
                    self.assertNotIn("card", event)

    def test_priority_passes_around_the_table(self):
        players = [ScriptedPlayer(str(i)) for i in range(4)]
        Game([(p, deck(lands=0, spells=99)) for p in players], seed=6).play(max_turns=1)
        for p in players:
            priority = [options for prompt, options in p.prompts if prompt.startswith("Priority")]
            # 12 steps minus untap and cleanup, and blockers and damage are skipped with no attackers.
            self.assertEqual(len(priority), 8)
            self.assertTrue(all(options == [PASS] for options in priority))

    def test_game_over_tcp(self):
        server = listen("127.0.0.1", 0)
        port = server.getsockname()[1]
        received = []

        def client():
            with socket.create_connection(("127.0.0.1", port)) as sock, sock.makefile("r") as reader:
                sock.sendall(b'{"type": "hello", "name": "Remote"}\n')
                for line in reader:
                    message = json.loads(line)
                    received.append(message)
                    if message["type"] == "choose":
                        reply = {"type": "response", "id": message["id"], "choice": 0}
                        sock.sendall((json.dumps(reply) + "\n").encode())

        thread = threading.Thread(target=client)
        thread.start()
        [remote] = accept_players(server, 1)
        local = ScriptedPlayer("Local")
        try:
            winner = Game([(remote, deck(lands=7, spells=0)), (local, deck())], seed=2).play()
        finally:
            remote.close()
            server.close()
        thread.join(5)
        self.assertEqual(winner.name, "Local")
        self.assertEqual(received[-1]["event"], "game_over")
        self.assertTrue(any(m["type"] == "event" and m["event"] == "opening_hand" for m in received))


if __name__ == "__main__":
    unittest.main()
