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
# or play in your browser instead
python -m infernal_machine.web --name Alice --deck examples/green_deck.txt
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
- `BulkSource(".cache/oracle_bulk.json")` skips the per-card API calls. It downloads Scryfall's
  [Oracle Cards bulk file](https://scryfall.com/docs/api/bulk-data) (~25 MB gzipped, ~35,000 cards) once, saves a
  slim copy, and refreshes it after a week (keeping the old copy if Scryfall is unreachable). Everything after
  that is offline. The server uses it with `--bulk .cache/oracle_bulk.json`.
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
  - Bestow {N} (Eidolon of Countless Battles): an alternative cost, offered when you control a creature to enchant. It
    resolves as an Aura attached to that creature (as a creature if the target is gone), and becomes a creature again
    when the creature it enchants leaves.
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
  - Two kicker costs ("Kicker {R} and/or {W}"): each is offered separately, when it can be paid, and
    "if it was kicked with its {R} kicker" / "If this spell was kicked with its {1}{B} kicker, ..." check that
    specific cost (Thornscape Battlemage).
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
| Exile the top N cards of your library. You may play it (them) this turn. / Until the end of your next turn, you may play those cards. | Reckless Impulse |
| Choose one / two / three / one or both / one or more — • mode • mode ... (also in "When ..., choose one —" and "{T}: Choose one —") | charms and commands, Cleanup Crew |
| Entwine {cost} / Escalate {cost} (mana costs only) | Barbed Lightning (entwine), Blessed Alliance (escalate) |
| Tap all creatures your opponents control. | Cryptic Command |
| Target player (or opponent) draws N cards / gains N life / loses N life. | |
| Exile target card from a graveyard. | |
| Return (another) target permanent to its owner's hand. Return all creatures to their owners' hands. | Cyclonic Rift, Evacuation, Rushing River |
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
| Untap target land (permanent, creature, ...). / Untap another target creature. / Untap up to two target lands. | |
| Untap all lands (artifacts, permanents, enchantments) you control. | |
| Return all creature tokens / all nontoken creatures to their owners' hands. | Perplexing Test |
| Untap it. / Untap this creature. (in "Whenever this creature attacks, untap it", or "equipped creature ... untap it") | |
| You become the monarch. | Thorn of the Black Rose |
| You take the initiative. | Underdark Explorer |
| Goad target creature. / Goad all creatures you don't control. | Disrupt Decorum |
| Whenever an opponent casts a spell / draws a card, (you may) draw a card / create a Treasure token unless that player pays {N}. | Rhystic Study, Mystic Remora, Smothering Tithe |
| Whenever you become the monarch, ... / Whenever an opponent becomes the monarch, ... | |
| Starting with you, each player votes for X or Y. For each X vote, ... / If X gets more votes (or the vote is tied), ... | Tivit, Seller of Secrets; Plea for Power; Capital Punishment |
| Starting with you, each player votes for a nonland permanent you don't control. Exile each permanent with the most votes or tied for most votes. | Council's Judgment |
| Investigate. | |
| Mill N cards. / Target player (or opponent) mills N cards. / Each opponent (or player) mills N cards. | |
| Discard N cards (at random). / Discard your hand. / Target player (or opponent) discards N cards (at random). / Each opponent (or player) discards N cards or their hand. | Mind Rot, Hymn to Tourach |
| Draw N cards, then discard N cards. / Each player discards their hand, then draws N cards. / Each player draws N cards. | Faithless Looting, Wheel of Fortune |
| Target player reveals their hand. You choose a (nonland / noncreature, nonland / ... with mana value N or less) card from it. That player discards that card. | Thoughtseize, Duress |
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
| Exile target monocolored permanent. | Vanishing Verse |
| Look at the top three cards of your library. Put one of them into your hand, put one of them on the bottom of your library, and exile one of them. You may play the exiled card this turn. (with fewer cards, the hand and the bottom come first) | Expressive Iteration |
| Exile target creature. Its controller manifests the top card of their library. | Reality Shift |
| Shuffle your library. As many times as you choose, you may exile the top card of your library. If the total mana value of the cards exiled this way is 13 or less, you may cast any number of spells from among those cards without paying their mana costs. (you are asked after each card, shown the running total; bots stop at 4 cards or total 9) | Dance with Calamity |
| Create a token that's a copy of target creature (you control). / Populate. | Growing Ranks |
| Create a 3/3 ... token, then populate. (the new token may be the one copied; "token with trample, then populate" too) | Horncaller's Chant |
| Create a token that's a copy of another target creature you control(, except it isn't legendary). It gains haste. Sacrifice it at the beginning of the next end step. (also five tokens) | Orthion, Tempestra |
| Target player draws cards equal to half the number of cards in their library and loses half their life. Round up each time. | Peer into the Abyss |
| Whenever equipped creature deals combat damage to a player, that player loses half their life, rounded up. ("that player" is who was hit) | Quietus Spike |
| When this Aura enters, put a +1/+1 counter on enchanted creature. / Have the base power and toughness of other creatures you control become equal to CARDNAME's power and toughness until end of turn. | Seismic Tutelage, Tanazir Quandrix |
| When this creature dies, return it to the battlefield tapped under its owner's control at the beginning of their next upkeep. | Phytotitan |
| You may put a creature card from your hand onto the battlefield. If you do, sacrifice it unless you pay its mana cost reduced by {2}. | Flash |
| Mill four cards, then return a creature card and a land card from your graveyard to your hand / a creature card to the battlefield (tapped). ("Exile this land" as a cost works) | Sudden Reclamation, Tomb Fortress, Port of Karfell |
| When this creature enters, if it's not a token, each opponent creates a token that's a copy of it. The tokens are goaded for the rest of the game. | Life of the Party |
| You lose all but 1 life. / When this creature leaves the battlefield, you gain life equal to the life you lost when it entered. | Soulgorger Orgg |
| Create a token that's a copy of another target creature you control. (not the source itself) | |
| Create a token that's a copy of it, tapped and attacking. (the copy attacks whom the source attacks; it is never declared, so attack triggers don't see it) | |
| Target player loses half their life, rounded up / rounded down. | |
| Double the number of +1/+1 counters on target creature. | |
| When this creature dies, return it to the battlefield (tapped). / ... under its owner's control. (a token is gone for good) | |
| You may put a creature card from your hand onto the battlefield. | |
| Mill three cards, then return a creature card from your graveyard to your hand. (any two effects that each work alone join with ", then") | |
| You gain life equal to the amount of life you lost this turn. | |
| Destroy target permanent. Its controller creates a 3/3 green Beast creature token. / That creature's controller creates ... | Beast Within, Rapid Hybridization, Resculpt |
| Draw two cards and create two Treasure tokens. | Big Score, Seize the Spoils |
| Create a token that's a copy of target creature. If this spell was kicked, create five of those tokens instead. | Rite of Replication |
| For each opponent, create two 3/3 ... tokens with flying that attack that opponent this turn if able. They gain haste until end of turn. Exile them at the beginning of the next end step. | Furygale Flocking |
| Prevent all combat damage that would be dealt to you this turn. For each 1 damage prevented this way, create a 2/1 ... token with flying. | Inkshield |
| CARDNAME deals 4 damage divided as you choose among any number of targets. (a point at a time: the first to a target, the rest to targets or nowhere) | Magma Opus |
| Tap two target permanents. | Magma Opus |
| Exile X target creatures. For each creature exiled this way, its controller creates a 2/2 ... token. | Curse of the Swine |
| Destroy up to X target artifacts and/or enchantments. Create twice X 1/1 ... tokens with "<an ability we understand>". | Pest Infestation |
| Choose any number of target creatures you control. For each of them, create a token that's a copy of that creature, except it has haste. Exile those tokens at the beginning of the next end step. | Twinflame |
| Put N +1/+1 (or -1/-1) counters on target creature / on each creature you control / on it. | |
| This creature enters with N +1/+1 counters on it. | Hydras |
| Target creature gets +N/+N (and gains keywords) / gains keywords until end of turn. | Giant Growth |
| Creatures you control (or your opponents control) get +N/+N (and gain keywords) until end of turn. | |
| Target creature gets +X/+X (-X/-X, +X/+0, ...) until end of turn, for each ... / where X is ... | |
| Target creature becomes a 4/4 Dragon until end of turn. / has base power and toughness 0/1 until end of turn. | |
| Put N <kind> counters on target <permanent>. / Remove N (all) <kind> counters from target <permanent>. / Remove all counters from target <permanent>. | |
| Double the number of +1/+1 counters on each creature you control. | |
| Move a (or all) +1/+1 counter(s) from target creature onto another target creature. | |
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
- **Targets in a list:** "X target creatures" (Curse of the Swine) has exactly X targets, so X is limited to how many
  legal targets there are; "up to X target artifacts and/or enchantments" (Pest Infestation) and "any number of target
  creatures" (Twinflame) may have fewer, or none. Each is one list, and a list whose targets are all gone by the time the
  spell resolves makes it fizzle (a list that never had any still resolves, so "twice X tokens" still happens with no
  targets). "Create twice X ..." is twice the spell's X. A copy "except it has haste" has haste for good, and copies made
  together count as one "one or more creature tokens" event.
