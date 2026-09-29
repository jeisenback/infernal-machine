import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.effects import (Counter, Damage, Destroy, Draw, FetchBasicLand, GainLife,
                                      OpponentsLoseLife, mana_ability, spell_effects)
from infernal_machine.game import CAST, CAST_COMMANDER, COMMAND_ZONE_PROMPT, PASS, Game, Permanent
from tests.test_game import ScriptedPlayer

RAINBOW = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG"))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BOLT = Card(name="Lightning Bolt", mana_cost="{R}", type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.")
DIVINATION = Card(name="Divination", mana_cost="{2}{U}", type_line="Sorcery", oracle_text="Draw two cards.")
COUNTERSPELL = Card(name="Counterspell", mana_cost="{U}{U}", type_line="Instant", oracle_text="Counter target spell.")
MURDER = Card(name="Murder", mana_cost="{1}{B}{B}", type_line="Instant", oracle_text="Destroy target creature.")
RAMPANT = Card(name="Rampant Growth", mana_cost="{1}{G}", type_line="Sorcery",
               oracle_text="Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.")
WEIRD = Card(name="Weird Spell", mana_cost="{U}", type_line="Instant", oracle_text="Exchange control of two target creatures.")
SOL_RING = Card(name="Sol Ring", mana_cost="{1}", type_line="Artifact", oracle_text="{T}: Add {C}{C}.")
ELVES = Card(name="Llanowar Elves", mana_cost="{G}", type_line="Creature — Elf Druid",
             oracle_text="{T}: Add {G}.", power="1", toughness="1")
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", type_line="Creature — Bear", power="2", toughness="2")
OGRE = Card(name="Gray Ogre", mana_cost="{2}{R}", type_line="Creature — Ogre", power="2", toughness="2")
DARKSTEEL = Card(name="Darksteel Myr", mana_cost="{3}", type_line="Artifact Creature — Myr",
                 oracle_text="Indestructible", power="0", toughness="1")
TROLL = Card(name="Troll", mana_cost="{G}", type_line="Creature — Troll", oracle_text="Hexproof", toughness="2")
WALKER = Card(name="Walker", mana_cost="{3}", type_line="Legendary Planeswalker — Test", loyalty="3")
COMMANDER = Card(name="Omnath", mana_cost="{G}", type_line="Legendary Creature — Elemental", toughness="1")


def pick(*labels):
    """Policy: take the first option starting with any of `labels`, in order; else pass/first."""
    def policy(prompt, options):
        for label in labels:
            for i, option in enumerate(options):
                if option.startswith(label):
                    return i
        return options.index(PASS) if PASS in options else 0
    return policy


def table(policy_a=None, policy_b=None, library=(FOREST,) * 20):
    a, b = ScriptedPlayer("A", policy_a), ScriptedPlayer("B", policy_b)
    deck = Deck(commanders=[COMMANDER], main=list(library), sideboard=[])
    game = Game([(a, deck), (b, deck)], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand, seat.command_zone = [], []
    return game, a, b


def lands(n, card=RAINBOW):
    return [Permanent(card) for _ in range(n)]


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(BOLT), [Damage(3, "any")])
        self.assertEqual(spell_effects(DIVINATION), [Draw(2)])
        self.assertEqual(spell_effects(COUNTERSPELL), [Counter()])
        self.assertEqual(spell_effects(MURDER), [Destroy("creature")])
        self.assertEqual(spell_effects(RAMPANT), [FetchBasicLand()])

    def test_several_sentences_and_new_templating(self):
        card = Card(name="Mix", oracle_text="Draw a card. You gain 3 life.\nEach opponent loses 1 life.")
        self.assertEqual(spell_effects(card), [Draw(1), GainLife(3), OpponentsLoseLife(1)])
        shock = Card(name="Shock", oracle_text="This spell deals 2 damage to target creature or planeswalker.")
        self.assertEqual(spell_effects(shock), [Damage(2, "creature or planeswalker")])

    def test_any_unknown_sentence_means_unsupported(self):
        self.assertIsNone(spell_effects(WEIRD))
        self.assertIsNone(spell_effects(Card(name="x", oracle_text="Draw two cards. Then discard a card.")))

    def test_mana_abilities(self):
        identity = frozenset("GU")
        self.assertEqual(mana_ability(SOL_RING, identity), [frozenset("C"), frozenset("C")])
        self.assertEqual(mana_ability(ELVES, identity), [frozenset("G")])
        either = Card(name="x", oracle_text="Flying\n{T}: Add {R} or {G}.")
        self.assertEqual(mana_ability(either, identity), [frozenset("RG")])
        signet = Card(name="Arcane Signet", oracle_text="{T}: Add one mana of any color in your commander's color identity.")
        self.assertEqual(mana_ability(signet, identity), [identity])
        self.assertIsNone(mana_ability(Card(name="x", oracle_text="{1}, {T}: Add {W}{U}."), identity))


