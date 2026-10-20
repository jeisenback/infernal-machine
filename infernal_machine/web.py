"""Browser client for a game server: the board, the log and your choices as buttons, on a local web page.

    python -m infernal_machine.web --name Alice --deck deck.txt [--host H] [--port P] [--listen 8765] [--no-browser]
    python -m infernal_machine.web --spectate [--host H] [--port P]        (watch: no name or deck needed)

It joins the table like the terminal client and serves the page at http://127.0.0.1:8765 with nothing beyond the
standard library. The page asks the client for changes (long polling) and a click answers the open prompt.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

from .client import Client

PAGE = Path(__file__).with_name("web.html")
LOG_LINES = 300  # how much of the log the page is given
POLL_SECONDS = 25.0  # how long a request for changes may wait before answering "nothing new"
CLOCK_GRACE = 1.0  # how long after a timed prompt's clock the client keeps waiting for the page before giving up


class WebClient(Client):
    """A client whose player sits at a browser: it keeps the latest board, the log and the open prompt for the page,
    and `decide` waits for the page's answer. The game socket is read on one thread; the web server's threads call
    `view` and `answer`."""

    def __init__(self, sock: socket.socket, name: str, deck_text: str | None = None, auto_pass: bool = True,
                 spectate: bool = False, password: str | None = None):
        super().__init__(sock, name, deck_text, show=self._add_line, auto_pass=auto_pass, spectate=spectate,
                         password=password)
        self.board_as_text = False  # the page draws the board; the log is only sentences
        self.lines: list[str] = []
        self.prompt: dict | None = None  # {"id", "prompt", "options"} while a decision is open
        self.over = False  # the game socket closed
        self.version = 0  # grows with every change the page should see
        self._changed = threading.Condition()
        self._prompt_id = 0
        self._answer: int | None = None

    def run(self) -> None:
        try:
            super().run()
        finally:
            with self._changed:
                self.over = True
                self._bump()

    def _bump(self) -> None:
        self.version += 1
        self._changed.notify_all()

    def _add_line(self, text: str) -> None:
        with self._changed:
            self.lines = (self.lines + [text.strip("\n")])[-LOG_LINES:]
            self._bump()

    def _event(self, message: dict) -> None:
        super()._event(message)
        if message.get("event") == "state":
            with self._changed:
                self._bump()

    def decide(self, prompt: str, options: list[str], seconds: float | None = None) -> int | None:
        """Wait for the page's answer. With a clock, only until it runs out (a little longer, so the server's own
        clock goes first): then None, and the events the server sent meanwhile are read."""
        with self._changed:
            self._prompt_id += 1
            self.prompt = {"id": self._prompt_id, "prompt": str(prompt), "options": list(options), "seconds": seconds, "kind": getattr(getattr(prompt, "kind", None), "name", None)}
            self._answer = None
            self._bump()
            self._changed.wait_for(lambda: self._answer is not None, seconds + CLOCK_GRACE if seconds else None)
            choice, self._answer, self.prompt = self._answer, None, None
            self._bump()
        return choice

    def answer(self, prompt_id: object, choice: object) -> bool:
        """The page's answer to the open prompt; False if it is for another prompt or not one of its options."""
        with self._changed:
            prompt = self.prompt
            if prompt is None or prompt_id != prompt["id"] or not isinstance(choice, int) or isinstance(choice, bool) \
                    or not 0 <= choice < len(prompt["options"]):
                return False
            self._answer = choice
            self._changed.notify_all()
            return True

    def view(self, since: int, timeout: float = POLL_SECONDS) -> dict:
        """Everything the page shows, once something changed after `since` (or `timeout` seconds passed)."""
        with self._changed:
            self._changed.wait_for(lambda: self.version > since or self.over, timeout)
            return {"version": self.version, "name": self.name, "me": self.narrator.me, "over": self.over,
                    "spectator": self.spectate,
                    "state": self.state, "lines": list(self.lines), "prompt": self.prompt}


class _Handler(BaseHTTPRequestHandler):
    @property
    def web(self) -> "WebServer":
        return cast("WebServer", self.server)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/":
            self._reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/favicon.ico":
            self._reply(204, b"", "image/x-icon")
        elif url.path == "/state":
            since = int(parse_qs(url.query).get("since", ["-1"])[0])
            self._reply(200, json.dumps(self.web.client.view(since, self.web.poll_seconds)).encode("utf-8"),
                        "application/json")
        else:
            self._reply(404, b"Not found", "text/plain")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/choose":
            self._reply(404, b"Not found", "text/plain")
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except ValueError:
            body = {}
        taken = isinstance(body, dict) and self.web.client.answer(body.get("id"), body.get("choice"))
        self._reply(200 if taken else 409, json.dumps({"ok": taken}).encode("utf-8"), "application/json")

    def _reply(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass  # the game's own output is enough


class WebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, client: WebClient, host: str = "127.0.0.1", port: int = 8765, poll_seconds: float = POLL_SECONDS):
        super().__init__((host, port), _Handler)
        self.client = client
        self.poll_seconds = poll_seconds

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m infernal_machine.web", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--host", default="localhost", help="the game server")
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--name", help="your name at the table (needed to play; spectators may leave it out)")
    parser.add_argument("--deck", metavar="FILE", help="your decklist (Commander / Deck sections); players need one")
    parser.add_argument("--spectate", action="store_true", help="watch the game instead of playing in it")
    parser.add_argument("--password", help="the table's password, if it has one")
    parser.add_argument("--listen", type=int, default=8765, help="the local port the page is served on")
    parser.add_argument("--no-browser", action="store_true", help="don't open the page in your browser")
    args = parser.parse_args(argv)
    if not args.spectate and not (args.name and args.deck):
        parser.error("--name and --deck are needed to play (or use --spectate)")
    deck_text = None
    if args.deck:
        with open(args.deck) as f:
            deck_text = f.read()
    try:
        sock = socket.create_connection((args.host, args.port))
    except OSError as err:
        print(f"Couldn't connect to {args.host}:{args.port}: {err}", file=sys.stderr)
        return 1
    client = WebClient(sock, args.name or "Spectator", deck_text, spectate=args.spectate, password=args.password)
    try:
        httpd = WebServer(client, port=args.listen)
    except OSError as err:
        print(f"Couldn't serve the page on port {args.listen}: {err}", file=sys.stderr)
        sock.close()
        return 1
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"{'Watching' if args.spectate else 'Playing as ' + args.name}; the table is at {httpd.url}")
    if not args.no_browser:
        webbrowser.open(httpd.url)
    try:
        client.run()
        print("The game server closed the connection. The page stays up; press Ctrl-C to quit.")
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
