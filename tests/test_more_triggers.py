import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Draw, GainLife, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, attack_all, creature
from tests.test_effects import table

DRYAD = Card(name="Dryad", mana_cost="{G}", type_line="Enchantment",
             oracle_text="At the beginning of each upkeep, you gain 1 life.")
WATCHMAN = Card(name="Watchman", mana_cost="{W}", type_line="Enchantment",
                oracle_text="At the beginning of each end step, you gain 1 life.")
DRUMMER = Card(name="Drummer", mana_cost="{R}", type_line="Enchantment",
               oracle_text="At the beginning of combat on your turn, you gain 1 life.")
DINA = Card(name="Dina, Soul Steeper", mana_cost="{B}{G}", type_line="Legendary Creature — Dryad Druid",
            power="1", toughness="3", oracle_text="Whenever you gain life, each opponent loses 1 life.")
MOURNER = Card(name="Mourner", mana_cost="{B}", type_line="Enchantment",
               oracle_text="Whenever you lose life, draw a card.")
ABOMINATION = creature("Abomination", 4, 3, "Whenever you sacrifice a creature, draw a card.")
HARNESS = Card(name="Harness", mana_cost="{1}", type_line="Artifact — Equipment",
               oracle_text="When this Equipment enters, draw a card.\nEquip {1}")
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")

OHRAN = Card(name="Ohran", mana_cost="{G}", type_line="Enchantment",
             oracle_text="Whenever a creature you control deals combat damage to a player, draw a card.")
CRAFTER = Card(name="Crafter", mana_cost="{U}", type_line="Enchantment",
               oracle_text="Whenever a creature token you control deals combat damage to a player, draw a card.")
SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")
BOOTS = Card(name="Boots", mana_cost="{1}", type_line="Artifact — Equipment",
             oracle_text="Whenever equipped creature attacks, you gain 2 life.\nEquip {1}")
IMPETUS = Card(name="Impetus", mana_cost="{B}", type_line="Enchantment — Aura",
               oracle_text="Enchant creature\nWhenever enchanted creature attacks, draw a card.")
COMMANDO = Card(name="Commando", mana_cost="{R}", type_line="Enchantment",
                oracle_text="Whenever you attack with two or more creatures, draw a card.")
LIEGE = Card(name="Liege", mana_cost="{R}", type_line="Enchantment",
             oracle_text="Whenever you cast a red spell, you gain 3 life.")
DANCER = Card(name="Dancer", mana_cost="{W}", type_line="Enchantment",
              oracle_text="Whenever you cast an Aura spell, you may draw a card.")
SRAM = Card(name="Sram", mana_cost="{W}", type_line="Enchantment",
            oracle_text="Whenever you cast an Aura, Equipment, or Vehicle spell, draw a card.")
TESHAR = Card(name="Teshar", mana_cost="{W}", type_line="Enchantment",
              oracle_text="Whenever you cast a historic spell, you gain 1 life.")
ANCIENT = Card(name="Ancient", mana_cost="{G}", type_line="Enchantment",
               oracle_text="Whenever a player casts a spell, you gain 1 life.")
TAXMAN = Card(name="Taxman", mana_cost="{W}", type_line="Enchantment",
              oracle_text="Whenever an opponent casts a spell, you gain 1 life.")
BOLT = Card(name="Bolt", mana_cost="{R}", type_line="Instant", colors=("R",), oracle_text="Draw a card.")
LEGEND = Card(name="Legend", mana_cost="{W}", type_line="Legendary Creature — Human", colors=("W",),
              power="1", toughness="1")

QUINTORIUS = Card(name="Quintorius", mana_cost="{R}{W}", type_line="Legendary Creature — Elephant",
                  power="2", toughness="5",
                  oracle_text="Whenever one or more cards leave your graveyard, you gain 1 life.")
