# Real Pauper decklists for the coverage audit

Ten Pauper decks that people actually play, used to aim the card-coverage work at Pauper the way `examples/decks/standard` aims it at
Standard (issue #522). Each is the featured list of one of the ten most played archetypes of MTGGoldfish's paper Pauper metagame
(`https://www.mtggoldfish.com/metagame/pauper/full#paper`) as it stood on 2026-10-29, one list per archetype: a tournament list, not an
average. The share is the archetype's share of that metagame on that day; the ten cover 58.6% of it (60 archetypes listed).
Each file's first line says the archetype, the share, the date, the deck and its event, and the coverage audit weighs the ranking by that
share (#565).

| File | Archetype | Share | List | MTGGoldfish deck |
|---|---|---|---|---|
| `mono_red_madness.txt` | Mono Red Madness | 13.2% | Mono-Red Madness Burn by StefanLebtag, Common Island 2 – A Tournament by Pauper to the People, 5-1-1 (melee.gg), Oct 3, 2026 | [7984225](https://www.mtggoldfish.com/deck/7984225) |
| `blue_terror.txt` | Blue Terror | 7.7% | Mono-Blue Terror by todor1705, British Pauper Open, 1st Place, 9-1 (melee.gg), Oct 3, 2026 | [7987742](https://www.mtggoldfish.com/deck/7987742) |
| `dimir_faeries.txt` | Dimir Faeries | 6.2% | Dimir Faeries by ridikolaus, Common Island 2 – A Tournament by Pauper to the People, 6-1 (melee.gg), Oct 3, 2026 | [7984220](https://www.mtggoldfish.com/deck/7984220) |
| `tron.txt` | Tron | 5.7% | Bant Tron by Lukasz Slowinski, British Pauper Open, 16th Place, 5-2 (melee.gg), Oct 3, 2026 | [7987757](https://www.mtggoldfish.com/deck/7987757) |
| `elves.txt` | Elves | 5.4% | Mono-Green Elves by THXrhys, British Pauper Open, 2nd Place, 8-2 (melee.gg), Oct 3, 2026 | [7987743](https://www.mtggoldfish.com/deck/7987743) |
| `grixis_affinity.txt` | Grixis Affinity | 4.7% | Grixis Affinity by Philipp Schultz, Common Island 2 – A Tournament by Pauper to the People, 5-2 (melee.gg), Oct 3, 2026 | [7984235](https://www.mtggoldfish.com/deck/7984235) |
| `bogles.txt` | Bogles | 4.3% | Selesnya Bogles by Pallm, Common Island 2 – A Tournament by Pauper to the People, 4-3 (melee.gg), Oct 3, 2026 | [7984255](https://www.mtggoldfish.com/deck/7984255) |
| `spy_combo.txt` | Spy Combo | 4.2% | Golgari Spy Combo by Marco De Pasquale, British Pauper Open, 5th Place, 6-2 (melee.gg), Oct 3, 2026 | [7987746](https://www.mtggoldfish.com/deck/7987746) |
| `mono_red_rally.txt` | Mono Red Rally | 3.9% | Mono-Red Aggro by Richard Stahl, Common Island 2 – A Tournament by Pauper to the People, 6-1 (melee.gg), Oct 3, 2026 | [7984222](https://www.mtggoldfish.com/deck/7984222) |
| `ruby_storm.txt` | Ruby Storm | 3.3% | Gruul Aggro by WickD, Common Island 2 – A Tournament by Pauper to the People, 4-3 (melee.gg), Oct 3, 2026 | [7984263](https://www.mtggoldfish.com/deck/7984263) |

```
python tools/coverage_audit.py --decks examples/decks/pauper/*.txt                                            # what blocks them, and what to build first
python tools/coverage_audit.py --decks examples/decks/pauper/*.txt --baseline examples/decks/pauper/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/pauper/*.txt --write-baseline examples/decks/pauper/baseline.json  # refresh it after building something
```

`baseline.json` works as the Commander one does (`examples/decks/README.md`): the names of the cards the engine cannot play yet, per deck,
and the `tracked decks` workflow fails when a card that played no longer does. Its Monday comment on the roadmap epic (#453) carries
this folder's headline (how many of the cards play, and how many of the decks play in full) beside Commander's and Standard's.

**The metagame moves.** A list here is only as current as its first line says. To refresh, do as for Standard
(`examples/decks/standard/README.md`): take the featured deck of each of the most played archetypes from the metagame page, download
its plain list, run it through `tools/import_deck.py`, put the archetype, share, date, deck and event in the first line, and refresh
the baseline. MTGGoldfish's plain lists drop accents and write a split or room card with one slash (`Lorien Revealed`, `Wear/Tear`);
the card file finds them by either spelling, and the files here keep the Oracle names (`Lórien Revealed`, `Wear // Tear`).
