import unittest

from infernal_machine.cards import Card
from infernal_machine.characteristics import Modifier
from infernal_machine.effects import DamageEach, DestroyAll, EachSacrifices, ExileAll, MassFilter, TargetSacrifices, spell_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, WURM, creature
from tests.test_effects import SOL_RING, lands, pick, table

BIRD = creature("Bird", 1, 1, "Flying")
DRAGON = creature("Dragon", 4, 4, "Flying")
FOREST_CARD = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def sorcery(text, cost="{2}{W}"):
    return Card(name="Wipe", mana_cost=cost, type_line="Sorcery", oracle_text=text)


def colored(name, color, power=2, toughness=2):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Test", power=str(power), toughness=str(toughness),
                colors=(color,))


def cast(card, mine, theirs=()):
    game, _, _ = table(pick(CAST))
    a, b = game.seats
    a.hand = [card]
    a.battlefield = lands(4) + [Permanent(c) for c in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    game._priority_round(a)
    return game, a, b


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


class ParseTests(unittest.TestCase):
    def test_keyword_and_stat_restrictions(self):
        self.assertEqual(spell_effects(sorcery("Destroy all creatures with flying.")),
                         [DestroyAll("creature", MassFilter(keyword="flying"))])
        self.assertEqual(spell_effects(sorcery("Destroy all creatures without flying.")),
                         [DestroyAll("creature", MassFilter(keyword="flying", keyword_wanted=False))])
        self.assertEqual(spell_effects(sorcery("Destroy all creatures with power 4 or greater.")),
                         [DestroyAll("creature", MassFilter(stat="power", at_least=4))])
        self.assertEqual(spell_effects(sorcery("Exile all creatures with toughness 2 or less.")),
                         [ExileAll("creature", MassFilter(stat="toughness", at_most=2))])

    def test_color_and_controller(self):
        self.assertEqual(spell_effects(sorcery("Destroy all nonblack creatures.")),
                         [DestroyAll("creature", MassFilter(color="B", other_color=True))])
        self.assertEqual(spell_effects(sorcery("Destroy all white creatures you control.")),
                         [DestroyAll("creature you control", MassFilter(color="W"))])

    def test_damage_to_each_with_a_restriction(self):
        self.assertEqual(spell_effects(sorcery("Wipe deals 1 damage to each creature with flying and each player.")),
                         [DamageEach(1, "all", "all", MassFilter(keyword="flying"))])

    def test_sacrificing_other_things(self):
        self.assertEqual(spell_effects(sorcery("Each player sacrifices a land.")), [EachSacrifices("player", "land")])
        self.assertEqual(spell_effects(sorcery("Target opponent sacrifices an artifact.")),
                         [TargetSacrifices("opponent", "artifact")])

    def test_report(self):
        for text in ("Destroy all creatures with flying.", "Exile all nonwhite creatures.",
                     "Wipe deals 2 damage to each creature with power 3 or greater."):
            self.assertEqual(unsupported_lines(sorcery(text)), [], text)

    def test_other_restrictions_are_still_unsupported(self):
        for text in ("Destroy all creatures with a +1/+1 counter on them.", "Destroy all creatures with islandwalk.",
                     "Wipe deals 2 damage to each opponent with flying."):
            self.assertIsNone(spell_effects(sorcery(text)), text)


class DestroyTests(unittest.TestCase):
    def test_with_flying_hits_every_side_but_only_flyers(self):
        _, a, b = cast(sorcery("Destroy all creatures with flying."), [BIRD, BEAR], [DRAGON, OGRE])
        self.assertEqual((names(a), names(b)), (["Bear"], ["Ogre"]))

    def test_without_flying_spares_the_flyers(self):
        _, a, b = cast(sorcery("Destroy all creatures without flying."), [BIRD, BEAR], [DRAGON, OGRE])
        self.assertEqual((names(a), names(b)), (["Bird"], ["Dragon"]))

    def test_a_granted_keyword_counts(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        bear = Permanent(BEAR)
        game.modify_until_end_of_turn(bear, Modifier(0, 0, frozenset({"flying"})))
        a.hand = [sorcery("Destroy all creatures with flying.")]
        a.battlefield = lands(4) + [bear]
        game._priority_round(a)
        self.assertEqual(names(a), [])

    def test_power_and_toughness(self):
        _, a, b = cast(sorcery("Destroy all creatures with power 4 or greater."), [BEAR, WURM], [DRAGON, OGRE])
        self.assertEqual((names(a), names(b)), (["Bear"], ["Ogre"]))
        _, a, b = cast(sorcery("Destroy all creatures with toughness 2 or less."), [BEAR, WURM, BIRD], [DRAGON, OGRE])
        self.assertEqual((names(a), names(b)), (["Wurm"], ["Dragon", "Ogre"]))

    def test_stat_restrictions_ignore_noncreatures(self):
        _, a, _ = cast(sorcery("Destroy all artifacts with power 1 or greater."), [SOL_RING])
        self.assertEqual(names(a), ["Sol Ring"])

    def test_nonblack_and_black(self):
        mine = [colored("Zombie", "B"), colored("Goblin", "R")]
        theirs = [colored("Elf", "G"), colored("Ghoul", "B")]
        _, a, b = cast(sorcery("Destroy all nonblack creatures."), mine, theirs)
        self.assertEqual((names(a), names(b)), (["Zombie"], ["Ghoul"]))
        _, a, b = cast(sorcery("Destroy all black creatures."), mine, theirs)
        self.assertEqual((names(a), names(b)), (["Goblin"], ["Elf"]))

    def test_your_own_only(self):
        _, a, b = cast(sorcery("Destroy all white creatures you control."), [colored("Knight", "W"), colored("Imp", "B")],
                       [colored("Angel", "W")])
        self.assertEqual((names(a), names(b)), (["Imp"], ["Angel"]))

    def test_exile(self):
        game, a, b = cast(sorcery("Exile all creatures with flying."), [BIRD], [BEAR])
        self.assertEqual((names(a), names(b)), ([], ["Bear"]))
        self.assertEqual([c.name for c in a.exile], ["Bird"])


class DamageTests(unittest.TestCase):
    def test_each_creature_with_flying(self):
        game, a, b = cast(sorcery("Wipe deals 2 damage to each creature with flying."), [BIRD, BEAR], [DRAGON])
        self.assertEqual((names(a), names(b)), (["Bear"], ["Dragon"]))
        bear = next(p for p in a.battlefield if p.card.name == "Bear")
        self.assertEqual(bear.damage, 0)
        self.assertEqual((a.life, b.life), (40, 40))

    def test_and_each_player(self):
        game, a, b = cast(sorcery("Wipe deals 1 damage to each creature with flying and each player."), [BIRD], [BEAR])
        self.assertEqual((a.life, b.life), (39, 39))
        self.assertEqual(names(a), [])


class SacrificeKindTests(unittest.TestCase):
    def test_each_player_sacrifices_a_land(self):
        game, a, b = cast(sorcery("Each player sacrifices a land."), [BEAR], [])
        b.battlefield = lands(2, FOREST_CARD)
        game.sacrifice(b, "land")
        self.assertEqual(len(b.battlefield), 1)

    def test_the_effect(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = lands(2, FOREST_CARD)
        b.battlefield = lands(2, FOREST_CARD) + [Permanent(BEAR)]
        EachSacrifices("player", "land").resolve(game, a, None)
        self.assertEqual((len(a.battlefield), len(b.battlefield)), (1, 2))  # B kept the Bear

    def test_only_opponents_and_only_that_kind(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(SOL_RING)]
        b.battlefield = [Permanent(SOL_RING), Permanent(BEAR)]
        EachSacrifices("opponent", "artifact").resolve(game, a, None)
        self.assertEqual((names(a), names(b)), (["Sol Ring"], ["Bear"]))

    def test_nothing_to_sacrifice(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)]
        TargetSacrifices("player", "artifact").resolve(game, game.seats[1], a)
        self.assertEqual(names(a), ["Bear"])

    def test_a_permanent_of_any_kind(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)]
        game.sacrifice(a, "permanent")
        self.assertEqual(a.battlefield, [])


if __name__ == "__main__":
    unittest.main()
