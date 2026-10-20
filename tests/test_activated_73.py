"""Activated abilities of issue #73 that were still unsupported: sacrifice-and-X, kinds of target, abilities that work from
the graveyard, new costs (exile or return this permanent, life by color count), and the one-off effects they make.

The lines are the issue's own; a card's other lines are not written here.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import activated_abilities, spell_effects
from infernal_machine.game import ACTIVATE, ACTIVATE_GRAVEYARD, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, creature, lands, OGRE, pick, run_stack, script, table

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
RELIC = Card(name="Relic", type_line="Artifact")
SHRINE = Card(name="Shrine", type_line="Enchantment")
CREATURE_RELIC = Card(name="Golem", type_line="Artifact Creature — Golem", power="2", toughness="2")


def supported(test, card):
    test.assertEqual(unsupported_lines(card), [], card.oracle_text)


def names(cards):
    return sorted(c.name for c in cards)


def on_battlefield(seat):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


def activate(game, seat, fragment):
    """Perform the activation whose text contains `fragment`, then let the stack resolve."""
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


DINA = Card(name="Dina, Essence Brewer", mana_cost="{2}{B}{G}", type_line="Legendary Creature — Test", power="3", toughness="3",
            oracle_text="{2}, {T}, Sacrifice another creature: You gain X life and put X +1/+1 counters on target creature you "
                        "control, where X is the sacrificed creature's power.")


class SacrificeAndXTests(unittest.TestCase):
    def test_gain_x_and_put_x_counters_where_x_is_the_sacrificed_power(self):
        supported(self, DINA)
        game, _, _ = table(script("Bear", "Ogre"))  # the action, the creature that gets counters, the sacrifice
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [Permanent(DINA), bear, ogre, *lands(2)]
        activate(game, a, "Sacrifice another creature")
        self.assertEqual((a.life, bear.counters, ogre in a.battlefield), (43, {"+1/+1": 3}, False))


HAYWIRE_MITE = Card(name="Haywire Mite", mana_cost="{1}", type_line="Artifact Creature — Insect", power="1", toughness="1",
                    oracle_text="{G}, Sacrifice this creature: Exile target noncreature artifact or noncreature enchantment.")


class NoncreatureKindsTests(unittest.TestCase):
    def test_exile_a_noncreature_artifact_or_enchantment_but_not_a_creature_or_land(self):
        supported(self, HAYWIRE_MITE)
        game, _, _ = table(script())
        a, b = game.seats
        a.battlefield = [Permanent(HAYWIRE_MITE), *lands(1)]
        b.battlefield = [Permanent(CREATURE_RELIC), Permanent(BEAR), Permanent(RELIC), Permanent(FOREST)]
        options = [label for label, _ in game.target_options("noncreature artifact or noncreature enchantment", a)]
        self.assertEqual(len(options), 1)
        self.assertIn("Relic", options[0])
        activate(game, a, "Exile target noncreature")
        self.assertEqual((names(b.exile), "Haywire Mite" in on_battlefield(a)), (["Relic"], False))

    def test_the_comma_wording_of_the_commands(self):
        for text, ok, bad in (("Destroy target noncreature, nonland permanent with mana value 2 or less.", RELIC, OGRE),
                              ("Destroy target nonland permanent with mana value 2 or less.", RELIC, FOREST)):
            card = Card(name="Command", type_line="Sorcery", oracle_text=text)
            self.assertIsNotNone(spell_effects(card), text)
            game, _, _ = table()
            a = game.seats[0]
            labels = [lbl for lbl, _ in game.target_options(spell_effects(card)[0].target, a)]
            self.assertEqual(labels, [])
            a.battlefield = [Permanent(ok), Permanent(bad)]
            labels = [lbl for lbl, _ in game.target_options(spell_effects(card)[0].target, a)]
            self.assertEqual(len(labels), 1, text)


LEITMOTIF = Card(name="Leitmotif Composer", mana_cost="{3}{U}", type_line="Creature — Bird Bard", power="2", toughness="2",
                 oracle_text="{2}{U}: Creatures named CARDNAME can't be blocked this turn.")


class NamedCreaturesTests(unittest.TestCase):
    def test_every_creature_with_the_name_cant_be_blocked_this_turn(self):
        supported(self, LEITMOTIF)
        game, _, _ = table(script())
        a, b = game.seats
        mine, copy, other = Permanent(LEITMOTIF), Permanent(LEITMOTIF), Permanent(BEAR)
        a.battlefield = [mine, other, *lands(3)]
        b.battlefield = [copy]  # a copy of it under another player's control is a creature with the name too
        activate(game, a, "can't be blocked")
        self.assertTrue(all(game.has_keyword(p, "can't be blocked") or any("can't be blocked" in m.keywords or "cant_be_blocked" in m.keywords
                                                                          for m in game.modifiers(p)) for p in (mine, copy)))
        self.assertFalse(any(m.keywords for m in game.modifiers(other)))


PERPETUAL_TIMEPIECE = Card(name="Perpetual Timepiece", mana_cost="{2}", type_line="Artifact",
                           oracle_text="{2}, Exile this artifact: Shuffle any number of target cards from your graveyard into your library.")


class ExileThisAsACostTests(unittest.TestCase):
    def test_exile_it_to_shuffle_any_number_of_cards_from_your_graveyard_back(self):
        supported(self, PERPETUAL_TIMEPIECE)
        [ability] = activated_abilities(PERPETUAL_TIMEPIECE)
        self.assertTrue(ability.exile_source)
        game, _, _ = table(script("Bear", "Ogre", "No target"))
        a = game.seats[0]
        a.battlefield = [Permanent(PERPETUAL_TIMEPIECE), *lands(2)]
        a.graveyard = [BEAR, OGRE, RELIC]
        library = len(a.library)
        activate(game, a, "Shuffle any number")
        self.assertEqual((names(a.graveyard), len(a.library) - library, names(a.exile)), (["Relic"], 2, ["Perpetual Timepiece"]))  # the artifact itself is exiled as the cost
        self.assertNotIn("Perpetual Timepiece", on_battlefield(a))

    def test_it_can_shuffle_none_back(self):
        game, _, _ = table(script("No target"))
        a = game.seats[0]
        a.battlefield = [Permanent(PERPETUAL_TIMEPIECE), *lands(2)]
        a.graveyard = [BEAR]
        activate(game, a, "Shuffle any number")
        self.assertEqual(names(a.graveyard), ["Bear"])


QUINTORIUS = Card(name="Quintorius, History Chaser", mana_cost="{1}{R}{W}", type_line="Legendary Planeswalker — Quintorius", loyalty="4",
                  oracle_text="+1: You may discard a card. If you do, draw two cards, then mill a card.\n"
                              "−4: Spirits you control gain double strike and vigilance until end of turn.")
SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", colors=("R", "W"), power="3", toughness="2")


class QuintoriusTests(unittest.TestCase):
    def test_parse(self):
        supported(self, QUINTORIUS)

    def test_plus_one_discard_to_draw_two_and_mill_one(self):
        game, _, _ = table(script("Ogre"))
        a = game.seats[0]
        a.battlefield = [Permanent(QUINTORIUS, loyalty=4)]
        a.hand = [OGRE]
        a.library = [BEAR, RELIC, SHRINE, FOREST] + a.library
        activate(game, a, "+1")
        self.assertEqual((names(a.hand), names(a.graveyard)), (["Bear", "Relic"], ["Ogre", "Shrine"]))

    def test_plus_one_you_may_decline_the_discard(self):
        game, _, _ = table(script("No"))
        a = game.seats[0]
        a.battlefield = [Permanent(QUINTORIUS, loyalty=4)]
        a.hand = [OGRE]
        activate(game, a, "+1")
        self.assertEqual((names(a.hand), a.graveyard), (["Ogre"], []))

    def test_minus_four_spirits_get_double_strike_and_vigilance(self):
        game, _, _ = table(script())
        a, b = game.seats
        spirit, bear, theirs = Permanent(SPIRIT), Permanent(BEAR), Permanent(SPIRIT)
        a.battlefield = [Permanent(QUINTORIUS, loyalty=4), spirit, bear]
        b.battlefield = [theirs]
        activate(game, a, "−4")
        self.assertEqual([(game.has_keyword(p, "double strike"), game.has_keyword(p, "vigilance")) for p in (spirit, bear, theirs)],
                         [(True, True), (False, False), (False, False)])


REDEMPTION_ARC = Card(name="Redemption Arc", mana_cost="{1}{W}", type_line="Enchantment — Aura",
                      oracle_text="Enchant creature\n{1}{W}: Exile enchanted creature.")


class EnchantedCreatureTests(unittest.TestCase):
    def test_the_aura_can_exile_what_it_enchants(self):
        supported(self, REDEMPTION_ARC)
        game, _, _ = table(script())
        a, b = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        a.battlefield = [Permanent(REDEMPTION_ARC, attached_to=bear), *lands(2)]
        activate(game, a, "Exile enchanted creature")
        self.assertEqual((b.battlefield, names(b.exile)), ([], ["Bear"]))


RESTLESS_SPIRE = Card(name="Restless Spire", type_line="Land",
                      oracle_text="{U}{R}: Until end of turn, this land becomes a 2/1 blue and red Elemental creature with "
                                  "\"During your turn, this creature has first strike.\" It's still a land.")


class AnimateWithAQuotedAbilityTests(unittest.TestCase):
    def test_it_has_first_strike_only_during_your_turn(self):
        supported(self, RESTLESS_SPIRE)
        game, _, _ = table(script())
        a = game.seats[0]
        spire = Permanent(RESTLESS_SPIRE)
        a.battlefield = [spire, *lands(2)]
        activate(game, a, "becomes a 2/1")
        self.assertEqual((game.power(spire), game.toughness(spire), "Creature" in spire.card.type_line), (2, 1, True))
        game.active = 0
        self.assertTrue(game.has_keyword(spire, "first strike"))
        game.active = 1
        self.assertFalse(game.has_keyword(spire, "first strike"))


ROOTHA = Card(name="Rootha, Mercurial Artist", mana_cost="{2}{U}{R}", type_line="Legendary Creature — Test", power="1", toughness="4",
              oracle_text="{2}, Return CARDNAME to its owner's hand: Copy target instant or sorcery spell you control. You may "
                          "choose new targets for the copy.")


class ReturnThisAsACostTests(unittest.TestCase):
    def test_parse(self):
        supported(self, ROOTHA)
        [ability] = activated_abilities(ROOTHA)
        self.assertTrue(ability.bounce_source)


TEACHERS_PEST = Card(name="Teacher's Pest", mana_cost="{B}{G}", type_line="Creature — Insect Pest", power="1", toughness="1",
                     oracle_text="{B}{G}: Return this card from your graveyard to the battlefield tapped.")


class FromTheGraveyardTests(unittest.TestCase):
    def test_it_comes_back_tapped_for_its_cost_and_only_from_the_graveyard(self):
        supported(self, TEACHERS_PEST)
        [ability] = activated_abilities(TEACHERS_PEST)
        self.assertTrue(ability.from_graveyard)
        game, _, _ = table(pick(ACTIVATE_GRAVEYARD))
        a = game.seats[0]
        a.graveyard = [TEACHERS_PEST]
        a.battlefield = lands(2)
        self.assertIn(ACTIVATE_GRAVEYARD + "Teacher's Pest", game.legal_actions(a))
        game._priority_round(a)
        pest = next(p for p in a.battlefield if p.card.name == "Teacher's Pest")
        self.assertEqual((pest.tapped, a.graveyard), (True, []))
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Teacher's Pest", game.legal_actions(a))  # no longer there to use it
        a.hand, a.battlefield = [TEACHERS_PEST], lands(2)
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Teacher's Pest", game.legal_actions(a))  # not from the hand

    def test_not_offered_without_the_mana(self):
        game, _, _ = table()
        a = game.seats[0]
        a.graveyard = [TEACHERS_PEST]
        a.battlefield = lands(1)
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Teacher's Pest", game.legal_actions(a))


WAR_ROOM = Card(name="War Room", type_line="Land",
                oracle_text="{3}, {T}, Pay life equal to the number of colors in your commanders' color identity: Draw a card.")


class LifeByColorsTests(unittest.TestCase):
    def test_pay_life_for_each_color_in_your_commanders_identity(self):
        supported(self, WAR_ROOM)
        game, _, _ = table(script())
        a = game.seats[0]
        a.color_identity = frozenset("UBR")
        a.battlefield = [Permanent(WAR_ROOM), *lands(3)]
        hand = len(a.hand)
        activate(game, a, "Draw a card")
        self.assertEqual((a.life, len(a.hand) - hand), (37, 1))

    def test_a_colorless_commander_pays_nothing(self):
        game, _, _ = table(script())
        a = game.seats[0]
        a.color_identity = frozenset()
        a.battlefield = [Permanent(WAR_ROOM), *lands(3)]
        activate(game, a, "Draw a card")
        self.assertEqual(a.life, 40)


ZIMONE = Card(name="Zimone, Quandrix Prodigy", mana_cost="{G}{U}", type_line="Legendary Creature — Test", power="1", toughness="1",
              oracle_text="{1}, {T}: You may put a land card from your hand onto the battlefield tapped.\n"
                          "{4}, {T}: Draw a card. If you control eight or more lands, draw two cards instead.")


class ZimoneTests(unittest.TestCase):
    def test_put_a_land_from_your_hand_onto_the_battlefield_tapped(self):
        supported(self, ZIMONE)
        game, _, _ = table(script("Forest"))
        a = game.seats[0]
        a.hand = [FOREST, BEAR]
        a.battlefield = [Permanent(ZIMONE), *lands(1)]
        activate(game, a, "land card from your hand")
        forest = next(p for p in a.battlefield if p.card.name == "Forest")
        self.assertEqual((forest.tapped, names(a.hand)), (True, ["Bear"]))

    def test_draw_one_or_two_with_eight_lands(self):
        for count, expected in ((6, 1), (8, 2)):
            game, _, _ = table(script())
            a = game.seats[0]
            a.battlefield = [Permanent(ZIMONE), *lands(count)]
            before = len(a.hand)
            activate(game, a, "Draw a card")
            self.assertEqual(len(a.hand) - before, expected, count)  # the lands include the ones tapped to pay


FABLED_PASSAGE = Card(name="Fabled Passage", type_line="Land",
                      oracle_text="{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield "
                                  "tapped, then shuffle. Then if you control four or more lands, untap that land.")


class FabledPassageTests(unittest.TestCase):
    def test_the_fetched_land_untaps_with_four_or_more_lands(self):
        supported(self, FABLED_PASSAGE)
        for others, expected_tapped in ((2, True), (3, False)):  # the Passage is sacrificed: with 3 others and the new land, four
            game, _, _ = table(script())
            a = game.seats[0]
            a.library = [FOREST] + a.library
            a.battlefield = [Permanent(FABLED_PASSAGE), *lands(others)]
            activate(game, a, "Search your library")
            fetched = next(p for p in a.battlefield if p.card.name == "Forest")
            self.assertEqual(fetched.tapped, expected_tapped, others)


FERAL_APPETITE = Card(name="Feral Appetite", mana_cost="{1}{G}", type_line="Enchantment",
                      oracle_text="{1}{G}: Exile target card from a graveyard. If a creature card is exiled this way, create a 1/1 "
                                  "black and green Pest creature token with \"When this token dies, you gain 1 life.\"")


class ExileForATokenTests(unittest.TestCase):
    def test_a_creature_card_makes_a_pest_and_another_card_does_not(self):
        supported(self, FERAL_APPETITE)
        for card, pests in ((BEAR, 1), (RELIC, 0)):
            game, _, _ = table(script())
            a, b = game.seats
            b.graveyard = [card]
            a.battlefield = [Permanent(FERAL_APPETITE), *lands(2)]
            activate(game, a, "Exile target card from a graveyard")
            self.assertEqual((b.graveyard, sum(p.card.name == "Pest" for p in a.battlefield)), ([], pests), card.name)


ALCHEMISTS_REFUGE = Card(name="Alchemist's Refuge", type_line="Land",
                         oracle_text="{G}{U}, {T}: You may cast spells this turn as though they had flash.")


class FlashPermissionTests(unittest.TestCase):
    def test_spells_can_be_cast_at_instant_speed_for_the_rest_of_the_turn(self):
        supported(self, ALCHEMISTS_REFUGE)
        game, _, _ = table(script())
        a, b = game.seats
        sorcery = Card(name="Slow", mana_cost="{1}", type_line="Sorcery", oracle_text="You gain 3 life.")
        a.hand = [sorcery]
        a.battlefield = [Permanent(ALCHEMISTS_REFUGE), *lands(4)]
        game.active = 1  # the opponent's turn: a sorcery can't normally be cast
        self.assertNotIn(CAST + "Slow", game.legal_actions(a))
        activate(game, a, "as though they had flash")
        self.assertIn(CAST + "Slow", game.legal_actions(a))
        game.turn += 1
        self.assertNotIn(CAST + "Slow", game.legal_actions(a))  # only this turn


ARCANE_LIGHTHOUSE = Card(name="Arcane Lighthouse", type_line="Land",
                         oracle_text="{1}, {T}: Until end of turn, creatures your opponents control lose hexproof and shroud and "
                                     "can't have hexproof or shroud.")


class LoseHexproofTests(unittest.TestCase):
    def test_opponents_creatures_lose_hexproof_and_shroud_until_end_of_turn(self):
        supported(self, ARCANE_LIGHTHOUSE)
        game, _, _ = table(script())
        a, b = game.seats
        hexed = Permanent(creature("Troll", 2, 2, "Hexproof"))
        shrouded = Permanent(creature("Ghost", 2, 2, "Shroud"))
        mine = Permanent(creature("Mine", 2, 2, "Hexproof"))
        a.battlefield = [Permanent(ARCANE_LIGHTHOUSE), mine, *lands(2)]
        b.battlefield = [hexed, shrouded]
        self.assertEqual([lbl for lbl, _ in game.target_options("creature an opponent controls", a)], [])
        activate(game, a, "lose hexproof")
        self.assertEqual(len(game.target_options("creature an opponent controls", a)), 2)
        self.assertTrue(game.has_keyword(mine, "hexproof"))  # only your opponents' creatures
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual([lbl for lbl, _ in game.target_options("creature an opponent controls", a)], [])


ORAN_RIEF = Card(name="Oran-Rief, the Vastwood", type_line="Land",
                 oracle_text="{T}: Put a +1/+1 counter on each green creature that entered this turn.")


class EnteredThisTurnTests(unittest.TestCase):
    def test_each_green_creature_that_entered_this_turn_gets_a_counter(self):
        supported(self, ORAN_RIEF)
        game, _, _ = table(script())
        a, b = game.seats
        green = Card(name="Green Bear", type_line="Creature — Bear", colors=("G",), power="2", toughness="2")
        old, new, red, theirs = Permanent(green), Permanent(green), Permanent(OGRE), Permanent(green)
        a.battlefield = [Permanent(ORAN_RIEF), old]
        b.battlefield = []
        old.entered_turn = game.turn - 1
        game._enter(a, new)
        game._enter(a, red)
        game._enter(b, theirs)  # "each green creature that entered this turn": any player's
        activate(game, a, "green creature that entered")
        self.assertEqual([p.counters for p in (old, new, red, theirs)], [{}, {"+1/+1": 1}, {}, {"+1/+1": 1}])
