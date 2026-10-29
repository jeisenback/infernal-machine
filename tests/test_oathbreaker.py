"""Oathbreaker: a planeswalker and a signature spell in the command zone (#365)."""

import dataclasses
import json
import os
import tempfile
import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import CARD_FORMAT, BulkSource, Card, Deck, load_deck, parse_decklist
from infernal_machine.formats import COMMANDER, FORMATS, OATHBREAKER, deck_problems, format_of, with_format
from infernal_machine.game import CAST, CAST_COMMANDER, PASS, Game, Permanent
from infernal_machine.oathbreaker import deck_problems as oathbreaker_problems
from tests.helpers import FOREST, ScriptedPlayer, lands, pick, real, run_stack, table

OATH = Card(name="Oath Walker", mana_cost="{2}{G}", cmc=3, type_line="Planeswalker — Test", loyalty="3", color_identity=("G",))
SIG = dataclasses.replace(real("Sig Spell", "{1}", "Sorcery", "Draw a card."), color_identity=("G",))
SIG_REMOVAL = dataclasses.replace(real("Sig Kill", "{1}", "Instant", "Destroy target creature."), color_identity=("G",))
BEAR = dataclasses.replace(real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2"), color_identity=("G",))
RED_BEAR = dataclasses.replace(BEAR, name="Red Cub", color_identity=("R",))


def oath_deck(main=None, oathbreaker=OATH, signature=SIG, size=60, **more):
    others = main if main is not None else [BEAR] + [FOREST] * (size - 3)
    return Deck([oathbreaker] if oathbreaker else [], list(others), [], signature_spell=signature, **more)


class FormatTests(unittest.TestCase):
    def test_the_numbers(self):
        self.assertEqual((OATHBREAKER.life, OATHBREAKER.min_deck, OATHBREAKER.copy_limit, OATHBREAKER.commander), (20, 60, 1, True))
        self.assertIsNone(OATHBREAKER.commander_damage, "there is no commander damage")
        self.assertEqual(OATHBREAKER.label, "Oathbreaker")
        self.assertIs(FORMATS["oathbreaker"], OATHBREAKER)
        self.assertEqual(COMMANDER.commander_damage, 21)

    def test_it_is_asked_for_by_name_and_needs_a_commander(self):
        self.assertIs(format_of([with_format(oath_deck(), "oathbreaker")]), OATHBREAKER)
        self.assertIs(format_of([oath_deck()]), COMMANDER, "60 cards with a planeswalker is not taken for Oathbreaker: it has to be asked for")
        with self.assertRaises(ValueError):
            format_of([Deck([], [FOREST] * 60, [], format="oathbreaker")])


class DeckRulesTests(unittest.TestCase):
    def problems(self, deck):
        return deck_problems(deck, OATHBREAKER)

    def test_a_legal_deck(self):
        self.assertEqual(self.problems(oath_deck()), [])
        self.assertEqual(oathbreaker_problems(oath_deck()), [])

    def test_sixty_cards_counting_the_oathbreaker_and_the_signature_spell(self):
        self.assertIn("Deck has 59 cards including the Oathbreaker and the signature spell; needs exactly 60", self.problems(oath_deck(size=59)))
        self.assertTrue(any("needs exactly 60" in p for p in self.problems(oath_deck(size=61))))
        self.assertTrue(any("has 59 cards" in p for p in self.problems(Deck([OATH], [BEAR] + [FOREST] * 57, [], signature_spell=None))), "without a signature spell")

    def test_one_oathbreaker_and_it_is_a_planeswalker(self):
        self.assertTrue(any("0 Oathbreakers" in p for p in self.problems(oath_deck(oathbreaker=None))))
        two = Deck([OATH, dataclasses.replace(OATH, name="Second")], [BEAR] + [FOREST] * 56, [], signature_spell=SIG)
        self.assertTrue(any("2 Oathbreakers" in p for p in self.problems(two)))
        creature = dataclasses.replace(BEAR, name="Legend", type_line="Legendary Creature — Elf")
        self.assertIn("Legend can't be your Oathbreaker (it is not a planeswalker)", self.problems(oath_deck(oathbreaker=creature)))

    def test_any_planeswalker_will_do_it_need_not_be_legendary(self):
        self.assertNotIn("Legendary", OATH.type_line)
        self.assertEqual([p for p in self.problems(oath_deck()) if "Oathbreaker" in p], [])

    def test_a_signature_spell_that_is_an_instant_or_sorcery(self):
        self.assertIn("Deck has no signature spell", self.problems(oath_deck(signature=None)))
        self.assertIn("Cub can't be your signature spell (it is not an instant or sorcery)", self.problems(oath_deck(signature=BEAR, main=[FOREST] * 58)))
        self.assertEqual(self.problems(oath_deck(signature=SIG_REMOVAL)), [])

    def test_singleton_and_the_oathbreakers_colors_for_every_card_and_the_signature_spell(self):
        double = oath_deck(main=[BEAR, BEAR] + [FOREST] * 56)
        self.assertIn("Cub: 2 copies, limit is 1", self.problems(double))
        sig_twice = oath_deck(main=[SIG] + [FOREST] * 57)
        self.assertIn("Sig Spell: 2 copies, limit is 1", self.problems(sig_twice))
        off = oath_deck(main=[RED_BEAR] + [FOREST] * 57)
        self.assertIn("Red Cub is outside the Oathbreaker's color identity (R)", self.problems(off))
        off_sig = oath_deck(signature=dataclasses.replace(SIG, color_identity=("R",)))
        self.assertIn("Sig Spell is outside the Oathbreaker's color identity (R)", self.problems(off_sig))

    def test_cards_must_be_legal_in_oathbreaker(self):
        banned = dataclasses.replace(BEAR, name="Banned Cub", legal=("commander",))
        self.assertEqual(self.problems(oath_deck(main=[banned] + [FOREST] * 57)), ["Banned Cub is not legal in Oathbreaker"])
        banned_sig = dataclasses.replace(SIG, legal=("commander",))
        self.assertEqual(self.problems(oath_deck(signature=banned_sig)), ["Sig Spell is not legal in Oathbreaker"])


class CardTests(unittest.TestCase):
    def test_legality_is_read_from_scryfall_on_every_face(self):
        banned = {"commander": "legal", "oathbreaker": "banned"}

        def faces(layout, back_type="Instant"):
            return {"name": "Front // Back", "layout": layout, "cmc": 1, "legalities": banned,
                    "card_faces": [{"name": "Front", "mana_cost": "{R}", "type_line": "Creature — Imp", "oracle_text": "", "power": "1", "toughness": "1"},
                                   {"name": "Back", "mana_cost": "{R}", "type_line": back_type, "oracle_text": "", "colors": ["R"]}]}
        plain = {"name": "Cub", "type_line": "Creature", "cmc": 0, "legalities": banned}
        self.assertFalse(Card.from_scryfall(plain).legal_in("oathbreaker"))
        self.assertTrue(Card.from_scryfall({**plain, "legalities": {"oathbreaker": "legal"}}).legal_in("oathbreaker"))
        self.assertFalse(Card.from_scryfall(faces("modal_dfc", "Land")).back.legal_in("oathbreaker"))
        self.assertFalse(Card.from_scryfall(faces("prepare")).prepare.legal_in("oathbreaker"))
        self.assertFalse(Card.from_scryfall(faces("transform", "Creature — Imp")).flip.legal_in("oathbreaker"))
        self.assertFalse(Card.from_scryfall(faces("adventure")).alternate.legal_in("oathbreaker"))
        self.assertGreaterEqual(CARD_FORMAT, 6)


class DecklistTests(unittest.TestCase):
    def test_the_sections(self):
        parsed = parse_decklist("Oathbreaker\n1 Oath Walker\n\nSignature Spell\n1 Sig Spell\n\nDeck\n4 Forest\n")
        self.assertEqual((parsed.commanders, parsed.signature, parsed.main), ({"Oath Walker": 1}, {"Sig Spell": 1}, {"Forest": 4}))
        self.assertEqual(parse_decklist("Signature\n1 Sig Spell\n").signature, {"Sig Spell": 1})
        self.assertEqual(parse_decklist("Commander\n1 Oath Walker\n").commanders, {"Oath Walker": 1})

    def test_load_deck_gives_the_signature_spell_and_refuses_two(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bulk.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, OATH, SIG, SIG_REMOVAL)}}, f)
            source = BulkSource(path)
            loaded = load_deck("Oathbreaker\n1 Oath Walker\n\nSignature Spell\n1 Sig Spell\n\nDeck\n4 Forest\n", source)
            self.assertEqual((loaded.commanders[0].name, loaded.signature_spell.name, len(loaded.main)), ("Oath Walker", "Sig Spell", 4))
            self.assertIsNone(load_deck("Deck\n4 Forest\n", source).signature_spell)
            with self.assertRaises(ValueError):
                load_deck("Signature Spell\n1 Sig Spell\n1 Sig Kill\n\nDeck\n4 Forest\n", source)