- **Tokens for other players:** "Each opponent (or player) creates ..." and "Target opponent creates ...". A token
  with "This creature can't block / attack / attack or block." gets that restriction.
- **Static abilities:** "(Other) (Elf) creatures you control get +1/+1 (and have flying)",
  "Creatures you control have haste" and "Creature tokens you control have haste" (Brudiclad). These apply only
  while their source is on the battlefield.
  - Either can be conditional, written "As long as X, ..." or "... as long as X.", and a creature can buff
    itself ("As long as you control an artifact, this creature gets +1/+1 and has flying."). The buff is checked
    every time power, toughness or keywords are looked at, so it switches on and off as the game changes.
    Conditions: you control a/N or more <type>, you control no <type>, it's your turn, you're the monarch,
    you have no cards in hand, you have N or more cards in hand, plus the graveyard, life, lands and cast
    conditions listed under triggers. A line with any other condition is ignored.
  - Who it affects can be a color ("Other red creatures you control"), a tribe in the plural ("Spirits you control"),
    or attackers only ("Attacking Pests you control"). Bonuses can scale: "This creature gets +1/+0 for each artifact
    you control", "... for each creature card in your graveyard", "+2/+2 for each Aura attached to it", and on an Aura
    "Enchanted creature gets +1/+1 for each Aura you control that's attached to a creature". "Enchanted creature gets
    +1/+1 and is goaded" goads it for as long as the Aura stays (the Aura's controller is the goader).
    "White creatures get +1/+1" (Crusade) affects every player's creatures. An Aura can give keywords, including
    "annihilator 2" (Eldrazi Conscription: when it attacks, the defending player sacrifices two permanents), a quoted
    ability (Fallen Ideal) and an extra creature type (Angelic Destiny: "is an Angel in addition"; lords see it).
    "As this enters, choose a creature type" (Patchwork Banner) names the most common type in your cards unless you
    choose; "Creatures you control of the chosen type get +1/+1" follows. "... for each time you've cast your
    commander from the command zone" scales a tribe (Vanguard of the Restless, which also returns from the
    graveyard when a Spirit enters if you pay {2}{W}). Veyran makes your instant and sorcery triggers happen twice.
  - Counters: "that many plus one +1/+1 counters" replacements can cover other creatures (Benevolent Hydra), any permanent
    (Kami of Whispered Hopes) or artifacts and creatures (Ozolith). "Enters with twice X" (Primo), "escapes with two
    +1/+1 counters" (Woe Strider), a copy "except it enters with X additional counters" (Altered Ego) and "enters with an
    additional counter for each creature that died this turn" (Gorma) are supported, as are "as long as it has ten or more
    counters" (Primordial Hydra) and "creatures you control with counters on them" (Nev). A creature that taps for as
    much mana as its power (Kami), a mana ability that removes a counter once each turn (Mana Bloom), "double the
    counters on this creature" and a spell that costs {1} less for each counter on a permanent (Zimone) work too.
  - Counters on cards: "Move all counters" and "Remove all counters ... draw a card for each" (Nexus Mentality, whose
    "choose both" needs a commander), "Put a +1/+1 counter on each of up to X target creatures" (Silkguard, which asks
    for X before the targets), a counter for each player's creature (Nils, whose attack tax makes each counter cost {1}),
    vow counters that keep a creature from attacking the caster (Promise of Loyalty), "each opponent loses all counters"
    (Final Act), and Zimone's Hypothesis (odd or even).
  - Shadrix Silverquill chooses two modes for two different players, or none. Rousing Refrain adds {R} for each card in an
    opponent's hand, keeps the mana until end of turn and suspends itself; Suspend N—{cost} exiles a card from your hand
    with time counters, one comes off each upkeep, and the last one casts it for free.
