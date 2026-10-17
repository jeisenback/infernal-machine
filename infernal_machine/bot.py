"""A simple computer player, plus goldfishing: playing a deck alone to see how it opens."""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from .analysis import color_pips, is_land
from .cards import Card, Deck
from .combat import ASSIGN_PROMPT, ATTACK_PROMPT, BLOCK_PROMPT
from .effects import RETURN_LAND_PROMPT, DamageEach, DestroyAll, ExileAll, ReturnAllToHand, spell_effects
from .undercity import HELPS_ITS_TARGET
from .effects import MOVE_COUNTERS_PROMPT
from .game import (COMMAND_ZONE_PROMPT, COMMANDER_TAX, NONE_TAKEN, CHOOSE_DISCARD_PROMPT, DISCARD_CARD_PROMPT, VOTE_PROMPT, THRONE_PROMPT, CLONE_PROMPT, PROLIFERATE_PROMPT, ACTIVATE, COMPANION, BOTTOM_PROMPT, CAST, CAST_COMMANDER, CAST_EXILE, CAST_GRAVEYARD, CAST_PREPARED, PLAY_EXILE, PLAY_GRAVEYARD, DISCARD_PROMPT, HAND_SIZE, KEEP_PROMPT, LOOK_PROMPT, PASS, SEARCH_PROMPT, SEARCH_LAND_PROMPT, SEARCH_LAND_HAND_PROMPT,
                   CYCLE, DONE_MODES, MODE_PROMPT, SCRY_PROMPT, SURVEIL_PROMPT,
                   MULTIKICKER_PROMPT, DANCE_PROMPT, PLAY_LAND, SACRIFICE_COST_PROMPT, SACRIFICE_PROMPT, SEARCH_CARD_PROMPT, SHOCK_PROMPT, TARGET_PROMPT, X_PROMPT, LIFE_X_PROMPT, DEVOUR_PROMPT, EXPLOIT_PROMPT, REPLICATE_PROMPT)

MIN_LANDS = 2
MAX_LANDS = 5
MAX_MULLIGANS = 2  # after this many, keep whatever comes
FEATURES = frozenset({"timing", "attack", "land", "target", "mana", "commander", "threat", "destination", "keep", "block", "hold", "tempo", "fetch"})  # the judgments a bot can make; BotPlayer(features=frozenset()) is the plain bot
HIGH_TAX = 6  # a commander cast from the command zone three times has this much tax; past it, a graveyard with a way out can be the better place
# A card that brings a card back from a graveyard to the battlefield or the hand: where a commander that dies can be worth leaving.
RECURSION = re.compile(r"\b(return|put)\b[^.]{0,120}?\bfrom (?:your|a|any|an opponent's) graveyard (?:to|onto) (?:the battlefield|your hand)"
                       r"|return enchanted creature card to the battlefield", re.IGNORECASE)
COMMANDER_FIRST_TAX = 2  # cast the commander before anything else while its tax is at most this; after that it competes for mana
COMMANDER_DAMAGE = 21  # the commander damage that loses a game, unless the game says otherwise (Duel Commander: 15)
LAND_SEARCH_PROMPTS = (SEARCH_PROMPT, SEARCH_LAND_PROMPT, SEARCH_LAND_HAND_PROMPT)  # asked when a spell or land fetches a land
LOW_CURVE = 3.0  # a deck whose spells cost this much on average or less can keep a two-land hand that has cheap spells
CHEAP_SPELL = 2  # a spell this cheap (or cheaper) is one a two-land hand can cast
SMALL_THREAT = 2  # an opposing creature this small (power) is not worth a removal spell while nothing bigger is out
LAND_GOAL = 6  # lands (in play and in hand) the bot wants before it stops keeping more


def keep_hand(hand: list[Card], mulligans: int = 0) -> bool:
    lands = sum(1 for c in hand if is_land(c))
    return mulligans >= MAX_MULLIGANS or MIN_LANDS <= lands <= MAX_LANDS


def keep_hand_for(hand: list[Card], average_cost: float, mulligans: int = 0) -> bool:
    """`keep_hand` for a deck whose spells cost `average_cost` on average: a hand of two lands is only kept when the deck is cheap
    enough to play on two (`LOW_CURVE`) and the hand has two spells to cast with them; hands of three to five lands are kept as ever."""
    if mulligans >= MAX_MULLIGANS:
        return True
    lands = sum(1 for c in hand if is_land(c))
    if lands == MIN_LANDS:
        return average_cost <= LOW_CURVE and sum(1 for c in hand if not is_land(c) and c.cmc <= CHEAP_SPELL) >= 2
    return MIN_LANDS < lands <= MAX_LANDS


def worst_card(hand: list[Card]) -> int:
    """Index of the card to put on the bottom or discard: a land if over half
    the hand is lands, otherwise the most expensive spell."""
    lands = [i for i, c in enumerate(hand) if is_land(c)]
    spells = [i for i, c in enumerate(hand) if not is_land(c)]
    if lands and (len(lands) * 2 > len(hand) or not spells):
        return lands[0]
    return max(spells, key=lambda i: hand[i].cmc)


