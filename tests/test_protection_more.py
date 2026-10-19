import unittest

from infernal_machine.cards import Card
from infernal_machine.characteristics import source_qualities
from infernal_machine.effects import GrantProtection, activated_abilities, printed_protection, protection_tokens, spell_effects, ward_cost
from infernal_machine.game import ACTIVATE, CAST, PASS, PROTECTION_PROMPT, WARD_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, creature
from tests.test_effects import lands, pick
from tests.test_protection_ward import BOLT, GREEN_BEAR, PLAIN, RED_OGRE, table2

IMMORTAL = creature("Immortal", 2, 2, "Protection from everything")
BUILDER = creature("Armor Plated", 2, 2, "Protection from creatures")
HATER = creature("Mono Hater", 2, 2, "Protection from monocolored")
SNOB = creature("Snob", 2, 2, "Protection from multicolored")
NO_SPELLS = creature("Untouchable", 2, 2, "Protection from instants and from sorceries")
PRISM = creature("Prism Guard", 2, 2, "Protection from all colors")
LIFE_WARD = creature("Blood Ward", 2, 2, "Ward—Pay 3 life.")
DISCARD_WARD = creature("Hand Ward", 2, 2, "Ward—Discard a card.")
COMBO_WARD = creature("Combo Ward", 2, 2, "Ward—{1}, Pay 2 life.")
LORD = creature("Warding Lord", 2, 2, "Other creatures you control have ward {1}.")
MOTHER = Card(name="Mother of Runes", mana_cost="{W}", type_line="Creature — Human Cleric", power="1", toughness="1",
              oracle_text="{T}: Target creature you control gains protection from the color of your choice until end of turn.")
GODS_WILLING = REAL["Gods Willing"]
SELF_SHIELD = creature("Pro Self", 1, 1, "{W}: CARDNAME gains protection from the color of your choice until end of turn.")
BLUE_ARTIFACT = Card(name="Blue Thing", mana_cost="{2}", type_line="Artifact Creature — Construct", colors=("U",),
                     power="1", toughness="1")
