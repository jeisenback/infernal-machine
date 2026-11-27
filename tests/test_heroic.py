"""Heroic, "Whenever you cast a spell that targets this creature, ..." (the event `cast_targeting_self`), from the cards' real Oracle
text. All 42 cards whose only gap it was are fully playable. Hero of Iroas gets a +1/+1 counter when its controller casts Giant
Growth on it, and keeps the pump too; not when Giant Growth targets another creature, not when an opponent casts it on the Hero, and
not for an activated ability that targets it (an ability isn't cast). Seeds of Strength, targeting Satyr Hoplite three times and Hero
of Iroas never, gives the Hoplite one counter ("whenever you cast a spell": once for the spell) and the Hero none."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, activate, choose, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Agent of the Fates", "Akroan Crusader", "Akroan Line Breaker", "Akroan Skyguard", "Anax and Cymede", "Arena Athlete",
         "Artisan of Forms", "Ashiok's Adept", "Battlewise Hoplite", "Brigone, Soldier of Meletis", "Centaur Battlemaster",
         "Chorus of the Tides", "Cleon, Merry Champion", "Dawnbringer Charioteers", "Elite Skirmisher", "Fabled Hero", "Gnarlback Rhino",
         "Hero of Iroas", "Hero of Leina Tower", "Hero of the Games", "Hero of the Nyxborn", "Hero of the Pride", "Hero of the Winds",
         "Heroes of the Revel", "Labyrinth Champion", "Lagonna-Band Trailblazer", "Meletis Astronomer", "Phalanx Leader",
         "Pheres-Band Thunderhoof", "Satyr Hoplite", "Setessan Battle Priest", "Setessan Oathsworn", "Staunch-Hearted Warrior",
         "Tenth District Legionnaire", "Tethmos High Priest", "Tormented Hero", "Triton Cavalry", "Triton Fortune Hunter",
         "Vanguard of Brimaz", "War-Wing Siren", "Wavecrash Triton", "Wingsteed Rider"]
HERO, HOPLITE, GROWTH, SEEDS = REAL["Hero of Iroas"], REAL["Satyr Hoplite"], REAL["Giant Growth"], REAL["Seeds of Strength"]
WAND = real("Pump Wand", "{1}", "Artifact", "{T}: Target creature gets +1/+1 until end of turn.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_heroic).
MUTATIONS = [
    ("infernal_machine/casting.py", "if isinstance(t, g.Permanent) and self.game.on_battlefield(t) and self.game.controller(t) is item.controller}",
     "if isinstance(t, g.Permanent) and self.game.on_battlefield(t)}", "only \"you cast\": the caster's own creature"),
    ("infernal_machine/casting.py", "            self.game.trigger(\"cast_targeting_self\", hero, item.controller)", "            pass",
     "the spell's targets trigger it"),
    ("infernal_machine/casting.py", "        heroes = {id(t): t for chosen in item.targets", "        heroes = {id(t) + i: t for i, chosen in enumerate(item.targets)",
     "once for the spell"),
]


def cast_at(spell, *targets, mine=(HERO,), caster=0):
    """Seat 0 has `mine`; seat `caster` casts `spell` (with lands enough), aimed at `targets` in order."""
    game, players = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c, sick=False) for c in mine]
    who = game.seats[caster]
    who.battlefield += lands(4)
    who.hand = [spell]
    aimed = [p for c in targets for p in a.battlefield + b.battlefield if p.card is c]
    players[caster].policy = choose(game, *aimed)
    game._perform(who, CAST + spell.name)
    run_stack(game)
    return game, a


class HeroicTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_spell_you_cast_on_it(self):
        game, a = cast_at(GROWTH, HERO)
        (hero,) = a.battlefield[:1]
        self.assertEqual((hero.counters.get("+1/+1"), game.power(hero)), (1, 6))  # (2/2, a counter and +3/+3)

    def test_not_another_creature_nor_an_opponents_spell(self):
        _, a = cast_at(GROWTH, BEAR, mine=(HERO, BEAR))
        self.assertEqual(a.battlefield[0].counters.get("+1/+1"), None)
        _, a = cast_at(GROWTH, HERO, caster=1)
        self.assertEqual(a.battlefield[0].counters.get("+1/+1"), None)

    def test_not_an_ability(self):
        game, _ = table3()
        a = game.seats[0]
        hero = Permanent(HERO, sick=False)
        a.battlefield = [hero, Permanent(WAND)]
        game.seats[0].player.policy = choose(game, hero)
        activate(game, a, "Target creature")
        self.assertEqual(hero.counters.get("+1/+1"), None)

    def test_once_for_the_spell(self):
        _, a = cast_at(SEEDS, HOPLITE, HOPLITE, HOPLITE, mine=(HOPLITE, HERO))
        hoplite, hero = a.battlefield[:2]
        self.assertEqual((hoplite.counters.get("+1/+1"), hero.counters.get("+1/+1")), (1, None))


if __name__ == "__main__":
    unittest.main()
