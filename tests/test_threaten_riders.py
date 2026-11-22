"""Issue #843: four threaten cards ("Gain control of target creature until end of turn. Untap that creature. It gains haste until end of
turn."), each with a sentence of its own, from the cards' real Oracle text; all four are fully playable. Goatnap: "If that creature is a
Goat, it also gets +3/+0 until end of turn." (a Goat gets it, an Ogre doesn't). Bond of Passion: "CARDNAME deals 2 damage to any other
target." (not the creature it took). In Thrall to the Pit: "If this spell was kicked, sacrifice that creature at the beginning of the
next end step." (kicked it is sacrificed, not kicked it goes back). Pack's Betrayal: "If you control a Wolf or Werewolf, scry 2." (a
Werewolf: scry; neither: no scry). Their "It gains haste until end of turn." gives the creature taken haste, as Act of Treason's now does
(it gave the spell itself haste)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.families.combat_and_pump import PumpThatIfType
from infernal_machine.game import CAST, KICKER_PROMPT, SCRY_PROMPT, TARGET_PROMPT, Permanent
from tests.helpers import BEAR, OGRE, choose, end_step, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Goatnap", "Bond of Passion", "In Thrall to the Pit", "Pack's Betrayal"]
GOAT = Card(name="Mountain Goat", mana_cost="{R}", type_line="Creature — Goat", power="1", toughness="1")
WEREWOLF = Card(name="Village Werewolf", mana_cost="{1}{G}", type_line="Creature — Human Werewolf", power="2", toughness="2")

# The guards these tests are there to catch (python tools/mutate.py tests.test_threaten_riders).
MUTATIONS = [
    ("infernal_machine/effects/families/combat_and_pump.py", "and (has_type(target.card, self.kind) or self.kind in game.subtypes(target)):",
     ":", "only a creature of that type"),
    ("infernal_machine/effects/families/combat_and_pump.py", "and (has_type(target.card, self.kind) or self.kind in game.subtypes(target)):",
     "and has_type(target.card, self.kind):", "a type an Aura gives counts"),
    ("infernal_machine/casting.py", "                       and not (getattr(effect, \"not_chosen\", False) and any(o[1] is t for t in targets))]",
     "                       ]", "not a target already chosen"),
    ("infernal_machine/effects/families/combat_and_pump.py",
     "if target is not None and game.resolving_item is not None and game.resolving_item.kicked and game.on_battlefield(target):",
     "if target is not None and game.on_battlefield(target):", "only if kicked"),
    ("infernal_machine/effects/outcomes.py", "    Follow(_ItGains, GainControl, set_fields(haste=lambda m: True), strict=False,",
     "    Follow(_ItGains, GainControl, set_fields(haste=lambda m: False), strict=False,", "\"It gains haste\" is the stolen creature's"),
    ("infernal_machine/effects/outcomes.py", 'r"you control an? ([A-Za-z]+) or (?:an? )?([A-Za-z]+)"', 'r"you control an? ([A-Za-z]+) or an? ([A-Za-z]+)"',
     "\"a Wolf or Werewolf\" is read"),
]


def cast(name, theirs, mine=(), kick=False, target=None):
    """Seat 0, with eight lands and `mine`, casts `name` at seat 1's `theirs` (the first one, or `target`)."""
    game, players = table3()
    a, b, _ = game.seats
    b.battlefield = [Permanent(c, sick=False) for c in theirs]
    a.battlefield = lands(8) + [Permanent(c) for c in mine]
    a.hand, a.library = [REAL[name]], [BEAR, BEAR]
    taken = target or b.battlefield[0]
    aim = choose(game, taken, b)
    players[0].policy = lambda prompt, options: ((0 if kick else 1) if KICKER_PROMPT.matches(prompt) else aim(prompt, options))
    game._perform(a, CAST + name)
    run_stack(game)
    return game, players, a, b, taken


def asked(players, kind):
    return [options for prompt, options in players[0].prompts if kind.matches(prompt)]


class ThreatenRiderTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_the_creature_taken_gains_haste(self):
        for name in ("Act of Treason", "Goatnap"):
            game, _, a, _, ogre = cast(name, [OGRE])
            self.assertEqual((ogre in a.battlefield, game.has_keyword(ogre, "haste")), (True, True), name)

    def test_goatnap_pumps_only_a_goat(self):
        game, _, a, _, goat = cast("Goatnap", [GOAT])
        self.assertEqual((goat in a.battlefield, game.power(goat), game.has_keyword(goat, "haste")), (True, 4, True))
        game, _, a, _, ogre = cast("Goatnap", [OGRE])
        self.assertEqual((ogre in a.battlefield, game.power(ogre)), (True, 3))

    def test_a_type_an_aura_gives_counts(self):
        game, _ = table3()
        a, b, _ = game.seats
        ogre = Permanent(OGRE)
        b.battlefield = [ogre, Permanent(REAL["Tall as a Beanstalk"], attached_to=ogre)]  # (+3/+3, reach, and a Giant)
        PumpThatIfType(3, 0, "Giant").resolve(game, a, ogre)  # (Goatnap's sentence, read for a Giant: no real Aura makes a Goat)
        self.assertEqual(game.power(ogre), 9)

    def test_bond_of_passion_deals_its_damage_to_another_target(self):
        game, players, a, b, ogre = cast("Bond of Passion", [OGRE])
        second = asked(players, TARGET_PROMPT)[1]
        self.assertFalse(any(game._target_label(ogre) in o for o in second))
        self.assertEqual((ogre in a.battlefield, 40 - b.life), (True, 2))

    def test_in_thrall_kicked_sacrifices_it_at_end_step(self):
        game, _, a, b, ogre = cast("In Thrall to the Pit", [OGRE], kick=True)
        end_step(game, a)
        self.assertEqual(([p.card.name for p in a.battlefield + b.battlefield if p.card.name == "Ogre"], [c.name for c in b.graveyard]),
                         ([], ["Ogre"]))
        game, _, a, b, ogre = cast("In Thrall to the Pit", [OGRE])
        end_step(game, a)
        self.assertEqual(([c.name for c in b.graveyard], ogre in a.battlefield), ([], True))  # (not kicked: it goes back at cleanup)

    def test_packs_betrayal_scries_only_with_a_wolf_or_werewolf(self):
        _, players, _, _, _ = cast("Pack's Betrayal", [OGRE], mine=[WEREWOLF])
        self.assertEqual(len(asked(players, SCRY_PROMPT)), 2)
        _, players, _, _, _ = cast("Pack's Betrayal", [OGRE])
        self.assertEqual(asked(players, SCRY_PROMPT), [])


if __name__ == "__main__":
    unittest.main()
