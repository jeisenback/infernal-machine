import dataclasses
import unittest

from infernal_machine.effects import activated_abilities
from infernal_machine.game import ACTIVATE, MAY_PAY_PROMPT, PASS, TARGET_PROMPT, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table

RINGS = real("Rings of Brighthearth", "{3}", "Artifact",
             "Whenever you activate an ability, if it isn't a mana ability, you may pay {2}. If you do, copy that ability. You may choose new "
             "targets for the copy.")
KURKESH = real("Kurkesh, Onakke Ancient", "{2}{R}{R}", "Legendary Creature — Ogre Spirit",
               "Whenever you activate an ability of an artifact, if it isn't a mana ability, you may pay {R}. If you do, copy that ability. "
               "You may choose new targets for the copy.", "4", "3")
BRACERS = real("Illusionist's Bracers", "{2}", "Artifact — Equipment",
               "Whenever an ability of equipped creature is activated, if it isn't a mana ability, copy that ability. You may choose new "
               "targets for the copy.\nEquip {3}")
RESONATOR = real("Strionic Resonator", "{2}", "Artifact",
                 '{2}, {T}: Copy target triggered ability you control. You may choose new targets for the copy. (A triggered ability uses the '
                 'words "when," "whenever," or "at.")')
FANTASTIC = real("Mister Fantastic", "{2}{U}", "Legendary Creature — Human Scientist Hero",
                 "Reach, vigilance\nAt the beginning of combat on your turn, if you've cast a noncreature spell this turn, draw a card.\n"
                 "{R}{G}{W}{U}, {T}: Copy target triggered ability you control twice. You may choose new targets for the copies.", "4", "4")
SORCERER = real("Prodigal Sorcerer", "{2}{U}", "Creature — Human Wizard", "{T}: This creature deals 1 damage to any target.", "1", "1")
PINGER_RELIC = real("Pinging Relic", "{1}", "Artifact", "{T}: This artifact deals 1 damage to any target.")
HEALER = real("Healing Hall", "{1}{W}", "Creature — Human Cleric", "When this creature enters, you gain 2 life.", "1", "1")
MANA_ROCK = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")


def policy(activate, pay=True):
    """Activate the card named `activate`; target the opponent; pay (or not) when asked; otherwise pass."""
    def choose(prompt, options):
        if prompt.startswith(MAY_PAY_PROMPT):
            return 0 if pay else 1
        if prompt.startswith(TARGET_PROMPT) or "target" in prompt.lower():
            return next((i for i, o in enumerate(options) if "seat 1" in o), 0)
        return next((i for i, o in enumerate(options) if o.startswith(ACTIVATE + activate)), options.index(PASS) if PASS in options else 0)
    return choose


def ping(battlefield, activate, pay=True):
    game, _, _ = table(policy(activate, pay))
    a, b = game.seats
    a.battlefield = lands(4) + battlefield
    game._priority_round(a)
    run_stack(game)
    return game, a, b


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (RINGS, KURKESH, BRACERS, RESONATOR, FANTASTIC):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ActivationCopyTests(unittest.TestCase):
    def test_paying_copies_the_ability(self):
        _, _, b = ping([Permanent(RINGS), Permanent(SORCERER, sick=False)], "Prodigal Sorcerer")
        self.assertEqual(b.life, 38)

    def test_not_paying_leaves_one_activation(self):
        _, _, b = ping([Permanent(RINGS), Permanent(SORCERER, sick=False)], "Prodigal Sorcerer", pay=False)
        self.assertEqual(b.life, 39)

    def test_without_the_artifact_there_is_no_copy(self):
        _, _, b = ping([Permanent(SORCERER, sick=False)], "Prodigal Sorcerer")
        self.assertEqual(b.life, 39)

    def test_a_mana_ability_is_not_an_activation_to_copy(self):
        game, _, _ = table(policy("Sol Ring"))
        a = game.seats[0]
        a.battlefield = [Permanent(RINGS), Permanent(MANA_ROCK)]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Sol Ring")], [],
                         "mana abilities are paid with, not activated: nothing for Rings of Brighthearth to see")

    def test_only_an_artifacts_ability_is_copied_for_kurkesh(self):
        _, _, b = ping([Permanent(KURKESH), Permanent(PINGER_RELIC)], "Pinging Relic")
        self.assertEqual(b.life, 38)
        _, _, b = ping([Permanent(KURKESH), Permanent(SORCERER, sick=False)], "Prodigal Sorcerer")
        self.assertEqual(b.life, 39, "a creature's ability is not an artifact's")

    def test_the_equipped_creatures_ability_is_copied_only_when_it_is_equipped(self):
        sorcerer = Permanent(SORCERER, sick=False)
        _, _, b = ping([Permanent(BRACERS, attached_to=sorcerer), sorcerer], "Prodigal Sorcerer")
        self.assertEqual(b.life, 38)
        other = Permanent(dataclasses.replace(BEAR, name="Other"))
        _, _, b = ping([Permanent(BRACERS, attached_to=other), other, Permanent(SORCERER, sick=False)], "Prodigal Sorcerer")
        self.assertEqual(b.life, 39)


