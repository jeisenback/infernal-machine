# Real Pioneer decklists for the coverage audit

Ten Pioneer decks that people actually play, used to aim the card-coverage work at Pioneer the way `examples/decks/standard` aims it at
Standard (issue #522). Each is the featured list of one of the ten most played archetypes of MTGGoldfish's paper Pioneer metagame
(`https://www.mtggoldfish.com/metagame/pioneer/full#paper`) as it stood on 2026-10-29, one list per archetype: a tournament list, not an
average. The share is the archetype's share of that metagame on that day; the ten cover 74.5% of it (46 archetypes listed).
Each file's first line says the archetype, the share, the date, the deck and its event, and the coverage audit weighs the ranking by that
share (#565).

| File | Archetype | Share | List | MTGGoldfish deck |
|---|---|---|---|---|
| `golgari_midrange.txt` | Golgari Midrange | 17.5% | Golgari Midrange by SuperCow12653, Pioneer Challenge 16 2026-10-24, 1st Place, 6-2 (www.mtgo.com), Oct 24, 2026 | [8015238](https://www.mtggoldfish.com/deck/8015238) |
| `izzet_prowess.txt` | Izzet Prowess | 13.5% | Izzet Prowess by Craigpuncher, Pioneer Challenge 16 2026-10-25, 4th Place, 5-2 (www.mtgo.com), Oct 25, 2026 | [8017434](https://www.mtggoldfish.com/deck/8017434) |
| `nykthos_ramp.txt` | Nykthos Ramp | 10.1% | Nykthos Ramp by MandrillMan, Pioneer Challenge 32 2026-10-19, 1st Place, 7-2 (www.mtgo.com), Oct 19, 2026 | [8009130](https://www.mtggoldfish.com/deck/8009130) |
| `mono_red_prowess.txt` | Mono-Red Prowess | 6.4% | Mono-Red Prowess by Chiozzani_23, Pioneer Challenge 16 2026-10-18, 4th Place, 4-3 (www.mtgo.com), Oct 18, 2026 | [8007857](https://www.mtggoldfish.com/deck/8007857) |
| `jund_sacrifice.txt` | Jund Sacrifice | 5.8% | Jund Sacrifice by xfile, Pioneer Challenge 32 2026-10-19, 12th Place, 4-2 (www.mtgo.com), Oct 19, 2026 | [8009124](https://www.mtggoldfish.com/deck/8009124) |
| `jund_artifact_sacrifice.txt` | Jund Artifact Sacrifice | 5.6% | Jund Artifact Sacrifice by SpockVidaLoka, Pioneer Challenge 32 2026-10-22, 14th Place, 4-2 (www.mtgo.com), Oct 22, 2026 | [8012442](https://www.mtggoldfish.com/deck/8012442) |
| `dimir_aggro.txt` | Dimir Aggro | 4.8% | Dimir Aggro by itstime, Pioneer Challenge 16 2026-10-24, 3rd Place, 5-1 (www.mtgo.com), Oct 24, 2026 | [8015248](https://www.mtggoldfish.com/deck/8015248) |
| `selesnya_company.txt` | Selesnya Company | 3.7% | Selesnya Company by Kako_Ferrer, Pioneer Challenge 32 2026-10-26, 2nd Place, 7-2 (www.mtgo.com), Oct 26, 2026 | [8019005](https://www.mtggoldfish.com/deck/8019005) |
| `izzet_aggro.txt` | Izzet Aggro | 3.7% | Izzet Aggro by Kingokarado, Pioneer Challenge 16 2026-10-25, 1st Place, 7-1 (www.mtgo.com), Oct 25, 2026 | [8017435](https://www.mtggoldfish.com/deck/8017435) |
| `izzet_phoenix.txt` | Izzet Phoenix | 3.4% | Izzet Phoenix by monzatubarao, Pioneer Challenge 32 2026-10-26, 9th Place, 4-2 (www.mtgo.com), Oct 26, 2026 | [8019001](https://www.mtggoldfish.com/deck/8019001) |

```
python tools/coverage_audit.py --decks examples/decks/pioneer/*.txt                                            # what blocks them, and what to build first
python tools/coverage_audit.py --decks examples/decks/pioneer/*.txt --baseline examples/decks/pioneer/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/pioneer/*.txt --write-baseline examples/decks/pioneer/baseline.json  # refresh it after building something
```

`baseline.json` works as the Commander one does (`examples/decks/README.md`): the names of the cards the engine cannot play yet, per deck,
and the `tracked decks` workflow fails when a card that played no longer does. Its Monday comment on the roadmap epic (#453) carries
this folder's headline (how many of the cards play, and how many of the decks play in full) beside Commander's and Standard's.

**The metagame moves.** A list here is only as current as its first line says. To refresh, do as for Standard
(`examples/decks/standard/README.md`): take the featured deck of each of the most played archetypes from the metagame page, download
its plain list, run it through `tools/import_deck.py`, put the archetype, share, date, deck and event in the first line, and refresh
the baseline. MTGGoldfish's plain lists drop accents and write a split or room card with one slash (`Lorien Revealed`, `Wear/Tear`);
the card file finds them by either spelling, and the files here keep the Oracle names (`Lórien Revealed`, `Wear // Tear`).