class BotPlayer:
    """Keeps 2-5 land hands, plays a land whenever it can, then casts its most
    expensive affordable spell (its commander first), and otherwise passes.

    It chooses the largest X it can afford, sacrifices its weakest creature, targets opponents' things
    when it can, never responds to its own
    spell, and always sends its commander back to the command zone.
    After casting, it activates abilities whose cost taps or sacrifices the
    source, or uses loyalty (so it can't loop on a mana-only ability), and equips
    Equipment that isn't attached yet. It puts helpful Auras on its own creatures.
    In combat it attacks the opponent with the lowest life with every creature
    that has power, blocks when its blocker survives, and chump-blocks the
    biggest attacker once its life is at CHUMP_LIFE or below.

    It watches the board (the same snapshot TCP players get) for a few judgments: scry and surveil keep a land on
    top until it has LAND_GOAL lands and a spell it can cast soon, and send the rest away; it casts a wipe only
    when opponents have more creatures than it does; it cycles extra lands and spells it can't cast soon; and it
    picks the modes that do the most (removal, then cards and tokens). It always pays ward: the spell is already
    paid for, and the game only asks when it can afford it.
    """

    wants_state = True  # the game sends the board before each priority decision

    CHUMP_LIFE = 10

    def __init__(self, name: str, deck: Deck, features: frozenset[str] = FEATURES):
        """`features` turns judgments on: "timing" (tap-and-sacrifice abilities only after casting, never before the
        main phase), "attack" (only attacks that can't be blocked and killed for nothing), "land" (plays the land its
        hand needs), "target" (removal goes on the biggest opposing creature), "mana" (casts what spends the most mana),
        "keep" (a hand of two lands is kept only by a cheap deck, and only with two cheap spells), "commander" (a commander with a high tax is weighed against other spells, and its damage goes where it adds up to 21),
        "threat" (in a pod, it finishes an opponent it can kill and otherwise attacks the one with the most on the board, not the one on
        the lowest life), "destination" (a commander that would be bounced goes to the hand to be cast without tax, and one that would
        die with a lot of tax on it goes to the graveyard if the deck can bring it back)."""
        self.features = features
        self._commanders = {c.name for c in deck.commanders}
        self._signature = deck.signature_spell.name if deck.signature_spell else None  # an Oathbreaker's spell: cast like any spell, not first like a commander
        self._commander_casts: Counter = Counter()  # times each of its commanders was cast from the command zone: the tax is two mana a time
        self._recursion = any(RECURSION.search(c.oracle_text) for c in deck.main)
        spells = [c.cmc for c in deck.main if not is_land(c)]
        self._average_cost = sum(spells) / len(spells) if spells else 0.0  # what the deck's spells cost on average
        self.name = name
        self._cards = {c.name: c for c in deck.commanders + deck.main + ([deck.signature_spell] if deck.signature_spell else [])}
        self._cards.update({c.prepare.name: c.prepare for c in list(self._cards.values()) if c.prepare})  # the spell halves
        self._cards.update({c.alternate.name: c.alternate for c in list(self._cards.values()) if c.alternate})  # Adventures and other cast-from-hand halves
        self._hand: list[Card] = []
        self._mulligans = 0
        self._seat: int | None = None
        self._stack: list[int] = []  # seat of each spell on the stack, bottom first
        self._life: dict[int, int] = {}
        self._state: dict | None = None  # the latest board snapshot
        self._damage_limit = COMMANDER_DAMAGE
        self._joint: dict[str, list[str]] = {}  # this combat's double blocks: the attacker -> the blockers that were planned for it
        self._joint_turn: int | None = None

    def _card(self, name: str) -> Card:
        """The card called `name`. One from another deck (Plargg and Nassari casts opponents' cards) is known by name only."""
        return self._cards.get(name) or Card(name=name)

    def notify(self, event: dict) -> None:
        kind = event.get("event")
        if kind == "opening_hand":
            self._hand = [self._card(name) for name in event["cards"]]
            self._mulligans = event["mulligans"]
        elif kind == "seat":
            self._damage_limit = event.get("damage_limit", self._damage_limit)
            self._life[event["seat"]] = event["life"]
            if event["name"] == self.name:
                self._seat = event["seat"]
        elif kind == "life":
            self._life[event["seat"]] = event["life"]
        elif kind == "state":
            self._state = event
        elif kind in ("cast", "trigger", "activate"):
            self._stack.append(event["seat"])
            if kind == "cast" and event["seat"] == self._seat and event.get("from") == "command_zone":
                self._commander_casts[event["card"]] += 1
        elif kind in ("resolve", "fizzle") and self._stack:
            self._stack.pop()
        elif kind == "countered" and event["seat"] in self._stack:
            self._stack.reverse()
            self._stack.remove(event["seat"])
            self._stack.reverse()

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        if prompt == KEEP_PROMPT:
            keep = keep_hand_for(self._hand, self._average_cost, self._mulligans) if "keep" in self.features else keep_hand(self._hand, self._mulligans)
            return 0 if keep else 1
        if prompt in (BOTTOM_PROMPT, DISCARD_PROMPT, DISCARD_CARD_PROMPT):
            return worst_card([self._card(name) for name in options])
        if prompt.startswith(ATTACK_PROMPT):
            if _stats(prompt)[0] <= 0 or ("attack" in self.features and not self._worth_attacking(prompt)):
                return 0
            if "commander" in self.features and (lethal := self._commander_target(prompt, options)) is not None:
                return lethal
            return self._attack_target(options)
        if prompt == COMMAND_ZONE_PROMPT:
            return self._commander_zone(options)
        if prompt in LAND_SEARCH_PROMPTS and (land := self._best_search_land(options, list(range(len(options))))) is not None:
            return land  # Evolving Wilds, Cultivate, Path to Exile's land: the colour the hand needs
        if prompt.startswith(BLOCK_PROMPT):
            return self._block(prompt, options)
        if prompt.startswith(SHOCK_PROMPT):
            return 0 if self._life_of(self._seat) > 10 else 1  # pay life only while healthy
        if prompt.startswith(DANCE_PROMPT):  # Dance with Calamity: keep exiling while the total is well under the limit
            return 0 if _prompt_number(prompt, "(") < 4 and _prompt_number(prompt, "total mana value ") < 9 else 1
        if prompt.startswith(DEVOUR_PROMPT):  # the bot keeps its creatures
            return len(options) - 1
        if prompt.startswith(EXPLOIT_PROMPT):  # only a creature that is hardly worth keeping
            weakest = min(range(len(options) - 1), key=lambda i: sum(_stats(options[i])))
            return weakest if sum(_stats(options[weakest])) <= 2 else len(options) - 1
        if prompt.startswith(REPLICATE_PROMPT):
            return len(options) - 1
        if prompt.startswith(LIFE_X_PROMPT):  # paying life for X: some, not everything
            return min(len(options) - 1, 3)
        if prompt.startswith((X_PROMPT, MULTIKICKER_PROMPT)):
            return len(options) - 1  # as big as it can afford
        if prompt.startswith(CLONE_PROMPT):  # copy the biggest creature, or nothing if there is none
            sizes = [sum(_stats(option)) for option in options[:-1]]
            return sizes.index(max(sizes)) if sizes and max(sizes) > 0 else len(options) - 1
        if prompt.startswith(VOTE_PROMPT) and all(_seat_of(o) is not None for o in options):
            return next((i for i, o in enumerate(options) if _seat_of(o) != self._seat), 0)  # vote against an opponent's
        if prompt.startswith(MOVE_COUNTERS_PROMPT):  # moves them all
            return len(options) - 1
        if prompt == PROLIFERATE_PROMPT:  # add counters to its own permanents, and never to an opponent's
            mine = [i for i, option in enumerate(options[:-1]) if _seat_of(option) == self._seat]
            return mine[0] if mine else len(options) - 1
        if prompt.startswith(ASSIGN_PROMPT):  # kill the blockers with the least toughness first
            return min(range(len(options)), key=lambda i: _stats(options[i])[1])
        if prompt == RETURN_LAND_PROMPT:
            return len(options) - 1  # the bounceland that just came in is the newest land
        if prompt in (SEARCH_CARD_PROMPT, LOOK_PROMPT, CHOOSE_DISCARD_PROMPT, THRONE_PROMPT):
            taken = [i for i, name in enumerate(options) if name != NONE_TAKEN]  # never declines the optional take
            if prompt == SEARCH_CARD_PROMPT and (land := self._best_search_land(options, taken)) is not None:
                return land
            # its best card; one it can't see in its own deck (from an opponent's hand) counts as worth nothing
            return max(taken, key=lambda i: self._cards[options[i]].cmc if options[i] in self._cards else 0)
        if prompt == SACRIFICE_PROMPT or prompt.startswith(SACRIFICE_COST_PROMPT):
            return min(range(len(options)), key=lambda i: sum(_stats(options[i])))  # its weakest creature
        if prompt.startswith((SCRY_PROMPT, SURVEIL_PROMPT)):
            card = self._cards.get(prompt.split(": ", 1)[1])
            return 0 if card is None or self._wants_on_top(card) else 1  # 1: to the bottom, or the graveyard
        if prompt.startswith(MODE_PROMPT):
            modes = [option for option in options if option != DONE_MODES]
            scores = [_mode_score(mode) for mode in modes]
            best = max(range(len(modes)), key=scores.__getitem__)
            return options.index(DONE_MODES) if DONE_MODES in options and scores[best] <= 0 else best
        if prompt.startswith(TARGET_PROMPT):
            mine = [i for i, option in enumerate(options) if _seat_of(option) == self._seat]
            theirs = [i for i, option in enumerate(options) if _seat_of(option) != self._seat]
            if self._is_buff_aura(prompt.removeprefix(TARGET_PROMPT)) and mine:
                return mine[0]
            if "target" in self.features and theirs and self._is_removal(prompt.removeprefix(TARGET_PROMPT)):
                sized = [i for i in theirs if sum(_stats(options[i])) > 0]
                if sized:
                    return max(sized, key=lambda i: sum(_stats(options[i])))
            return theirs[0] if theirs else 0
        if PASS not in options:
            return 0  # search, command zone and other yes/no choices: take the first option
        if self._stack and self._stack[-1] == self._seat:
            return options.index(PASS)
        lands = [i for i, option in enumerate(options) if option.startswith((PLAY_LAND, PLAY_EXILE, PLAY_GRAVEYARD))]
        if lands:
            return self._best_land(lands, options) if "land" in self.features else lands[0]
        commanders = [i for i, option in enumerate(options) if option.startswith(CAST_COMMANDER) and _cast_name(option) != self._signature]
        if "commander" not in self.features:
            if commanders:
                return commanders[0]
        else:
            cheap = [i for i in commanders if self._tax(options[i]) <= COMMANDER_FIRST_TAX]
            if cheap:
                return cheap[0]
        casts = [i for i, option in enumerate(options)
                 if (option.startswith((CAST, CAST_GRAVEYARD, CAST_EXILE, CAST_PREPARED)) or (option.startswith(CAST_COMMANDER) and _cast_name(option) == self._signature))
                 and not _is_ritual(self._cards.get(_cast_name(option)))
                 and not self._unhelpful_wipe(self._cards.get(_cast_name(option))) and not self._holds_removal(self._cards.get(_cast_name(option)))]
        if "commander" in self.features:
            casts += [i for i in commanders if i not in casts]  # a commander that has grown expensive competes with the rest
        if casts:
            if "mana" in self.features:
                return self._best_cast(casts, options)
            return max(casts, key=lambda i: self._cards[name].cmc if (name := _cast_name(options[i])) in self._cards else 0)
        for i, option in enumerate(options):
            if option.startswith(CYCLE) and self._cycle_away(self._cards.get(option.removeprefix(CYCLE))):
                return i
        for i, option in enumerate(options):
            if option.startswith(ACTIVATE) and (_limited_cost(option) or _equip_needed(option)) and self._activation_time(prompt, option):
                return i
        for i, option in enumerate(options):
            if option.startswith(COMPANION):  # nothing else to do with the mana: the companion is a card from outside the game for {3}
                return i
        return options.index(PASS)

    def _attack_target(self, options: Sequence[str]) -> int:
        """The opponent to attack. The plain bot takes the one on the lowest life. With "threat" and more than one choice it finishes an
        opponent its ready creatures can kill, and otherwise attacks the most dangerous: the most creature power on the board, then
        nonland permanents and cards in hand, and on a tie the lower life."""
        lowest = min(range(1, len(options)), key=lambda i: self._life_of(_seat_of(options[i])))
        mine = self._my_seat()
        seats = {s["seat"]: s for s in (self._state or {}).get("seats", [])}
        foes = [(i, seats[_seat_of(options[i])]) for i in range(1, len(options)) if _seat_of(options[i]) in seats]
        if "threat" not in self.features or mine is None or len(foes) < 2:
            return lowest
        reach = sum(p["power"] for p in mine["battlefield"] if p.get("power") and not p.get("tapped") and not p.get("sick"))
        killable = [(i, s) for i, s in foes if s["life"] <= reach]
        if killable:
            return min(killable, key=lambda f: f[1]["life"])[0]
        return max(foes, key=lambda f: (_threat(f[1]), -f[1]["life"]))[0]

    def _commander_zone(self, options: Sequence[str]) -> int:
        """Where a commander goes when it would be put in a graveyard, exile, hand or library: 0 for the command zone, 1 for there. Only
        the hand (cast from there, it pays no tax) and, with a lot of tax and a way back, the graveyard are worth it."""
        if "destination" not in self.features:
            return 0
        zone = options[1].lower()
        in_zone = {z["name"] for z in (self._my_seat() or {}).get("command_zone", [])}
        away = [name for name in self._commanders if name not in in_zone] or list(self._commanders)
        tax = COMMANDER_TAX * max((self._commander_casts[name] for name in away), default=0)
        if zone == "hand" and tax >= COMMANDER_TAX:
            return 1
        if zone == "graveyard" and tax >= HIGH_TAX and self._recursion:
            return 1
        return 0

    def _tax(self, option: str) -> int:
        """The commander tax on a "Cast commander: ..." action."""
        mine = self._my_seat()
        name = option.removeprefix(CAST_COMMANDER)
        return next((z["tax"] for z in (mine or {}).get("command_zone", []) if z["name"] == name), 0)

    def _commander_target(self, prompt: str, options: Sequence[str]) -> int | None:
        """For one of its own commanders attacking: the opponent it has hurt enough that this attack makes 21."""
        label = prompt.removeprefix(ATTACK_PROMPT)
        name = next((n for n in self._commanders if label.startswith(n + " ")), None)
        if name is None:
            return None
        power = _stats(prompt)[0]
        seats = {s["seat"]: s for s in (self._state or {}).get("seats", [])}
        for i in range(1, len(options)):
            foe = seats.get(_seat_of(options[i]))
            dealt = sum(d["damage"] for d in (foe or {}).get("commander_damage", []) if d["from_seat"] == self._seat and d["commander"] == name)
            if foe is not None and dealt + power >= self._damage_limit:
                return i
        return None

    def _lethal_commander(self, options: Sequence[str]) -> int | None:
        """The attacker to block: an opposing commander whose damage to this bot would reach 21 with this hit."""
        mine = self._my_seat()
        dealt = {d["commander"]: d["damage"] for d in (mine or {}).get("commander_damage", [])}
        for i in range(1, len(options)):
            name = next((n for n in dealt if options[i].startswith(n + " ")), None)
            if name is not None and dealt[name] + _stats(options[i])[0] >= self._damage_limit:
                return i
        return None

    def _activation_time(self, prompt: str, option: str) -> bool:
        """With "timing": equip, crew and loyalty abilities in either main phase, but an ability that taps or sacrifices
        its source (a land it needs for spells, a creature that should attack) only in the second main phase."""
        if "timing" not in self.features:
            return True
        step = prompt.removeprefix("Priority: ")
        cost = option.split("): ", 1)[1].split(":", 1)[0]
        if step == "main2":
            return True
        return step == "main1" and "{T}" not in cost and "Sacrifice" not in cost

    def _land_wants(self) -> tuple[set[str], set[str], int, list[int]]:
        """What the next land should do: (the colors its lands in play make, the colors the spells in hand need, how much mana is
        untapped now, the mana values of the spells in hand)."""
        state = self._state or {}
        have: set[str] = set()
        untapped = 0
        for seat in state.get("seats", []):
            if seat["seat"] == self._seat:
                for p in seat["battlefield"]:
                    if "Land" in p["type"] and p.get("name") in self._cards:
                        have |= set(self._cards[p["name"]].produced_mana)
                    if not p.get("tapped") and ("Land" in p["type"] or (p.get("name") in self._cards and self._cards[p["name"]].produced_mana)):
                        untapped += 1
        needed: set[str] = set()
        costs: list[int] = []
        for name in state.get("hand", []):
            card = self._cards.get(name)
            if card is not None and not is_land(card):
                needed |= set(color_pips(card.mana_cost))
                costs.append(int(card.cmc))
        return have, needed, untapped, costs

    def _best_land(self, lands: list[int], options: Sequence[str]) -> int:
        """The land that adds the most colors the hand still needs and the lands in play lack; untapped ones first. With "tempo", a land
        that enters tapped is played on a turn when no spell in hand needs the mana it would add, and an untapped one when one does."""
        have, needed, untapped, costs = self._land_wants()
        wanted_now = "tempo" in self.features and any(untapped < cost <= untapped + 1 for cost in costs)  # a spell this land's mana would let it cast

        def score(i: int) -> tuple[int, int, bool]:
            card = self._card(options[i].split(": ", 1)[1])
            colors = set(card.produced_mana) & set("WUBRG")
            tapped = _enters_tapped(card)
            return len((colors & needed) - have), len(colors & needed), (not tapped) if wanted_now or "tempo" not in self.features else tapped

        return max(lands, key=score)

    def _best_search_land(self, options: Sequence[str], taken: list[int]) -> int | None:
        """With "fetch": of the lands a search can find, the one that adds the most colors the hand needs and the lands in play lack
        (ties: the one that enters untapped, then the first). None when the search is for something that is not a land."""
        cards = [self._cards.get(options[i]) for i in taken]
        if "fetch" not in self.features or not cards or not all(c is not None and is_land(c) for c in cards):
            return None
        have, needed, _, _ = self._land_wants()

        def score(position: int) -> tuple[int, int, bool]:
            card = cards[position]
            colors = (set(card.produced_mana) if card else set()) & set("WUBRG")
            return len((colors & needed) - have), len(colors & needed), not _enters_tapped(card) if card else True

        return taken[max(range(len(taken)), key=score)]  # (the first of equals: max keeps the first it sees)

    def _best_cast(self, casts: list[int], options: Sequence[str]) -> int:
        """Of the spells it can cast, the biggest one in the combination that spends the most of its untapped mana."""
        mine = self._my_seat()
        mana = sum(1 for p in mine["battlefield"] if not p.get("tapped") and (
            "Land" in p["type"] or (p.get("name") in self._cards and self._cards[p["name"]].produced_mana))) if mine else 0
        mana += len((mine or {}).get("mana_pool", []))
        costs = {i: int(self._cards[name].cmc) + (self._tax(options[i]) if options[i].startswith(CAST_COMMANDER) else 0)
                 if (name := _cast_name(options[i])) in self._cards else 0 for i in casts}
        if max(costs.values()) > mana:  # the game says it can pay for that, so this count is wrong (a cost reduction, a mana ability it can't see)
            return max(casts, key=costs.__getitem__)
        best_total, best = -1, casts[0]
        for mask in range(1, 1 << min(len(casts), 12)):
            chosen = [casts[b] for b in range(min(len(casts), 12)) if mask >> b & 1]
            total = sum(costs[i] for i in chosen)
            if total <= mana and (total > best_total or (total == best_total and max(costs[i] for i in chosen) > costs[best])):
                best_total, best = total, max(chosen, key=costs.__getitem__)
        if best_total < 0:  # it cannot tell what it can pay (X spells, cost reductions): the plain rule
            return max(casts, key=costs.__getitem__)
        return best

    def _is_removal(self, name: str) -> bool:
        card = self._cards.get(name)
        text = card.oracle_text.lower() if card else ""
        return any(word in text for word in ("destroy", "exile", "damage", "return", "gain control", "-x/-x", "fight"))

    def _worth_attacking(self, prompt: str) -> bool:
        """Attack when it is lethal, when it can't be blocked, or when nothing could block and kill this creature and
        survive; stay home when the opponents' board could be lethal next turn."""
        power, toughness = _stats(prompt)
        label = prompt.removeprefix(ATTACK_PROMPT)
        card = next((c for n, c in self._cards.items() if label.startswith(n + " ")), None)
        text = card.oracle_text.lower() if card else ""
        mine = self._my_seat()
        foes = [s for s in (self._state or {}).get("seats", []) if s["seat"] != self._seat and not s["lost"]]
        if mine is None or not foes:
            return True
        ready = [p for p in mine["battlefield"] if p["power"] and not p["tapped"] and not p["sick"]]
        if sum(p["power"] for p in ready) >= min(s["life"] for s in foes):
            return True  # lethal
        if "flying" in text or "can't be blocked" in text:
            return True
        blockers = [p for s in foes for p in s["battlefield"] if p["power"] is not None and not p["tapped"]]
        if any(p["power"] >= toughness and p["toughness"] > power for p in blockers):
            return False  # something kills it and survives
        threat = sum(p["power"] for s in foes for p in s["battlefield"] if p["power"])  # summoning sickness wears off by their turn
        return threat < mine["life"]


    def _smart_block(self, prompt: str, options: Sequence[str]) -> int | None:
        """With "block": block to kill an attacker the creature survives, else join a double block planned for it, else trade with a
        bigger creature, else take the hardest hit it survives, else plan a double block that kills an attacker neither blocker could alone (and the attacker cannot kill both),
        else chump the biggest attacker when what is coming would be lethal. None when none of these applies: the plain rules go on."""
        label = prompt.removeprefix(BLOCK_PROMPT)
        me = _Fighter(label, next((c for n, c in self._cards.items() if label.startswith(n + " ")), None))
        attackers = [(i, _Fighter(options[i].removeprefix("Block "))) for i in range(1, len(options))]
        turn = (self._state or {}).get("turn")
        if turn != self._joint_turn:
            self._joint, self._joint_turn = {}, turn
        for i, attacker in attackers:  # a double block planned for this attacker, with this creature as one of the blockers
            if _spot(label) in [_spot(b) for b in self._joint.get(_spot(attacker.label), [])]:
                return i
        safe = [(attacker.value, attacker.power, i) for i, attacker in attackers if me.kills(attacker) and me.survives(attacker)]
        if safe:
            return max(safe)[2]
        trades = [(attacker.value - me.value, attacker.power, i) for i, attacker in attackers if me.kills(attacker) and attacker.value > me.value]
        if trades:
            return max(trades)[2]
        best = self._double_block(me, attackers)
        if best is not None:
            return best
        absorbed = [(attacker.power, i) for i, attacker in attackers if me.survives(attacker)]  # (it kills none of them, or it would be above)
        if absorbed:
            return max(absorbed)[1]  # the hardest hitter it takes for nothing
        if sum(a.power for _, a in attackers) >= self._life_of(self._seat) and not any(me.survives(a) for _, a in attackers):
            return max(attackers, key=lambda ia: ia[1].power)[0]  # nothing it can do but chump: the biggest first
        return None

    def _double_block(self, me: _Fighter, attackers: list[tuple[int, _Fighter]]) -> int | None:
        """The attacker to block together with another of the bot's untapped creatures: one they kill between them and that cannot kill both
        of them (when it can kill one, it is a bigger creature than that one). Records the plan so the other blocker joins when it is asked."""
        mine = self._my_seat()
        if mine is None:
            return None
        planned = {_spot(b) for blockers in self._joint.values() for b in blockers}
        partners = []
        for index, p in enumerate(mine["battlefield"]):
            if p["power"] is None or p["tapped"] or f"(seat {self._seat}, #{index + 1})" == _spot(me.label) or f"(seat {self._seat}, #{index + 1})" in planned:
                continue
            partners.append(_Fighter(f"{p['name']} {p['power']}/{p['toughness']} (seat {self._seat}, #{index + 1})",
                                     next((c for n, c in self._cards.items() if n == p["name"]), None)))
        found: list[tuple[int, int, int, _Fighter]] = []
        for i, attacker in attackers:
            for other in partners:
                together = me.deathtouch or other.deathtouch or me.power + other.power >= attacker.toughness > 0
                if not together or me.kills(attacker) or other.kills(attacker):
                    continue  # (one of them could do it alone: the single-block rules had their say)
                if attacker.power >= me.toughness + other.toughness and not (me.indestructible or other.indestructible):
                    continue  # it would kill both
                # (what the attacker can kill is worth less than it: neither blocker kills it alone, so its toughness is above their power
                # and its power at least their toughness; the fewer it can kill, the better)
                losses = [x.value for x in (me, other) if attacker.power >= x.toughness and not x.indestructible]
                found.append((attacker.value, -len(losses), i, other))
        if not found:
            return None
        _, _, i, other = max(found, key=lambda f: f[:3])
        spot = _spot(dict(attackers)[i].label)
        self._joint[spot] = [me.label, other.label]
        return i

    def _my_seat(self) -> dict | None:
        return next((s for s in (self._state or {}).get("seats", []) if s["seat"] == self._seat), None)

    def _lands(self) -> int:
        """Lands the bot has in play and in hand."""
        mine = self._my_seat()
        in_play = sum("Land" in p["type"] for p in mine["battlefield"]) if mine else 0
        in_hand = sum(is_land(self._cards[name]) for name in (self._state or {}).get("hand", []) if name in self._cards)
        return in_play + in_hand

    def _creatures(self, mine: bool) -> int:
        return sum("Creature" in p["type"] for s in (self._state or {}).get("seats", [])
                   if (s["seat"] == self._seat) == mine and not s["lost"] for p in s["battlefield"])

    def _wants_on_top(self, card: Card) -> bool:
        """For scry and surveil: a land while it's short of lands, or a spell it can cast soon."""
        return self._lands() < LAND_GOAL if is_land(card) else card.cmc <= self._lands() + 1

    def _cycle_away(self, card: Card | None) -> bool:
        """Cycle a land once it has enough, or a spell it won't be able to cast for a while."""
        if card is None:
            return False
        return self._lands() >= LAND_GOAL if is_land(card) else card.cmc > self._lands() + 2

    def _holds_removal(self, card: Card | None) -> bool:
        """With "hold": a spell that removes a creature waits while the opponents have no creature (it could only be cast at the bot's
        own), and while every creature they have is small (power `SMALL_THREAT` or less), unless the bot is under pressure (at
        `CHUMP_LIFE` or less) or its hand is full (a card it would discard is cast)."""
        if "hold" not in self.features or card is None or not _is_creature_removal(card):
            return False
        mine = self._my_seat()
        foes = [s for s in (self._state or {}).get("seats", []) if s["seat"] != self._seat and not s["lost"]]
        if mine is None or not foes:
            return False
        powers = [p["power"] for s in foes for p in s["battlefield"] if p["power"] is not None]
        if not powers:
            return True  # nothing of theirs to remove: cast now, it would go at one of its own creatures
        if self._life_of(self._seat) <= self.CHUMP_LIFE or len((self._state or {}).get("hand", [])) >= HAND_SIZE:
            return False
        return all(power <= SMALL_THREAT for power in powers)

    def _unhelpful_wipe(self, card: Card | None) -> bool:
        """A wipe that hits everyone's creatures is only worth it when opponents have more of them."""
        return card is not None and _is_wipe(card) and self._creatures(mine=False) <= self._creatures(mine=True)

    def _is_buff_aura(self, name: str) -> bool:
        """An Aura that helps its target, as opposed to a Pacifism-style one that hurts it."""
        if name in HELPS_ITS_TARGET:
            return True
        card = self._cards.get(name)
        return (card is not None and "Aura" in card.type_line and "can't attack or block" not in card.oracle_text
                and "You control enchanted creature" not in card.oracle_text)

    def _life_of(self, seat: int | None) -> int:
        """The last life total heard for a seat; 0 for one not heard from."""
        return self._life.get(seat, 0) if seat is not None else 0

    def _block(self, prompt: str, options: Sequence[str]) -> int:
        toughness = _stats(prompt)[1]
        powers = {i: _stats(options[i])[0] for i in range(1, len(options))}
        if "commander" in self.features and (lethal := self._lethal_commander(options)) is not None:
            return lethal
        if "block" in self.features and (smart := self._smart_block(prompt, options)) is not None:
            return smart
        survivable = [i for i, p in powers.items() if p < toughness]
        if survivable:
            return max(survivable, key=powers.__getitem__)
        if self._life_of(self._seat) <= self.CHUMP_LIFE:
            return max(powers, key=powers.__getitem__)
        return 0


