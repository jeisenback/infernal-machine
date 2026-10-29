# Real Legacy decklists for the coverage audit

Ten Legacy decks that people actually play, used to aim the card-coverage work at Legacy the way `examples/decks/standard` aims it at
Standard (issue #522). Each is the featured list of one of the ten most played archetypes of MTGGoldfish's paper Legacy metagame
(`https://www.mtggoldfish.com/metagame/legacy/full#paper`) as it stood on 2026-10-29, one list per archetype: a tournament list, not an
average. The share is the archetype's share of that metagame on that day; the ten cover 57.6% of it (60 archetypes listed).
Each file's first line says the archetype, the share, the date, the deck and its event, and the coverage audit weighs the ranking by that
share (#565).

| File | Archetype | Share | List | MTGGoldfish deck |
|---|---|---|---|---|
| `dimir_tempo.txt` | Dimir Tempo | 12.6% | Dimir Tempo by Oceansoul92, Legacy Challenge 32 2026-10-18, 1st Place, 9-1 (www.mtgo.com), Oct 18, 2026 | [8007708](https://www.mtggoldfish.com/deck/8007708) |
| `boros_energy.txt` | Boros Energy | 7.6% | Boros Energy by Craigpuncher, Legacy Challenge 32 2026-10-23 (1), 3rd Place, 7-1 (www.mtgo.com), Oct 23, 2026 | [8016565](https://www.mtggoldfish.com/deck/8016565) |
| `izzet_delver.txt` | Izzet Delver | 6.7% | Izzet Delver by i_b_TRUE, Legacy Challenge 32 2026-10-23 (1), 1st Place, 8-1 (www.mtgo.com), Oct 23, 2026 | [8016541](https://www.mtggoldfish.com/deck/8016541) |
| `doomsday.txt` | Doomsday | 5.8% | Doomsday by boryas, Legacy Showcase Challenge 2026-10-25 (1), 1st Place, 10-2 (www.mtgo.com), Oct 25, 2026 | [8017841](https://www.mtggoldfish.com/deck/8017841) |
| `eldrazi.txt` | Eldrazi | 4.5% | Eldrazi by Pharina, Legacy Challenge 32 2026-10-17, 3rd Place, 6-2 (www.mtgo.com), Oct 17, 2026 | [8004713](https://www.mtggoldfish.com/deck/8004713) |
| `lands.txt` | Lands | 4.5% | Lands by Phellipe, Legacy Challenge 32 2026-10-21 (1), 1st Place, 8-1 (www.mtgo.com), Oct 21, 2026 | [8011462](https://www.mtggoldfish.com/deck/8011462) |
| `sneak_and_show.txt` | Sneak and Show | 4.2% | Sneak and Show by GieralK, Legacy Challenge 32 2026-10-18, 2nd Place, 8-2 (www.mtgo.com), Oct 18, 2026 | [8007724](https://www.mtggoldfish.com/deck/8007724) |
| `beanstalk_control_non_yorion.txt` | Beanstalk Control (Non-Yorion) | 4.0% | Beanstalk Control (Non-Yorion) by ChuckNoris43, Legacy Challenge 32 2026-10-25 (1), 2nd Place, 6-3 (www.mtgo.com), Oct 25, 2026 | [8018390](https://www.mtggoldfish.com/deck/8018390) |
| `mystic_forge_combo.txt` | Mystic Forge Combo | 3.9% | Mystic Forge Combo by musasabi, Legacy Challenge 32 2026-10-20, 2nd Place, 8-1 (www.mtgo.com), Oct 20, 2026 | [8009714](https://www.mtggoldfish.com/deck/8009714) |
| `death_and_taxes_yorion_black_white.txt` | Death and Taxes (Yorion) - Black/White | 3.8% | Orzhov Death and Taxes (Yorion) by Theodore Lockman, $1K Legacy - SCG CON Hartford - Saturday - 9:00 am, 1st Place, 7-0-2 (melee.gg), Oct 24, 2026 | [8016073](https://www.mtggoldfish.com/deck/8016073) |

```
python tools/coverage_audit.py --decks examples/decks/legacy/*.txt                                            # what blocks them, and what to build first
python tools/coverage_audit.py --decks examples/decks/legacy/*.txt --baseline examples/decks/legacy/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/legacy/*.txt --write-baseline examples/decks/legacy/baseline.json  # refresh it after building something
```

`baseline.json` works as the Commander one does (`examples/decks/README.md`): the names of the cards the engine cannot play yet, per deck,
and the `tracked decks` workflow fails when a card that played no longer does. Its Monday comment on the roadmap epic (#453) carries
this folder's headline (how many of the cards play, and how many of the decks play in full) beside Commander's and Standard's.

**The metagame moves.** A list here is only as current as its first line says. To refresh, do as for Standard
(`examples/decks/standard/README.md`): take the featured deck of each of the most played archetypes from the metagame page, download
its plain list, run it through `tools/import_deck.py`, put the archetype, share, date, deck and event in the first line, and refresh
the baseline. MTGGoldfish's plain lists drop accents and write a split or room card with one slash (`Lorien Revealed`, `Wear/Tear`);
the card file finds them by either spelling, and the files here keep the Oracle names (`Lórien Revealed`, `Wear // Tear`).
