"""Fixtures and helpers shared by many tests, importable without importing another test module's tests (issue #282).

Test files never import from one another (`tests/test_test_imports.py` enforces it): a fixture two files need lives here.
"""

from infernal_machine.cards import Card, Deck, _mana_value
from infernal_machine.game import CAST, PASS, Game, Permanent
from infernal_machine.cards import Card
from tests.real import REAL
from infernal_machine.game import ACTIVATE
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.cards import Deck
from infernal_machine.cards import CardNotFound
import json
import socket
from infernal_machine.game import CHANGE_WHICH_PROMPT
from infernal_machine.game import TARGET_PROMPT
from infernal_machine.game import CAST


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


COUNTERSPELL = Card(name="Counterspell", mana_cost="{U}{U}", type_line="Instant", oracle_text="Counter target spell.")


LIBRARY = [Card(name="Filler", type_line="Land")] * 10


def scryfall(layout, *faces, cmc=3.0, colors=None):
    data = {"name": " // ".join(f["name"] for f in faces), "layout": layout, "cmc": cmc, "id": "x", "color_identity": [],
            "legalities": {"commander": "legal"}, "card_faces": list(faces)}
    if colors is not None:
        data["colors"] = colors
    return data


def attack_all(prompt, options):
    """Attack the first opponent with everything; block the first attacker offered."""
    if len(options) > 1 and options[0] in ("Don't attack", "Don't block"):
        return 1
    return options.index("Pass") if "Pass" in options else 0


EXILE_OGRE = Card(name="Ogre", mana_cost="{3}", type_line="Creature — Ogre", power="3", toughness="3")


def spell(cost, name="Spell"):
    return Card(name=name, mana_cost=cost, type_line="Sorcery", oracle_text="Draw a card.")


ANTHEM = Card(name="Glorious Anthem", mana_cost="{W}", type_line="Enchantment", oracle_text="Creatures you control get +1/+1.")


ELF = Card(name="Elf", mana_cost="{G}", type_line="Creature — Elf Warrior", power="1", toughness="1")


HASTE = Card(name="Fervor", mana_cost="{R}", type_line="Enchantment", oracle_text="Creatures you control have haste.")


LORD = REAL["Elvish Archdruid"]


BIG = Card(name="Big", type_line="Creature — Giant", power="5", toughness="5", mana_cost="{4}{R}", cmc=5.0)


SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")


BIRD = creature("Bird", 1, 1, "Flying")


RELIC = Card(name="Relic", type_line="Artifact", mana_cost="{1}", cmc=1.0)


SHRINE = Card(name="Shrine", type_line="Enchantment", mana_cost="{2}", cmc=2.0)


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def fire(game, seat, permanent, event):
    game.trigger(event, permanent, seat)
    run_stack(game)


SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))


def enter(game, seat, card):
    permanent = Permanent(card)
    game._enter(seat, permanent)
    return permanent


SOL_RING = Card(name="Sol Ring", mana_cost="{1}", type_line="Artifact", oracle_text="{T}: Add {C}{C}.")


BOLT = Card(name="Bolt", mana_cost="{R}", cmc=1.0, type_line="Instant", oracle_text="Draw a card.")


COMMANDER = TABLE3_COMMANDER


def half(name, text, type_line="Sorcery"):
    return Card(name=name, mana_cost="{1}", type_line=type_line, oracle_text=text)


SPELL = Card(name="Quick Study", mana_cost="{1}{U}", type_line="Instant", oracle_text="Draw two cards.", cmc=2.0)


def prepper(text, name="Student"):
    return Card(name=f"{name} // Quick Study", mana_cost="{1}", type_line="Creature — Wizard", power="1", toughness="1",
                oracle_text=text, prepare=SPELL)


def supported(test, card):
    test.assertEqual(unsupported_lines(card), [], card.oracle_text)


def card(text, name="Test", type_line="Creature — Test", **fields):
    return Card(name=name, type_line=type_line, oracle_text=text, power="2" if "Creature" in type_line else None,
                toughness="2" if "Creature" in type_line else None, **fields)


def names(seat, zone="battlefield"):
    items = getattr(seat, zone)
    return sorted(p.card.name if isinstance(p, Permanent) else p.name for p in items)


def triggers_80_supported(test, c):
    test.assertEqual(unsupported_lines(c), [], c.oracle_text)


