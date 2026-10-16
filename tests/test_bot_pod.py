"""The bot in a pod: whom to attack, and where a commander goes when it would leave the battlefield (#376)."""

import unittest

from infernal_machine.bot import FEATURES, RECURSION, BotPlayer, _threat
from infernal_machine.cards import Card, Deck
from infernal_machine.combat import ATTACK_PROMPT
from infernal_machine.game import COMMAND_ZONE_PROMPT
from tests.helpers import real

BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3")
SECOND = Card(name="Second Boss", mana_cost="{4}{G}", cmc=5, type_line="Legendary Creature — Elf", power="4", toughness="4")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
REANIMATE = real("Reanimate", "{B}", "Sorcery", "Put target creature card from a graveyard onto the battlefield under your control. You lose life equal to that card's mana value.")
REGROWTH = real("Regrowth", "{1}{G}", "Sorcery", "Return target card from your graveyard to your hand.")
WITNESS = real("Eternal Witness", "{1}{G}{G}", "Creature — Human Shaman", "When this creature enters, you may return target card from your graveyard to your hand.", "2", "1")
SUN_TITAN = real("Sun Titan", "{4}{W}{W}", "Creature — Giant", "Vigilance\nWhenever this creature enters or attacks, you may return target permanent card with mana value 3 or less from your graveyard to the battlefield.", "6", "6")
BOG = real("Bojuka Bog", "", "Land", "This land enters tapped.\nWhen this land enters, exile target player's graveyard.\n{T}: Add {B}.")
OOZE = real("Scavenging Ooze", "{1}{G}", "Creature — Ooze", "{G}: Exile target card from a graveyard. If it was a creature card, put a +1/+1 counter on this creature and you gain 1 life.", "2", "2")
WRATH = real("Wrath of God", "{2}{W}{W}", "Sorcery", "Destroy all creatures. They can't be regenerated.")

OPTIONS = ["Don't attack", "Attack Player: One (seat 1)", "Attack Player: Two (seat 2)", "Attack Player: Three (seat 3)"]


def creature(power, tapped=False, sick=False):
    return {"name": "Body", "type": "Creature", "power": power, "toughness": power, "tapped": tapped, "sick": sick}


def seat(index, life, board=(), hand=3):
    return {"seat": index, "lost": False, "life": life, "hand": hand, "mana_pool": [], "battlefield": list(board), "command_zone": [], "commander_damage": []}


# These tests are about whom to attack, not whether to: the attack judgment (which would keep a 3/3 home against 4/4 blockers) is off.
CHOOSING = FEATURES - {"attack"}


