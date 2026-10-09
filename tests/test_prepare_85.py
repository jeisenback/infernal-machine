"""The prepare-card lines of issue #85 that were still unsupported: new ways to become prepared, and the spell halves.

The lines are the issue's own; a card's other lines are not written here.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_x_targets import script

SPELL = Card(name="Quick Study", mana_cost="{1}{U}", type_line="Instant", oracle_text="Draw two cards.", cmc=2.0)
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
TRINKET = Card(name="Trinket", type_line="Artifact")
SHRINE = Card(name="Shrine", type_line="Enchantment")


def prepper(text, name="Student"):
    return Card(name=f"{name} // Quick Study", mana_cost="{1}", type_line="Creature — Wizard", power="1", toughness="1",
                oracle_text=text, prepare=SPELL)


def half(name, text, type_line="Sorcery"):
    return Card(name=name, mana_cost="{1}", type_line=type_line, oracle_text=text)


def supported(test, card):
    test.assertEqual(unsupported_lines(card), [], card.oracle_text)


def fire(game, seat, permanent, event):
    game.trigger(event, permanent, seat)
    run_stack(game)


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


TOMEKEEPER = prepper("When this creature enters, choose up to one —\n• Target creature becomes prepared.\n"
                     "• Target creature becomes unprepared.", "Tomekeeper")


class ChooseUpToOneTests(unittest.TestCase):
    def test_parse(self):
        supported(self, TOMEKEEPER)

    def test_unprepare_a_creature(self):
        game, _ = table3(script("Target creature becomes unprepared", "Student"))
        a = game.seats[0]
        tomekeeper, other = Permanent(TOMEKEEPER), Permanent(prepper("", "Student"), prepared=True)
        a.battlefield = [tomekeeper, other]
        fire(game, a, tomekeeper, "enters")
        self.assertFalse(other.prepared)

    def test_prepare_a_creature(self):
        game, _ = table3(script("Target creature becomes prepared", "Student"))
        a = game.seats[0]
        tomekeeper, other = Permanent(TOMEKEEPER), Permanent(prepper("", "Student"))
        a.battlefield = [tomekeeper, other]
        fire(game, a, tomekeeper, "enters")
        self.assertTrue(other.prepared)

    def test_choosing_none_changes_nothing(self):
        game, _ = table3(script("Done"))
        a = game.seats[0]
        tomekeeper, other = Permanent(TOMEKEEPER), Permanent(prepper("", "Student"), prepared=True)
        a.battlefield = [tomekeeper, other]
        fire(game, a, tomekeeper, "enters")
        self.assertTrue(other.prepared)


GRAVE_RESEARCHER = prepper("At the beginning of your upkeep, surveil 1. Then if there are three or more creature cards in your "
                           "graveyard, this creature becomes prepared.", "Researcher")


class ThenIfTests(unittest.TestCase):
    def upkeep(self, graveyard):
        game, _ = table3(script("Keep"))
        a = game.seats[0]
        creature = Permanent(GRAVE_RESEARCHER)
        a.battlefield = [creature]
        a.graveyard = list(graveyard)
        fire(game, a, creature, "upkeep")
        return creature

    def test_parse(self):
        supported(self, GRAVE_RESEARCHER)

    def test_prepared_with_three_creature_cards(self):
        self.assertTrue(self.upkeep([BEAR, BEAR, OGRE]).prepared)

    def test_not_prepared_with_two_or_with_other_cards(self):
        self.assertFalse(self.upkeep([BEAR, OGRE]).prepared)
        self.assertFalse(self.upkeep([BEAR, OGRE, TRINKET]).prepared)


IDEATION = prepper("Whenever this creature attacks, you may exile eight cards from your graveyard. If you do, this creature "
                   "becomes prepared.", "Ideation")


class ExileFromYourGraveyardTests(unittest.TestCase):
    def attack(self, graveyard, answer):
        game, _ = table3(pick(answer))
        a = game.seats[0]
        creature = Permanent(IDEATION)
        a.battlefield = [creature]
        a.graveyard = list(graveyard)
        fire(game, a, creature, "attacks")
        return a, creature

    def test_parse(self):
        supported(self, IDEATION)

    def test_eight_cards_are_exiled_and_it_becomes_prepared(self):
        a, creature = self.attack([BEAR] * 9, "Yes")
        self.assertEqual((len(a.graveyard), len(a.exile), creature.prepared), (1, 8, True))

    def test_declining_keeps_the_cards(self):
        a, creature = self.attack([BEAR] * 9, "No")
        self.assertEqual((len(a.graveyard), creature.prepared), (9, False))

    def test_fewer_than_eight_cards_does_nothing(self):
        a, creature = self.attack([BEAR] * 7, "Yes")
        self.assertEqual((len(a.graveyard), len(a.exile), creature.prepared), (7, 0, False))


TRIO = prepper("{T}, Tap two untapped creatures you control: This creature becomes prepared.", "Trio")


class TapCreaturesCostTests(unittest.TestCase):
    def test_tap_two_other_untapped_creatures(self):
        supported(self, TRIO)
        game, _ = table3(script("Bear", "Ogre"))
        a = game.seats[0]
        trio, bear, ogre, spare = Permanent(TRIO), Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)
        trio.sick = False
        a.battlefield = [trio, bear, ogre]
        activate(game, a, "Tap two untapped creatures")
        self.assertEqual((trio.prepared, trio.tapped, bear.tapped, ogre.tapped), (True, True, True, True))

    def test_not_offered_with_only_one_other_creature(self):
        game, _ = table3()
        a = game.seats[0]
        trio = Permanent(TRIO)
        trio.sick = False
        a.battlefield = [trio, Permanent(BEAR)]
        self.assertFalse([x for x in game.legal_actions(a) if "Tap two untapped" in x])

    def test_tapped_creatures_do_not_count(self):
        game, _ = table3()
        a = game.seats[0]
        trio = Permanent(TRIO)
        trio.sick = False
        a.battlefield = [trio, Permanent(BEAR), Permanent(BEAR, tapped=True)]
        self.assertFalse([x for x in game.legal_actions(a) if "Tap two untapped" in x])


LLUWEN = prepper("Exile a creature card from your graveyard: CARDNAME becomes prepared. Activate only as a sorcery.", "Lluwen")


class ExileACreatureCardCostTests(unittest.TestCase):
    def test_a_creature_card_pays_and_another_card_does_not(self):
        supported(self, LLUWEN)
        game, _ = table3(script("Bear"))
        a = game.seats[0]
        lluwen = Permanent(LLUWEN)
        a.battlefield = [lluwen]
        a.graveyard = [TRINKET, BEAR]
        activate(game, a, "Exile a creature card")
        self.assertEqual((lluwen.prepared, [c.name for c in a.graveyard], [c.name for c in a.exile]), (True, ["Trinket"], ["Bear"]))

    def test_not_offered_without_a_creature_card(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(LLUWEN)]
        a.graveyard = [TRINKET]
        self.assertFalse([x for x in game.legal_actions(a) if "Exile a creature card" in x])


SKYPAINTER = prepper("When this creature enters and whenever one or more creature tokens you control deal combat damage to a "
                     "player, this creature becomes prepared.", "Skypainter")
ENTHUSIAST = prepper("Whenever one or more tokens you control enter, this creature becomes prepared.", "Enthusiast")
TOKEN_MAKER = half("Maker", "Create a Treasure token.")


class TwoTriggersAndTokensTests(unittest.TestCase):
    def test_parse(self):
        supported(self, SKYPAINTER)
        self.assertEqual(sorted(a.event for a in triggered_abilities(SKYPAINTER)), ["enters", "tokens_combat_damage"])
        supported(self, ENTHUSIAST)

    def test_it_becomes_prepared_when_it_enters(self):
        game, _ = table3()
        a = game.seats[0]
        creature = Permanent(SKYPAINTER)
        a.battlefield = [creature]
        fire(game, a, creature, "enters")
        self.assertTrue(creature.prepared)

    def test_it_becomes_prepared_when_a_token_is_created(self):
        game, _ = table3()
        a = game.seats[0]
        creature = Permanent(ENTHUSIAST)
        a.battlefield = [creature]
        game.create_tokens(a, Card(name="Treasure", type_line="Token Artifact — Treasure"), 2)
        run_stack(game)
        self.assertTrue(creature.prepared)

    def test_a_card_entering_is_not_a_token(self):
        game, _ = table3()
        a = game.seats[0]
        creature = Permanent(ENTHUSIAST)
        a.battlefield = [creature]
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertFalse(creature.prepared)


def cast(card, *answers):
    game, _ = table3(script(*answers))
    a = game.seats[0]
    a.hand = [card]
    a.battlefield = lands(4)
    return game, a


class SpellHalfTests(unittest.TestCase):
    def resolve(self, text, setup=None, *answers):
        spell = half("Half", text)
        supported(self, spell)
        game, a = cast(spell, CAST, *answers)
        if setup:
            setup(game, a)
        game._priority_round(a)
        run_stack(game)
        return game, a

    def test_search_for_a_land_and_put_it_into_the_graveyard(self):
        def setup(game, a):
            a.library = [BEAR, FOREST, BEAR]
        game, a = self.resolve("Search your library for a land card, put it into your graveyard, then shuffle.", setup, "Forest")
        self.assertEqual([c.name for c in a.graveyard if c.name == "Forest"], ["Forest"])

    def test_a_pest_for_each_opponent_that_gains_life_when_it_dies(self):
        game, a = self.resolve('For each opponent, you create a 1/1 black and green Pest creature token with '
                               '"When this token dies, you gain 1 life."')
        pests = [p for p in a.battlefield if p.card.name == "Pest"]
        self.assertEqual(len(pests), 2)  # a three-player table
        self.assertIn("gain 1 life", pests[0].card.oracle_text)

    def test_return_every_enchantment_card_from_your_graveyard(self):
        def setup(game, a):
            a.graveyard = [SHRINE, BEAR, SHRINE]
        game, a = self.resolve("Return all enchantment cards from your graveyard to the battlefield.", setup)
        self.assertEqual(([p.card.name for p in a.battlefield if p.card.name == "Shrine"], [c.name for c in a.graveyard]),
                         (["Shrine", "Shrine"], ["Bear", "Half"]))

    def test_a_token_copy_of_a_creature_has_haste(self):
        def setup(game, a):
            a.battlefield.append(Permanent(OGRE))
        game, a = self.resolve("Create a token that's a copy of target creature you control. That token gains haste until end "
                               "of turn.", setup, "Ogre")
        token = next(p for p in a.battlefield if p.card.type_line.startswith("Token"))
        self.assertEqual((token.card.name, game.has_keyword(token, "haste")), ("Ogre", True))

    def test_exile_a_card_from_your_graveyard_and_make_a_token_copy(self):
        def setup(game, a):
            a.graveyard = [OGRE, SHRINE]
        game, a = self.resolve("Exile target artifact or creature card from your graveyard. Create a token that's a copy of it.",
                               setup, "Ogre")
        token = next(p for p in a.battlefield if p.card.type_line.startswith("Token"))
        self.assertEqual((token.card.name, [c.name for c in a.exile], [c.name for c in a.graveyard]), ("Ogre", ["Ogre"], ["Shrine", "Half"]))  # the spell itself is in the graveyard too

    def test_the_next_instant_or_sorcery_this_turn_is_copied(self):
        game, a = self.resolve("When you next cast an instant or sorcery spell this turn, copy that spell. You may choose new "
                               "targets for the copy.")
        self.assertEqual(a.copy_next_turn, game.turn)
        draw = half("Study", "Draw a card.", "Instant")
        a.hand = [draw]
        before = len(a.hand)
        game._perform(a, CAST + "Study")
        run_stack(game)
        self.assertEqual((len(a.hand) - before + 1, a.copy_next_turn), (2, None))  # the spell and its copy each drew one

    def test_a_copy_is_made_only_for_an_instant_or_sorcery(self):
        game, a = self.resolve("When you next cast an instant or sorcery spell this turn, copy that spell. You may choose new "
                               "targets for the copy.")
        a.hand = [BEAR]
        game._perform(a, CAST + "Bear")
        run_stack(game)
        self.assertEqual(a.copy_next_turn, game.turn)  # still waiting

    def test_exile_a_creature_you_control_and_return_it(self):
        def setup(game, a):
            a.battlefield.append(Permanent(OGRE))
        game, a = self.resolve("Exile target non-Pilot creature you control, then return that card to the battlefield under its "
                               "owner's control.", setup, "Ogre")
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Ogre"], ["Ogre"])

    def test_non_pilot_leaves_out_pilots(self):
        pilot = Card(name="Pilot", type_line="Creature — Human Pilot", power="1", toughness="1")
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(pilot), Permanent(OGRE)]
        options = [lbl for lbl, _ in game.target_options("non-pilot creature you control", a)]
        self.assertEqual(len(options), 1)
        self.assertIn("Ogre", options[0])

    def test_counters_on_up_to_x_creatures_who_gain_flying(self):
        def setup(game, a):
            a.battlefield += [Permanent(OGRE), Permanent(BEAR)]
        spell = half("Half", "Put a +1/+1 counter on each of up to X target creatures. Those creatures gain flying until end of "
                             "turn. Draw a card.")
        spell = Card(name="Half", mana_cost="{X}", type_line="Sorcery", oracle_text=spell.oracle_text)
        supported(self, spell)
        game, a = cast(spell, CAST, "2", "Ogre", "Bear")
        setup(game, a)
        game._priority_round(a)
        run_stack(game)
        creatures = [p for p in a.battlefield if "Creature" in p.card.type_line]
        self.assertEqual([(p.counters, game.has_keyword(p, "flying")) for p in creatures],
                         [({"+1/+1": 1}, True), ({"+1/+1": 1}, True)])

    def test_counters_on_each_bear_who_gain_trample(self):
        bear_cub = Card(name="Bear Cub", type_line="Creature — Bear", power="2", toughness="2")
        def setup(game, a):
            a.battlefield += [Permanent(bear_cub), Permanent(OGRE)]
        game, a = self.resolve("Put a +1/+1 counter on each Bear you control. They gain trample until end of turn.", setup)
        cub = next(p for p in a.battlefield if p.card.name == "Bear Cub")
        ogre = next(p for p in a.battlefield if p.card.name == "Ogre")
        self.assertEqual((cub.counters, game.has_keyword(cub, "trample"), ogre.counters, game.has_keyword(ogre, "trample")),
                         ({"+1/+1": 1}, True, {}, False))

    def test_mill_seven_then_put_a_creature_from_among_them_onto_the_battlefield(self):
        def setup(game, a):
            a.library = [TRINKET] * 3 + [OGRE] + [TRINKET] * 3 + [BEAR] * 5
            a.graveyard = [BEAR]  # an older creature card is not "among them"
        game, a = self.resolve("Mill seven cards. Then put a creature card from among them onto the battlefield.", setup)
        self.assertEqual(([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], len(a.graveyard)), (["Ogre"], 8))  # the old Bear, six milled cards, and the spell


class ReportTests(unittest.TestCase):
    def test_the_lines_are_understood(self):
        for text in ("Search your library for a land card, put it into your graveyard, then shuffle.",
                     "Return all enchantment cards from your graveyard to the battlefield.",
                     "Mill seven cards. Then put a creature card from among them onto the battlefield."):
            supported(self, half("Half", text))


if __name__ == "__main__":
    unittest.main()