- **Current power, toughness and keywords:** printed values plus counters, static abilities and
  "until end of turn" effects. They count everywhere: combat, damage, targeting (granted hexproof),
  destroy (granted indestructible), state checks, and the labels players see ("Bear 4/4").
  "Until end of turn" effects wear off in the cleanup step. An effect on "creatures you control"
  affects only the creatures there when it resolves. `Game.power`, `Game.toughness` and
  `Game.has_keyword` are the way to read them.
- **Tokens:** they enter with summoning sickness, and "dies" triggers still happen when they leave.
  After leaving the battlefield they stop existing, so they never reach the graveyard or exile.
  Treasure is a mana source that's sacrificed when used, and it's spent after lands and other sources.
  "Create a 0/0 Fractal token. Put X +1/+1 counters on it." (or ", then put three ... on it") gives the new token the
  counters. Clue and Food work through their activated abilities. A token with a quoted ability
  ("When this token dies, you gain 1 life.") works when that ability is understood; otherwise the card isn't.
  "Put X +1/+1 counters on it, where X is the amount of mana spent to cast that spell." (Deekah) reads the mana paid
  for the spell that set off the magecraft trigger; a copy of a spell was never cast, so its Fractal gets none.
  Brudiclad's "Then you may choose a token you control. If you do, each other token you control becomes a copy of
  that token until end of turn." asks which token (or none); the others keep their counters and damage and get
  their own card back at cleanup.
