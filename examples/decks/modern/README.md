# Real Modern decklists for the coverage audit

Ten Modern decks that people actually play, used to aim the card-coverage work at Modern the way `examples/decks/standard` aims it at
Standard (issue #522). Each is the featured list of one of the ten most played archetypes of MTGGoldfish's paper Modern metagame
(`https://www.mtggoldfish.com/metagame/modern/full#paper`) as it stood on 2026-10-29, one list per archetype: a tournament list, not an
average. The share is the archetype's share of that metagame on that day; the ten cover 58.0% of it (60 archetypes listed).
Each file's first line says the archetype, the share, the date, the deck and its event, and the coverage audit weighs the ranking by that
share (#565).

| File | Archetype | Share | List | MTGGoldfish deck |
|---|---|---|---|---|
| `eldrazi_ramp.txt` | Eldrazi Ramp | 9.7% | Broodscale Combo by Timothée Blondiaux, Ultimate Guard European Magic Series - Regional Championship - Ghent 2026, 2nd Place, 13-3-1 (melee.gg), Oct 10, 2026 | [7997877](https://www.mtggoldfish.com/deck/7997877) |
| `izzet_prowess.txt` | Izzet Prowess | 7.8% | Izzet Prowess by Kazuaki Kurokawa, チャンピオンズカップファイナル シーズン5ラウンド1 Champions Cup Final Season 5 Round 1, 2nd Place, 13-1-2 (melee.gg), Oct 3, 2026 | [7984346](https://www.mtggoldfish.com/deck/7984346) |
| `affinity.txt` | Affinity | 6.4% | Izzet Affinity by Sebastian Moreira, $5K RCQ - Modern - SCG CON Los Angeles - Saturday - 9:30 am, 1st Place, 10-1 (melee.gg), Oct 10, 2026 | [7997485](https://www.mtggoldfish.com/deck/7997485) |
| `domain_zoo.txt` | Domain Zoo | 5.8% | W-U-R-G Domain Zoo by ryuumei, チャンピオンズカップファイナル シーズン5ラウンド1 Champions Cup Final Season 5 Round 1, 1st Place, 13-2-1 (melee.gg), Oct 3, 2026 | [7984345](https://www.mtggoldfish.com/deck/7984345) |
| `eldrazi.txt` | Eldrazi | 5.8% | Broodscale Combo by Alexander Rosdahl, Ultimate Guard European Magic Series - Regional Championship - Ghent 2026, 1st Place, 15-2 (melee.gg), Oct 10, 2026 | [7997876](https://www.mtggoldfish.com/deck/7997876) |
| `boros_energy.txt` | Boros Energy | 5.6% | Boros Energy by Daniel Keener, Regional Championship - SCG CON Los Angeles - Season 5 - Round 1 - Saturday - 9:00 am, 6th Place, 12-3-1 (melee.gg), Oct 10, 2026 | [8006214](https://www.mtggoldfish.com/deck/8006214) |
| `esper_blink.txt` | Esper Blink | 5.4% | Esper by Keita Tonouchi, チャンピオンズカップファイナル シーズン5ラウンド1 Champions Cup Final Season 5 Round 1, 4th Place, 11-3-1 (melee.gg), Oct 3, 2026 | [7984348](https://www.mtggoldfish.com/deck/7984348) |
| `jeskai_energy.txt` | Jeskai Energy | 3.9% | Jeskai Energy by Hirotaka Kawasaki, チャンピオンズカップファイナル シーズン5ラウンド1 Champions Cup Final Season 5 Round 1, 3rd Place, 11-3-1 (melee.gg), Oct 3, 2026 | [7984347](https://www.mtggoldfish.com/deck/7984347) |
| `goryos_vengeance.txt` | Goryo's Vengeance | 3.9% | W-U-B-G Goryo's by Nick Deriu, $1K Modern RCQ - SCG CON Los Angeles - Friday - 10:00 am, 11th Place, 5-1-1 (melee.gg), Oct 9, 2026 | [7999486](https://www.mtggoldfish.com/deck/7999486) |
| `azorius_control.txt` | Azorius Control | 3.7% | Azorius Control (Kaheera) by Toothy, Regional Championship - SCG CON Los Angeles - Season 5 - Round 1 - Saturday - 9:00 am, 1st Place, 15-1-2 (melee.gg), Oct 10, 2026 | [8006209](https://www.mtggoldfish.com/deck/8006209) |

```
python tools/coverage_audit.py --decks examples/decks/modern/*.txt                                            # what blocks them, and what to build first
python tools/coverage_audit.py --decks examples/decks/modern/*.txt --baseline examples/decks/modern/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/modern/*.txt --write-baseline examples/decks/modern/baseline.json  # refresh it after building something
```

`baseline.json` works as the Commander one does (`examples/decks/README.md`): the names of the cards the engine cannot play yet, per deck,
and the `tracked decks` workflow fails when a card that played no longer does. Its Monday comment on the roadmap epic (#453) carries
this folder's headline (how many of the cards play, and how many of the decks play in full) beside Commander's and Standard's.

**The metagame moves.** A list here is only as current as its first line says. To refresh, do as for Standard
(`examples/decks/standard/README.md`): take the featured deck of each of the most played archetypes from the metagame page, download
its plain list, run it through `tools/import_deck.py`, put the archetype, share, date, deck and event in the first line, and refresh
the baseline. MTGGoldfish's plain lists drop accents and write a split or room card with one slash (`Lorien Revealed`, `Wear/Tear`);
the card file needs the Oracle name (`Lórien Revealed`, `Wear // Tear`), so those names were corrected by hand here.
