"""The third popularity pass: the most played cards still missing a rules line, each from the card's own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))


def cast(card, *answers, n=6, mine=(), theirs=(), library=(), hand=()):
    game, _ = table3(script(*answers))
    a, b, c = game.seats
    a.hand, a.battlefield, a.library = [card, *hand], lands(n) + [Permanent(x) for x in mine], list(library)
    b.battlefield = [Permanent(x) for x in theirs]
    game._perform(a, CAST + card.name)
    run_stack(game)
    game._check_state()
    return game, a, b, c


def activate(game, seat, text):
    game._perform(seat, next(x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and text in x))
    run_stack(game)
    game._check_state()


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name != "City of Brass")


FOREBODING = real("Foreboding Landscape", "", "Land", "{T}: Add {C}.\n{T}, Sacrifice this land: Search your library for a basic Swamp, "
                  "Forest, or Island card, put it onto the battlefield tapped, then shuffle.")
MYRIAD = real("Myriad Landscape", "", "Land", "{T}: Add {C}.\n{2}, {T}, Sacrifice this land: Search your library for up to two basic land cards "
              "that share a land type, put them onto the battlefield tapped, then shuffle.")


class LandscapeTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual([unsupported_lines(c) for c in (FOREBODING, MYRIAD)], [[], []])

    def test_a_basic_of_one_of_the_three_types_enters_tapped_and_the_landscape_is_sacrificed(self):
        game, _ = table3(script("Island"))
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(FOREBODING, sick=False)], [PLAINS, MOUNTAIN, ISLAND, SWAMP]
        activate(game, a, "Search")
        [island] = a.battlefield
        self.assertEqual((island.card.name, island.tapped), ("Island", True))
        self.assertEqual(sorted(c.name for c in a.library), ["Mountain", "Plains", "Swamp"])

    def test_only_the_three_types_are_offered(self):
        asked = []

        def record(prompt, options):
            asked.append(list(options))
            return 0
        game, _ = table3(record)
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(FOREBODING, sick=False)], [PLAINS, MOUNTAIN, ISLAND, SWAMP, FOREST]
        activate(game, a, "Search")
        self.assertEqual(sorted(asked[-1]), ["Forest", "Island", "Swamp"])

    def test_a_dual_land_with_those_types_is_not_basic(self):
        asked = []

        def record(prompt, options):
            asked.append(list(options))
            return 0
        game, _ = table3(record)
        a = game.seats[0]
        pool = real("Breeding Pool", "", "Land — Forest Island", "")
        a.battlefield, a.library = [Permanent(FOREBODING, sick=False)], [pool, FOREST]
        activate(game, a, "Search")
        self.assertEqual(asked[-1], ["Forest"])

    def test_the_two_lands_of_myriad_landscape_share_a_land_type(self):
        asked = []

        def record(prompt, options):
            asked.append(sorted(options))
            return options.index("Forest") if "Forest" in options else 0
        game, _ = table3(record)
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(MYRIAD, sick=False), *lands(2)], [PLAINS, FOREST, FOREST, ISLAND, SWAMP]
        activate(game, a, "Search")
        self.assertEqual(asked[-1], ["Forest"])  # the second land must be a Forest too
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.tapped and p.card.name == "Forest"), ["Forest", "Forest"])

    def test_with_one_matching_land_left_only_one_is_found(self):
        game, _ = table3(script("Forest"))
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(MYRIAD, sick=False), *lands(2)], [PLAINS, FOREST, ISLAND]
        activate(game, a, "Search")
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name == "Forest"), ["Forest"])


BITE_DOWN = real("Bite Down", "{1}{G}", "Instant", "Target creature you control deals damage equal to its power to target creature or planeswalker you don't control.")
SOULS_FIRE = real("Soul's Fire", "{R}", "Instant", "Target creature you control deals damage equal to its power to any target.")
IGNITION = real("Chandra's Ignition", "{3}{R}{R}", "Sorcery", "Target creature you control deals damage equal to its power to each other creature and each opponent.")
CHARM = real("Rakdos Charm", "{B}{R}", "Instant", "Choose one —\n• Exile target player's graveyard.\n• Destroy target artifact.\n• Each creature deals 1 damage to its controller.")


class BiteTests(unittest.TestCase):
    def test_parse(self):
        for card in (BITE_DOWN, SOULS_FIRE, IGNITION, CHARM):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_creature_you_control_deals_damage_equal_to_its_power_to_a_creature_and_takes_none_back(self):
        game, a, b, c = cast(BITE_DOWN, "Ogre", "Bear", mine=[OGRE], theirs=[BEAR])
        self.assertEqual(names(b), [])
        self.assertEqual(names(a), ["Ogre"])
        self.assertEqual(game.seats[0].battlefield[-1].damage, 0)

    def test_any_target_can_be_a_player(self):
        game, a, b, c = cast(SOULS_FIRE, "Ogre", "Player: B", mine=[OGRE])
        self.assertEqual(b.life, 37)

    def test_each_other_creature_and_each_opponent_takes_the_damage(self):
        game, a, b, c = cast(IGNITION, "Ogre", mine=[OGRE, BEAR], theirs=[BEAR])
        self.assertEqual((b.life, c.life, a.life), (37, 37, 40))
        self.assertEqual((names(a), names(b)), (["Ogre"], []))  # the Bear of each side died; the Ogre took none

    def test_each_creature_deals_one_damage_to_its_controller(self):
        game, a, b, c = cast(CHARM, "Each creature", mine=[BEAR, OGRE], theirs=[BEAR])
        self.assertEqual((a.life, b.life, c.life), (38, 39, 40))


FUNGAL = real("Fungal Sprouting", "{G}{G}", "Sorcery", "Create X 1/1 green Saproling creature tokens, where X is the greatest power among creatures you control.")
HARVEST = real("Essence Harvest", "{2}{B}", "Sorcery", "Target player loses X life and you gain X life, where X is the greatest power among creatures you control.")
HUMAN = real("Human", "{1}", "Creature — Human", "", "6", "6")
TUYA = real("Tuya Bearclaw", "{3}{G}", "Creature — Human", "Whenever CARDNAME attacks, it gets +X/+X until end of turn, where X is the greatest power among other creatures you control.", "3", "3")


class GreatestPowerTests(unittest.TestCase):
    def test_parse(self):
        for card in (FUNGAL, HARVEST, TUYA):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_tokens_equal_to_the_greatest_power_among_your_creatures(self):
        game, a, b, c = cast(FUNGAL, mine=[BEAR, OGRE])
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Saproling"]), 3)

    def test_with_no_creatures_it_is_zero(self):
        game, a, b, c = cast(FUNGAL)
        self.assertEqual(names(a), [])

    def test_life_loss_and_gain(self):
        game, a, b, c = cast(HARVEST, "Player: B", mine=[HUMAN])
        self.assertEqual((a.life, b.life), (46, 34))

    def test_only_your_creatures_count(self):
        game, a, b, c = cast(HARVEST, "Player: B", mine=[BEAR], theirs=[HUMAN])
        self.assertEqual(a.life, 42)

    def test_other_creatures_leaves_out_the_source(self):
        game, _ = table3()
        a = game.seats[0]
        tuya = Permanent(TUYA)
        a.battlefield = [tuya, Permanent(BEAR)]
        game.resolving_source = tuya
        from infernal_machine.effects import Amount
        self.assertEqual(game.evaluate(Amount("greatest_power", "other creature"), a), 2)
        self.assertEqual(game.evaluate(Amount("greatest_power", "creature"), a), 3)


COAT = real("Mithril Coat", "{3}", "Legendary Artifact — Equipment", "Indestructible\nWhen CARDNAME enters, attach it to target legendary creature you control.\n"
            "Equipped creature has indestructible.\nEquip {3}")
LEGEND = real("Legend", "{1}", "Legendary Creature — Human", "", "2", "2")
MALFUNCTION = real("Untimely Malfunction", "{1}{R}", "Instant", "Choose one —\n• Destroy target artifact.\n• Change the target of target spell or ability "
                   "with a single target.\n• One or two target creatures can't block this turn.")
DAMN = real("Damn", "{B}{B}", "Sorcery", "Destroy target creature. A creature destroyed this way can't be regenerated.\n"
            "Overload {2}{W}{W} (You may cast this spell for its overload cost. If you do, change \"target\" in its text to \"each.\")")


class SmallLinesTests(unittest.TestCase):
    def test_parse(self):
        for card in (COAT, MALFUNCTION, DAMN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_equipment_attaches_to_the_legendary_creature_as_it_enters(self):
        game, a, b, c = cast(COAT, "Legend", mine=[LEGEND, BEAR])
        coat = next(p for p in a.battlefield if p.card.name == "Mithril Coat")
        self.assertEqual(coat.attached_to.card.name, "Legend")

    def test_it_needs_a_legendary_creature(self):
        game, a, b, c = cast(COAT, mine=[BEAR])
        self.assertIsNone(next(p for p in a.battlefield if p.card.name == "Mithril Coat").attached_to)

    def test_one_or_two_target_creatures_cannot_block(self):
        from infernal_machine.effects import CANT_BLOCK
        game, a, b, c = cast(MALFUNCTION, "One or two", "Bear", "Ogre", theirs=[BEAR, OGRE, BEAR])
        blockers = sorted(p.card.name for p in b.battlefield if game.has_keyword(p, CANT_BLOCK))
        self.assertEqual(blockers, ["Bear", "Ogre"])

    def test_one_target_is_enough(self):
        from infernal_machine.effects import CANT_BLOCK
        game, a, b, c = cast(MALFUNCTION, "One or two", "Ogre", "No target", theirs=[BEAR, OGRE])
        self.assertEqual([p.card.name for p in b.battlefield if game.has_keyword(p, CANT_BLOCK)], ["Ogre"])

    def test_the_regeneration_sentence_does_not_get_in_the_way_of_overload(self):
        game, a, b, c = cast(DAMN, "Overload", mine=[BEAR], theirs=[OGRE])
        self.assertEqual((names(a), names(b)), ([], []))


SWAT = real("Deflecting Swat", "{2}{R}", "Instant", "If you control a commander, you may cast this spell without paying its mana cost.\n"
            "You may choose new targets for target spell or ability.")


class DeflectingSwatTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SWAT), [])

    def test_the_new_target_is_chosen(self):
        from tests.test_change_target import BOLT, stack_fight
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", SWAT, answers=("Spell", "Player: C"))
        self.assertEqual((b.life, c.life), (40, 37))
        self.assertEqual([e["to"] for e in a.player.events if e.get("event") == "target_changed"], ["Player: C (seat 2)"])

    def test_the_target_may_stay(self):
        from tests.test_change_target import BOLT, stack_fight
        game, a, b, c, responder = stack_fight(BOLT, "Player: B", SWAT, answers=("Spell",))
        self.assertEqual((b.life, c.life), (37, 40))
        self.assertEqual([e for e in a.player.events if e.get("event") == "target_changed"], [])
        self.assertTrue(responder.asked[-1][0].startswith("Player: B"))  # the current target is the first choice

    def test_a_spell_with_no_target_can_be_aimed_at_but_nothing_happens(self):
        from tests.test_change_target import stack_fight
        draw = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")
        game, a, b, c, _ = stack_fight(draw, "", SWAT, answers=("Spell",))
        self.assertEqual(([x.name for x in b.graveyard], len(a.hand)), (["Deflecting Swat"], 2))  # it was cast, and Divination still drew


BITTER = real("Bitter Triumph", "{1}{B}", "Instant", "As an additional cost to cast this spell, discard a card or pay 3 life.\nDestroy target creature or planeswalker.")
DEMAND = real("Demand Answers", "{1}{R}", "Instant", "As an additional cost to cast this spell, sacrifice an artifact or discard a card.\nDraw two cards.")
ROCK = real("Rock", "{1}", "Artifact", "")


class EitherCostTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual([unsupported_lines(c) for c in (BITTER, DEMAND)], [[], []])

    def test_paying_the_life(self):
        game, a, b, c = cast(BITTER, "Pay 3", "Bear", theirs=[BEAR], hand=[FOREST])
        self.assertEqual((a.life, names(b), [x.name for x in a.hand]), (37, [], ["Forest"]))

    def test_discarding_the_card(self):
        game, a, b, c = cast(BITTER, "Discard", "Bear", theirs=[BEAR], hand=[FOREST])
        self.assertEqual((a.life, names(b), [x.name for x in a.graveyard]), (40, [], ["Forest", "Bitter Triumph"]))

    def test_with_only_one_way_to_pay_it_is_not_asked(self):
        game, a, b, c = cast(BITTER, "Bear", theirs=[BEAR])  # nothing else in hand: pay the life
        self.assertEqual((a.life, names(b)), (37, []))

    def test_it_cannot_be_cast_when_neither_cost_can_be_paid(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield, a.life = [BITTER], lands(4), 2
        game.seats[1].battlefield = [Permanent(BEAR)]
        self.assertNotIn(CAST + "Bitter Triumph", game.legal_actions(a))

    def test_sacrificing_an_artifact(self):
        game, a, b, c = cast(DEMAND, "Rock", mine=[ROCK], hand=[FOREST], library=[FOREST] * 3)
        self.assertEqual(names(a), [])
        self.assertEqual(len(a.hand), 3)  # Forest still in hand, plus the two drawn

    def test_discarding_instead(self):
        game, a, b, c = cast(DEMAND, "Discard", mine=[ROCK], hand=[FOREST], library=[FOREST] * 3)
        self.assertEqual(names(a), ["Rock"])

    def test_the_artifact_option_is_not_offered_without_an_artifact(self):
        game, a, b, c = cast(DEMAND, hand=[FOREST], library=[FOREST] * 3)
        self.assertEqual([x.name for x in a.graveyard], ["Forest", "Demand Answers"])


REDIRECT = real("Redirect Lightning", "{R}", "Instant", "As an additional cost to cast this spell, pay 5 life or pay {2}.\n"
                "Change the target of target spell or ability with a single target.")
EATEN = real("Eaten Alive", "{B}", "Sorcery", "As an additional cost to cast this spell, sacrifice a creature or pay {3}{B}.\nExile target creature or planeswalker.")
MANGLER = real("Dusk Mangler", "{B}", "Sorcery", "As an additional cost to cast this spell, sacrifice a creature, discard a card, or pay 4 life.\nDraw a card.")


def bolt_then(response, *, b_lands, b_life, answers):
    """A casts Lightning Bolt at B; B (with `b_lands` lands and `b_life` life) answers with `response`."""
    from tests.test_change_target import BOLT, Responder
    responder = Responder(*answers)
    game, _ = table3(script("Player: B"), responder)
    a, b, c = game.seats
    a.hand, a.battlefield = [BOLT], lands(2)
    b.hand, b.battlefield, b.life = [response], lands(b_lands), b_life
    game._perform(a, CAST + "Lightning Bolt")
    return game, a, b, c, responder


class ManaOptionTests(unittest.TestCase):
    def test_parse(self):
        for card in (REDIRECT, EATEN, MANGLER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_options_of_each_cost(self):
        from infernal_machine.effects import additional_costs
        [redirect] = additional_costs(REDIRECT)
        self.assertEqual([(o.life, o.mana) for o in redirect.options], [(5, ""), (0, "{2}")])
        [mangler] = additional_costs(MANGLER)
        self.assertEqual([(o.sacrifice, o.discard, o.life) for o in mangler.options], [("creature", False, 0), (None, True, 0), (None, False, 4)])
        [eaten] = additional_costs(EATEN)
        self.assertEqual([(o.sacrifice, o.mana) for o in eaten.options], [("creature", ""), (None, "{3}{B}")])

    def test_with_the_life_the_extra_mana_is_not_needed(self):
        game, a, b, c, _ = bolt_then(REDIRECT, b_lands=1, b_life=40, answers=("Spell", "Player: C"))
        game._perform(b, CAST + "Redirect Lightning")
        run_stack(game)
        self.assertEqual((b.life, c.life), (35, 37))  # paid 5 life; the Bolt went to C

    def test_with_too_little_life_the_extra_mana_is_paid(self):
        game, a, b, c, _ = bolt_then(REDIRECT, b_lands=3, b_life=4, answers=("Spell", "Player: C"))
        game._perform(b, CAST + "Redirect Lightning")
        self.assertTrue(all(p.tapped for p in b.battlefield))  # {R} and the {2}
        run_stack(game)
        self.assertEqual((b.life, c.life), (4, 37))

    def test_it_is_not_cast_when_neither_the_life_nor_the_mana_is_there(self):
        game, a, b, c, _ = bolt_then(REDIRECT, b_lands=2, b_life=4, answers=("Spell",))
        self.assertNotIn(CAST + "Redirect Lightning", game.legal_actions(b))
        game, a, b, c, _ = bolt_then(REDIRECT, b_lands=2, b_life=5, answers=("Spell",))
        self.assertIn(CAST + "Redirect Lightning", game.legal_actions(b))  # exactly 5 life is enough

    def test_when_both_can_be_paid_you_choose(self):
        game, a, b, c, responder = bolt_then(REDIRECT, b_lands=3, b_life=40, answers=("Pay {2}", "Spell", "Player: C"))
        game._perform(b, CAST + "Redirect Lightning")
        self.assertTrue(all(p.tapped for p in b.battlefield))
        self.assertEqual(b.life, 40)

    def test_sacrifice_or_pay_mana(self):
        game, _ = table3(script("Pay", "Bear"))
        a = game.seats[0]
        a.hand, a.battlefield = [EATEN], lands(5) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._perform(a, CAST + "Eaten Alive")
        self.assertEqual(sum(p.tapped for p in a.battlefield), 5)  # {B} and {3}{B}, and the Bear stays
        self.assertIn("Bear", names(a))

    def test_sacrifice_or_pay_mana_chooses_the_sacrifice(self):
        game, a, b, c = cast(EATEN, "Sacrifice", "Ogre", mine=[BEAR], theirs=[OGRE], n=5)
        self.assertEqual((names(a), names(b)), ([], []))

    def test_three_ways_to_pay(self):
        game, _ = table3(script("Pay 4 life"))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [MANGLER, FOREST], lands(2) + [Permanent(BEAR)], [FOREST] * 3
        game._perform(a, CAST + "Dusk Mangler")
        run_stack(game)
        self.assertEqual((a.life, names(a), len(a.hand)), (36, ["Bear"], 2))


CHORD = real("Chord of Calling", "{X}{G}{G}{G}", "Instant", "Convoke\nSearch your library for a creature card with mana value X or less, put it onto the battlefield, then shuffle.")
ZENITH = real("Green Sun's Zenith", "{X}{G}", "Sorcery", "Search your library for a green creature card with mana value X or less, put it onto the battlefield, then shuffle. Shuffle CARDNAME into its owner's library.")
ORDER = real("Natural Order", "{2}{G}{G}", "Sorcery", "As an additional cost to cast this spell, sacrifice a green creature.\nSearch your library for a green creature card, put it onto the battlefield, then shuffle.")
CALL = real("Eladamri's Call", "{G}{W}", "Instant", "Search your library for a creature card, reveal that card, put it into your hand, then shuffle.")
ELF = real("Elf", "{G}", "Creature — Elf", "", "1", "1", colors=("G",))
TITAN = real("Titan", "{4}{G}", "Creature — Giant", "", "6", "6", colors=("G",))
BEAR_G = real("Green Bear", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
KNIGHT = real("Knight", "{1}{W}", "Creature — Knight", "", "2", "2", colors=("W",))


class SearchTests(unittest.TestCase):
    def test_parse(self):
        for card in (CHORD, ZENITH, ORDER, CALL):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_chord_of_calling_puts_a_creature_of_mana_value_x_or_less_onto_the_battlefield(self):
        game, a, b, c = cast(CHORD, "2", "Knight", library=[TITAN, KNIGHT, ELF], n=6)
        self.assertEqual(names(a), ["Knight"])
        self.assertEqual(sorted(x.name for x in a.library), ["Elf", "Titan"])

    def test_x_zero_finds_nothing_costly(self):
        game, a, b, c = cast(CHORD, "0", library=[TITAN, KNIGHT], n=6)
        self.assertEqual(names(a), [])

    def test_green_sun_zenith_wants_a_green_one_and_shuffles_itself_back(self):
        game, a, b, c = cast(ZENITH, "2", "Green Bear", library=[KNIGHT, BEAR_G, TITAN], n=6)
        self.assertEqual(names(a), ["Green Bear"])
        self.assertIn("Green Sun's Zenith", [x.name for x in a.library])
        self.assertEqual(a.graveyard, [])

    def test_natural_order_sacrifices_a_green_creature_and_finds_any_green_creature(self):
        game, a, b, c = cast(ORDER, "Elf", "Titan", mine=[ELF], library=[KNIGHT, TITAN])
        self.assertEqual(names(a), ["Titan"])
        self.assertEqual([x.name for x in a.graveyard], ["Elf", "Natural Order"])

    def test_natural_order_needs_a_green_creature_to_sacrifice(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [ORDER], lands(6) + [Permanent(KNIGHT)], [TITAN]
        self.assertNotIn(CAST + "Natural Order", game.legal_actions(a))

    def test_revealing_that_card(self):
        game, a, b, c = cast(CALL, "Knight", library=[TITAN, KNIGHT])
        self.assertEqual([x.name for x in a.hand], ["Knight"])


EXPERTISE = real("Rishkar's Expertise", "{4}{G}{G}", "Sorcery", "Draw cards equal to the greatest power among creatures you control.\n"
                 "You may cast a spell with mana value 5 or less from your hand without paying its mana cost.")
SMALL_SPELL = real("Small Spell", "{2}{R}", "Sorcery", "Draw a card.")
BIG_SPELL = real("Big Spell", "{4}{R}{R}", "Sorcery", "Draw a card.")


class FreeCastTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(EXPERTISE), [])

    def test_a_spell_of_mana_value_five_or_less_is_cast_free_from_the_hand(self):
        game, a, b, c = cast(EXPERTISE, "Small Spell", mine=[OGRE], hand=[SMALL_SPELL, BIG_SPELL, FOREST], library=[FOREST] * 6, n=6)
        self.assertEqual(sorted(x.name for x in a.graveyard), ["Rishkar's Expertise", "Small Spell"])
        self.assertEqual(sorted(x.name for x in a.hand), ["Big Spell", "Forest", "Forest", "Forest", "Forest", "Forest"])  # drew 3, then 1; none of it paid for

    def test_nothing_is_offered_above_the_limit_or_for_lands(self):
        asked = []

        def record(prompt, options):
            asked.append(list(options))
            return len(options) - 1
        game, _ = table3(record)
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [EXPERTISE, BIG_SPELL, FOREST], lands(6), [FOREST] * 3
        game._perform(a, CAST + "Rishkar's Expertise")
        run_stack(game)
        self.assertFalse([o for o in asked if "Small Spell" in o or "Big Spell" in o or "Forest" in o and "Don't cast" in o])

    def test_it_may_be_declined(self):
        game, a, b, c = cast(EXPERTISE, "Don't", hand=[SMALL_SPELL], library=[FOREST] * 3)
        self.assertEqual([x.name for x in a.hand], ["Small Spell"])  # no creature to draw for; the spell stays in hand


WILDSPEAKER = real("Return of the Wildspeaker", "{4}{G}", "Instant", "Choose one —\n• Draw cards equal to the greatest power among non-Human creatures you control.\n"
                   "• Non-Human creatures you control get +3/+3 until end of turn.")
STAMPEDE = real("Overwhelming Stampede", "{3}{G}{G}", "Sorcery", "Until end of turn, creatures you control gain trample and get +X/+X, where X is the greatest power among creatures you control.")
SINK = real("Sink into Stupor", "{1}{U}{U}", "Instant", "Return target spell or nonland permanent an opponent controls to its owner's hand.")


class PumpAndBounceTests(unittest.TestCase):
    def test_parse(self):
        for card in (WILDSPEAKER, STAMPEDE, SINK):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_non_human_creatures_get_the_bonus(self):
        game, a, b, c = cast(WILDSPEAKER, "Non-Human", mine=[HUMAN, OGRE, BEAR])
        power = {p.card.name: game.power(p) for p in a.battlefield if "Creature" in p.card.type_line}
        self.assertEqual(power, {"Human": 6, "Ogre": 6, "Bear": 5})

    def test_cards_equal_to_the_greatest_power_among_non_humans(self):
        game, a, b, c = cast(WILDSPEAKER, "Draw", mine=[HUMAN, OGRE], library=[FOREST] * 5)
        self.assertEqual(len(a.hand), 3)  # the Ogre's 3, not the Human's 6

    def test_trample_and_the_greatest_power_for_each(self):
        game, a, b, c = cast(STAMPEDE, mine=[BEAR, OGRE], theirs=[BEAR])
        mine = {p.card.name: (game.power(p), game.has_keyword(p, "trample")) for p in a.battlefield if "Creature" in p.card.type_line}
        self.assertEqual(mine, {"Bear": (5, True), "Ogre": (6, True)})
        self.assertEqual(game.power(b.battlefield[0]), 2)

    def test_it_returns_an_opponents_permanent_or_spell_to_its_owners_hand(self):
        game, _ = table3(script("Bear"))
        a, b, c = game.seats
        a.hand, a.battlefield = [SINK], lands(3)
        b.battlefield = [Permanent(BEAR), Permanent(FOREST)]
        game._perform(a, CAST + "Sink into Stupor")
        run_stack(game)
        self.assertEqual(([x.name for x in b.hand], names(b)), (["Bear"], ["Forest"]))

    def test_it_returns_a_spell_and_not_one_of_your_own(self):
        from tests.test_change_target import BOLT
        game, _ = table3(script("Player: A"), script("Spell"))
        a, b, c = game.seats
        a.hand, a.battlefield = [BOLT], lands(2)
        b.hand, b.battlefield = [SINK, BOLT], lands(4) + [Permanent(BEAR)]
        game._perform(a, CAST + "Lightning Bolt")
        game._perform(b, CAST + "Lightning Bolt")  # B's own spell is on the stack too
        options = [label for label, _ in game.target_options("spell or nonland permanent an opponent controls", b)]
        self.assertEqual([label for label in options if label.startswith("Spell")], ["Spell: Lightning Bolt (seat 0)"])
        self.assertFalse(any(label.startswith("Bear") for label in options))  # its own Bear is not an opponent's
        game._perform(b, CAST + "Sink into Stupor")
        run_stack(game)
        self.assertEqual(([x.name for x in a.hand], a.graveyard, b.life), (["Lightning Bolt"], [], 40))  # A's Bolt never hit B


BMC = real("Black Market Connections", "{2}{B}", "Enchantment", "At the beginning of your first main phase, choose one or more —\n"
           "• Sell Contraband — Create a Treasure token. You lose 1 life.\n• Buy Information — Draw a card. You lose 2 life.\n"
           "• Hire a Mercenary — Create a 3/2 colorless Shapeshifter creature token with changeling. You lose 3 life.")


class ModeLabelTests(unittest.TestCase):
    def test_a_named_mode_is_the_mode(self):
        self.assertEqual(unsupported_lines(BMC), [])

    def test_the_named_modes_work(self):
        game, _ = table3(script("Create a Treasure", "Create a 3/2", "Done"))
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(BMC)], [FOREST] * 3
        game.trigger("first_main", a.battlefield[0], a)
        run_stack(game)
        self.assertEqual((a.life, sorted(p.card.name for p in a.battlefield)), (36, ["Black Market Connections", "Shapeshifter", "Treasure"]))


if __name__ == "__main__":
    unittest.main()
