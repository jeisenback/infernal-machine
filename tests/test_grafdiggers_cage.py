""""Creature cards in graveyards and libraries can't enter the battlefield. Players can't cast spells from graveyards or libraries."
(Grafdigger's Cage): each way a card leaves a graveyard or library for the battlefield or the stack, with and without the Cage."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST_DISTURB, UNEARTH, GraveyardTarget, Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.zones import CAST_GRAVEYARD, CAST_MILLED, CAST_PARAGON, CAST_PERMIT, CAST_TOP, PLAY_PARAGON
from tests.helpers import BEAR, FOREST, RELIC, enter, lands, real, run_stack, scryfall, table3

CAGE = real("Grafdigger's Cage", "{1}", "Artifact", "Creature cards in graveyards and libraries can't enter the battlefield.\nPlayers can't "
            "cast spells from graveyards or libraries.")
THINK_TWICE = real("Think Twice", "{1}{U}", "Instant", "Draw a card.\nFlashback {2}{U} (You may cast this card from your graveyard for its "
                   "flashback cost. Then exile it.)", colors=("U",))
PARAGON = real("Serra Paragon", "{2}{W}{W}", "Creature — Angel", "Flying\nOnce during each of your turns, you may play a land from your "
               "graveyard or cast a permanent spell with mana value 3 or less from your graveyard. If you do, it gains \"When this "
               "permanent is put into a graveyard from the battlefield, exile it and you gain 2 life.\"", "3", "4", colors=("W",))
GISA = real("Gisa and Geralf", "{2}{U}{B}", "Legendary Creature — Human Wizard", "When Gisa and Geralf enters, mill four cards.\nOnce "
            "during each of your turns, you may cast a Zombie creature spell from your graveyard.", "4", "4", colors=("U", "B"))
ZOMBIE = real("Dregscape Zombie", "{1}{B}", "Creature — Zombie", "Unearth {B} ({B}: Return this card from your graveyard to the "
              "battlefield. It gains haste. Exile it at the beginning of the next end step or if it would leave the battlefield. Unearth "
              "only as a sorcery.)", "2", "1", colors=("B",))
FUTURE_SIGHT = real("Future Sight", "{2}{U}{U}{U}", "Enchantment", "Play with the top card of your library revealed.\nYou may play lands "
                    "and cast spells from the top of your library.", colors=("U",))
YOUNG_WOLF = real("Young Wolf", "{G}", "Creature — Wolf", "Undying (When this creature dies, if it had no +1/+1 counters on it, return it "
                  "to the battlefield under its owner's control with a +1/+1 counter on it.)", "1", "1", colors=("G",))
COMPANY = real("Collected Company", "{3}{G}", "Instant", "Look at the top six cards of your library. Put up to two creature cards with mana "
               "value 3 or less from among them onto the battlefield. Put the rest on the bottom of your library in any order.",
               colors=("G",))

URENI = real("Ureni of the Unwritten", "{4}{G}{U}{R}", "Legendary Creature — Spirit Dragon", "Flying, trample\nWhenever Ureni enters or "
             "attacks, look at the top eight cards of your library. You may put a Dragon creature card from among them onto the "
             "battlefield. Put the rest on the bottom of your library in a random order.", "7", "7", colors=("G", "R", "U"))
MUXUS = real("Muxus, Goblin Grandee", "{4}{R}{R}", "Legendary Creature — Goblin Noble", "When Muxus enters, reveal the top six cards of "
             "your library. Put all Goblin creature cards with mana value 5 or less from among them onto the battlefield and the rest on "
             "the bottom of your library in a random order.\nWhenever Muxus attacks, it gets +1/+1 until end of turn for each other Goblin "
             "you control.", "4", "4", colors=("R",))
DRAGON = real("Test Dragon", "{3}{R}", "Creature — Dragon", "", "4", "4")
GOBLIN = real("Test Goblin", "{R}", "Creature — Goblin", "", "1", "1")

GAIN = real("Test Gain", "{2}", "Sorcery", "You gain 3 life.")


def lunarch():
    veteran = {"name": "Lunarch Veteran", "mana_cost": "{W}", "type_line": "Creature — Human Cleric", "power": "1", "toughness": "1",
               "oracle_text": "Whenever another creature you control enters, you gain 1 life.\nDisturb {1}{W} (You may cast this card from "
                              "your graveyard transformed for its disturb cost.)"}
    phantom = {"name": "Luminous Phantom", "mana_cost": "", "type_line": "Creature — Spirit Cleric", "power": "1", "toughness": "1",
               "oracle_text": "Flying\nWhenever another creature you control leaves the battlefield, you gain 1 life.\nIf Luminous Phantom "
                              "would be put into a graveyard from anywhere, exile it instead."}
    return Card.from_scryfall(scryfall("transform", veteran, phantom, cmc=1.0, colors=["W"]))


def table(caged, battlefield=(), graveyard=(), library=(FOREST,) * 5):
    game, _ = table3(lambda prompt, options: 0)
    a = game.seats[0]
    a.battlefield = [Permanent(c) for c in battlefield] + lands(6) + ([Permanent(CAGE)] if caged else [])
    a.graveyard, a.library, a.hand = list(graveyard), list(library), []
    game.active, game.step = 0, "main1"
    return game, a


def offered(prefix, caged, **zones):
    game, a = table(caged, **zones)
    return [action for action in game.legal_actions(a) if action.startswith(prefix)]


class GrafdiggersCageTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CAGE), [])

    def test_flashback_is_stopped(self):
        self.assertEqual([offered(CAST_GRAVEYARD, c, graveyard=[THINK_TWICE]) for c in (False, True)], [[CAST_GRAVEYARD + "Think Twice"], []])

    def test_serra_paragon_casts_no_spell_but_still_plays_a_land(self):
        self.assertEqual([offered(CAST_PARAGON, c, battlefield=[PARAGON], graveyard=[BEAR]) for c in (False, True)], [[CAST_PARAGON + "Bear"], []])
        self.assertEqual(offered(PLAY_PARAGON, True, battlefield=[PARAGON], graveyard=[FOREST]), [PLAY_PARAGON + "Forest"])

    def test_a_graveyard_permit_is_stopped(self):
        self.assertEqual([offered(CAST_PERMIT, c, battlefield=[GISA], graveyard=[ZOMBIE]) for c in (False, True)],
                         [[CAST_PERMIT + "Dregscape Zombie"], []])

    def test_casting_from_the_top_of_the_library_is_stopped(self):
        self.assertEqual([offered(CAST_TOP, c, battlefield=[FUTURE_SIGHT], library=[BEAR]) for c in (False, True)], [[CAST_TOP + "Bear"], []])

    def test_a_milled_card_may_not_be_cast(self):
        for caged, expected in ((False, [CAST_MILLED + "Bear"]), (True, [])):
            game, a = table(caged, graveyard=[BEAR])
            a.graveyard_play = [(BEAR, game.turn)]
            self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_MILLED)], expected)

    def test_disturb_is_stopped(self):
        veteran = lunarch()
        self.assertEqual([offered(CAST_DISTURB, c, graveyard=[veteran]) for c in (False, True)], [[CAST_DISTURB + veteran.name], []])

    def test_a_cast_from_the_graveyard_by_an_effect_is_stopped(self):
        for caged, life in ((False, 43), (True, 40)):
            game, a = table(caged, graveyard=[GAIN])
            game.may_cast_from_graveyard(a, ("Sorcery",), False)
            run_stack(game)
            self.assertEqual(a.life, life)

    def test_unearth_is_not_offered(self):
        self.assertEqual([offered(UNEARTH, c, graveyard=[ZOMBIE]) for c in (False, True)], [[UNEARTH + "Dregscape Zombie"], []])

    def test_reanimation_leaves_a_creature_card_in_the_graveyard_but_not_an_artifact(self):
        game, a = table(True, graveyard=[BEAR, RELIC])
        game.return_from_graveyard(GraveyardTarget(BEAR, a), a, "battlefield")
        game.return_from_graveyard(GraveyardTarget(RELIC, a), a, "battlefield")
        self.assertEqual(a.graveyard, [BEAR])
        game.return_from_graveyard(GraveyardTarget(BEAR, a), a, "hand")  # to the hand is fine
        self.assertEqual((a.graveyard, a.hand), ([], [BEAR]))

    def test_undying_fails(self):
        for caged, back in ((False, True), (True, False)):
            game, a = table(caged, battlefield=[YOUNG_WOLF])
            game.destroy(next(p for p in a.battlefield if p.card is YOUNG_WOLF))
            run_stack(game)
            self.assertEqual(any(p.card is YOUNG_WOLF for p in a.battlefield), back)

    def test_a_search_puts_no_creature_onto_the_battlefield(self):
        game, a = table(True, library=[BEAR, FOREST])
        game.tutor(a, "creature", "battlefield", False)
        self.assertEqual(sorted(c.name for c in a.library), ["Bear", "Forest"])
        game.tutor(a, "creature", "hand", False)
        self.assertEqual(a.hand, [BEAR])

    def test_collected_company_finds_nothing(self):
        for caged, found in ((False, 1), (True, 0)):
            game, a = table(caged, library=[BEAR, FOREST, FOREST])
            a.hand = [COMPANY]
            game._perform(a, "Cast: Collected Company")
            run_stack(game)
            self.assertEqual(sum(p.card is BEAR for p in a.battlefield), found)

    def test_ureni_puts_no_dragon_onto_the_battlefield(self):
        for caged, found in ((False, 1), (True, 0)):
            game, a = table(caged, library=[DRAGON, FOREST])
            enter(game, a, URENI)
            run_stack(game)
            self.assertEqual(sum(p.card is DRAGON for p in a.battlefield), found)

    def test_muxus_puts_no_goblin_onto_the_battlefield(self):
        for caged, found in ((False, 1), (True, 0)):
            game, a = table(caged, library=[GOBLIN, FOREST])
            enter(game, a, MUXUS)
            run_stack(game)
            self.assertEqual(sum(p.card is GOBLIN for p in a.battlefield), found)
            self.assertEqual(len(a.library), 2 - found)

    def test_ao_puts_no_creature_but_an_artifact(self):
        for caged, found in ((False, {"Bear", "Relic"}), (True, {"Relic"})):
            game, a = table(caged, library=[BEAR, RELIC, FOREST])
            game.look_and_put_permanents(a, 3, 4)
            self.assertEqual({p.card.name for p in a.battlefield} & {"Bear", "Relic"}, found)


if __name__ == "__main__":
    unittest.main()
