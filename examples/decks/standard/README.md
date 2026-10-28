# Real Standard decklists for the coverage audit

Fifteen Standard decks that people actually play, used to aim the card-coverage work at Standard the way `examples/decks` aims it at
Commander (issue #521). Each is the featured list of one of the fifteen most played archetypes of MTGGoldfish's paper Standard metagame
(`https://www.mtggoldfish.com/metagame/standard/full#paper`) as it stood on 2026-10-28, one list per archetype: a tournament list from
melee.gg or Magic Online, not an average. The share is the archetype's share of that metagame on that day. They are **not** in the
gauntlet and are not meant as opponents; the gauntlet's Standard decks are the five baselines in `examples/gauntlet`.

| File | Archetype | Share | List | MTGGoldfish deck |
|---|---|---|---|---|
| `dimir_midrange.txt` | Dimir Midrange | 10.6% | Dimir Midrange by Rsaephan, $uper $unday RCQ - Standard - SCG CON Los Angeles - Sunday - 9:30 am, 4-1-1 (melee.gg), Oct 11, 2026 | [7996136](https://www.mtggoldfish.com/deck/7996136) |
| `mono_green_landfall.txt` | Mono-Green Landfall | 10.4% | Mono-Green Landfall by Jeff Lin, Arena Championship 13, 2nd Place, 12-1 (melee.gg), Oct 24, 2026 | [8019516](https://www.mtggoldfish.com/deck/8019516) |
| `izzet_spellementals.txt` | Izzet Spellementals | 8.2% | Izzet Spellementals by Skylar Pastor, $1K Standard RCQ - SCG CON Hartford - Friday - 10:00 am, 15th Place, 5-2 (melee.gg), Oct 23, 2026 | [8014635](https://www.mtggoldfish.com/deck/8014635) |
| `dimir_reanimator.txt` | Dimir Reanimator | 7.8% | Dimir Uldaros by Adriano Moscato, Arena Championship 13, 5th Place, 9-2 (melee.gg), Oct 24, 2026 | [8019519](https://www.mtggoldfish.com/deck/8019519) |
| `azorius_control.txt` | Azorius Control | 6.3% | Azorius Control by Maxime Auger, $uper $unday RCQ - Standard - SCG CON Hartford - Sunday - 9:30 am, 5-1 (melee.gg), Oct 25, 2026 | [8018102](https://www.mtggoldfish.com/deck/8018102) |
| `izzet_prowess.txt` | Izzet Prowess | 5.1% | Temur Prowess by Chris McMahon, $1K Standard RCQ - SCG CON Hartford - Friday - 10:00 am, 7th Place, 5-2-1 (melee.gg), Oct 23, 2026 | [8014627](https://www.mtggoldfish.com/deck/8014627) |
| `jeskai_artifacts.txt` | Jeskai Artifacts | 4.4% | Jeskai by GLP, $1K Standard RCQ - SCG CON Hartford - Friday - 10:00 am, 13th Place, 5-2 (melee.gg), Oct 23, 2026 | [8014633](https://www.mtggoldfish.com/deck/8014633) |
| `boros_dragons.txt` | Boros Dragons | 4.2% | Boros Dragons by dragonslovetacos, $1K Standard RCQ - SCG CON Hartford - Friday - 10:00 am, 5th Place, 5-2-1 (melee.gg), Oct 23, 2026 | [8014625](https://www.mtggoldfish.com/deck/8014625) |
| `azorius_momo.txt` | Azorius Momo | 3.2% | Azorius Momo by HyPPeR, Standard Challenge 32 2026-10-23 (1), 1st Place, 8-1 (www.mtgo.com), Oct 23, 2026 | [8013459](https://www.mtggoldfish.com/deck/8013459) |
| `rakdos_lizards.txt` | Rakdos Lizards | 3.1% | Rakdos Lizards by yeojlil, Standard Challenge 16 2026-10-14, 4th Place, 4-3 (www.mtgo.com), Oct 14, 2026 | [8000796](https://www.mtggoldfish.com/deck/8000796) |
| `jund_sacrifice.txt` | Jund Sacrifice | 1.8% | Jund Sacrifice by Bernardo Santos, Arena Championship 13, 8th Place, 8-3 (melee.gg), Oct 24, 2026 | [8019522](https://www.mtggoldfish.com/deck/8019522) |
| `dimir_excruciator.txt` | Dimir Excruciator | 1.7% | Dimir Excruciator by VitorCarvalho01, Standard Challenge 32 2026-10-26, 9th Place, 4-2 (www.mtgo.com), Oct 26, 2026 | [8018890](https://www.mtggoldfish.com/deck/8018890) |
| `selesnya_landfall.txt` | Selesnya Landfall | 1.5% | Selesnya Landfall by _Batutinha_, Standard Challenge 16 2026-10-24, 2nd Place, 6-3 (www.mtgo.com), Oct 24, 2026 | [8014894](https://www.mtggoldfish.com/deck/8014894) |
| `boros_dwarves.txt` | Boros Dwarves | 1.4% | Boros Dwarves by Yuuki Ichikawa, Arena Championship 13, 4th Place, 10-2 (melee.gg), Oct 24, 2026 | [8019518](https://www.mtggoldfish.com/deck/8019518) |
| `jeskai_control.txt` | Jeskai Control | 1.3% | Jeskai Lessons by Allen Hobson, $uper $unday RCQ - Standard - SCG CON Los Angeles - Sunday - 9:30 am, 4-2 (melee.gg), Oct 11, 2026 | [7996138](https://www.mtggoldfish.com/deck/7996138) |

```
python tools/coverage_audit.py --decks examples/decks/standard/*.txt                                            # what blocks them, and what to build first
python tools/coverage_audit.py --decks examples/decks/standard/*.txt --baseline examples/decks/standard/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/standard/*.txt --write-baseline examples/decks/standard/baseline.json  # refresh it after building something
```

`baseline.json` works as the Commander one does (`examples/decks/README.md`): the names of the cards the engine cannot play yet, per deck,
and the `tracked decks` workflow fails when a card that played no longer does. The audit's headline for these decks (how many of their
cards play, and how many of the decks play in full) is posted beside Commander's in the Monday comment on the roadmap epic (#453).

**Standard rotates.** A list here is only as current as its header line says (the metagame date, the deck's event and date). When the
format rotates or the metagame moves on, replace the lists rather than adding to them: open the metagame page, take the featured deck of
each of the most played archetypes (the deck page's "Download" gives the plain list), run it through `tools/import_deck.py`, put the
archetype, share, date, event and deck number in the first line, refresh the baseline, and note the rotation in the roadmap. MTGGoldfish
strips accents from card names (`Kili the Resourceful` for `Kíli the Resourceful`); the audit reports such a card as not found, and the
name is put back by hand.

On 2026-10-28, the day the lists were taken: 501 of 900 cards fully playable (56%), none of the fifteen decks in full.