YAHENNI = creature("Yahenni", 2, 2, "Whenever a creature an opponent controls dies, put a +1/+1 counter on this creature.")
MERCHANT = creature("Merchant", 2, 2, "Whenever a player sacrifices a permanent, put a +1/+1 counter on this creature.")
MAZIREK = creature("Mazirek", 2, 2, "Whenever a player sacrifices another permanent, you gain 1 life.")
DESTINY = Card(name="Destiny", mana_cost="{W}", type_line="Enchantment — Aura",
               oracle_text="Enchant creature\nWhen enchanted creature dies, draw a card.")
CHIROGRAPHY = Card(name="Chirography", mana_cost="{B}", type_line="Enchantment",
                   oracle_text="Whenever you lose life for the first time each turn, draw a card.")
BREWER = creature("Brewer", 1, 1, "Whenever you sacrifice a creature, draw a card. This ability triggers only once each turn.")


def resolve_triggers(game, seat):
    game._priority_round(seat)


class ParseTests(unittest.TestCase):
    def test_new_events(self):
        cases = {DRYAD: "each_upkeep", WATCHMAN: "each_end_step", DRUMMER: "combat", DINA: "gain_life",
                 MOURNER: "lose_life", ABOMINATION: "sacrifice_creature"}
        for card, event in cases.items():
            [ability] = triggered_abilities(card)
            self.assertEqual(ability.event, event, card.name)
        self.assertEqual(triggered_abilities(DRYAD)[0].effects, (GainLife(1),))

    def test_aura_equipment_and_class_call_themselves_this(self):
        [ability] = triggered_abilities(HARNESS)
        self.assertEqual((ability.event, ability.effects), ("enters", (Draw(1),)))
        for kind in ("Aura", "Class", "Vehicle", "Saga"):
            card = Card(name="x", oracle_text=f"When this {kind} enters, draw a card.")
            self.assertEqual(triggered_abilities(card)[0].event, "enters", kind)

    def test_report_accepts_them(self):
        for card in (DRYAD, WATCHMAN, DRUMMER, DINA, MOURNER, ABOMINATION):
            self.assertEqual(unsupported_lines(card), [], card.name)


class TimingTests(unittest.TestCase):
    def test_each_upkeep_triggers_on_every_players_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DRYAD)]
        game.turn = 3
        game._take_turn(b)
        self.assertEqual(a.life, 41)
        game._take_turn(a)
        self.assertEqual(a.life, 42)

    def test_each_end_step_triggers_on_every_players_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(WATCHMAN)]
        game.turn = 3
        game._take_turn(b)
        self.assertEqual(a.life, 41)

    def test_beginning_of_combat_only_on_your_turn(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DRUMMER)]
        game.turn = 3
        game._take_turn(b)
        self.assertEqual(a.life, 40)
        game._take_turn(a)
        self.assertEqual(a.life, 41)


class PlayerEventTests(unittest.TestCase):
    def test_gaining_life_triggers(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DINA)]
        game.change_life(a, 3)
        resolve_triggers(game, a)
        self.assertEqual(b.life, 39)  # once per life-gain event, not per point

    def test_losing_life_or_an_opponent_gaining_doesnt_trigger_gain(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(DINA)]
        game.change_life(a, -3)
        game.change_life(b, 3)
        resolve_triggers(game, a)
        self.assertEqual(b.life, 43)

    def test_losing_life_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(MOURNER)]
        a.library = [BEAR, BEAR]
        game.change_life(a, -2)
        game.change_life(a, 0)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [BEAR])

    def test_sacrificing_a_creature_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ABOMINATION), Permanent(BEAR)]
        a.library = [BEAR, BEAR]
        game.sacrifice(a)
        resolve_triggers(game, a)
        self.assertEqual(len(a.hand), 1)

    def test_sacrificing_the_watcher_itself_triggers(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ABOMINATION)]
        a.library = [BEAR]
        game.sacrifice(a)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [BEAR])  # it looks back in time (CR 603.10a)

    def test_destroying_or_sacrificing_a_noncreature_doesnt_trigger(self):
        game, _, _ = table()
        a = game.seats[0]
        bear, treasure = Permanent(BEAR), Permanent(TREASURE)
        a.battlefield = [Permanent(ABOMINATION), bear, treasure]
        a.library = [BEAR]
        game.destroy(bear)
        game._leave_battlefield(treasure, "sacrificed")
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [])

    def test_opponents_sacrifice_doesnt_trigger(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(ABOMINATION)]
        b.battlefield = [Permanent(BEAR)]
        a.library = [BEAR]
        game.sacrifice(b)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [])


