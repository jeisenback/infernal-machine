"""The nine mana, ramp and fetch cards of the precon decks that no test named (issue #155), each played from its real Oracle
text: the mana really pays for a spell, and each has cases where it must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import battlefield_names, BEAR, FOREST, lands, OGRE, pick, PLAINS, real, RELIC, run_stack, Table, table3

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
CITY = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG"))
BREEDING_POOL = Card(name="Breeding Pool", type_line="Land — Forest Island", produced_mana=("G", "U"))
BLUE_SPELL = real("Blue Draw", "{U}", "Instant", "Draw a card.", colors=("U",))
RED_SPELL = real("Red Draw", "{R}", "Instant", "Draw a card.", colors=("R",))
ONE_SPELL = real("One Draw", "{1}", "Instant", "Draw a card.")
GREEN_SPELL = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def castable(t):
    return any(a.startswith(CAST + t.card.name) for a in t.game.legal_actions(t.a))


def with_rock(spell, rock, theirs=(), **kw):
    return Table(spell, n=0, mine=[rock], theirs=list(theirs), **kw)


FELLWAR = real("Fellwar Stone", "{2}", "Artifact", "{T}: Add one mana of any color that a land an opponent controls could produce.")


class FellwarStoneTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(FELLWAR), [])

    def test_it_makes_a_color_an_opponents_land_could_produce(self):
        t = with_rock(BLUE_SPELL, Permanent(FELLWAR), theirs=[Permanent(ISLAND)])
        self.assertTrue(castable(t))

    def test_it_cannot_make_a_color_no_opposing_land_makes(self):
        t = with_rock(RED_SPELL, Permanent(FELLWAR), theirs=[Permanent(ISLAND)])
        self.assertFalse(castable(t))

    def test_an_opponent_with_no_lands_gives_it_nothing(self):
        t = with_rock(ONE_SPELL, Permanent(FELLWAR))
        self.assertFalse(castable(t))

    def test_a_colorless_land_is_not_a_color(self):
        t = with_rock(ONE_SPELL, Permanent(FELLWAR), theirs=[Permanent(WASTES)])
        self.assertFalse(castable(t))

    def test_a_land_that_makes_any_color_lets_it_make_any_color(self):
        for spell in (BLUE_SPELL, RED_SPELL, GREEN_SPELL):
            t = with_rock(spell, Permanent(FELLWAR), theirs=[Permanent(CITY)])
            self.assertTrue(castable(t), spell.name)

    def test_my_own_lands_do_not_count(self):
        t = Table(BLUE_SPELL, n=0, mine=[Permanent(FELLWAR), Permanent(ISLAND, tapped=True)], theirs=[Permanent(MOUNTAIN)])
        self.assertFalse(castable(t))  # my Island is tapped and the opponent's land makes only red

    def test_casting_through_it_taps_it(self):
        rock = Permanent(FELLWAR)
        t = with_rock(BLUE_SPELL, rock, theirs=[Permanent(ISLAND)]).cast()
        self.assertTrue(rock.tapped)


def talisman(name, other_a, other_b):
    return real(name, "{2}", "Artifact", "{T}: Add {C}.\n{T}: Add {%s} or {%s}. This artifact deals 1 damage to you." % (other_a, other_b))


CREATIVITY = talisman("Talisman of Creativity", "U", "R")
HIERARCHY = talisman("Talisman of Hierarchy", "W", "B")
WHITE_SPELL = real("White Draw", "{W}", "Instant", "Draw a card.", colors=("W",))
BLACK_SPELL = real("Black Draw", "{B}", "Instant", "Draw a card.", colors=("B",))


class TalismanTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(CREATIVITY), [])
        self.assertEqual(unsupported_lines(HIERARCHY), [])

    def test_colored_mana_costs_one_life(self):
        for rock, spell in ((CREATIVITY, BLUE_SPELL), (CREATIVITY, RED_SPELL), (HIERARCHY, WHITE_SPELL), (HIERARCHY, BLACK_SPELL)):
            t = with_rock(spell, Permanent(rock)).cast()
            self.assertEqual(t.a.life, 39, (rock.name, spell.name))

    def test_colorless_mana_costs_no_life(self):
        t = with_rock(ONE_SPELL, Permanent(CREATIVITY)).cast()
        self.assertEqual(t.a.life, 40)

    def test_it_cannot_make_a_color_it_does_not_list(self):
        self.assertFalse(castable(with_rock(GREEN_SPELL, Permanent(CREATIVITY))))
        self.assertFalse(castable(with_rock(RED_SPELL, Permanent(HIERARCHY))))

    def test_it_makes_only_one_mana(self):
        self.assertFalse(castable(with_rock(real("Two Draw", "{2}", "Instant", "Draw a card."), Permanent(CREATIVITY))))
        self.assertTrue(castable(Table(real("Two Draw", "{2}", "Instant", "Draw a card."), n=1, mine=[Permanent(CREATIVITY)])))


MYSTIC = real("Elvish Mystic", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1")


class ElvishMysticTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(MYSTIC), [])

    def test_it_pays_for_a_green_spell(self):
        t = with_rock(GREEN_SPELL, Permanent(MYSTIC, sick=False)).cast()
        self.assertEqual(len(t.a.hand), 1)

    def test_it_cannot_make_other_colors(self):
        self.assertFalse(castable(with_rock(BLUE_SPELL, Permanent(MYSTIC, sick=False))))

    def test_it_cannot_tap_while_summoning_sick(self):
        self.assertFalse(castable(with_rock(GREEN_SPELL, Permanent(MYSTIC, sick=True))))

    def test_it_cannot_tap_twice(self):
        t = with_rock(GREEN_SPELL, Permanent(MYSTIC, sick=False), library=[FOREST] * 5)
        t.a.hand = [GREEN_SPELL, GREEN_SPELL]
        t.game._perform(t.a, CAST + "Green Draw")
        run_stack(t.game)
        self.assertFalse(any(a.startswith(CAST) for a in t.game.legal_actions(t.a)))


ELDER = real("Sakura-Tribe Elder", "{1}{G}", "Creature — Snake Shaman",
             "Sacrifice this creature: Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.",
             "1", "1")


class SakuraTribeElderTests(unittest.TestCase):
    def sacrifice(self, library):
        game, _ = table3(pick("Mountain"))
        a = game.seats[0]
        elder = Permanent(ELDER, sick=True)  # sacrifice needs no tap, so summoning sickness does not matter
        a.battlefield = [elder]
        a.library = list(library)
        activate(game, a, "Sacrifice this creature")
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(ELDER), [])

    def test_it_fetches_a_basic_land_tapped_even_while_summoning_sick(self):
        game, a = self.sacrifice([FOREST, MOUNTAIN, FOREST])
        land = next(p for p in a.battlefield if p.card.name == "Mountain")
        self.assertTrue(land.tapped)
        self.assertEqual([c.name for c in a.graveyard], ["Sakura-Tribe Elder"])
        self.assertEqual(len(a.library), 2)

    def test_a_nonbasic_land_is_not_a_choice(self):
        game, a = self.sacrifice([BREEDING_POOL, MOUNTAIN])
        self.assertEqual(battlefield_names(a), ["Mountain"])

    def test_with_no_basic_land_it_is_still_sacrificed(self):
        game, a = self.sacrifice([BREEDING_POOL, BEAR])
        self.assertEqual((battlefield_names(a), [c.name for c in a.graveyard]), ([], ["Sakura-Tribe Elder"]))


SOLEMN = real("Solemn Simulacrum", "{4}", "Artifact Creature — Golem",
              "When this creature enters, you may search your library for a basic land card, put that card onto the battlefield tapped, "
              "then shuffle.\nWhen this creature dies, you may draw a card.", "2", "2")


class SolemnSimulacrumTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SOLEMN), [])

    def cast(self, *answers, library=(FOREST, MOUNTAIN, BEAR)):
        return Table(SOLEMN, *answers, library=list(library)).cast()

    def test_it_may_fetch_a_basic_land_tapped_on_entering(self):
        t = self.cast("Yes", "Mountain")
        land = next(p for p in t.a.battlefield if p.card.name == "Mountain")
        self.assertTrue(land.tapped)

    def test_it_may_decline_the_land(self):
        t = self.cast("No")
        self.assertFalse(any(p.card.name in ("Forest", "Mountain") for p in t.a.battlefield))

    def test_dying_it_may_draw_a_card(self):
        t = self.cast("No", "Yes")
        solemn = next(p for p in t.a.battlefield if p.card.name == "Solemn Simulacrum")
        t.game.destroy(solemn)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1)

    def test_dying_it_may_decline_to_draw(self):
        t = self.cast("No", "No")
        solemn = next(p for p in t.a.battlefield if p.card.name == "Solemn Simulacrum")
        t.game.destroy(solemn)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)

    def test_it_does_not_draw_when_it_is_exiled_instead_of_dying(self):
        t = self.cast("No", "Yes")
        solemn = next(p for p in t.a.battlefield if p.card.name == "Solemn Simulacrum")
        t.game.exile(solemn)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)


VISITS = real("Three Visits", "{1}{G}", "Sorcery", "Search your library for a Forest card, put it onto the battlefield, then shuffle.")


class ThreeVisitsTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(VISITS), [])

    def test_it_fetches_a_basic_forest_untapped(self):
        t = Table(VISITS, "Forest", library=[ISLAND, FOREST, BEAR]).cast()
        forest = next(p for p in t.a.battlefield if p.card.name == "Forest")
        self.assertFalse(forest.tapped)

    def test_a_nonbasic_forest_counts(self):
        t = Table(VISITS, "Breeding Pool", library=[BREEDING_POOL, FOREST]).cast()
        self.assertIn("Breeding Pool", battlefield_names(t.a))

    def test_a_basic_that_is_not_a_forest_is_not_a_choice(self):
        t = Table(VISITS, "Island", library=[ISLAND, MOUNTAIN]).cast()
        self.assertEqual(battlefield_names(t.a), [])

    def test_with_no_forest_it_fetches_nothing(self):
        t = Table(VISITS, library=[BEAR]).cast()
        self.assertEqual((battlefield_names(t.a), len(t.a.library)), ([], 1))


ZONE = real("Awakening Zone", "{2}{G}", "Enchantment",
            'At the beginning of your upkeep, you may create a 0/1 colorless Eldrazi Spawn creature token. It has "Sacrifice this token: '
            'Add {C}."')


class AwakeningZoneTests(unittest.TestCase):
    def upkeep(self, choice):
        game, _ = table3(pick(choice))
        a = game.seats[0]
        zone = Permanent(ZONE)
        a.battlefield = [zone]
        game.trigger("upkeep", zone, a)
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(ZONE), [])

    def test_upkeep_it_may_create_a_spawn(self):
        game, a = self.upkeep("Yes")
        spawn = next(p for p in a.battlefield if "Spawn" in p.card.name)
        self.assertEqual((game.power(spawn), game.toughness(spawn)), (0, 1))

    def test_it_may_decline(self):
        game, a = self.upkeep("No")
        self.assertFalse(any("Spawn" in p.card.name for p in a.battlefield))

    def test_the_spawn_sacrifices_for_colorless_mana_that_pays_for_a_spell(self):
        t = Table(ONE_SPELL, "Yes", n=0, mine=[Permanent(ZONE)])
        t.game.trigger("upkeep", t.a.battlefield[0], t.a)
        run_stack(t.game)
        t.game.step = "main1"
        t.game._perform(t.a, CAST + "One Draw")
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1)
        self.assertFalse(any("Spawn" in p.card.name for p in t.a.battlefield))

    def test_the_spawn_cannot_make_colored_mana(self):
        t = Table(GREEN_SPELL, "Yes", n=0, mine=[Permanent(ZONE)])
        t.game.trigger("upkeep", t.a.battlefield[0], t.a)
        run_stack(t.game)
        self.assertFalse(castable(t))


GEYSER = real("Mana Geyser", "{3}{R}{R}", "Sorcery", "Add {R} for each tapped land your opponents control.")


class ManaGeyserTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(GEYSER), [])

    def test_it_adds_one_red_for_each_tapped_opposing_land(self):
        tapped = [Permanent(FOREST, tapped=True) for _ in range(3)]
        t = Table(GEYSER, theirs=[*tapped, Permanent(FOREST)]).cast()
        self.assertEqual(t.a.mana_pool, [frozenset("R")] * 3)

    def test_untapped_lands_do_not_count(self):
        t = Table(GEYSER, theirs=[Permanent(FOREST)]).cast()
        self.assertEqual(t.a.mana_pool, [])

    def test_its_own_tapped_lands_do_not_count(self):
        t = Table(GEYSER)
        t.cast()  # paying for the Geyser taps five of my own lands
        self.assertEqual(t.a.mana_pool, [])

    def test_tapped_nonland_permanents_do_not_count(self):
        t = Table(GEYSER, theirs=[Permanent(RELIC, tapped=True), Permanent(OGRE, tapped=True)]).cast()
        self.assertEqual(t.a.mana_pool, [])

    def test_the_red_mana_can_be_spent_on_a_red_spell(self):
        t = Table(GEYSER, theirs=[Permanent(FOREST, tapped=True)]).cast()
        t.a.hand = [RED_SPELL]
        for p in t.a.battlefield:
            p.tapped = True  # all my lands are tapped; only the {R} from the Geyser is left
        t.game._perform(t.a, CAST + "Red Draw")
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1)
