import json
import socket
import threading
import time
import unittest
from contextlib import redirect_stderr
from io import StringIO

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import CachedSource, Card, CardNotFound, Deck, ScryfallSource
from infernal_machine.client import Client, Narrator, render_board
from infernal_machine.game import Game, Permanent
from infernal_machine.server import AutoPilotPlayer, main as server_main, run_table
from infernal_machine.tcp import Disconnected, TcpPlayer, listen
from infernal_machine.cards import load_deck
from tests.test_effects import BEAR, lands, table
from tests.test_game import ScriptedPlayer
from tests.test_triggers import MARTYR

EXAMPLES = "examples"


def offline_source():
    """The demo cards, with any attempt to reach Scryfall a test failure."""
    def no_network(request):
        raise AssertionError("tests must not use the network")
    return CachedSource(ScryfallSource(http=no_network), f"{EXAMPLES}/demo_cards.json")


def demo_deck(name):
    with open(f"{EXAMPLES}/{name}_deck.txt") as f:
        return f.read()


class DictSource:
    def __init__(self, cards):
        self.cards = {c.name.lower(): c for c in cards}

    def get(self, name):
        return self.get_many([name])[name]

    def get_many(self, names):
        missing = [n for n in names if n.lower() not in self.cards]
        if missing:
            raise CardNotFound(", ".join(missing))
        return {n: self.cards[n.lower()] for n in names}


COMMANDER = Card(name="Test Commander", mana_cost="{2}", type_line="Legendary Creature — Test", power="2", toughness="2")
CARDS = [COMMANDER] + [Card(name=f"Card {i}", mana_cost="{1}", type_line="Artifact") for i in range(99)]
LEGAL_DECK = "Commander\n1 Test Commander\n\nDeck\n" + "\n".join(f"1 Card {i}" for i in range(99))
ILLEGAL_DECK = "Commander\n1 Test Commander\n\nDeck\n" + "\n".join(f"1 Card {i}" for i in range(50))


class StatePlayer(ScriptedPlayer):
    wants_state = True


class SnapshotTests(unittest.TestCase):
    def test_opponents_hands_and_libraries_are_counts_only(self):
        game, _, _ = table()
        game.seats[0].hand = [BEAR]
        game.seats[1].hand = [BEAR, BEAR]
        snap = game.snapshot(game.seats[0])
        self.assertEqual(snap["hand"], ["Grizzly Bears"])
        self.assertEqual([s["hand"] for s in snap["seats"]], [1, 2])
        self.assertEqual(snap["seats"][1]["library"], 20)
        self.assertNotIn("Grizzly", json.dumps(snap["seats"][1]))  # nothing about what they hold

    def test_permanents_show_current_stats_counters_and_attachments(self):
        game, _, _ = table()
        bear = Permanent(BEAR, counters={"+1/+1": 2}, tapped=True)
        boots = Permanent(Card(name="Sword", type_line="Artifact — Equipment", oracle_text="Equipped creature gets +1/+1."),
                          attached_to=bear)
        game.seats[0].battlefield = [bear, boots] + lands(1)
        view = {p["name"]: p for p in game.snapshot(game.seats[0])["seats"][0]["battlefield"]}
        bears = view["Grizzly Bears"]
        self.assertEqual((bears["power"], bears["toughness"], bears["tapped"]), (5, 5, True))  # 2/2, +2 counters, +1/+1 Sword
        self.assertEqual(bears["counters"], {"+1/+1": 2})
        self.assertEqual((view["Sword"]["attached_to"], view["Sword"]["power"]), ("Grizzly Bears", None))

    def test_stack_shows_real_card_names(self):
        game, _, _ = table()
        game.seats[0].battlefield = [Permanent(MARTYR)]
        game.trigger("dies", game.seats[0].battlefield[0], game.seats[0])
        game._put_triggers_on_stack()
        self.assertEqual(game.snapshot(game.seats[0])["stack"][0]["ability"], "When Martyr dies, you gain 3 life.")

    def test_state_goes_only_to_players_who_want_it_and_before_their_decision(self):
        a, b = StatePlayer("A"), ScriptedPlayer("B")
        deck = Deck([COMMANDER], [BEAR] * 30, [])
        game = Game([(a, deck), (b, deck)], seed=1)
        game.setup()
        a.events.clear()
        game._priority_round(game.seats[game.active])
        self.assertTrue(all(e["event"] != "state" for e in b.events))
        first = next(e for e in a.events if e["event"] == "state")
        self.assertEqual(first["you"], 0)
        self.assertEqual(len(first["hand"]), 7)
        self.assertEqual([s["name"] for s in first["seats"]], ["A", "B"])
        json.dumps(first)  # must be plain data

    def test_snapshots_from_a_whole_game_are_json(self):
        class Recorder(BotPlayer):
            wants_state = True

            def __init__(self, name, deck):
                super().__init__(name, deck)
                self.states = []

            def notify(self, event):
                super().notify(event)
                if event["event"] == "state":
                    self.states.append(json.dumps(event))

        src = offline_source()
        green, red = load_deck(demo_deck("green"), src), load_deck(demo_deck("red"), src)
        a, b = Recorder("A", green), BotPlayer("B", red)
        Game([(a, green), (b, red)], seed=2).play(max_turns=6)
        self.assertGreater(len(a.states), 10)