- **Lands:**
  - Entering tapped: "This land enters tapped" (taplands, gain-lands, temples, triomes), and the conditional
    kinds: checklands ("unless you control an Island or a Swamp"; any land with that land type counts),
    fastlands ("two or fewer other lands"), slowlands ("two or more other lands"), and bond lands
    ("unless you have two or more opponents", so untapped in a 3+ player game), plus "unless you control two or more
    basic lands", "unless you control three or more other Islands", "unless your opponents control eight or more lands"
    (their lands added together), and the Snarls ("you may reveal a Mountain or Plains card from your hand"; you are
    asked, and it enters tapped if you decline or have no such card). Fetched and reanimated lands follow the same rules.
    More conditions: "unless you control a planeswalker / a basic land / a legendary creature / a Mount or Vehicle / a
    Mountain" (one type of land works for any of the five), "unless a player has 13 or less life" (any player, you
    included), "If you control two or more other lands, this land enters tapped", "If you were the starting player, this
    land enters tapped" (the game remembers who started), and a reveal of any one creature type ("you may reveal an
    Elemental card from your hand", with the Snarl wording kept for two land types).
  - "This land enters tapped with two charge (depletion, ...) counters on it": tapped, with the counters.
  - "This land enters tapped. As it enters, choose a color.": you choose one of the five as it enters and the land
    remembers it. Mana from "the chosen color" is not built yet.
  - Karoos: "When this land enters, sacrifice it unless you return an untapped Mountain you control to its owner's
    hand." You are asked which land to return (or to sacrifice it); with no untapped land of the type it is sacrificed.
  - "At the beginning of your upkeep, if this land is tapped, put a storage counter on it" (the condition "if this
    land is tapped" works on any trigger).
  - Shocklands: you may pay 2 life or the land enters tapped. Life you can't spare (2 or less) isn't offered.
  - Painlands and Talismans: 1 damage when tapped for a colored mana. Colorless mana from them is free, and
    the payer picks painless sources first. Talismans make their colors now (they used to make colorless only).
  - Command Tower: only makes your commander's colors, whatever the card data lists.
  - Study Hall and Path of Ancestry: mana abilities with a "When that mana is spent to cast ..., scry" rider. The
    rider triggers when the auto-payer tapped the land for that ability while paying for the right spell: your
    commander (Study Hall scries the number of times it has been cast from the command zone, counting this cast) or
    a creature spell sharing a creature type with your commander (Path of Ancestry scries 1). The trigger goes on
    the stack above the spell. Study Hall tapped for its plain {C} spends no such mana, so it doesn't trigger then.
  - Mana with strings attached: "Spend this mana only to cast spells with mana value 5 or greater or spells with {X}" (Troyan)
    and "only on costs that contain {X}" (Elementalist's Palette) are only used for what they may pay for; "{T}, Sacrifice a
    Food: Add one mana of any color" (Gilded Goose, one Food per Goose) and "{T}, Mill a card: Add {C}" (Millikin, needs a
    library) pay their extra cost when the mana is spent; "Add one mana ... for each charge counter" (Astral Cornucopia,
    Palette) makes one mana per counter (the mana of one tap may be spent as different colors).
  - Exile and graveyard effects: Serra Paragon (once each turn, play a land or cast a permanent spell of mana value 3 or
    less from your graveyard; that permanent is exiled, and you gain 2 life, if it goes to the graveyard). Surge to
    Victory (exile an instant or sorcery from your graveyard, creatures get +X/+0, and each creature that connects this
    turn lets you cast a free copy of it). Fateful Tempest (a past-or-present vote: mill and damage, or exile cards you
    may play until your next turn ends). Abstract Performance (two piles of four; an opponent sends one to your
    graveyard, you may cast a spell from the other for free and take the rest).
  - Ancient Tomb ("{T}: Add {C}{C}. ... deals 2 damage to you."): two mana from one tap, and the damage is dealt
    once per tap however much of the mana is used. Bouncelands ("{T}: Add {B}{G}.") make both colors the same way.
  - City of Brass ("Whenever this land becomes tapped, it deals 1 damage to you."): hurts every time it's tapped
    for mana. Mana Confluence ("{T}, Pay 1 life: Add one mana of any color."): pays life (not damage), and is not
    used when you can't afford it. The payer picks painless sources first.
  - Bouncelands: "enters tapped" plus "When this land enters, return a land you control to its owner's hand."
    You choose the land and it can be itself; bots return the newest land.
  - **Prepare cards** (Secrets of Strixhaven, e.g. Eiganjo Dynastorian // Replenish): a creature whose card also has a spell half. "This creature enters prepared" and "... becomes prepared" (from any trigger the engine fires) make it prepared; while it is, you get a "Cast prepared: <spell>" action (with the spell's own timing and cost). It casts a copy of the spell, which ends instead of going to a graveyard, and the creature stops being prepared. The report checks both halves. "Target creature becomes prepared / unprepared" (Skycoach Waypoint, Hexhaven Dueling Arena's "creature that attacked this turn"), "each creature you control becomes prepared" (Codie) and the conditions "if this creature isn't prepared", "three or more artifact and/or creature cards in your graveyard", "a player has one or fewer cards in hand" and "an opponent has more cards in hand than you" work. Also: "choose up to one" modes (Biblioplex Tomekeeper), "Then if <condition>, <effect>" sentences, exiling cards from your graveyard ("you may exile eight cards ... If you do, this creature becomes prepared", and "Exile a creature card from your graveyard" as a cost), "Tap two untapped creatures you control" as a cost, "When X and whenever Y" as two triggers, and "Whenever one or more tokens you control enter". The spell halves of Carnivorous Cultivator, Eccentric Pestfinder, Eiganjo Dynastorian, Inspired Skypainter, Lorehold Archivist, Pigment Wrangler, Skycoach Conductor, Striding Shotcaller, Ursine Guide and Vastlands Scavenger work. The three cards whose text the issue cut off work, from their full Oracle text: Emeritus of Truce ("Then if an opponent controls more creatures than you, this creature becomes prepared", counted after the token it just made), Stensian Sanguinist ("Whenever you attack" is the same trigger as "whenever one or more creatures you control attack"; "Whenever that creature deals combat damage to a player this combat" is kept on the combat, so it ends with it) and Yavimaya Bloomsage ("if that creature has power 7 or greater" looks at the creature that just got the counter). Static lines with a condition also work for the rest of the report: Threshold ("Threshold — This creature gets +1/+1 as long as there are seven or more cards in your graveyard", Theorix Metamage and Void Extrapolator; an ability word in front of a static line is ignored, as it already was for triggers) and "As long as an opponent was dealt noncombat damage this turn" (Whiplash Wordsmith; combat damage and life loss do not count, and it ends with the turn). Alchemy "conjure" works for "Conjure a card named X onto the battlefield" (Galathul Galecaller, Ursine Guide, Crescendo Conductor): `load_deck` finds the names in the deck's text, looks them up in the same card source and keeps them in `Deck.conjured`, so nothing is fetched during a game; a name the source does not know is left out and conjuring it does nothing. A conjured card is marked `conjured`, which is all "a spell that isn't from your starting deck" checks, and "Whenever you conjure one or more cards" fires once per conjure. Conjuring into a hand or a graveyard is not built. "Each creature you control with a +1/+1 counter on it has vigilance" (Vigorbloom Vanguard; only that counter counts, and only your own creatures) and the mana restriction "This mana can't be spent to cast spells from your hand" (Heartwood Crafter; the mana still pays for abilities and for spells cast from the command zone or elsewhere) work. A spell counts as cast from hand when that exact card object is in the hand as it is paid for, so a second identical card in hand can make a flashback cast count as from hand. The two mana effects that last for a turn work too. Pyre Rhymer's Molten Tide makes each Mountain (any land with the Mountain subtype) you tap this turn add an additional {R}. Yavimaya Bloomsage's Channel lets you pay 1 life for {C} any time this turn; since mana is paid automatically, it is used only when your other mana cannot cover the cost, it can never pay you down to 0 life, and at most 10 life-paid {C} are offered for one payment. With these, all 70 prepare cards are fully playable in the report.
  - Abilities from the hand: "{U/R}{U/R}, Discard this card: Create a Treasure token." (Magma Opus) is offered as
    "Activate from hand: <card>" at instant speed; the card is discarded as the cost and the effect goes on the stack.
  - More activated abilities (#73): costs that exile this permanent ("Exile this artifact", Perpetual Timepiece) or return it
    to its owner's hand (Rootha) are paid before the ability goes on the stack, so it outlives the source. An ability that
    says "Return this card from your graveyard to the battlefield tapped" (Teacher's Pest) is offered as "Activate from
    graveyard: <card>". "Pay life equal to the number of colors in your commanders' color identity" (War Room) works.
    Alchemist's Refuge lets you cast every spell this turn at instant speed, Arcane Lighthouse takes hexproof and shroud
    off your opponents' creatures until end of turn, and Restless Spire's creature has first strike only during your turn.
    Also: "noncreature artifact or noncreature enchantment" and "noncreature, nonland permanent" as target kinds, "creatures
    named CARDNAME can't be blocked", "Spirits you control gain ... until end of turn", "Exile enchanted creature", a
    counter on each green creature that entered this turn (Oran-Rief), a land fetched untapped when you control four lands
    (Fabled Passage), a token if the exiled card is a creature (Feral Appetite), "draw two cards instead" with a condition
    (Zimone) and Quintorius's "draw two cards, then mill a card". Still unsupported from #73: mana abilities that spend
    other resources or restrict what the mana buys, Level up, Priest of Forgotten Gods and Currency Converter.
  - Rules text of #81: "Counter target spell unless its controller pays {N}" (the controller is asked), "Destroy target artifact,
    enchantment, or planeswalker", "Return six target nonland permanents ...", "target creature with mana value X",
    "gets +X/+X and gains hexproof and indestructible", "Then it fights up to one target creature", "Proliferate X times",
    Dig Through Time's look-seven-take-two, Commander's Insight, Culling Ritual (mana for each permanent destroyed), Mana Geyser,
    Biomass Mutation, Wave of Reckoning, Winds of Rath ("that aren't enchanted"), Volcanic Torrent (creatures and planeswalkers),
    damage to "each of one or two targets", draw-then-discard, mill-then-return, "You may sacrifice a permanent. If you do, draw two
    cards", "sacrifice X creatures" as an additional cost (Immoral Bargain), X limited by the number of players (Open the Way),
    "Arcane Denial"'s draws at the next upkeep, Flashback with a life payment, casting from the graveyard "by paying {2}{W}",
    cost reductions ("costs {2} less if you gained life this turn", "{X} less where X is the total power of your creatures",
    Aura spells, spells that target a creature, affinity for Auras), Pest Rescuer's extra life, haste while an opponent is at 10 or
    less life, and combat limits: Ghostly Prison's tax per attacker, "Inklings can't attack you", creatures enchanted by your Auras
    can't attack you, "can block only creatures with flying" and "creatures with power less than this creature's power can't block it".
    Not built (see #81): the Class level lines, Anger and Cursed Mirror, Drumbellower, Galazeth Prismari and Goldspan Dragon (they give
    mana abilities to other permanents), Harmonic Prodigy, Flickering Ward, spell mastery, and Quandrix Command's shuffle-back mode.
  - Trigger effects of #80: "sacrifice two lands", a search whose "it" is the card found (Bitterthorn), "Whenever one or more
    creatures die / enter" (once for everything that happens together, with "with mana value 3 or less" and "only once each turn"),
    "its controller loses 2 life and you gain 2 life" (Parasitic Impetus), "you may attach this Aura to that creature" and
    "if that enchantment is an Aura, you may attach it to the token", "tap up to one target creature and goad it", "return target
    nonland permanent card with mana value 3 or less", "exile target noncreature, nonland card", "exile up to one target nonland,
    nontoken permanent you don't control", a token copy of this creature, "create half X Food tokens, rounded up", "When you cast
    this spell, you gain half X life and draw half X cards", tapped Treasures equal to its power, "gets +X/+0 where X is that spell's
    mana value", "creatures you control gain flying and get +X/+X", "You may pay {2}. If you do, ..." (including a target), "pay {1}
    and discard a card", "remove a counter from it. If you do, draw a card", "It has "Sacrifice this token: Add {C}."", populate with
    a hasty token that is sacrificed at the end step, "put into a graveyard from the battlefield", "becomes the target of a spell",
    decayed, "return this card from your graveyard to your hand" at upkeep (Squee), "exile that card from your graveyard" after a
    discard, and "mill a card, then exile a card from your graveyard at random. You may play the exiled card this turn".
    Not built (see #80): phasing (Guardian of Faith), Hateful Eidolon, Laelia, Pearl-Ear's modified permanents, Unbound Flourishing,
    Firemane Commando, Forgotten Ancient, Fractal Harness (an ETB trigger gets no X), and two of Killian's and Conspiracy Theorist's lines.
  - Manifest (Reality Shift): the top card of the library enters face down as a 2/2 creature with no abilities. A creature
    card can be turned face up at any time you have priority for its mana cost ("Turn face up: ..."; not a stack
    action). It goes to the graveyard as the real card, and only its controller is shown what it is
    (`face_down_as` in the board).
  - Cycling {N}: an ability you can use from your hand at instant speed. Pay, discard the card, draw.
    Basic landcycling {N} and Plainscycling / Islandcycling / Swampcycling / Mountaincycling / Forestcycling {N}
    fetch a land to your hand instead (basic land, or any land with that type). The cost can be mana or "Pay N life"
    (offered only if it leaves you above 0 life).
  - Mana abilities that end with "Activate only if <condition>." (Temple of the False God, Mox Jasper) make mana only
    while the condition holds, checked each time you pay. "{1}, {T}: Add one mana of any color." (Hall of Oracles) works
    like a Signet. A filter or Signet can no longer tap for mana to pay for its own cost (a land with a plain
    {T}: Add {C} could before).
  - "{T}: Add {G} for each creature you control" (Gaea's Cradle, Elvish Archdruid) and "{2}, {T}: Add {B} for each Swamp
    you control" (Cabal Coffers): the amount is worked out each time you pay. Coffers' {2} is paid first, so it is only
    worth it with enough Swamps (the payment picks the first mana that fits).
  - Filter lands ("{W/B}, {T}: Add {W}{W}, {W}{B}, or {B}{B}."): paid like a Signet, so one Swamp becomes two white,
    two black or one of each. A filter land can't pay for its own ability.
  - Exotic Orchard ("any color that a land an opponent controls could produce") and Reflecting Pool ("any type that
    a land you control could produce", colorless included): they read the other lands' mana, and a land of this
    kind adds nothing to another's, so two never feed each other. With nothing to read they make no mana.
  - Pathways (modal double-faced lands): the card shows both faces' names, and "Play land" is offered once for
    each face. The face you play is the permanent and makes only its own color. This applies to a land back face
    of any modal double-faced card; other double-faced cards use their front face only.
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
    Exiled, it isn't returned. Other Aura returns on "When enchanted creature dies" work too: "return it to the
    battlefield under your control" (Changing Loyalty), "return this card from your graveyard to the battlefield"
    (Screams from Within) and "... at the beginning of the next end step" (Ghoulish Impetus) with you choosing what
    it enchants (it stays in the graveyard if nothing is legal), and Gift of Immortality's creature-then-Aura pair.
  - **Granting abilities:** "Enchanted (or equipped) creature has "{T}: Draw a card."" lets that creature activate it
    (a summoning-sick one can't use {T}). "Enchanted land has "{T}: Add {G}{G}."" makes the land tap for that mana
    instead of its own single mana. A quoted ability that isn't understood leaves the card unsupported.
  - **Reconfigure {N}:** an Equipment creature has two abilities at sorcery speed: attach to another creature you
    control (offered only if you have one), and "(unattach)" (offered only while attached). While attached it is
    not a creature; when unattached, when its creature leaves, or when it leaves the battlefield it is its real
    card again.
  - **"It" on the host:** "Whenever equipped (enchanted) creature attacks (deals combat damage to a player), put a
    +1/+1 counter on it" means the equipped creature. In "Whenever equipped creature dies, ... it" the creature is
    gone, so that line isn't understood.
  - **Not built:** Fortify and Fortifications, "Whenever this Equipment becomes attached", Wild
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
- **Library and mana tricks:** Chaos Warp ("The owner of target permanent shuffles it into their library, then reveals the top
  card. If it's a permanent card, they put it onto the battlefield": the owner shuffles and reveals, a token just
  vanishes, an Aura stays on top), Sensei's Divining Top ("{T}: Draw a card, then put this artifact on top of its
  owner's library"), and Mana Drain (the {C} equal to the countered spell's mana value, X included, arrives at the
  beginning of your next main phase and is lost at the end of it).
- **Keywords:**
  - **Prowess:** whenever you cast a noncreature spell, +1/+1 until end of turn.
  - **Shadow:** it can block or be blocked only by creatures with shadow. **Skulk:** it can't be blocked by creatures
    with greater power. **Devoid** is accepted: the card data already has no color.
  - **Living weapon:** a 0/0 black Phyrexian Germ token is created and the Equipment attached to it when it enters.
  - **Echo {cost}:** at your next upkeep after it enters you pay once (you are asked, if you can) or sacrifice it.
  - **Delve:** exiling cards from your graveyard pays for generic mana. The engine exiles as few as will do, and you
    choose which. **Cascade:** a trigger above the spell exiles cards from your library until a nonland card that costs
    less; you may cast it for free, and the rest go to the bottom in a random order (a cascade spell's X counts as 0 on
    the card but its chosen X counts for the comparison).
  - **Devour N:** as it enters you may sacrifice any number of other creatures (asked one at a time, then Done); it
    gets N +1/+1 counters for each. The bot never devours.
  - **Replicate {cost}:** you choose how many times to pay when you cast (any affordable number); a trigger above the
    spell makes that many copies, each with new targets. A copy of an Aura spell becomes a token Aura. **Storm** (a copy
    for each spell cast before it this turn, by anyone) and **Gravestorm** (a copy for each permanent put into a
    graveyard this turn) use the same trigger.
  - **Ascend:** with ten or more permanents you get the city's blessing for the rest of the game, if you control a
    permanent with Ascend ("as long as you have the city's blessing" works in static abilities).
  - **Affinity for <type>s:** costs {1} less for each of that type you control.
- **Reanimation Auras** (Animate Dead): "Enchant creature card in a graveyard" is cast on a creature card in any
  graveyard; when it resolves the creature comes back under your control and the Aura is attached to it, and if the
  Aura leaves the battlefield the creature is sacrificed. The tapped version (Dance of the Dead) is understood
  too, but its other lines are not. Necromancy (it becomes an Aura as it enters) is not built.
- **Kaalia of the Vast:** "Whenever this creature attacks an opponent, you may put an Angel, Demon, or Dragon creature
  card from your hand onto the battlefield tapped and attacking that opponent." It attacks the same player and
  triggers nothing for attacking. A legendary card's short name ("Kaalia", "Edgar") is read as the card itself.
- **Cumulative upkeep {1}** (Mystic Remora): at your upkeep it gets an age counter and you pay the cost once for each
  counter, or sacrifice it. You are asked if you can pay. Mana costs only; "Cumulative upkeep—Pay 1 life" is not built.
- **Reordering the library:** "Look at the top three cards of your library, then put them back in any order. You may
  shuffle." (Ponder, Sensei's Divining Top's first ability) and "Draw three cards, then put two cards from your hand on
  top of your library in any order." (Brainstorm). You choose the order; the first card you pick goes on top.
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
    last controller; an indestructible survivor gives nothing. "Then create a 3/2 ... token for each nontoken creature
    you controlled that was destroyed this way." (Ceaseless Conflict) pays only the caster, and "Each player creates a
    0/0 ... Fractal creature token and puts a number of +1/+1 counters on it equal to the total power of the creatures
    they controlled that were exiled this way." (Oversimplify) gives everyone one token, as big as what they lost (as
    it last was); with no counters it dies at once.
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
  | Whenever an opponent searches their library, ... | Ob Nixilis, Unshackled (the event; its effect is not built yet) |
  | Whenever a Pest (Elf, token, creature token) you control dies / another Elf you control enters, ... | |
  | Whenever (another) creature (permanent) you control leaves the battlefield, ... | |
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
  | Whenever a creature (a permanent) you control becomes tapped, ... (attacking, tapping for mana or as a cost, or a tap effect; not entering tapped) | Quest for Renewal (whose creatures also untap in each other player's untap step while it has four quest counters) |
  | Whenever you cycle a card (another card), ... / Whenever you cycle or discard a card, ... | Drannith Healer, Pitiless Vizier |
  | Whenever you scry, ... / Whenever you surveil, ... / Whenever you scry or surveil, ... (scry 0 and surveil 0 are no event) | Denzilore Fatehold, Nimrodel Watcher |
  | Whenever you attack with a creature alone, ... (also "a creature you control attacks alone"; "it" is the attacker; the Exalted keyword) | Black Panther, Aven Squire |
  | Whenever one or more creatures you control attack, ... (once) | |
  | Whenever an opponent attacks with creatures, if two or more of those creatures are attacking you and/or planeswalkers you control, ... | Mangara |
  | Whenever a creature enters under an opponent's control, ... (or "a creature an opponent controls enters"; "you may have that player lose 1 life") | Blood Seeker |
  | Whenever a creature (with power 4 or greater / toughness 4 or greater / power 2 or less / with flying / with a +1/+1 counter on it) you control enters, dies or attacks, ... | Kiora, Kheru Bloodsucker, Raid Bombardment ("the player or planeswalker that creature is attacking"), Skyclave Shadowcat |
  | Whenever you cast a spell from your graveyard / from anywhere other than your hand, ... (and "a player casts a spell from their graveyard") | |
  | Whenever you cast a multicolored spell, ... ("the number of colors that spell is" is an amount) | Tome of the Guildpact, Mana Cannons |
  | Whenever a player casts a spell, that player gains X life, where X is the number of cards in all graveyards with the same name as that spell. | Aven Shrine |
  | Whenever a creature card is put into your graveyard from anywhere, ... (dying, discarding, milling, cycling and spells all count; tokens are not cards) | |
  | Whenever you expend 4, ... (as the mana you have spent on spells this turn reaches 4) | |
  | At the beginning of your draw step, ... ("draw an additional card", "two additional cards", and "remove two hour counters" work) | Well of Ideas, Midnight Oil |
  | At the beginning of each other player's draw step, that player draws an additional card. | Well of Ideas |
  | At the beginning of each opponent's upkeep / each opponent's end step / an opponent's end step, ... ("that player" is whose turn it is; "if that player didn't cast a creature spell this turn"; damage equal to the cards in their hand, or minus 4) | Predatory Advantage, Price of Knowledge, Viseling |
  | "Power and toughness are each equal to the number of cards in your hand" is a base size; "Players have no maximum hand size" and "Your maximum hand size is equal to the number of hour counters on this enchantment" decide who discards at cleanup. | Overbeing of Myth, Price of Knowledge, Midnight Oil |
  | Whenever you cast or copy an instant or sorcery spell, ... (Magecraft) | Archmage Emeritus |
  | Whenever you cast an instant or sorcery spell with mana value 5 or greater (from your hand), ... | Dirgur Focusmage |
  | Whenever one or more creatures (creature tokens) you control deal combat damage to a player, ... (once per player hit) | Striding Shotcaller |
  | Whenever you gain life for the first time each turn, ... | Leech Collector |
  | Whenever an opponent draws their second card each turn, ... | Faerie Mastermind |
  | Whenever you cast your first / second / third spell each turn, ... (and an opponent's "their second spell") | Monologue Tax |
  | At the beginning of your first / second main phase, ... | Scathing Shadelock |
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
    the monarch", "if you have no cards in hand", "if you gained 2 or more life this turn", "if two or more creatures
    died this turn" (any player's), "if there are three or more creature cards in your graveyard", "if a player has one
    or fewer cards in hand", "if an opponent has more cards in hand than you", "if this creature isn't prepared", "if
    this land is tapped", "if you control no other creatures" (the source doesn't count itself), "if a modified
    creature died under your control this turn" (a creature with counters, or with Equipment or an Aura of yours on it),
    and "if two or more of those creatures are attacking you and/or planeswalkers you control". A trigger with any
    other "if" clause is ignored. Not built: "a spell with the same name as ..." and the wording of Tomik's trigger.
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
  | Remove a counter from this (+1/+1 or a named one) | "{2}{G}, Remove a +1/+1 counter from this creature: Destroy target artifact or enchantment." |
  | Sacrifice a Food / Treasure / Clue | "{1}, Sacrifice a Food: Target creature gains indestructible until end of turn. Tap it." |

  - They can be activated whenever you have priority, unless they say "Activate only as a sorcery".
    "Activate only once each turn" is respected.
    "Activate only if <condition>" (and "... as a sorcery and only if ...") uses the same conditions as triggers,
    plus "you control two or more white permanents". "Target creature can't be blocked this turn" is understood.
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

The report looks the deck up in Scryfall's bulk data (downloaded to `.cache/oracle_bulk.json` on first use) and prints:
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
| `--timer SECONDS` | a clock on every decision: when it runs out, a bot answers for the player (default: no limit) |
| `--password TEXT` | players and spectators must give it to join (see below) |
| `--cache FILE` | where fetched cards are saved (default `.cache/cards.json`) |
| `--no-check` | accept decks that aren't legal Commander decks |

Each human sends their decklist when they connect. The server fetches the cards, checks the deck, and either
seats the player or explains why not (wrong size, a card outside the commander's colors, an unknown card, a name
already in use), leaving the seat open. If a human disconnects during the game, a bot takes over their seat until
they come back: the server keeps listening, and connecting again with the same name (no deck needed) gives them
their seat back. The welcome says `rejoined`, the seats are introduced again, and the board arrives with their next
decision. A connection still open under that name is dropped, since it may be dead without the server knowing; there
is no password yet, so anyone who knows a player's name can take their seat. Someone else is told the game has started.

**Password.** With `--password`, every hello (a player's, a rejoin, a spectator's) must carry `"password"`; otherwise
the connection gets `Wrong password.` and is dropped, and a seat stays open. This also stops someone who only knows a
player's name from taking their seat on a rejoin. The password is sent as plain text over an unencrypted connection, so it
keeps out the curious, not someone who can read the network traffic.

**Spectators.** A hello with `"spectate": true` (no deck needed; `--name` is optional on the clients) watches the game
instead of playing: the welcome is `{"type": "welcome", "spectator": true}`, and from then on they are sent every public
event and the board (`state`, with `"you": -1` and an empty `hand`) whenever it changes. They can join in the lobby or
during the game (they are told who sits where and the current board first), and are never sent a hand, a card drawn
privately, an opening hand or what a scry or a search found. They are never asked to choose anything.

With `--timer`, each decision is sent with its time limit (`"seconds"` in the `choose` message). A player who hasn't
answered by then gets a `timed_out` event saying what the bot chose for them, and keeps their seat for the next
decision; the terminal client shows the limit in the prompt's hint and the browser client counts it down. An answer
that arrives late is refused, like any answer to a question that is no longer open.

**Client** (`python -m infernal_machine.client --name Alice --deck deck.txt [--host H] [--port P]`):
- Events are printed as sentences ("Bot 1 casts Sol Ring.", "You lose 3 life (25).").
- When you have a decision, the board is shown and the options are numbered. Type a number.
  At a priority prompt, Enter passes. Type `b` to show the board again.
- `--spectate` (no `--name` or `--deck` needed) watches a table instead: the events are printed, and the board comes
  with each turn.
- `--password TEXT` joins a table that has one.
- Prompts where passing is your only option are answered for you.
- Your hand is shown to you only. Opponents' hands and libraries appear as counts.
- On a table with `--timer`, the hint shows the seconds you have; when they run out a bot answers and you are told
  what it chose.

**Browser client** (`python -m infernal_machine.web --name Alice --deck deck.txt [--host H] [--port P] [--listen 8765] [--no-browser]`):
- Joins the table like the terminal client, then serves a page at `http://127.0.0.1:8765/` (`--listen` picks the
  port) and opens it in your browser (`--no-browser` just prints the address). Nothing beyond the standard library.
- The page shows each seat's life, hand and library counts, graveyard and exile (hover for the cards), command zone
  and commander damage, the permanents as cards (tapped ones tilt, summoning-sick ones are marked, with counters,
  damage and attachments) and the lands as counted chips; the stack; your hand; the log of events as sentences.
  Your seat is at the bottom. It follows your light or dark theme and fits a phone.
- A decision shows its prompt with one button per option (Pass stands out) and, on a table with `--timer`, a
  countdown. The page asks the client for changes
  (`GET /state?since=N`, answered when something changed) and answers with `POST /choose` (`{"id", "choice"}`).
- Prompts where passing is your only option are answered for you, as in the terminal client.
- Dropping and reconnecting works the same way: run it again with the same name.
- `--spectate` and `--password` work as in the terminal client; a spectator's page shows the board and the log with
  no hand and no buttons.

All three can also be run as `infernal-server`, `infernal-client` and `infernal-web` after `pip install .`.

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
| server -> client | `{"type": "welcome", "seat": 0}` (`"rejoined": true` when a dropped player took their seat back) |
| server -> client | `{"type": "event", ...}` (no reply) |
| server -> client | `{"type": "event", "event": "state", ...}`: the whole board, sent before each of your decisions. It has `turn`, `step`, `active`, `you`, your `hand`, the `stack`, and for each seat its life, hand and library counts, graveyard, exile, command zone (with commander tax), commander damage, and battlefield (with current power and toughness, counters and attachments) |
| server -> client | `{"type": "choose", "id": 1, "prompt": "...", "options": ["Keep", "Mulligan"]}` (`"seconds": 60` when the table has a timer) |
| server -> client | `{"type": "event", "event": "timed_out", "prompt": "...", "choice": "Pass"}`: the clock ran out and a bot chose for you |
| client -> server | `{"type": "response", "id": 1, "choice": 0}` |
| server -> client | `{"type": "error", "message": "..."}` (after bad input the prompt is sent again) |

You can connect by hand with `nc localhost 4000`.

## Tests

```
python3 -m unittest discover -s tests -t .
```
