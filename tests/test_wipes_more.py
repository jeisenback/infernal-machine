import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import DestroyAll, EachSacrifices, GiveBack, SacrificeAll, spell_effects
from infernal_machine.game import SACRIFICE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import FOREST
from tests.test_mass_effects import table3


def sorcery(text):
    return Card(name="Spell", mana_cost="{2}", type_line="Sorcery", oracle_text=text)


def make(name, power, toughness, text="", cmc=2.0, kind="Creature — Test"):
    return Card(name=name, mana_cost="{%d}" % int(cmc), cmc=cmc, type_line=kind, power=str(power), toughness=str(toughness),
                oracle_text=text)


SMALL = make("Small", 1, 1, cmc=2.0)
BIG = make("Big", 5, 5, cmc=6.0)
LEGEND = make("Legend", 2, 2, cmc=3.0, kind="Legendary Creature — Test")
GOLEM = make("Golem", 3, 3, cmc=3.0, kind="Artifact Creature — Golem")
BIRD = make("Bird", 1, 1, "Flying", cmc=1.0)
SPIRIT = Card(name="Spirit Token", type_line="Token Creature — Spirit", power="1", toughness="1", colors=("W",))
RELIC = Card(name="Relic", mana_cost="{2}", cmc=2.0, type_line="Artifact")
IDOL = Card(name="Idol", mana_cost="{5}", cmc=5.0, type_line="Artifact")
CHARM = Card(name="Charm", mana_cost="{1}", cmc=1.0, type_line="Enchantment")
SHRINE = Card(name="Shrine", type_line="Land")


def survivors(seat):
    return sorted(p.card.name for p in seat.battlefield)


def wipe(text, *cards):
    """Resolve `text` for seat 0 against seat 1 holding `cards`; return the game."""
    game, _ = table3()
    a, b, _ = game.seats
    b.battlefield = [Permanent(c) for c in cards]
    for effect in spell_effects(sorcery(text)):
        effect.resolve(game, a, None)
    return game


class ParseTests(unittest.TestCase):
    def test_all_are_understood(self):
        for text in ("Destroy all creatures with mana value 3 or less.", "Destroy all creatures with mana value 4 or greater.",
                     "Destroy all nontoken creatures.", "Destroy all creature tokens.", "Destroy all legendary creatures.",
                     "Destroy all tapped creatures.", "Destroy all nonbasic lands.", "Exile all creatures except for artifact creatures.",
                     "Destroy all creatures except legendary creatures.",
                     "Destroy all creatures. For each creature destroyed this way, its controller creates a 1/1 white Spirit creature token.",
                     "Each opponent sacrifices a creature with the greatest power among creatures they control.",
                     "Each player sacrifices two lands.", "Each opponent sacrifices a nonland permanent.",
                     "Each opponent sacrifices an artifact or enchantment.",
                     "Each player sacrifices all creatures they control.", "Sacrifice all creatures you control.",
                     "CARDNAME deals 3 damage to each creature your opponents control.", "All creatures get -2/-2 until end of turn."):
            self.assertEqual(unsupported_lines(sorcery(text)), [], text)

    def test_the_second_half_alone_is_not_understood(self):
        self.assertIsNone(spell_effects(sorcery("For each creature destroyed this way, its controller creates a 1/1 white Spirit "
                                                 "creature token.")))

    def test_shapes(self):
        [wipe_] = spell_effects(sorcery("Destroy all creatures. For each creature destroyed this way, its controller creates a 1/1 "
                                         "white Spirit creature token."))
        self.assertEqual((wipe_.gives[0], wipe_.gives[1].name), (1, "Spirit"))
        self.assertEqual(spell_effects(sorcery("Each opponent sacrifices a creature with the greatest power among creatures "
                                                "they control.")), [EachSacrifices("opponent", "creature", 1, True)])
        self.assertEqual(spell_effects(sorcery("Each player sacrifices all creatures they control.")),
                         [EachSacrifices("player", "creature", None)])
        self.assertEqual(spell_effects(sorcery("Sacrifice all lands you control.")), [SacrificeAll("land")])


