"""The five Hideaway 4 lands (the last piece of #91's land list): Howltooth Hollow, Mosswort Bridge, Shelldock Isle, Spinerock
Knoll and Windbrisk Heights, each played from its real Oracle text. As the land enters one of the top four cards is hidden
away; its ability plays that card for free, but only when its own condition holds as the ability resolves."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, HIDEAWAY_PLAY_PROMPT, HIDEAWAY_PROMPT, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, creature, FOREST, OGRE, pick, PLAINS, run_stack, table3

REMINDER = ("Hideaway 4 (When this land enters, look at the top four cards of your library, exile one face down, then put "
            "the rest on the bottom in a random order.)")


def hideaway(name, mana, condition):
    return Card(name=name, type_line="Land", produced_mana=(mana,),
                oracle_text=f"{REMINDER}\nThis land enters tapped.\n{{T}}: Add {{{mana}}}.\n"
                            f"{{{mana}}}, {{T}}: You may play the exiled card without paying its mana cost if {condition}.")


HOLLOW = hideaway("Howltooth Hollow", "B", "each player has no cards in hand")
BRIDGE = hideaway("Mosswort Bridge", "G", "creatures you control have total power 10 or greater")
ISLE = hideaway("Shelldock Isle", "U", "a library has twenty or fewer cards in it")
KNOLL = hideaway("Spinerock Knoll", "R", "an opponent was dealt 7 or more damage this turn")
HEIGHTS = hideaway("Windbrisk Heights", "W", "you attacked with three or more creatures this turn")
ALL = [HOLLOW, BRIDGE, ISLE, KNOLL, HEIGHTS]
SOURCE = {"B": Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",)),
          "G": FOREST, "W": PLAINS,
          "U": Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",)),
          "R": Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))}

# Five cards on top of the library: the first four are the choices, the fifth stays where it is.
HIDDEN = Card(name="Hidden Giant", mana_cost="{6}{G}", cmc=7.0, type_line="Creature — Giant", power="5", toughness="5")
TOP = [Card(name="Top One", type_line="Instant"), HIDDEN, Card(name="Top Three", type_line="Instant"),
       Card(name="Top Four", type_line="Instant"), Card(name="Fifth Card", type_line="Instant")]
HIDDEN_LAND = Card(name="Hidden Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def enter(card, policy=None, library=None, others=()):
    """Seat 0 plays the land; returns (game, seat, the land's permanent, the events broadcast)."""
    game, _ = table3(policy or pick("Hidden Giant"))
    events = []
    original = game.broadcast
    game.broadcast = lambda event: (events.append(event), original(event))[1]
    a = game.seats[0]
    a.battlefield = list(others)
    a.hand = [card]
    a.library = list(library if library is not None else TOP + [BEAR] * 30)
    game.active, game.step = 0, "main1"
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    permanent = next(p for p in a.battlefield if p.card is card)
    return game, a, permanent, events


def ready(card, policy=None, library=None):
    """The land entered, untapped now, with a land that can pay its cost beside it."""
    mana = card.produced_mana[0]
    game, a, permanent, events = enter(card, policy, library, others=[Permanent(SOURCE[mana])])
    permanent.tapped = False
    a.lands_played = 0
    return game, a, permanent


def use(game, seat, permanent):
    action = next((x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and "play the exiled card" in x
                   and permanent.card.name in x), None)
    if action is None:
        return False
    game._perform(seat, action)
    run_stack(game)
    return True


class ParseTests(unittest.TestCase):
    def test_all_five_are_fully_understood(self):
        for card in ALL:
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])