GOLD_CREATURE = Card(name="Gold", mana_cost="{R}{G}", type_line="Creature — Test", colors=("R", "G"), power="2", toughness="2")
COLORLESS_ARTIFACT = Card(name="Rock", mana_cost="{1}", type_line="Artifact")
SORCERY = REAL["Fell"]
class QualityTests(unittest.TestCase):
    def test_what_a_source_is(self):
        self.assertEqual(source_qualities(BOLT), {"R", "instant", "monocolored"})
        self.assertEqual(source_qualities(GOLD_CREATURE), {"R", "G", "creature", "multicolored"})
        self.assertEqual(source_qualities(COLORLESS_ARTIFACT), {"artifact", "colorless"})

    def test_parsing_what_a_card_is_protected_from(self):
        self.assertEqual(printed_protection(IMMORTAL), frozenset({"everything"}))
        self.assertEqual(printed_protection(BUILDER), frozenset({"creature"}))
        self.assertEqual(printed_protection(NO_SPELLS), frozenset({"instant", "sorcery"}))
        self.assertEqual(printed_protection(PRISM), frozenset("WUBRG"))
        self.assertEqual(protection_tokens("protection from monocolored"), frozenset({"monocolored"}))

    def test_the_report(self):
        for card in (IMMORTAL, BUILDER, HATER, SNOB, NO_SPELLS, PRISM, LIFE_WARD, DISCARD_WARD, COMBO_WARD, LORD, MOTHER,
                     GODS_WILLING, SELF_SHIELD):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ProtectionTests(unittest.TestCase):
    def setup(self, card):
        game, _ = table2()
        permanent = Permanent(card)
        game.seats[1].battlefield = [permanent]
        return game, permanent

    def targets(self, game, source):
        return [label for label, _ in game.target_options("creature", game.seats[0], source_qualities(source))]

    def test_everything(self):
        game, immortal = self.setup(IMMORTAL)
        for source in (BOLT, SORCERY, BEAR, COLORLESS_ARTIFACT):
            self.assertEqual(self.targets(game, source), [], source.name)
        self.assertTrue(game.protected_from(immortal, source_qualities(BEAR)))

    def test_everything_and_creatures_cannot_be_blocked_by_creatures(self):
        for card in (IMMORTAL, BUILDER):
            game, attacker = self.setup(card)
            blocker = Permanent(GREEN_BEAR)
            game.seats[0].battlefield = [blocker]
            self.assertFalse(game.combat._can_block(blocker, attacker), card.name)
        game, attacker = self.setup(HATER)  # a monocolored blocker can't block it, a colorless one can
        colorless = Permanent(creature("Golem", 2, 2))
        self.assertFalse(game.combat._can_block(Permanent(GREEN_BEAR), attacker))
        self.assertTrue(game.combat._can_block(colorless, attacker))

    def test_creatures(self):
        game, _ = self.setup(BUILDER)
        self.assertEqual(self.targets(game, BEAR), [])  # a creature's ability
        self.assertEqual(len(self.targets(game, BOLT)), 1)  # a spell is fine

    def test_creature_damage_is_prevented_but_spell_damage_is_not(self):
        game, builder = self.setup(BUILDER)
        game.damage(builder, 2, Permanent(RED_OGRE))
        self.assertEqual(builder.damage, 0)
        game.resolving_colors = source_qualities(BOLT)
        game.damage(builder, 2)
        self.assertEqual(builder.damage, 2)

    def test_monocolored_and_multicolored(self):
        game, _ = self.setup(HATER)
        self.assertEqual((self.targets(game, BOLT), len(self.targets(game, GOLD_CREATURE)),
                          len(self.targets(game, COLORLESS_ARTIFACT))), ([], 1, 1))
        game, _ = self.setup(SNOB)
        self.assertEqual((len(self.targets(game, BOLT)), self.targets(game, GOLD_CREATURE)), (1, []))

    def test_card_types(self):
        game, _ = self.setup(NO_SPELLS)
        self.assertEqual((self.targets(game, BOLT), self.targets(game, SORCERY), len(self.targets(game, BEAR))), ([], [], 1))

    def test_all_colors(self):
        game, _ = self.setup(PRISM)
        self.assertEqual((self.targets(game, BOLT), self.targets(game, BLUE_ARTIFACT), len(self.targets(game, COLORLESS_ARTIFACT))),
                         ([], [], 1))

    def test_an_aura_falls_off_when_the_host_has_protection_from_its_type(self):
        game, _ = self.setup(creature("Shielded", 2, 2, "Protection from enchantments"))
        aura = Card(name="Blessing", mana_cost="{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature\nEnchanted creature gets +1/+1.")
        host = game.seats[1].battlefield[0]
        game.seats[1].battlefield.append(Permanent(aura, attached_to=host))
        game._check_state()
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Shielded"])


class ChosenColorTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(GODS_WILLING)[0], GrantProtection("creature you control"))

    def test_the_controller_picks_the_color(self):
        picks = iter([3])  # red
        base = pick(CAST)
        game, players = table2(lambda prompt, options: next(picks) if prompt.startswith(PROTECTION_PROMPT) else base(prompt, options))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.hand, a.battlefield = [GODS_WILLING], lands(1) + [bear]
        game._priority_round(a)
        self.assertEqual(next(o for p, o in players[0].prompts if p.startswith(PROTECTION_PROMPT)),
                         ["white", "blue", "black", "red", "green"])
        self.assertTrue(game.protected_from(bear, source_qualities(BOLT)))
        self.assertFalse(game.protected_from(bear, source_qualities(GREEN_BEAR)))

    def test_it_ends_with_the_turn(self):
        game, _ = table2(lambda prompt, options: 3 if prompt.startswith(PROTECTION_PROMPT) else 0)
        bear = Permanent(BEAR)
        game.seats[0].battlefield = [bear]
        game.resolving_item = None
        game.grant_protection_of_choice(bear, game.seats[0])
        self.assertTrue(game.protected_from(bear, source_qualities(BOLT)))
        bear.until_end_of_turn = []
        self.assertFalse(game.protected_from(bear, source_qualities(BOLT)))

    def test_mother_of_runes_protects_a_creature_you_control(self):
        base = lambda prompt, options: (next((i for i, o in enumerate(options) if o.startswith(ACTIVATE)), options.index(PASS))
                                        if prompt.startswith("Priority") else 3 if prompt.startswith(PROTECTION_PROMPT) else 0)
        game, _ = table2(base)
        a = game.seats[0]
        mother, bear = Permanent(MOTHER), Permanent(BEAR)
        a.battlefield = [mother, bear]
        mother.sick = False
        game._priority_round(a)
        self.assertEqual(mother.tapped, True)
        self.assertTrue(game.protected_from(mother, source_qualities(BOLT)))  # the first creature it could target

    def test_a_creature_can_protect_itself(self):
        [ability] = activated_abilities(SELF_SHIELD)
        self.assertEqual(ability.effects, (GrantProtection(on_source=True),))


