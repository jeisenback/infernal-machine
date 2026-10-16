# Simulation and tuning tools

Reference for the tools that analyze a deck. For a guided tour, start with [Tune a deck](tune-a-deck.md).

## Analyzing a deck

```
python -m infernal_machine.analyze DECKLIST [OPPONENT ...] [--games 40] [--sim-games 500] [--turns 8] [--seed 0] [--pod 2]
                                   [--workers N] [--try "Card Name"]... [--skip tuning,matchups] [--output FILE]
```

One command for everything below: it runs the Bracket check, the mana base, the goldfish, the tuning report and, when opponents are
given, the matchups, and prints one markdown report (`--output` also writes it to a file). Each part is the tool of its own section
with the options shared across them given once: `--games` is matchup games per opponent, `--sim-games` the games for the goldfish and
the tuning report. The cards the engine can't play come first, since they qualify everything under them, and each fact is said once (the
tuning report's own Bracket, mana base and unreadable-card lines, and the matchup report's sentence about the focus deck, are left out
because the report already has them). A Standard deck has no Bracket part; without opponents there is no matchup part; `--skip` leaves
out parts (`bracket`, `manabase`, `goldfish`, `tuning`, `matchups`). The end of the report lists what was left out and how long each part
took; progress goes to stderr, so a long run shows it is alive. The matchup games are the slow part (roughly a few seconds a game); the
goldfish and tuning take a minute or so at the defaults.

## Commander Brackets

```
python -m infernal_machine.brackets DECKLIST
```

`brackets.analyze(deck)` reads the hard limits of the Commander Brackets (1 Exhibition, 2 Core, 3 Upgraded, 4 Optimized, 5 cEDH) off
a deck's cards and returns the lowest bracket it can be played at (`floor`): the Game Changers in it (Scryfall's `game_changer` flag,
so the list follows Scryfall; none below Bracket 3, up to three in Bracket 3), mass land denial (found by its Oracle text: destroys,
exiles or returns all lands, or makes each player sacrifice four or more; not below Bracket 4), and its extra-turn cards, which are
listed but not counted against it. It cannot see two-card infinite combos or how the deck is played, and it cannot tell Bracket 1
from 2 or 4 from 5, so the floor is a first check before choosing opponents, not a rating.

- **Tuning:** the report starts with the deck's Bracket line, and a `--try` card that is a Game Changer, is mass land denial, or
  takes a Game Changer out says what the swap does to the floor.
- **Matchups:** the report shows the focus deck's floor and each opponent's, and warns when an opponent can only be played at a
  higher bracket than the focus deck, because those win rates compare unlike decks. `--max-bracket N` leaves such opponents out.
