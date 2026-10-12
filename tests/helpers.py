"""Fixtures and helpers shared by many tests, importable without importing another test module's tests (issue #282).

The old homes (`test_effects`, `test_mass_effects`, `test_more_triggers`, `test_combat`, `test_x_targets`, `test_rules_text_81`,
`test_triggers_80`, `test_exile`, `test_game`) still export the same names, so no other test file has to change. New tests import
from here.
"""

from infernal_machine.cards import Card, Deck, _mana_value
from infernal_machine.game import CAST, PASS, Game, Permanent


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


RAINBOW = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG"))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
TABLE_COMMANDER = Card(name="Omnath", mana_cost="{G}", type_line="Legendary Creature — Elemental", toughness="1")  # the commander of `table`
TABLE3_COMMANDER = Card(name="Omnath", mana_cost="{G}", type_line="Legendary Creature — Elemental", power="4", toughness="4")  # of `table3`


def creature(name, power, toughness, text=""):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Test", power=str(power),
                toughness=str(toughness), oracle_text=text)


BEAR = creature("Bear", 2, 2)
OGRE = creature("Ogre", 3, 3)


def pick(*labels):
    """Policy: take the first option starting with any of `labels`, in order; else pass/first."""
    def policy(prompt, options):
        for label in labels:
            for i, option in enumerate(options):
                if option.startswith(label):
                    return i
        return options.index(PASS) if PASS in options else 0
    return policy


def script(*answers):
    """A policy that answers each question with the first option starting with the next answer, then passes."""
    queue = iter(answers)
    return lambda prompt, options: pick(next(queue, "Pass"))(prompt, options)


def table(policy_a=None, policy_b=None, library=(FOREST,) * 20):
    a, b = ScriptedPlayer("A", policy_a), ScriptedPlayer("B", policy_b)
    deck = Deck(commanders=[TABLE_COMMANDER], main=list(library), sideboard=[])
    game = Game([(a, deck), (b, deck)], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand, seat.command_zone = [], []
    return game, a, b


def table3(*policies):
    players = [ScriptedPlayer(name, policy) for name, policy in zip("ABC", policies + (None,) * 3)]
    deck = Deck(commanders=[TABLE3_COMMANDER], main=[FOREST] * 20, sideboard=[])
    game = Game([(p, deck) for p in players], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand, seat.command_zone = [], []
    return game, players


def lands(n, card=RAINBOW):
    return [Permanent(card) for _ in range(n)]


def run_stack(game):
    """Put the triggers on the stack and resolve everything, including what resolving triggers in turn."""
    while game.pending or game.stack:
        game._put_triggers_on_stack()
        while game.stack:
            game._resolve(game.stack.pop())


def resolve_triggers(game, seat):
    game._priority_round(seat)


def take_turn_attacking(game, seat):
    game.turn = 3
    game._take_turn(seat)


def real(name, cost, type_line, text, power=None, toughness=None, colors=()):
    return Card(name=name, mana_cost=cost, cmc=_mana_value(cost), type_line=type_line, oracle_text=text, power=power,
                toughness=toughness, colors=colors)


class Table:
    """Seat 0 casts `card` with `n` lands against two opponents; `answers` are the replies to what the game asks."""

    def __init__(self, card, *answers, n=6, mine=(), theirs=(), graveyard=(), library=None, policy=None):
        self.game, _ = table3(policy or script(*answers))
        self.a, self.b, self.c = self.game.seats
        self.a.battlefield = list(mine) + lands(n)
        self.b.battlefield = list(theirs)
        self.a.hand = [card]
        self.a.graveyard = list(graveyard)
        self.a.library = list(library if library is not None else [FOREST] * 10)
        self.card = card

    def cast(self):
        self.game._perform(self.a, CAST + self.card.name)
        run_stack(self.game)
        self.game._check_state()
        return self


def battlefield_names(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name != "City of Brass")
