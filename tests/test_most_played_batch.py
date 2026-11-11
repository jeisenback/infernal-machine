"""Most-played cards the engine could not play (#200), from their real Oracle text: Plaza of Heroes' "one mana of any color among
legendary permanents you control", Sanctum Weaver's "X mana of any one color", Inspiring Call, Shadowspear and Colossus Hammer ("lose
hexproof and indestructible", "loses flying"), Fountainport's "Sacrifice a token", Cruel Celebrant's "creature or planeswalker ... dies",
Tragic Slip's morbid and Warstorm Surge's "it deals damage equal to its power" (the creature that entered deals it)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, SOL_RING, activate, enter, lands, pick, real, run_stack, table3

PLAZA = real("Plaza of Heroes", "", "Land", "{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only to cast a legendary spell.\n"
             "{T}: Add one mana of any color among legendary permanents you control.\n{3}, {T}, Exile this land: Target legendary creature "
             "gains hexproof and indestructible until end of turn.")
WEAVER = real("Sanctum Weaver", "{1}{G}", "Enchantment Creature — Dryad", "{T}: Add X mana of any one color, where X is the number of "
              "enchantments you control.", "0", "2", colors=("G",))
CALL = real("Inspiring Call", "{2}{G}", "Instant", "Draw a card for each creature you control with a +1/+1 counter on it. Those creatures gain "
            "indestructible until end of turn. (Damage and effects that say \"destroy\" don't destroy them.)", colors=("G",))
SHADOWSPEAR = real("Shadowspear", "{1}", "Legendary Artifact — Equipment", "Equipped creature gets +1/+1 and has trample and lifelink.\n{1}: "
                   "Permanents your opponents control lose hexproof and indestructible until end of turn.\nEquip {2}")
HAMMER = real("Colossus Hammer", "{1}", "Artifact — Equipment", "Equipped creature gets +10/+10 and loses flying.\nEquip {8} ({8}: Attach "
              "to target creature you control. Equip only as a sorcery.)")
FOUNTAINPORT = real("Fountainport", "", "Land", "{T}: Add {C}.\n{2}, {T}, Sacrifice a token: Draw a card.\n{3}, {T}, Pay 1 life: Create a "
                    "1/1 blue Fish creature token.\n{4}, {T}: Create a Treasure token.")
CELEBRANT = real("Cruel Celebrant", "{W}{B}", "Creature — Vampire", "Whenever this creature or another creature or planeswalker you control "
                 "dies, each opponent loses 1 life and you gain 1 life.", "1", "2", colors=("W", "B"))
SLIP = real("Tragic Slip", "{B}", "Instant", "Target creature gets -1/-1 until end of turn.\nMorbid — That creature gets -13/-13 until end "
            "of turn instead if a creature died this turn.", colors=("B",))
SURGE = real("Warstorm Surge", "{5}{R}", "Enchantment", "Whenever a creature you control enters, it deals damage equal to its power to any "
             "target.", colors=("R",))
BELAKOR = real("Be'lakor, the Dark Master", "{3}{U}{B}{R}", "Legendary Creature — Demon Noble", "Flying\nPrince of Chaos — When Be'lakor "
               "enters, you draw X cards and you lose X life, where X is the number of Demons you control.\nLord of Torment — Whenever "
               "another Demon you control enters, it deals damage equal to its power to any target.", "6", "5", colors=("U", "B", "R"))
CARDS = (PLAZA, WEAVER, CALL, SHADOWSPEAR, HAMMER, FOUNTAINPORT, CELEBRANT, SLIP, SURGE, BELAKOR)

TITANIA = real("Titania, Protector of Argoth", "{3}{G}{G}", "Legendary Creature — Elemental", "When Titania enters, return target land card "
               "from your graveyard to the battlefield.\nWhenever a land you control is put into a graveyard from the battlefield, create a "
               "5/3 green Elemental creature token.", "5", "3", colors=("G",))
OATH = real("Oath of Teferi", "{3}{W}{U}", "Legendary Enchantment", "When Oath of Teferi enters, exile another target permanent you control. "
            "Return it to the battlefield under its owner's control at the beginning of the next end step.\nYou may activate the loyalty "
            "abilities of planeswalkers you control twice each turn rather than only once.", colors=("W", "U"))
CITADEL = real("Darksteel Citadel", "", "Artifact Land", "Indestructible (Effects that say \"destroy\" don't destroy it. If its toughness is "
               "0 or less, it still dies, though.)\n{T}: Add {C}.")
SCOUT = real("Gladecover Scout", "{G}", "Creature — Elf Scout", "Hexproof (This creature can't be the target of spells or abilities your "
             "opponents control.)", "1", "1", colors=("G",))
DRAKE = real("Wind Drake", "{2}{U}", "Creature — Drake", "Flying", "2", "2", colors=("U",))
JACE = real("Jace Beleren", "{1}{U}{U}", "Legendary Planeswalker — Jace", "+2: Each player draws a card.\n−1: Target player draws a card.\n"
            "−10: Target player mills twenty cards.", colors=("U",))
NIGHTHAWK = real("Vampire Nighthawk", "{1}{B}{B}", "Creature — Vampire", "Flying\nDeathtouch\nLifelink", "2", "3", colors=("B",))
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure", oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")


def payable(battlefield, cost):
    game, _ = table3()
    seat = game.seats[0]
    seat.battlefield = battlefield
    return game._payment(seat, Card(name="Probe", mana_cost=cost, type_line="Sorcery")) is not None


def cast(game, seat, card, n=6):
    seat.battlefield += lands(n)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


class MostPlayedBatchTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_plaza_of_heroes_makes_the_colors_of_your_legendary_permanents(self):
        self.assertTrue(payable([Permanent(PLAZA), Permanent(TITANIA)], "{G}"))  # (a nonlegendary spell: not the restricted mana)
        self.assertFalse(payable([Permanent(PLAZA), Permanent(TITANIA)], "{U}"))
        self.assertFalse(payable([Permanent(PLAZA), Permanent(BEAR)], "{G}"))  # the Bear isn't legendary
        self.assertTrue(payable([Permanent(PLAZA), Permanent(OATH)], "{U}"))  # any legendary permanent, not only a creature (Mox Amber's)

    def test_sanctum_weaver_makes_one_for_each_enchantment(self):
        weaver = [Permanent(WEAVER), Permanent(SURGE), Permanent(Card(name="Shrine", type_line="Enchantment"))]
        self.assertTrue(payable(weaver, "{G}{G}{G}"))  # it counts itself
        self.assertFalse(payable(weaver, "{G}{G}{G}{G}"))
        # (the payment lets each of the X be its own color, as it does for a power's worth: a known simplification)

    def test_inspiring_call_draws_for_and_protects_the_creatures_with_counters(self):
        game, _ = table3()
        a = game.seats[0]
        countered, plain = Permanent(OGRE), Permanent(BEAR)
        countered.counters["+1/+1"] = 1
        a.battlefield, a.library = [countered, plain], [FOREST] * 3
        cast(game, a, CALL)
        game.destroy(countered)
        game.destroy(plain)
        self.assertEqual((len(a.hand), countered in a.battlefield, plain in a.battlefield), (1, True, False))

    def test_shadowspear_strips_hexproof_and_indestructible_from_the_opponents_only(self):
        game, _ = table3()
        a, b, _ = game.seats
        citadel, scout, mine = Permanent(CITADEL), Permanent(SCOUT), Permanent(CITADEL)
        a.battlefield, b.battlefield = [Permanent(SHADOWSPEAR), mine] + lands(1), [citadel, scout]
        self.assertNotIn(scout, [t for _, t in game.target_options("creature", a)])
        activate(game, a, "lose hexproof")
        self.assertIn(scout, [t for _, t in game.target_options("creature", a)])
        game.destroy(citadel)  # an artifact land: not only creatures
        game.destroy(mine)
        self.assertEqual((citadel in b.battlefield, mine in a.battlefield), (False, True))

    def test_colossus_hammer_takes_flying_away(self):
        game, _ = table3()
        a = game.seats[0]
        drake, other = Permanent(DRAKE), Permanent(DRAKE)
        a.battlefield = [drake, other, Permanent(HAMMER, attached_to=drake)]
        self.assertEqual((game.power(drake), game.has_keyword(drake, "flying"), game.has_keyword(other, "flying")), (12, False, True))

    def test_fountainport_sacrifices_a_token_not_a_card(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(FOUNTAINPORT), Permanent(BEAR)] + lands(2), [FOREST] * 3
        self.assertFalse(any("Sacrifice a token" in x for x in game.legal_actions(a) if x.startswith(ACTIVATE)))
        token = Permanent(TREASURE)
        a.battlefield.append(token)
        activate(game, a, "Sacrifice a token")
        self.assertEqual((token in a.battlefield, len(a.hand), any(p.card is BEAR for p in a.battlefield)), (False, 1, True))

    def test_cruel_celebrant_hears_a_planeswalker_die_but_not_an_artifact(self):
        game, _ = table3()
        a, b, c = game.seats
        jace, ring = Permanent(JACE, loyalty=3), Permanent(SOL_RING)
        a.battlefield = [Permanent(CELEBRANT), jace, ring]
        game.destroy(jace)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (41, 39, 39))
        game.destroy(ring)
        run_stack(game)
        self.assertEqual((a.life, b.life), (41, 39))

    def test_tragic_slip_is_minus_13_only_after_a_death(self):
        for died in (False, True):
            game, _ = table3(pick("Ogre"))
            a, b, _ = game.seats
            ogre = Permanent(OGRE)
            b.battlefield = [ogre, Permanent(BEAR)]
            if died:
                game.destroy(b.battlefield[1])
            cast(game, a, SLIP, n=1)
            game._check_state()
            self.assertEqual(ogre in b.battlefield, not died, died)  # -1/-1 leaves the 3/3 at 2/2; -13/-13 kills it

    def test_warstorm_surge_has_the_creature_deal_the_damage(self):
        game, _ = table3(pick("Ogre"))
        a, b, _ = game.seats
        ogre = Permanent(OGRE)
        a.battlefield, b.battlefield = [Permanent(SURGE)], [ogre]
        enter(game, a, NIGHTHAWK)
        run_stack(game)
        game._check_state()
        self.assertEqual((ogre in b.battlefield, a.life), (False, 42))  # its deathtouch and lifelink: the Nighthawk dealt it

    def test_warstorm_surge_ignores_an_opponents_creature(self):
        game, _ = table3(pick("Player: A"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(SURGE)]
        enter(game, b, OGRE)
        run_stack(game)
        self.assertEqual((a.life, b.life), (40, 40))


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


if __name__ == "__main__":
    unittest.main()
