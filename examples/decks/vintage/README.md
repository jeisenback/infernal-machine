# Real Vintage decklists for the coverage audit

Ten Vintage decks that people actually play, used to aim the card-coverage work at Vintage the way `examples/decks/standard` aims it at
Standard (issue #522). Each is the featured list of one of the ten most played archetypes of MTGGoldfish's paper Vintage metagame
(`https://www.mtggoldfish.com/metagame/vintage/full#paper`) as it stood on 2026-10-29, one list per archetype: a tournament list, not an
average. The share is the archetype's share of that metagame on that day; the ten cover 77.3% of it (29 archetypes listed).
Each file's first line says the archetype, the share, the date, the deck and its event, and the coverage audit weighs the ranking by that
share (#565).

| File | Archetype | Share | List | MTGGoldfish deck |
|---|---|---|---|---|
| `jewel_shops.txt` | Jewel Shops | 17.9% | Jewel Shops by Munchlax446, Vintage Challenge 16 2026-10-25 (1), 2nd Place, 7-1 (www.mtgo.com), Oct 25, 2026 | [8018423](https://www.mtggoldfish.com/deck/8018423) |
| `mono_white_initiative.txt` | Mono-White Initiative | 12.3% | Mono-White Initiative by espiatrianero, Vintage Challenge 32 2026-10-18, 2nd Place, 6-3 (www.mtgo.com), Oct 18, 2026 | [8007942](https://www.mtggoldfish.com/deck/8007942) |
| `esper_lurrus_control.txt` | Esper Lurrus Control | 10.6% | Esper Lurrus Control by Piedings, Vintage Challenge 32 2026-10-25, 1st Place, 7-2 (www.mtgo.com), Oct 25, 2026 | [8017591](https://www.mtggoldfish.com/deck/8017591) |
| `lurrus_po.txt` | Lurrus PO | 8.6% | Lurrus PO by CrazyDiamond513, Vintage Challenge 32 2026-10-25, 3rd Place, 7-1 (www.mtgo.com), Oct 25, 2026 | [8017606](https://www.mtggoldfish.com/deck/8017606) |
| `dimir_lurrus_control.txt` | Dimir Lurrus Control | 7.8% | Dimir Lurrus Control by Pietart, Vintage Challenge 32 2026-10-18, 1st Place, 8-1 (www.mtgo.com), Oct 18, 2026 | [8007937](https://www.mtggoldfish.com/deck/8007937) |
| `raker_shops.txt` | Raker Shops | 4.6% | Raker Shops by Peppembr, Vintage Challenge 32 2026-10-17, 9th Place, 4-2 (www.mtgo.com), Oct 17, 2026 | [8004931](https://www.mtggoldfish.com/deck/8004931) |
| `lurrus_breach.txt` | Lurrus Breach | 4.4% | Lurrus Breach by Sommertroll, Vintage Challenge 32 2026-10-24, 1st Place, 8-1 (www.mtgo.com), Oct 24, 2026 | [8015108](https://www.mtggoldfish.com/deck/8015108) |
| `paradoxical_outcome.txt` | Paradoxical Outcome | 3.9% | Paradoxical Outcome by crK, Vintage Challenge 16 2026-10-25, 1st Place, 6-2 (www.mtgo.com), Oct 25, 2026 | [8015529](https://www.mtggoldfish.com/deck/8015529) |
| `dredge.txt` | Dredge | 3.7% | Dredge by Lord_Beerus, Vintage Challenge 32 2026-10-25, 27th Place, 2-2 (www.mtgo.com), Oct 25, 2026 | [8017599](https://www.mtggoldfish.com/deck/8017599) |
| `oath_of_druids.txt` | Oath of Druids | 3.5% | Oath of Druids by PsiVen, Vintage Challenge 32 2026-10-24, 8th Place, 4-3 (www.mtgo.com), Oct 24, 2026 | [8015092](https://www.mtggoldfish.com/deck/8015092) |

```
python tools/coverage_audit.py --decks examples/decks/vintage/*.txt                                            # what blocks them, and what to build first
python tools/coverage_audit.py --decks examples/decks/vintage/*.txt --baseline examples/decks/vintage/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/vintage/*.txt --write-baseline examples/decks/vintage/baseline.json  # refresh it after building something
```

`baseline.json` works as the Commander one does (`examples/decks/README.md`): the names of the cards the engine cannot play yet, per deck,
and the `tracked decks` workflow fails when a card that played no longer does. Its Monday comment on the roadmap epic (#453) carries
this folder's headline (how many of the cards play, and how many of the decks play in full) beside Commander's and Standard's.

**The metagame moves.** A list here is only as current as its first line says. To refresh, do as for Standard
(`examples/decks/standard/README.md`): take the featured deck of each of the most played archetypes from the metagame page, download
its plain list, run it through `tools/import_deck.py`, put the archetype, share, date, deck and event in the first line, and refresh
the baseline. MTGGoldfish's plain lists drop accents and write a split or room card with one slash (`Lorien Revealed`, `Wear/Tear`);
the card file finds them by either spelling, and the files here keep the Oracle names (`Lórien Revealed`, `Wear // Tear`).

The Lurrus decks list Lurrus of the Dream-Den in the sideboard, as MTGGoldfish's plain list does, not as a marked companion; the
coverage audit counts the main deck only, so it makes no difference to the numbers.
