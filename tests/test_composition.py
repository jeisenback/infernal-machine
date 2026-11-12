"""Deck composition against the Command Zone's template (infernal_machine/composition.py), from the cards' real Oracle text: each role
is read from the effects the engine parsed, so a pump or a blink of your own creature is not removal and a land is not ramp."""

import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.composition import DRAW, MASS, RAMP, TARGETED, TEMPLATE, analyze_composition, format_composition, roles
from tests.helpers import FOREST, real, scryfall

SOL_RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))
RAMPANT = real("Rampant Growth", "{1}{G}", "Sorcery", "Search your library for a basic land card, put that card onto the battlefield tapped, "
               "then shuffle.", colors=("G",))
CULTIVATE = real("Cultivate", "{2}{G}", "Sorcery", "Search your library for up to two basic land cards, reveal those cards, put one onto the "
                 "battlefield tapped and the other into your hand, then shuffle.", colors=("G",))
HARMONIZE = real("Harmonize", "{2}{G}{G}", "Sorcery", "Draw three cards.", colors=("G",))
SWORDS = real("Swords to Plowshares", "{W}", "Instant", "Exile target creature. Its controller gains life equal to its power.", colors=("W",))
COUNTERSPELL = real("Counterspell", "{U}{U}", "Instant", "Counter target spell.", colors=("U",))
WRATH = real("Wrath of God", "{2}{W}{W}", "Sorcery", "Destroy all creatures. They can't be regenerated.", colors=("W",))
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.", colors=("G",))
EPHEMERATE = real("Ephemerate", "{W}", "Instant", "Exile target creature you control, then return it to the battlefield under its owner's "
                  "control.\nRebound (If you cast this spell from your hand, exile it as it resolves. At the beginning of your next upkeep, "
                  "you may cast this card from exile without paying its mana cost.)", colors=("W",))
BORROWER = Card.from_scryfall(scryfall(
    "adventure",
    {"name": "Brazen Borrower", "mana_cost": "{1}{U}{U}", "type_line": "Creature — Faerie Rogue",
     "oracle_text": "Flash\nFlying\nThis creature can block only creatures with flying.", "power": "3", "toughness": "1"},
    {"name": "Petty Theft", "mana_cost": "{1}{U}", "type_line": "Instant — Adventure",
     "oracle_text": "Return target nonland permanent an opponent controls to its owner's hand."}, colors=["U"]))
TOWER = real("Command Tower", "", "Land", "{T}: Add one mana of any color in your commander's color identity.")
LAND_TAX = real("Land Tax", "{W}", "Enchantment", "At the beginning of your upkeep, if an opponent controls more lands than you, you may search "
                "your library for up to three basic land cards, reveal them, put them into your hand, then shuffle.", colors=("W",))
RESCUE = real("Rescue", "{U}", "Instant", "Return target permanent you control to its owner's hand.", colors=("U",))
UNREAD = real("Unread Thing", "{2}", "Artifact", "{T}: Add {C}.\nThis artifact does something the engine has never heard of.")
COMMANDER = real("Titania, Protector of Argoth", "{3}{G}{G}", "Legendary Creature — Elemental", "When Titania enters, return target land card "
                 "from your graveyard to the battlefield.\nWhenever a land you control is put into a graveyard from the battlefield, create a "
                 "5/3 green Elemental creature token.", "5", "3", colors=("G",))


class CompositionTests(unittest.TestCase):
    def test_ramp_is_mana_from_a_nonland_or_lands_onto_the_battlefield(self):
        for card in (SOL_RING, ELVES, RAMPANT, CULTIVATE):
            self.assertEqual(roles(card), {RAMP}, card.name)
        self.assertEqual(roles(TOWER), set())  # a land that taps for mana is a land, not ramp
        self.assertEqual(roles(LAND_TAX), set())  # lands into the hand are not ramp

    def test_the_other_roles(self):
        self.assertEqual(roles(HARMONIZE), {DRAW})
        self.assertEqual(roles(SWORDS), {TARGETED})
        self.assertEqual(roles(COUNTERSPELL), {TARGETED})
        self.assertEqual(roles(WRATH), {MASS})

    def test_a_pump_or_a_blink_of_your_own_creature_is_no_removal(self):
        self.assertEqual(roles(GROWTH), set())
        self.assertEqual(roles(EPHEMERATE), set())
        self.assertEqual(roles(RESCUE), set())  # a bounce of your own permanent

    def test_an_adventure_counts_its_other_half(self):
        self.assertEqual(roles(BORROWER), {TARGETED})  # Petty Theft

    def test_the_99_are_counted_and_an_unread_card_gets_no_role(self):
        deck = Deck(commanders=[COMMANDER], main=[FOREST] * 3 + [SOL_RING, HARMONIZE, WRATH, GROWTH, UNREAD], sideboard=[])
        result = analyze_composition(deck)
        self.assertEqual((len(result.lands), result.roles[RAMP], result.roles[DRAW], result.roles[MASS], result.plan, result.unread),
                         (3, ["Sol Ring"], ["Harmonize"], ["Wrath of God"], ["Giant Growth"], ["Unread Thing"]))
        report = format_composition(result)
        self.assertIn("lands                   3       38  35 short", report)
        self.assertIn("not read", report)
        self.assertNotIn("Titania", report)  # the commander is not one of the 99

    def test_the_template_is_the_command_zones(self):
        self.assertEqual(TEMPLATE, {"lands": 38, RAMP: 10, DRAW: 12, TARGETED: 12, MASS: 6})


if __name__ == "__main__":
    unittest.main()