class EffectTests(unittest.TestCase):
    def test_bolt_a_player(self):
        game, _, _ = table(pick(CAST, "Player: B"))
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1)
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].life, 37)
        self.assertEqual(game.seats[0].graveyard, [BOLT])

    def test_lethal_damage_destroys_a_creature(self):
        game, _, _ = table(pick(CAST, "Grizzly Bears"))
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].battlefield, [])
        self.assertEqual(game.seats[1].graveyard, [BEAR])

    def test_damage_wears_off_in_cleanup(self):
        game, _, _ = table()
        ogre = Permanent(OGRE, damage=1)
        game.seats[1].battlefield = [ogre]
        game.step = "cleanup"
        game._turn_based_actions(game.seats[0])
        self.assertEqual(ogre.damage, 0)

    def test_planeswalker_loses_loyalty(self):
        game, _, _ = table(pick(CAST, "Walker"))
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(WALKER, loyalty=3)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].graveyard, [WALKER])

    def test_draw(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [DIVINATION]
        game.seats[0].battlefield = lands(3)
        game._priority_round(game.seats[0])
        self.assertEqual(len(game.seats[0].hand), 2)

    def test_destroy_respects_indestructible(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [MURDER]
        game.seats[0].battlefield = lands(3)
        game.seats[1].battlefield = [Permanent(DARKSTEEL)]
        game._priority_round(game.seats[0])
        self.assertEqual([p.card for p in game.seats[1].battlefield], [DARKSTEEL])

    def test_hexproof_and_no_targets(self):
        game, _, _ = table()
        game.seats[0].hand = [MURDER]
        game.seats[0].battlefield = lands(3)
        game.seats[1].battlefield = [Permanent(TROLL)]
        self.assertEqual(game.legal_actions(game.seats[0]), [PASS])  # the only creature has hexproof
        game.seats[1].hand = [MURDER]
        game.seats[1].battlefield.append(Permanent(RAINBOW))
        game.seats[1].battlefield += lands(2)
        self.assertIn(CAST + "Murder", game.legal_actions(game.seats[1]))  # its controller can target it

    def test_counterspell(self):
        game, a, b = table(pick(CAST), pick(CAST))
        game.seats[0].hand = [BEAR]
        game.seats[0].battlefield = lands(2)
        game.seats[1].hand = [COUNTERSPELL]
        game.seats[1].battlefield = lands(2)
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].graveyard, [BEAR])
        self.assertEqual(game.seats[0].battlefield[-1].card, RAINBOW)
        self.assertEqual(game.stack, [])

    def test_countered_commander_can_return_to_command_zone(self):
        game, a, b = table(pick(CAST_COMMANDER, "Command zone"), pick(CAST))
        game.seats[0].command_zone = [COMMANDER]
        game.seats[0].commander_names = {COMMANDER.name}
        game.seats[0].battlefield = lands(1)
        game.seats[1].hand = [COUNTERSPELL]
        game.seats[1].battlefield = lands(2)
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].command_zone, [COMMANDER])
        self.assertIn(COMMAND_ZONE_PROMPT, [prompt for prompt, _ in a.prompts])
        self.assertEqual(game.commander_tax(game.seats[0], COMMANDER), 2)

    def test_spell_fizzles_when_its_target_is_gone(self):
        # A bolts the Bears; B responds by bolting them too. B's resolves first, so A's fizzles.
        game, a, _ = table(pick(CAST, "Grizzly Bears"), pick(CAST, "Grizzly Bears"))
        for seat in game.seats:
            seat.hand = [BOLT]
            seat.battlefield = lands(1)
        game.seats[1].battlefield.append(Permanent(BEAR))
        game._priority_round(game.seats[0])
        events = [(e["event"], e["seat"]) for e in a.events if e["event"] in ("resolve", "fizzle")]
        self.assertEqual(events, [("resolve", 1), ("fizzle", 0)])

    def test_fetch_basic_land(self):
        game, _, _ = table(pick(CAST), library=[BOLT] * 5 + [FOREST])
        game.seats[0].library = [BOLT] * 5 + [FOREST]
        game.seats[0].hand = [RAMPANT]
        game.seats[0].battlefield = lands(2)
        game._priority_round(game.seats[0])
        fetched = game.seats[0].battlefield[-1]
        self.assertEqual((fetched.card, fetched.tapped), (FOREST, True))
        self.assertNotIn(FOREST, game.seats[0].library)

    def test_unsupported_spell_does_nothing_and_says_so(self):
        game, a, _ = table(pick(CAST))
        game.seats[0].hand = [WEIRD]
        game.seats[0].battlefield = lands(1)
        game._priority_round(game.seats[0])
        resolve = next(e for e in a.events if e["event"] == "resolve")
        self.assertTrue(resolve["unsupported"])
        self.assertEqual(game.seats[0].graveyard, [WEIRD])


