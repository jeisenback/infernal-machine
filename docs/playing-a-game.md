# Playing a game

How a game is run, and what ends one that cannot finish.

## Playing a game

```python
from infernal_machine.game import Game

game = Game([(player_a, deck_a), (player_b, deck_b), (player_c, deck_c)], seed=42)
winner = game.play()
```

- **Setup:** 40 life, commanders in the command zone, shuffle, and a random starting player.
- **Mulligans:** London mulligan. The first one is free in games with 3 or more players (CR 103.5c).
- **Turns:** all twelve steps. Priority goes around the table, and a step ends only when every
  player passes in a row. There's no priority in untap or cleanup.
- **Draw:** the first player skips their first draw only in a two-player game (CR 103.8a).
- **Cleanup:** discard down to seven cards.
- **Losing:** a player loses at 0 life or when drawing from an empty library.
  The last player standing wins.
- **Actions so far:** play a land (one per turn, your main phase, empty stack), cast spells, and pass.
- **Casting:** permanents, sorceries and your commander at sorcery speed.
  Instants and Flash cards whenever you have priority.
- **Paying mana:** mana is paid automatically from lands (using Scryfall's `produced_mana`) and from
  permanents with a simple tap ability: `{T}: Add {C}{C}.`, `{T}: Add {G}.`, `{T}: Add {R} or {G}.`,
  and "one mana of any color" (optionally limited to your commander's colors).
  Creatures can't tap for mana the turn they arrive.
  - Phyrexian symbols ({B/P}) are paid with mana when possible, otherwise with 2 life each, but never down to 0 life.
  - Twobrid symbols ({2/W}) are paid with one mana of that color if possible, otherwise with two mana of any kind.
  - {S} (snow) is paid by mana from a snow permanent ("Snow-Covered Forest"), which still makes its normal color.
  Signet-style abilities ("{1}, {T}: Add {W}{U}.") are used when plain sources aren't enough. One Signet can pay
  another's {1} (but never its own). A Signet's cost is paid with the first mana that fits, so a chain of Signets
  can occasionally miss a payment that a different choice would have found.
  Lands with "{T}, Pay 1 life: Add {G} or {W}." (Horizon lands) pay life for each tap, like Mana Confluence, and are
  not used at 1 life or less.
  Their own cost is always paid by a plain source.
- **Mana pool and rituals:** "Add {B}{B}{B}." as a spell (Dark Ritual) puts mana in the caster's pool. Pool mana is
  spent first on whatever they cast or activate next, and the pool empties at the end of every step. Clients see it
  as `mana_pool` in the board state. Bots don't cast cards that only add mana, since they don't plan ahead.
- **X in abilities:** "{X}, {T}: Draw X cards." asks for X when you activate, from 0 up to what you can afford,
  the same way spells do.
- **X spells:** the caster chooses X when casting, from 0 up to what they can afford.
  X works in effects ("draw X cards", "deals X damage", "create X tokens", "put X counters")
  and in "enters with X +1/+1 counters".
- **Other costs:**
  - Cost reducers: "Green spells you cast cost {1} less to cast." (Medallions), for a color, "creature",
    "artifact", "enchantment", "noncreature", "instant and sorcery", or all spells. Only generic mana is
    reduced, including commander tax and kicker.
  - Evoke and Overload are alternative costs paid in mana, offered when you cast ("Evoke {2}{U}", "Overload {6}{U}").
    An evoked creature is sacrificed once it enters, after its own "when it enters" abilities have resolved
    (Mulldrifter draws its two cards first). An overloaded spell reads every "target" as "each" and has no targets
    (Cyclonic Rift returns every nonland permanent you don't control; Vandalblast destroys every artifact you don't
    control). Overload is only offered when the "each" version is understood; otherwise the line is reported.
  - A spell can reduce its own cost: "This spell costs {1} less to cast for each creature on the battlefield."
    (Blasphemous Act, any player's creatures) or "... for each instant and sorcery card in your graveyard".
  - Alternative costs: "If you control a commander, you may cast this spell without paying its mana cost."
    (Fierce Guardianship, Deadly Rollick) and "(If it's not your turn,) you may (pay N life and) exile a blue card
    from your hand rather than pay this spell's mana cost." (Force of Will, Force of Negation). When more than
    one way is payable, the caster chooses. X is 0 when the mana cost isn't paid.
  - Flashback {N}: you may cast the card from your graveyard for that cost (at the usual timing: an instant at any
    time, anything else at sorcery speed). Whenever it leaves the stack, whether it resolves, fizzles or is
    countered, it is exiled instead of going to the graveyard. Bots use graveyard casts like any other cast.
  - Escape—{N}, Exile N other cards from your graveyard: you cast it from the graveyard for that cost and exile the
    other cards you choose, which counts as cards leaving your graveyard. It isn't exiled afterwards, so an escaped
    creature stays. Only one graveyard-casting ability per card is used (the first on the card). Kicker and
    commander tax don't apply to a graveyard cast.
  - Retrace (Throes of Chaos): cast it from the graveyard for its mana cost and a land card discarded from your hand;
    it goes back to the graveyard afterwards, so it can be cast again.
  - Demonstrate (Replication Technique, Creative Technique): when you cast the spell you may copy it, and if you do you
    choose an opponent who also copies it. Each copy's controller chooses new targets.
  - Backup N (Guardian Scalelord): when it enters, put N +1/+1 counters on a target creature; if that is another
    creature, it gains the abilities written below the Backup line until end of turn.
  - Encore {N} (Angel of Indemnity): at sorcery speed, pay it and exile the card from your graveyard; each opponent gets
    a token copy with haste that attacks that opponent this turn if able and is sacrificed at the next end step.
  - Madness {N} (Obsessive Search): a card with it that is discarded (by an effect, to hand size, or as a cost) goes to exile
    instead of the graveyard, and its owner may cast it for the madness cost, if that can be paid and it has a legal target;
    if it isn't cast it goes to the graveyard. The choice is made at once, not from a trigger on the stack, and discard
    triggers still happen. Cycling a card, or a card that discards itself from your hand, does not get madness.
  - Unearth {N} (Dregscape Zombie): at sorcery speed, pay it and the card comes back from your graveyard (it is not
    cast, so nothing triggers on a cast, but enters triggers happen). It has haste until end of turn and is exiled at the
    next end step, or instead of dying or going to a hand. Only a mana cost is read.
  - Bestow {N} (Eidolon of Countless Battles): an alternative cost, offered when you control a creature to enchant. It
    resolves as an Aura attached to that creature (as a creature if the target is gone), and becomes a creature again
    when the creature it enchants leaves.
  - Buyback {N} (Capsize): asked, when it can be paid, before choosing targets; the mana is added to the cost, and the
    spell returns to its owner's hand as it resolves. A spell that is countered or fizzles (every target gone) goes to the
    graveyard, and the cost stays paid. "Buyback\u2014Sacrifice a land." and "Buyback\u2014Pay N life." work the same way; the
    other forms (discard two cards, sacrifice three Islands, pay life and discard at random) and "Buyback costs cost {2}
    less" are not read.
  - Kicker {N}: the caster chooses whether to pay it, before choosing targets. "If this spell was kicked, ..."
    effects on instants and sorceries happen only when it was, and can target (kicker is only offered when those
    targets exist). A kicked permanent (Auras too) remembers it: "If this creature was kicked, it enters with
    N +1/+1 counters on it." and "When this creature enters, if it was kicked, ..." (Untamed Kavu, Josu Vess).
  - Multikicker {N}: the caster chooses how many times to pay it, and "... enters with a +1/+1 counter on it for
    each time it was kicked." counts them (Gnarlid Pack).
  - Kicked "instead" wordings change the effect just before them: "it deals N damage instead" (Burst Lightning),
    "create N of those tokens instead" (Saproling Migration) and "draw N cards instead".
  - Strive {cost} (Twinflame): "This spell costs {2}{R} more to cast for each target beyond the first." With "any
    number of target creatures you control" you are offered only as many targets as the mana can pay for, and the extra
    cost is added once they are chosen.
  - Kicker costs that aren't mana: "Kicker—Sacrifice a land / a creature / ...", "Kicker—Discard a card." and
    "Kicker—Pay N life." are paid like additional costs, and only offered when they can be paid.
  - Bargain (sacrifice an artifact, enchantment, or token as you cast the spell, CR 702.166): paid like a kicker that is not mana, and "if this spell was bargained" / "if it was bargained" read as the kicker conditions. "If this spell was kicked, that creature gets -5/-5 until end of turn instead." (and "destroy that creature instead", "exile target nonland permanent instead") replaces the effect before it, "that creature" being the target of that effect, and "it fights up to one target creature you don't control" is the source creature fighting. "Add four mana in any combination of colors" gives each mana its own color. Candy Grapple, Kellan's Lightblades, Archon's Glory, High Fae Negotiator, Tenacious Tomeseeker, Troublemaker Ouphe, Realm-Scorcher Hellkite and Agatha's Champion work; the cost reduction of Ice Out, Johann's Stopgap and Hamlet Glutton (" costs {N} less if it's bargained"), Beseech the Mirror and the other long modes are not read.
  - Two kicker costs ("Kicker {R} and/or {W}"): each is offered separately, when it can be paid, and
    "if it was kicked with its {R} kicker" / "If this spell was kicked with its {1}{B} kicker, ..." check that
    specific cost (Thornscape Battlemage).
  - Eternalize {cost}: from the graveyard at sorcery speed, pay it and exile the card to create a token copy that is a
    4/4 black Zombie (plus the card's own creature types) with no mana cost (CR 702.129a). "Eternalize—{cost}, Discard a
    card." also discards a card as part of the cost, and is only offered when there is one in hand.
  - Offspring {N}: offered like a kicker as the creature spell is cast; if it was paid, a 1/1 token copy of the creature
    enters with it (CR 702.175a) and has the creature's own abilities. The token was not cast, so it does not make another
    token.
  - Additional costs: "As an additional cost to cast this spell, sacrifice a creature / an artifact / an artifact
    or creature / a land / a permanent", "discard a card" or "pay N life". They're paid after mana, so a creature
    that tapped for mana can still be sacrificed. Effects that read the paid cost ("the sacrificed creature's
    power") aren't supported.
    "Pay X life" (Toxic Deluge) is chosen as you cast: any amount that leaves you with at least 1 life, and the
    spell's X is that amount ("All creatures get -X/-X until end of turn"; also "Creatures you control get +X/+X" and
    "Creatures your opponents control get -X/-X"). The bot pays up to 3. "{X}, Sacrifice this enchantment: Destroy each
    artifact, creature, and enchantment with mana value X or less." (Pernicious Deed) takes its X from the activation.
- **Commander tax:** your commander costs {2} more for each earlier cast from the command zone.
  When your commander would go to the graveyard, you choose whether it goes back to the command zone instead.
- **The stack:** spells go on the stack and resolve last in, first out once everyone passes in a row.
- **Combat:** the active player chooses, creature by creature, whether to attack and whom: an opponent, or a
  planeswalker an opponent controls ("Attack Planeswalker: ..."). Damage to a planeswalker removes loyalty (it dies at
  0), and the player's creatures can block attackers aimed at their planeswalker. A trampler's extra damage goes to
  the planeswalker. If the planeswalker has left, the attacker deals no damage. Bots attack players only.
  "Whenever a creature attacks you" triggers only for attacks on the player; "... attacks you or a planeswalker you
  control" triggers for both. When several creatures block one attacker, its controller names which blocker gets
  lethal damage first, then the next, and so on (bots go for the weakest first); the rest goes to the last, or to the
  player with trample.
  Each defending player then chooses blockers, and damage is dealt all at once. With no attackers,
  the blockers and damage steps are skipped. If any creature in combat has first strike or double strike,
  there's an extra first-strike damage step.
  - Keywords: flying, reach, vigilance, haste, defender, menace, trample, first strike,
    double strike, deathtouch and lifelink.
  - A blocked attacker deals lethal damage to each blocker in the order they blocked. Any extra goes
    to the last blocker, or to the player with trample. It stays blocked even if its blockers leave.
  - Creatures can't attack planeswalkers yet.
- **Commander damage:** combat damage from each commander is tracked per player.
  21 from one commander makes that player lose.
- **State checks:** players lose at 0 life, when drawing from an empty library, or at 21 commander damage.
  Creatures die from lethal damage (unless indestructible) or 0 toughness,
  and planeswalkers die at 0 loyalty. Damage wears off in the cleanup step.

## Shortcuts

A player may name a loop and how many times to go round it (the Comprehensive Rules' shortcuts; opponents may respond to the proposal).
`infernal_machine/shortcut.py` is that: `take(game, seat, Shortcut(steps, answers), times)` takes the actions of one round, in order,
`times` times. Each step is a piece of an action's text (the first legal action that contains it is taken; "A until B" takes A again and
again until B is offered), the stack resolves after each (`Game.resolve_stack`), and the answers are what the player says to the
questions the actions raise ("wanted", or "about~wanted" for a question that contains "about"; a question none answers goes to the
player as usual). It stops when a step is not offered (and says which, in which round), when the game is over, or after `times` rounds.
Nothing in the game proposes one yet; `tools/combo_lines.py` is the one user, and a bot that follows a combo line would be the next.

What it does not do: make anything infinite. N rounds give N rounds' worth, and the payer spends the mana pool before it taps anything,
so a loop that makes one mana more than it pays leaves the pool where it was, not N mana richer. `take(..., keep_pool=True)` (`Game.pool_last`) has the payer spend the pool last, so the surplus of each round stays in it (a prototype for
`tools/combo_lines.py`; nothing else sets it). A round that grows the board meets the
board limit; one whose whole state comes back is drawn (`LoopDraw`). Opponents get no chance to respond inside it.

## Runaway boards

Nothing in the rules stops a token engine that copies itself (a copy of each creature every turn, or within one resolution), but each
step costs more as the board grows, so such a game never finishes. `Game(..., board_limit=300)` (`game.BOARD_LIMIT`; `None` for no
limit) ends a game as a draw when more than that many permanents are in play, all players together. The check is where a permanent
enters the battlefield, so a single effect that makes tokens without end stops at the limit instead of making them all. `Game.play`
catches `BoardLimitReached`, sets `game.ended` to `"board_limit"`, returns no winner (even if a player had just lost: the turn was cut
off mid-way), and the `game_over` event carries `"reason": "board_limit"`. A real game seldom has 100 permanents; the largest of 48
precon games was about 70, and a limit of 300 only ends a game that has gone wrong.

- **Matchups:** such a game is a draw in the W-L-D count and is also counted in `Record.board_limit`; the report says how many ended
  that way, so a runaway is not mistaken for a timeout or a crash.
- **`tools/bot_games.py`:** prints the seeds of games that ended at the limit and still exits 0, since a runaway board is a finding and not
  a crash; replay one with `--start SEED --games 1`.

A loop that does not grow the board is the other way a game can fail to finish. CR 104.4b: a loop of mandatory actions with no way to
stop is a draw (a loop with an optional action in it is not, and neither is one that ends when a player loses). In `Game._priority_round`,
after 1000 stack items have resolved with nobody doing anything but passing, the game state (every seat's zones, life, mana, the stack,
the pending triggers and the random generator) is compared from one resolution to the next; the first time one comes back exactly,
`LoopDraw` is raised, `Game.play` sets `game.ended` to `"loop"`, returns no winner, and the `game_over` event carries `"reason": "loop"`.
Any action a player takes resets the count. This is only the exact repeat: a loop that adds something each time (a token, a counter) is
not seen as one and meets the board limit instead. `tools/bot_games.py` prints the seeds of games drawn this way. A combo whose loop is
the player's own choice, like the ones `tools/combo_lines.py` plays, is never one of these: every round has an action in it.
