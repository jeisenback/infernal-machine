"""Copies with changes (CR 707.9), #657: a destroyed creature's two half-size copies, a land or creature that becomes a copy of another and
keeps "this ability", a clone that keeps its name and gains a quoted ability. Lines are the cards' own Oracle text."""

import unittest

from infernal_machine.game import CAST, CLONE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, PASS, activate, activations, enter, fire, lands, pick, real, run_stack, table3

SAW_IN_HALF = real("Saw in Half", "{2}{B}", "Instant",
                   "Destroy target creature. If that creature dies this way, its controller creates two tokens that are copies of that "
                   "creature, except their power is half that creature's power and their toughness is half that creature's toughness. "
                   "Round up each time.", colors=("B",))
THESPIANS_STAGE = real("Thespian's Stage", "", "Land",
                       "{T}: Add {C}.\n{2}, {T}: This land becomes a copy of target land, except it has this ability.")
SAKASHIMA = real("Sakashima the Impostor", "{2}{U}{U}", "Legendary Creature — Human Rogue",
                 "You may have Sakashima the Impostor enter as a copy of any creature on the battlefield, except its name is Sakashima the "
                 "Impostor, it's legendary in addition to its other types, and it has \"{2}{U}{U}: Return Sakashima the Impostor to its "
                 "owner's hand at the beginning of the next end step.\"", "3", "1", colors=("U",))
SARKHAN = real("Sarkhan, Soul Aflame", "{1}{U}{R}", "Legendary Creature — Human Shaman",
               "Dragon spells you cast cost {1} less to cast.\nWhenever a Dragon you control enters, you may have Sarkhan become a copy of "
               "it until end of turn, except its name is Sarkhan, Soul Aflame and it's legendary in addition to its other types.", "2", "4",
               colors=("R", "U"))
SUNFRILL = real("Sunfrill Imitator", "{2}{G}", "Creature — Dinosaur",
                "Whenever this creature attacks, you may have it become a copy of another target Dinosaur you control, except its name is "
                "Sunfrill Imitator and it has this ability.", "3", "3", colors=("G",))
IRMA = real("Irma, Part-Time Mutant", "{2}{U}", "Legendary Creature — Human Mutant Shapeshifter",
            "At the beginning of combat on your turn, Irma becomes a copy of up to one other target creature you control, except her name "
            "is Irma, Part-Time Mutant and she has this ability. Then put a +1/+1 counter on her.", "1", "1", colors=("U",))
BRUTE = real("Test Brute", "{4}{G}", "Creature — Beast", "Trample", "5", "3", colors=("G",))
WALL = real("Test Wall", "{2}{W}", "Creature — Wall", "Indestructible", "0", "4", colors=("W",))
DRAGON = real("Test Dragon", "{4}{R}", "Creature — Dragon", "Flying", "5", "5", colors=("R",))
DINO = real("Test Dinosaur", "{4}{G}", "Creature — Dinosaur", "Trample", "6", "6", colors=("G",))
CAVE = real("Test Cave", "", "Land", "{T}: Add {G}.")


class CopyChangesTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (SAW_IN_HALF, THESPIANS_STAGE, SAKASHIMA, SARKHAN, SUNFRILL, IRMA):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_saw_in_half_gives_two_half_size_copies_to_the_controller(self):
        game, _ = table3(pick("Test Brute"))
        a, b, _ = game.seats
        a.battlefield, a.hand, b.battlefield = lands(3), [SAW_IN_HALF], [Permanent(BRUTE)]
        game._perform(a, CAST + "Saw in Half")
        run_stack(game)
        made = [p for p in b.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual([(p.card.name, game.power(p), game.toughness(p)) for p in made], [("Test Brute", 3, 2)] * 2)  # 5/3: 3/2, rounded up

    def test_saw_in_half_does_nothing_more_if_the_creature_does_not_die(self):
        game, _ = table3(pick("Test Wall"))
        a, b, _ = game.seats
        a.battlefield, a.hand, b.battlefield = lands(3), [SAW_IN_HALF], [Permanent(WALL)]
        game._perform(a, CAST + "Saw in Half")
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Test Wall"])

    def test_thespians_stage_becomes_the_land_and_keeps_its_ability(self):
        game, _ = table3(pick("Test Cave"))
        a = game.seats[0]
        stage = Permanent(THESPIANS_STAGE)
        a.battlefield = [stage, Permanent(CAVE), *lands(2)]
        activate(game, a, "This land becomes a copy")
        self.assertEqual((stage.card.name, "{T}: Add {G}." in stage.card.oracle_text, "becomes a copy of target land" in stage.card.oracle_text),
                         ("Test Cave", True, True))
        stage.tapped = False
        for land in a.battlefield[2:]:
            land.tapped = False
        self.assertTrue(activations(game, a, "This land becomes a copy"))  # it still has the ability
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual(stage.card.name, "Test Cave")  # for good, not until end of turn

    def test_sakashima_keeps_its_name_and_can_return_itself(self):
        def policy(prompt, options):
            if CLONE_PROMPT.matches(prompt):
                return next(i for i, o in enumerate(options) if o.startswith("Test Brute"))
            return options.index(PASS) if PASS in options else 0
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield, a.hand = [Permanent(BRUTE), *lands(8)], [SAKASHIMA]
        game._perform(a, CAST + "Sakashima the Impostor")
        run_stack(game)
        clone = next(p for p in a.battlefield if p.real_card is not None)
        self.assertEqual((clone.card.name, "Legendary" in clone.card.type_line, game.power(clone)), ("Sakashima the Impostor", True, 5))
        activate(game, a, "Return")
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Sakashima the Impostor"])

    def test_sarkhan_becomes_the_dragon_until_end_of_turn(self):
        for card, copies in ((DRAGON, True), (BEAR, False)):
            game, _ = table3()
            a = game.seats[0]
            sarkhan = Permanent(SARKHAN)
            a.battlefield = [sarkhan]
            enter(game, a, card)
            run_stack(game)
            self.assertEqual((sarkhan.card.name, game.power(sarkhan) == 5), ("Sarkhan, Soul Aflame", copies), card.name)
            self.assertEqual("Legendary" in sarkhan.card.type_line and game.has_keyword(sarkhan, "flying"), copies)
            game.step = "cleanup"
            game._turn_based_actions(a)
            self.assertEqual(game.power(sarkhan), 2)  # back to itself

    def test_sunfrill_imitator_becomes_another_dinosaur_and_keeps_the_ability(self):
        game, _ = table3(pick("Test Dinosaur"))
        a = game.seats[0]
        sunfrill = Permanent(SUNFRILL)
        a.battlefield = [sunfrill, Permanent(DINO), Permanent(BEAR)]
        fire(game, a, sunfrill, "attacks")
        self.assertEqual((sunfrill.card.name, game.power(sunfrill), "Whenever this creature attacks" in sunfrill.card.oracle_text),
                         ("Sunfrill Imitator", 6, True))

    def test_sunfrill_imitator_copies_only_a_dinosaur(self):
        game, _ = table3(pick("Test Dinosaur", "Bear"))
        a, b, _ = game.seats
        sunfrill = Permanent(SUNFRILL)
        a.battlefield, b.battlefield = [sunfrill, Permanent(BEAR)], [Permanent(DINO)]  # an opponent's Dinosaur is not one you control
        fire(game, a, sunfrill, "attacks")
        self.assertEqual(game.power(sunfrill), 3)

    def test_irma_becomes_another_creature_keeps_her_name_and_gets_a_counter(self):
        game, _ = table3(pick("Test Brute"))
        a = game.seats[0]
        irma = Permanent(IRMA)
        a.battlefield = [irma, Permanent(BRUTE)]
        fire(game, a, irma, "combat")
        self.assertEqual((irma.card.name, game.power(irma), "At the beginning of combat on your turn" in irma.card.oracle_text),
                         ("Irma, Part-Time Mutant", 6, True))
