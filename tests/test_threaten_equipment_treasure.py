"""Issue #843, the second part: three more threaten cards ("Gain control of target creature until end of turn. Untap that creature. It
gains haste until end of turn."), each with a sentence of its own, from the cards' real Oracle text; all three are fully playable.
Price of Loyalty: "If mana from a Treasure was spent to cast this spell, that creature gets +2/+0 until end of turn." (paid with a
Treasure the stolen Ogre is a 5/3; with lands only, a 3/3). Awaken the Sleeper: "If it's equipped, you may destroy all Equipment attached
to that creature." (its Equipment is destroyed; an unequipped creature asks nothing). Unexpected Request: "You may attach an Equipment you
control to that creature. If you do, unattach it at the beginning of the next end step." (attached, then unattached at the end step,
wherever it is attached by then; declined, it stays where it was). Only mana spent on the spell itself counts as a Treasure's: not a
Treasure that paid a Signet's {1}."""

import unittest

from infernal_machine.effects import TREASURE
from infernal_machine.game import ATTACH_EQUIPMENT_PROMPT, CAST, DESTROY_EQUIPMENT_PROMPT, NO_EQUIPMENT, Permanent
from tests.helpers import BEAR, OGRE, choose, end_step, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Price of Loyalty", "Awaken the Sleeper", "Unexpected Request"]
SPLITTER = REAL["Vulshok Splitter"]  # (an Equipment: "Equipped creature gets +2/+0.")
SIGNET = real("Dimir Signet", "{2}", "Artifact", "{1}, {T}: Add {U}{B}.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_threaten_equipment_treasure).
MUTATIONS = [
    ("infernal_machine/casting.py", 'treasure_mana=any(p is not None and "Treasure" in p.card.type_line for p in tapped.spent_from))',
     "treasure_mana=True)", "only if Treasure mana paid for it"),
    ("infernal_machine/casting.py", 'treasure_mana=any(p is not None and "Treasure" in p.card.type_line for p in tapped.spent_from))',
     'treasure_mana=any("Treasure" in p.card.type_line for p in tapped))', "not a Treasure that paid a Signet's own cost"),
    ("infernal_machine/game.py", "        if equipment and seat.player.choose(DESTROY_EQUIPMENT_PROMPT(creature.card.name), YES_NO) == 0:",
     "        if seat.player.choose(DESTROY_EQUIPMENT_PROMPT(creature.card.name), YES_NO) == 0:", "asked only if it's equipped"),
    ("infernal_machine/game.py", "self.at_end_step.append((fire_turn, lambda: self.detach(equipment) if", "(fire_turn, lambda: None if",
     "unattached at the end step"),
    ("infernal_machine/game.py", "lambda: self.detach(equipment) if equipment.attached_to is not None and",
     "lambda: self.detach(equipment) if equipment.attached_to is creature and", "unattached wherever it is"),
]


def cast(name, mine, theirs_equipped=False, policy=None):
    """Seat 0, with `mine` (its lands and the rest), casts `name` at seat 1's Ogre (wearing a Vulshok Splitter if `theirs_equipped`)."""
    game, players = table3()
    a, b, _ = game.seats
    ogre = Permanent(OGRE, sick=False)
    b.battlefield = [ogre]
    if theirs_equipped:
        b.battlefield.append(Permanent(SPLITTER, attached_to=ogre))
    a.battlefield, a.hand = list(mine), [REAL[name]]
    aim = choose(game, ogre)
    players[0].policy = lambda prompt, options: policy(prompt, options) if policy and (policy(prompt, options) is not None) else aim(prompt, options)
    game._perform(a, CAST + name)
    run_stack(game)
    return game, players, a, b, ogre


def asked(players, kind):
    return [options for prompt, options in players[0].prompts if kind.matches(prompt)]


class ThreatenEquipmentTreasureTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_treasure_mana_pumps_the_stolen_creature(self):
        game, _, a, _, ogre = cast("Price of Loyalty", lands(2) + [Permanent(TREASURE)])  # ({2}{R}: the Treasure has to pay)
        self.assertEqual((ogre in a.battlefield, game.power(ogre)), (True, 5))
        game, _, a, _, ogre = cast("Price of Loyalty", lands(3))
        self.assertEqual((ogre in a.battlefield, game.power(ogre)), (True, 3))

    def test_a_treasure_that_only_paid_a_signets_cost_is_not_mana_spent_on_the_spell(self):
        game, _ = table3()
        a = game.seats[0]
        signet, treasure, thing = Permanent(SIGNET), Permanent(TREASURE), real("Thing", "{U}{B}", "Sorcery", "Draw a card.")
        a.battlefield, a.hand = [treasure, signet], [thing]  # (the Treasure can only pay the Signet's {1}; the Signet's {U}{B} pays the spell)
        game._perform(a, CAST + thing.name)
        (item,) = game.stack
        self.assertEqual((treasure in a.battlefield, item.treasure_mana), (False, False))

    def test_the_equipment_on_it_may_be_destroyed(self):
        _, players, _, b, ogre = cast("Awaken the Sleeper", lands(4), theirs_equipped=True,
                                      policy=lambda prompt, options: 0 if DESTROY_EQUIPMENT_PROMPT.matches(prompt) else None)
        self.assertEqual([p.card.name for p in b.battlefield], [])  # (the Ogre is seat 0's now; its Splitter is destroyed)
        self.assertEqual([c.name for c in b.graveyard], [SPLITTER.name])
        _, players, _, _, _ = cast("Awaken the Sleeper", lands(4))
        self.assertEqual(asked(players, DESTROY_EQUIPMENT_PROMPT), [])

    def test_an_equipment_is_attached_until_the_end_step(self):
        splitter = Permanent(SPLITTER)
        game, _, a, _, ogre = cast("Unexpected Request", lands(3) + [splitter],
                                   policy=lambda prompt, options: 1 if ATTACH_EQUIPMENT_PROMPT.matches(prompt) else None)
        self.assertEqual((splitter.attached_to, game.power(ogre)), (ogre, 5))
        end_step(game, a)
        self.assertIsNone(splitter.attached_to)

    def test_moved_meanwhile_it_is_still_unattached(self):
        splitter = Permanent(SPLITTER)
        game, _, a, _, ogre = cast("Unexpected Request", lands(3) + [splitter],
                                   policy=lambda prompt, options: 1 if ATTACH_EQUIPMENT_PROMPT.matches(prompt) else None)
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        game.attach(splitter, bear)  # (moved by an equip ability, say)
        end_step(game, a)
        self.assertIsNone(splitter.attached_to)

    def test_declined_nothing_is_attached(self):
        splitter = Permanent(SPLITTER)
        _, players, _, _, _ = cast("Unexpected Request", lands(3) + [splitter],
                                   policy=lambda prompt, options: options.index(NO_EQUIPMENT) if ATTACH_EQUIPMENT_PROMPT.matches(prompt) else None)
        self.assertEqual((splitter.attached_to, len(asked(players, ATTACH_EQUIPMENT_PROMPT))), (None, 1))


if __name__ == "__main__":
    unittest.main()
