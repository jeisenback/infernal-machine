"""Standard's Jeskai Artifacts deck, part two, from its cards' real Oracle text: Pinnacle Starcage (exile all "until this artifact
leaves the battlefield", then put them into graveyards), Repurposing Bay (a search keyed to the sacrificed artifact's mana value),
Simulacrum Synthesizer ("another artifact you control with mana value 3 or greater enters"), The Irencrag (becomes Everflame) and
The Mind Stone (Harness and its ∞ ability)."""

import unittest

from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, COMPARE_BEAR, FOREST, enter, lands, pick, real, run_stack, script, table3

STARCAGE = real("Pinnacle Starcage", "{1}{W}{W}", "Artifact", "When this artifact enters, exile all artifacts and creatures with mana value "
                "2 or less until this artifact leaves the battlefield.\n{6}{W}{W}: Put each card exiled with this artifact into its owner's "
                "graveyard, then create a 2/2 colorless Robot artifact creature token for each card put into a graveyard this way. Sacrifice "
                "this artifact.", colors=("W",))
BAY = real("Repurposing Bay", "{2}{U}", "Artifact", "{2}, {T}, Sacrifice another artifact: Search your library for an artifact card with "
           "mana value equal to 1 plus the sacrificed artifact's mana value, put that card onto the battlefield, then shuffle. Activate "
           "only as a sorcery.", colors=("U",))
SYNTHESIZER = real("Simulacrum Synthesizer", "{2}{U}", "Artifact", "When this artifact enters, scry 2.\nWhenever another artifact you "
                   "control with mana value 3 or greater enters, create a 0/0 colorless Construct artifact creature token with \"This "
                   "token gets +1/+1 for each artifact you control.\"", colors=("U",))
IRENCRAG = real("The Irencrag", "{2}", "Legendary Artifact", "{T}: Add {C}.\nWhenever a legendary creature you control enters, you may "
                "have The Irencrag become a legendary Equipment artifact named Everflame, Heroes' Legacy. If you do, it gains equip {3} and "
                "\"Equipped creature gets +3/+3\" and loses all other abilities.")
MIND_STONE = real("The Mind Stone", "{1}{W}", "Legendary Artifact — Infinity Stone", "Indestructible\n{T}: Add {W}.\n{5}{W}, {T}: Harness "
                  "The Mind Stone. (Once harnessed, its ∞ ability is active.)\n∞ — At the beginning of your end step, exile up to one "
                  "other target nonland permanent you control, then return that card to the battlefield under its owner's control.",
                  colors=("W",))
TRINKET = real("Trinket", "{1}", "Artifact", "")
GADGET = real("Gadget", "{2}", "Artifact", "")
ENGINE = real("Engine", "{3}", "Artifact", "")
HERO = real("Hero", "{1}{W}", "Legendary Creature — Human Soldier", "", "2", "2")


def table(*answers, battlefield=(), library=None, policy=None):
    game, _ = table3(policy or (script(*answers) if answers else None))
    a, b, c = game.seats
    a.battlefield = list(battlefield)
    for seat in game.seats:
        seat.library = list(library) if library is not None else [FOREST] * 6
    return game, a, b, c


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


def names(seat, zone="battlefield"):
    cards = [p.card for p in seat.battlefield] if zone == "battlefield" else getattr(seat, zone)
    return sorted(c.name for c in cards if "Land" not in c.type_line)


class StandardJeskaiArtifactsTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (STARCAGE, BAY, SYNTHESIZER, IRENCRAG, MIND_STONE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_pinnacle_starcage_exiles_the_cheap_artifacts_and_creatures_until_it_leaves(self):
        game, a, b, _ = table(battlefield=lands(3) + [Permanent(BIG)])
        b.battlefield = [Permanent(COMPARE_BEAR), Permanent(TRINKET), Permanent(ENGINE)]
        a.hand = [STARCAGE]
        game._perform(a, CAST + STARCAGE.name)
        run_stack(game)
        self.assertEqual((names(a), names(b)), (["Big", "Pinnacle Starcage"], ["Engine"]))
        self.assertEqual(names(b, "exile"), ["Grizzly Bears", "Trinket"])
        game.destroy(next(p for p in a.battlefield if p.card is STARCAGE))
        run_stack(game)
        self.assertEqual(names(b), ["Engine", "Grizzly Bears", "Trinket"])

    def test_pinnacle_starcage_puts_what_it_holds_into_graveyards_and_makes_robots(self):
        cage = Permanent(STARCAGE)
        game, a, b, _ = table(battlefield=lands(8) + [cage])
        b.battlefield = [Permanent(COMPARE_BEAR), Permanent(TRINKET)]
        game.trigger("enters", cage, a)
        run_stack(game)
        game._perform(a, offered(game, a, ACTIVATE + "Pinnacle Starcage")[0])
        run_stack(game)
        self.assertEqual((names(a), names(a, "graveyard")), (["Robot", "Robot"], ["Pinnacle Starcage"]))
        self.assertEqual((names(b), names(b, "graveyard"), b.exile), ([], ["Grizzly Bears", "Trinket"], []))

    def test_repurposing_bay_finds_an_artifact_one_mana_value_above_the_sacrificed_one(self):
        game, a, _, _ = table("Trinket", policy=pick("Trinket", "Gadget"), battlefield=lands(2) + [Permanent(BAY), Permanent(TRINKET)],
                              library=[ENGINE, GADGET, TRINKET])
        game._perform(a, offered(game, a, ACTIVATE + "Repurposing Bay")[0])
        run_stack(game)
        self.assertEqual(names(a), ["Gadget", "Repurposing Bay"])
        self.assertEqual(sorted(c.name for c in a.library), ["Engine", "Trinket"])

    def test_repurposing_bay_needs_another_artifact(self):
        game, a, _, _ = table(battlefield=lands(2) + [Permanent(BAY), Permanent(BEAR)])
        self.assertEqual(offered(game, a, ACTIVATE + "Repurposing Bay"), [])

    def test_simulacrum_synthesizer_makes_a_construct_for_its_controllers_big_artifacts_only(self):
        game, a, b, _ = table(battlefield=[Permanent(SYNTHESIZER)])
        enter(game, a, GADGET)  # mana value 2
        enter(game, b, ENGINE)  # an opponent's
        run_stack(game)
        self.assertEqual(names(a), ["Gadget", "Simulacrum Synthesizer"])
        enter(game, a, ENGINE)
        run_stack(game)
        construct = next(p for p in a.battlefield if p.card.name == "Construct")
        self.assertEqual(game.power(construct), 4)  # the Synthesizer, the Gadget, the Engine and itself

    def test_the_irencrag_becomes_everflame_when_a_legendary_creature_enters(self):
        crag = Permanent(IRENCRAG)
        game, a, _, _ = table(policy=pick("Yes", "Hero"), battlefield=lands(3) + [crag])
        self.assertIn(crag, [m.permanent for m in game._mana_sources(a)])
        enter(game, a, BEAR)  # not legendary
        run_stack(game)
        self.assertEqual(crag.card.name, "The Irencrag")
        hero = enter(game, a, HERO)
        run_stack(game)
        self.assertEqual((crag.card.name, crag.card.type_line), ("Everflame, Heroes' Legacy", "Legendary Artifact — Equipment"))
        self.assertNotIn(crag, [m.permanent for m in game._mana_sources(a)])  # its mana ability is gone
        game._perform(a, offered(game, a, ACTIVATE + "Everflame")[0])
        run_stack(game)
        self.assertEqual((crag.attached_to, game.power(hero)), (hero, 5))
        game.destroy(crag)
        run_stack(game)
        self.assertEqual(names(a, "graveyard"), ["The Irencrag"])

    def test_the_mind_stone_flickers_only_once_harnessed(self):
        stone, bear = Permanent(MIND_STONE), Permanent(BEAR, counters={"+1/+1": 1})
        game, a, _, _ = table(policy=pick("Bear"), battlefield=lands(6) + [stone, bear])
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertIn(bear, a.battlefield)
        game._perform(a, offered(game, a, ACTIVATE + "The Mind Stone (seat 0, #7): {5}{W}")[0])
        run_stack(game)
        self.assertTrue(stone.harnessed)
        game._turn_based_actions(a)
        run_stack(game)
        self.assertNotIn(bear, a.battlefield)  # it came back as a new object, without its counter
        self.assertEqual([p.counters for p in a.battlefield if p.card is BEAR], [{}])

    def test_the_mind_stones_infinity_ability_may_leave_out_its_target(self):
        stone, bear = Permanent(MIND_STONE, harnessed=True), Permanent(BEAR)
        game, a, _, _ = table(policy=pick("No target"), battlefield=[stone, bear])
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertIn(bear, a.battlefield)


if __name__ == "__main__":
    unittest.main()