class DisplayTests(unittest.TestCase):
    def test_render_board(self):
        game, _, _ = table()
        seat = game.seats[0]
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        seat.battlefield = [bear, Permanent(Card(name="Sword", type_line="Artifact — Equipment"), attached_to=bear)] + lands(2)
        seat.hand = [BEAR, BEAR]
        game.seats[1].commander_names = {"Omnath"}
        text = render_board(game.snapshot(seat))
        self.assertIn("A (you): life 40 | hand 2 | library 20", text)
        self.assertIn("Lands: City of Brass x2", text)
        self.assertIn("Grizzly Bears 3/3 [1 +1/+1 counter]", text)
        self.assertIn("Sword [on Grizzly Bears]", text)
        self.assertIn("Your hand: 1. Grizzly Bears, 2. Grizzly Bears", text)

    def test_every_event_a_real_game_produces_reads_as_a_sentence(self):
        class Narrating(BotPlayer):
            def __init__(self, name, deck):
                super().__init__(name, deck)
                self.narrator = Narrator()
                self.lines = []

            def notify(self, event):
                super().notify(event)
                if event["event"] == "seat" and event["name"] == self.name:
                    self.narrator.me = event["seat"]
                if line := self.narrator.narrate(event):
                    self.lines.append(line)

        src = offline_source()
        green, red = load_deck(demo_deck("green"), src), load_deck(demo_deck("red"), src)
        players = [Narrating("A", green), Narrating("B", red), Narrating("C", red)]
        Game([(p, d) for p, d in zip(players, (green, red, red))], seed=4).play(max_turns=40)
        lines = players[0].lines
        self.assertGreater(len(lines), 200)
        self.assertEqual([line for line in lines if line.startswith("{")], [])  # none fell back to raw JSON
        self.assertEqual([line for line in lines if ".." in line or "CARDNAME" in line], [])

    def test_perspective_and_fallback(self):
        n = Narrator()
        n.me = 0
        n.narrate({"event": "seat", "seat": 0, "name": "Alice", "life": 40, "commanders": []})
        n.narrate({"event": "seat", "seat": 1, "name": "Bob", "life": 40, "commanders": []})
        self.assertEqual(n.narrate({"event": "cast", "seat": 0, "card": "Bolt", "from": "hand", "targets": [], "x": 0}),
                         "You cast Bolt.")
        self.assertEqual(n.narrate({"event": "cast", "seat": 1, "card": "Bolt", "from": "hand", "targets": ["Player: Alice (seat 0)"], "x": 0}),
                         "Bob casts Bolt targeting Player: Alice (seat 0).")
        self.assertEqual(n.narrate({"event": "turn", "turn": 3, "seat": 1}), "\n--- Turn 3: Bob's turn ---")
        self.assertEqual(n.narrate({"event": "trigger", "seat": 1, "card": "Kaelen", "ability": "Whenever Kaelen attacks, each opponent loses 1 life.", "targets": []}),
                         "Kaelen triggers for Bob: Whenever Kaelen attacks, each opponent loses 1 life.")
        self.assertEqual(n.narrate({"event": "brand_new", "x": 1}), '{"event":"brand_new","x":1}')


class FakeServer:
    """The other end of a client's socket, for scripted exchanges."""

    def __init__(self):
        self.client_sock, self.sock = socket.socketpair()
        self.client_sock.settimeout(10)
        self.sock.settimeout(10)
        self.reader = self.sock.makefile("r", encoding="utf-8")

    def send(self, message):
        self.sock.sendall((json.dumps(message) + "\n").encode())

    def receive(self):
        return json.loads(self.reader.readline())

    def close(self):
        self.reader.close()
        self.sock.close()


