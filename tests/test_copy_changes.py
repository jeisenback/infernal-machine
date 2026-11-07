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


FLESH_DUPLICATE = real("Flesh Duplicate", "{U}{U}", "Creature — Shapeshifter Rebel",
                       "You may have this creature enter as a copy of any creature on the battlefield, except it has vanishing 3 if that "
                       "creature doesn't have vanishing. (A permanent with vanishing 3 enters with three time counters on it. At the beginning "
                       "of your upkeep, remove a time counter from it. When the last is removed, sacrifice it.)", "0", "0", colors=("U",))
IMPOSTER_MECH = real("Imposter Mech", "{1}{U}", "Artifact — Vehicle",
                     "You may have this Vehicle enter as a copy of a creature an opponent controls, except it's a Vehicle artifact with crew 3 "
                     "and it loses all other card types.\nCrew 3", "3", "1", colors=("U",))
ESTRIDS_INVOCATION = real("Estrid's Invocation", "{2}{U}", "Enchantment",
                          "You may have this enchantment enter as a copy of an enchantment you control, except it has \"At the beginning of "
                          "your upkeep, you may exile this enchantment. If you do, return it to the battlefield under its owner's control.\"")
SAKASHIMA_FACES = real("Sakashima of a Thousand Faces", "{3}{U}", "Legendary Creature — Human Rogue",
                       "You may have Sakashima enter as a copy of another creature you control, except it has Sakashima's other abilities.\n"
                       "The \"legend rule\" doesn't apply to permanents you control.\nPartner (You can have two commanders if both have "
                       "partner.)", "3", "1", colors=("U",))
DREAMTIDE_WHALE = real("Dreamtide Whale", "{2}{U}", "Creature — Whale",
                       "Vanishing 2 (This creature enters with two time counters on it. At the beginning of your upkeep, remove a time "
                       "counter from it. When the last is removed, sacrifice it.)\nWhenever a player casts their second spell each turn, "
                       "proliferate. (Choose any number of permanents and/or players, then give each another counter of each kind already "
                       "there.)", "7", "5", colors=("U",))
ANTHEM_CARD = real("Test Anthem", "{2}{W}", "Enchantment", "Creatures you control get +1/+1.", colors=("W",))


def clone_into(card, copying, mine=(), theirs=(), lands_=6):
    """Seat 0 casts `card` and copies the permanent whose label starts with `copying`."""
    def policy(prompt, options):
        if CLONE_PROMPT.matches(prompt):
            return next(i for i, o in enumerate(options) if o.startswith(copying))
        return options.index(PASS) if PASS in options else 0
    game, _ = table3(policy)
    a, b, _ = game.seats
    a.battlefield, a.hand, b.battlefield = [*(Permanent(c) for c in mine), *lands(lands_)], [card], [Permanent(c) for c in theirs]
    game._perform(a, CAST + card.name)
    run_stack(game)
    return game, a, next(p for p in a.battlefield if p.real_card is not None)


def upkeep(game, seat):
    game.step = "upkeep"
    game._turn_based_actions(seat)
    run_stack(game)


class CopyChangesBatch2Tests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (FLESH_DUPLICATE, IMPOSTER_MECH, ESTRIDS_INVOCATION, SAKASHIMA_FACES, DREAMTIDE_WHALE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_vanishing_counts_down_and_sacrifices_on_the_last(self):
        game, _ = table3()
        a = game.seats[0]
        whale = enter(game, a, DREAMTIDE_WHALE)
        self.assertEqual(whale.counters.get("time"), 2)
        upkeep(game, a)
        self.assertEqual((whale.counters.get("time"), whale in a.battlefield), (1, True))
        upkeep(game, a)
        self.assertNotIn(whale, a.battlefield)
        bare = Permanent(DREAMTIDE_WHALE)  # with no time counter on it, the trigger does nothing (CR 702.63a: "if this permanent has ...")
        a.battlefield.append(bare)
        upkeep(game, a)
        self.assertIn(bare, a.battlefield)

    def test_flesh_duplicate_gets_vanishing_only_if_the_copied_creature_has_none(self):
        _, _, copy = clone_into(FLESH_DUPLICATE, "Test Brute", mine=[BRUTE])
        self.assertEqual((copy.card.name, copy.counters.get("time")), ("Test Brute", 3))
        _, _, copy = clone_into(FLESH_DUPLICATE, "Dreamtide Whale", mine=[DREAMTIDE_WHALE])
        self.assertEqual((copy.card.name, copy.counters.get("time")), ("Dreamtide Whale", 2))  # its own vanishing 2, not 3

    def test_imposter_mech_is_a_vehicle_copy_of_an_opponents_creature(self):
        game, a, mech = clone_into(IMPOSTER_MECH, "Test Brute", theirs=[BRUTE])
        self.assertEqual((mech.card.name, mech.card.type_line, "Creature" in mech.card.type_line), ("Test Brute", "Artifact — Vehicle", False))
        self.assertIn("Crew 3", mech.card.oracle_text)

    def test_estrids_invocation_copies_an_enchantment_and_may_blink_itself(self):
        game, a, copy = clone_into(ESTRIDS_INVOCATION, "Test Anthem", mine=[ANTHEM_CARD])
        self.assertEqual(copy.card.name, "Test Anthem")
        upkeep(game, a)  # it leaves and comes back: a new object, which may copy again
        self.assertNotIn(copy, a.battlefield)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Enchantment" in p.card.type_line), ["Test Anthem", "Test Anthem"])

    def test_sakashima_of_a_thousand_faces_keeps_its_own_other_abilities(self):
        _, _, copy = clone_into(SAKASHIMA_FACES, "Test Brute", mine=[BRUTE])
        self.assertEqual(copy.card.name, "Test Brute")
        self.assertIn("legend rule", copy.card.oracle_text)
        self.assertNotIn("enter as a copy", copy.card.oracle_text)
