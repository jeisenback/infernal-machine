"""Standard's Dimir Midrange deck, from its cards' real Oracle text: The Wondrous Wasp and Tishana's Tidebinder (a permanent loses all
abilities for as long as the source remains), Wan Shi Tong, Librarian (X counters, half X cards; a counter and a card when an opponent
searches) and We Say Thee Nay! (Teamwork)."""

import unittest

from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, TEAMWORK_NONE, TEAMWORK_PROMPT, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, lands, real, run_stack, script, table3

WASP = real("The Wondrous Wasp", "{1}{U}", "Legendary Creature — Human Hero", "Flash\nFlying\nWasp's Sting — When The Wondrous Wasp enters, "
            "tap up to one target creature. It loses all abilities for as long as The Wondrous Wasp remains on the battlefield.", "2", "1",
            colors=("U",))
TIDEBINDER = real("Tishana's Tidebinder", "{2}{U}", "Creature — Merfolk Wizard", "Flash\nWhen this creature enters, counter up to one target "
                  "activated or triggered ability. If an ability of an artifact, creature, or planeswalker is countered this way, that "
                  "permanent loses all abilities for as long as this creature remains on the battlefield. (Mana abilities can't be "
                  "targeted.)", "3", "2", colors=("U",))
WAN_SHI_TONG = real("Wan Shi Tong, Librarian", "{X}{U}{U}", "Legendary Creature — Bird Spirit", "Flash\nFlying, vigilance\nWhen Wan Shi Tong "
                    "enters, put X +1/+1 counters on him. Then draw half X cards, rounded down.\nWhenever an opponent searches their library, "
                    "put a +1/+1 counter on Wan Shi Tong and draw a card.", "1", "1", colors=("U",))
NAY = real("We Say Thee Nay!", "{1}{U}", "Instant — Arcane", "Teamwork 2 (As an additional cost to cast this spell, you may tap any number of "
           "creatures you control with total power 2 or more.)\nCounter target spell unless its controller pays {2}. Counter that spell "
           "unless its controller pays {4} instead if this spell was cast using teamwork.", colors=("U",))
FLIER = real("Hawk", "{1}{W}", "Creature — Bird", "Flying", "1", "1", colors=("W",))
CONFIDANT = real("Dark Confidant", "{1}{B}", "Creature — Human Wizard", "At the beginning of your upkeep, reveal the top card of your library "
                 "and put that card into your hand. You lose life equal to its mana value.", "2", "1", colors=("B",))
STIFLE = real("Stifle", "{U}", "Instant", "Counter target activated or triggered ability. (Mana abilities can't be targeted.)",
              colors=("U",))
OMEN = real("Dark Omen", "{1}{B}", "Enchantment", "At the beginning of your upkeep, you lose 1 life.", colors=("B",))


def table(*answers, battlefield=(), hand=()):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield, a.hand = list(battlefield), list(hand)
    for seat in game.seats:
        seat.library = [FOREST] * 6
    return game, a, b, c


def upkeep_trigger(game, seat, permanent):
    """`permanent`'s upkeep trigger, on the stack."""
    ability = next(t for t in triggered_abilities(permanent.card) if t.event == "upkeep")
    item = StackItem(permanent.card, seat, list(ability.effects), [], ability, permanent)
    game.stack.append(item)
    return item


def resolve_above(game, item):
    """Resolve what is above `item` on the stack, one at a time, putting each new trigger on the stack as it happens."""
    while game.stack and game.stack[-1] is not item:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()


class StandardDimirMidrangeTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (WASP, TIDEBINDER, WAN_SHI_TONG, NAY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_wondrous_wasp_taps_and_strips_a_creature_while_it_stays(self):
        hawk = Permanent(FLIER)
        game, a, b, _ = table("Hawk", battlefield=lands(2), hand=[WASP])
        b.battlefield = [hawk]
        game._perform(a, CAST + "The Wondrous Wasp")
        run_stack(game)
        self.assertEqual((hawk.tapped, game.has_keyword(hawk, "flying")), (True, False))
        wasp = next(p for p in a.battlefield if p.card is WASP)
        game._leave_battlefield(wasp, "destroyed")
        self.assertTrue(game.has_keyword(hawk, "flying"))

    def test_the_wondrous_wasp_may_target_nothing(self):
        hawk = Permanent(FLIER)
        game, a, b, _ = table("No target", battlefield=lands(2), hand=[WASP])
        b.battlefield = [hawk]
        game._perform(a, CAST + "The Wondrous Wasp")
        run_stack(game)
        self.assertEqual((hawk.tapped, game.has_keyword(hawk, "flying")), (False, True))

    def test_tishanas_tidebinder_counters_a_creatures_trigger_and_strips_the_creature(self):
        confidant = Permanent(CONFIDANT)
        game, a, b, _ = table("Ability: Dark Confidant", battlefield=lands(3), hand=[TIDEBINDER])
        b.battlefield = [confidant]
        trigger = upkeep_trigger(game, b, confidant)
        game._perform(a, CAST + "Tishana's Tidebinder")
        resolve_above(game, trigger)
        self.assertNotIn(trigger, game.stack)
        self.assertTrue(game.loses_abilities(confidant))
        binder = next(p for p in a.battlefield if p.card is TIDEBINDER)
        game._leave_battlefield(binder, "destroyed")
        self.assertFalse(game.loses_abilities(confidant))

    def test_tishanas_tidebinder_counters_an_enchantments_trigger_without_stripping_it(self):
        omen = Permanent(OMEN)
        game, a, b, _ = table("Ability: Dark Omen", battlefield=lands(3), hand=[TIDEBINDER])
        b.battlefield = [omen]
        trigger = upkeep_trigger(game, b, omen)
        life = b.life
        game._perform(a, CAST + "Tishana's Tidebinder")
        resolve_above(game, trigger)
        run_stack(game)
        self.assertNotIn(trigger, game.stack)
        self.assertEqual((b.life, game.loses_abilities(omen)), (life, False))

    def test_stifle_counters_a_trigger_without_stripping_and_cannot_target_a_spell(self):
        confidant = Permanent(CONFIDANT)
        game, a, b, _ = table("Ability: Dark Confidant", battlefield=lands(1), hand=[STIFLE])
        b.battlefield = [confidant]
        game.stack.append(StackItem(BEAR, b))  # a spell is not an activated or triggered ability
        trigger = upkeep_trigger(game, b, confidant)
        asked = []
        choose = a.player.choose
        a.player.choose = lambda prompt, options: asked.append(list(options)) or choose(prompt, options)
        game._perform(a, CAST + "Stifle")
        game._resolve(game.stack.pop())
        self.assertNotIn(trigger, game.stack)
        self.assertFalse(game.loses_abilities(confidant))
        self.assertEqual([o for options in asked for o in options if "Bear" in o], [])

    def test_wan_shi_tong_gets_x_counters_and_draws_half_x(self):
        game, a, _, _ = table("4", battlefield=lands(6), hand=[WAN_SHI_TONG])
        game._perform(a, CAST + "Wan Shi Tong, Librarian")
        run_stack(game)
        wan = next(p for p in a.battlefield if p.card is WAN_SHI_TONG)
        self.assertEqual((wan.counters.get("+1/+1"), len(a.hand)), (4, 2))

    def test_wan_shi_tong_grows_when_an_opponent_searches(self):
        wan = Permanent(WAN_SHI_TONG)
        game, a, b, _ = table(battlefield=[wan])
        game.happened("searched", b)
        run_stack(game)
        self.assertEqual((wan.counters.get("+1/+1"), len(a.hand)), (1, 1))
        game.happened("searched", a)  # its own controller searching is not an opponent's search
        run_stack(game)
        self.assertEqual((wan.counters.get("+1/+1"), len(a.hand)), (1, 1))

    def nay(self, *answers):
        ogre = Permanent(OGRE)
        game, a, b, _ = table(*answers, battlefield=lands(2) + [ogre], hand=[NAY])
        b.battlefield = lands(3)
        spell = StackItem(BEAR, b)
        game.stack.append(spell)
        game._perform(a, CAST + "We Say Thee Nay!")
        run_stack(game)
        return ogre, b, spell

    def test_we_say_thee_nay_with_teamwork_asks_four(self):
        ogre, b, _ = self.nay("Spell: Bear", "Ogre")
        self.assertTrue(ogre.tapped)
        self.assertEqual(b.graveyard, [BEAR])  # three lands can't pay {4}

    def test_we_say_thee_nay_without_enough_untapped_power_has_no_teamwork(self):
        game, a, b, _ = table("Spell: Bear", "Hawk", battlefield=lands(2) + [Permanent(OGRE, tapped=True), Permanent(FLIER)], hand=[NAY])
        b.battlefield = lands(3)
        game.stack.append(StackItem(BEAR, b))
        asked = []
        choose = a.player.choose
        a.player.choose = lambda prompt, options: asked.append(prompt) or choose(prompt, options)
        game._perform(a, CAST + "We Say Thee Nay!")
        run_stack(game)
        self.assertEqual(b.graveyard, [])  # only {2} was asked, and paid
        self.assertFalse(any(TEAMWORK_PROMPT.matches(p) for p in asked))  # the untapped Hawk alone is not enough: no question

    def test_we_say_thee_nay_without_teamwork_asks_two(self):
        ogre, b, _ = self.nay("Spell: Bear", TEAMWORK_NONE)
        self.assertFalse(ogre.tapped)
        self.assertEqual(b.graveyard, [])  # {2} was paid
        self.assertEqual(sum(p.tapped for p in b.battlefield), 2)


if __name__ == "__main__":
    unittest.main()