class _Fighter:
    """A creature in a block decision: its size and the combat keywords the bot knows it has (only its own creatures' text is known)."""

    def __init__(self, label: str, card: Card | None = None):
        self.label = label
        self.power, self.toughness = _stats(label)
        text = card.oracle_text.lower() if card else ""
        self.deathtouch = "deathtouch" in text
        self.first_strike = "first strike" in text or "double strike" in text
        self.indestructible = "indestructible" in text

    @property
    def value(self) -> int:
        return self.power + self.toughness

    def kills(self, other: "_Fighter") -> bool:
        return self.deathtouch and self.power > 0 or self.power >= other.toughness > 0

    def survives(self, other: "_Fighter") -> bool:
        """Whether it lives through the other one's hit (the other is taken to have no first strike or deathtouch: it isn't known)."""
        return self.indestructible or other.power < self.toughness or (self.first_strike and self.kills(other))


def _spot(label: str) -> str:
    """Which permanent a label is: its "(seat 1, #3)" (the stats in the label change, the spot does not)."""
    return label[label.rindex("("):] if "(" in label else label


def _enters_tapped(card: Card) -> bool:
    return "enters tapped" in card.oracle_text or "enters the battlefield tapped" in card.oracle_text


def _threat(seat: dict) -> float:
    """How dangerous a player looks: creature power first, then half a point for each nonland permanent and card in hand."""
    board = seat.get("battlefield", [])
    return sum(p.get("power") or 0 for p in board) + 0.5 * sum(1 for p in board if "Land" not in p.get("type", "")) + 0.5 * seat.get("hand", 0)