def take_turn_attacking(game, seat):
    game.turn = 3
    game._take_turn(seat)


class CombatTriggerTests(unittest.TestCase):
    def test_a_creature_you_control_deals_combat_damage(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(OHRAN), Permanent(BEAR), Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1 + 2)  # draw step, then once per creature

    def test_only_tokens_count_for_token_triggers(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(CRAFTER), Permanent(BEAR), Permanent(SPIRIT)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1 + 1)

    def test_opponents_creatures_dont_count(self):
        game, _, _ = table(None, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(OHRAN)]
        b.battlefield = [Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, b)
        self.assertEqual(a.hand, [])

    def test_equipped_and_enchanted_creature_attacks(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(BOOTS, attached_to=bear), Permanent(IMPETUS, attached_to=bear)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(a.life, 42)
        self.assertEqual(len(a.hand), 1 + 1)

    def test_attachment_on_a_creature_that_doesnt_attack(self):
        game, _, _ = table()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(BOOTS, attached_to=bear)]
        take_turn_attacking(game, a)
        self.assertEqual(a.life, 40)

    def test_attack_with_two_or_more(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(COMMANDO), Permanent(BEAR), Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1 + 1)
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(COMMANDO), Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1)


class CastFilterTests(unittest.TestCase):
    def cast(self, watcher, spell, by=0, controller=0):
        game, _, _ = table(lambda prompt, options: 0)
        game.seats[controller].battlefield = [Permanent(watcher)]
        game.seats[controller].library = [BEAR] * 3
        game._observe("cast", spell, game.seats[by])
        game._put_triggers_on_stack()
        return game, len(game.stack)

    def test_color(self):
        self.assertEqual(self.cast(LIEGE, BOLT)[1], 1)
        self.assertEqual(self.cast(LIEGE, LEGEND)[1], 0)

    def test_aura(self):
        self.assertEqual(self.cast(DANCER, IMPETUS)[1], 1)
        self.assertEqual(self.cast(DANCER, BOOTS)[1], 0)

    def test_aura_equipment_or_vehicle(self):
        self.assertEqual(self.cast(SRAM, IMPETUS)[1], 1)
        self.assertEqual(self.cast(SRAM, BOOTS)[1], 1)
        self.assertEqual(self.cast(SRAM, BOLT)[1], 0)

    def test_historic(self):
        self.assertEqual(self.cast(TESHAR, LEGEND)[1], 1)
        self.assertEqual(self.cast(TESHAR, BOOTS)[1], 1)  # artifacts are historic
        self.assertEqual(self.cast(TESHAR, BOLT)[1], 0)

    def test_a_player_casts(self):
        self.assertEqual(self.cast(ANCIENT, BOLT, by=0)[1], 1)
        self.assertEqual(self.cast(ANCIENT, BOLT, by=1)[1], 1)

    def test_an_opponent_casts(self):
        self.assertEqual(self.cast(TAXMAN, BOLT, by=0)[1], 0)
        self.assertEqual(self.cast(TAXMAN, BOLT, by=1)[1], 1)

    def test_report_accepts_them(self):
        for card in (OHRAN, CRAFTER, BOOTS, IMPETUS, COMMANDO, LIEGE, DANCER, SRAM, TESHAR, ANCIENT, TAXMAN):
            self.assertEqual(unsupported_lines(card), [], card.name)