EFFECTS_BOLT = Card(name="Lightning Bolt", mana_cost="{R}", type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.")


DIVINATION = Card(name="Divination", mana_cost="{2}{U}", type_line="Sorcery", oracle_text="Draw two cards.")


FURNACE = real("Furnace of Rath", "{1}{R}{R}{R}", "Enchantment", "If a source would deal damage to a permanent or player, it deals double "
               "that damage to that permanent or player instead.")


TOMIK = real("Tomik, Izzet Sparkmage", "{1}{R}", "Legendary Creature — Human Wizard", "Prowess (Whenever you cast a noncreature spell, "
             "this creature gets +1/+1 until end of turn.)\nIf a source you control would deal noncombat damage to an opponent or a permanent "
             "an opponent controls, it deals that much damage plus 1 instead.", "1", "2")


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))


def settle(game, seat=None):
    game._priority_round(seat or game.seats[0])


def watcher(name, text, kind="Enchantment"):
    return Card(name=name, mana_cost="{1}", type_line=kind, oracle_text=text)


TROLL = Card(name="Troll", mana_cost="{G}", type_line="Creature — Troll", oracle_text="Hexproof", toughness="2")


COMPARE_BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")


DUD = Card(name="Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1")  # never castable with Forests


COMPARE_FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def standard(spell, extra=()):
    return Deck([], [COMPARE_FOREST] * 24 + list(extra) + [spell] * (36 - len(extra)), [])


EFFECTS_BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", type_line="Creature — Bear", power="2", toughness="2")


MARTYR = Card(name="Martyr", mana_cost="{W}", type_line="Creature — Human", power="1", toughness="1",
              oracle_text="When Martyr dies, you gain 3 life.")


BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))


ODD = Card(name="Odd Spell", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text="Exchange the frobnicator of each player with the quuxes.")


COURSEWORK = Card(name="Infinite Coursework", mana_cost="{2}{U}", type_line="Enchantment — Aura",
                  oracle_text="Enchant creature\nWhen this Aura enters, tap enchanted creature. It becomes unprepared.\n"
                              "Enchanted creature loses all abilities and doesn't untap during its controller's untap step.")


ANALYZE_BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))


ANALYZE_BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))


ANALYZE_FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


class FakeSource:
    def __init__(self, *cards):
        self.cards = {c.name: c for c in cards}

    def get(self, name):
        if name not in self.cards:
            raise CardNotFound(name)
        return self.cards[name]

    def get_many(self, names):
        return {n: self.get(n) for n in dict.fromkeys(names)}


def commander_deck(*extras):
    return Deck([ANALYZE_BOSS], [*extras, *[ANALYZE_FOREST] * 38, *[ANALYZE_BEAR] * (61 - len(extras))], [])


def fight(attackers, blockers=(), attacker_policy=attack_all, blocker_policy=attack_all):
    game, _, _ = table(attacker_policy, blocker_policy)
    a, b = game.seats
    a.battlefield = [Permanent(c) for c in attackers]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    if game.combat.has_first_strike():
        game.combat.deal_damage(first_strike_step=True)
        game._check_state()
    game.combat.deal_damage(first_strike_step=False)
    game._check_state()
    return game, a, b


def activation(game, seat, starts):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and starts in a]


def gift_table(*hand, mana=4, policy=None):
    game, _ = table3(policy or script("Give"))
    a = game.seats[0]
    a.hand, a.graveyard = list(hand), []
    a.battlefield = lands(mana)
    a.library = [BEAR] * 5
    for seat in game.seats[1:]:
        seat.library = [OGRE] * 5
    game.turn, game.step = 2, "main1"
    return game, a, game.seats[1], game.seats[2]


def begin(game, step, seat=None):
    game.step = step
    game._turn_based_actions(seat or game.seats[game.active])
    run_stack(game)


COURSER = Card(name="Courser", mana_cost="{G}", type_line="Enchantment",
               oracle_text="Landfall — Whenever a land you control enters, you gain 1 life.")


RAISE = Card(name="Raise the Alarm", mana_cost="{1}{W}", type_line="Instant",
             oracle_text="Create two 1/1 white Soldier creature tokens.")


MULLDRIFTER = REAL["Mulldrifter"]


LOOTER = Card(name="Looter", mana_cost="{1}", type_line="Artifact", oracle_text="{1}, Discard a card: Draw a card.")


ABILITY_COSTS_MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))


def ability_costs_settle(game):
    game._priority_round(game.seats[0])


EFFECTS_COMMANDER = TABLE_COMMANDER