def bot(foes, mine=(), features=CHOOSING, deck=None):
    b = BotPlayer("Bot", deck or Deck([BOSS], [FOREST], []), features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
    for s in foes:
        b.notify({"event": "seat", "seat": s["seat"], "name": f"P{s['seat']}", "life": s["life"]})
    b.notify({"event": "state", "hand": [], "seats": [seat(0, 40, mine), *foes]})
    return b


def pick(b):
    return b.choose(ATTACK_PROMPT + "Body 3/3 (seat 0, #5)", OPTIONS)


def board_of(*powers):
    return [creature(p) for p in powers]


class ThreatTests(unittest.TestCase):
    def foes(self):
        return [seat(1, 30, board_of(4, 4), hand=5), seat(2, 12, [], hand=2), seat(3, 25, board_of(2), hand=3)]

    def test_the_plain_bot_attacks_the_lowest_life(self):
        self.assertEqual(pick(bot(self.foes(), [creature(3)], features=CHOOSING - {"threat"})), 2)

    def test_it_attacks_the_most_dangerous_opponent_when_it_cannot_kill_anyone(self):
        self.assertEqual(pick(bot(self.foes(), [creature(3)])), 1)  # eight power on the board and five cards in hand

    def test_it_finishes_an_opponent_its_ready_creatures_can_kill(self):
        self.assertEqual(pick(bot(self.foes(), board_of(5, 4, 3))), 2)  # twelve ready power against twelve life

    def test_among_several_it_can_kill_it_takes_the_lowest_life(self):
        foes = [seat(1, 11, board_of(4, 4)), seat(2, 6), seat(3, 9, board_of(2))]
        self.assertEqual(pick(bot(foes, board_of(6, 6))), 2)

    def test_creatures_that_cannot_attack_do_not_count_toward_a_kill(self):
        mine = [creature(5), creature(5, tapped=True), creature(5, sick=True)]
        self.assertEqual(pick(bot(self.foes(), mine)), 1)  # five ready power against twelve life: no kill

    def test_a_tie_in_danger_goes_to_the_lower_life(self):
        foes = [seat(1, 30, board_of(3), hand=3), seat(2, 20, board_of(3), hand=3), seat(3, 25, board_of(3), hand=3)]
        self.assertEqual(pick(bot(foes, [creature(1)])), 2)

    def test_one_opponent_is_just_that_opponent(self):
        b = bot([seat(1, 30, board_of(9))], [creature(3)])
        self.assertEqual(b.choose(ATTACK_PROMPT + "Body 3/3 (seat 0, #5)", OPTIONS[:2]), 1)

    def test_the_threat_score(self):
        self.assertEqual(_threat(seat(1, 20, board_of(3, 2), hand=4)), 5 + 0.5 * 2 + 0.5 * 4)
        self.assertEqual(_threat(seat(1, 20, [{"name": "Forest", "type": "Basic Land", "power": None}], hand=0)), 0)  # a land is nothing
        self.assertEqual(_threat({"battlefield": []}), 0)  # (a sparse snapshot)

    def test_its_own_commander_going_for_21_still_comes_first(self):
        foes = self.foes()
        foes[2]["commander_damage"] = [{"from_seat": 0, "commander": "Boss", "damage": 19}]
        b = bot(foes, [{**creature(3), "name": "Boss"}])
        self.assertEqual(b.choose(ATTACK_PROMPT + "Boss 3/3 (seat 0, #5)", OPTIONS), 3)  # 19 + 3 reaches 21 on seat 3


class RecursionTests(unittest.TestCase):
    def test_cards_that_bring_one_back(self):
        for card in (REANIMATE, REGROWTH, WITNESS, SUN_TITAN):
            self.assertTrue(RECURSION.search(card.oracle_text), card.name)

    def test_cards_that_do_not(self):
        for card in (BOG, OOZE, WRATH):
            self.assertFalse(RECURSION.search(card.oracle_text), card.name)


class DestinationTests(unittest.TestCase):
    def cast(self, b, times, seat=0, source="command_zone", card="Boss"):
        for _ in range(times):
            b.notify({"event": "cast", "seat": seat, "card": card, "from": source, "targets": [], "x": 0, "tapped": []})
            b.notify({"event": "resolve", "seat": seat, "card": card, "to": "battlefield"})

    def bot(self, casts=0, features=FEATURES, main=(FOREST,), commanders=(BOSS,), **kw):
        b = bot([seat(1, 30)], features=features, deck=Deck(list(commanders), list(main), []), **kw)
        self.cast(b, casts)
        return b

    def test_the_command_zone_is_the_default(self):
        for zone in ("Graveyard", "Exile", "Hand", "Library"):
            self.assertEqual(self.bot().choose(COMMAND_ZONE_PROMPT, ["Command zone", zone]), 0, zone)

    def test_a_commander_that_would_be_bounced_goes_to_the_hand_once_it_has_tax_on_it(self):
        self.assertEqual(self.bot(casts=0).choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 0)  # no tax to save
        self.assertEqual(self.bot(casts=1).choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 1)  # cast from the hand it costs two less
        self.assertEqual(self.bot(casts=4).choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 1)

    def test_a_graveyard_is_worth_it_only_with_a_lot_of_tax_and_a_way_back(self):
        deck = (FOREST, REANIMATE)
        zone = ["Command zone", "Graveyard"]
        self.assertEqual(self.bot(casts=3, main=deck).choose(COMMAND_ZONE_PROMPT, zone), 1)  # six mana of tax and a Reanimate
        self.assertEqual(self.bot(casts=3).choose(COMMAND_ZONE_PROMPT, zone), 0)  # no way back
        self.assertEqual(self.bot(casts=2, main=deck).choose(COMMAND_ZONE_PROMPT, zone), 0)  # only four of tax
        self.assertEqual(self.bot(casts=3, main=(FOREST, WRATH)).choose(COMMAND_ZONE_PROMPT, zone), 0)

    def test_exile_and_the_library_are_never_better(self):
        for zone in ("Exile", "Library"):
            self.assertEqual(self.bot(casts=5, main=(FOREST, REANIMATE)).choose(COMMAND_ZONE_PROMPT, ["Command zone", zone]), 0, zone)

    def test_only_its_own_casts_from_the_command_zone_count(self):
        b = self.bot()
        self.cast(b, 3, seat=1)  # someone else's Boss
        self.cast(b, 3, source="hand")  # its own, but from the hand: no tax
        self.assertEqual(b.choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 0)

    def test_with_partners_the_one_that_left_decides(self):
        b = bot([seat(1, 30)], deck=Deck([BOSS, SECOND], [FOREST], []))
        self.cast(b, 3, card="Second Boss")  # Second Boss has been cast three times (six tax) but is home again, in the command zone
        b.notify({"event": "state", "hand": [], "seats": [{**seat(0, 40), "command_zone": [{"name": "Second Boss", "tax": 6}]}, seat(1, 30)]})
        self.assertEqual(b.choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 0)  # Boss is the one leaving, and it has no tax
        self.cast(b, 1, card="Boss")
        self.assertEqual(b.choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 1)  # now it has been cast once: two mana of tax to save

    def test_without_the_feature_it_always_goes_home(self):
        b = self.bot(casts=5, main=(FOREST, REANIMATE), features=FEATURES - {"destination"})
        self.assertEqual(b.choose(COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), 0)
        self.assertEqual(b.choose(COMMAND_ZONE_PROMPT, ["Command zone", "Graveyard"]), 0)


if __name__ == "__main__":
    unittest.main()
