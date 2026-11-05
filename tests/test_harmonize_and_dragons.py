"""Harmonize (Wild Ride, Winternight Stories), Secret Identity, and the Dragons of Standard's Boros deck, from their real Oracle text:
Magda, the Hoardmaster ("Whenever you commit a crime") and Sarkhan, Dragon Ascendant (behold a Dragon; becomes a Dragon until end of
turn)."""

import unittest

from infernal_machine.game import ACTIVATE, CAST, HARMONIZE_NONE, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, end_turn, lands, real, run_stack, script, table3

HARMONIZE = ("Harmonize {cost} (You may cast this card from your graveyard for its harmonize cost. You may tap a creature you control to "
             "reduce that cost by {{X}}, where X is its power. Then exile this spell.)")
WILD_RIDE = real("Wild Ride", "{R}", "Sorcery", "Target creature gets +3/+0 and gains haste until end of turn.\n"
                 + HARMONIZE.format(cost="{4}{R}"), colors=("R",))
WINTERNIGHT = real("Winternight Stories", "{2}{U}", "Sorcery", "Draw three cards. Then discard two cards unless you discard a creature card.\n"
                   + HARMONIZE.format(cost="{4}{U}"), colors=("U",))
SECRET = real("Secret Identity", "{U}", "Instant", "Choose one —\n• Conceal — Until end of turn, target creature you control becomes a Citizen "
              "with base power and toughness 1/1 and gains hexproof.\n• Reveal — Until end of turn, target creature you control becomes a "
              "Hero with base power and toughness 3/4 and gains flying and vigilance.", colors=("U",))
MAGDA = real("Magda, the Hoardmaster", "{1}{R}", "Legendary Creature — Dwarf Berserker", "Whenever you commit a crime, create a tapped "
             "Treasure token. This ability triggers only once each turn. (Targeting opponents, anything they control, and/or cards in their "
             "graveyards is a crime.)\nSacrifice three Treasures: Create a 4/4 red Scorpion Dragon creature token with flying and haste. "
             "Activate only as a sorcery.", "2", "2", colors=("R",))
SARKHAN = real("Sarkhan, Dragon Ascendant", "{1}{R}", "Legendary Creature — Human Druid", "When Sarkhan enters, you may behold a Dragon. If "
               "you do, create a Treasure token. (To behold a Dragon, choose a Dragon you control or reveal a Dragon card from your hand.)\n"
               "Whenever a Dragon you control enters, put a +1/+1 counter on Sarkhan. Until end of turn, Sarkhan becomes a Dragon in "
               "addition to his other types and gains flying.", "2", "2", colors=("R",))
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
CURATOR = real("Keen-Eyed Curator", "{G}{G}", "Creature — Raccoon Scout", "As long as there are four or more card types among cards exiled "
               "with this creature, it gets +4/+4 and has trample.\n{1}: Exile target card from a graveyard.", "3", "3", colors=("G",))
COUNTERSPELL = real("Counterspell", "{U}{U}", "Instant", "Counter target spell.", colors=("U",))
DRAGON = real("Whelp", "{1}{R}", "Creature — Dragon", "Flying", "2", "2", colors=("R",))


def table(*answers, battlefield=(), hand=(), graveyard=()):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield, a.hand, a.graveyard = list(battlefield), list(hand), list(graveyard)
    for seat in game.seats:
        seat.library = [FOREST] * 5
    return game, a, b, c


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


def treasures(seat):
    return [p for p in seat.battlefield if p.card.name == "Treasure"]


class HarmonizeAndDragonsTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (WILD_RIDE, WINTERNIGHT, SECRET, MAGDA, SARKHAN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_harmonize_taps_a_creature_to_pay_its_power_less(self):
        ogre, bear = Permanent(OGRE, sick=True), Permanent(BEAR)  # summoning sickness doesn't stop the tapping
        game, a, _, _ = table("Bear", battlefield=lands(2) + [ogre, bear], graveyard=[WILD_RIDE])
        game._perform(a, offered(game, a, "Cast from graveyard: Wild Ride")[0])  # {4}{R} less 3: two lands pay the rest
        run_stack(game)
        self.assertTrue(ogre.tapped)
        self.assertEqual((game.power(bear), a.graveyard, a.exile), (5, [], [WILD_RIDE]))

    def test_harmonize_can_be_cast_for_its_full_cost_without_tapping(self):
        ogre, bear = Permanent(OGRE), Permanent(BEAR)
        game, a, _, _ = table("Bear", HARMONIZE_NONE, battlefield=lands(5) + [ogre, bear], graveyard=[WILD_RIDE])
        game._perform(a, offered(game, a, "Cast from graveyard: Wild Ride")[0])
        run_stack(game)
        self.assertEqual((ogre.tapped, bear.tapped, game.power(bear)), (False, False, 5))

    def test_harmonize_needs_enough_power_or_mana(self):
        game, a, _, _ = table(battlefield=lands(2) + [Permanent(BEAR)], graveyard=[WILD_RIDE])  # {4}{R} less 2: three mana, two lands
        self.assertEqual(offered(game, a, "Cast from graveyard: Wild Ride"), [])
        a.battlefield = lands(2) + [Permanent(BEAR, tapped=True), Permanent(OGRE, tapped=True)]  # a tapped creature can't be tapped
        self.assertEqual(offered(game, a, "Cast from graveyard: Wild Ride"), [])

    def test_harmonize_offers_only_creatures_to_tap(self):
        game, a, _, _ = table("Bear", battlefield=lands(6), graveyard=[WILD_RIDE])
        a.battlefield.append(Permanent(BEAR))
        asked = []
        choose = a.player.choose
        a.player.choose = lambda prompt, options: asked.append(list(options)) or choose(prompt, options)
        game._perform(a, offered(game, a, "Cast from graveyard: Wild Ride")[0])
        harmonize = [options for options in asked if HARMONIZE_NONE in options]
        self.assertEqual(len(harmonize), 1)
        self.assertEqual([o for o in harmonize[0] if o != HARMONIZE_NONE and not o.startswith("Bear")], [])

    def test_harmonize_with_a_creature_that_makes_mana_leaves_it_to_pay_for_mana(self):
        elf = Permanent(real("Elf", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",)))
        game, a, _, _ = table(battlefield=lands(3) + [elf], graveyard=[WINTERNIGHT])  # tapping the Elf pays {1} less but makes no mana
        self.assertEqual(offered(game, a, "Cast from graveyard: Winternight Stories"), [])

    def test_secret_identity_makes_a_creature_a_3_4_flier(self):
        bear = Permanent(BEAR)
        game, a, _, _ = table("Until end of turn, target creature you control becomes a Hero", "Bear", battlefield=lands(1) + [bear], hand=[SECRET])
        game._perform(a, CAST + "Secret Identity")
        run_stack(game)
        self.assertEqual((game.power(bear), game.toughness(bear)), (3, 4))
        self.assertTrue(game.has_keyword(bear, "flying") and game.has_keyword(bear, "vigilance"))

    def test_secret_identity_conceal_makes_a_1_1_with_hexproof(self):
        ogre = Permanent(OGRE)
        game, a, _, _ = table("Until end of turn, target creature you control becomes a Citizen", "Ogre", battlefield=lands(1) + [ogre], hand=[SECRET])
        game._perform(a, CAST + "Secret Identity")
        run_stack(game)
        self.assertEqual((game.power(ogre), game.toughness(ogre), game.has_keyword(ogre, "hexproof")), (1, 1, True))

    def test_targeting_an_opponent_is_a_crime_that_makes_one_treasure_a_turn(self):
        game, a, b, _ = table("Player: B", "Player: B", battlefield=lands(2) + [Permanent(MAGDA)], hand=[SHOCK, SHOCK])
        game._perform(a, CAST + "Shock")
        run_stack(game)
        self.assertEqual([p.tapped for p in treasures(a)], [True])
        game._perform(a, CAST + "Shock")
        run_stack(game)
        self.assertEqual((len(treasures(a)), b.life), (1, 36))  # only once each turn

    def test_targeting_an_opponents_creature_or_graveyard_card_is_a_crime(self):
        game, a, b, _ = table("Bear", battlefield=lands(1) + [Permanent(MAGDA)], hand=[SHOCK])
        b.battlefield = [Permanent(BEAR)]
        game._perform(a, CAST + "Shock")
        run_stack(game)
        self.assertEqual(len(treasures(a)), 1)

    def test_targeting_a_card_in_an_opponents_graveyard_is_a_crime(self):
        game, a, b, _ = table("Bear", battlefield=lands(1) + [Permanent(MAGDA), Permanent(CURATOR)])
        b.graveyard = [BEAR]
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Keen-Eyed Curator")))
        run_stack(game)
        self.assertEqual((b.exile, len(treasures(a))), ([BEAR], 1))

    def test_targeting_an_opponents_spell_is_a_crime(self):
        game, a, b, _ = table(battlefield=lands(2) + [Permanent(MAGDA)], hand=[COUNTERSPELL])
        game.stack.append(StackItem(SHOCK, b, [], []))
        game._perform(a, CAST + "Counterspell")
        run_stack(game)
        self.assertEqual(len(treasures(a)), 1)

    def test_targeting_your_own_creature_is_no_crime(self):
        game, a, _, _ = table("Bear", battlefield=lands(1) + [Permanent(MAGDA), Permanent(BEAR)], hand=[SHOCK])
        game._perform(a, CAST + "Shock")
        run_stack(game)
        self.assertEqual(treasures(a), [])

    def test_sarkhan_beholds_a_dragon_for_a_treasure(self):
        game, a, _, _ = table(battlefield=lands(2), hand=[SARKHAN, DRAGON])
        game._perform(a, CAST + "Sarkhan, Dragon Ascendant")
        run_stack(game)
        self.assertEqual(len(treasures(a)), 1)
        game, a, _, _ = table(battlefield=lands(2), hand=[SARKHAN, BEAR])  # no Dragon to behold
        game._perform(a, CAST + "Sarkhan, Dragon Ascendant")
        run_stack(game)
        self.assertEqual(treasures(a), [])

    def test_sarkhan_grows_and_becomes_a_flying_dragon_until_end_of_turn(self):
        sarkhan = Permanent(SARKHAN)
        game, a, _, _ = table(battlefield=lands(2) + [sarkhan], hand=[DRAGON])
        game._perform(a, CAST + "Whelp")
        run_stack(game)
        self.assertEqual(sarkhan.counters.get("+1/+1"), 1)
        self.assertIn("Dragon", sarkhan.card.type_line.split())
        self.assertTrue(game.has_keyword(sarkhan, "flying"))
        end_turn(game, a)
        self.assertNotIn("Dragon", sarkhan.card.type_line.split())
        self.assertFalse(game.has_keyword(sarkhan, "flying"))
        self.assertEqual(sarkhan.counters.get("+1/+1"), 1)

    def test_sarkhan_ignores_a_creature_that_is_not_a_dragon(self):
        sarkhan = Permanent(SARKHAN)
        game, a, _, _ = table(battlefield=lands(2) + [sarkhan], hand=[BEAR])
        game._perform(a, CAST + "Bear")
        run_stack(game)
        self.assertEqual((sarkhan.counters.get("+1/+1"), sarkhan.card is SARKHAN), (None, True))


if __name__ == "__main__":
    unittest.main()
