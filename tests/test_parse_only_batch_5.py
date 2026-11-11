"""The fifth batch of cards whose every effect the engine already had, read from new wordings (each picked with Forge's card scripts),
from their real Oracle text: amounts ("your life total", "each creature your opponents control", "the greatest mana value among
artifacts you control", "tapped creatures" and "attacking Elves" you control, "each other Dinosaur you control", "each Zombie card in
your graveyard"), "enters with a +1/+1 counter on it for each ...", "mills half their library, rounded down", "Destroy all creatures that
entered this turn.", "Counter target spell with mana value 4 or greater.", "a blue instant card", "all legendary permanent cards",
"Whenever a player draws a card", "Whenever a legendary creature you control deals combat damage to a player", damage to "each opponent
and each creature they control", "You gain 1 life for each creature destroyed this way.", and "Choose a creature type." spells."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import (BEAR, FOREST, OGRE, attack_all, lands, pick, real, run_stack, table, table3,
                           take_turn_attacking)

STORM_HERD = real("Storm Herd", "{8}{W}{W}", "Sorcery", "Create X 1/1 white Pegasus creature tokens with flying, where X is your life "
                  "total.", colors=("W",))
MATCH = real("Match the Odds", "{2}{G}", "Sorcery — Lesson", "Create a 1/1 white Ally creature token. Put a +1/+1 counter on it for "
             "each creature your opponents control.", colors=("G",))
MACHINE = real("One with the Machine", "{3}{U}", "Sorcery", "Draw cards equal to the greatest mana value among artifacts you control.",
               colors=("U",))
THRONE = real("Throne of the God-Pharaoh", "{2}", "Legendary Artifact", "At the beginning of your end step, each opponent loses life "
              "equal to the number of tapped creatures you control.")
DWYNEN = real("Dwynen, Gilt-Leaf Daen", "{2}{G}{G}", "Legendary Creature — Elf Warrior", "Reach (This creature can block creatures with "
              "flying.)\nOther Elf creatures you control get +1/+1.\nWhenever Dwynen attacks, you gain 1 life for each attacking Elf you "
              "control.", "3", "4", colors=("G",))
DREADMAW = real("Earthshaker Dreadmaw", "{4}{G}{G}", "Creature — Dinosaur", "Trample\nWhen this creature enters, draw a card for each "
                "other Dinosaur you control.", "6", "6", colors=("G",))
GRAVE_TROLL = real("Golgari Grave-Troll", "{4}{G}", "Creature — Troll Skeleton", "This creature enters with a +1/+1 counter on it for "
                   "each creature card in your graveyard.\n{1}, Remove a +1/+1 counter from this creature: Regenerate this "
                   "creature.\nDredge 6 (If you would draw a card, you may mill six cards instead. If you do, return this card from "
                   "your graveyard to your hand.)", "0", "0", colors=("G",))
COLOSSUS = real("Diregraf Colossus", "{2}{B}", "Creature — Zombie Giant", "This creature enters with a +1/+1 counter on it for each "
                "Zombie card in your graveyard.\nWhenever you cast a Zombie spell, create a tapped 2/2 black Zombie creature token.",
                "2", "2", colors=("B",))
TRAUMATIZE = real("Traumatize", "{3}{U}{U}", "Sorcery", "Target player mills half their library, rounded down.", colors=("U",))
DESPAIR = real("Force of Despair", "{1}{B}{B}", "Instant", "If it's not your turn, you may exile a black card from your hand rather "
               "than pay this spell's mana cost.\nDestroy all creatures that entered this turn.", colors=("B",))
STROKE = real("Disdainful Stroke", "{1}{U}", "Instant", "Counter target spell with mana value 4 or greater.", colors=("U",))
SCROLL = real("Merchant Scroll", "{1}{U}", "Sorcery", "Search your library for a blue instant card, reveal that card, put it into your "
              "hand, then shuffle.", colors=("U",))
REBIRTH = real("Primevals' Glorious Rebirth", "{5}{W}{B}", "Legendary Sorcery", "(You may cast a legendary sorcery only if you control "
               "a legendary creature or planeswalker.)\nReturn all legendary permanent cards from your graveyard to the battlefield.",
               colors=("B", "W"))
VISIONS = real("Spiteful Visions", "{2}{B/R}{B/R}", "Enchantment", "At the beginning of each player's draw step, that player draws an "
               "additional card.\nWhenever a player draws a card, this enchantment deals 1 damage to that player.", colors=("B", "R"))
VRASKA = real("Vraska Joins Up", "{B}{G}", "Legendary Enchantment", "When Vraska Joins Up enters, put a deathtouch counter on each "
              "creature you control.\nWhenever a legendary creature you control deals combat damage to a player, draw a card.",
              colors=("B", "G"))
HAZARD = real("Tectonic Hazard", "{R}", "Sorcery", "Tectonic Hazard deals 1 damage to each opponent and each creature they control.",
              colors=("R",))
FUMIGATE = real("Fumigate", "{3}{W}{W}", "Sorcery", "Destroy all creatures. You gain 1 life for each creature destroyed this way.",
                colors=("W",))
MELODY = real("Distant Melody", "{3}{U}", "Sorcery", "Choose a creature type. Draw a card for each permanent you control of that type.",
              colors=("U",))
DOMINANCE = real("Kindred Dominance", "{5}{B}{B}", "Sorcery", "Choose a creature type. Destroy all creatures that aren't of the chosen "
                 "type.", colors=("B",))
PALISADE = real("Raise the Palisade", "{4}{U}", "Sorcery", "Choose a creature type. Return all creatures that aren't of the chosen type "
                "to their owners' hands.", colors=("U",))
CARDS = (STORM_HERD, MATCH, MACHINE, THRONE, DWYNEN, DREADMAW, GRAVE_TROLL, COLOSSUS, TRAUMATIZE, DESPAIR, STROKE, SCROLL, REBIRTH,
         VISIONS, VRASKA, HAZARD, FUMIGATE, MELODY, DOMINANCE, PALISADE)

ELF = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))
DINOSAUR = real("Ancient Brontodon", "{6}{G}{G}", "Creature — Dinosaur", "", "9", "9", colors=("G",))
ZOMBIE = real("Walking Corpse", "{1}{B}", "Creature — Zombie", "", "2", "2", colors=("B",))
LEGEND = real("Isamaru, Hound of Konda", "{W}", "Legendary Creature — Dog", "", "2", "2", colors=("W",))
MONOLITH = real("Basalt Monolith", "{3}", "Artifact", "Basalt Monolith doesn't untap during your untap step.\n{T}: Add {C}{C}{C}.")
BLUE = real("Brainstorm", "{U}", "Instant", "Draw three cards, then put two cards from your hand on top of your library in any order.",
            colors=("U",))
RED = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.", colors=("R",))
SOL = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")
INDESTRUCTIBLE = real("Darksteel Myr", "{3}", "Artifact Creature — Myr", "Indestructible", "0", "1")


def cast(game, seat, card):
    seat.battlefield += lands(10)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


def creatures(seat):
    return [p.card.name for p in seat.battlefield if "Creature" in p.card.type_line]


class ParseOnlyBatch5Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_storm_herd_counts_your_life(self):
        game, _ = table3()
        a = game.seats[0]
        a.life = 7
        cast(game, a, STORM_HERD)
        self.assertEqual(creatures(a).count("Pegasus"), 7)

    def test_match_the_odds_counts_only_your_opponents_creatures(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, b.battlefield, c.battlefield = [Permanent(BEAR)], [Permanent(BEAR), Permanent(OGRE)], [Permanent(BEAR)]
        cast(game, a, MATCH)
        ally = next(p for p in a.battlefield if p.card.name == "Ally")
        self.assertEqual(ally.counters.get("+1/+1"), 3)

    def test_one_with_the_machine_draws_the_greatest_mana_value(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 5
        a.battlefield = [Permanent(SOL), Permanent(MONOLITH)]  # mana values 1 and 3: the greatest, not the sum
        cast(game, a, MACHINE)
        self.assertEqual(len(a.hand), 3)

    def test_throne_counts_your_tapped_creatures(self):
        game, _ = table3()
        a, b, c = game.seats
        tapped, untapped = Permanent(BEAR), Permanent(OGRE)
        tapped.tapped = True
        theirs = Permanent(BEAR)
        theirs.tapped = True
        a.battlefield, b.battlefield = [Permanent(THRONE), tapped, untapped], [theirs]
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual((b.life, c.life, a.life), (39, 39, 40))

    def test_dwynen_counts_attacking_elves(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(DWYNEN), Permanent(ELF), Permanent(BEAR)]
        a.library = [FOREST] * 5
        life = a.life
        take_turn_attacking(game, a)
        self.assertEqual(a.life, life + 2)  # Dwynen and the Elf, not the Bear

    def test_earthshaker_dreadmaw_counts_the_other_dinosaurs(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 5
        a.battlefield = [Permanent(DINOSAUR), Permanent(DINOSAUR), Permanent(BEAR)]
        cast(game, a, DREADMAW)
        self.assertEqual(len(a.hand), 2)

    def test_grave_troll_and_colossus_count_the_graveyard_as_they_enter(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [ZOMBIE, ZOMBIE, BEAR, FOREST]
        cast(game, a, GRAVE_TROLL)
        cast(game, a, COLOSSUS)
        troll, colossus = (next(p for p in a.battlefield if p.card.name == n) for n in ("Golgari Grave-Troll", "Diregraf Colossus"))
        self.assertEqual((troll.counters.get("+1/+1"), colossus.counters.get("+1/+1")), (3, 2))

    def test_traumatize_mills_half_rounded_down(self):
        game, _ = table3(pick("Player: B"))
        a, b, _ = game.seats
        b.library = [FOREST] * 7
        cast(game, a, TRAUMATIZE)
        self.assertEqual((len(b.library), len(b.graveyard)), (4, 3))

    def test_force_of_despair_destroys_only_what_entered_this_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        new, old = Permanent(BEAR, entered_turn=game.turn), Permanent(OGRE, entered_turn=game.turn - 1)
        b.battlefield = [new, old]
        cast(game, a, DESPAIR)
        self.assertEqual(creatures(b), ["Ogre"])

    def test_disdainful_stroke_targets_only_mana_value_4_or_greater(self):
        from infernal_machine.game import StackItem
        game, _ = table3()
        a, b, _ = game.seats
        big, small = (StackItem(card, b, []) for card in (DREADMAW, RED))
        game.stack = [big, small]
        from infernal_machine.effects import spell_effects, target_kind
        kind = target_kind(spell_effects(STROKE)[0])  # as the card reads it
        options = [target for _, target in game.target_options(kind, a)]
        self.assertEqual(options, [big])

    def test_merchant_scroll_finds_only_a_blue_instant(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [RED, FOREST, BLUE]
        cast(game, a, SCROLL)
        self.assertEqual([c.name for c in a.hand], ["Brainstorm"])

    def test_primevals_glorious_rebirth_returns_only_legendary_permanents(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(LEGEND)]
        a.graveyard = [LEGEND, BEAR, THRONE]
        cast(game, a, REBIRTH)
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Primevals' Glorious Rebirth"])
        self.assertEqual(sum(p.card.name == "Isamaru, Hound of Konda" for p in a.battlefield), 2)

    def test_spiteful_visions_hurts_whoever_draws(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, b.library = [Permanent(VISIONS)], [FOREST] * 3
        game.draw(b, 2)
        run_stack(game)
        self.assertEqual((b.life, a.life, c.life), (38, 40, 40))

    def test_vraska_joins_up_draws_for_a_legendary_attacker_only(self):
        for attacker, drawn in ((BEAR, 0), (LEGEND, 1)):
            game, _, _ = table(attack_all)
            a = game.seats[0]
            a.battlefield = [Permanent(VRASKA), Permanent(attacker)]
            a.library = [FOREST] * 5
            take_turn_attacking(game, a)
            self.assertEqual(len(a.hand), 1 + drawn, attacker.name)

    def test_tectonic_hazard_spares_you_and_your_creatures(self):
        game, _ = table3()
        a, b, c = game.seats
        mine, theirs = Permanent(ELF), Permanent(ELF)
        a.battlefield, b.battlefield = [mine], [theirs]
        cast(game, a, HAZARD)
        game._check_state()
        self.assertEqual((a.life, b.life, c.life), (40, 39, 39))
        self.assertEqual((creatures(a), creatures(b)), (["Llanowar Elves"], []))

    def test_fumigate_gains_life_for_what_it_destroyed(self):
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(BEAR), Permanent(OGRE), Permanent(INDESTRUCTIBLE)]
        cast(game, a, FUMIGATE)
        self.assertEqual((a.life, creatures(b)), (42, ["Darksteel Myr"]))

    def test_distant_melody_draws_for_the_chosen_type(self):
        game, _ = table3(pick("Elf"))
        a = game.seats[0]
        a.library = [FOREST] * 5
        a.battlefield = [Permanent(ELF), Permanent(DWYNEN), Permanent(BEAR)]
        cast(game, a, MELODY)
        self.assertEqual(len(a.hand), 2)

    def test_kindred_dominance_spares_the_chosen_type(self):
        game, _ = table3(pick("Elf"))
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(ELF), Permanent(BEAR)], [Permanent(ELF), Permanent(OGRE)]
        cast(game, a, DOMINANCE)
        self.assertEqual((creatures(a), creatures(b)), (["Llanowar Elves"], ["Llanowar Elves"]))

    def test_raise_the_palisade_returns_the_others(self):
        game, _ = table3(pick("Elf"))
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(ELF)], [Permanent(OGRE)]
        cast(game, a, PALISADE)
        self.assertEqual((creatures(b), [c.name for c in b.hand]), ([], ["Ogre"]))


if __name__ == "__main__":
    unittest.main()
