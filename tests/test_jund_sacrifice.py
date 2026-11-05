"""Standard's Jund Sacrifice deck, from its cards' real Oracle text: Gene Pollinator ("Tap an untapped permanent you control"), Wolverine
(a fight on entering, and damage that heals what was already dealt), Mutagen Man (Mutagen tokens, and artifact tokens' abilities cost {1}
less), The Misty Mountains Cold (sacrifice the Saga for a Dragon), Lively Dirge (Spree), Obsessive Pursuit (two triggers on one line, and
the permanents sacrificed this turn) and Rottenmouth Viper (sacrifice permanents to cast it for less; a punisher for each blight counter)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import CLUE, TREASURE
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, fire, lands, real, run_stack, script, table3

POLLINATOR = real("Gene Pollinator", "{G}", "Artifact Creature — Robot Insect", "{T}, Tap an untapped permanent you control: Add one mana of "
                  "any color.", "1", "2", colors=("G",))
WOLVERINE = real("Wolverine, Fierce Fighter", "{2}{R}{G}", "Legendary Creature — Mutant Berserker Hero", "Haste\nWhen Wolverine enters, he "
                 "fights up to one other target creature.\nIf damage would be dealt to Wolverine, instead that damage is dealt, but all other "
                 "damage already dealt to him is healed.", "3", "5", colors=("G", "R"))
MUTAGEN_MAN = real("Mutagen Man, Living Ooze", "{X}{G}{G}", "Legendary Creature — Ooze Mutant", "Trample\nActivated abilities of artifact "
                   "tokens you control cost {1} less to activate.\nWhen Mutagen Man enters, create X Mutagen tokens. (They're artifacts with "
                   "\"{1}, {T}, Sacrifice this token: Put a +1/+1 counter on target creature. Activate only as a sorcery.\")", "2", "3",
                   colors=("G",))
MISTY = real("The Misty Mountains Cold", "{2}{R}", "Enchantment — Saga", "(As this Saga enters and after your draw step, add a lore counter. "
             "Sacrifice after IV.)\nI, II, III, IV — Create a Treasure token. Then if you control four or more Treasures, sacrifice this Saga. "
             "If you do, create a 6/6 red Dragon creature token with flying. (A Treasure token is an artifact with \"{T}, Sacrifice this "
             "token: Add one mana of any color.\")", colors=("R",))
DIRGE = real("Lively Dirge", "{1}{B}", "Sorcery", "Spree (Choose one or more additional costs.)\n+ {1} — Search your library for a card, put "
             "it into your graveyard, then shuffle.\n+ {2} — Return up to two creature cards with total mana value 4 or less from your "
             "graveyard to the battlefield.", colors=("B",))
PURSUIT = real("Obsessive Pursuit", "{1}{B}", "Enchantment", "When this enchantment enters and at the beginning of your upkeep, you lose 1 "
               "life and create a Clue token. (It's an artifact with \"{2}, Sacrifice this token: Draw a card.\")\nWhenever you attack, put "
               "X +1/+1 counters on target attacking creature, where X is the number of permanents you've sacrificed this turn. If X is "
               "three or more, that creature gains lifelink until end of turn.", colors=("B",))
VIPER = real("Rottenmouth Viper", "{5}{B}", "Creature — Elemental Snake", "As an additional cost to cast this spell, you may sacrifice any "
             "number of nonland permanents. This spell costs {1} less to cast for each permanent sacrificed this way.\nWhenever this "
             "creature enters or attacks, put a blight counter on it. Then for each blight counter on it, each opponent loses 4 life unless "
             "that player sacrifices a nonland permanent of their choice or discards a card.", "6", "6", colors=("B",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
TWO = real("Grizzly", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
TWO_MORE = real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
THREE = real("Brute", "{2}{R}", "Creature — Ogre", "", "3", "3", colors=("R",))
FIVE = real("Giant", "{4}{R}", "Creature — Giant", "", "5", "5", colors=("R",))
MUTAGEN_RELIC = Card(name="Mutagen Relic", type_line="Artifact", oracle_text="{1}, {T}, Sacrifice this artifact: Put a +1/+1 counter on "
                     "target creature. Activate only as a sorcery.")
SOLDIER = Card(name="Soldier", type_line="Token Creature — Soldier", oracle_text="{1}: This creature gets +1/+0 until end of turn.",
               power="1", toughness="1")
MUTATION = real("Darksteel Mutation", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature is an Insect artifact creature "
                "with base power and toughness 0/1 and has indestructible, and it loses all other abilities, card types, and creature types.",
                colors=("W",))


def table(*answers, n=0):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield = lands(n)
    for seat in game.seats:
        seat.library = [FOREST] * 5
    return game, a, b, c


def recording(choose, asked):
    def wrapped(prompt, options):
        asked.append((prompt, list(options)))
        return choose(prompt, options)
    return wrapped


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class JundSacrificeTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (POLLINATOR, WOLVERINE, MUTAGEN_MAN, MISTY, DIRGE, PURSUIT, VIPER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_gene_pollinator_taps_another_permanent_for_mana(self):
        game, a, _, _ = table("Relic")
        relic = Permanent(RELIC)
        a.battlefield, a.hand = [Permanent(POLLINATOR), relic], [OPT]
        game._perform(a, offered(game, a, ACTIVATE + "Gene Pollinator")[0])
        run_stack(game)
        self.assertEqual((relic.tapped, len(a.mana_pool)), (True, 1))
        self.assertEqual(offered(game, a, CAST + "Opt"), [CAST + "Opt"])
        a.battlefield = [Permanent(POLLINATOR), Permanent(RELIC, tapped=True)]  # nothing else untapped to tap
        self.assertEqual(offered(game, a, ACTIVATE + "Gene Pollinator"), [])

    def test_wolverine_fights_a_creature_as_he_enters(self):
        game, a, b, _ = table("Ogre", n=4)
        a.hand, b.battlefield = [WOLVERINE], [Permanent(OGRE)]
        game._perform(a, CAST + "Wolverine, Fierce Fighter")
        run_stack(game)
        game._check_state()
        wolverine = next(p for p in a.battlefield if p.card is WOLVERINE)
        self.assertEqual((b.battlefield, wolverine.damage), ([], 3))

    def test_damage_to_wolverine_heals_the_damage_already_dealt(self):
        game, a, _, _ = table()
        wolverine, ogre = Permanent(WOLVERINE), Permanent(OGRE)
        a.battlefield = [wolverine, ogre]
        wolverine.damage, ogre.damage = 4, 1
        game.damage(wolverine, 3)
        game.damage(ogre, 1)
        game._check_state()
        self.assertEqual((wolverine.damage, ogre.damage), (3, 2))
        self.assertIn(wolverine, a.battlefield)
        game.damage(wolverine, 0)  # no damage dealt: nothing is healed
        self.assertEqual(wolverine.damage, 3)

    def test_a_wolverine_without_abilities_keeps_his_damage(self):
        game, a, _, _ = table()
        wolverine = Permanent(WOLVERINE)
        mutation = Permanent(MUTATION)
        a.battlefield = [wolverine, mutation]
        game.attach(mutation, wolverine)
        game.damage(wolverine, 1)
        game.damage(wolverine, 1)
        self.assertEqual(wolverine.damage, 2)

    def test_mutagen_man_makes_x_mutagen_tokens(self):
        game, a, _, _ = table("2", n=4)
        a.hand = [MUTAGEN_MAN]
        game._perform(a, CAST + "Mutagen Man, Living Ooze")
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Mutagen"], ["Mutagen", "Mutagen"])

    def test_mutagen_man_makes_artifact_token_abilities_cost_one_less(self):
        game, a, b, _ = table("Bear")
        mutagen = Permanent(Card(name="Mutagen", type_line="Token Artifact — Mutagen", oracle_text=MUTAGEN_RELIC.oracle_text))
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(MUTAGEN_MAN), mutagen, bear]
        self.assertTrue(offered(game, a, ACTIVATE + "Mutagen"))  # {1} less: free, with no land
        game._perform(a, offered(game, a, ACTIVATE + "Mutagen")[0])
        run_stack(game)
        self.assertEqual(bear.counters.get("+1/+1"), 1)
        a.battlefield = [Permanent(MUTAGEN_MAN), Permanent(CLUE)] + lands(1)  # a Clue's {2} is {1}
        self.assertTrue(offered(game, a, ACTIVATE + "Clue"))

    def test_mutagen_man_does_not_discount_nontoken_artifacts_or_an_opponents_tokens(self):
        game, a, b, _ = table()
        a.battlefield = [Permanent(MUTAGEN_MAN), Permanent(MUTAGEN_RELIC), Permanent(BEAR)]
        self.assertEqual(offered(game, a, ACTIVATE + "Mutagen Relic"), [])
        a.battlefield = [Permanent(CLUE)] + lands(1)
        b.battlefield = [Permanent(MUTAGEN_MAN)]
        self.assertEqual(offered(game, a, ACTIVATE + "Clue"), [])
        a.battlefield = [Permanent(MUTAGEN_MAN), Permanent(SOLDIER)]  # a token, but not an artifact
        self.assertEqual(offered(game, a, ACTIVATE + "Soldier"), [])

    def test_the_misty_mountains_cold_trades_itself_for_a_dragon_at_four_treasures(self):
        game, a, _, _ = table(n=3)
        a.battlefield += [Permanent(TREASURE) for _ in range(3)]
        a.hand = [MISTY]
        game._perform(a, CAST + "The Misty Mountains Cold")
        run_stack(game)
        self.assertNotIn("The Misty Mountains Cold", names(a))
        self.assertIn("Dragon", names(a))
        self.assertEqual(names(a).count("Treasure"), 4)

    def test_the_misty_mountains_cold_stays_with_fewer_treasures(self):
        game, a, _, _ = table(n=3)
        a.hand = [MISTY]
        game._perform(a, CAST + "The Misty Mountains Cold")
        run_stack(game)
        self.assertIn("The Misty Mountains Cold", names(a))
        self.assertNotIn("Dragon", names(a))
        self.assertEqual(names(a).count("Treasure"), 1)

    def test_the_misty_mountains_cold_gone_before_its_chapter_resolves_makes_no_dragon(self):
        game, a, _, _ = table(n=3)
        a.battlefield += [Permanent(TREASURE) for _ in range(3)]
        a.hand = [MISTY]
        game._perform(a, CAST + "The Misty Mountains Cold")
        game._resolve(game.stack.pop())  # the Saga enters; its chapter waits to go on the stack
        saga = next(p for p in a.battlefield if p.card is MISTY)
        game._leave_battlefield(saga, "destroyed")
        run_stack(game)
        self.assertNotIn("Dragon", names(a))
        self.assertEqual(names(a).count("Treasure"), 4)

    def test_lively_dirge_entombs_then_returns_creatures_up_to_the_total(self):
        game, a, _, _ = table("+ {1}", "+ {2}", "Cub", "Grizzly", "Cub", n=5)
        a.hand, a.library, a.graveyard = [DIRGE], [TWO_MORE, FOREST], [TWO, FIVE]
        game._perform(a, CAST + "Lively Dirge")
        run_stack(game)
        self.assertEqual([n for n in names(a) if n in ("Cub", "Grizzly", "Giant")], ["Cub", "Grizzly"])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Giant", "Lively Dirge"])

    def test_lively_dirge_stops_when_nothing_else_fits_the_total(self):
        game, a, _, _ = table("+ {2}", "Done", "Brute", n=5)
        a.hand, a.graveyard = [DIRGE], [OPT, THREE, TWO, FIVE]
        game.seats[0].player.choose = recording(game.seats[0].player.choose, asked := [])
        game._perform(a, CAST + "Lively Dirge")
        run_stack(game)
        self.assertEqual([n for n in names(a) if n in ("Brute", "Grizzly", "Giant")], ["Brute"])
        self.assertNotIn("Opt", [o for _, options in asked for o in options])  # an instant isn't a creature card

    def test_obsessive_pursuit_loses_life_and_makes_a_clue_on_entering_and_each_upkeep(self):
        game, a, _, _ = table(n=2)
        a.hand = [PURSUIT]
        life = a.life
        game._perform(a, CAST + "Obsessive Pursuit")
        run_stack(game)
        self.assertEqual((a.life, names(a).count("Clue")), (life - 1, 1))
        fire(game, a, next(p for p in a.battlefield if p.card is PURSUIT), "upkeep")
        self.assertEqual((a.life, names(a).count("Clue")), (life - 2, 2))

    def attack_after_sacrificing(self, count, earlier_turn=False):
        game, a, _, _ = table("Attack Player: B", "Bear")
        bear = Permanent(BEAR)
        doomed = [Permanent(RELIC) for _ in range(count)]
        a.battlefield = [Permanent(PURSUIT), bear] + doomed
        for permanent in doomed:
            game._leave_battlefield(permanent, "sacrificed")
        if earlier_turn:
            game.turn += 1
        game.combat.declare_attackers(a)
        run_stack(game)
        return bear, game

    def test_obsessive_pursuit_counts_the_permanents_sacrificed_this_turn(self):
        bear, game = self.attack_after_sacrificing(3)
        self.assertEqual(bear.counters.get("+1/+1"), 3)
        self.assertTrue(game.has_keyword(bear, "lifelink"))

    def test_obsessive_pursuit_gives_lifelink_only_from_three(self):
        bear, game = self.attack_after_sacrificing(2)
        self.assertEqual(bear.counters.get("+1/+1"), 2)
        self.assertFalse(game.has_keyword(bear, "lifelink"))

    def test_obsessive_pursuit_forgets_last_turns_sacrifices(self):
        bear, _ = self.attack_after_sacrificing(3, earlier_turn=True)
        self.assertFalse(bear.counters.get("+1/+1"))

    def test_rottenmouth_viper_costs_one_less_for_each_permanent_sacrificed(self):
        game, a, _, _ = table("4", "Relic", "Relic", "Relic", "Relic", "Lose", "Lose", n=2)
        a.battlefield += [Permanent(RELIC) for _ in range(4)]
        a.hand = [VIPER]
        game._perform(a, CAST + "Rottenmouth Viper")
        run_stack(game)
        self.assertEqual(names(a).count("Relic"), 0)
        self.assertIn("Rottenmouth Viper", names(a))
        self.assertEqual(a.sacrificed, 4)

    def test_rottenmouth_viper_cast_for_free_needs_no_mana_and_no_sacrifice(self):
        game, a, _, _ = table("Lose", "Lose")
        a.hand = [VIPER]
        game._cast(a, VIPER, a.hand, free=True)
        run_stack(game)
        self.assertIn("Rottenmouth Viper", names(a))

    def test_lively_dirge_may_return_nothing(self):
        game, a, _, _ = table("+ {2}", "Done", "Take none", n=5)
        a.hand, a.graveyard = [DIRGE], [TWO]
        game._perform(a, CAST + "Lively Dirge")
        run_stack(game)
        self.assertEqual([c.name for c in a.graveyard], ["Grizzly", "Lively Dirge"])

    def test_rottenmouth_viper_needs_enough_permanents_to_sacrifice(self):
        game, a, _, _ = table(n=2)
        a.battlefield += [Permanent(RELIC) for _ in range(3)]
        a.hand = [VIPER]
        self.assertEqual(offered(game, a, CAST + "Rottenmouth Viper"), [])

    def test_a_treasure_pays_for_mana_or_is_sacrificed_not_both(self):
        game, a, _, _ = table(n=1)
        a.battlefield += [Permanent(TREASURE) for _ in range(4)]  # four sacrificed leave {1}{B} and one land: not enough
        a.hand = [VIPER]
        self.assertEqual(offered(game, a, CAST + "Rottenmouth Viper"), [])
        a.battlefield += lands(1)  # two lands: two Treasures pay, the other two are sacrificed for {2}{B}
        self.assertEqual(offered(game, a, CAST + "Rottenmouth Viper"), [CAST + "Rottenmouth Viper"])

    def test_rottenmouth_viper_punishes_each_opponent_for_each_blight_counter(self):
        game, _ = table3(script("Sacrifice", "Discard"), script("Lose", "Discard", "Forest", "Sacrifice"), script("Sacrifice", "Discard"))
        a, b, c = game.seats  # c would rather sacrifice or discard, but has nothing to; the Viper's controller is not asked
        viper = Permanent(VIPER)
        a.battlefield = [viper]
        b.hand, b.battlefield, c.hand = [FOREST], [Permanent(RELIC)], []
        fire(game, a, viper, "enters")  # one counter: one choice each
        self.assertEqual((b.life, c.life, viper.counters.get("blight")), (36, 36, 1))
        fire(game, a, viper, "attacks")  # two counters: two choices each
        self.assertEqual(viper.counters.get("blight"), 2)
        self.assertEqual((b.hand, b.battlefield), ([], []))
        self.assertEqual((c.life, a.life), (28, 40))  # c has nothing to sacrifice or discard: it loses the life each time

    def test_a_rottenmouth_viper_gone_before_its_attack_trigger_resolves_punishes_for_the_counters_it_had(self):
        game, a, b, c = table()
        viper = Permanent(VIPER, counters={"blight": 1})
        a.battlefield = [viper]
        game.trigger("attacks", viper, a)
        game._put_triggers_on_stack()
        game._leave_battlefield(viper, "destroyed")
        run_stack(game)
        self.assertEqual((b.life, c.life), (36, 36))  # one counter when it left: one loss each


if __name__ == "__main__":
    unittest.main()