class WatchingMoreTests(unittest.TestCase):
    def test_cards_leaving_your_graveyard_trigger_once_per_event(self):
        from infernal_machine.game import GraveyardTarget
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(QUINTORIUS)]
        a.graveyard = [BEAR, BEAR, BEAR]
        game.return_from_graveyard(GraveyardTarget(a.graveyard[0], a), a, "hand")
        game.exile_graveyard(a)  # two cards, one event
        game.exile_graveyard(a)  # nothing left: no event
        game.exile_graveyard(b)  # someone else's graveyard
        resolve_triggers(game, a)
        self.assertEqual(a.life, 42)

    def test_a_creature_an_opponent_controls_dies(self):
        game, _, _ = table()
        a, b = game.seats
        yahenni, mine, theirs = Permanent(YAHENNI), Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [yahenni, mine]
        b.battlefield = [theirs]
        game.destroy(mine)
        game.destroy(theirs)
        resolve_triggers(game, a)
        self.assertEqual(yahenni.counters, {"+1/+1": 1})

    def test_a_player_sacrifices_a_permanent(self):
        game, _, _ = table()
        a, b = game.seats
        merchant = Permanent(MERCHANT)
        a.battlefield = [merchant, Permanent(TREASURE)]
        b.battlefield = [Permanent(BEAR)]
        game._leave_battlefield(a.battlefield[1], "sacrificed")
        game.sacrifice(b)
        game.destroy(merchant)  # not a sacrifice
        game.seats[0].battlefield = [merchant]
        resolve_triggers(game, a)
        self.assertEqual(merchant.counters, {"+1/+1": 2})

    def test_another_permanent_excludes_itself(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(MAZIREK)]
        game.sacrifice(a)
        resolve_triggers(game, a)
        self.assertEqual(a.life, 40)
        a.battlefield = [Permanent(MAZIREK), Permanent(TREASURE)]
        game._leave_battlefield(a.battlefield[1], "sacrificed")
        resolve_triggers(game, a)
        self.assertEqual(a.life, 41)

    def test_enchanted_creature_dies(self):
        game, _, _ = table()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(DESTINY, attached_to=bear)]
        a.library = [BEAR]
        game.destroy(bear)
        resolve_triggers(game, a)
        self.assertEqual(a.hand, [BEAR])


class OncePerTurnTests(unittest.TestCase):
    def test_first_life_loss_each_turn(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(CHIROGRAPHY)]
        a.library = [BEAR] * 3
        game.change_life(a, -1)
        game.change_life(a, -1)
        resolve_triggers(game, a)
        self.assertEqual(len(a.hand), 1)
        game.turn += 1
        game.change_life(a, -1)
        resolve_triggers(game, a)
        self.assertEqual(len(a.hand), 2)

    def test_triggers_only_once_each_turn(self):
        game, _, _ = table()
        a = game.seats[0]
        brewer = Permanent(BREWER)
        a.battlefield = [Permanent(BEAR), Permanent(BEAR), Permanent(BEAR), brewer]
        a.library = [BEAR] * 3
        [ability] = triggered_abilities(BREWER)
        self.assertEqual((ability.effects, ability.once_per_turn), ((Draw(1),), True))
        for _ in range(2):
            game.sacrifice(a)  # the first creature offered: a Bear
        resolve_triggers(game, a)
        self.assertEqual(len(a.hand), 1)
        game.turn += 1
        game.sacrifice(a)
        resolve_triggers(game, a)
        self.assertEqual(len(a.hand), 2)

    def test_report_accepts_them(self):
        for card in (QUINTORIUS, YAHENNI, MERCHANT, MAZIREK, DESTINY, CHIROGRAPHY, BREWER):
            self.assertEqual(unsupported_lines(card), [], card.name)


if __name__ == "__main__":
    unittest.main()