class RestrictionTests(unittest.TestCase):
    def test_mana_value(self):
        game = wipe("Destroy all creatures with mana value 3 or less.", SMALL, BIG, LEGEND)
        self.assertEqual(survivors(game.seats[1]), ["Big"])
        game = wipe("Destroy all creatures with mana value 3 or greater.", SMALL, BIG, LEGEND)
        self.assertEqual(survivors(game.seats[1]), ["Small"])

    def test_mana_value_works_on_noncreatures_too(self):
        game = wipe("Destroy all artifacts with mana value 2 or less.", RELIC, IDOL)
        self.assertEqual(survivors(game.seats[1]), ["Idol"])

    def test_tokens(self):
        game = wipe("Destroy all creature tokens.", SMALL, SPIRIT)
        self.assertEqual(survivors(game.seats[1]), ["Small"])
        game = wipe("Destroy all nontoken creatures.", SMALL, SPIRIT)
        self.assertEqual(survivors(game.seats[1]), ["Spirit Token"])

    def test_legendary_tapped_and_nonbasic(self):
        game = wipe("Destroy all legendary creatures.", SMALL, LEGEND)
        self.assertEqual(survivors(game.seats[1]), ["Small"])
        game, _ = table3()
        a, b, _ = game.seats
        tapped, untapped = Permanent(SMALL, tapped=True), Permanent(BIG)
        b.battlefield = [tapped, untapped]
        spell_effects(sorcery("Destroy all tapped creatures."))[0].resolve(game, a, None)
        self.assertEqual(b.battlefield, [untapped])
        game = wipe("Destroy all nonbasic lands.", FOREST, SHRINE)
        self.assertEqual(survivors(game.seats[1]), ["Forest"])

    def test_except_for(self):
        game = wipe("Destroy all creatures except for artifact creatures.", SMALL, GOLEM)
        self.assertEqual(survivors(game.seats[1]), ["Golem"])
        game = wipe("Exile all creatures except creatures with flying.", SMALL, BIRD)
        self.assertEqual(survivors(game.seats[1]), ["Bird"])
        game = wipe("Destroy all creatures except for legendary creatures.", SMALL, LEGEND)
        self.assertEqual(survivors(game.seats[1]), ["Legend"])


class GiveBackTests(unittest.TestCase):
    def test_each_controller_gets_a_token_per_creature_they_lost(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, b.battlefield, c.battlefield = [Permanent(SMALL)], [Permanent(SMALL), Permanent(BIG)], []
        for effect in spell_effects(sorcery("Destroy all creatures. For each creature destroyed this way, its controller creates "
                                            "a 1/1 white Spirit creature token.")):
            effect.resolve(game, a, None)
        self.assertEqual([survivors(s) for s in game.seats], [["Spirit"], ["Spirit", "Spirit"], []])

    def test_an_indestructible_creature_gives_nothing(self):
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(make("Rock", 2, 2, "Indestructible")), Permanent(SMALL)]
        for effect in spell_effects(sorcery("Destroy all creatures. For each creature destroyed this way, its controller creates "
                                            "a 1/1 white Spirit creature token.")):
            effect.resolve(game, a, None)
        self.assertEqual(survivors(b), ["Rock", "Spirit"])


class SacrificeTests(unittest.TestCase):
    def test_the_greatest_power_among_their_creatures(self):
        game, players = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(SMALL), Permanent(BIG), Permanent(make("Big2", 5, 1))]
        spell_effects(sorcery("Each opponent sacrifices a creature with the greatest power among creatures they control."))[0].resolve(game, a, None)
        offered = next(o for p, o in players[1].prompts if p == SACRIFICE_PROMPT)
        self.assertEqual(len(offered), 2)  # only the two 5-power creatures
        self.assertIn("Small", survivors(b))  # the weak one is never the choice
        self.assertEqual(len(b.battlefield), 2)

    def test_two_lands(self):
        game = wipe("Each player sacrifices two lands.", FOREST, FOREST, FOREST)
        self.assertEqual(len(game.seats[1].battlefield), 1)

    def test_fewer_than_asked(self):
        game = wipe("Each player sacrifices two lands.", FOREST)
        self.assertEqual(game.seats[1].battlefield, [])

    def test_all_of_a_kind(self):
        game = wipe("Each player sacrifices all creatures they control.", SMALL, BIG, RELIC)
        self.assertEqual(survivors(game.seats[1]), ["Relic"])

    def test_nonland_permanent_and_artifact_or_enchantment(self):
        game = wipe("Each opponent sacrifices a nonland permanent.", FOREST, SMALL)
        self.assertEqual(survivors(game.seats[1]), ["Forest"])
        game = wipe("Each opponent sacrifices an artifact or enchantment.", SMALL, CHARM)
        self.assertEqual(survivors(game.seats[1]), ["Small"])

    def test_sacrificing_your_own(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(SMALL), Permanent(BIG), Permanent(RELIC)]
        spell_effects(sorcery("Sacrifice all creatures you control."))[0].resolve(game, a, None)
        self.assertEqual(survivors(a), ["Relic"])


class MassPumpAndDamageTests(unittest.TestCase):
    def test_damage_to_opponents_creatures_only(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(SMALL)], [Permanent(SMALL)]
        spell_effects(Card(name="Blast", mana_cost="{2}", type_line="Sorcery",
                           oracle_text="Blast deals 3 damage to each creature your opponents control."))[0].resolve(game, a, None)
        game._check_state()
        self.assertEqual((survivors(a), survivors(b)), (["Small"], []))

    def test_all_creatures_get_minus_two(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(SMALL), Permanent(BIG)], [Permanent(SMALL)]
        spell_effects(sorcery("All creatures get -2/-2 until end of turn."))[0].resolve(game, a, None)
        game._check_state()
        self.assertEqual((survivors(a), survivors(b)), (["Big"], []))
