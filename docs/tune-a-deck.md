# Tune a deck

A guided tour of the deck tools, in the order you would use them. Every example below is real output, from the Lorehold precon in
`examples/precons/` (a Commander deck) against the Prismari and Quandrix precons, on 2026-10-16 with `--seed 0`. Your numbers will
differ; what matters is how to read them. For the options of each tool, see the
[reference](simulation.md).

You need a decklist file: one card per line as `N Card Name`, with the commander under a `Commander` heading. Cards are looked up in
Scryfall's data the first time (see [the card caches](cards-and-decks.md#the-card-caches)) and kept after that. A deck with no commander
is treated as a Standard deck and every tool below works on it too (there is just no Bracket step).

A deck on Moxfield or Archidekt becomes a decklist with `python tools/import_deck.py EXPORT.txt -o my_deck.txt` (you export the text
from the site; the tool makes no request to it, see [decks from Moxfield or Archidekt](cards-and-decks.md#decks-from-moxfield-or-archidekt)).

If you want the whole tour in one command:

```
python -m infernal_machine.analyze my_deck.txt opponent1.txt opponent2.txt
```

Name no opponents and it plays the [saved gauntlet](cards-and-decks.md#the-saved-gauntlet) (the five precons); `--max-bracket N` keeps
the gauntlet decks that can be played at Bracket N or lower.

and read it top to bottom. The rest of this page is what each part means.

## 1. Can the engine play your cards?

```
python -m infernal_machine.report my_deck.txt
Fully playable: 100/100 cards
```

The engine understands the text of about a third of all Commander-legal cards completely (the most played ones far better: all of the
top 100, nine in ten of the top 500). A card it does not fully understand is still cast, but the text it cannot read is ignored: a
spell with such text does nothing, and a creature has none of that ability. If the report lists cards, every result below is a result
for a deck without that text, and the other tools say so at the top of their output ("The deck has 3 cards ... the engine can't fully
play"). Fix what you can by swapping the card, or read those cards' results with that in mind.

## 2. How strong a Commander Bracket does the deck force?

```
python -m infernal_machine.brackets my_deck.txt
no hard limit above Bracket 1
```

This reads the hard limits off the cards: Game Changers (none below Bracket 3, up to three in 3), mass land denial (not below
Bracket 4), and it lists extra-turn cards. With `--combos` it also asks Commander Spellbook which combos the deck holds (a two-card
combo that wins early is not below Bracket 4; `analyze` always asks, and lists them in its Combos part). It cannot see how the deck is
played, so the answer is the *lowest* bracket the deck can be played at, not a rating. Use it before choosing opponents: results against a deck at a higher bracket compare unlike
decks, and the matchup report warns about that.

## 3. Does the mana base hold up?

```
python -m infernal_machine.manabase my_deck.txt
color   pips  sources  needed  verdict                         hardest spells
White     52       31      24  enough                          White Orchid Phantom ({W}{W}, by turn 4) needs 30, Guardian of Faith ...
Red       23       24      18  enough (hardest short by 2)     Atsushi, the Blazing Sky ({2}{R}{R}, by turn 6) needs 26, Faithless ...
Not counted as sources: mana rocks and creatures that make White 3, Red 3.
```

For each color, *sources* is the lands that make it and *needed* is what covers 80% of that color's spells at 90% odds of casting them
by their mana value plus two turns (the first line of the real output spells the assumptions out). The hardest spells are named
separately, because a deck can have enough for most of its red and still be short for its one expensive double-red card, as here: 24
sources, 18 needed, but Atsushi wants 26. "Short by N" is the number to add; "hardest short by N" is a judgment call about that one card.
Change the assumptions with `--target`, `--coverage`, `--slack`, `--play` and `--draw`; the numbers are advice to weigh, not a verdict.

## 4. How does the deck play out alone? (the goldfish)

```
python -m infernal_machine.simulate my_deck.txt --games 500 --turns 8
500 games, 8 turns. Mulligan rate 18.0%, 2.99 lands in the opening hand, 79% of available mana spent.
On curve: 42% of the spells drawn were cast as soon as their mana value allowed.

turn  land drop  mana  spent  color-stuck  damage
   1     100.0%   0.8    0.3         1.6%     0.0
   2      99.8%   2.0    1.6         7.0%     0.0
   3      91.6%   3.1    2.9         6.4%     0.6
   4      75.8%   4.0    3.8         4.6%     2.4
   ...
   8      18.4%   6.6    4.1         2.2%    25.2

card                                  copies  seen  cast  cast if seen  avg turn  avg wait  on curve
Moonshaker Cavalry                         1   16%    3%          21%       7.3       4.8       21%
Angel of Indemnity                         1   15%   10%          63%       6.6       4.2       33%
...
```

The deck plays alone: it draws, plays a land a turn and casts what it can pay for, 500 times. *Land drop* is how often every land drop was
made through that turn; *mana* is what could be tapped and *spent* what went on spells; *color-stuck* is how often a spell the lands'
count could pay for was blocked by their colors; *damage* is the total dealt so far, unblocked. In the card table, sorted worst first,
*cast if seen* is the share of draws that got cast: a card at 21% is too expensive, in the wrong colors, or both. It models mana and
creature bodies only, so removal and card draw show up as mana spent and nothing more. A
[goldfish through the real engine](https://github.com/jeisenback/infernal-machine/issues/390) is planned.

## 5. Which cards earn their slot? (tuning)

```
python -m infernal_machine.tune my_deck.txt --games 300 --turns 8 --try "Thought Vessel" --try "Swiftfoot Boots" --try "Mind Stone"
300 games, 8 turns. Average game value 51.94 (mana spent on spells + damage dealt by the last turn).
Bracket: no hard limit above Bracket 1.

Per card, weakest first: what the card adds per game, replayed with the card as a blank.
card                                  copies  adds per game        seen  cast if seen  note
Monologue Tax                              1  -0.31 ±0.11            15%          89%
Fateful Tempest                            1  -0.12 ±0.08  (within noise)   12%          78%
Secret Rendezvous                          1  -0.08 ±0.09  (within noise)   15%          78%
...

Land count (change in lands -> change in value):
  -3 lands: -0.28 ±0.49  (within noise)
  ...
  +1 lands: +1.17 ±0.29
  +3 lands: +2.43 ±0.49

Swaps (best first): the card replaces the weakest card in the deck.
  Thought Vessel for Monologue Tax: +1.17 ±0.25
  Swiftfoot Boots for Monologue Tax: +0.38 ±0.13

Not tried: Mind Stone (already in the deck)
```

Each card is measured by replaying the *same* games with it swapped for a blank, so the difference is that card's contribution. The
score of a game is the mana it spent on spells plus the damage it dealt by the last turn. Read the `±` as the size of the doubt: a
number is only believable when it is clearly larger than its `±` ("within noise" marks the ones that are not). Here the deck gains from
extra lands (+1.17 ± 0.29 for one more) and from Thought Vessel in place of its weakest card; most of the cards in the table are
within noise, which is the honest answer for most cards. `--try` takes cards to test in the weakest slot, and anything that cannot be
played in this deck is listed as "Not tried" with the reason (Mind Stone is already in this deck).

The caution that matters: the goldfish reads no card text, so a removal spell or a counterspell scores near zero because it does
nothing *in a goldfish*. A low score means "does little alone", not "bad card". To measure those you need other players: that is the next
two steps.

### Removal and card draw: measure them in real games

The goldfish scores a removal spell as nothing, so the cards it ranks lowest are exactly the ones it may be wrong about. `impact` plays
the *same* games with and without a card (every copy swapped for a blank) against other decks and reports what the card added:

```
python -m infernal_machine.impact my_deck.txt opponent1.txt opponent2.txt --top 6 --games 30
Card impact in real games: 30 paired games against PrismariArtistry_SOC, QuandrixUnlimited_SOC for each of 6 cards. ...
The unchanged deck scores 48.3%.

card                                  copies  impact                       pairs  differ  for 5 pts  note
Secret Rendezvous                          1    -3.3 ± 2.3  (within noise)     60       2          -
Fateful Tempest                            1    -1.7 ± 2.9  (within noise)     60       3          -
Archaeomancer's Map                        1    +1.7 ± 1.7  (within noise)     60       1          -
Lorehold Charm                             1    +1.7 ± 1.7  (within noise)     60       1          -
Monologue Tax                              1    +1.7 ± 1.7  (within noise)     60       1          -
Faithless Looting                          1    +5.0 ± 3.7  (within noise)     60       5          -
```

The honest answer here is "not enough games to say". Out of 60 pairs, a card changed the result in only 1 to 5 (the *differ* column):
each card is drawn in a fraction of the games, and often changes nothing when it is. The dash under *for 5 pts* means too few pairs
differed to estimate how many it would take. To see a few points of effect you need hundreds of pairs per card (`--games 100` or more),
and every card you add to `--cards` is another full set of games, so measure the handful you are unsure of. Testing six cards at 95%
will make one look clear about one time in twenty by chance; re-run the one you like with another `--seed`.

## 6. How does it do against other decks? (matchups)

```
python -m infernal_machine.matchup my_deck.txt opponent1.txt opponent2.txt --games 12
LoreholdSpirit_SOC against bots. Win rate with its 95% interval (fair share 50%); win rate when going first / second; why it lost.
Bracket: the focus deck plays at Bracket 1 or higher; opponents' floors: PrismariArtistry_SOC 1, QuandrixUnlimited_SOC 1.

opponent                           W-L-D  win rate         turns  first        second       how it lost
PrismariArtistry_SOC               5-7-0  42% (19%-68%)     15.7  43% of 7     40% of 5     life 7
QuandrixUnlimited_SOC              8-4-0  67% (39%-86%)     16.3  83% of 6     50% of 6     life 4

Overall 13/24 (54%).
Stumbled on lands (two or fewer after four turns) in 12% of games, winning 0% of them.
Had the lands but cast at most one spell in four turns in 17% of games, winning 50% of them.
```

Bots play every seat, so this is how the bots do with the deck. The interval is the point: 12 games per opponent give a win rate that
could be anywhere from 19% to 68%, which is no answer at all. Play 100 or more per opponent for anything you want to act on. "Stumbled"
and "had the lands but did little" say what lost the games the deck lost, and they are about the deck as much as the bot. `--pod 4`
plays four-player games with the opponents drawn at random (a fair share is then 25%), `--max-bracket N` leaves out opponents above a
bracket, and `--workers` sets how many games run at once.

## 7. Did the change help? (compare)

```
python -m infernal_machine.compare my_deck.txt my_deck_changed.txt opponent1.txt opponent2.txt --games 12
24 paired games. LoreholdSpirit_SOC against LoreholdSpirit_MindStone: -1 Sol Ring, +1 Mind Stone.

Score (a win is 1, a draw 1/2): LoreholdSpirit_SOC 54.2%, LoreholdSpirit_MindStone 45.8%.
Difference -8.3 points (95% interval -28.5 to +11.8): within noise: more pairs are needed.
Pairs: LoreholdSpirit_MindStone did better in 2, LoreholdSpirit_SOC did better in 4, the same in 18.
At this spread, about 98 pairs separate a 10 point difference from nothing, and about 390 a 5 point one.
```

Both builds play the same games (same seeds, seats and opponents), so a pair differs only by the cards that changed; 18 of these 24 pairs
came out identical. The difference is measured per pair, which is much less noisy than comparing two win rates. The result here is
the usual one for a small change: *within noise*, with the number of pairs it would take to tell. Taking Sol Ring out of a deck should
cost something, and 24 games cannot show it; about 390 pairs could resolve five points. Either play that many (it is minutes with
`--workers`, not hours) or accept that the change is too small for the engine to see. The goldfish of both builds is printed beside
it, since that is exact where the games are not. Add `--early-stop` to stop as soon as the answer is clear (or clearly out of reach
for the games planned) instead of always playing them all; the output says which, and how it decided.

### The report as a web page

`--html report.html` writes one self-contained page (no scripts or styles loaded from anywhere, so it can be mailed or opened offline;
it follows the reader's light or dark setting and fits a phone): the numbers that matter as tiles at the top (format, Bracket, lands,
mulligans, turns on curve, matchup games won), the mana base as bars against what each color needs, the goldfish's damage by turn as a
chart, **each card's value with its error as a whisker** (a table that sorts when you click a header, with only the clearly nonzero
values coloured), the land-count and swap tables, and each matchup as a win rate with its 95% interval and a verdict ("ahead",
"behind", "too close to say"). The cards the engine can't play are a note above everything. A part whose numbers were not kept (a run
saved before this option existed, then reused with `--since`) shows its text instead. The page is made by `htmlreport.py` from the
same `Analysis` the markdown comes from.

### Keeping a run, and seeing what an edit changed

`analyze` takes minutes, and "did my edit help" used to mean reading two long reports. Keep the numbers of a run, and ask a later one what moved:

```
python -m infernal_machine.analyze my_deck.txt opp1.txt opp2.txt --save before.json
# ... change a card or two in my_deck.txt ...
python -m infernal_machine.analyze my_deck.txt opp1.txt opp2.txt --since before.json --save after.json
```

The second report starts with a **What changed** section: the cards that changed (`-1 Sol Ring, +1 Mind Stone`), the Bracket and any new Game
Changers, the colors whose sources or shortfall moved, the goldfish numbers before and after, and the win rate against each opponent
that both runs played. A rate is marked *outside noise* only when the 95% interval of the difference between the two runs leaves out zero
(two independent proportions), so a 12-game win rate that fell from 67% to 33% is correctly labelled *within noise*; an average with
no error bar kept (damage by turn, tuning's baseline) is shown without a verdict. If the settings differ (games, turns, seed, pod) it
says so, since the numbers then are not directly comparable.

A part is not played again when the saved run has it for the same deck **and** the same settings (the opponents' decks and the games for the
matchups, the games, turns and seed for the goldfish, the candidates tried for the tuning): its numbers and text are reused, and the report
says "reused" instead of comparing a part with itself. So a re-run after changing only the opponents takes the time of the matchups alone;
a changed card changes every part, so then everything is played. `--no-reuse` plays everything and still compares. The saved file is a
JSON of the deck's cards, the settings and each part's numbers and text; a file saved by another version of the tool is refused.

## 8. Reading all of this honestly

- **An interval, not a number.** If the interval holds zero (or 50%), nothing was found. Say "within noise", not "slightly better".
- **More games before more conclusions.** Tens of games rule out almost nothing; hundreds begin to. The tools say how many it would take.
- **The engine's reading of the cards.** Cards it cannot play make every result about a different deck. The reports say so; believe them.
- **Bots, not players.** A card the bots play badly (a combo piece, a card that wants careful timing) is under-rated in both builds.
- **Many comparisons find false winners.** Test ten swaps at 95% and one will look clear by chance. Re-run the one you like with a
  different `--seed` before you act on it.

## How long it takes

On a recent laptop, a goldfish of 500 games takes about 11 seconds, the tuning report at 300 games about 55 seconds, and the 24 matchup
games above, on six workers, about 25 seconds (a few seconds a game, so 400 games is several minutes). `analyze` prints what each
part took. The weekly
`bot strength` check on GitHub plays 480 duels in about a minute per shard.