class HideawayTests(unittest.TestCase):
    def test_it_enters_tapped(self):
        _, _, permanent, _ = enter(HOLLOW)
        self.assertTrue(permanent.tapped)

    def test_you_choose_one_of_the_top_four_and_it_is_exiled(self):
        seen = []

        def policy(prompt, options):
            seen.append((prompt, options))
            return pick("Hidden Giant")(prompt, options)

        game, a, permanent, _ = enter(HOLLOW, policy)
        self.assertEqual(seen, [(HIDEAWAY_PROMPT + "Howltooth Hollow", ["Top One", "Hidden Giant", "Top Three", "Top Four"])])
        self.assertIn(HIDDEN, a.exile)
        self.assertEqual(permanent.exiled_with, [(a, HIDDEN)])

    def test_the_other_three_go_to_the_bottom_and_the_fifth_card_is_the_new_top(self):
        game, a, _, _ = enter(HOLLOW)
        self.assertEqual(a.library[0].name, "Fifth Card")
        self.assertEqual(sorted(c.name for c in a.library[-3:]), ["Top Four", "Top One", "Top Three"])
        self.assertEqual(len(a.library), 35 - 1)

    def test_it_is_face_down_so_the_event_does_not_name_the_card(self):
        _, _, _, events = enter(HOLLOW)
        shown = [e for e in events if e.get("event") == "hideaway"]
        self.assertEqual(len(shown), 1)
        self.assertNotIn("Hidden Giant", str(shown[0]))

    def test_with_fewer_than_four_cards_it_hides_one_of_those(self):
        game, a, permanent, _ = enter(HOLLOW, library=[BEAR, OGRE], policy=pick("Ogre"))
        self.assertEqual(([c.name for c in a.exile], [c.name for c in a.library]), (["Ogre"], ["Bear"]))

    def test_with_one_card_there_is_no_choice(self):
        game, a, permanent, _ = enter(HOLLOW, library=[BEAR], policy=pick())
        self.assertEqual(([c.name for c in a.exile], a.library), (["Bear"], []))

    def test_with_an_empty_library_nothing_happens(self):
        game, a, permanent, _ = enter(HOLLOW, library=[])
        self.assertEqual((a.exile, permanent.exiled_with), ([], []))


class ConditionTests(unittest.TestCase):
    def test_howltooth_hollow_needs_every_hand_empty(self):
        for opponent_cards, expected in ((0, True), (1, False)):
            with self.subTest(opponent_cards=opponent_cards):
                game, a, permanent = ready(HOLLOW)
                a.hand = []
                game.seats[1].hand = [BEAR] * opponent_cards
                game.seats[2].hand = []
                use(game, a, permanent)
                self.assertEqual(any(p.card is HIDDEN for p in a.battlefield), expected)

    def test_howltooth_hollow_needs_your_own_hand_empty_too(self):
        game, a, permanent = ready(HOLLOW)
        a.hand = [BEAR]
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield))

    def test_mosswort_bridge_needs_total_power_ten(self):
        for creatures, expected in (([creature("Big", 7, 7), OGRE], True), ([creature("Big", 7, 7), BEAR], False)):
            with self.subTest(power=sum(int(c.power) for c in creatures)):
                game, a, permanent = ready(BRIDGE)
                a.battlefield += [Permanent(c) for c in creatures]
                use(game, a, permanent)
                self.assertEqual(any(p.card is HIDDEN for p in a.battlefield), expected)

    def test_mosswort_bridge_counts_only_your_creatures(self):
        game, a, permanent = ready(BRIDGE)
        game.seats[1].battlefield = [Permanent(creature("Huge", 12, 12))]
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield))

    def test_shelldock_isle_needs_a_library_of_twenty_or_fewer(self):
        for size, expected in ((20, True), (21, False)):
            with self.subTest(size=size):
                game, a, permanent = ready(ISLE)
                game.seats[0].library = [BEAR] * 40
                game.seats[1].library = [BEAR] * size
                game.seats[2].library = [BEAR] * 40
                use(game, a, permanent)
                self.assertEqual(any(p.card is HIDDEN for p in a.battlefield), expected)

    def test_shelldock_isle_counts_your_own_library_too(self):
        game, a, permanent = ready(ISLE)
        a.library = [BEAR] * 20
        game.seats[1].library = game.seats[2].library = [BEAR] * 40
        use(game, a, permanent)
        self.assertTrue(any(p.card is HIDDEN for p in a.battlefield))

    def test_spinerock_knoll_needs_one_opponent_dealt_seven_this_turn(self):
        for amount, expected in ((7, True), (6, False)):
            with self.subTest(amount=amount):
                game, a, permanent = ready(KNOLL)
                game.damage(game.seats[1], amount)
                use(game, a, permanent)
                self.assertEqual(any(p.card is HIDDEN for p in a.battlefield), expected)

    def test_spinerock_knoll_adds_up_one_opponents_damage(self):
        game, a, permanent = ready(KNOLL)
        game.damage(game.seats[1], 3)
        game.damage(game.seats[1], 4)
        use(game, a, permanent)
        self.assertTrue(any(p.card is HIDDEN for p in a.battlefield))

    def test_spinerock_knoll_does_not_add_up_two_opponents(self):
        game, a, permanent = ready(KNOLL)
        game.damage(game.seats[1], 4)
        game.damage(game.seats[2], 4)
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield))

    def test_spinerock_knoll_does_not_count_damage_to_you_or_from_an_earlier_turn(self):
        game, a, permanent = ready(KNOLL)
        game.damage(a, 9)
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield), "damage to you")
        game.damage(game.seats[1], 9)
        game.turn += 1
        for p in a.battlefield:
            p.tapped = False
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield), "an earlier turn")

    def attack_with(self, count):
        def policy(prompt, options):
            attack = next((i for i, o in enumerate(options) if o.startswith("Attack Player")), None)
            return attack if attack is not None else pick("Hidden Giant")(prompt, options)

        game, a, permanent = ready(HEIGHTS, policy)
        attackers = [Permanent(creature(f"Soldier {i}", 1, 1)) for i in range(count)]
        for p in attackers:
            p.sick = False
        a.battlefield += attackers
        game.active, game.step = 0, "declare_attackers"
        game.combat.declare_attackers(a)
        run_stack(game)
        game.step = "main2"
        return game, a, permanent

    def test_windbrisk_heights_needs_three_attackers(self):
        for count, expected in ((3, True), (2, False)):
            with self.subTest(count=count):
                game, a, permanent = self.attack_with(count)
                permanent.tapped = False
                use(game, a, permanent)
                self.assertEqual(any(p.card is HIDDEN for p in a.battlefield), expected)

    def test_windbrisk_heights_does_not_count_an_attack_from_an_earlier_turn(self):
        game, a, permanent = self.attack_with(3)
        game.turn += 1
        for p in a.battlefield:
            p.tapped = False
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield))

    def test_windbrisk_heights_does_nothing_without_an_attack(self):
        game, a, permanent = ready(HEIGHTS)
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield))


