import json
import socket
import threading
import time
import unittest

from infernal_machine.game import CLONE_PROMPT
from infernal_machine.tcp import Disconnected, TimedOut, accept_players, listen


class Client:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port))
        self.reader = self.sock.makefile("r", encoding="utf-8")

    def send(self, message):
        raw = message if isinstance(message, str) else json.dumps(message)
        self.sock.sendall((raw + "\n").encode())

    def recv(self):
        return json.loads(self.reader.readline())

    def close(self):
        self.reader.close()
        self.sock.close()


class TcpTests(unittest.TestCase):
    def setUp(self):
        self.server = listen("127.0.0.1", 0)
        self.port = self.server.getsockname()[1]
        self.clients = []
        self.players = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        for player in self.players:
            player.close()
        self.server.close()

    def connect(self, name=None):
        client = Client(self.port)
        self.clients.append(client)
        if name:
            client.send({"type": "hello", "name": name})
        return client

    def accept(self, count, **kwargs):
        result = {}

        def run():
            result["players"] = accept_players(self.server, count, **kwargs)
            self.players += result["players"]

        thread = threading.Thread(target=run)
        thread.start()
        return thread, result

    def test_seats_players_in_connection_order(self):
        thread, result = self.accept(2)
        alice, bob = self.connect("Alice"), self.connect("Bob")
        thread.join(5)
        self.assertEqual([p.name for p in result["players"]], ["Alice", "Bob"])
        self.assertEqual(alice.recv(), {"type": "welcome", "seat": 0})
        self.assertEqual(bob.recv(), {"type": "welcome", "seat": 1})

    def test_bad_handshake_frees_the_seat(self):
        thread, result = self.accept(1)
        rude = self.connect()
        rude.send({"type": "attack"})
        self.assertEqual(rude.recv()["type"], "error")
        self.connect("Alice")
        thread.join(5)
        self.assertEqual(result["players"][0].name, "Alice")

    def test_stalled_handshake_times_out(self):
        thread, result = self.accept(1, handshake_timeout=0.2)
        self.connect()  # never says hello
        self.connect("Alice")
        thread.join(5)
        self.assertEqual(result["players"][0].name, "Alice")

    def test_choose_retries_until_valid_response(self):
        thread, result = self.accept(1)
        client = self.connect("Alice")
        thread.join(5)
        client.recv()  # welcome
        player = result["players"][0]

        answer = {}
        chooser = threading.Thread(target=lambda: answer.update(i=player.choose("Mulligan?", ["Keep", "Mulligan"])))
        chooser.start()
        prompt = client.recv()
        self.assertEqual(prompt["options"], ["Keep", "Mulligan"])
        client.send("not json")
        self.assertEqual(client.recv()["message"], "Invalid JSON")
        client.send({"type": "response", "id": prompt["id"], "choice": 7})
        self.assertEqual(client.recv()["type"], "error")
        self.assertEqual(client.recv(), prompt)  # re-prompted
        client.send({"type": "response", "id": prompt["id"] - 1, "choice": 0})  # a late answer to an earlier choice
        client.send({"type": "response", "id": prompt["id"], "choice": 1})
        chooser.join(5)
        self.assertEqual(answer["i"], 1)
        player.notify({"event": "ping"})
        self.assertEqual(client.recv(), {"type": "event", "event": "ping"})  # the late answer drew no error

    def test_a_typed_prompt_goes_out_with_its_kind_and_subject_and_a_plain_one_without(self):
        thread, result = self.accept(1)
        client = self.connect("Alice")
        thread.join(5)
        client.recv()  # welcome
        player = result["players"][0]
        for question, expected in ((CLONE_PROMPT("Clone"), {"kind": "clone", "subject": "Clone"}), ("Mulligan?", {})):
            chooser = threading.Thread(target=lambda: player.choose(question, ["Yes", "No"]))
            chooser.start()
            message = client.recv()
            self.assertEqual({k: v for k, v in message.items() if k in ("kind", "subject")}, expected)
            self.assertEqual(message["prompt"], str(question))
            client.send({"type": "response", "id": message["id"], "choice": 0})
            chooser.join(5)

    def test_a_timed_choice_tells_the_client_the_limit_and_gives_up_when_it_passes(self):
        thread, result = self.accept(1)
        client = self.connect("Alice")
        thread.join(5)
        client.recv()  # welcome
        player = result["players"][0]
        with self.assertRaises(TimedOut):
            player.choose("Keep?", ["Keep", "Mulligan"], seconds=0.2)
        self.assertEqual(client.recv()["seconds"], 0.2)
        answer = {}  # the connection is still good: the next, untimed choice waits for its answer
        chooser = threading.Thread(target=lambda: answer.update(i=player.choose("Priority: main1", ["Pass", "Play"])))
        chooser.start()
        prompt = client.recv()
        self.assertNotIn("seconds", prompt)
        time.sleep(0.3)
        client.send({"type": "response", "id": prompt["id"], "choice": 1})
        chooser.join(5)
        self.assertEqual(answer["i"], 1)

    def test_notify_and_disconnect(self):
        thread, result = self.accept(1)
        client = self.connect("Alice")
        thread.join(5)
        client.recv()
        player = result["players"][0]
        player.notify({"event": "draw", "card": "Lightning Bolt"})
        self.assertEqual(client.recv(), {"type": "event", "event": "draw", "card": "Lightning Bolt"})
        client.close()
        self.clients.remove(client)
        with self.assertRaises(Disconnected):
            player.choose("Anything?", ["Yes"])


if __name__ == "__main__":
    unittest.main()
