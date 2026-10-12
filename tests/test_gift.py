"""Gift: promise an opponent a gift as you cast the spell; "if the gift was promised" then works like a kicker that costs nothing."""

import unittest

from infernal_machine.effects import gift_of
from infernal_machine.game import CAST, GIFT_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

HUNGER = real("Nocturnal Hunger", "{2}{B}", "Instant", "Gift a Food (You may promise an opponent a gift as you cast this spell. If you do, they create a "
              "Food token before its other effects. It's an artifact with \"{2}, {T}, Sacrifice this token: You gain 3 life.\")\nDestroy target "
              "creature. If the gift wasn't promised, you lose 2 life.")
SCRAPSHOOTER = real("Scrapshooter", "{3}{G}", "Creature — Elf Archer", "Gift a card (You may promise an opponent a gift as you cast this spell. If "
                    "you do, when it enters, they draw a card.)\nReach\nWhen this creature enters, if the gift was promised, destroy target artifact "
                    "or enchantment an opponent controls.", "4", "4")
FLOOD_MAW = real("Into the Flood Maw", "{U}", "Instant", "Gift a tapped Fish (You may promise an opponent a gift as you cast this spell. If you do, "
                 "they create a tapped 1/1 blue Fish creature token before its other effects.)\nReturn target creature an opponent controls to its "
                 "owner's hand. If the gift was promised, instead return target nonland permanent an opponent controls to its owner's hand.")
RIVER = real("Long River's Pull", "{U}{U}", "Instant", "Gift a card (You may promise an opponent a gift as you cast this spell. If you do, they draw "
             "a card before its other effects.)\nCounter target creature spell. If the gift was promised, instead counter target spell.")
CRUMB = real("Crumb and Get It", "{W}", "Instant", "Gift a Food\nTarget creature you control gets +2/+2 until end of turn. If the gift was promised, "
             "that creature also gains indestructible until end of turn.")
WEAR_DOWN = real("Wear Down", "{1}{G}", "Sorcery", "Gift a card\nDestroy target artifact or enchantment. If the gift was promised, instead destroy two "
                 "target artifacts and/or enchantments.")
TURN = real("Time Gift", "{1}", "Sorcery", "Gift an extra turn\nYou gain 1 life.")
OCTO = real("Deep Gift", "{1}", "Sorcery", "Gift an Octopus\nYou gain 1 life.")
TREASURE_GIFT = real("Gold Gift", "{1}", "Sorcery", "Gift a Treasure\nYou gain 1 life.")
GIFT_AURA = real("Gifted Aura", "{1}", "Enchantment — Aura", "Gift a card\nEnchant creature\nEnchanted creature gets +1/+1.")
TRINKET = real("Trinket", "{1}", "Artifact", "")
SHRINE = real("Shrine", "{1}", "Enchantment", "")
FOREST = real("Forest", "", "Basic Land — Forest", "")
GIVE = "Give it to"


def table(*hand, mana=4, policy=None):
    game, _ = table3(policy or script("Give"))
    a = game.seats[0]
    a.hand, a.graveyard = list(hand), []
    a.battlefield = lands(mana)
    a.library = [BEAR] * 5
    for seat in game.seats[1:]:
        seat.library = [OGRE] * 5
    game.turn, game.step = 2, "main1"
    return game, a, game.seats[1], game.seats[2]


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (HUNGER, SCRAPSHOOTER, FLOOD_MAW, RIVER, CRUMB, WEAR_DOWN, TURN, OCTO, TREASURE_GIFT):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_gift_is_read(self):
        self.assertEqual([gift_of(c) for c in (HUNGER, SCRAPSHOOTER, FLOOD_MAW, TURN, OCTO, TREASURE_GIFT, BEAR)],
                         ["Food", "card", "tapped Fish", "extra turn", "Octopus", "Treasure", None])

    def test_a_gift_of_something_is_not_an_ability_word(self):
        ability = real("Dark Apostle", "{2}{B}", "Creature — Cleric", "Gift of Chaos — {3}, {T}: Draw a card.", "2", "2")
        self.assertIsNone(gift_of(ability))


class PromiseTests(unittest.TestCase):
    def test_the_first_option_is_no_gift(self):
        seen = []

        def policy(prompt, options):
            seen.append((prompt, options))
            return 0
        game, a, b, c = table(HUNGER, policy=policy)
        b.battlefield = [Permanent(OGRE)]
        game._perform(a, CAST + HUNGER.name)
        [(prompt, options)] = [s for s in seen if s[0].startswith(GIFT_PROMPT)]
        self.assertEqual(options[0], "Don't promise a gift")
        self.assertEqual(len(options), 3)  # and one per opponent
        run_stack(game)
        self.assertEqual(names(b), [])
        self.assertEqual(a.life, 38)

    def test_a_card_with_no_gift_is_not_asked(self):
        seen = []
        game, a, b, c = table(real("Plain", "{1}", "Instant", "You gain 1 life."), policy=lambda p, o: seen.append(p) or 0)
        game._perform(a, CAST + "Plain")
        self.assertEqual([p for p in seen if p.startswith(GIFT_PROMPT)], [])

    def test_a_gift_that_cannot_be_used_is_not_offered(self):
        seen = []
        game, a, b, c = table(WEAR_DOWN, policy=lambda p, o: seen.append(p) or 0)
        b.battlefield = [Permanent(TRINKET)]  # one target is not enough for the promised two
        game._perform(a, CAST + WEAR_DOWN.name)
        self.assertEqual([p for p in seen if p.startswith(GIFT_PROMPT)], [])