- Decks without a commander (Standard) have no bracket. `.cache/oracle_bulk.json` is downloaded again on first use, because cards
  gained the flag; `.cache/cards.json` is fetched again too (see [The card caches](cards-and-decks.md#the-card-caches)).

## Simulating a deck

```
python -m infernal_machine.simulate DECKLIST [--games 1000] [--turns 8] [--seed 0] [--play] [--commander-dies TURN]
```

`simulate(deck, games, turns, seed, on_the_play, free_mulligan)` in `simulate.py` plays the deck alone with the bot's
mulligan rules and reports, per turn: how often every land drop was made, mana available and spent, how often a spell the
lands' count could pay for was stuck on colors, and total combat damage dealt so far. Per card it reports how often the
card was seen and cast, how often it was cast once seen, the average turn it was cast, and how long it sat in hand. Sorted
worst-first, the card table points at cards that are too expensive, in the wrong colors, or never come together.

It models mana and bodies, not rules text: a spell is cast when its cost can be paid (by `mana.pay`, color by color),
mana rocks and mana creatures are sources, creatures attack unblocked from the turn after they enter (haste: at once),
X is 0, and conditional "enters tapped" lands and shocklands count as untapped. A land
that fetches a basic land (Evolving Wilds, Terramorphic Expanse, Fabled Passage) is cracked when played: it takes the basic
that adds a color the hand wants, removes it from the library, and enters tapped (Fabled Passage untaps with four lands).
A commander is cast from the command zone at its mana value plus {2} for each earlier cast (CR 903.8), and partners are taxed
separately. With `--commander-dies N` (`commander_dies_on=N`) every commander on the battlefield goes back to the command zone at
the start of turn N, taking its body and any mana it made with it, and the report adds a "commander recast" section: the turn of
the first cast, how often it was cast again, and the turn of the recast. That shows how much a deck leans on its commander. Eminence
cost reducers and the rest of a commander's text are not modeled.
Use it to compare builds, not to predict a game. Any card list works, so a 60-card deck is fine; a deck with a commander
gets the free first mulligan, one without does not.

### The same goldfish through the engine

```
python -m infernal_machine.goldfish DECKLIST [--games 100] [--turns 8] [--seed 0] [--play] [--workers N] [--model-games 1000]
```

The model above reads no card text. `goldfish(deck, games, turns, seed, on_the_play, workers)` in `goldfish.py` plays the deck for real:
`BotPlayer` plays it in `Game` against an idle second seat (it keeps its hand, passes every priority, never attacks or plays a card,
and its life is so high that nothing ends the game), and the report is built from what the engine did, in the model's own shape
(`SimStats`). Damage is the life the idle seat lost, so removal, tricks and everything a card's text does are in it, where the model sums
every creature's power; mana available is counted at the first main phase after the land drop, spent from the casts, and a game
number `n` shuffles the same way for the same seed and deck. It adds two columns the model cannot have, the cards drawn and the
permanents on the battlefield by turn. With `--model-games` it prints the model beside it (mulligans, mana spent, on curve, land
drops, damage) so the gap is visible: that gap is what the model leaves out. The engine is slow, a game takes a few seconds, so the
default is 100 games where the model runs thousands, and `tune` keeps using the model. A game the engine cannot finish (an error, or
the time limit) is left out and counted, and a deck with cards the engine can't read gets the usual warning.

## Mana base

```
python -m infernal_machine.manabase DECKLIST [--target 0.9] [--coverage 0.8] [--slack N] [--play | --draw]
```

`tune` sweeps the total land count; `manabase.analyze_mana_base(deck)` says how many sources of each *color* the deck needs and has,
and the tuning report ends its land section with the result. For one spell, the sources needed are the fewest for which the chance of
holding at least as many colored sources as the spell has pips of that color, among the cards seen by the turn it should be cast, is at
least the target (the hypergeometric distribution: a library of N cards, S of them sources). The turn is the spell's mana value plus
`slack`, or its pip count if that is higher. A mana base is built around what most of a color's spells ask for, not its one hardest
card, so the number shown as *needed* covers 80% of the color's spells (counting copies), and the most demanding spells are named beside
it with what they need; the verdict says "short by N" against the first and "(hardest short by N)" against the second.

- **Sources** are lands: basics, duals and any-color lands (limited to the commander's colors), and a land that fetches a basic counts
  for the colors of the basics in the deck. Mana rocks and mana creatures that make a color are listed apart, not counted.
- **Defaults follow the format:** a Commander deck is on the draw with two turns of slack (90% on the exact turn of the mana value is out
  of reach for three colors), a Standard deck on the play with none. `--play`, `--draw` and `--slack` override them.
- **Left out:** mulligans, hybrid and Phyrexian symbols (they can be paid another way), and X spells (they are cast whenever there is
  mana enough). A commander counts like any spell. Published tables (Frank Karsten's, for one) make further assumptions, so their
  numbers can differ from these; read the result as advice to weigh against the deck, not a verdict.
- **Tuning report:** also shows, from the goldfish games, how often a spell was stuck on colors on turns 3 and 5.

## Comparing two builds

```
python -m infernal_machine.compare BASELINE CHANGED OPPONENT [OPPONENT ...] [--games 40] [--pod 4] [--workers N] [--goldfish-games 500]
```

`tune` scores one swap at a time with a goldfish; `compare` asks whether a changed build actually does better in games.
`compare_builds(baseline, changed, opponents, ...)` in `compare.py` plays both builds on the same games: game `n` against an
opponent has the same seed, seat and opponents whichever build is playing (`matchup.plan_games`), so a pair of games differs only
by the cards that changed. It reports:

- **The difference** in score (a win is 1, a draw 1/2) over the pairs, changed minus baseline, with a 95% interval from the spread of
  the per-pair differences, and whether that interval leaves out zero. This is much less noisy than comparing two separate win rates.
- **How many pairs it takes:** at the observed spread, about how many pairs separate a 10 point and a 5 point difference from nothing,
  so a "within noise" result says how much more to play.
- **Pairs** the changed build did better in, the baseline did better in, and the same; a line per opponent when there are several.
- **The goldfish** (`simulate`) of both builds side by side: mulligans, opening lands, mana spent, on-curve rate, land drops, damage.
- **Notes:** the cards that changed, a change of Commander Bracket, builds of different sizes (they shuffle differently, so the games
  pair less closely), and changed cards the engine can't read (it cannot see what they do).

A pair is dropped if either game crashes or times out. The bots play every game, so the result is how the *bots* do with the two builds:
a card they play badly is under-rated in both. The two builds must both have commanders or both have none.

**Stopping early** (`--early-stop`, `early_stop=True`): the games are played in up to ten rounds, and the comparison stops when it is
settled, saying which: *clear* (the interval leaves out zero: "clearly better after 62 of 200 planned pairs") or *hopeless* (separating
a 5 point difference, or `--target`, would take more than three times the pairs planned, so more games would not settle it either;
"within noise, about 900 pairs needed"). Nothing stops before 30 pairs. Stopping the first time an ordinary 95% interval excludes
zero would call equal builds clear far more than one time in twenty, so with ten looks each look's interval is widened to 99.5%
(each look gets 5% / looks), which keeps the chance that equal builds ever come out clear at 5% or less; the output prints the width
used and the rule. A run that is never settled plays every pair and reports it. The pairs are the same games either way.

## Tuning a deck

```
python -m infernal_machine.tune DECKLIST [--games 500] [--turns 8] [--seed 0] [--play] [--try "Card Name"]...
```

`tune(deck, games, turns, seed, candidates)` in `tune.py` scores a deck by the simulation's game value (mana spent on
spells plus damage dealt by the last turn) and reports:

- **Per card, weakest first:** what the card adds per game. The same games are replayed with the card swapped for a blank, so
  every shuffle is identical and the difference is that card's contribution (only the games where it was drawn are replayed).
  Each number has a standard error; "within noise" means more games are needed before believing it. Cards cast less than half
  the time they are drawn are flagged.
- **Land count:** the effect of moving one to three slots between the weakest cards and the most played basic land, and between
  lands and a typical card.
- **Swaps:** `--try` cards each take the weakest card's slot; the effect is the change in value. A card the deck couldn't legally play
  is listed as not tried, with the reason: in a Commander deck that is outside the commander's color identity, banned, or already
  in the deck (singleton); in a deck with no commander, a fifth copy.

It cannot see what a card's text does (removal, card draw, counterspells, life gain), so a low score means "does little in a
goldfish", not "bad card". More games (`--games 2000`) tighten the error bars; 500 games of a 100-card deck takes about 30 seconds.

## Card impact in real games

```
python -m infernal_machine.impact DECKLIST OPPONENT [OPPONENT ...] [--cards "Card Name"]... [--top 12] [--games 40] [--pod N] [--workers N]
```

`tune` cannot see what a card's text does, because the goldfish plays alone and reads no text: removal, card draw and counterspells score
as mana spent or nothing. `impact.measure_impacts(deck, opponents, ...)` measures a card against other decks. The baseline games are
played once; then for each chosen card the *same* games (same seeds, seats and opponents, as in [comparing builds](#comparing-two-builds))
are played with every copy of the card replaced by a blank, which takes its slot so the deck keeps its size and the shuffles stay paired.
The card's impact is the baseline's score minus the blank's (a win is 1, a draw 1/2), per pair, with a 95% interval from the spread of
those differences.

- **Which cards:** `--cards` names them (repeat it), or by default the `--top` the goldfish scores lowest, since those are where its
  blindness to text matters most. A commander is not measured: taking it out leaves the deck without its color identity.
- **Reading it:** most pairs come out identical, because a card is drawn in only a fraction of games and often changes nothing when it
  is; the *differ* column counts the pairs that did not. *For 5 pts* is about how many pairs it would take to resolve a 5 point impact at
  the spread seen, and is a dash when fewer than 8 pairs differed, since a spread from so few events is not worth quoting. At a few dozen
  games per opponent most cards show a dash, and the honest reading is "not enough games to say": plan on hundreds of pairs for a card
  whose effect is a few points. A result is believable when its `±` is clearly smaller than the impact.
- **Cost:** each card is another full set of games, so 12 cards at 40 games per opponent against two opponents is about a thousand games,
  roughly ten minutes on six workers. Run it on the handful of cards you are unsure of, not the whole deck.
- **Caveats:** testing many cards finds a false winner about one time in twenty (at 95%), so re-run the ones you act on with another
  `--seed`; the bots play every game, so a card they play badly is under-rated; and cards the engine can't read are marked, since the
  games cannot see their text.

## Matchups

```
python -m infernal_machine.matchup DECKLIST OPPONENT [OPPONENT ...] [--games 40] [--pod 4] [--max-bracket N] [--workers N] [--time-limit 120]
```

`matchups(focus, opponents, games, pod, seed, max_turns, time_limit, workers)` in `matchup.py` plays `BotPlayer` games and
reports, per opponent, wins-losses-draws, the win rate with its 95% (Wilson) interval, average game length, the win rate
going first and going second, and how the focus deck lost (life, commander damage, poison, empty library). By default each
opponent gets `games` duels with the focus deck alternating seats; with `--pod 4` each game seats the focus deck with three
opponents drawn at random and the win rate is read against a fair share of 25%. Games run in parallel (`--workers`, default
half the CPUs). Standard decks need the Standard game mode (see #354).

Across all games it also reports how often the focus deck stumbled on lands (two or fewer after its first four turns) or had
the lands but cast at most one spell, and how it did when that happened. A game that crashes or passes `--time-limit` is
counted apart and the first error is shown, so engine bugs and runaway boards show up instead of hanging the run.

The bots decide everything, so a deck that needs careful play (combos, holding up mana, politics) is under-rated and one the
bot plays well is over-rated. Compare builds of one deck against the same opponents and seed instead of reading one win rate
as the deck's strength; 40 games per opponent only separates differences of about 25 points.

## When a deck has cards the engine can't play

The engine casts a card it does not fully understand, but ignores the text it can't read: a spell with such text resolves and does
nothing, and a creature arrives without that ability. So a result for a deck that holds such cards is not a result for the deck.
The reports say so, using `report.unplayable_cards(deck)` (the same test as `python -m infernal_machine.report DECK`):

- **Matchups:** a line for the focus deck and one for each opponent (or for all the opponents of a pod) naming the first few cards,
  and that the win rates are unreliable. `Record.focus_unplayable` and `Record.opponent_unplayable` hold the cards.
- **Tuning:** the deck's line, a "text the engine can't read" note on those cards in the card table (so a low score is not read as a
  bad card), and, for a `--try` card, the first line of its text the engine can't read. The score comes from the goldfish, which
  does not read card text for any card, so these notes do not change the numbers; they say what a matchup run would get wrong.
- **Simulation:** one closing line that card text is not played, only mana and creature bodies.
