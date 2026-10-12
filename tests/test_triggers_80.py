"""Trigger effects of issue #80 that were still unsupported: the effect side of lines about sacrifices, searches, tokens,
batches of creatures, optional costs, and cards that work from the graveyard.

The lines are the issue's own; a card's other lines are not written here.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, PLAINS  # noqa: F401  (they live in tests/helpers.py; other tests still import them from here)
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_x_targets import script

RELIC = Card(name="Relic", type_line="Artifact", mana_cost="{1}", cmc=1.0)
SHRINE = Card(name="Shrine", type_line="Enchantment", mana_cost="{2}", cmc=2.0)
GREEN_BEAR = Card(name="Green Bear", type_line="Creature — Bear", colors=("G",), power="2", toughness="2", mana_cost="{1}{G}", cmc=2.0)
BIG = Card(name="Big", type_line="Creature — Giant", power="5", toughness="5", mana_cost="{4}{R}", cmc=5.0)


def card(text, name="Test", type_line="Creature — Test", **fields):
    return Card(name=name, type_line=type_line, oracle_text=text, power="2" if "Creature" in type_line else None,
                toughness="2" if "Creature" in type_line else None, **fields)


def supported(test, c):
    test.assertEqual(unsupported_lines(c), [], c.oracle_text)


def names(seat, zone="battlefield"):
    items = getattr(seat, zone)
    return sorted(p.card.name if isinstance(p, Permanent) else p.name for p in items)


def fire(game, seat, permanent, event, **kw):
    game.trigger(event, permanent, seat, **kw)
    run_stack(game)


def kill(game, *permanents):
    game._leave_together([(p, "destroyed") for p in permanents])
    run_stack(game)


class SacrificeAndSearchTests(unittest.TestCase):
    def test_sacrifice_two_lands_when_it_enters(self):
        field = card("When this land enters, sacrifice two lands.", "Lotus Field", "Land")
        supported(self, field)
        game, _ = table3(script("Plains", "Forest"))
        a = game.seats[0]
        a.battlefield = [Permanent(PLAINS), Permanent(FOREST), Permanent(FOREST)]
        field_permanent = Permanent(field)
        a.battlefield.append(field_permanent)
        fire(game, a, field_permanent, "enters")
        self.assertEqual(len(a.battlefield), 2)

    def test_equipped_creature_attacks_and_you_may_search_for_a_basic_land(self):
        bitterthorn = card("Whenever equipped creature attacks, you may search your library for a basic land card, put it onto the "
                           "battlefield tapped, then shuffle.", "Bitterthorn", "Legendary Artifact — Equipment")
        supported(self, bitterthorn)
        [ability] = triggered_abilities(bitterthorn)
        self.assertTrue(ability.optional)
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] + a.library
        holder = Permanent(bitterthorn)
        host = Permanent(BEAR)
        holder.attached_to = host
        a.battlefield = [holder, host]
        fire(game, a, holder, "host_attacks", subject=host)
        land = [p for p in a.battlefield if p.card.name == "Forest"]
        self.assertEqual((len(land), land[0].tapped), (1, True))

    def test_search_for_two_basic_plains_into_your_hand(self):
        map_ = card("When this artifact enters, search your library for up to two basic Plains cards, reveal them, put them into your "
                    "hand, then shuffle.", "Map", "Artifact")
        supported(self, map_)
        game, _ = table3(script("Plains", "Plains"))
        a = game.seats[0]
        a.library = [PLAINS, PLAINS, FOREST, Card(name="Temple", type_line="Land — Plains Forest")] + a.library
        permanent = Permanent(map_)
        a.battlefield = [permanent]
        fire(game, a, permanent, "enters")
        self.assertEqual(names(a, "hand"), ["Plains", "Plains"])  # a nonbasic Plains is not a basic Plains


class BatchTests(unittest.TestCase):
    OPPORTUNIST = card("Whenever one or more other creatures die, draw a card. This ability triggers only once each turn.", "Opportunist")

    def test_it_draws_once_for_creatures_that_die_together(self):
        supported(self, self.OPPORTUNIST)
        game, _ = table3()
        a = game.seats[0]
        watcher = Permanent(self.OPPORTUNIST)
        a.battlefield = [watcher, Permanent(BEAR), Permanent(BEAR)]
        before = len(a.hand)
        kill(game, *a.battlefield[1:])
        self.assertEqual(len(a.hand) - before, 1)

    def test_it_does_not_trigger_for_itself(self):
        game, _ = table3()
        a = game.seats[0]
        watcher = Permanent(self.OPPORTUNIST)
        a.battlefield = [watcher]
        kill(game, watcher)
        self.assertEqual(len(a.hand), 0)

    WELCOME = card("Whenever one or more creatures you control with mana value 3 or less enter, draw a card. This ability triggers "
                   "only once each turn.", "Welcome", "Enchantment")

    def test_a_cheap_creature_entering_draws_a_card_once_each_turn(self):
        supported(self, self.WELCOME)
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(self.WELCOME)]
        game._enter(a, Permanent(BEAR))
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_an_expensive_creature_does_not(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(self.WELCOME)]
        game._enter(a, Permanent(BIG))
        run_stack(game)
        self.assertEqual(len(a.hand), 0)


class EnchantedCreatureTests(unittest.TestCase):
    def test_its_controller_loses_life_and_you_gain_life_when_enchanted_creature_attacks(self):
        impetus = card("Whenever enchanted creature attacks, its controller loses 2 life and you gain 2 life.", "Impetus",
                       "Enchantment — Aura")
        supported(self, impetus)
        game, _ = table3()
        a, b, _ = game.seats
        host = Permanent(BEAR)
        b.battlefield = [host]
        aura = Permanent(impetus, attached_to=host)
        a.battlefield = [aura]
        fire(game, a, aura, "host_attacks", subject=host)
        self.assertEqual((a.life, b.life), (42, 38))

    def test_shielded_by_faith_moves_to_a_creature_that_enters(self):
        aura = card("Enchant creature\nWhenever a creature enters, you may attach this Aura to that creature.", "Shield", "Enchantment — Aura")
        supported(self, aura)
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        first = Permanent(BEAR)
        shield = Permanent(aura, attached_to=first)
        a.battlefield = [first, shield]
        second = Permanent(OGRE)
        game._enter(a, second)
        run_stack(game)
        self.assertIs(shield.attached_to, second)

    def test_a_token_for_an_enchantment_and_the_aura_may_move_to_it(self):
        chosen = card("Whenever an enchantment you control enters, create a 2/2 white Cat creature token. If that enchantment is an "
                      "Aura, you may attach it to the token.", "Chosen")
        supported(self, chosen)
        aura = card("Enchant creature", "Blessing", "Enchantment — Aura")
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        host = Permanent(BEAR)
        a.battlefield = [Permanent(chosen), host]
        blessing = Permanent(aura, attached_to=host)
        game._enter(a, blessing)
        run_stack(game)
        cat = next(p for p in a.battlefield if p.card.name == "Cat")
        self.assertIs(blessing.attached_to, cat)

    def test_a_token_for_a_plain_enchantment_has_nothing_to_attach(self):
        chosen = card("Whenever an enchantment you control enters, create a 2/2 white Cat creature token. If that enchantment is an "
                      "Aura, you may attach it to the token.", "Chosen")
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(chosen)]
        game._enter(a, Permanent(SHRINE))
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Cat" for p in a.battlefield), 1)

    def test_killian_taps_and_goads_a_creature_when_an_enchantment_enters(self):
        killian = card("Whenever an enchantment you control enters, tap up to one target creature and goad it.", "Killian")
        supported(self, killian)
        game, _ = table3(script("Bear"))
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        a.battlefield = [Permanent(killian)]
        game._enter(a, Permanent(SHRINE))
        run_stack(game)
        self.assertEqual((bear.tapped, game.goader_of(bear) is a), (True, True))


class GraveyardTargetTests(unittest.TestCase):
    def test_return_a_cheap_nonland_permanent_card_to_the_battlefield(self):
        research = card("When this enchantment enters, return target nonland permanent card with mana value 3 or less from your "
                        "graveyard to the battlefield.", "Research", "Enchantment")
        supported(self, research)
        game, _ = table3(script("Relic"))
        a = game.seats[0]
        a.graveyard = [FOREST, BIG, RELIC]
        permanent = Permanent(research)
        a.battlefield = [permanent]
        fire(game, a, permanent, "enters")
        self.assertEqual(names(a), ["Relic", "Research"])

    def test_exile_a_noncreature_nonland_card_and_make_a_spirit(self):
        loremaster = card("At the beginning of your end step, exile target noncreature, nonland card from your graveyard. Create a "
                          "3/2 red and white Spirit creature token.", "Loremaster")
        supported(self, loremaster)
        options = lambda game, a: [label for label, _ in game.target_options("graveyard:noncreature, nonland:yours", a)]
        game, _ = table3(script("Relic"))
        a = game.seats[0]
        a.graveyard = [FOREST, BEAR, RELIC]
        self.assertEqual(len(options(game, a)), 1)
        permanent = Permanent(loremaster)
        a.battlefield = [permanent]
        fire(game, a, permanent, "end_step")
        self.assertEqual((names(a, "exile"), [p.card.name for p in a.battlefield if p.card.name == "Spirit"]), (["Relic"], ["Spirit"]))

    def test_exile_a_cheap_nontoken_nonland_permanent_you_do_not_control(self):
        apparition = card("When this creature enters, exile up to one target nonland, nontoken permanent you don't control with mana "
                          "value 4 or less.", "Apparition")
        supported(self, apparition)
        treasure = Card(name="Treasure", type_line="Token Artifact — Treasure", mana_cost="")
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(RELIC), Permanent(treasure), Permanent(FOREST), Permanent(BIG), Permanent(BEAR)]
        labels = [label for label, _ in game.target_options("nonland, nontoken permanent you don't control with mana value 4 or less", a)]
        self.assertEqual(len(labels), 2)  # the Relic and the Bear


class TokenTests(unittest.TestCase):
    def test_a_copy_of_the_creature_when_a_big_spell_is_cast(self):
        composer = card("Whenever you cast an instant or sorcery spell with mana value 5 or greater, create a token that's a copy of this "
                        "creature.", "Composer")
        supported(self, composer)
        game, _ = table3()
        a = game.seats[0]
        permanent = Permanent(composer)
        a.battlefield = [permanent]
        big_spell = Card(name="Big Spell", type_line="Sorcery", mana_cost="{5}", cmc=5.0, oracle_text="Draw a card.")
        small = Card(name="Small", type_line="Sorcery", mana_cost="{1}", cmc=1.0, oracle_text="Draw a card.")
        a.cast_log.append((game.turn, big_spell))
        game._observe("cast", big_spell, a)
        game._observe("cast", small, a)
        run_stack(game)
        tokens = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual([t.card.name for t in tokens], ["Composer"])

    def test_half_x_food_tokens_rounded_up(self):
        goose = card("When CARDNAME enters, create half X Food tokens, rounded up.", "Goose")
        supported(self, goose)
        for x, expected in ((5, 3), (4, 2), (0, 0)):
            game, _ = table3()
            a = game.seats[0]
            permanent = Permanent(goose)
            a.battlefield = [permanent]
            game.trigger("enters", permanent, a, x=x)
            run_stack(game)
            self.assertEqual(sum(p.card.name == "Food" for p in a.battlefield), expected, x)

    def test_sacrifice_a_food_to_draw_a_card(self):
        goose = card("Whenever CARDNAME attacks, you may sacrifice a Food. If you do, draw a card.", "Goose")
        supported(self, goose)
        food = Card(name="Food", type_line="Token Artifact — Food")
        game, _ = table3(pick("Yes", "Food"))
        a = game.seats[0]
        permanent = Permanent(goose)
        a.battlefield = [permanent, Permanent(food)]
        fire(game, a, permanent, "attacks")
        self.assertEqual((len(a.hand), names(a)), (1, ["Goose"]))

    def test_tapped_treasures_equal_to_its_power_when_it_dies(self):
        hydra = card("When this creature dies, create a number of tapped Treasure tokens equal to its power.", "Hydra")
        supported(self, hydra)
        game, _ = table3()
        a = game.seats[0]
        permanent = Permanent(hydra, counters={"+1/+1": 2})
        a.battlefield = [permanent]
        kill(game, permanent)
        treasures = [p for p in a.battlefield if p.card.name == "Treasure"]
        self.assertEqual((len(treasures), all(t.tapped for t in treasures)), (4, True))

    def test_a_spawn_that_can_be_sacrificed_for_mana(self):
        zone = card('At the beginning of your upkeep, you may create a 0/1 colorless Eldrazi Spawn creature token. It has "Sacrifice this '
                    'token: Add {C}."', "Zone", "Enchantment")
        supported(self, zone)
        game, _ = table3()
        a = game.seats[0]
        permanent = Permanent(zone)
        a.battlefield = [permanent]
        fire(game, a, permanent, "upkeep")
        spawn = next(p for p in a.battlefield if p.card.name == "Eldrazi Spawn")
        self.assertIn("Add {C}", spawn.card.oracle_text)

    def test_populate_gives_haste_and_the_token_is_sacrificed_at_end_step(self):
        iteration = card("At the beginning of combat on your turn, populate. The token created this way gains haste. Sacrifice it at the "
                         "beginning of the next end step.", "Iteration", "Enchantment")
        supported(self, iteration)
        game, _ = table3()
        a = game.seats[0]
        soldier = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1")
        permanent = Permanent(iteration)
        a.battlefield = [permanent, Permanent(soldier)]
        fire(game, a, permanent, "combat")
        copies = [p for p in a.battlefield if p.card.name == "Soldier"]
        self.assertEqual(len(copies), 2)
        self.assertTrue(game.has_keyword(copies[1], "haste"))
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Soldier"]), 1)


class AmountTests(unittest.TestCase):
    def test_creatures_gain_flying_and_get_plus_x_for_each_creature(self):
        cavalry = card("When this creature enters, creatures you control gain flying and get +X/+X until end of turn, where X is the "
                       "number of creatures you control.", "Cavalry")
        supported(self, cavalry)
        game, _ = table3()
        a, b, _ = game.seats
        permanent = Permanent(cavalry)
        other, theirs = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [permanent, other]
        b.battlefield = [theirs]
        fire(game, a, permanent, "enters")
        self.assertEqual((game.power(other), game.has_keyword(other, "flying"), game.power(theirs)), (4, True, 2))

    def test_plus_x_where_x_is_the_mana_value_of_the_spell_cast(self):
        bull = card("Whenever you cast an instant or sorcery spell, this creature gets +X/+0 until end of turn, where X is that spell's "
                    "mana value.", "Bull")
        supported(self, bull)
        game, _ = table3(script(CAST))
        a = game.seats[0]
        permanent = Permanent(bull)
        a.battlefield = [permanent, *lands(4)]
        spell = Card(name="Spell", type_line="Instant", mana_cost="{3}", cmc=3.0, oracle_text="You gain 1 life.")
        a.hand = [spell]
        game._perform(a, CAST + "Spell")
        run_stack(game)
        self.assertEqual(game.power(permanent), 5)

    def test_gain_and_draw_half_x_when_cast(self):
        krasis = Card(name="Krasis", mana_cost="{X}{G}{U}", type_line="Creature — Hydra", power="0", toughness="0",
                      oracle_text="When you cast this spell, you gain half X life and draw half X cards. Round down each time.")
        supported(self, krasis)
        game, _ = table3(script(CAST, "5"))
        a = game.seats[0]
        a.hand = [krasis]
        a.battlefield = lands(8)
        game._priority_round(a)
        self.assertEqual((a.life, len(a.hand)), (42, 2))


class OptionalCostTests(unittest.TestCase):
    TRUDGE = card("Whenever you gain life, you may pay {2}. If you do, create a 4/4 green Fungus Beast creature token with trample.",
                  "Trudge", "Enchantment")

    def test_pay_to_make_a_token(self):
        supported(self, self.TRUDGE)
        game, _ = table3(pick("Pay"))
        a = game.seats[0]
        a.battlefield = [Permanent(self.TRUDGE), *lands(2)]
        game.change_life(a, 1)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Fungus Beast" for p in a.battlefield), 1)
        self.assertTrue(all(p.tapped for p in a.battlefield if "Land" in p.card.type_line))

    def test_declining_makes_nothing(self):
        game, _ = table3(pick("Don't"))
        a = game.seats[0]
        a.battlefield = [Permanent(self.TRUDGE), *lands(2)]
        game.change_life(a, 1)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Fungus Beast" for p in a.battlefield), 0)

    def test_without_the_mana_nothing_happens(self):
        game, _ = table3(pick("Pay"))
        a = game.seats[0]
        a.battlefield = [Permanent(self.TRUDGE), *lands(1)]
        game.change_life(a, 1)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Fungus Beast" for p in a.battlefield), 0)

    def test_pay_to_return_a_creature_card(self):
        coven = card("Whenever you gain life, you may pay {B}. If you do, return target creature card from your graveyard to your hand.",
                     "Coven", "Enchantment")
        supported(self, coven)
        game, _ = table3(script("Bear", "Pay"))
        a = game.seats[0]
        a.battlefield = [Permanent(coven), *lands(1)]
        a.graveyard = [BEAR]
        game.change_life(a, 1)
        run_stack(game)
        self.assertEqual((names(a, "hand"), a.graveyard), (["Bear"], []))

    def test_pay_and_discard_to_draw(self):
        theorist = card("Whenever this creature attacks, you may pay {1} and discard a card. If you do, draw a card.", "Theorist")
        supported(self, theorist)
        game, _ = table3(pick("Pay", "Relic"))
        a = game.seats[0]
        permanent = Permanent(theorist)
        a.battlefield = [permanent, *lands(1)]
        a.hand = [RELIC]
        a.library = [SHRINE] + a.library
        fire(game, a, permanent, "attacks")
        self.assertEqual((names(a, "hand"), names(a, "graveyard")), (["Shrine"], ["Relic"]))

    def test_remove_a_counter_to_draw(self):
        prodigy = card("At the beginning of your upkeep, if this creature has one or more +1/+1 counters on it, you may remove a +1/+1 "
                       "counter from it. If you do, draw a card.", "Prodigy")
        supported(self, prodigy)
        for counters, expected in ((1, 1), (0, 0)):
            game, _ = table3(pick("Yes"))
            a = game.seats[0]
            permanent = Permanent(prodigy, counters={"+1/+1": counters} if counters else {})
            a.battlefield = [permanent]
            fire(game, a, permanent, "upkeep")
            self.assertEqual((len(a.hand), permanent.counters.get("+1/+1", 0)), (expected, 0), counters)

    def test_the_second_ability_of_a_class_style_trigger_with_a_condition(self):
        jadar = card("At the beginning of your end step, if you control no creatures with decayed, create a 2/2 black Zombie creature "
                     "token with decayed.", "Jadar")
        supported(self, jadar)
        game, _ = table3()
        a = game.seats[0]
        permanent = Permanent(jadar)
        a.battlefield = [permanent]
        fire(game, a, permanent, "end_step")
        fire(game, a, permanent, "end_step")
        self.assertEqual(sum(p.card.name == "Zombie" for p in a.battlefield), 1)  # the second time it controls one already


class DecayedTests(unittest.TestCase):
    ZOMBIE = Card(name="Zombie", type_line="Token Creature — Zombie", power="2", toughness="2", oracle_text="Decayed")

    def test_decayed_cannot_block(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(BEAR)]
        b.battlefield = [Permanent(self.ZOMBIE)]
        zombie, attacker = b.battlefield[0], a.battlefield[0]
        self.assertFalse(game.combat._can_block(zombie, attacker))

    def test_decayed_is_sacrificed_at_end_of_combat_after_attacking(self):
        policy = lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(policy, policy)
        a = game.seats[0]
        a.battlefield = [Permanent(self.ZOMBIE)]
        game.combat.declare_attackers(a)
        self.assertEqual(len(game.combat.attacks), 1)
        game.step = "main2"
        game._turn_based_actions(a)
        self.assertEqual(a.battlefield, [])


class GraveyardAndDiscardTests(unittest.TestCase):
    def test_squee_returns_from_the_graveyard_at_upkeep(self):
        squee = card("At the beginning of your upkeep, you may return this card from your graveyard to your hand.", "Squee")
        supported(self, squee)
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.graveyard = [squee]
        game.step = "upkeep"
        game.active = 0
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual((names(a, "hand"), a.graveyard), (["Squee"], []))

    def test_squee_on_the_battlefield_does_nothing_at_upkeep(self):
        squee = card("At the beginning of your upkeep, you may return this card from your graveyard to your hand.", "Squee")
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(squee)]
        game.step = "upkeep"
        game._turn_based_actions(a)
        self.assertEqual(game.pending, [])

    def test_exile_a_discarded_card_and_play_it_this_turn(self):
        construct = card("Whenever you discard a card, you may exile that card from your graveyard. If you do, you may play that card "
                         "this turn.", "Construct", "Artifact Creature — Construct")
        supported(self, construct)
        game, _ = table3(pick("Yes", "Forest"))
        a = game.seats[0]
        a.battlefield = [Permanent(construct)]
        a.hand = [FOREST]
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual((a.graveyard, names(a, "exile")), ([], ["Forest"]))
        self.assertEqual([c.name for c, until in a.exile_play], ["Forest"])

    def test_exile_a_discarded_card_without_playing_it(self):
        converter = card("Whenever you discard a card, you may exile that card from your graveyard.", "Converter", "Artifact")
        supported(self, converter)
        game, _ = table3(pick("Yes", "Forest"))
        a = game.seats[0]
        a.battlefield = [Permanent(converter)]
        a.hand = [FOREST]
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual((a.graveyard, names(a, "exile"), a.exile_play), ([], ["Forest"], []))


class MiscTests(unittest.TestCase):
    def test_a_counter_when_an_enchantment_you_control_goes_to_the_graveyard(self):
        mystic = card("Whenever an enchantment you control is put into a graveyard from the battlefield, put a +1/+1 counter on this "
                      "creature.", "Mystic")
        supported(self, mystic)
        game, _ = table3()
        a = game.seats[0]
        permanent = Permanent(mystic)
        shrine = Permanent(SHRINE)
        a.battlefield = [permanent, shrine, Permanent(RELIC)]
        kill(game, a.battlefield[2])
        self.assertEqual(permanent.counters, {})
        kill(game, shrine)
        self.assertEqual(permanent.counters, {"+1/+1": 1})

    def test_treasure_when_it_attacks_or_becomes_the_target_of_a_spell(self):
        dragon = card("Whenever this creature attacks or becomes the target of a spell, create a Treasure token.", "Dragon")
        supported(self, dragon)
        self.assertEqual(sorted(a.event for a in triggered_abilities(dragon)), ["attacks", "targeted"])
        game, _ = table3(script("Dragon"))
        a = game.seats[0]
        permanent = Permanent(dragon)
        a.battlefield = [permanent, *lands(2)]
        a.hand = [Card(name="Bolt", type_line="Instant", mana_cost="{R}", cmc=1.0, oracle_text="CARDNAME deals 3 damage to any target.")]
        game._perform(a, CAST + "Bolt")
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Treasure" for p in a.battlefield), 1)

    def test_you_may_copy_the_first_x_spell_each_turn(self):
        spiralmancer = card("Whenever you cast your first spell with {X} in its mana cost each turn, you may copy it. You may choose new "
                            "targets for the copy.", "Spiralmancer")
        supported(self, spiralmancer)
        [ability] = triggered_abilities(spiralmancer)
        self.assertTrue(ability.optional)

    def test_mill_exile_at_random_and_play_it(self):
        reconstruction = card("At the beginning of your first main phase, mill a card, then exile a card from your graveyard at random. "
                              "You may play the exiled card this turn.", "Reconstruction", "Class — Test")
        supported(self, reconstruction)
        game, _ = table3()
        a = game.seats[0]
        permanent = Permanent(reconstruction)
        a.battlefield = [permanent]
        a.library = [RELIC] + a.library
        fire(game, a, permanent, "first_main")
        self.assertEqual((names(a, "exile"), a.graveyard), (["Relic"], []))
        self.assertEqual([c.name for c, until in a.exile_play], ["Relic"])


if __name__ == "__main__":
    unittest.main()
