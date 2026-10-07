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
  Creatures can't tap for mana the turn they arrive.
  - Phyrexian symbols ({B/P}) are paid with mana when possible, otherwise with 2 life each, but never down to 0 life.
  - Twobrid symbols ({2/W}) are paid with one mana of that color if possible, otherwise with two mana of any kind.
  - {S} (snow) is paid by mana from a snow permanent ("Snow-Covered Forest"), which still makes its normal color.
  Signet-style abilities ("{1}, {T}: Add {W}{U}.") are used when plain sources aren't enough.
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
  - Kicker {N}: the caster chooses whether to pay it, before choosing targets. "If this spell was kicked, ..."
    effects on instants and sorceries happen only when it was, and can target (kicker is only offered when those
    targets exist). A kicked permanent (Auras too) remembers it: "If this creature was kicked, it enters with
    N +1/+1 counters on it." and "When this creature enters, if it was kicked, ..." (Untamed Kavu, Josu Vess).
  - Multikicker {N}: the caster chooses how many times to pay it, and "... enters with a +1/+1 counter on it for
    each time it was kicked." counts them (Gnarlid Pack). "Instead" wordings and non-mana kicker costs aren't
    supported.
  - Additional costs: "As an additional cost to cast this spell, sacrifice a creature / an artifact / an artifact
    or creature / a land / a permanent", "discard a card" or "pay N life". They're paid after mana, so a creature
    that tapped for mana can still be sacrificed. Effects that read the paid cost ("the sacrificed creature's
    power") aren't supported.
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
| Exile target creature (you control), then return it to the battlefield under its owner's (your) control. / ... Return it to the battlefield (or its owner's hand) at the beginning of the next end step. | Cloudshift, Flickerwisp |
| Exile target spell. / Counter target spell. If that spell is countered this way, exile it instead ... | Dissipate |
| Exile the top N cards of your library. You may play it (them) this turn. / Until the end of your next turn, you may play those cards. | Light Up the Stage |
| Choose one / two / three / one or both / one or more — • mode • mode ... (also in "When ..., choose one —" and "{T}: Choose one —") | charms and commands, Charming Prince |
| Entwine {cost} / Escalate {cost} (mana costs only) | Tooth and Nail |
| Tap all creatures your opponents control. | Cryptic Command |
| Target player (or opponent) draws N cards / gains N life / loses N life. | |
| Exile target card from a graveyard. | |
| Return target permanent to its owner's hand. Return all creatures to their owners' hands. | Cyclonic Rift, Evacuation |
| Return target (creature) card from your graveyard to your hand / to the battlefield. | Raise Dead, Zombify |
| Put target creature card from a graveyard onto the battlefield under your control. | Reanimate |
| Search your library for a (creature / legendary creature / Aura / Equipment / nonbasic land) card (with mana value N or less), (reveal it,) put it into your hand, then shuffle. | Demonic Tutor, Stoneforge-style |
| Search your library for a nonbasic land card / up to two Forest cards, put it onto the battlefield (tapped), then shuffle. | Skyshroud Claim |
| Return target creature card from your graveyard to the battlefield tapped. | |
| Search your library for a card, then shuffle and put that card on top. | Vampiric Tutor |
| You lose N life. | |
| Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle. | Cultivate, Kodama's Reach |
| Search your library for a (Plains, Island, ...) card, put it onto the battlefield (tapped), then shuffle. | Farseek, Nature's Lore |
| Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle. | Explosive Vegetation |
| Scry N. / Surveil N. | |
| Look at the top N cards of your library. Put one of them into your hand and the rest on the bottom. / You may reveal a creature card from among them... | |
| Take an extra turn after this one. / Target player takes an extra turn after this one. | Time Walk, Time Warp |
| After this (main) phase, there is an additional combat phase (followed by an additional main phase). | Relentless Assault |
| Untap all creatures that attacked this turn. / Untap all creatures you control. | Aggravated Assault |
| You become the monarch. | Palace Jailer |
| You take the initiative. | Caves of Chaos Adventurer |
| Goad target creature. / Goad all creatures you don't control. | Disrupt Decorum |
| Whenever an opponent casts a spell / draws a card, (you may) draw a card / create a Treasure token unless that player pays {N}. | Rhystic Study, Mystic Remora, Smothering Tithe |
| Whenever you become the monarch, ... / Whenever an opponent becomes the monarch, ... | |
| Starting with you, each player votes for X or Y. For each X vote, ... / If X gets more votes (or the vote is tied), ... | Tivit, Plea for Power, Capital Punishment |
| Starting with you, each player votes for a nonland permanent you don't control. Exile each permanent with the most votes or tied for most votes. | Council's Judgment |
| Investigate. | |
| Mill N cards. / Target player (or opponent) mills N cards. / Each opponent (or player) mills N cards. | |
| Discard N cards (at random). / Discard your hand. / Target player (or opponent) discards N cards (at random). / Each opponent (or player) discards N cards or their hand. | Mind Rot, Hymn to Tourach, Windfall |
| Draw N cards, then discard N cards. / Each player discards their hand, then draws N cards. / Each player draws N cards. | Faithless Looting, Wheel of Fortune |
| Target player reveals their hand. You choose a (nonland / noncreature, nonland / ... with mana value N or less) card from it. That player discards that card. | Thoughtseize, Duress, Inquisition of Kozilek |
| Equip {N} (Equipment) | Swiftfoot Boots, Lightning Greaves |
| Equip—Pay N life. / Sacrifice a creature. / Discard a card. | Blood-style equipment |
| Whenever equipped (enchanted) creature dies / deals combat damage to a player, ... | Sword of Feast and Famine-style |
| When this is put into a graveyard from the battlefield, return it to its owner's hand. | Rancor |
| Enchanted (equipped) creature (land) has "{T}: ..." | Enchanted land has "{T}: Add {G}{G}." |
| Equipped creature gets +N/+N and has keywords. / Enchanted creature gets +N/+N and has keywords. | |
| Enchant creature / land / ... (Auras) | |
| Enchanted creature can't attack or block. | Pacifism |
| Destroy all creatures / artifacts / lands / nonland permanents / ... (optionally "you don't control", "you control") | Wrath of God, Armageddon |
| Exile all creatures / ... | |
| Destroy / exile all creatures with flying / without flying / with power 4 or greater / with toughness 2 or less / nonblack / white | Hurricane-style wipes |
| This spell deals N (or X) damage to each creature / each creature you don't control / each opponent / each player | Pyroclasm |
| ... damage to each creature with flying (and each player) | Electrickery-style |
| Each opponent (or each player) sacrifices a creature / artifact / enchantment / land / permanent. Target player (or opponent) sacrifices one. | Diabolic Edict |
| Sacrifice a creature. | Smothering Abomination |
| Two things joined by "and": "... and you gain 1 life", "You gain 1 life and draw a card", "You draw two cards and lose 2 life" | Blood Artist, Night's Whisper |
| Create N P/T color Subtype (artifact) creature token(s) (with flying, vigilance, ...). | Raise the Alarm |
| Create a P/T ... creature token with (flying and) "<an ability we understand>" | Pest: "When this creature dies, you gain 1 life." |
| Create N Treasure / Clue / Food token(s). | Smothering Tithe |
| Create a token that's a copy of target creature (you control). / Populate. | Growing Ranks |
| Destroy target permanent. Its controller creates a 3/3 green Beast creature token. | Beast Within |
| Put N +1/+1 (or -1/-1) counters on target creature / on each creature you control / on it. | |
| This creature enters with N +1/+1 counters on it. | Hydras |
| Target creature gets +N/+N (and gains keywords) / gains keywords until end of turn. | Giant Growth |
| Creatures you control (or your opponents control) get +N/+N (and gain keywords) until end of turn. | |
| Target creature gets +X/+X (-X/-X, +X/+0, ...) until end of turn, for each ... / where X is ... | |
| Target creature becomes a 4/4 Dragon until end of turn. / has base power and toughness 0/1 until end of turn. | |
| Put N <kind> counters on target <permanent>. / Remove N (all) <kind> counters from target <permanent>. / Remove all counters from target <permanent>. | |
| Double the number of +1/+1 counters on each creature you control. | |
| Move a (or all) +1/+1 counter(s) from target creature onto another target creature. | Bioshift |
| Until end of turn, this land becomes a P/T (color) (Subtype) (artifact) creature (with keywords). It's still a land. / Target land you control becomes a ... | Mutavault, Treetop Village |
| Each opponent (or player) creates a token. / Target opponent creates a token. | |
| Creatures you control get +N/+N and gain trample until end of turn. | Overrun |
| This creature gets +1/+0 until end of turn. (as an activated ability) | Shivan Dragon |
| Search your library for a basic land card, put it onto the battlefield tapped, then shuffle. | Rampant Growth |

