"""Issue #874: suspect (CR 701.60): a suspected creature has menace and "This creature can't block" until it leaves the battlefield, from
the cards' real Oracle text. Seven cards whose only gap it was are fully playable. Caught Red-Handed suspects the creature it takes;
Barbed Servitor and Person of Interest suspect themselves as they enter, Convenient Target the creature it enchants, Reasonable Doubt
its target, It Doesn't Add Up the creature it returns. Repeat Offender suspects itself, then gets a +1/+1 counter; Agrus Kos suspects a
creature, then exiles it; Eliminate the Impossible makes only opponents' creatures no longer suspected; Rubblebelt Braggart may suspect
itself as it attacks, and isn't asked once it is. Deadly Complication may target only a suspected creature you control, which then may
become no longer suspected; Agency Coroner draws two for a suspected creature, one for another; Presumed Dead's creature comes back
suspected when it dies. A suspected creature has menace and can't block; one that isn't, or that left
the battlefield and came back, can block and has no menace."""

import unittest

from infernal_machine.effects import CANT_BLOCK
from infernal_machine.game import ACTIVATE, CAST, SUSPECT_PROMPT, UNSUSPECT_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, attack_all, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Caught Red-Handed", "Barbed Servitor", "Person of Interest", "Convenient Target", "Incriminating Impetus", "It Doesn't Add Up",
         "Repeat Offender", "Agrus Kos, Spirit of Justice", "Eliminate the Impossible", "Rubblebelt Braggart", "Agency Coroner", "Presumed Dead"]
NEED_A_TARGET = ["Reasonable Doubt", "Deadly Complication"]  # (a spell to counter, a suspected creature: the smoke table has neither, so only read)

# The guards these tests are there to catch (python tools/mutate.py tests.test_suspect).
MUTATIONS = [
    ("infernal_machine/game.py", '        if state == "suspected":  # Deadly Complication: "target suspected creature you control"\n            return permanent.suspected',
     '        if state == "suspected":  # Deadly Complication: "target suspected creature you control"\n            return True', "only a suspected creature is a target"),
    ("infernal_machine/game.py", "        if seat.player.choose(UNSUSPECT_PROMPT(creature.card.name), YES_NO) == 0:\n            creature.suspected = False",
     "        if seat.player.choose(UNSUSPECT_PROMPT(creature.card.name), YES_NO) == 0:\n            pass", "it can become no longer suspected"),
    ("infernal_machine/game.py", "        self.cost_sacrificed_suspected = any(p.suspected for p in chosen)", "        self.cost_sacrificed_suspected = False",
     "the sacrificed creature was suspected"),
    ("infernal_machine/game.py", "        if suspect:  # Presumed Dead: \"... and suspect it.\"\n            self.suspect(returned)",
     "        if suspect:  # Presumed Dead: \"... and suspect it.\"\n            pass", "it comes back suspected"),
    ("infernal_machine/effects/families/combat_and_pump.py", "            if target.suspected:\n                game.put_counters(", "            if False:\n                game.put_counters(",
     "a suspected Repeat Offender gets a counter"),
    ("infernal_machine/effects/families/combat_and_pump.py", "            if target.suspected:\n                game.exile(target)", "            if False:\n                game.exile(target)",
     "Agrus Kos exiles a suspected creature"),
    ("infernal_machine/effects/families/combat_and_pump.py", "        for seat in game.opponents(controller):\n            for permanent in seat.battlefield:\n                permanent.suspected = False",
     "        for seat in game.seats:\n            for permanent in seat.battlefield:\n                permanent.suspected = False", "only the opponents' creatures"),
    ("infernal_machine/effects/triggers.py", 'return [MaySuspectSelf()], False, False, Condition("source_not_suspected")',
     "return [MaySuspectSelf()], False, False, None", "it doesn't trigger once it is suspected"),
    ("infernal_machine/game.py", 'or (permanent.suspected and keyword in ("menace", CANT_BLOCK))', 'or (permanent.suspected and keyword in ("menace",))',
     "it can't block"),
    ("infernal_machine/game.py", 'or (permanent.suspected and keyword in ("menace", CANT_BLOCK))', 'or (permanent.suspected and keyword in (CANT_BLOCK,))',
     "it has menace"),
    ("infernal_machine/effects/outcomes.py", "        effects[0] = replace(effects[0], binds=SOURCE)  # \"When this creature enters, suspect it.\"",
     "        pass  # \"When this creature enters, suspect it.\"", "an enters trigger's \"it\" is the creature itself"),
    ("infernal_machine/game.py", "for p in reversed(s.battlefield) if p.card is creature.card", "for p in s.battlefield if p.card is creature.card",
     "the copy that was returned"),
    ("infernal_machine/game.py", "        if isinstance(creature, GraveyardTarget):\n            found = next(", "        if False:\n            found = next(",
     "a returned card is the permanent it became"),
]


