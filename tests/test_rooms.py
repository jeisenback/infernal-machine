"""Rooms: one card with two doors. Either door is cast; the other is unlocked later by paying its cost; a door's "When you unlock this
door" ability triggers as it unlocks, and a locked door's abilities are not there."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import is_room, room_view
from infernal_machine.game import CAST, UNLOCK, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_x_targets import script

REMINDER = "(You may cast either half. That door unlocks on the battlefield. As a sorcery, you may pay the mana cost of a locked door to unlock it.)"


def scryfall(front, back):
    faces = [{"name": name, "mana_cost": cost, "type_line": "Enchantment — Room", "oracle_text": f"{text}\n{REMINDER}"}
             for name, cost, text in (front, back)]
    return {"name": " // ".join(f["name"] for f in faces), "layout": "split", "cmc": 5.0, "id": "r", "color_identity": [],
            "legalities": {"commander": "legal"}, "card_faces": faces}


DERELICT = Card.from_scryfall(scryfall(("Derelict Attic", "{2}{B}", "When you unlock this door, you draw two cards and you lose 2 life."),
                                       ("Widow's Walk", "{3}{B}", "Whenever a creature you control attacks alone, it gets +1/+0 and gains deathtouch until end of turn.")))
FUNERAL = Card.from_scryfall(scryfall(("Funeral Room", "{2}{B}", "Whenever a creature you control dies, each opponent loses 1 life and you gain 1 life."),
                                      ("Awakening Hall", "{6}{B}{B}", "When you unlock this door, return all creature cards from your graveyard to the battlefield.")))
GLASSWORKS = Card.from_scryfall(scryfall(("Glassworks", "{2}{R}", "When you unlock this door, this Room deals 4 damage to target creature an opponent controls."),
                                         ("Shattered Yard", "{4}{R}", "At the beginning of your end step, this Room deals 1 damage to each opponent.")))
ENTRYWAY = Card.from_scryfall(scryfall(("Grand Entryway", "{1}{W}", "When you unlock this door, create a 1/1 white Glimmer enchantment creature token."),
                                       ("Elegant Rotunda", "{2}{W}", "When you unlock this door, put a +1/+1 counter on each of up to two target creatures.")))
OFFICE = Card.from_scryfall({**scryfall(("Restricted Office", "{2}{W}{W}", "When you unlock this door, destroy all creatures with power 3 or greater."),
                                        ("Lecture Hall", "{5}{U}{U}", "Other permanents you control have hexproof.")),
                             "color_identity": ["W", "U"]})
OGRE = Card(name="Ogre", type_line="Creature \u2014 Ogre", power="3", toughness="3")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def start(room=DERELICT, mana=3):
    game, _ = table3(script(), script())
    a, b, _ = game.seats
    a.hand, a.battlefield, a.library = [room], lands(mana), [FOREST] * 10
    return game, a, b


def cast(game, a, name):
    game._perform(a, CAST + name)
    run_stack(game)
    game._check_state()


def the_room(a):
    return next(p for p in a.battlefield if "Room" in p.card.type_line)


class LoadingTests(unittest.TestCase):
    def test_a_room_has_two_castable_doors(self):
        self.assertEqual((is_room(DERELICT), DERELICT.alternate.name, DERELICT.other_face), (True, "Widow's Walk", ""))

    def test_both_doors_have_to_be_understood(self):
        self.assertEqual(unsupported_lines(DERELICT), [])
        odd = Card.from_scryfall(scryfall(("Front", "{1}", "Draw a card at the end of time."), ("Back", "{2}", "Draw a card.")))
        self.assertEqual(unsupported_lines(odd), ["Draw a card at the end of time.", "Draw a card."])  # (the back door's, too, as a spell line)

    def test_the_view_has_only_the_unlocked_doors(self):
        front = room_view(DERELICT, (DERELICT.name,))
        both = room_view(DERELICT, (DERELICT.name, "Widow's Walk"))
        self.assertEqual((front.name, "attacks alone" in front.oracle_text, "unlock" in front.oracle_text), ("Derelict Attic // Widow's Walk", False, True))
        self.assertTrue("unlock" in both.oracle_text and "attacks alone" in both.oracle_text)
        self.assertIsNone(both.alternate)


class ColorTests(unittest.TestCase):
    def test_a_room_has_the_colors_of_its_unlocked_doors(self):
        front, back = OFFICE, OFFICE.alternate
        self.assertEqual((room_view(OFFICE, (front.name,)).colors, room_view(OFFICE, (back.name,)).colors,
                          room_view(OFFICE, (front.name, back.name)).colors), (("W",), ("U",), ("W", "U")))


class CastingTests(unittest.TestCase):
    def test_both_doors_are_offered_from_the_hand(self):
        game, a, b = start()
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Derelict Attic // Widow's Walk"])  # the other costs {3}{B}

    def test_casting_the_front_door_unlocks_it_and_its_ability_triggers(self):
        game, a, b = start()
        cast(game, a, "Derelict Attic // Widow's Walk")
        room = the_room(a)
        self.assertEqual((room.doors, len(a.hand), a.life), (("Derelict Attic // Widow's Walk",), 2, 38))

    def test_casting_the_back_door_leaves_the_front_ability_out(self):
        game, a, b = start(mana=4)
        cast(game, a, "Widow's Walk")
        room = the_room(a)
        self.assertEqual((room.doors, len(a.hand), a.life), (("Widow's Walk",), 0, 40))
        self.assertIn("attacks alone", room.card.oracle_text)
        self.assertNotIn("draw two", room.card.oracle_text)

    def test_the_card_is_one_object_on_the_battlefield_and_goes_back_whole(self):
        game, a, b = start()
        cast(game, a, "Derelict Attic // Widow's Walk")
        game.destroy(the_room(a))
        self.assertEqual((a.graveyard, [p for p in a.battlefield if "Room" in p.card.type_line]), ([DERELICT], []))

    def test_a_countered_door_spell_puts_the_whole_card_in_the_graveyard(self):
        game, a, b = start()
        game._perform(a, CAST + "Derelict Attic // Widow's Walk")
        game.counter(game.stack[-1])
        self.assertEqual(a.graveyard, [DERELICT])


class UnlockTests(unittest.TestCase):
    def unlocked_front(self, mana=8):
        game, a, b = start(mana=mana)
        cast(game, a, "Derelict Attic // Widow's Walk")
        for p in a.battlefield:
            p.tapped = False
        a.hand = []
        game.step, game.active = "main1", 0
        return game, a, b

    def test_the_locked_door_can_be_unlocked_for_its_cost_at_sorcery_speed(self):
        game, a, b = self.unlocked_front()
        offers = [x for x in game.legal_actions(a) if x.startswith(UNLOCK)]
        self.assertEqual(len(offers), 1)
        self.assertTrue(offers[0].startswith(UNLOCK + "Widow's Walk of "))

    def test_unlocking_adds_the_doors_ability_and_does_not_trigger_the_other(self):
        game, a, b = self.unlocked_front()
        life, cards = a.life, len(a.hand)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(UNLOCK)))
        run_stack(game)
        room = the_room(a)
        self.assertEqual((room.doors, a.life, len(a.hand)), ((DERELICT.name, "Widow's Walk"), life, cards))  # no second "draw two"
        self.assertIn("attacks alone", room.card.oracle_text)
        self.assertEqual(len([p for p in a.battlefield if "Land" not in p.card.type_line]), 1)  # the same Room

    def test_it_costs_the_doors_mana(self):
        game, a, b = self.unlocked_front()
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(UNLOCK)))
        self.assertEqual(sum(p.tapped for p in a.battlefield), 4)  # {3}{B}

    def test_not_offered_without_the_mana(self):
        game, a, b = self.unlocked_front(mana=3)
        for p in a.battlefield[1:]:
            p.tapped = True
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(UNLOCK)], [])

    def test_not_offered_at_instant_speed(self):
        game, a, b = self.unlocked_front()
        game.step = "end"
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(UNLOCK)], [])

    def test_a_fully_unlocked_room_offers_nothing(self):
        game, a, b = self.unlocked_front()
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(UNLOCK)))
        run_stack(game)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(UNLOCK)], [])

    def test_unlocking_the_back_door_with_an_unlock_ability_triggers_that_one(self):
        game, _ = table3(script(), script())
        a, b, _ = game.seats
        a.hand, a.battlefield = [FUNERAL], lands(10)
        a.graveyard = [BEAR]
        cast(game, a, "Funeral Room // Awakening Hall")
        for p in a.battlefield:
            p.tapped = False
        game.step, game.active = "main1", 0
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(UNLOCK)))
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], ["Bear"])
        self.assertEqual(a.graveyard, [])


class DoorEffectTests(unittest.TestCase):
    def test_parse(self):
        for room in (GLASSWORKS, ENTRYWAY):
            self.assertEqual(unsupported_lines(room), [], room.name)

    def test_glassworks_damages_a_creature_an_opponent_controls_not_your_own(self):
        game, _ = table3(script("Ogre"), script())
        a, b, _ = game.seats
        a.hand, a.battlefield = [GLASSWORKS], lands(3) + [Permanent(BEAR)]
        b.battlefield = [Permanent(OGRE), Permanent(BEAR)]
        cast(game, a, "Glassworks // Shattered Yard")
        self.assertEqual(([p.card.name for p in b.battlefield], len([p for p in a.battlefield if p.card.name == "Bear"])), (["Bear"], 1))

    def test_shattered_yard_hits_each_opponent_at_the_end_step(self):
        game, _ = table3(script(), script())
        a, b, c = game.seats
        a.hand, a.battlefield = [GLASSWORKS], lands(5)
        cast(game, a, "Shattered Yard")
        game.trigger("end_step", the_room(a), a)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (40, 39, 39))

    def test_a_locked_shattered_yard_does_nothing(self):
        game, _ = table3(script(), script())
        a, b, c = game.seats
        a.hand, a.battlefield = [GLASSWORKS], lands(3)
        cast(game, a, "Glassworks // Shattered Yard")
        game.trigger("end_step", the_room(a), a)
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 40))

    def test_an_enchantment_creature_token_is_both(self):
        game, _ = table3(script(), script())
        a, b, _ = game.seats
        a.hand, a.battlefield = [ENTRYWAY], lands(2)
        cast(game, a, "Grand Entryway // Elegant Rotunda")
        token = next(p for p in a.battlefield if p.card.name == "Glimmer")
        self.assertEqual((token.card.type_line, token.card.colors, (token.card.power, token.card.toughness)),
                         ("Token Enchantment Creature \u2014 Glimmer", ("W",), ("1", "1")))

    def test_up_to_two_targets_works_with_only_one_creature(self):
        game, _ = table3(script("Bear"), script())
        a, b, _ = game.seats
        a.hand, a.battlefield = [ENTRYWAY], lands(3) + [Permanent(BEAR)]
        cast(game, a, "Elegant Rotunda")
        self.assertEqual([p.counters.get("+1/+1", 0) for p in a.battlefield if "Creature" in p.card.type_line], [1])

    def test_counters_on_each_of_up_to_two_target_creatures(self):
        game, _ = table3(script("Bear", "Ogre"), script())
        a, b, _ = game.seats
        a.hand, a.battlefield = [ENTRYWAY], lands(3) + [Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)]
        cast(game, a, "Elegant Rotunda")
        self.assertEqual(sorted(p.counters.get("+1/+1", 0) for p in a.battlefield if "Creature" in p.card.type_line), [0, 1, 1])


if __name__ == "__main__":
    unittest.main()