def oath_game(policy=None, mana=0):
    game, a, b = table(policy)
    seat = game.seats[0]
    seat.command_zone = [OATH, SIG]
    seat.commander_names = {"Oath Walker", "Sig Spell"}
    seat.signature = "Sig Spell"
    seat.battlefield = lands(mana)
    return game, seat


class GameTests(unittest.TestCase):
    def test_a_seat_starts_with_both_in_the_command_zone_and_20_life(self):
        deck = with_format(oath_deck(), "oathbreaker")
        game = Game([(ScriptedPlayer("A"), deck), (ScriptedPlayer("B"), deck)], seed=1, format=OATHBREAKER)
        seat = game.seats[0]
        self.assertEqual([c.name for c in seat.command_zone], ["Oath Walker", "Sig Spell"])
        self.assertEqual(seat.commander_names, {"Oath Walker", "Sig Spell"})
        self.assertEqual((seat.signature, seat.life), ("Sig Spell", 20))

    def test_a_deck_without_a_signature_spell_has_none(self):
        deck = Deck([OATH], [FOREST] * 20, [])
        game = Game([(ScriptedPlayer("A"), deck), (ScriptedPlayer("B"), deck)], seed=1)
        self.assertEqual((game.seats[0].signature, [c.name for c in game.seats[0].command_zone]), (None, ["Oath Walker"]))

    def test_the_signature_spell_needs_the_oathbreaker_on_the_battlefield(self):
        game, seat = oath_game(mana=5)
        actions = game.legal_actions(seat)
        self.assertIn(CAST_COMMANDER + "Oath Walker", actions)
        self.assertNotIn(CAST_COMMANDER + "Sig Spell", actions)
        seat.battlefield.append(Permanent(OATH))
        self.assertIn(CAST_COMMANDER + "Sig Spell", game.legal_actions(seat))

    def test_a_permanent_of_the_same_name_that_is_not_the_oathbreaker_does_not_count_for_a_spell(self):
        game, seat = oath_game(mana=5)
        seat.battlefield.append(Permanent(BEAR))
        self.assertNotIn(CAST_COMMANDER + "Sig Spell", game.legal_actions(seat))

    def test_the_signature_spell_is_cast_at_its_timing(self):
        instant = dataclasses.replace(SIG, name="Sig Instant", type_line="Instant")
        game, seat = oath_game(mana=5)
        seat.command_zone, seat.commander_names, seat.signature = [OATH, instant], {"Oath Walker", "Sig Instant"}, "Sig Instant"
        seat.battlefield.append(Permanent(OATH))
        game.active = 1  # the other player's turn: an instant is still castable, a sorcery would not be
        self.assertIn(CAST_COMMANDER + "Sig Instant", game.legal_actions(seat))
        seat.command_zone = [OATH, SIG]
        seat.signature, seat.commander_names = "Sig Spell", {"Oath Walker", "Sig Spell"}
        self.assertNotIn(CAST_COMMANDER + "Sig Spell", game.legal_actions(seat))

    def test_cast_it_and_it_returns_to_the_command_zone_costing_two_more(self):
        game, seat = oath_game(pick(CAST_COMMANDER + "Sig Spell", "Command zone"), mana=6)
        seat.battlefield.append(Permanent(OATH))
        before = len(seat.library)
        game._perform(seat, CAST_COMMANDER + "Sig Spell")
        run_stack(game)
        self.assertEqual(len(seat.library), before - 1, "it drew a card")
        self.assertIn("Sig Spell", [c.name for c in seat.command_zone], "back in the command zone, not the graveyard")
        self.assertNotIn("Sig Spell", [c.name for c in seat.graveyard])
        self.assertEqual(game.commander_tax(seat, SIG), 2)
        self.assertEqual(game.commander_tax(seat, OATH), 0, "the Oathbreaker's own tax is its own")

    def test_there_is_no_commander_damage(self):
        deck = with_format(oath_deck(), "oathbreaker")
        game = Game([(ScriptedPlayer("A"), deck), (ScriptedPlayer("B"), deck)], seed=1, format=OATHBREAKER)
        game.turn, game.active, game.step = 2, 0, "main1"
        game.seats[1].commander_damage[(0, "Oath Walker")] = 100
        game._check_state()
        self.assertFalse(game.seats[1].lost)

    def test_combat_damage_from_the_oathbreaker_is_not_commander_damage(self):
        # the Oathbreaker, animated, hits a player: in Commander that is commander damage, here it is not recorded at all
        attacker = dataclasses.replace(BEAR, name="Oath Walker", type_line="Planeswalker Creature — Test", power="5", toughness="5")
        attack_all = lambda prompt, options: 1 if prompt.startswith("Attack with") else (options.index(PASS) if PASS in options else 0)  # noqa: E731
        results = {}
        for fmt in (OATHBREAKER, COMMANDER):
            deck = with_format(oath_deck(), fmt.name)
            game = Game([(ScriptedPlayer("A", attack_all), deck), (ScriptedPlayer("B"), deck)], seed=1, format=fmt)
            game.turn, game.active, game.step = 2, 0, "main1"
            game.seats[0].battlefield = [Permanent(attacker)]
            events = []
            game.broadcast = lambda event, skip=None, sink=events: sink.append(event)  # type: ignore[method-assign]
            game.combat.declare_attackers(game.seats[0])
            game.combat.deal_damage(first_strike_step=False)
            results[fmt.name] = (dict(game.seats[1].commander_damage), any(e.get("event") == "commander_damage" for e in events))
        self.assertEqual(results["oathbreaker"], ({}, False))
        self.assertEqual(results["commander"], ({(0, "Oath Walker"): 5}, True), "the same hit is commander damage in Commander")

    def test_a_permanent_with_the_signature_spells_name_is_not_an_oathbreaker(self):
        game, seat = oath_game(mana=5)
        seat.battlefield.append(Permanent(dataclasses.replace(BEAR, name="Sig Spell")))
        self.assertNotIn(CAST_COMMANDER + "Sig Spell", game.legal_actions(seat))

    def test_the_seats_are_not_told_a_commander_damage_limit(self):
        events = []
        deck = with_format(oath_deck(), "oathbreaker")
        game = Game([(ScriptedPlayer("A"), deck), (ScriptedPlayer("B"), deck)], seed=1, format=OATHBREAKER)
        game.broadcast = lambda event, skip=None: events.append(event)  # type: ignore[method-assign]
        game.setup()
        seats = [e for e in events if e.get("event") == "seat"]
        self.assertTrue(seats)
        self.assertTrue(all("damage_limit" not in e for e in seats))
        self.assertEqual(seats[0]["commanders"], ["Oath Walker", "Sig Spell"])