def suspected(game, permanent):
    return permanent.suspected, game.has_keyword(permanent, "menace"), game.has_keyword(permanent, CANT_BLOCK)


def cast(name, mana, policy_targets=(), theirs=(), graveyard=()):
    """Seat 0, with `mana` lands, casts `name`; seat 1 has `theirs`; seat 0's graveyard is `graveyard`."""
    game, players = table3()
    a, b, _ = game.seats
    a.battlefield, a.hand, a.graveyard = lands(mana), [REAL[name]], list(graveyard)
    b.battlefield = [Permanent(c, sick=False) for c in theirs]
    players[0].policy = choose(game, *(b.battlefield + list(policy_targets)))
    game._perform(a, CAST + name)
    run_stack(game)
    return game, a, b


class SuspectTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        for name in NEED_A_TARGET:
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_the_creature_it_takes_is_suspected(self):
        game, a, _ = cast("Caught Red-Handed", 5, theirs=[OGRE])
        (ogre,) = [p for p in a.battlefield if p.card is OGRE]
        self.assertEqual(suspected(game, ogre), (True, True, True))

    def test_it_suspects_itself_as_it_enters(self):
        game, a, _ = cast("Barbed Servitor", 4)
        (servitor,) = [p for p in a.battlefield if p.card.name == "Barbed Servitor"]
        self.assertEqual(suspected(game, servitor), (True, True, True))

    def test_the_aura_suspects_the_creature_it_enchants(self):
        game, players = table3()
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = lands(3) + [bear], [REAL["Convenient Target"]]
        players[0].policy = choose(game, bear)
        game._perform(a, CAST + "Convenient Target")
        run_stack(game)
        self.assertEqual(suspected(game, bear), (True, True, True))

    def test_the_creature_it_returns_is_suspected(self):
        game, a, _ = cast("It Doesn't Add Up", 5, graveyard=[OGRE])
        (ogre,) = [p for p in a.battlefield if p.card is OGRE]
        self.assertEqual(suspected(game, ogre), (True, True, True))

    def test_the_returned_copy_is_suspected_not_another_copy(self):
        game, players = table3()
        a = game.seats[0]
        older = Permanent(OGRE, sick=False)  # (another copy of the same card already on the battlefield)
        a.battlefield, a.hand, a.graveyard = lands(5) + [older], [REAL["It Doesn't Add Up"]], [OGRE]
        game._perform(a, CAST + "It Doesn't Add Up")
        run_stack(game)
        (returned,) = [p for p in a.battlefield if p.card is OGRE and p is not older]
        self.assertEqual((returned.suspected, older.suspected), (True, False))

    def test_not_a_creature_never_suspected_nor_one_that_came_back(self):
        game, a, _ = cast("Barbed Servitor", 4)
        (servitor,) = [p for p in a.battlefield if p.card.name == "Barbed Servitor"]
        bear = Permanent(BEAR, sick=False)
        a.battlefield.append(bear)
        self.assertEqual(suspected(game, bear), (False, False, False))
        game.return_to_hand(servitor)
        back = Permanent(servitor.card)
        game._enter(a, back)  # (a new object: it isn't suspected until its trigger resolves)
        self.assertEqual(back.suspected, False)


    def test_repeat_offender_suspects_itself_then_grows(self):
        game, _ = table3()
        a = game.seats[0]
        offender = Permanent(REAL["Repeat Offender"], sick=False)
        a.battlefield = lands(6) + [offender]
        for _ in range(2):
            (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Repeat Offender" in x]
            game._perform(a, action)
            run_stack(game)
        self.assertEqual((offender.suspected, offender.counters.get("+1/+1")), (True, 1))  # (suspected first, then a counter)

    def test_agrus_kos_suspects_then_exiles(self):
        game, players = table3()
        a, b, _ = game.seats
        ogre = Permanent(OGRE, sick=False)
        b.battlefield = [ogre]
        players[0].policy = choose(game, ogre)
        for _ in range(2):  # (it enters twice: the first suspects the Ogre, the second exiles it)
            game._enter(a, Permanent(REAL["Agrus Kos, Spirit of Justice"]))
            run_stack(game)
            if _ == 0:
                self.assertEqual((ogre.suspected, ogre in b.battlefield), (True, True))
        self.assertEqual(ogre in b.battlefield, False)

    def test_eliminate_the_impossible_unsuspects_only_opponents_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine, theirs = Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)
        mine.suspected = theirs.suspected = True
        a.battlefield, a.hand, b.battlefield = lands(3) + [mine], [REAL["Eliminate the Impossible"]], [theirs]
        game._perform(a, CAST + "Eliminate the Impossible")
        run_stack(game)
        self.assertEqual((mine.suspected, theirs.suspected, game.power(theirs)), (True, False, 1))

    def test_rubblebelt_braggart_may_suspect_itself_as_it_attacks(self):
        game, players = table3(attack_all)
        a = game.seats[0]
        braggart = Permanent(REAL["Rubblebelt Braggart"], sick=False)
        a.battlefield = [braggart]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual((braggart.suspected, len([p for p, _ in players[0].prompts if SUSPECT_PROMPT.matches(p)])), (True, 1))
        game, players = table3(attack_all)
        a = game.seats[0]
        braggart = Permanent(REAL["Rubblebelt Braggart"], sick=False)
        braggart.suspected = True  # (already suspected: it doesn't trigger, CR 603.4, so nothing is asked)
        a.battlefield = [braggart]
        game.combat.declare_attackers(a)
        self.assertEqual([t for t in game.pending if t.permanent is braggart], [])
        run_stack(game)
        self.assertEqual([p for p, _ in players[0].prompts if SUSPECT_PROMPT.matches(p)], [])


    def test_suspected_before_its_trigger_resolves_it_isnt_asked(self):
        game, players = table3(attack_all)
        a = game.seats[0]
        braggart = Permanent(REAL["Rubblebelt Braggart"], sick=False)
        a.battlefield = [braggart]
        game.combat.declare_attackers(a)
        braggart.suspected = True  # (between the trigger and its resolution: the "if" is checked again, CR 603.4)
        run_stack(game)
        self.assertEqual([p for p, _ in players[0].prompts if SUSPECT_PROMPT.matches(p)], [])


    def test_deadly_complication_counters_a_suspected_creature_that_may_become_unsuspected(self):
        game, players = table3()
        a = game.seats[0]
        suspect, other = Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)
        suspect.suspected = True
        a.battlefield, a.hand = lands(4) + [suspect, other], [REAL["Deadly Complication"]]
        self.assertEqual([o for _, o in game.target_options("suspected creature you control", a)], [suspect])  # (not the Ogre)
        aim = choose(game, suspect)
        players[0].policy = lambda prompt, options: (next(i for i, o in enumerate(options) if o.startswith(("Put", "Done"))) if "mode" in prompt
                                                     else 0 if UNSUSPECT_PROMPT.matches(prompt) else aim(prompt, options))
        game._perform(a, CAST + "Deadly Complication")
        run_stack(game)
        self.assertEqual((suspect.counters.get("+1/+1"), suspect.suspected), (1, False))

    def test_agency_coroner_draws_two_for_a_suspected_creature(self):
        for suspected_one, drawn in ((True, 2), (False, 1)):
            game, players = table3()
            a = game.seats[0]
            coroner, bear = Permanent(REAL["Agency Coroner"], sick=False), Permanent(BEAR, sick=False)
            bear.suspected = suspected_one
            a.battlefield, a.hand, a.library = lands(3) + [coroner, bear], [], [OGRE, OGRE, OGRE]
            (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Agency Coroner" in x]
            game._perform(a, action)
            run_stack(game)
            self.assertEqual(len(a.hand), drawn, suspected_one)

    def test_presumed_dead_returns_the_creature_suspected(self):
        game, players = table3()
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = lands(2) + [bear], [REAL["Presumed Dead"]]
        players[0].policy = choose(game, bear)
        game._perform(a, CAST + "Presumed Dead")
        run_stack(game)
        self.assertEqual(game.power(bear), 4)
        game.destroy(bear)
        run_stack(game)
        (back,) = [p for p in a.battlefield if p.card is BEAR]
        self.assertEqual((back is not bear, back.suspected, back.tapped), (True, True, False))

    def test_without_presumed_dead_it_stays_dead(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield = [bear]
        game.destroy(bear)
        run_stack(game)
        self.assertEqual([p for p in a.battlefield if p.card is BEAR], [])


if __name__ == "__main__":
    unittest.main()