class PlayingTheCardTests(unittest.TestCase):
    def test_a_spell_is_cast_without_paying_its_mana_cost(self):
        game, a, permanent = ready(HOLLOW)
        a.hand = []
        spare = [Permanent(FOREST) for _ in range(8)]  # enough to pay for it, were it not free
        a.battlefield += spare
        use(game, a, permanent)
        self.assertTrue(any(p.card is HIDDEN for p in a.battlefield))
        self.assertFalse(any(p.tapped for p in spare), "no mana was spent on it")
        self.assertNotIn(HIDDEN, a.exile)
        self.assertEqual(permanent.exiled_with, [])

    def test_the_cost_is_paid_and_the_land_is_tapped_even_when_the_condition_fails(self):
        game, a, permanent = ready(HOLLOW)
        a.hand = [BEAR]
        use(game, a, permanent)
        self.assertTrue(permanent.tapped)
        self.assertTrue(a.battlefield[0].tapped)
        self.assertIn(HIDDEN, a.exile, "the card stays hidden away")

    def test_you_may_decline(self):
        game, a, permanent = ready(HOLLOW, policy=lambda prompt, options: pick("Hidden Giant", "Don't")(prompt, options))
        a.hand = []
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN for p in a.battlefield))
        self.assertIn(HIDDEN, a.exile)

    def test_a_land_is_played_if_a_land_drop_is_left(self):
        game, a, permanent = ready(HOLLOW, library=[HIDDEN_LAND] + [BEAR] * 30, policy=pick("Hidden Forest"))
        a.hand = []
        use(game, a, permanent)
        self.assertTrue(any(p.card is HIDDEN_LAND for p in a.battlefield))
        self.assertEqual(a.lands_played, 1)

    def test_a_land_stays_hidden_when_the_land_drop_is_used(self):
        game, a, permanent = ready(HOLLOW, library=[HIDDEN_LAND] + [BEAR] * 30, policy=pick("Hidden Forest"))
        a.hand = []
        a.lands_played = 1
        use(game, a, permanent)
        self.assertFalse(any(p.card is HIDDEN_LAND for p in a.battlefield))
        self.assertIn(HIDDEN_LAND, a.exile)

    def test_the_prompt_names_the_card_to_the_player_who_hid_it(self):
        seen = []

        def policy(prompt, options):
            seen.append(prompt)
            return pick("Hidden Giant")(prompt, options)

        game, a, permanent = ready(HOLLOW, policy)
        a.hand = []
        use(game, a, permanent)
        self.assertIn(HIDEAWAY_PLAY_PROMPT + "Hidden Giant", seen)

    def test_two_lands_hide_their_own_cards(self):
        game, a, permanent, _ = enter(HOLLOW)
        first = permanent.exiled_with
        game.step = "main1"
        a.hand = [BRIDGE]
        a.lands_played = 0
        game._perform(a, PLAY_LAND + BRIDGE.name)
        run_stack(game)
        other = next(p for p in a.battlefield if p.card is BRIDGE)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(other.exiled_with), 1)
        self.assertIsNot(first[0][1], other.exiled_with[0][1])


if __name__ == "__main__":
    unittest.main()