class GiftTests(unittest.TestCase):
    def test_a_food_for_the_opponent_and_no_life_lost(self):
        game, a, b, c = table(HUNGER)
        b.battlefield = [Permanent(OGRE)]
        game._perform(a, CAST + HUNGER.name)
        run_stack(game)
        self.assertEqual(names(b), ["Food"])
        self.assertEqual(a.life, 40)

    def test_the_gift_goes_to_the_opponent_chosen(self):
        for pick, expected in ((1, (["Food"], [])), (2, ([], ["Food"]))):
            game, a, b, c = table(HUNGER, policy=lambda prompt, options, pick=pick: pick if prompt.startswith(GIFT_PROMPT) else 0)
            b.battlefield, c.battlefield = [Permanent(OGRE)], [Permanent(OGRE)]
            game.stack = []
            game._perform(a, CAST + HUNGER.name)
            run_stack(game)
            self.assertEqual((names(b).count("Food") and ["Food"] or [], names(c).count("Food") and ["Food"] or []), expected, pick)

    def test_a_card_drawn_by_the_opponent(self):
        game, a, b, c = table(SCRAPSHOOTER, mana=4)
        b.battlefield = [Permanent(TRINKET)]
        before = len(b.hand)
        game._perform(a, CAST + SCRAPSHOOTER.name)
        run_stack(game)
        self.assertEqual(len(b.hand), before + 1)
        self.assertEqual(names(b), [])  # and its enters trigger destroyed the artifact

    def test_without_the_gift_nothing_is_drawn_and_nothing_destroyed(self):
        game, a, b, c = table(SCRAPSHOOTER, mana=4, policy=script("Don't"))
        b.battlefield = [Permanent(TRINKET)]
        before = len(b.hand)
        game._perform(a, CAST + SCRAPSHOOTER.name)
        run_stack(game)
        self.assertEqual(len(b.hand), before)
        self.assertEqual(names(b), ["Trinket"])

    def test_an_aura_gives_the_gift_as_it_enters(self):
        game, a, b, c = table(GIFT_AURA, mana=1)
        a.battlefield.append(Permanent(BEAR))
        before = len(b.hand)
        game._perform(a, CAST + GIFT_AURA.name)
        run_stack(game)
        self.assertEqual(len(b.hand), before + 1)

    def test_a_tapped_fish(self):
        game, a, b, c = table(FLOOD_MAW, mana=1)
        b.battlefield = [Permanent(OGRE)]
        game._perform(a, CAST + FLOOD_MAW.name)
        run_stack(game)
        [fish] = b.battlefield
        self.assertEqual((fish.card.name, fish.tapped), ("Fish", True))

    def test_a_treasure_and_an_octopus(self):
        for card, token in ((TREASURE_GIFT, "Treasure"), (OCTO, "Octopus")):
            game, a, b, c = table(card, mana=1)
            game._perform(a, CAST + card.name)
            run_stack(game)
            self.assertEqual(names(b), [token], card.name)

    def test_an_extra_turn_for_the_opponent(self):
        game, a, b, c = table(TURN, mana=1)
        game._perform(a, CAST + TURN.name)
        run_stack(game)
        self.assertEqual(game.extra_turns, [1])


class PromisedEffectsTests(unittest.TestCase):
    def test_instead_a_nonland_permanent_may_be_returned(self):
        game, a, b, c = table(FLOOD_MAW, mana=1)
        b.battlefield = [Permanent(TRINKET)]
        game._perform(a, CAST + FLOOD_MAW.name)  # no creature to bounce, but a promised gift allows an artifact
        run_stack(game)
        self.assertEqual([x.name for x in b.hand], ["Trinket"])

    def test_without_the_gift_it_must_be_a_creature(self):
        game, a, b, c = table(FLOOD_MAW, mana=1, policy=script("Don't"))
        b.battlefield = [Permanent(TRINKET)]
        self.assertNotIn(CAST + FLOOD_MAW.name, game.legal_actions(a))

    def test_two_targets_instead_of_one(self):
        game, a, b, c = table(WEAR_DOWN, mana=2)
        b.battlefield = [Permanent(TRINKET), Permanent(SHRINE)]
        game._perform(a, CAST + WEAR_DOWN.name)
        run_stack(game)
        self.assertEqual(names(b), [])

    def test_one_target_without_the_gift(self):
        game, a, b, c = table(WEAR_DOWN, mana=2, policy=script("Don't"))
        b.battlefield = [Permanent(TRINKET), Permanent(SHRINE)]
        game._perform(a, CAST + WEAR_DOWN.name)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 1)

    def test_a_pump_also_gains_a_keyword_if_promised(self):
        for answer, indestructible in (("Give", True), ("Don't", False)):
            game, a, b, c = table(CRUMB, mana=1, policy=script(answer))
            a.battlefield.append(Permanent(BEAR, sick=False))
            game._perform(a, CAST + CRUMB.name)
            run_stack(game)
            self.assertEqual(game.has_keyword(a.battlefield[-1], "indestructible"), indestructible, answer)
            self.assertEqual(game.power(a.battlefield[-1]), 4, answer)


if __name__ == "__main__":
    unittest.main()