DARKSTEEL = Card(name="Darksteel Myr", mana_cost="{3}", type_line="Artifact Creature — Myr",
                 oracle_text="Indestructible", power="0", toughness="1")


PAWN = Card(name="Pawn", mana_cost="{B}", type_line="Creature — Human", power="1", toughness="1",
            oracle_text="Whenever another creature you control dies, draw a card.")


ZULAPORT = Card(name="Zulaport", mana_cost="{B}", type_line="Creature — Human", power="1", toughness="1",
                oracle_text="Whenever Zulaport or another creature you control dies, each opponent loses 1 life.")


MURDER = Card(name="Murder", mana_cost="{1}{B}{B}", type_line="Instant", oracle_text="Destroy target creature.")


ARCHIVE = real("Alhammarret's Archive", "{5}", "Legendary Artifact", "If you would gain life, you gain twice that much life instead.\n"
               "If you would draw a card except the first one you draw in each of your draw steps, draw two cards instead.")


WURM = creature("Wurm", 6, 6, "Trample")


PROTECTION_WARD_BOLT = Card(name="Lightning Bolt", mana_cost="{R}", type_line="Instant", colors=("R",),
            oracle_text="Lightning Bolt deals 3 damage to any target.")


def protection_ward_creature(name, power, toughness, colors, text=""):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Test", power=str(power), toughness=str(toughness),
                colors=tuple(colors), oracle_text=text)


GREEN_BEAR = protection_ward_creature("Green Bear", 2, 2, "G")


PLAIN = protection_ward_creature("Plain Bear", 2, 2, "G")


RED_OGRE = protection_ward_creature("Red Ogre", 3, 3, "R")


def table2(*policies):
    """table() with the players in a list, like table3()."""
    game, a, b = table(*policies)
    return game, [a, b]


def attack_first_opponent(prompt, options):
    return 1 if options[0] == "Don't attack" else 0


SPARE = Card(name="Spare", mana_cost="{1}", type_line="Sorcery", oracle_text="Draw a card.")


def activations(game, seat, text):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and text in a]


BARGAIN = real("Immoral Bargain", "{1}{B}{G}", "Sorcery",
               "As an additional cost to cast this spell, sacrifice X creatures.\nDestroy X target nonland permanents.")


def priority_cast(table):
    """Immoral Bargain's X is asked for as the spell is cast from priority, so go in through the priority round."""
    table.game._priority_round(table.a)
    run_stack(table.game)
    table.game._check_state()
    return table


def combat_names(seat):
    return sorted(p.card.name for p in seat.battlefield)


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


SWORDS = Card(name="Swords to Plowshares", mana_cost="{W}", type_line="Instant",
              oracle_text="Exile target creature. Its controller gains life equal to its power.")


CHANGE_TARGET_BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


class Responder:
    """Seat B's replies, remembering what it was asked for a target."""

    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, prompt, options):
        if prompt.startswith((TARGET_PROMPT, CHANGE_WHICH_PROMPT)):
            self.asked.append(list(options))
        return pick(self.answers.pop(0) if self.answers else "Pass")(prompt, options)


def stack_fight(spell, aimed, response, *, mine=(), theirs=(), third=(), answers=(), a_answers=(), counter=None, n=6, b_lands=6):
    """A casts `spell` at `aimed`; B (with `response`) answers it with the retargeting spell, and the stack resolves."""
    from tests.helpers import script
    responder = counter or Responder(*answers)
    game, _ = table3(script(aimed, *a_answers), responder)
    a, b, c = game.seats
    a.hand, a.battlefield = [spell], lands(n)
    a.battlefield += [Permanent(x) for x in mine]
    b.hand, b.battlefield = [response], lands(b_lands) + [Permanent(x) for x in theirs]
    c.battlefield = [Permanent(x) for x in third]
    game._perform(a, CAST + spell.name)
    game._perform(b, CAST + response.name)
    run_stack(game)
    game._check_state()
    return game, a, b, c, responder


STUDY = Card(name="Quick Study", mana_cost="{1}{U}", type_line="Instant", oracle_text="Draw two cards.", cmc=2.0)


ADEPT = Card(name="Study Adept // Quick Study", mana_cost="{1}{U}", type_line="Creature — Wizard",
             oracle_text="This creature enters prepared. (While it's prepared, you may cast a copy of its spell. "
                         "Doing so unprepares it.)", prepare=STUDY)



