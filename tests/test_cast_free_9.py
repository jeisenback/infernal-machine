"""Casting without paying the mana cost, batch 9, from the cards' real Oracle text: Tibalt's Trickery (counter, mill 1 to 3 at random, exile
until a nonland card with another name, which the spell's controller may cast free; the rest go to the bottom), Sunforger (an "Unattach this
Equipment" cost, and "Search your library for a red or white instant card with mana value 4 or less and cast that card without paying its
mana cost. Then shuffle.") and The Key to the Vault (look at that many cards, exile a nonland one, the rest to the bottom, cast it free)."""

import unittest

from infernal_machine.game import ACTIVATE, CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, attack_all, lands, pick, real, run_stack, table, table3, take_turn_attacking

TRICKERY = real("Tibalt's Trickery", "{1}{R}", "Instant", "Counter target spell. Choose 1, 2, or 3 at random. Its controller mills that many "
                "cards, then exiles cards from the top of their library until they exile a nonland card with a different name than that spell. "
                "They may cast that card without paying its mana cost. Then they put the exiled cards on the bottom of their library in a "
                "random order.", colors=("R",))
SUNFORGER = real("Sunforger", "{3}", "Artifact — Equipment", "Equipped creature gets +4/+0.\n{R}{W}, Unattach this Equipment: Search your "
                 "library for a red or white instant card with mana value 4 or less and cast that card without paying its mana cost. Then "
                 "shuffle.\nEquip {3}")
KEY = real("The Key to the Vault", "{1}{U}", "Legendary Artifact — Equipment", "Whenever equipped creature deals combat damage to a player, "
           "look at that many cards from the top of your library. You may exile a nonland card from among them. Put the rest on the bottom of "
           "your library in a random order. You may cast the exiled card without paying its mana cost.\nEquip {2}{U}", colors=("U",))
CARDS = (TRICKERY, SUNFORGER, KEY)

ALARM = real("Raise the Alarm", "{1}{W}", "Instant", "Create two 1/1 white Soldier creature tokens.", colors=("W",))
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.", colors=("G",))
FLARE = real("Blaze of Glory", "{W}", "Instant", "Cast this spell only during combat before blockers are declared.\nTarget creature defending "
             "player controls can block any number of creatures this turn. It blocks each attacking creature this turn if able.", colors=("W",))
COMMAND = real("Boros Charm", "{R}{W}", "Instant", "Choose one —\n• Boros Charm deals 4 damage to target player or planeswalker.\n• Permanents "
               "you control gain indestructible until end of turn.\n• Target creature gains double strike until end of turn.",
               colors=("R", "W"))
BIG = real("Gerrard's Verdict", "{W}{B}", "Sorcery", "Target player discards two cards. You gain 3 life for each land card discarded this way.",
           colors=("W", "B"))


def names(cards):
    return [c.name for c in cards]


def soldiers(seat):
    return sum(p.card.name == "Soldier" for p in seat.battlefield)


class CastFree9Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_tibalts_trickery_counters_and_gives_a_free_spell_of_another_name(self):
        for answer, cast in (("Yes", True), ("No", False)):
            game, _ = table3(pick("Spell: Ogre"), pick(answer))
            a, b, _ = game.seats
            ogre_spell = StackItem(OGRE, b)
            game.stack = [ogre_spell]
            b.library = [FOREST, FOREST, FOREST, OGRE, FOREST, BEAR, FOREST, FOREST]
            a.hand, a.battlefield = [TRICKERY], lands(2)
            game._perform(a, CAST + TRICKERY.name)
            run_stack(game)
            on_battlefield = any(p.card is BEAR for p in b.battlefield)
            self.assertEqual((on_battlefield, OGRE in b.graveyard, b.exile), (cast, True, []), answer)  # the Ogre with the same name is passed over
            self.assertEqual(names(b.library).count("Ogre"), 1)  # the library's Ogre went to the bottom
            self.assertEqual("Bear" in names(b.library), not cast)
            self.assertIn(len(b.graveyard) - 1, (1, 2, 3))  # the countered Ogre, and one to three cards milled

    def test_sunforger_unattaches_and_casts_a_red_or_white_instant_free(self):
        offered = []

        def policy(prompt, options):
            offered.append(list(options))
            return next((i for i, o in enumerate(options) if o == "Raise the Alarm"), 0)
        game, _ = table3(policy)
        a = game.seats[0]
        bear = Permanent(BEAR)
        forger = Permanent(SUNFORGER, attached_to=bear)
        a.battlefield = [bear, forger] + lands(2)
        a.library = [GROWTH, FLARE, ALARM, BIG, COMMAND, FOREST]
        activate(game, a, "Unattach this Equipment")
        self.assertIsNone(forger.attached_to)
        self.assertEqual(soldiers(a), 2)  # cast without paying: the two lands were spent on {R}{W}
        search = next(o for o in offered if "Raise the Alarm" in o)
        self.assertNotIn("Giant Growth", search)  # green
        self.assertNotIn("Gerrard's Verdict", search)  # a sorcery
        self.assertIn("Boros Charm", search)
        self.assertNotIn("Raise the Alarm", names(a.library))

    def test_sunforger_cant_be_used_unattached(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR), Permanent(SUNFORGER)] + lands(2)
        a.library = [ALARM]
        self.assertFalse(any(x.startswith(ACTIVATE) and "Unattach" in x for x in game.legal_actions(a)))

    def test_the_key_to_the_vault_looks_at_as_many_as_the_damage(self):
        for answer, cast in (("Yes", True), ("No", False)):
            def policy(prompt, options):
                return attack_all(prompt, options) if any("ttack" in o for o in options) else pick("Bear", answer)(prompt, options)
            game, _, _ = table(policy)
            a = game.seats[0]
            ogre = Permanent(OGRE, sick=False)
            a.battlefield = [ogre, Permanent(KEY, attached_to=ogre)]
            a.library = [FOREST, FOREST, FOREST, BEAR, OGRE] + [FOREST] * 5  # the draw step takes the first; the Ogre's 3 damage: the next three
            take_turn_attacking(game, a)
            on_battlefield = any(p.card is BEAR for p in a.battlefield)
            self.assertEqual((on_battlefield, BEAR in a.exile), (cast, not cast), answer)
            self.assertEqual(names(a.library)[0], "Ogre")  # the fourth card was not looked at; the two Forests went to the bottom


if __name__ == "__main__":
    unittest.main()
