"""Issue #796: Kinship (an ability word, CR 207.2c), "At the beginning of your upkeep, you may look at the top card of your library. If it
shares a creature type with this creature, you may reveal it. If you do, <reward>.", from the cards' real Oracle text. All twelve cards
whose only gap it was are fully playable. On Wolf-Skull Shaman, the most played with a reward the other templates read: a card that
shares a type (a creature, or a kindred card) may be revealed for the token, one that shares none gives nothing, and a declined reveal
gives nothing. Winnower Patrol's counter goes on it only while it is on the battlefield; Leaf-Crowned Elder casts the revealed card for
free; Waterspout Weavers' "each creature you control gains flying" is read as "creatures you control gain flying"."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import KINSHIP_PROMPT, Permanent
from tests.helpers import BEAR, begin, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Leaf-Crowned Elder", "Wolf-Skull Shaman", "Sensation Gorger", "Nightshade Schemers", "Wandering Graybeard", "Mudbutton Clanger",
         "Kithkin Zephyrnaut", "Ink Dissolver", "Waterspout Weavers", "Squeaking Pie Grubfellows", "Winnower Patrol", "Pyroclast Consul"]
ELF = Card(name="Elvish Scout", mana_cost="{G}", type_line="Creature — Elf Scout", power="1", toughness="1")
KINDRED_ELF = Card(name="Elvish Ritual", mana_cost="{G}", type_line="Kindred Instant — Elf", oracle_text="Draw a card.")
OGRE = Card(name="Hill Ogre", mana_cost="{2}{R}", type_line="Creature — Ogre", power="3", toughness="3")
SAPLING = Card(name="Treefolk Sapling", mana_cost="{3}{G}", type_line="Creature — Treefolk", power="2", toughness="5")
MERFOLK = Card(name="Merfolk Scout", mana_cost="{U}", type_line="Creature — Merfolk", power="1", toughness="1")

# The guards these tests are there to catch (python tools/mutate.py tests.test_kinship).
MUTATIONS = [
    ("infernal_machine/game.py", "        if not kinds & mine or seat.player.choose(KINSHIP_PROMPT", "        if seat.player.choose(KINSHIP_PROMPT",
     "only a card that shares a creature type"),
    ("infernal_machine/game.py", "if not kinds & mine or seat.player.choose(KINSHIP_PROMPT(source.card.name), [\"Reveal\", \"Don't reveal\"]) != 0:",
     "if not kinds & mine:", "the reveal is the player's choice"),
    ("infernal_machine/game.py", ' or "Kindred" in card.type_line else set()', " else set()", "a kindred card has creature types"),
    ("infernal_machine/game.py", "source if binding(effect) == SOURCE and self.on_battlefield(source) else None)",
     "source if binding(effect) == SOURCE else None)", "this creature's reward only while it is there"),
    ("infernal_machine/game.py", "        if play_free:\n            if not is_land(card)", "        if False:\n            if not is_land(card)",
     "Leaf-Crowned Elder casts the card"),
    ("infernal_machine/effects/outcomes.py", "    if m := _EACH_YOURS_UNTIL_EOT.fullmatch(sentence):", "    if False:",
     "each creature you control gains: creatures you control gain"),
]


def decline(prompt, options):
    """Use the trigger, but don't reveal."""
    return 1 if KINSHIP_PROMPT.matches(prompt) else 0


def upkeep(name, top, policy=None, gone_first=False):
    """Seat 0 has `name` (and a Bear) with `top` on top of its library; its upkeep begins and the trigger resolves (after the creature
    has left the battlefield, with `gone_first`)."""
    game, _ = table3(policy)
    a = game.seats[0]
    source = Permanent(REAL[name])
    a.battlefield = [source, Permanent(BEAR)]
    a.library = [top, BEAR]
    if gone_first:
        game.step = "upkeep"
        game._turn_based_actions(a)
        game._put_triggers_on_stack()
        game.destroy(source)
        run_stack(game)
    else:
        begin(game, "upkeep", a)
    return game, a, source


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class KinshipTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_card_that_shares_a_creature_type_may_be_revealed_for_the_reward(self):
        for top in (ELF, KINDRED_ELF):
            _, a, _ = upkeep("Wolf-Skull Shaman", top)
            self.assertEqual((names(a), a.library), (["Bear", "Wolf", "Wolf-Skull Shaman"], [top, BEAR]), top.name)

    def test_a_card_that_shares_none_or_a_declined_reveal_gives_nothing(self):
        for top, policy in ((OGRE, None), (ELF, decline)):
            game, a, _ = upkeep("Wolf-Skull Shaman", top, policy)
            self.assertEqual((names(a), a.library), (["Bear", "Wolf-Skull Shaman"], [top, BEAR]), top.name)
        asked = [p for p, _ in upkeep("Wolf-Skull Shaman", OGRE)[0].seats[0].player.prompts if KINSHIP_PROMPT.matches(p)]
        self.assertEqual(asked, [])  # (nothing to reveal: not asked)

    def test_the_counter_goes_on_this_creature_only_while_it_is_there(self):
        _, _, patrol = upkeep("Winnower Patrol", ELF)
        self.assertEqual(patrol.counters, {"+1/+1": 1})
        _, a, patrol = upkeep("Winnower Patrol", ELF, gone_first=True)
        self.assertEqual((patrol.counters, [c.name for c in a.graveyard]), ({}, ["Winnower Patrol"]))

    def test_leaf_crowned_elder_casts_the_revealed_card_for_free(self):
        _, a, _ = upkeep("Leaf-Crowned Elder", SAPLING)
        self.assertEqual((names(a), a.library), (["Bear", "Leaf-Crowned Elder", "Treefolk Sapling"], [BEAR]))
        _, a, _ = upkeep("Leaf-Crowned Elder", ELF)
        self.assertEqual((names(a), a.library), (["Bear", "Leaf-Crowned Elder"], [ELF, BEAR]))

    def test_waterspout_weavers_gives_each_creature_you_control_flying(self):
        game, a, _ = upkeep("Waterspout Weavers", MERFOLK)
        self.assertTrue(all(game.has_keyword(p, "flying") for p in a.battlefield))
        game, a, _ = upkeep("Waterspout Weavers", OGRE)
        self.assertFalse(any(game.has_keyword(p, "flying") for p in a.battlefield))


if __name__ == "__main__":
    unittest.main()
