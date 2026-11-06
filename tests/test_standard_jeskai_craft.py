"""Standard's Jeskai Artifacts deck, part one, from its cards' real Oracle text: Craft (Braided Net, Clay-Fired Bricks, Spring-Loaded
Sawblades and their back faces), Cryogen Relic ("enters or leaves the battlefield"; a stun counter) and Perilous Snare (Max speed)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, fire, lands, real, run_stack, script, table3

QUIPU = Card(name="Braided Quipu", type_line="Artifact", colors=("U",),
             oracle_text="{3}{U}, {T}: Draw a card for each artifact you control, then put this artifact into its owner's library third from "
                         "the top.")
NET = Card(name="Braided Net // Braided Quipu", mana_cost="{2}{U}", cmc=3.0, type_line="Artifact", colors=("U",), flip=QUIPU,
           oracle_text="This artifact enters with three net counters on it.\n{T}, Remove a net counter from this artifact: Tap another target "
                       "nonland permanent. Its activated abilities can't be activated for as long as it remains tapped.\nCraft with artifact "
                       "{1}{U}")
KILN = Card(name="Cosmium Kiln", type_line="Artifact", colors=("W",),
            oracle_text="When this artifact enters, create two 1/1 colorless Gnome artifact creature tokens.\nCreatures you control get +1/+1.")
BRICKS = Card(name="Clay-Fired Bricks // Cosmium Kiln", mana_cost="{1}{W}", cmc=2.0, type_line="Artifact", colors=("W",), flip=KILN,
              oracle_text="When this artifact enters, search your library for a basic Plains card, reveal it, put it into your hand, then "
                          "shuffle. You gain 2 life.\nCraft with artifact {5}{W}{W} ({5}{W}{W}, Exile this artifact, Exile another artifact "
                          "you control or an artifact card from your graveyard: Return this card transformed under its owner's control. "
                          "Craft only as a sorcery.)")
CHARIOT = Card(name="Bladewheel Chariot", type_line="Artifact — Vehicle", colors=("W",), power="5", toughness="5",
               oracle_text="Tap two other untapped artifacts you control: This Vehicle becomes an artifact creature until end of turn.\nCrew 1 "
                           "(Tap any number of creatures you control with total power 1 or more: This Vehicle becomes an artifact creature "
                           "until end of turn.)")
SAWBLADES = Card(name="Spring-Loaded Sawblades // Bladewheel Chariot", mana_cost="{1}{W}", cmc=2.0, type_line="Artifact", colors=("W",),
                 flip=CHARIOT,
                 oracle_text="Flash\nWhen this artifact enters, it deals 5 damage to target tapped creature an opponent controls.\nCraft with "
                             "artifact {3}{W} ({3}{W}, Exile this artifact, Exile another artifact you control or an artifact card from your "
                             "graveyard: Return this card transformed under its owner's control. Craft only as a sorcery.)")
RELIC = real("Cryogen Relic", "{1}{U}", "Artifact", "When this artifact enters or leaves the battlefield, draw a card.\n{1}{U}, Sacrifice this "
             "artifact: Put a stun counter on up to one target tapped creature. (If a permanent with a stun counter would become untapped, "
             "remove one from it instead.)", colors=("U",))
SNARE = real("Perilous Snare", "{2}{W}", "Artifact", "Start your engines! (If you have no speed, it starts at 1. It increases once on each of "
             "your turns when an opponent loses life. Max speed is 4.)\nWhen this artifact enters, exile target nonland permanent an opponent "
             "controls until this artifact leaves the battlefield.\nMax speed — {T}: Put a +1/+1 counter on target creature or Vehicle you "
             "control. Activate only as a sorcery.", colors=("W",))
TRINKET = real("Trinket", "{1}", "Artifact", "")
MIND_STONE = real("Mind Stone", "{2}", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.")
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
TEMPLE = Card(name="Holy Ground", type_line="Land — Plains", produced_mana=("W",))
TRUCK = real("Truck", "{2}", "Artifact — Vehicle", "Crew 3", "4", "4")


def table(*answers, battlefield=(), hand=(), graveyard=(), library=None):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield, a.hand, a.graveyard = list(battlefield), list(hand), list(graveyard)
    for seat in game.seats:
        seat.library = list(library) if library is not None else [FOREST] * 6
    return game, a, b, c


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


class StandardJeskaiCraftTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (NET, QUIPU, BRICKS, KILN, SAWBLADES, CHARIOT, RELIC, SNARE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_crafting_exiles_another_artifact_and_returns_the_card_transformed(self):
        bricks = Permanent(BRICKS)
        game, a, _, _ = table("Trinket", battlefield=lands(7) + [bricks, Permanent(TRINKET)])
        game._perform(a, offered(game, a, ACTIVATE + "Clay-Fired Bricks")[0])
        run_stack(game)
        self.assertEqual(names(a), ["Cosmium Kiln", "Gnome", "Gnome"])
        self.assertEqual([c.name for c in a.exile], ["Trinket"])
        gnome = next(p for p in a.battlefield if p.card.name == "Gnome")
        self.assertEqual(game.power(gnome), 2)  # Creatures you control get +1/+1

    def test_crafting_can_exile_an_artifact_card_from_the_graveyard(self):
        game, a, _, _ = table("Trinket", battlefield=lands(7) + [Permanent(BRICKS)], graveyard=[TRINKET])
        game._perform(a, offered(game, a, ACTIVATE + "Clay-Fired Bricks")[0])
        run_stack(game)
        self.assertEqual((names(a)[0], a.graveyard, a.exile), ("Cosmium Kiln", [], [TRINKET]))

    def test_a_crafted_card_that_left_exile_does_not_return(self):
        game, a, _, _ = table("Trinket", battlefield=lands(7) + [Permanent(BRICKS), Permanent(TRINKET)])
        game._perform(a, offered(game, a, ACTIVATE + "Clay-Fired Bricks")[0])
        a.exile.remove(BRICKS)  # gone from exile before the ability resolves
        a.hand.append(BRICKS)
        run_stack(game)
        self.assertEqual(names(a), [])

    def test_crafting_needs_another_artifact(self):
        game, a, _, _ = table(battlefield=lands(7) + [Permanent(BRICKS)], graveyard=[BEAR])
        self.assertEqual(offered(game, a, ACTIVATE + "Clay-Fired Bricks"), [])

    def test_clay_fired_bricks_finds_a_basic_plains_and_gains_two_life(self):
        game, a, _, _ = table(battlefield=lands(2), hand=[BRICKS], library=[TEMPLE, PLAINS, FOREST])
        life = a.life
        game._perform(a, CAST + BRICKS.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], a.life), (["Plains"], life + 2))

    def test_spring_loaded_sawblades_hits_only_a_tapped_creature_an_opponent_controls(self):
        game, a, b, _ = table("Ogre", battlefield=lands(2), hand=[SAWBLADES])
        tapped, untapped = Permanent(OGRE, tapped=True), Permanent(BEAR)
        b.battlefield = [untapped, tapped]
        game._perform(a, CAST + SAWBLADES.name)
        run_stack(game)
        game._check_state()
        self.assertEqual(b.battlefield, [untapped])

    def test_bladewheel_chariot_becomes_a_creature_by_tapping_two_other_artifacts(self):
        chariot, first, second = Permanent(CHARIOT), Permanent(TRINKET), Permanent(TRINKET)
        game, a, _, _ = table(battlefield=[chariot, first, Permanent(BEAR)])  # a creature is not an artifact
        self.assertEqual(offered(game, a, ACTIVATE + "Bladewheel Chariot (seat 0, #1): Tap two"), [])
        a.battlefield.append(second)
        game._perform(a, offered(game, a, ACTIVATE + "Bladewheel Chariot (seat 0, #1): Tap two")[0])
        run_stack(game)
        self.assertEqual((first.tapped, second.tapped, "Creature" in chariot.card.type_line), (True, True, True))

    def test_braided_net_taps_a_permanent_whose_abilities_wait_until_it_untaps(self):
        net, stone = Permanent(NET, counters={"net": 3}), Permanent(MIND_STONE)
        game, a, b, _ = table("Mind Stone", battlefield=[net])
        b.battlefield = [stone] + lands(1)
        game._perform(a, offered(game, a, ACTIVATE + "Braided Net")[0])
        run_stack(game)
        self.assertEqual((stone.tapped, net.counters["net"]), (True, 2))
        self.assertTrue(game._ability_barred(stone, mana=True))
        game.untap(stone)
        self.assertFalse(game._ability_barred(stone))
        stone.tapped = True  # tapped again by its own ability: no longer under the Net
        self.assertFalse(game._ability_barred(stone))

    def test_braided_quipu_draws_for_each_artifact_then_goes_third_from_the_top(self):
        quipu = Permanent(QUIPU)
        game, a, _, _ = table(battlefield=lands(4) + [quipu, Permanent(TRINKET)], library=[FOREST] * 6)
        game._perform(a, offered(game, a, ACTIVATE + "Braided Quipu")[0])
        run_stack(game)
        self.assertEqual((len(a.hand), a.library.index(QUIPU)), (2, 2))
        self.assertNotIn(quipu, a.battlefield)

    def test_cryogen_relic_draws_on_entering_and_leaving_and_stuns_a_tapped_creature(self):
        game, a, b, _ = table("Ogre", battlefield=lands(4), hand=[RELIC])
        tapped = Permanent(OGRE, tapped=True)
        b.battlefield = [Permanent(BEAR), tapped]
        game._perform(a, CAST + "Cryogen Relic")
        run_stack(game)
        self.assertEqual(len(a.hand), 1)
        game._perform(a, offered(game, a, ACTIVATE + "Cryogen Relic")[0])
        run_stack(game)
        self.assertEqual((len(a.hand), tapped.counters.get("stun")), (2, 1))

    def test_perilous_snare_counters_a_creature_or_vehicle_only_at_max_speed(self):
        snare, truck = Permanent(SNARE), Permanent(TRUCK)
        game, a, _, _ = table("Truck", battlefield=[snare, truck])
        a.speed = 3
        self.assertEqual(offered(game, a, ACTIVATE + "Perilous Snare"), [])
        a.speed = 4
        game._perform(a, offered(game, a, ACTIVATE + "Perilous Snare")[0])
        run_stack(game)
        self.assertEqual(truck.counters.get("+1/+1"), 1)


if __name__ == "__main__":
    unittest.main()