class TriggeredAbilityCopyTests(unittest.TestCase):
    def copy(self, card, extra_mana=()):
        game, _, _ = table(policy(card.name))
        a = game.seats[0]
        healer = Permanent(HEALER)
        a.battlefield = lands(4) + [Permanent(card), healer]
        game.trigger("enters", healer, a)
        game._put_triggers_on_stack()
        game._priority_round(a)
        run_stack(game)
        return a

    def test_a_triggered_ability_you_control_is_copied(self):
        a = self.copy(RESONATOR)
        self.assertEqual(a.life, 44, "the trigger and its copy each gained 2")

    def test_it_is_copied_twice(self):
        a = self.copy(FANTASTIC)
        self.assertEqual(a.life, 46)

    def test_the_copy_may_have_a_new_target(self):
        kavu = real("Flametongue Kavu", "{3}{R}", "Creature — Elemental", "When this creature enters, it deals 4 damage to target creature.",
                    "4", "2")
        asked = []

        def choose(prompt, options):
            if prompt.startswith(TARGET_PROMPT + "Flametongue"):
                asked.append(prompt)
                return next(i for i, o in enumerate(options) if o.startswith("First" if len(asked) == 1 else "Last"))
            if prompt.startswith(TARGET_PROMPT):  # the Resonator's own target: the trigger
                return 0
            return next((i for i, o in enumerate(options) if o.startswith(ACTIVATE + "Strionic")), options.index(PASS) if PASS in options else 0)

        game, _, _ = table(choose)
        a, b = game.seats
        flame = Permanent(kavu)
        a.battlefield = lands(4) + [Permanent(RESONATOR), flame]
        b.battlefield = [Permanent(dataclasses.replace(BEAR, name="First")), Permanent(dataclasses.replace(BEAR, name="Last"))]
        game.trigger("enters", flame, a)
        game._put_triggers_on_stack()
        game._priority_round(a)
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], [], "the trigger hit one, its copy the other")

    def test_an_opponents_triggered_ability_or_an_activated_one_is_no_target(self):
        game, _, _ = table(policy("Strionic Resonator"))
        a, b = game.seats
        healer = Permanent(HEALER)
        b.battlefield = [healer]
        a.battlefield = lands(4) + [Permanent(RESONATOR)]
        game.trigger("enters", healer, b)
        game._put_triggers_on_stack()
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Strionic")], [], "not one you control")
        game.stack.clear()
        sorcerer = Permanent(SORCERER, sick=False)
        a.battlefield.append(sorcerer)
        [ability] = activated_abilities(SORCERER)
        game.stack.append(StackItem(SORCERER, a, list(ability.effects), [b], ability, sorcerer))  # an activated ability of yours
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Strionic")], [], "not a triggered one")

    def test_with_no_triggered_ability_on_the_stack_it_cannot_be_activated(self):
        game, _, _ = table(policy("Strionic Resonator"))
        a = game.seats[0]
        a.battlefield = lands(4) + [Permanent(RESONATOR)]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Strionic")], [])


if __name__ == "__main__":
    unittest.main()