class ManaSourceTests(unittest.TestCase):
    def test_sol_ring_pays_two(self):
        game, _, _ = table()
        game.seats[0].hand = [OGRE]
        game.seats[0].battlefield = [Permanent(SOL_RING)] + lands(1)
        self.assertIn(CAST + "Gray Ogre", game.legal_actions(game.seats[0]))

    def test_mana_creatures_have_summoning_sickness(self):
        game, _, _ = table()
        game.seats[0].hand = [BEAR]
        elves = Permanent(ELVES, sick=True)
        game.seats[0].battlefield = [elves, Permanent(FOREST)]
        self.assertEqual(game.legal_actions(game.seats[0]), [PASS])
        elves.sick = False
        self.assertIn(CAST + "Grizzly Bears", game.legal_actions(game.seats[0]))

    def test_resolved_creature_is_sick_until_its_controllers_untap(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [ELVES]
        game.seats[0].battlefield = [Permanent(FOREST)]
        game._priority_round(game.seats[0])
        self.assertTrue(game.seats[0].battlefield[-1].sick)
        game.step = "untap"
        game._turn_based_actions(game.seats[0])
        self.assertFalse(game.seats[0].battlefield[-1].sick)


class PriorityTests(unittest.TestCase):
    def test_player_who_acts_gets_priority_again(self):
        log = []
        a = pick()
        b_casts = pick(CAST, "Player: A")

        def logged(name, policy):
            def inner(prompt, options):
                log.append(name)
                return policy(prompt, options)
            return inner

        game, _, _ = table(logged("A", a), logged("B", b_casts))
        game.seats[1].hand = [BOLT]
        game.seats[1].battlefield = lands(1)
        game._priority_round(game.seats[0])
        # A passes, B casts (and picks a target), B again, A passes, B passes -> resolves; A, B pass.
        self.assertEqual(log[:4], ["A", "B", "B", "B"])
        self.assertEqual(game.seats[0].life, 37)


if __name__ == "__main__":
    unittest.main()
