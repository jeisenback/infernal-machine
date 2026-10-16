# Bots

The computer player, its judgments, and how a bot version is compared with another.

## Bots and goldfishing

```python
from infernal_machine.bot import BotPlayer, goldfish

game = Game([(BotPlayer("Bot", deck), deck), (tcp_player, other_deck)])
stats = goldfish(deck, games=5000, turns=5)
# GoldfishStats(mulligan_rate=0.188, average_opening_lands=3.01,
#               land_drop_rate={1: 1.0, 2: 0.998, 3: 0.918, 4: 0.772, 5: 0.596})
```

- **`BotPlayer`:** keeps hands with 2-5 lands, and keeps anything after two mulligans.
  It chooses the largest X it can afford, sacrifices its weakest creature, and tutors for its most expensive card.
  It pays life for shocklands only while above 10 life. It equips Equipment once (not repeatedly), puts helpful
  Auras on its own creatures, and Pacifism-style ones on opponents'.
  It watches the board (the snapshot TCP players get) for a few judgments:
  - Scry and surveil: it keeps a land on top until it has 6 lands (in play and in hand), and a spell it can cast
    within a turn; the rest go to the bottom (or the graveyard).
  - Modes: it picks the mode that does the most (removal, then cards, tokens, buffs and life), and stops choosing
    when only modes that cost it (life, discards, sacrifices) are left.
  - Wipes: it casts one that hits everyone's creatures only when opponents have more creatures than it does.
    One-sided wipes are always fine.
  - Cycling: it cycles lands once it has 6, and spells that cost more than 2 above what it has.
  - Ward: it always pays, since the spell is already paid for and it's only asked when it can afford the cost.
  It plays a land whenever it can, then casts its commander if it can,
  then its most expensive affordable spell, then cycles, and otherwise passes.
  After casting, it activates abilities that tap, sacrifice, or use loyalty.
  It targets opponents' things when it can, never responds to its own spell,
  and always returns its commander to the command zone. In combat it attacks the opponent
  with the lowest life with every creature that has power. It blocks when its blocker survives,
  and chump-blocks the biggest attacker once it's at 10 life or less. When bottoming or discarding,
  it drops a land if over half the hand is lands, otherwise its most expensive spell.
- **Judgments (`features`):** `BotPlayer(name, deck, features=...)` turns these on, all by default; `features=frozenset()` is
  the plain bot, kept to measure changes against.
  - `timing`: abilities that tap or sacrifice their source wait for the second main phase (before, the bot tapped a land at
    upkeep for a useless ability and then couldn't cast anything). Equip, crew and loyalty abilities still go in either main phase.
  - `attack`: a creature stays home if a blocker could kill it and survive, unless the attack is lethal or the creature can't
    be blocked (flying, "can't be blocked"), and everything stays home when the opponents' board could be lethal next turn.
  - `land`: plays the land that adds a color the hand needs and the lands in play lack, an untapped one on a tie.
  - `target`: removal (destroy, exile, damage, bounce, steal) goes on the biggest opposing creature, not the first listed.
  - `mana`: of the spells it can cast, it picks the one in the combination that spends the most of its untapped mana.
  - `commander`: the commander is cast first only while its tax is 2 or less (after that it competes with the other spells for the
    mana); a commander that attacks goes at the player whose commander damage from it this attack would bring to 21; and it blocks
    an opposing commander whose hit would bring the damage it has taken from that commander to 21 or more. In 146 four-player pods
    (`compare_bots.py --pod 4`) it won 25.3% (19.0%-33.0%) against opponents without it, where a fair share is 25%: no measurable
    difference, so these are rule-following choices, not a proven gain.
  - `threat`: in a pod it attacks an opponent its ready creatures can kill (the lowest life among them), and otherwise the one that looks
    most dangerous: the most creature power on the board, then nonland permanents and cards in hand, with the lower life breaking a
    tie. The plain bot attacks the lowest life. In 160 four-player pods (`compare_bots.py --pod 4`) it won 26.9% (20.6%-34.2%) against
    the same bot without it, where a fair share is 25%: no measurable difference either way.
  - `destination`: when its commander would be put into a graveyard, exile, hand or library, it goes to the hand if it would be bounced
    and has any tax on it (cast from the hand it pays none), to the graveyard if it has six or more tax and the deck has a card that
    brings creatures back from a graveyard, and to the command zone otherwise. It counts the tax from its commander's casts from the
    command zone. These events are rare, so no pod comparison could show an effect; the unit tests are the evidence.
  `python tools/compare_bots.py DECK DECK ...` plays one version of the bot against another on the same decks and reports the
  win rate with its 95% interval. Against the plain bot on the five Secrets of Strixhaven precons (191 games) all five
  together won 67.5% (60.6%-73.8%); alone, timing won 65.5%, attack 57.6%, land 56.8%, target 55.2% and mana 52.9%.
  A weekly CI job (`bot strength`) repeats this against the plain bot and fails if the whole interval drops below 50%.
- **`goldfish`:** plays the deck alone many times with the same mulligan rules and one land a turn.
  It reports how often you mulligan, how many lands the kept hand has, and how often
  you've made every land drop through each turn. The example above is a 38-land deck.
