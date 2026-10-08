# Infernal Machine

A Magic: The Gathering engine, starting with the Commander format.
Python 3.11+, standard library only.

## Quick start: play a game

You can try a full game offline, with no Scryfall, using the demo cards in `examples/`:

```
# terminal 1: a table for one human and two bots
python -m infernal_machine.server --humans 1 --bots 2 --bot-deck examples/red_deck.txt \
    --cache examples/demo_cards.json --no-check

# terminal 2: join it
python -m infernal_machine.client --name Alice --deck examples/green_deck.txt
```

For real decks, leave out `--cache examples/demo_cards.json` and `--no-check`. The server then fetches cards
from Scryfall (and saves them in `.cache/cards.json`) and only seats decks that are legal Commander decks.
See [Playing over TCP](#playing-over-tcp) for all the options.

## Pulling cards

```python
from infernal_machine.cards import CachedSource, ScryfallSource, load_deck

source = CachedSource(ScryfallSource(), ".cache/cards.json")
bolt = source.get("Lightning Bolt")
deck = load_deck(open("deck.txt").read(), source)  # deck.commanders, deck.main, deck.sideboard
```

- `ScryfallSource` calls the [Scryfall API](https://scryfall.com/docs/api). Single
  lookups use `/cards/named`, and decklists use `/cards/collection` in batches of 75.
  It sends the required headers and spaces requests 100 ms apart.
- `CachedSource` wraps any source and stores the cards it fetches in a JSON file,
  so repeat lookups work offline.
- `parse_decklist` reads Arena/MTGO/Moxfield text: `Commander` / `Deck` / `Sideboard`
  headers, `1 Sol Ring (CMM) 400`, and Moxfield's `*CMDR*` and `*F*` tags.

## Commander deck rules

```python
from infernal_machine.commander import deck_problems

for problem in deck_problems(deck):
    print(problem)
```

`deck_problems` returns every rule a deck breaks. An empty list means the deck is legal. It checks:

- The deck has exactly 100 cards, counting the commanders.
- The commander is a legendary creature or says it "can be your commander".
- Two commanders are allowed when they pair: Partner, Partner with, Partner—X,
  Friends forever, Choose a Background, or Doctor's companion.
- Singleton, except basic lands and cards that allow more copies (Relentless Rats, Seven Dwarves).
- Every card fits within the commanders' combined color identity.
- Banned cards are flagged, using Scryfall's Commander legality.

## Deck stats

```python
from infernal_machine.analysis import analyze

stats = analyze(deck.commanders + deck.main)
stats.land_count, stats.average_mana_value, stats.curve, stats.color_pips
```

- `curve` counts nonland cards by mana value, with 7+ in one bucket.
- `average_mana_value` also leaves out lands.
- `color_pips` counts colored mana symbols across all costs. Hybrid symbols count toward both colors.

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
- **Draw:** the first player skips their first draw only in a two-player game (CR 103.8).
- **Cleanup:** discard down to seven cards.
- **Losing:** a player loses at 0 life or when drawing from an empty library.
  The last player standing wins.
- **Actions so far:** play a land (one per turn, your main phase, empty stack), cast spells, and pass.
- **Casting:** permanents, sorceries and your commander at sorcery speed.
  Instants and Flash cards whenever you have priority.
- **Paying mana:** mana is paid automatically from lands (using Scryfall's `produced_mana`) and from
  permanents with a simple tap ability: `{T}: Add {C}{C}.`, `{T}: Add {G}.`, `{T}: Add {R} or {G}.`,
  and "one mana of any color" (optionally limited to your commander's colors).
  Creatures can't tap for mana the turn they arrive. Phyrexian symbols are paid with mana.
  Signet-style abilities ("{1}, {T}: Add {W}{U}.") are used when plain sources aren't enough.
  Their own cost is always paid by a plain source.
- **X spells:** the caster chooses X when casting, from 0 up to what they can afford.
  X works in effects ("draw X cards", "deals X damage", "create X tokens", "put X counters")
  and in "enters with X +1/+1 counters".
- **Other costs:**
  - Cost reducers: "Green spells you cast cost {1} less to cast." (Medallions), for a color, "creature",
    "artifact", "enchantment", "noncreature", "instant and sorcery", or all spells. Only generic mana is
    reduced, including commander tax and kicker.
  - Alternative costs: "If you control a commander, you may cast this spell without paying its mana cost."
    (Fierce Guardianship, Deadly Rollick) and "(If it's not your turn,) you may (pay N life and) exile a blue card
    from your hand rather than pay this spell's mana cost." (Force of Will, Force of Negation). When more than
    one way is payable, the caster chooses. X is 0 when the mana cost isn't paid.
  - Kicker {N}: the caster chooses whether to pay it, before choosing targets. "If this spell was kicked, ..."
    effects on instants and sorceries happen only when it was, and can target (kicker is only offered when those
    targets exist). A kicked permanent (Auras too) remembers it: "If this creature was kicked, it enters with
    N +1/+1 counters on it." and "When this creature enters, if it was kicked, ..." (Untamed Kavu, Josu Vess).
  - Multikicker {N}: the caster chooses how many times to pay it, and "... enters with a +1/+1 counter on it for
    each time it was kicked." counts them (Gnarlid Pack).
  - Kicked "instead" wordings change the effect just before them: "it deals N damage instead" (Burst Lightning),
    "create N of those tokens instead" (Saproling Migration) and "draw N cards instead".
  - Kicker costs that aren't mana: "Kicker—Sacrifice a land / a creature / ...", "Kicker—Discard a card." and
    "Kicker—Pay N life." are paid like additional costs, and only offered when they can be paid. Two kicker costs
    on one card ("Kicker {1}{B} and/or {1}{R}") aren't supported.
  - Additional costs: "As an additional cost to cast this spell, sacrifice a creature / an artifact / an artifact
    or creature / a land / a permanent", "discard a card" or "pay N life". They're paid after mana, so a creature
    that tapped for mana can still be sacrificed. Effects that read the paid cost ("the sacrificed creature's
    power") aren't supported.
- **Commander tax:** your commander costs {2} more for each earlier cast from the command zone.
  When your commander would go to the graveyard, you choose whether it goes back to the command zone instead.
- **The stack:** spells go on the stack and resolve last in, first out once everyone passes in a row.
- **Combat:** the active player chooses, creature by creature, whether to attack and which opponent.
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

## Card effects

`effects.py` reads an instant's or sorcery's rules text one sentence at a time. It understands:

| Rules text | Example |
|---|---|
| Draw N cards. | Divination |
| You gain N life. / Each opponent loses N life. | |
| (This spell) deals N damage to any target / target creature / target player / ... | Lightning Bolt |
| Destroy target creature / artifact / enchantment / nonland permanent / ... | Murder |
| Counter target (noncreature / creature / instant or sorcery / artifact / enchantment) spell. | Counterspell, Negate |
| Exile target creature / artifact / nonland permanent / ... | |
| Exile target creature. Its controller gains life equal to its power. | Swords to Plowshares |
| Exile target creature. Its controller may search their library for a basic land card, ... | Path to Exile |
| Exile target player's graveyard. | Tormod's Crypt |
| Exile (another) target nonland permanent ... until this enchantment leaves the battlefield. | Banishing Light |
| Exile another target ...; When this leaves the battlefield, return the exiled card to the battlefield under its owner's control. | Oblivion Ring, Fiend Hunter |
| Choose one / two / three / one or both / one or more — • mode • mode ... | charms and commands |
| Target player (or opponent) draws N cards / gains N life / loses N life. | |
| Exile target card from a graveyard. | |
| Return target permanent to its owner's hand. Return all creatures to their owners' hands. | Cyclonic Rift, Evacuation |
| Return target (creature) card from your graveyard to your hand / to the battlefield. | Raise Dead, Zombify |
| Put target creature card from a graveyard onto the battlefield under your control. | Reanimate |
| Search your library for a (creature) card, (reveal it,) put it into your hand, then shuffle. | Demonic Tutor |
| Search your library for a card, then shuffle and put that card on top. | Vampiric Tutor |
| You lose N life. | |
| Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle. | Cultivate, Kodama's Reach |
| Search your library for a (Plains, Island, ...) card, put it onto the battlefield (tapped), then shuffle. | Farseek, Nature's Lore |
| Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle. | Explosive Vegetation |
| Scry N. / Surveil N. | |
| Mill N cards. / Target player (or opponent) mills N cards. / Each opponent (or player) mills N cards. | |
| Equip {N} (Equipment) | Swiftfoot Boots, Lightning Greaves |
| Equipped creature gets +N/+N and has keywords. / Enchanted creature gets +N/+N and has keywords. | |
| Enchant creature / land / ... (Auras) | |
| Enchanted creature can't attack or block. | Pacifism |
| Destroy all creatures / artifacts / lands / nonland permanents / ... (optionally "you don't control", "you control") | Wrath of God, Armageddon |
| Exile all creatures / ... | |
| This spell deals N (or X) damage to each creature / each creature you don't control / each opponent / each player | Pyroclasm |
| Each opponent (or each player) sacrifices a creature. Target player (or opponent) sacrifices a creature. | Diabolic Edict |
| Create N P/T color Subtype (artifact) creature token(s) (with flying, vigilance, ...). | Raise the Alarm |
| Create N Treasure / Clue / Food token(s). | Smothering Tithe |
| Destroy target permanent. Its controller creates a 3/3 green Beast creature token. | Beast Within |
| Put N +1/+1 (or -1/-1) counters on target creature / on each creature you control / on it. | |
| This creature enters with N +1/+1 counters on it. | Hydras |
| Target creature gets +N/+N (and gains keywords) / gains keywords until end of turn. | Giant Growth |
| Creatures you control get +N/+N and gain trample until end of turn. | Overrun |
| This creature gets +1/+0 until end of turn. (as an activated ability) | Shivan Dragon |
| Search your library for a basic land card, put it onto the battlefield tapped, then shuffle. | Rampant Growth |

- **Target restrictions:** destroy and exile targets can say "an opponent controls",
  "you don't control" or "you control".
- **Counters:** +1/+1 and -1/-1 counters change power and toughness. Matching +1/+1 and -1/-1
  counters cancel out.
- **Static abilities:** "(Other) (Elf) creatures you control get +1/+1 (and have flying)" and
  "Creatures you control have haste". These apply only while their source is on the battlefield.
- **Current power, toughness and keywords:** printed values plus counters, static abilities and
  "until end of turn" effects. They count everywhere: combat, damage, targeting (granted hexproof),
  destroy (granted indestructible), state checks, and the labels players see ("Bear 4/4").
  "Until end of turn" effects wear off in the cleanup step. An effect on "creatures you control"
  affects only the creatures there when it resolves. `Game.power`, `Game.toughness` and
  `Game.has_keyword` are the way to read them.
- **Tokens:** they enter with summoning sickness, and "dies" triggers still happen when they leave.
  After leaving the battlefield they stop existing, so they never reach the graveyard or exile.
  Treasure is a mana source that's sacrificed when used, and it's spent after lands and other sources.
  Clue and Food work through their activated abilities. Copy tokens and tokens with quoted abilities
  aren't supported yet.
- **Lands:**
  - Entering tapped: "This land enters tapped" (taplands, gain-lands, temples, triomes), and the conditional
    kinds: checklands ("unless you control an Island or a Swamp"; any land with that land type counts),
    fastlands ("two or fewer other lands"), slowlands ("two or more other lands"), and bond lands
    ("unless you have two or more opponents", so untapped in a 3+ player game). Fetched and reanimated lands
    follow the same rules.
  - Shocklands: you may pay 2 life or the land enters tapped. Life you can't spare (2 or less) isn't offered.
  - Painlands and Talismans: 1 damage when tapped for a colored mana. Colorless mana from them is free, and
    the payer picks painless sources first. Talismans make their colors now (they used to make colorless only).
  - Command Tower: only makes your commander's colors, whatever the card data lists.
  - Cycling {N}: an ability you can use from your hand at instant speed. Pay, discard the card, draw.
    Landcycling and other costs aren't supported.
  - Not yet: bouncelands, Pathways (double-faced), filter lands, City of Brass and Mana Confluence,
    Ancient Tomb, lands that make several mana.
- **Equipment and Auras:** "Equip {N}" is an activated ability at sorcery speed that targets a creature you
  control (re-equipping moves the Equipment). An Aura chooses what it enchants when cast, and goes to the
  graveyard instead of entering if that target is gone when it resolves. Attached permanents change the
  creature's power, toughness and keywords, so granted haste, hexproof or shroud work as usual (shroud stops
  even the controller's equip). Equipment stays on the battlefield, unattached, when its creature leaves;
  an Aura goes to the graveyard. Labels show attachments ("Sword attached to Bear (seat 0, #1)").
  "Can't attack or block" is supported through Auras. Other equip costs (like "Equip legendary creature {3}")
  and Auras on lands with special abilities aren't supported yet.
- **Protection from a color:** "Protection from red" (and "from red and from blue"), whether printed or given by
  Equipment, an Aura, a static ability, or "gains protection from red until end of turn". The protected permanent
  can't be targeted by red spells or abilities, takes no damage from red sources, can't be blocked by red
  creatures, and can't be enchanted or equipped by red permanents, so a red Aura or Equipment already on it
  falls off. The source's color is what counts: colorless sources ignore protection. A spell that targeted it
  before it gained protection fizzles. Not supported: "protection from the color of your choice" (Mother of
  Runes), "protection from everything", and non-color qualities like "from creatures".
- **Ward {N}:** when an opponent's spell or ability targets a warded permanent, a ward trigger goes on the stack
  above it. When it resolves, that opponent may pay {N} or their spell or ability is countered (an ability's
  source is left alone). You can't ward yourself, and if the opponent can't afford the cost they aren't asked.
  Only mana ward costs work, not "Ward—Pay 3 life".
- **Exile until it leaves:** Oblivion Ring, Banishing Light and Fiend Hunter exile a permanent, and when the source
  leaves the battlefield for any reason the exiled card comes back under its owner's control as a new permanent
  (summoning sick, without counters or attachments, and its "enters" abilities happen again). Tokens exiled this way
  are gone for good, and a commander that went to the command zone instead isn't returned. If the source has left
  by the time the exile ability resolves, nothing is exiled. "Another target" can't be the source itself.
- **Modal spells:** you choose the modes as you cast. Only modes that have a legal target are offered, a mode can't
  be chosen twice, and "one or both" / "one or more" let you stop with "Done choosing modes" once you have enough.
  Chosen modes happen in the order printed. If any mode isn't supported (or the card has entwine or escalate), the
  whole card is unsupported, and the report lists the mode.
- **Zones:** bounced permanents go to their owner's hand, and tokens stop existing. A commander headed for the
  hand can go to the command zone instead. Cards keep their owner: a creature you reanimate from an opponent's
  graveyard enters under your control, but goes back to their graveyard when it dies. Graveyard targets are
  checked again on resolution, and a spell with no legal graveyard target can't be cast.
- **Land ramp:** the player picks each land from the matching cards in their library ("basic land", or lands
  with the listed land types, which includes non-basic lands like Steam Vents for "Island or Mountain"),
  then the library is shuffled. Lands put onto the battlefield trigger landfall. A land put into the hand is
  revealed when the card says so.
- **Scry, surveil and mill:** scrying and surveilling look at the top cards one at a time and choose to keep
  each on top or put it on the bottom (scry) or into the graveyard (surveil). Cards kept on top stay in
  their original order. Only the scrying player sees the cards. Surveil's graveyard cards are public. Milling
  more cards than the library holds just mills what's there, and the player loses on their next draw.
- **Tutors:** the searcher picks from the matching cards in their library, which is then shuffled. Other players
  only learn which card unless it says "reveal it". If nothing matches, the library is just shuffled.
  Restrictions like "with mana value 3 or less" aren't supported yet.
- **Mass effects:** nothing is targeted, so hexproof doesn't help. Indestructible permanents survive
  "destroy all" but not exile or sacrifice. Everything leaves the battlefield at the same moment, so a
  creature watching for deaths triggers for every other creature that died with it, and a creature with
  "Whenever this creature or another creature dies" sees itself go too. The same is true when several
  creatures die to damage at once. "They can't be regenerated" is accepted and does nothing, since
  regeneration isn't implemented. A player chooses their own creature to sacrifice, in turn order.
  Restrictions like "with flying" or "with the greatest power" aren't supported yet.
- **Exile:** each player has an exile zone. Exiled creatures don't "die", so dies triggers don't fire.
  A commander heading to exile or the graveyard can go to the command zone instead.
- **Targets:** chosen when the spell is cast. If every target is gone when it resolves, the spell
  does nothing ("fizzles"). Hexproof and shroud are respected, and a spell with no legal target can't be cast.
- **Partial text:** if any sentence isn't understood, the spell still resolves but does nothing,
  and the `resolve` event is marked `"unsupported": true`. The engine never does half of what a card says.
- **Triggered abilities on permanents:** these use the same effect list as spells.

  | Trigger | Example |
  |---|---|
  | When this creature enters, ... | Mulldrifter: "When Mulldrifter enters, draw two cards." |
  | When this creature dies, ... | |
  | Whenever this creature attacks, ... | |
  | Whenever this creature deals combat damage to a player, ... | |
  | At the beginning of your upkeep / end step, ... | |
  | At the beginning of each upkeep / each end step, ... (every player's turn) | Tendershoot Dryad |
  | At the beginning of combat on your turn, ... | |
  | Whenever you gain life / lose life, ... (once per event, not per point) | Dina, Soul Steeper |
  | Whenever you sacrifice a creature, ... | Smothering Abomination |
  | Whenever another creature / a nontoken creature you control / an artifact ... enters, ... | Soul Warden |
  | Whenever a land you control enters, ... (Landfall) | |
  | Whenever (this creature or) another creature (you control) dies, ... | Zulaport Cutthroat |
  | Whenever a creature an opponent controls dies, ... | Yahenni, Undying Partisan |
  | When enchanted creature dies, ... | |
  | Whenever one or more cards leave your graveyard, ... (once per event) | Quintorius, History Chaser |
  | Whenever a player sacrifices a permanent / another permanent, ... | Merchant of Venom |
  | Whenever you lose life for the first time each turn, ... | |
  | Whenever you cast a (creature / noncreature / instant or sorcery) spell, ... | |
  | Whenever you cast a red (or other color) / Aura / "Aura, Equipment, or Vehicle" / historic spell, ... | Sram, Senior Edificer |
  | Whenever a player / an opponent casts a spell, ... | |
  | Whenever you cast your first spell with {X} in its mana cost each turn, ... (X is that spell's X) | Zimone, Infinite Analyst |
  | Whenever a creature (token) you control deals combat damage to a player, ... (once per creature) | Ohran Frostfang |
  | Whenever equipped / enchanted creature attacks, ... | |
  | Whenever you attack with two or more creatures, ... | Firemane Commando |

  - Triggers go on the stack the next time a player would get priority. The active player's go
    first, so they resolve last, and players can respond to them.
  - Targets are chosen when a trigger goes on the stack. A trigger with no legal target is removed.
  - "You may" abilities ask their controller when they resolve.
  - A card can call itself by its full name, its short legendary name ("Omnath"),
    "this creature" (or "this Aura", "this Equipment", "this Class", ...), or "it".
  - "This ability triggers only once each turn." is respected.
  - Intervening "if" clauses are checked when the ability triggers and again when it resolves (CR 603.4).
    Supported: "if a card left your graveyard this turn", "if you gained life this turn", "if an opponent
    controls more lands than you", "if you've cast an instant or sorcery spell this turn", "if you control
    seven or more Plains", "if you control no Snakes". A trigger with any other "if" clause is ignored.
  - Paying life counts as losing it. A creature that's sacrificed sees itself go
    ("Whenever you sacrifice a creature" on the creature itself triggers).
  - A trigger whose effect isn't understood is ignored. So is a watching trigger whose effect mentions
    "it" or "that creature", because that may mean the other object rather than the source.
  - Ability words like "Landfall —" are ignored when reading the trigger. A creature that dies still sees
    its own death ("Whenever this creature or another creature dies").
- **Activated abilities on permanents:** these also use the same effect list.

  | Cost | Example |
  |---|---|
  | Mana, {T}, sacrifice this, pay N life | Mind Stone: "{1}, {T}, Sacrifice this artifact: Draw a card." |
  | Planeswalker loyalty (+1, −3, 0) | "−3: Destroy target creature." |

  - They can be activated whenever you have priority, unless they say "Activate only as a sorcery".
    "Activate only once each turn" is respected.
  - Loyalty abilities: one per planeswalker per turn, at sorcery speed, and loyalty can't go below 0.
  - Creatures can't use {T} abilities the turn they arrive (unless they have haste).
  - A permanent can't tap itself for mana to pay for its own {T} or sacrifice ability.
  - Abilities go on the stack, so players can respond, and counterspells can't target them.
- **Other rules text on permanents:** static abilities, mana abilities with a cost (Signets),
  and activation costs like "sacrifice a creature" aren't implemented yet.

- **Hidden cards:** a drawn card's name goes only to the player who drew it.
- **Replays:** the same `seed` gives the same shuffles.

## What the engine can't play yet

```
python -m infernal_machine.report deck.txt
```

The report fetches the deck from Scryfall (caching cards in `.cache/cards.json`) and prints:
- how many cards are fully playable,
- the missing pieces grouped by kind, such as activated abilities, tokens or exile, with the most-affected kind first,
- every rules-text line the engine doesn't understand yet.

Use it to decide which effects to add next. In code: `deck_report(deck)` and `unsupported_lines(card)` in `report.py`.

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
  It pays life for shocklands only while above 10 life, takes the first mode of a modal spell, and always pays ward. It always keeps cards on top when scrying or surveilling. It equips Equipment once (not repeatedly), puts helpful Auras on its own creatures, and Pacifism-style ones on
  opponents'. It doesn't judge whether a board
  wipe helps it, so it will cast Wrath of God while ahead.
  It plays a land whenever it can, then casts its commander if it can,
  then its most expensive affordable spell, and otherwise passes.
  After casting, it activates abilities that tap, sacrifice, or use loyalty.
  It targets opponents' things when it can, never responds to its own spell,
  and always returns its commander to the command zone. In combat it attacks the opponent
  with the lowest life with every creature that has power. It blocks when its blocker survives,
  and chump-blocks the biggest attacker once it's at 10 life or less. When bottoming or discarding,
  it drops a land if over half the hand is lands, otherwise its most expensive spell.
- **`goldfish`:** plays the deck alone many times with the same mulligan rules and one land a turn.
  It reports how often you mulligan, how many lands the kept hand has, and how often
  you've made every land drop through each turn. The example above is a 38-land deck.

## Playing over TCP

**Server** (`python -m infernal_machine.server`) hosts one table:

| Option | Meaning |
|---|---|
| `--humans N` (default 1) | how many players will connect |
| `--bots N` (default 3) | bots that fill the other seats |
| `--bot-deck FILE` | decklist for the bots; repeat the option to give different bots different decks |
| `--port`, `--host` | where to listen (default `0.0.0.0:4000`) |
| `--seed N` | repeat the same shuffles |
| `--max-turns N` (default 300) | end the game with no winner after this many turns |
| `--cache FILE` | where fetched cards are saved (default `.cache/cards.json`) |
| `--no-check` | accept decks that aren't legal Commander decks |

Each human sends their decklist when they connect. The server fetches the cards, checks the deck, and either
seats the player or explains why not (wrong size, a card outside the commander's colors, an unknown card, a name
already in use), leaving the seat open. If a human disconnects during the game, a bot takes over their seat.

**Client** (`python -m infernal_machine.client --name Alice --deck deck.txt [--host H] [--port P]`):
- Events are printed as sentences ("Bot 1 casts Sol Ring.", "You lose 3 life (25).").
- When you have a decision, the board is shown and the options are numbered. Type a number.
  At a priority prompt, Enter passes. Type `b` to show the board again.
- Prompts where passing is your only option are answered for you.
- Your hand is shown to you only. Opponents' hands and libraries appear as counts.

Both can also be run as `infernal-server` and `infernal-client` after `pip install .`.

## TCP players

The engine talks to players through the `Player` protocol (`notify`, `choose`).
`TcpPlayer` implements it for remote clients:

```python
from infernal_machine.tcp import accept_players, listen

server = listen("0.0.0.0", 4000)
players = accept_players(server, count=2)
players[0].choose("Keep this hand?", ["Keep", "Mulligan"])
```

Each message is one JSON object per line:

| Direction | Message |
|---|---|
| client -> server | `{"type": "hello", "name": "Alice", "deck": "<decklist text>"}` (must come first; the deck is optional, but the game server needs it) |
| server -> client | `{"type": "welcome", "seat": 0}` |
| server -> client | `{"type": "event", ...}` (no reply) |
| server -> client | `{"type": "event", "event": "state", ...}`: the whole board, sent before each of your decisions. It has `turn`, `step`, `active`, `you`, your `hand`, the `stack`, and for each seat its life, hand and library counts, graveyard, exile, command zone (with commander tax), commander damage, and battlefield (with current power and toughness, counters and attachments) |
| server -> client | `{"type": "choose", "id": 1, "prompt": "...", "options": ["Keep", "Mulligan"]}` |
| client -> server | `{"type": "response", "id": 1, "choice": 0}` |
| server -> client | `{"type": "error", "message": "..."}` (after bad input the prompt is sent again) |

You can connect by hand with `nc localhost 4000`.

## Tests

```
python3 -m unittest discover -s tests -t .
```
