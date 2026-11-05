"""Standard's removal and lands, from their real Oracle text: Get Lost, Charring Bite ("target creature without flying"), Vibrant Outburst
("Tap up to one target creature."), Shoot the Sheriff ("non-outlaw"), Settle the Wreckage, Soulstone Sanctuary and Great Hall of the
Biblioplex (lands that become creatures for good), Mistrise Village (the next spell can't be countered) and Demolition Field."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIRD, FOREST, attack_all, end_turn, lands, pick, real, run_stack, script, table3

GET_LOST = real("Get Lost", "{1}{W}", "Instant", "Destroy target creature, enchantment, or planeswalker. Its controller creates two Map tokens. "
                "(They're artifacts with \"{1}, {T}, Sacrifice this token: Target creature you control explores. Activate only as a sorcery.\")",
                colors=("W",))
CHARRING_BITE = real("Charring Bite", "{1}{R}", "Sorcery — Omen", "Charring Bite deals 5 damage to target creature without flying. (Then "
                     "shuffle this card into its owner's library.)", colors=("R",))
OUTBURST = real("Vibrant Outburst", "{U}{R}", "Instant", "Vibrant Outburst deals 3 damage to any target. Tap up to one target creature.",
                colors=("U", "R"))
SHERIFF = real("Shoot the Sheriff", "{1}{B}", "Instant", "Destroy target non-outlaw creature. (Assassins, Mercenaries, Pirates, Rogues, and "
               "Warlocks are outlaws. Everyone else is fair game.)", colors=("B",))
SETTLE = real("Settle the Wreckage", "{2}{W}{W}", "Instant", "Exile all attacking creatures target player controls. That player may search "
              "their library for that many basic land cards, put those cards onto the battlefield tapped, then shuffle.", colors=("W",))
GREAT_HALL = real("Great Hall of the Biblioplex", "", "Land", "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
                  "to cast an instant or sorcery spell.\n{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with \"Whenever "
                  "you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.\" It's still a land.")
SOULSTONE = real("Soulstone Sanctuary", "", "Land", "{T}: Add {C}.\n{4}: This land becomes a 3/3 creature with vigilance and all creature "
                 "types. It's still a land.")
MISTRISE = real("Mistrise Village", "", "Land", "This land enters tapped unless you control a Mountain or a Forest.\n{T}: Add {U}.\n{U}, {T}: "
                "The next spell you cast this turn can't be countered.")
DEMOLITION = real("Demolition Field", "", "Land", "{T}: Add {C}.\n{2}, {T}, Sacrifice this land: Destroy target nonbasic land an opponent "
                  "controls. That land's controller may search their library for a basic land card, put it onto the battlefield, then "
                  "shuffle. You may search your library for a basic land card, put it onto the battlefield, then shuffle.")
ROGUE = Card(name="Rogue", type_line="Creature — Human Rogue", power="2", toughness="2")
KNIGHT = Card(name="Knight", type_line="Creature — Human Knight", power="2", toughness="2")
RELIC = Card(name="Relic", type_line="Artifact", mana_cost="{1}", cmc=1.0)
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
NONBASIC = Card(name="Nonbasic", type_line="Land", produced_mana=("C",))


def table(*answers, card=None, n=4):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield = lands(n)
    if card is not None:
        a.hand = [card]
    for seat in game.seats:
        seat.library = [FOREST] * 5
    return game, a, b, c


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


class StandardRemovalAndLandsTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GET_LOST, CHARRING_BITE, OUTBURST, SHERIFF, SETTLE, GREAT_HALL, SOULSTONE, MISTRISE, DEMOLITION):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_get_lost_destroys_a_creature_and_gives_its_controller_two_maps(self):
        game, a, b, _ = table("Bear", card=GET_LOST)
        b.battlefield = [Permanent(BEAR), Permanent(RELIC)]
        game._perform(a, CAST + "Get Lost")
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Map", "Map", "Relic"])

    def test_get_lost_cannot_target_an_artifact(self):
        game, a, b, _ = table(card=GET_LOST)
        b.battlefield = [Permanent(RELIC)]
        self.assertEqual(offered(game, a, CAST + "Get Lost"), [])

    def test_charring_bite_hits_a_creature_without_flying_only(self):
        game, a, b, _ = table("Bird", "Bear", card=CHARRING_BITE)  # the Bird is offered first if it can be
        bear, bird = Permanent(BEAR), Permanent(BIRD)
        b.battlefield = [bird, bear]
        game._perform(a, CAST + "Charring Bite")
        run_stack(game)
        game._check_state()
        self.assertEqual((bear in b.battlefield, bird in b.battlefield), (False, True))

    def test_vibrant_outburst_damages_and_may_tap_a_creature(self):
        game, a, b, _ = table("Player: B", "Bear", card=OUTBURST)
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game._perform(a, CAST + "Vibrant Outburst")
        run_stack(game)
        self.assertEqual((b.life, bear.tapped), (37, True))
        game, a, b, _ = table("Player: B", "No target", card=OUTBURST)
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game._perform(a, CAST + "Vibrant Outburst")
        run_stack(game)
        self.assertEqual((b.life, bear.tapped), (37, False))

    def test_shoot_the_sheriff_spares_an_outlaw(self):
        game, a, b, _ = table("Rogue", "Knight", card=SHERIFF)
        b.battlefield = [Permanent(ROGUE), Permanent(KNIGHT)]
        game._perform(a, CAST + "Shoot the Sheriff")
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Rogue"])

    def test_settle_the_wreckage_exiles_the_attackers_and_gives_basic_lands(self):
        game, _ = table3(pick("Player: B"), attack_all)  # B attacks with everything, then says yes to the search
        a, b, _ = game.seats
        game.active = 1
        attackers = [Permanent(BEAR), Permanent(KNIGHT)]
        home = Permanent(ROGUE, sick=True)
        b.battlefield, b.library = attackers + [home], [FOREST] * 5
        game.combat.declare_attackers(b)
        a.battlefield, a.hand = lands(4), [SETTLE]
        game._perform(a, CAST + "Settle the Wreckage")
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Forest", "Forest", "Rogue"])
        self.assertTrue(all(p.tapped for p in b.battlefield if p.card.name == "Forest"))
        self.assertEqual(sorted(c.name for c in b.exile), ["Bear", "Knight"])

    def test_settle_the_wreckage_on_a_player_who_is_not_attacking_does_nothing(self):
        game, _ = table3(pick("Player: C"), attack_all)
        a, b, c = game.seats
        game.active = 1
        b.battlefield = [Permanent(BEAR)]
        game.combat.declare_attackers(b)
        c.battlefield = [Permanent(KNIGHT)]
        a.battlefield, a.hand = lands(4), [SETTLE]
        game._perform(a, CAST + "Settle the Wreckage")
        run_stack(game)
        self.assertEqual(([p.card.name for p in b.battlefield], [p.card.name for p in c.battlefield]), (["Bear"], ["Knight"]))

    def test_settle_the_wreckage_lets_the_player_decline_the_lands(self):
        game, _ = table3(pick("Player: B"), lambda prompt, options: 1 if options == ["Yes", "No"] else attack_all(prompt, options))
        a, b, _ = game.seats
        game.active = 1
        b.battlefield, b.library = [Permanent(BEAR)], [FOREST] * 5
        game.combat.declare_attackers(b)
        a.battlefield, a.hand = lands(4), [SETTLE]
        game._perform(a, CAST + "Settle the Wreckage")
        run_stack(game)
        self.assertEqual((b.battlefield, len(b.library)), ([], 5))

    def test_soulstone_sanctuary_stays_a_creature(self):
        game, a, _, _ = table()
        land = Permanent(SOULSTONE)
        a.battlefield.append(land)
        game._perform(a, next(x for x in offered(game, a, ACTIVATE + "Soulstone Sanctuary") if "{4}" in x))
        run_stack(game)
        end_turn(game, a)
        self.assertEqual((land.card.type_line, game.power(land), game.has_keyword(land, "vigilance")), ("Land Creature", 3, True))

    def test_great_hall_becomes_a_wizard_that_grows_with_instants(self):
        game, a, _, _ = table(n=6)
        hall = Permanent(GREAT_HALL)
        a.battlefield.append(hall)
        game._perform(a, next(x for x in offered(game, a, ACTIVATE + "Great Hall") if "{5}" in x))
        run_stack(game)
        end_turn(game, a)
        self.assertEqual((hall.card.type_line, game.power(hall), game.toughness(hall)), ("Land Creature — Wizard", 2, 4))
        game.step = "main1"
        for land in a.battlefield:
            land.tapped = False
        a.hand = [OPT]
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual(game.power(hall), 3)

    def test_great_hall_does_nothing_while_it_is_a_creature(self):
        game, a, _, _ = table(n=10)
        hall = Permanent(GREAT_HALL)
        a.battlefield.append(hall)
        for _ in range(2):
            game._perform(a, next(x for x in offered(game, a, ACTIVATE + "Great Hall") if "{5}" in x))
            run_stack(game)
        self.assertEqual(hall.card.oracle_text.count("Whenever you cast"), 2)  # its own text and the one it gained: not a second copy

    def test_mistrise_village_makes_only_the_next_spell_uncounterable(self):
        game, a, _, _ = table()
        a.battlefield.append(Permanent(MISTRISE))
        game._perform(a, next(x for x in offered(game, a, ACTIVATE + "Mistrise Village")))
        run_stack(game)
        a.hand = [OPT, OPT]
        game._perform(a, CAST + "Opt")
        self.assertTrue(game.stack[-1].cant_be_countered)
        run_stack(game)
        game._perform(a, CAST + "Opt")
        self.assertFalse(game.stack[-1].cant_be_countered)

    def test_demolition_field_destroys_a_nonbasic_land_and_both_fetch_a_basic(self):
        game, a, b, _ = table("Nonbasic", "Yes", "Forest", "Forest")
        a.battlefield.append(Permanent(DEMOLITION))
        b.battlefield = [Permanent(NONBASIC), Permanent(FOREST)]
        game._perform(a, next(x for x in offered(game, a, ACTIVATE + "Demolition Field")))
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Forest", "Forest"])
        self.assertEqual(sum(p.card.name == "Forest" for p in a.battlefield), 1)
        self.assertNotIn("Demolition Field", [p.card.name for p in a.battlefield])


if __name__ == "__main__":
    unittest.main()
