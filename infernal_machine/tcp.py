"""TCP connector: remote players speak newline-delimited JSON over a socket.

Protocol (one JSON object per line, UTF-8):

  client -> server  {"type": "hello", "name": "Alice", "deck": "<decklist text>"}   first message
                                                                (the deck is optional; the game server needs it)
  server -> client  {"type": "welcome", "seat": 0}                ("rejoined": true when you took your seat back)
  server -> client  {"type": "event", ...}                      no reply expected
  server -> client  {"type": "event", "event": "state", ...}    the whole board, sent before your decisions
  server -> client  {"type": "choose", "id": 1, "prompt": "...", "options": [...]}   ("seconds": 60 when a clock runs)
  client -> server  {"type": "response", "id": 1, "choice": 0}      (an answer to an earlier id is ignored)
  server -> client  {"type": "error", "message": "..."}         bad input; re-prompted
"""

from __future__ import annotations

import json
import select
import socket
import threading
import time
from typing import Sequence


class Disconnected(ConnectionError):
    pass


class TimedOut(TimeoutError):
    """A player didn't answer a choice within its time limit; the connection is still good."""


def send_promptly(sock: socket.socket) -> None:
    """Turn off Nagle's algorithm: our messages are small and come in bursts, and with delayed ACKs
    each one could otherwise be held back for tens of milliseconds. Sockets that aren't TCP (the
    in-process pairs used in tests) don't support the option and don't need it."""
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass


class TcpPlayer:
    """A Player backed by a connected socket."""

    wants_state = True  # the game sends this player a "state" event (the board) before their decisions

    def __init__(self, sock: socket.socket, name: str = ""):
        self.sock = sock
        self.name = name
        self.hello: dict = {}
        send_promptly(sock)
        self._buffer = b""  # bytes received but not yet read as a line
        self._next_id = 0
        self._send_lock = threading.Lock()  # whole lines, even when the server's threads write at once
        self._deadline: float | None = None  # when a timed choose stops waiting (time.monotonic())

    def notify(self, event: dict) -> None:
        self._send({"type": "event", **event})

    def choose(self, prompt: str, options: Sequence[str], seconds: float | None = None) -> int:
        """Ask and wait for the answer; with `seconds`, TimedOut once that long has passed without one."""
        if not options:
            raise ValueError("choose() needs at least one option")
        self._next_id += 1
        request = {"type": "choose", "id": self._next_id, "prompt": prompt, "options": list(options)}
        if seconds:
            request["seconds"] = seconds
        self._send(request)
        self._deadline = time.monotonic() + seconds if seconds else None
        try:
            while True:
                message = self._receive()
                choice = message.get("choice")
                if message.get("type") == "response" and message.get("id") != self._next_id:
                    continue  # the answer to an earlier choice, which a clock closed (TimedOut): dropped quietly
                if (
                    message.get("type") == "response"
                    and isinstance(choice, int)
                    and not isinstance(choice, bool)
                    and 0 <= choice < len(options)
                ):
                    return choice
                self._send({"type": "error", "message": f"Expected a response to choice {self._next_id}"})
                self._send(request)
        finally:
            self._deadline = None

    def read_hello(self) -> dict:
        """Read the client's hello (raising Disconnected if it isn't one) and remember it in `hello`."""
        hello = self._receive()
        if hello.get("type") != "hello" or not isinstance(hello.get("name"), str):
            self._send({"type": "error", "message": "First message must be hello with a name"})
            raise Disconnected("Bad handshake")
        self.name = hello["name"]
        self.hello = hello
        return hello

    def welcome(self, seat: int, rejoined: bool = False) -> None:
        self._send({"type": "welcome", "seat": seat, **({"rejoined": True} if rejoined else {})})

    def handshake(self, seat: int) -> None:
        self.read_hello()
        self.welcome(seat)

    def send_error(self, message: str) -> None:
        self._send({"type": "error", "message": message})

    def close(self) -> None:
        """Close the connection; a thread blocked reading from it wakes up with Disconnected."""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()

    def _send(self, message: dict) -> None:
        try:
            with self._send_lock:
                self.sock.sendall((json.dumps(message) + "\n").encode("utf-8"))
        except OSError as err:
            raise Disconnected(self.name) from err

    def _readline(self) -> bytes:
        """The next line from the socket. Until a timed choose's deadline, if one is set; the socket's own timeout
        (a handshake's) applies to each read."""
        while b"\n" not in self._buffer:
            try:
                if self._deadline is not None:
                    remaining = self._deadline - time.monotonic()
                    if remaining <= 0 or not select.select([self.sock], [], [], remaining)[0]:
                        raise TimedOut(self.name)
                chunk = self.sock.recv(4096)
            except TimedOut:
                raise
            except (OSError, ValueError) as err:  # ValueError: closed by another thread while we were waiting
                raise Disconnected(self.name) from err
            if not chunk:
                raise Disconnected(self.name)
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return line

    def _receive(self) -> dict:
        while True:
            line = self._readline()
            try:
                message = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                self._send({"type": "error", "message": "Invalid JSON"})
                continue
            if isinstance(message, dict):
                return message
            self._send({"type": "error", "message": "Messages must be JSON objects"})


def accept_players(server: socket.socket, count: int, handshake_timeout: float = 10.0) -> list[TcpPlayer]:
    """Accept `count` players on a listening socket and complete each handshake.

    A client that fails or stalls the handshake is dropped and its seat stays open.
    """
    players: list[TcpPlayer] = []
    while len(players) < count:
        conn, _ = server.accept()
        conn.settimeout(handshake_timeout)
        player = TcpPlayer(conn)
        try:
            player.handshake(seat=len(players))
            conn.settimeout(None)
        except Disconnected:
            player.close()
            continue
        players.append(player)
    return players


def listen(host: str = "0.0.0.0", port: int = 4000) -> socket.socket:
    return socket.create_server((host, port))