_MODE_GOOD = ("destroy", "exile", "counter target", "damage", "return target")  # removal and interaction
_MODE_USEFUL = ("draw", "create", "counter on", "gets +", "gain")
_MODE_BAD = ("you lose", "you discard", "you sacrifice")


def _mode_score(text: str) -> int:
    """How much the bot wants a mode: removal most, then cards, tokens and buffs; costs to itself count against it."""
    text = text.lower()
    return (3 * any(w in text for w in _MODE_GOOD) + 2 * any(w in text for w in _MODE_USEFUL)
            - 3 * any(w in text for w in _MODE_BAD))


def _is_creature_removal(card: Card) -> bool:
    """An instant or sorcery that destroys, exiles, bounces, shrinks or damages a target creature (not a wipe, and not burn for the face)."""
    text = card.oracle_text.lower()
    return (("Instant" in card.type_line or "Sorcery" in card.type_line) and re.search(r"target (?:[\w-]+ )*creature(?! card)", text) is not None
            and any(word in text for word in ("destroy", "exile", "damage", "return target", "gets -")))


def _is_wipe(card: Card) -> bool:
    """A spell that destroys, exiles, bounces or damages every creature, its controller's too."""
    def everyone(kind: str) -> bool:
        return (("creature" in kind or "permanent" in kind)
                and not kind.endswith(("you don't control", "an opponent controls", "your opponents control")))
    return any((isinstance(e, (DestroyAll, ExileAll, ReturnAllToHand)) and everyone(e.kind))
               or (isinstance(e, DamageEach) and e.creatures == "all") for e in spell_effects(card) or [])