class WardCostTests(unittest.TestCase):
    def cast(self, ward_card, answer, life=40, hand=(), mana=1):
        game, players = table2(pick(CAST, "Blood", "Hand", "Combo", answer))
        a = game.seats[0]
        a.hand, a.battlefield, a.life = [BOLT, *hand], lands(mana), life
        warded = Permanent(ward_card)
        game.seats[1].battlefield = [warded]
        game._priority_round(a)
        return game, players, warded

    def test_parse(self):
        self.assertEqual((ward_cost(LIFE_WARD), ward_cost(DISCARD_WARD), ward_cost(COMBO_WARD)),
                         ("Pay 3 life", "Discard a card", "{1}, Pay 2 life"))

    def test_paying_life(self):
        game, players, warded = self.cast(LIFE_WARD, "Pay")
        self.assertEqual((game.seats[0].life, game.seats[1].battlefield), (37, []))
        self.assertEqual(next(o for p, o in players[0].prompts if p.startswith(WARD_PROMPT)), ["Pay 3 life", "Don't pay"])

    def test_declining_counters_the_spell(self):
        game, players, warded = self.cast(LIFE_WARD, "Don't")
        self.assertEqual((game.seats[0].life, warded.damage, game.seats[0].graveyard), (40, 0, [BOLT]))

    def test_without_the_life_it_is_countered_unasked(self):
        game, players, warded = self.cast(LIFE_WARD, "Pay", life=2)
        self.assertEqual((warded.damage, game.seats[0].graveyard), (0, [BOLT]))
        self.assertFalse(any(p.startswith(WARD_PROMPT) for p, _ in players[0].prompts))

    def test_discarding(self):
        game, _, warded = self.cast(DISCARD_WARD, "Pay", hand=[BEAR])
        self.assertEqual(([c.name for c in game.seats[0].graveyard], game.seats[1].battlefield),
                         (["Bear", "Lightning Bolt"], []))  # the discard, then the Bolt after it resolved
        self.assertEqual(game.seats[0].hand, [])

    def test_nothing_to_discard(self):
        game, players, warded = self.cast(DISCARD_WARD, "Pay")
        self.assertEqual((warded.damage, game.seats[0].graveyard), (0, [BOLT]))
        self.assertFalse(any(p.startswith(WARD_PROMPT) for p, _ in players[0].prompts))

    def test_mana_and_life_together(self):
        game, _, warded = self.cast(COMBO_WARD, "Pay", mana=2)
        self.assertEqual((game.seats[0].life, game.seats[1].battlefield, all(p.tapped for p in game.seats[0].battlefield)),
                         (38, [], True))
        game, players, warded = self.cast(COMBO_WARD, "Pay", mana=1)  # no mana left for the {1}
        self.assertEqual((warded.damage, game.seats[0].life), (0, 40))

    def test_ward_given_by_a_static_ability(self):
        game, players = table2(pick(CAST, "Plain Bear", "Pay"))
        a = game.seats[0]
        a.hand, a.battlefield = [BOLT], lands(3)
        lord, ally = Permanent(LORD), Permanent(PLAIN)
        game.seats[1].battlefield = [lord, ally]
        self.assertEqual((game.ward_of(lord), game.ward_of(ally)), (None, "{1}"))
        game._priority_round(a)
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Warding Lord"])  # paid {1}; the Bolt killed it
        self.assertTrue(any(p.startswith(WARD_PROMPT) for p, _ in players[0].prompts))
