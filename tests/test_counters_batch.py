"""Counters on permanents, batch 1, from the cards' real Oracle text: Drana's counters on each attacking creature, Archfiend of Ifnir's -1/-1
counter on each creature the opponents control, Herald of Secret Streams' "Creatures you control with +1/+1 counters on them can't be
blocked.", Wave Goodbye's "each creature without a +1/+1 counter on it", Mondrak's "Sacrifice two other artifacts and/or creatures",
Elspeth, Storm Slayer's flying "until your next turn", Persist's "nonlegendary creature card ... with a -1/-1 counter on it", Scavenging
Ooze's "If it was a creature card, ..." and Slip Out the Back's "It phases out."."""

import unittest

from infernal_machine.combat import Attack
from infernal_machine.effects.common import CANT_BE_BLOCKED
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, activate, attack_all, lands, pick, real, run_stack, table, table3, take_turn_attacking

DRANA = real("Drana, Liberator of Malakir", "{1}{B}{B}", "Legendary Creature — Vampire Ally", "Flying, first strike\nWhenever Drana deals "
             "combat damage to a player, put a +1/+1 counter on each attacking creature you control.", "2", "3", colors=("B",))
ARCHFIEND = real("Archfiend of Ifnir", "{3}{B}{B}", "Creature — Demon", "Flying\nWhenever you cycle or discard another card, put a -1/-1 "
                 "counter on each creature your opponents control.\nCycling {2} ({2}, Discard this card: Draw a card.)", "5", "4", colors=("B",))
HERALD = real("Herald of Secret Streams", "{3}{U}", "Creature — Merfolk Warrior", "Creatures you control with +1/+1 counters on them can't be "
              "blocked.", "2", "3", colors=("U",))
WAVE = real("Wave Goodbye", "{2}{U}{U}", "Sorcery", "Return each creature without a +1/+1 counter on it to its owner's hand.", colors=("U",))
MONDRAK = real("Mondrak, Glory Dominus", "{2}{W}{W}", "Legendary Creature — Phyrexian Horror", "If one or more tokens would be created under "
               "your control, twice that many of those tokens are created instead.\n{1}{W/P}{W/P}, Sacrifice two other artifacts and/or "
               "creatures: Put an indestructible counter on Mondrak. ({W/P} can be paid with either {W} or 2 life.)", "4", "4", colors=("W",))
ELSPETH = real("Elspeth, Storm Slayer", "{3}{W}{W}", "Legendary Planeswalker — Elspeth", "If one or more tokens would be created under your "
               "control, twice that many of those tokens are created instead.\n+1: Create a 1/1 white Soldier creature token.\n0: Put a +1/+1 "
               "counter on each creature you control. Those creatures gain flying until your next turn.\n−3: Destroy target creature an "
               "opponent controls with mana value 3 or greater.", colors=("W",))
PERSIST = real("Persist", "{1}{B}", "Sorcery", "Return target nonlegendary creature card from your graveyard to the battlefield with a -1/-1 "
               "counter on it.", colors=("B",))
OOZE = real("Scavenging Ooze", "{1}{G}", "Creature — Ooze", "{G}: Exile target card from a graveyard. If it was a creature card, put a +1/+1 "
            "counter on this creature and you gain 1 life.", "2", "2", colors=("G",))
SLIP = real("Slip Out the Back", "{U}", "Instant", "Put a +1/+1 counter on target creature. It phases out. (Treat it and anything attached to "
            "it as though they don't exist until its controller's next turn.)", colors=("U",))
CARDS = (DRANA, ARCHFIEND, HERALD, WAVE, MONDRAK, ELSPETH, PERSIST, OOZE, SLIP)

WALL = real("Wall of Wood", "{G}", "Creature — Wall", "Defender (This creature can't attack.)", "0", "3", colors=("G",))
TITANIA = real("Titania, Protector of Argoth", "{3}{G}{G}", "Legendary Creature — Elemental", "When Titania enters, return target land card "
               "from your graveyard to the battlefield.\nWhenever a land you control is put into a graveyard from the battlefield, create a "
               "5/3 green Elemental creature token.", "5", "3", colors=("G",))


def cast(game, seat, card, n=6):
    seat.battlefield += lands(n)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


class CountersBatchTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_drana_puts_counters_on_the_attackers_only(self):
        game, _, _ = table(lambda prompt, options: attack_all(prompt, options) if any("ttack" in o for o in options) else 0)
        a = game.seats[0]
        drana, bear, home = Permanent(DRANA), Permanent(BEAR), Permanent(WALL)  # the Wall can't attack: it stays home
        a.battlefield = [drana, bear, home]
        take_turn_attacking(game, a)
        self.assertEqual((drana.counters.get("+1/+1"), bear.counters.get("+1/+1"), home.counters.get("+1/+1")), (1, 1, None))

    def test_archfiend_of_ifnir_shrinks_the_opponents_creatures_on_a_discard(self):
        game, _ = table3()
        a, b, c = game.seats
        theirs, other, mine = Permanent(OGRE), Permanent(BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield, c.battlefield = [Permanent(ARCHFIEND), mine], [theirs], [other]
        a.hand = [FOREST]
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual((theirs.counters.get("-1/-1"), other.counters.get("-1/-1"), mine.counters.get("-1/-1")), (1, 1, None))

    def test_herald_makes_only_the_creatures_with_counters_unblockable(self):
        game, _ = table3()
        a = game.seats[0]
        grown, plain = Permanent(BEAR), Permanent(BEAR)
        grown.counters["+1/+1"] = 1
        a.battlefield = [Permanent(HERALD), grown, plain]
        self.assertEqual((game.has_keyword(grown, CANT_BE_BLOCKED), game.has_keyword(plain, CANT_BE_BLOCKED)), (True, False))

    def test_a_herald_creature_with_a_counter_cant_be_blocked(self):
        game, _ = table3()
        a, b, _ = game.seats
        grown = Permanent(BEAR, sick=False)
        grown.counters["+1/+1"] = 1
        blocker = Permanent(OGRE)
        a.battlefield, b.battlefield = [Permanent(HERALD), grown], [blocker]
        game.combat.attacks = [Attack(grown, a, b)]
        self.assertFalse(game.combat._can_block(blocker, grown))
        self.assertTrue(game.combat._can_block(blocker, Permanent(BEAR)))

    def test_wave_goodbye_spares_the_creatures_with_a_counter(self):
        game, _ = table3()
        a, b, _ = game.seats
        grown, plain, other = Permanent(BEAR), Permanent(BEAR), Permanent(OGRE)
        grown.counters["+1/+1"] = 1
        other.counters["-1/-1"] = 1  # another kind of counter does not spare it
        a.battlefield, b.battlefield = [grown, plain], [other]
        cast(game, a, WAVE)
        self.assertEqual((grown in a.battlefield, plain in a.battlefield, other in b.battlefield), (True, False, False))

    def test_mondrak_sacrifices_two_others_for_an_indestructible_counter(self):
        for others, offered in (([RELIC, BEAR], True), ([RELIC], False)):
            game, _ = table3(pick("Relic", "Bear"))
            a = game.seats[0]
            mondrak = Permanent(MONDRAK)
            a.battlefield = [mondrak] + [Permanent(c) for c in others] + lands(3)
            abilities = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Mondrak" in x]
            self.assertEqual(bool(abilities), offered, len(others))
            if offered:
                activate(game, a, "Mondrak")
                self.assertEqual((mondrak.counters.get("indestructible"), [p.card.name for p in a.battlefield if p.card in (RELIC, BEAR)]),
                                 (1, []))

    def test_elspeth_gives_flying_until_your_next_turn(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(ELSPETH, loyalty=5), bear]
        activate(game, a, "0: Put a +1/+1 counter")
        self.assertEqual((bear.counters.get("+1/+1"), game.has_keyword(bear, "flying")), (1, True))
        self.assertTrue(any("flying" in m.keywords for m in bear.until_next_turn))  # it lasts past this turn's end

    def test_persist_returns_only_a_nonlegendary_creature_with_a_minus_counter(self):
        offered = []

        def policy(prompt, options):
            offered.append(list(options))
            return 0
        game, _ = table3(policy)
        a = game.seats[0]
        a.graveyard = [TITANIA, OGRE]
        cast(game, a, PERSIST)
        ogre = next(p for p in a.battlefield if p.card is OGRE)
        self.assertEqual(ogre.counters.get("-1/-1"), 1)
        self.assertFalse(any(any("Titania" in o for o in options) for options in offered))

    def test_scavenging_ooze_grows_only_for_a_creature_card(self):
        for card, grown in ((OGRE, True), (FOREST, False)):
            game, _ = table3(pick("Ogre", "Forest"))
            a, b, _ = game.seats
            ooze = Permanent(OOZE)
            a.battlefield, b.graveyard = [ooze] + lands(1), [card]
            activate(game, a, "Exile target card")
            self.assertEqual((b.graveyard, ooze.counters.get("+1/+1"), a.life), ([], 1 if grown else None, 41 if grown else 40), card.name)

    def test_slip_out_the_back_counters_then_phases_out(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        cast(game, a, SLIP, n=1)
        self.assertEqual((bear.counters.get("+1/+1"), bear in a.battlefield), (1, False))  # phased out: treated as though it doesn't exist


if __name__ == "__main__":
    unittest.main()
