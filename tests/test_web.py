"""The browser client (issue #24): the page's view of the game and its answers."""

import http.client
import json
import threading
import unittest

from infernal_machine.web import WebClient, WebServer
from tests.test_effects import table
from tests.test_play import FakeServer


class WebClientTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeServer()
        self.client = WebClient(self.server.client_sock, "Alice", "Commander\n1 X")
        self.thread = threading.Thread(target=self.client.run)
        self.thread.start()
        self.assertEqual(self.server.receive(), {"type": "hello", "name": "Alice", "deck": "Commander\n1 X"})
        self.httpd = WebServer(self.client, port=0, poll_seconds=0.2)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.shutdown)

    def tearDown(self):
        self.server.close()
        self.thread.join(10)

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection(*self.httpd.server_address[:2], timeout=10)
        conn.request(method, path, body=json.dumps(body) if body is not None else None,
                     headers={"Content-Type": "application/json"} if body is not None else {})
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def view(self, since=-1):
        status, data = self.request("GET", f"/state?since={since}")
        self.assertEqual(status, 200)
        return json.loads(data)

    def test_the_page_is_served(self):
        status, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>Infernal Machine</title>", data)
        self.assertEqual(self.request("GET", "/nothing")[0], 404)

    def test_the_view_has_the_welcome_the_board_and_the_prompt_and_a_click_answers(self):
        self.server.send({"type": "welcome", "seat": 0})
        view = self.view()
        self.assertEqual((view["name"], view["me"], view["state"], view["prompt"], view["over"]), ("Alice", 0, None, None, False))
        self.assertIn("Joined the table at seat 0.", view["lines"])
        game, _, _ = table()
        self.server.send({"type": "event", "event": "state", **game.snapshot(game.seats[0])})
        self.server.send({"type": "event", "event": "turn", "turn": 2, "seat": 0})
        self.server.send({"type": "choose", "id": 7, "prompt": "Priority: main1", "options": ["Pass", "Play land: Forest"],
                          "seconds": 45})
        while (view := self.view(view["version"]))["prompt"] is None:
            pass
        self.assertEqual(view["state"]["turn"], 2)
        self.assertEqual([s["name"] for s in view["state"]["seats"]], ["A", "B"])
        self.assertEqual((view["prompt"]["options"], view["prompt"]["seconds"]), (["Pass", "Play land: Forest"], 45))
        self.assertIn("--- Turn 2: your turn ---", view["lines"])
        prompt_id = view["prompt"]["id"]
        self.assertEqual(self.request("POST", "/choose", {"id": prompt_id + 1, "choice": 1})[0], 409)  # not this prompt
        self.assertEqual(self.request("POST", "/choose", {"id": prompt_id, "choice": 5})[0], 409)  # not an option
        self.assertEqual(self.request("POST", "/choose", {"id": prompt_id, "choice": 1})[0], 200)
        self.assertEqual(self.server.receive(), {"type": "response", "id": 7, "choice": 1})
        while (view := self.view(view["version"]))["prompt"] is not None:
            pass
        self.assertEqual(self.request("POST", "/choose", {"id": prompt_id, "choice": 1})[0], 409)  # already answered

    def test_a_timed_prompt_is_given_up_when_its_clock_runs_out(self):
        self.server.send({"type": "choose", "id": 5, "prompt": "Keep this hand?", "options": ["Keep", "Mulligan"], "seconds": 0.2})
        while (view := self.view(-1))["prompt"] is None:
            pass
        self.assertEqual(view["prompt"]["seconds"], 0.2)
        while (view := self.view(view["version"]))["prompt"] is not None:
            pass  # the clock (plus the grace) ran out: the page's answer is no longer waited for
        self.server.send({"type": "choose", "id": 6, "prompt": "Priority: main1", "options": ["Pass", "Play land: Forest"]})
        while (view := self.view(view["version"]))["prompt"] is None:
            pass
        self.assertEqual(self.request("POST", "/choose", {"id": view["prompt"]["id"], "choice": 1})[0], 200)
        self.assertEqual(self.server.receive(), {"type": "response", "id": 6, "choice": 1})  # nothing was sent for 5

    def test_a_pass_only_prompt_is_answered_without_asking_and_closing_ends_the_view(self):
        self.server.send({"type": "choose", "id": 3, "prompt": "Priority: upkeep", "options": ["Pass"]})
        self.assertEqual(self.server.receive(), {"type": "response", "id": 3, "choice": 0})
        view = self.view()
        self.assertIsNone(view["prompt"])
        self.server.close()
        while not (view := self.view(view["version"]))["over"]:
            pass
        self.assertEqual(self.view(view["version"])["over"], True)  # answers at once rather than waiting the poll out


class WebSpectatorTests(unittest.TestCase):
    def test_a_spectator_says_so_in_its_hello_and_sees_the_board_without_a_hand(self):
        server = FakeServer()
        client = WebClient(server.client_sock, "Eve", spectate=True, password="swordfish")
        thread = threading.Thread(target=client.run)
        thread.start()
        self.assertEqual(server.receive(), {"type": "hello", "name": "Eve", "password": "swordfish", "spectate": True})
        server.send({"type": "welcome", "spectator": True})
        game, _, _ = table()
        server.send({"type": "event", "event": "state", **game.snapshot(None)})
        server.send({"type": "event", "event": "turn", "turn": 3, "seat": 1})
        httpd = WebServer(client, port=0, poll_seconds=0.2)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        conn = http.client.HTTPConnection(*httpd.server_address[:2], timeout=10)
        view = {"state": None}
        while view["state"] is None:
            conn.request("GET", "/state?since=-1")
            view = json.loads(conn.getresponse().read())
        conn.close()
        self.assertEqual((view["spectator"], view["prompt"], view["state"]["you"], view["state"]["hand"]), (True, None, -1, []))
        self.assertTrue(any("Watching the table" in line for line in view["lines"]))
        while not any("Turn 3" in line for line in view["lines"]):
            conn = http.client.HTTPConnection(*httpd.server_address[:2], timeout=10)
            conn.request("GET", f"/state?since={view['version']}")
            view = json.loads(conn.getresponse().read())
            conn.close()
        self.assertFalse(any("=== Turn" in line for line in view["lines"]))  # the page draws the board; the log has sentences
        server.close()
        thread.join(10)