def _cast_name(option: str) -> str:
    """The card in a "Cast: ...", "Cast commander: ..." or "Cast from graveyard: ..." action."""
    return option.removeprefix(CAST).removeprefix(CAST_COMMANDER).removeprefix(CAST_GRAVEYARD).removeprefix(CAST_EXILE).removeprefix(CAST_PREPARED)


def _is_ritual(card: Card | None) -> bool:
    """A card that only adds mana ("Add {B}{B}{B}."): the bot doesn't plan ahead, so it would only waste it."""
    lines = [line.strip() for line in (card.oracle_text if card else "").splitlines() if line.strip()]
    return bool(lines) and all(re.fullmatch(r"Add (\{[WUBRGC]\})+\.", line) for line in lines)


def _limited_cost(action: str) -> bool:
    """Whether an activation's cost can only be paid a limited number of times."""
    cost = action.split("): ", 1)[1].split(":", 1)[0]
    if cost.startswith("Crew "):
        return True  # it taps creatures, and a Vehicle that is already a creature isn't crewed again
    if re.search(r"Sacrifice (a|an|another) |Discard a card|Exile a card", cost):
        return False  # the bot doesn't pay with its own cards
    return "{T}" in cost or "Sacrifice" in cost or re.fullmatch(r"[+\u2212-]?\d+", cost) is not None