class BotTests(unittest.TestCase):
    def bot(self, signature=SIG, battlefield=()):
        b = BotPlayer("Bot", oath_deck(signature=signature), features=FEATURES)
        b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
        b.notify({"event": "state", "hand": [], "seats": [
            {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": list(battlefield), "command_zone": [{"name": "Oath Walker", "tax": 0}, {"name": signature.name, "tax": 0}]},
            {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": [], "command_zone": []}]})
        return b

    def test_the_oathbreaker_is_cast_first_like_a_commander(self):
        options = [PASS, CAST_COMMANDER + "Sig Spell", CAST_COMMANDER + "Oath Walker"]
        self.assertEqual(self.bot().choose("Priority: main1", options), 2)

    def test_the_signature_spell_is_cast_like_any_spell(self):
        self.assertEqual(self.bot().choose("Priority: main1", [PASS, CAST_COMMANDER + "Sig Spell"]), 1)

    def test_a_signature_removal_spell_is_held_for_a_creature_worth_it(self):
        b = self.bot(SIG_REMOVAL)
        self.assertEqual(b.choose("Priority: main1", [PASS, CAST_COMMANDER + "Sig Kill"]), 0, "nothing of theirs to remove")

    def test_a_card_cast_from_hand_still_competes_normally(self):
        options = [PASS, CAST + "Cub", CAST_COMMANDER + "Sig Spell"]
        self.assertIn(self.bot().choose("Priority: main1", options), (1, 2))


if __name__ == "__main__":
    unittest.main()