class ClientTests(unittest.TestCase):
    def run_client(self, messages, answers, **kwargs):
        server, shown, answers = FakeServer(), [], iter(answers)
        client = Client(server.client_sock, "Alice", "Commander\n1 X", ask=lambda hint: next(answers), show=shown.append, **kwargs)
        thread = threading.Thread(target=client.run)
        thread.start()
        hello = server.receive()
        replies = []
        for message in messages:
            server.send(message)
            if message["type"] == "choose" and not (client.auto_pass and message["options"] == ["Pass"]):
                replies.append(server.receive())
        if kwargs.get("auto_pass", True):
            replies += [server.receive() for m in messages if m["type"] == "choose" and m["options"] == ["Pass"]]
        server.close()
        thread.join(10)
        return hello, replies, shown

    def test_hello_carries_the_deck(self):
        hello, _, _ = self.run_client([], [])
        self.assertEqual(hello, {"type": "hello", "name": "Alice", "deck": "Commander\n1 X"})

    def test_numbers_are_one_based_and_bad_input_is_asked_again(self):
        choose = {"type": "choose", "id": 7, "prompt": "Keep this hand?", "options": ["Keep", "Mulligan"]}
        _, replies, shown = self.run_client([choose], ["", "9", "abc", "2"])
        self.assertEqual(replies, [{"type": "response", "id": 7, "choice": 1}])
        self.assertEqual(sum("Enter a number from 1 to 2" in line for line in shown), 3)

    def test_enter_passes_at_a_priority_prompt(self):
        choose = {"type": "choose", "id": 1, "prompt": "Priority: main1", "options": ["Pass", "Play land: Forest"]}
        _, replies, _ = self.run_client([choose], [""])
        self.assertEqual(replies[0]["choice"], 0)

    def test_prompts_with_only_pass_are_answered_for_you(self):
        choose = {"type": "choose", "id": 3, "prompt": "Priority: upkeep", "options": ["Pass"]}
        _, replies, shown = self.run_client([choose], [])  # no answers available: it must not ask
        self.assertEqual(replies, [{"type": "response", "id": 3, "choice": 0}])
        self.assertNotIn("Priority: upkeep", "\n".join(shown))

    def test_the_board_key_shows_the_board(self):
        game, _, _ = table()
        state = {"type": "event", **{"event": "state", **game.snapshot(game.seats[0])}}
        choose = {"type": "choose", "id": 1, "prompt": "Priority: main1", "options": ["Pass", "Play land: Forest"]}
        _, _, shown = self.run_client([state, choose], ["b", "1"])
        self.assertEqual(sum("=== Turn 2, main1" in line for line in shown), 2)  # once automatically, once on request

    def test_server_errors_are_shown(self):
        _, _, shown = self.run_client([{"type": "error", "message": "Your deck was rejected:\n- 98 cards"}], [])
        self.assertIn("Server: Your deck was rejected:\n- 98 cards", shown)