def _equip_needed(action: str) -> bool:
    """An "Equip" activation for Equipment that isn't attached to anything yet (once attached, its
    label says "attached to ...", so the bot doesn't equip over and over)."""
    label, text = action.split("): ", 1)
    return text.startswith(("Equip ", "Equip\u2014")) and " attached to " not in label


def _prompt_number(prompt: str, after: str) -> int:
    """The number that follows `after` in a prompt ("... total mana value 8)" -> 8), or 0."""
    m = re.search(re.escape(after) + r"(\d+)", prompt)
    return int(m[1]) if m else 0


def _stats(label: str) -> tuple[int, int]:
    """Power and toughness from a label like "Grizzly Bears 2/2 (seat 1, #3)"; unknowns count as 0."""
    match = re.search(r" (\S+)/(\S+) \(seat", label)
    if not match:
        return 0, 0
    power, toughness = (int(v) if v.isdigit() else 0 for v in match.groups())
    return power, toughness


def _seat_of(label: str) -> int | None:
    match = re.search(r"\(seat (\d+)", label)
    return int(match[1]) if match else None


def opening_hand(cards: list[Card], rng: random.Random, free_mulligan: bool = True) -> tuple[list[Card], list[Card], int]:
    """Shuffle `cards`, mulligan by the bot's rules, and return (hand, library, mulligans taken). The bottomed cards of a
    kept mulligan go to the bottom of the library; a free first mulligan bottoms nothing."""
    library, hand = list(cards), []
    mulligans = 0
    while True:
        library += hand
        rng.shuffle(library)
        hand, library = library[:HAND_SIZE], library[HAND_SIZE:]
        if keep_hand(hand, mulligans):
            break
        mulligans += 1
    for _ in range(max(0, mulligans - (1 if free_mulligan else 0))):
        library.append(hand.pop(worst_card(hand)))
    return hand, library, mulligans