- **Wording:** "of their choice" and a leading "You draw" / "You create" are read the same as without them.
- **Amounts that depend on the game:** "..., where X is ...", "... equal to ..." and "... for each ..." are worked out
  when the effect resolves. Supported: its (or this creature's) power, using its last known power if it has left the
  battlefield; counters of any kind on it ("charge counters on this artifact"); cards (or <type> cards) in your graveyard; the number of <type> you control; creatures on the battlefield; the amount of life
  you gained this turn; half your life total, rounded down or up; spells you've cast this turn; the greatest mana value among instant and sorcery spells you've
  cast this turn; opponents. "For each" multiplies drawing, life, tokens, +1/+1 counters and a pump ("+2/+2 until end of turn for each creature you control") ("create a 1/1 Saproling
  token for each +1/+1 counter on this creature"). A sentence a template already understands is never rewritten.
  "An X/X ... token" gets its size when it's created (Rootha, Mastering the Moment).
- **Target restrictions:** destroy and exile targets can say "an opponent controls",
  "you don't control" or "you control".
- **Counters:** +1/+1 and -1/-1 counters change power and toughness. Matching +1/+1 and -1/-1
  counters cancel out. Other kinds ("charge", "time") are only counted. "Put N <kind> counters on target <permanent>",
  "Remove N <kind> counters from target ...", "Remove all (<kind>) counters from target ..." and "Double the number of
  +1/+1 counters on each creature you control" work. "Move a (or all) <kind> counter(s) from target creature onto
  another target creature" moves up to that many; moved counters aren't "put", so Doubling Season doesn't double them.
  "Move any number of" isn't built.
- **Setting power and toughness:** "Target creature becomes a 4/4 (color) (Subtype) (creature) (with flying) until end of
  turn" and "has base power and toughness 0/1 until end of turn" set the base; counters and bonuses still add to it,
  whatever order they came in. Its types, subtypes and colors don't change.
- **Animating lands:** "Until end of turn, this land becomes a 3/3 green Ape creature with trample. It's still a land."
  (Mutavault, Blinkmoth Nexus, Treetop Village, Celestial Colonnade) and "Target land you control becomes a 3/3
  Elemental creature with haste until end of turn. It's still a land." The permanent keeps its types and gains
  Creature (and Artifact), the stated subtypes, colors, power and toughness, and keywords; "with all creature types"
  adds no subtype. It goes back to a plain card at end of turn. A land is summoning sick the turn it comes in, so it
  can't attack or use {T} abilities if animated that turn. Bots never activate these abilities.
- **Tokens for other players:** "Each opponent (or player) creates ..." and "Target opponent creates ...". A token
  with "This creature can't block / attack / attack or block." gets that restriction.
- **Static abilities:** "(Other) (Elf) creatures you control get +1/+1 (and have flying)" and
  "Creatures you control have haste". These apply only while their source is on the battlefield.
  - Either can be conditional, written "As long as X, ..." or "... as long as X.", and a creature can buff
    itself ("As long as you control an artifact, this creature gets +1/+1 and has flying."). The buff is checked
    every time power, toughness or keywords are looked at, so it switches on and off as the game changes.
    Conditions: you control a/N or more <type>, you control no <type>, it's your turn, you're the monarch,
    you have no cards in hand, you have N or more cards in hand, plus the graveyard, life, lands and cast
    conditions listed under triggers. A line with any other condition is ignored.
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
  - Ancient Tomb ("{T}: Add {C}{C}. ... deals 2 damage to you."): two mana from one tap, and the damage is dealt
    once per tap however much of the mana is used. Bouncelands ("{T}: Add {B}{G}.") make both colors the same way.
  - City of Brass ("Whenever this land becomes tapped, it deals 1 damage to you."): hurts every time it's tapped
    for mana. Mana Confluence ("{T}, Pay 1 life: Add one mana of any color."): pays life (not damage), and is not
    used when you can't afford it. The payer picks painless sources first.
  - Bouncelands: "enters tapped" plus "When this land enters, return a land you control to its owner's hand."
    You choose the land and it can be itself; bots return the newest land.
  - Cycling {N}: an ability you can use from your hand at instant speed. Pay, discard the card, draw.
    Basic landcycling {N} and Plainscycling / Islandcycling / Swampcycling / Mountaincycling / Forestcycling {N}
    fetch a land to your hand instead (basic land, or any land with that type). Costs other than mana aren't supported.
  - Not yet: bouncelands, Pathways (double-faced), filter lands, City of Brass and Mana Confluence,
    Ancient Tomb, lands that make several mana.
- **Equipment and Auras:** "Equip {N}" is an activated ability at sorcery speed that targets a creature you
  control (re-equipping moves the Equipment). An Aura chooses what it enchants when cast, and goes to the
  graveyard instead of entering if that target is gone when it resolves. Attached permanents change the
  creature's power, toughness and keywords, so granted haste, hexproof or shroud work as usual (shroud stops
  even the controller's equip). Equipment stays on the battlefield, unattached, when its creature leaves;
  an Aura goes to the graveyard. Labels show attachments ("Sword attached to Bear (seat 0, #1)").
  "Can't attack or block" is supported through Auras.
  - **Other equip costs:** "Equip—Pay 3 life.", "Equip—Sacrifice a creature.", "Equip—Discard a card." are paid like any
    ability cost. "Equip legendary creature {3}" (a restriction on what it can equip) isn't supported.
  - **Triggers on what is attached:** "Whenever equipped (or enchanted) creature dies / deals combat damage to a
    player, ..." (the Equipment's or Aura's controller gets the trigger). "When this Aura is put into a graveyard
    from the battlefield, return it to its owner's hand" (Rancor) works for any permanent, and so does "When
    enchanted creature dies, return this Aura to its owner's hand": it comes back from the graveyard it is in.
    Exiled, it isn't returned.
  - **Granting abilities:** "Enchanted (or equipped) creature has "{T}: Draw a card."" lets that creature activate it
    (a summoning-sick one can't use {T}). "Enchanted land has "{T}: Add {G}{G}."" makes the land tap for that mana
    instead of its own single mana. A quoted ability that isn't understood leaves the card unsupported.
  - **Not built:** Reconfigure, Fortify and Fortifications, "Whenever this Equipment becomes attached", Wild
    Growth-style "whenever enchanted land is tapped for mana", and an equip bonus that scales ("+1/+1 for each").
- **Replacement effects:** statics that change what would happen, read from a permanent on the battlefield.
  - Rest in Peace: "If a card or token would be put into a graveyard from anywhere, exile it instead." (Leyline of the
    Void: only an opponent's cards.) Every route to a graveyard is covered: spells, dying, discarding, milling, cycling.
    Things still die, so dies triggers happen; a commander can still choose the command zone. Rest in Peace's "exile
    all cards from all graveyards" is supported.
  - Doubling Season and Parallel Lives: tokens an effect creates under your control, and counters an effect puts on your
    permanents (including the counters a permanent enters with), are doubled. Several stack (two doublers: four times).
    Hardened Scales adds one to +1/+1 counters on your creatures first, then doubling applies.
  - Panharmonicon and Yarok: a triggered ability of a permanent you control that triggers because an artifact or creature
    (or any permanent) entered triggers an additional time; each such permanent adds one. Both the entering
    permanent's own "When this enters" and watching "Whenever another creature enters" abilities count.
    "This ability triggers only once each turn" still holds.
- **Copying:**
  - Clone: "You may have this creature enter the battlefield as a copy of any creature on the battlefield." (also
    "a creature you control", and artifacts, enchantments or lands). It is decided as it enters, with a "Don't copy
    anything" choice, so the copy's enters abilities trigger. A copy has the other card's printed characteristics,
    not its counters or damage; a copy of a token isn't a token. It goes to the graveyard as the Clone card.
    Bots copy the biggest creature. "Except ..." variants (Phyrexian Metamorph, Phantasmal Image) aren't supported.
  - "Copy target instant or sorcery spell (you control). You may choose new targets for the copy." The copy goes on
    the stack above the spell and resolves first. It isn't cast (no cast triggers) and isn't a card, so it vanishes
    instead of going to the graveyard, even if countered. With the second sentence its controller picks targets
    again (the old ones are still choices); without it the copy keeps them. Abilities can't be copied yet.
  - "Create a token that's a copy of target creature" and populate were added earlier.
- **Control change:** "Gain control of target creature." (permanent), "Gain control of target creature until end of turn.
  Untap that creature. It gains haste until end of turn." (Threaten), and Control Magic ("Enchant creature. You
  control enchanted creature."). The permanent moves to the new controller's battlefield, is summoning sick for
  them (haste fixes that), and leaves combat. Its owner doesn't change, so it goes to its owner's graveyard if it
  dies. Threaten's effect ends in the cleanup step; Control Magic's ends as soon as the Aura stops being
  attached or leaves, and the creature goes back to whoever controlled it before. A lone "Untap that creature."
  isn't understood. Bots aim Control Magic at an opponent's creature.
- **Vehicles:** "Crew N" is an ability at instant speed: tap untapped creatures you control, one at a time, until their
  total power is N or more (summoning-sick creatures can crew, the Vehicle can't crew itself). Until end of turn the
  Vehicle is an artifact creature, with its printed power and toughness, so it can attack (not the turn it arrived)
  and block, and it dies like a creature. It goes back to being a plain card at end of turn or when it leaves. It
  can't be crewed twice in a turn, and bots crew whenever they can.
- **Sagas:** "I — ...", "II — ..." and "I, II — ..." chapters. A Saga enters with a lore counter and its
  chapter I triggers; each of its controller's turns, after the draw step, it gets another and the matching chapter
  triggers. Once the last chapter's ability has resolved it is put into the graveyard. A Saga is all or nothing: if
  any chapter isn't understood it has none, and the report lists its lines.
- **Protection:** "Protection from red" (and "from red and from blue"), printed or given by Equipment, an Aura, a
  static ability, or "gains protection from red until end of turn". The protected permanent can't be targeted,
  damaged, blocked, enchanted or equipped by the source. What counts about the source is its colors, its card types
  and whether it is monocolored, multicolored or colorless, so these work too: "protection from everything", "from
  all colors", "from monocolored" / "multicolored", "from creatures" / "artifacts" / "enchantments" / "instants" /
  "sorceries" / "planeswalkers". Protection from creatures stops creatures blocking it and creature damage and
  abilities, but not a Bolt. An Aura or Equipment of a type it is protected from falls off. A spell that targeted it
  before it gained protection fizzles.
  - **"Protection from the color of your choice"** (Mother of Runes, Gods Willing), as "Target creature (you
    control) gains protection from the color of your choice until end of turn" or "This creature gains ...": the
    controller picks one of the five colors as it resolves. Bots take the first (white).
- **Ward:** when an opponent's spell or ability targets a warded permanent, a ward trigger goes on the stack and the
  spell or ability is countered unless its controller pays. The cost can be mana ("Ward {2}"), life ("Ward—Pay 3
  life."), discarding ("Ward—Discard a card.") or a mix ("Ward—{1}, Pay 2 life."); if they can't pay they aren't
  asked, and bots always pay when they can. Ward can also be given: "Other creatures you control have ward {1}",
  "Equipped creature has ward {2}". You can't ward yourself. Not supported: tapping or sacrificing as a ward cost.
- **Exile until it leaves:** Oblivion Ring, Banishing Light and Fiend Hunter exile a permanent, and when the source
  leaves the battlefield for any reason the exiled card comes back under its owner's control as a new permanent
  (summoning sick, without counters or attachments, and its "enters" abilities happen again). Tokens exiled this way
  are gone for good, and a commander that went to the command zone instead isn't returned. If the source has left
  by the time the exile ability resolves, nothing is exiled. "Another target" can't be the source itself.
- **Flicker and delayed returns:** "Exile target creature you control, then return it to the battlefield under its
  owner's (or your) control" (Cloudshift, Ephemerate) brings it back at once; "Exile target creature. Return it to the
  battlefield under its owner's control at the beginning of the next end step" (Flickerwisp's "another target
  permanent" too) or "...to its owner's hand at the beginning of the next end step" waits. It comes back as a new
  object with no counters, summoning sick, and its enters triggers happen again. A token is gone for good. Cast
  during the end step itself, the card waits for the next turn's end step.
- **Exiling a spell:** "Exile target (kind of) spell." and "Counter target spell. If that spell is countered this way,
  exile it instead of putting it into its owner's graveyard." The spell goes to its owner's exile, not the graveyard.
- **Exile, then play it:** "Exile the top card (or N cards) of your library. You may play it this turn" and
  "...Until the end of your next turn, you may play those cards." The cards sit in exile and show up as "Cast from
  exile: ..." and "Play land from exile: ..." until the permission ends (a land uses your land drop; each card can
  be played once). "Your next turn" is the next turn that comes round to you in normal order. Without "you may play",
  "Exile the top N cards" just exiles them. Bots play exiled cards like cards in hand.
- **Modal spells:** you choose the modes as you cast. Only modes that have a legal target are offered, a mode can't
  be chosen twice, and "one or both" / "one or more" let you stop with "Done choosing modes" once you have enough.
  Chosen modes happen in the order printed. If any mode isn't supported, the whole card is unsupported, and the
  report lists the mode.
  - **Entwine {cost}:** offered (yes or no) when every mode has a target and the extra cost can be paid; paying it
    does all the modes. **Escalate {cost}:** each mode beyond the first adds the cost, and a mode that would cost
    more than the caster has isn't offered. Only mana costs are understood ("Escalate\u2014Discard a card" leaves
    the card unsupported). Bots always entwine when they can, and keep adding modes while they can pay.
  - **Modal triggers and abilities** ("When this creature enters, choose one \u2014", "{T}: Choose one \u2014"): the
    modes are chosen when the ability goes on the stack, before its targets. It isn't put on the stack if no
    mode has a legal target (and can't be activated at all). One mode that isn't understood leaves the whole
    ability unsupported.
- **Zones:** bounced permanents go to their owner's hand, and tokens stop existing. A commander headed for the
  hand can go to the command zone instead. Cards keep their owner: a creature you reanimate from an opponent's
  graveyard enters under your control, but goes back to their graveyard when it dies. Graveyard targets are
  checked again on resolution, and a spell with no legal graveyard target can't be cast.
- **Land ramp:** the player picks each land from the matching cards in their library ("basic land", or lands
  with the listed land types, which includes non-basic lands like Steam Vents for "Island or Mountain"),
  then the library is shuffled. Lands put onto the battlefield trigger landfall. A land put into the hand is
  revealed when the card says so.
- **Extra turns, monarch and goad:**
  - Extra turns go to the player who asked, right after the current turn; the latest one asked for goes first,
    and regular turn order then carries on from where it was.
  - The monarch draws a card at their end step. Combat damage dealt to the monarch by a creature makes that
    creature's controller the monarch. If the monarch loses, the active player becomes monarch.
  - **The initiative:** "You take the initiative" makes you venture into the Undercity (`undercity.py` has the
    rooms: Secret Entrance, Forge, Lost Well, Trap!, Arena, Stash, Archives, Catacombs, Throne of the Dead
    Three). You also venture at your upkeep while you hold it, and combat damage to the holder from a creature
    takes it (each hit is checked on its own, so two players' creatures hitting at once give it to the first
    one resolved). If the holder loses, the active player takes it. Each room's ability goes on the stack and
    uses the normal targeting, so the player chooses targets and the next room (when there are two exits);
    leaving the last room completes the dungeon and the next venture starts over. The Throne's creature enters
    with three +1/+1 counters and hexproof until its controller's next turn begins. Bots take the first exit and
    put the Forge's counters on their own creature. "Whenever you take the initiative" and "if you have the
    initiative" aren't understood.
  - **Voting:** "Starting with you, each player votes for X or Y" (and, for Council's Judgment, for a nonland
    permanent you don't control), with the card's own outcome: "For each X vote, ..." (Tivit),
    "If X gets more votes [or the vote is tied], ..." (Plea for Power), or "Exile each permanent with the most votes
    or tied for most votes". The vote goes round in turn order starting with the caster, and every vote is public.
    Only outcomes that need no target are understood, and a vote with no outcome is ignored with its card. Bots
    vote against an opponent's permanent, and for the first word otherwise. Capital Punishment's two-part
    outcome ("Each opponent sacrifices a creature for each death vote and discards a card for each taxes vote") is
    two per-vote outcomes; the second part takes the first's subject if it has none.
  - An additional combat phase goes right after the current phase (after combat ends, if it comes from inside
    combat), with an additional main phase after it if the card says so. Cast before combat, it simply gives
    you two combats, and creatures tapped in the first can't attack in the second.
  - A goaded creature must attack each combat if able, and not the goader if another opponent can be attacked.
    It lasts until the goader's next untap step. "Goad all creatures you don't control" goads every creature
    each opponent controls.
  - "Whenever you become the monarch" and "Whenever an opponent becomes the monarch" trigger only when the
    monarch actually changes.
  - "... unless that player pays {N}": the player who cast the spell or drew the card is asked whether to pay
    when the trigger resolves, and is only asked if they can. Understood only for effects that need no target
    (draw, create a token, gain or lose life).
- **Scry, surveil and mill:** scrying and surveilling look at the top cards one at a time and choose to keep
  each on top or put it on the bottom (scry) or into the graveyard (surveil). When two or more stay on top the
  player is asked which goes on top next (bots keep the order). Only the scrying player sees the cards. Surveil's graveyard cards are public. Milling
  more cards than the library holds just mills what's there, and the player loses on their next draw.
- **Discard:** the player discards the cards they choose, unless it says "at random" (then nobody is asked) or
  "their hand" (all of it goes, in order, and nobody is asked). Discarding more cards than the hand holds just
  empties it, and every discard is public. Thoughtseize-style effects reveal the hand to everyone, then the
  caster picks from the cards that fit ("nonland", "noncreature, nonland", "mana value 3 or less"); if none fit,
  the hand is only revealed. The three sentences are understood only together. Bots discard their worst card
  (a land if more than half the hand is lands, otherwise the most expensive spell), and take the most expensive
  card they can see; cards from an opponent's hand they don't know count as worth nothing. Not understood: "Discard
  a card, then ..." followed by anything but a draw, "whenever you discard", madness, and discarding "that many".
- **Look at the top N (impulse effects):** "Look at the top four cards of your library. Put one of them into
  your hand and the rest on the bottom of your library in any order." and "Look at the top five cards... You may
  reveal a creature card from among them and put it into your hand. Put the rest on the bottom..." are understood
  only as a whole. The rest go to the bottom in a random order (the engine picks the order for "any order").
  The optional reveal shows everyone the card; the plain version keeps it private. Bots take the highest
  mana value card.
- **Tutors:** the searcher picks from the matching cards in their library, which is then shuffled. Other players
  only learn which card unless it says "reveal it". If nothing matches, the library is just shuffled.
  "With mana value 3 or less / 3 or greater / 3" works for searches and for graveyard targets
  ("Return target creature card with mana value 2 or less from your graveyard to your hand"); only the cards that
  match are offered. "A land card" can go onto the battlefield (any land, not just a basic). Reanimate's "You lose
  life equal to its mana value" follows the card it put onto the battlefield.
  The kind can also be "legendary" or "legendary creature", "nonbasic land", or a subtype: "Aura", "Equipment",
  "Vehicle", "Saga" ("an Equipment card with mana value 2 or less"). The same kinds work for cards in a
  graveyard ("Return target legendary creature card from your graveyard to your hand"). "Return ... to the
  battlefield tapped" is supported. Land searches also cover "a nonbasic land card" and "up to two Forest (or
  Mountain or Forest) cards" onto the battlefield, tapped or not. "Your opponents control" works in "Return all
  creatures your opponents control to their owners' hands" and in destroy and exile all. Tribal cards work too: a
  capitalized subtype before "card" ("an Elf card", "target Goblin card from your graveyard"), but only a single
  word (not "Time Lord"). Cards in a graveyard are offered by name, so two copies of a card are one choice.
- **Targets:** "another target ..." (bounce, destroy, exile) can't be the source itself, and "up to one target ..."
  (bounce, destroy, exile) adds a "No target" choice at the end of the list; the spell can be cast even when there
  is nothing to target. Bots take a real target when there is one.
  - **"Up to two (three, four) target creatures"** (also artifacts, enchantments, permanents, nonland permanents,
    lands, creature tokens, and creature cards in your graveyard) for bounce, destroy and exile: one target prompt
    per target, each with "No target", and a target already chosen can't be chosen again by the same effect.
  - **More kinds of target:** "creature token", "nontoken creature", "tapped / untapped / attacking creature" and
    "land", each also with "you control" / "an opponent controls".
- **Mass effects:** nothing is targeted, so hexproof doesn't help. A restriction ("with flying", "with power 4 or
  greater", "nonblack") is checked when the effect resolves, using the permanent's current keywords and stats, so
  a creature that was given flying until end of turn counts. Only the keywords the engine knows are accepted; "with a
  +1/+1 counter on it" and similar aren't supported. Indestructible permanents survive
  "destroy all" but not exile or sacrifice. Everything leaves the battlefield at the same moment, so a
  creature watching for deaths triggers for every other creature that died with it, and a creature with
  "Whenever this creature or another creature dies" sees itself go too. The same is true when several
  creatures die to damage at once. A player chooses their own creature to sacrifice, in turn order.
  - **More restrictions:** "with mana value N or less / greater" (any permanent, not just creatures), "nontoken",
    "creature tokens", "legendary", "tapped" / "untapped", "nonbasic" (lands), plus the existing keywords, power,
    toughness and color. **"Except":** "except (for) artifact (enchantment, legendary, white, ...) creatures",
    "except (for) creatures with flying" and "except for tokens" leave those alone. "Your opponents control" works
    in all of them.
  - **Wipes that give something back:** "Destroy all creatures. For each creature destroyed this way, its controller
    creates a 1/1 white Spirit creature token." (also for exile): a token per creature that really left, to its
    last controller; an indestructible survivor gives nothing.
  - **Sacrifice:** "Each player (opponent) sacrifices two lands", "...a nonland permanent", "...an artifact or
    enchantment", "...all creatures they control", "...a creature with the greatest power among creatures they
    control" (they choose among the tied greatest), and "Sacrifice all creatures you control." With fewer
    than asked, they sacrifice what they have.
  - **Also:** "deals N damage to each creature your opponents control" and "All creatures get -2/-2 until end of turn."
    Farewell works as a plain modal spell ("Choose one or more" with "Exile all graveyards"). "That are one or more colors / colorless / multicolored / monocolored" works in destroy and exile all ("Exile all
    nonland permanents that are one or more colors"), and so do "an attacking / tapped / untapped creature" in the
    sacrifice effects. Not built: other "that are ..." conditions.
- **Regeneration:** "Regenerate target creature.", "{B}: Regenerate this creature." and "Regenerate each creature you
  control." give a shield that lasts until end of turn (several stack). The next time the creature would be
  destroyed, by a destroy effect or by lethal damage or deathtouch, it is tapped, loses all its damage and leaves
  combat instead (a blocked attacker stays blocked). "It can't be regenerated" and "They can't be regenerated" after
  a destroy effect make that effect skip shields. Exile, sacrifice and zero toughness aren't destruction, so shields
  don't help. Activating in response works like any ability, but bots don't regenerate on their own.
  "Sacrifices the creature with the greatest power" isn't supported yet.
- **Fight, proliferate, persist and undying:**
  - "Target creature you control fights target creature you don't control." (also "fights another target creature")
    and "Target creature you control deals damage equal to its power to target creature you don't control." (a bite,
    one-sided). It takes two targets; each deals damage equal to its power to the other at the same time, with its
    deathtouch and lifelink. If either target is gone or they are the same creature, nothing happens.
  - "Proliferate." lets you pick any permanents (yours or an opponent's) that have counters, or planeswalkers; each gets
    one more of every kind it has. You choose one at a time and finish with "Done". Bots pick only their own.
  - Persist and undying: when the creature dies with no -1/-1 (persist) or +1/+1 (undying) counter on it, it comes
    back from the graveyard under its owner's control with one. It is a dies trigger, so it uses the stack and
    can be answered; a token or a card that went somewhere else instead (a commander in the command zone) doesn't return.
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
  | Whenever this creature blocks, ... | |
  | When this creature enters or dies, ... (also "attacks or blocks"; one ability per event) | |
  | Whenever a creature you control attacks, ... (once per attacker) | |
  | Whenever you draw a card, ... (once per card; the opening hand doesn't count) | |
  | Whenever an opponent draws a card / gains life / loses life, ... | Sheoldred, the Apocalypse |
  | Whenever you draw your second card each turn, ... | |
  | Whenever an opponent sacrifices a creature, ... | |
  | Whenever you discard a card / an opponent discards a card, ... | Megrim |
  | Whenever an opponent searches their library, ... | Opposition Agent |
  | Whenever a creature enters / dies, ... its controller ... | |
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
  | Whenever a creature attacks you (or a planeswalker you control), ... (once per attacker) | |

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
    seven or more Plains", "if you control no Snakes", "if you control an artifact", "if it's your turn", "if you're
    the monarch", "if you have no cards in hand". A trigger with any other "if" clause is ignored.
  - Paying life counts as losing it. A creature that's sacrificed sees itself go
    ("Whenever you sacrifice a creature" on the creature itself triggers).
  - A trigger whose effect isn't understood is ignored.
  - In triggers about another creature (enters, dies, attacks, attacks you, deals combat damage), "it" and
    "that creature" mean that creature ("put a +1/+1 counter on it"), but only when every effect is about "it".
  - In triggers about another player (an opponent draws, gains or loses life, discards, searches their library, or casts a spell), "that player"
    and "they" mean that player ("they lose 2 life", "deals 2 damage to that player"), but only for effects that
    target a player. Anywhere else a line that says "it", "they" or "that player" is ignored.
  - Ability words like "Landfall —" are ignored when reading the trigger. A creature that dies still sees
    its own death ("Whenever this creature or another creature dies").
- **Activated abilities on permanents:** these also use the same effect list.

  | Cost | Example |
  |---|---|
  | Mana, {T}, sacrifice this, pay N life | Mind Stone: "{1}, {T}, Sacrifice this artifact: Draw a card." |
  | Planeswalker loyalty (+1, −3, 0) | "−3: Destroy target creature." |
  | Sacrifice a creature / another creature / an artifact (land, enchantment, permanent) | "Sacrifice a creature: Draw a card." |
  | Discard a card | "{1}, Discard a card: Draw a card." |
  | Exile a card from your graveyard | "{1}, Exile a card from your graveyard: You gain 1 life." |

  - They can be activated whenever you have priority, unless they say "Activate only as a sorcery".
    "Activate only once each turn" is respected.
  - Loyalty abilities: one per planeswalker per turn, at sorcery speed, and loyalty can't go below 0.
  - Creatures can't use {T} abilities the turn they arrive (unless they have haste).
  - A permanent can't tap itself for mana to pay for its own {T} or sacrifice ability.
  - Abilities go on the stack, so players can respond, and counterspells can't target them.
  - Card costs ("Sacrifice a creature", "Discard a card", "Exile a card from your graveyard") are paid when you
    activate, and the ability isn't offered unless you can pay. You can sacrifice only your own permanents; the
    source itself counts unless it says "another". Bots don't use abilities that cost their own cards. Costs
    can name two to four cards ("Sacrifice two creatures", "Discard two cards", "Exile three cards from your
    graveyard"); ward costs still pay one card.
  - "Scry N, then reveal the top card of your library. If it's a land card, put it onto the battlefield
    (tapped). Otherwise, draw a card." (Thrasios, Triton Hero) is understood as a whole or not at all.

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