def wait_for(lines, text, seconds=10):
    """Block until some line contains `text`, so a test can rely on who joined first."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if any(text in line for line in lines):
            return
        time.sleep(0.01)
    raise AssertionError(f"never saw {text!r} in {lines[-5:]}")


class TableHarness:
    """A real server on a real socket, running a game in a thread."""

    def __init__(self, test, humans, bot_decks, source, check=True, max_turns=3, seed=1):
        self.server = listen("127.0.0.1", 0)
        self.server.settimeout(15)
        self.port = self.server.getsockname()[1]
        self.log, self.result, self.error = [], {}, []

        def run():
            try:
                self.result["winner"] = run_table(self.server, humans, bot_decks, source, seed=seed, check_decks=check,
                                                  max_turns=max_turns, log=self.log.append)
            except BaseException as err:  # reported by finish()
                self.error.append(err)

        self.thread = threading.Thread(target=run)
        self.thread.start()
        test.addCleanup(self.server.close)

    def client(self, name, deck, answer="1"):
        """Connect a client that answers every question with `answer`; returns (thread, lines)."""
        lines = []

        def run():
            sock = socket.create_connection(("127.0.0.1", self.port))
            sock.settimeout(20)
            Client(sock, name, deck, ask=lambda hint: answer, show=lines.append).run()

        thread = threading.Thread(target=run)
        thread.start()
        return thread, lines

    def finish(self, *client_threads):
        for thread in client_threads:
            thread.join(20)
        self.thread.join(20)
        if self.error:
            raise self.error[0]
        assert not self.thread.is_alive(), "the server never finished"
        return self.result.get("winner"), self.log


class ServerTests(unittest.TestCase):
    def test_a_human_plays_a_whole_game_against_a_bot_over_tcp(self):
        src = offline_source()
        table_ = TableHarness(self, 1, [demo_deck("red")], src, check=False, max_turns=12)
        thread, lines = table_.client("Alice", demo_deck("green"))
        winner, log = table_.finish(thread)
        self.assertIn("Joined the table at seat 0.", lines)
        self.assertTrue(any(line.startswith("Seat 1: Bot 1") for line in lines))
        self.assertTrue(any("=== Turn" in line for line in lines))  # the board was shown at a real decision
        self.assertTrue(any("Game over" in line for line in lines))
        self.assertIn("Alice joined (1/1)", log)
        self.assertTrue(any(entry.startswith("Game over") for entry in log))

    def test_illegal_deck_is_rejected_and_the_seat_stays_open(self):
        table_ = TableHarness(self, 1, [LEGAL_DECK], DictSource(CARDS))
        bad, bad_lines = table_.client("Mallory", ILLEGAL_DECK)
        bad.join(20)
        self.assertTrue(any("Your deck was rejected" in line and "needs exactly 100" in line for line in bad_lines))
        good, good_lines = table_.client("Alice", LEGAL_DECK)
        table_.finish(good)
        self.assertIn("Joined the table at seat 0.", good_lines)

    def test_unknown_cards_and_missing_decks_are_explained(self):
        table_ = TableHarness(self, 1, [LEGAL_DECK], DictSource(CARDS))
        t1, typo = table_.client("Bob", "Commander\n1 Test Commander\n\nDeck\n1 Nonexistent Card")
        t1.join(20)
        self.assertTrue(any("Nonexistent Card" in line for line in typo))
        t2, none = table_.client("Bob", None)
        t2.join(20)
        self.assertTrue(any('Send your decklist' in line for line in none))
        good, _ = table_.client("Alice", LEGAL_DECK)
        table_.finish(good)

    def test_names_must_be_unique(self):
        table_ = TableHarness(self, 2, [], DictSource(CARDS), max_turns=2)
        first, first_lines = table_.client("Alice", LEGAL_DECK)
        wait_for(first_lines, "Joined the table")  # so the second Alice really is the duplicate
        dup, dup_lines = table_.client("Alice", LEGAL_DECK)
        dup.join(20)
        self.assertTrue(any("already taken" in line for line in dup_lines))
        second, _ = table_.client("Bob", LEGAL_DECK)
        table_.finish(first, second)

    def test_a_bot_takes_over_when_a_human_disconnects(self):
        src = offline_source()
        table_ = TableHarness(self, 1, [demo_deck("red")], src, check=False, max_turns=15)
        lines = []

        def quitter():
            sock = socket.create_connection(("127.0.0.1", table_.port))
            sock.settimeout(20)

            def leave(hint):
                raise EOFError
            Client(sock, "Alice", demo_deck("green"), ask=leave, show=lines.append).run()

        thread = threading.Thread(target=quitter)
        thread.start()
        winner, log = table_.finish(thread)
        self.assertTrue(any("a bot will play your seat" in line for line in lines))
        self.assertTrue(any(entry.startswith("Game over") for entry in log))

    def test_bad_arguments(self):
        for argv in (["--bots", "1", "--humans", "1"], ["--bots", "0", "--humans", "1"]):
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                server_main(argv)

    def test_a_table_needs_two_players(self):
        server = listen("127.0.0.1", 0)
        self.addCleanup(server.close)
        with self.assertRaises(ValueError):
            run_table(server, 1, [], DictSource(CARDS))


class AutoPilotTests(unittest.TestCase):
    def test_bot_answers_after_the_human_drops(self):
        class Gone:
            name = "Alice"

            def notify(self, event):
                raise Disconnected("Alice")

            def choose(self, prompt, options):
                raise Disconnected("Alice")

        pilot = AutoPilotPlayer(Gone(), BotPlayer("Alice", Deck([COMMANDER], [BEAR] * 5, [])))
        pilot.notify({"event": "seat", "seat": 0, "name": "Alice", "life": 40, "commanders": []})
        self.assertTrue(pilot.disconnected)
        self.assertEqual(pilot.choose("Priority: main1", ["Pass"]), 0)


class ProtocolTests(unittest.TestCase):
    def test_hello_keeps_the_deck_and_handshake_still_works_without_one(self):
        a, b = socket.socketpair()
        b.settimeout(5)
        player = TcpPlayer(a)
        b.sendall(b'{"type": "hello", "name": "Alice", "deck": "1 Forest"}\n')
        player.handshake(0)
        self.assertEqual((player.name, player.hello["deck"]), ("Alice", "1 Forest"))
        self.assertEqual(json.loads(b.makefile().readline()), {"type": "welcome", "seat": 0})
        a.close()
        b.close()


if __name__ == "__main__":
    unittest.main()