@dataclass
class GoldfishStats:
    games: int
    mulligan_rate: float  # share of games with at least one mulligan
    average_opening_lands: float  # lands in the kept hand, after bottoming
    land_drop_rate: dict[int, float]  # turn -> share of games with a land on every turn so far


def goldfish(deck: Deck, games: int = 1000, turns: int = 5, seed: int = 0, free_mulligan: bool = True) -> GoldfishStats:
    """Play `deck` alone `games` times with the bot's mulligan rules and one land a turn.

    Draws every turn, as in a multiplayer game; `free_mulligan` matches the
    multiplayer free first mulligan.
    """
    mulliganed = 0
    opening_lands = 0
    on_curve = {turn: 0 for turn in range(1, turns + 1)}
    for game in range(games):
        rng = random.Random(f"{seed}-{game}")
        hand, library, mulligans = opening_hand(deck.main, rng, free_mulligan)
        mulliganed += mulligans > 0
        opening_lands += sum(1 for c in hand if is_land(c))

        for turn in range(1, turns + 1):
            if library:
                hand.append(library.pop(0))
            land = next((c for c in hand if is_land(c)), None)
            if land is None:
                break
            hand.remove(land)
            on_curve[turn] += 1
    return GoldfishStats(
        games=games,
        mulligan_rate=round(mulliganed / games, 3),
        average_opening_lands=round(opening_lands / games, 2),
        land_drop_rate={turn: round(hits / games, 3) for turn, hits in on_curve.items()},
    )
