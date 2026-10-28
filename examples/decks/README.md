# Real decklists for the coverage audit

The Standard decks are in `standard/` (its README says where they come from); this page is the Commander ones.

Fifteen Commander decks that people actually play, used to aim the card-coverage work (issues #428, #475). Each is the EDHREC "average
deck" for its commander (public pages, copied as plain card lists: Atraxa, Ur-Dragon and Krenko on 2026-10-18, the rest on 2026-10-21):
the 99 cards most often played with it, so a typical list, not any one player's. They are **not** in the gauntlet and are not meant as
opponents. The modelled decks that stood in for some of them until 2026-10-21 (built from the most played cards, which the engine already
plays best, so they read 93-99% playable) are gone, and so is the tool that built them.

| File | Commander | Style |
|---|---|---|
| `atraxa_edhrec_average.txt` | Atraxa, Praetors' Voice | proliferate and poison, four colors |
| `ur_dragon_edhrec_average.txt` | The Ur-Dragon | Dragon tribal, five colors |
| `krenko_edhrec_average.txt` | Krenko, Mob Boss | Goblin tribal, mono red |
| `yuriko_edhrec_average.txt` | Yuriko, the Tiger's Shadow | ninjas and tempo, Dimir |
| `edgar_markov_edhrec_average.txt` | Edgar Markov | Vampire tokens and aristocrats, Mardu |
| `niv_mizzet_edhrec_average.txt` | Niv-Mizzet, Parun | spellslinger, Izzet |
| `ashling_edhrec_average.txt` | Ashling, the Limitless | Elementals and blink, mono red |
| `giada_edhrec_average.txt` | Giada, Font of Hope | Angel tribal, mono white |
| `jace_multiverse_architect_edhrec_average.txt` | Jace, Multiverse Architect | control, mono blue |
| `kinnan_edhrec_average.txt` | Kinnan, Bonder Prodigy | big mana, Simic |
| `korvold_edhrec_average.txt` | Korvold, Fae-Cursed King | sacrifice and treasure, Jund |
| `pantlaza_edhrec_average.txt` | Pantlaza, Sun-Favored | Dinosaurs and discover, Naya |
| `sisay_edhrec_average.txt` | Sisay, Weatherlight Captain | legendary toolbox, five colors |
| `tymna_thrasios_edhrec_average.txt` | Tymna the Weaver and Thrasios, Triton Hero | partners, four-color value (EDHREC publishes this one as 98 cards; kept as published) |
| `yshtola_edhrec_average.txt` | Y'shtola, Night's Blessed | life loss and draw, Esper |

```
python tools/coverage_audit.py --decks examples/decks/*.txt        # what blocks them, and what to build first
```

To add a list, export one from a deck site (or copy an EDHREC average deck) and run it through `tools/import_deck.py`; record the source and date here.

## The baseline (#475)

`baseline.json` keeps, for each deck here, the names of the cards the engine cannot play yet. It is how the tracked decks stay honest:

```
python tools/coverage_audit.py --decks examples/decks/*.txt --baseline examples/decks/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/*.txt --write-baseline examples/decks/baseline.json  # refresh it after building something
```

A card that played in the baseline and does not now is a regression (a parser change, or a card whose Oracle text changed) and fails the
check, naming the card. A card that now plays is only a reminder to refresh the file. A deck with no entry is recorded, not failed; an entry
whose deck was not checked fails (a deck file that went missing must not read as "nothing got worse"). Every coverage pull request reports the
decks' playable share next to the pool's, and refreshes the baseline in the same commit as the cards it unlocks.

The `tracked decks` workflow (`.github/workflows/tracked-decks.yml`) runs that check on every pull request that touches `infernal_machine/` or these
decks, and every Monday. A regression, a baseline deck that was not checked, or a deck file that cannot be read fails it. The Monday run also
keeps one comment up to date on the roadmap epic (#453) with each deck's share and the five pieces of work that unlock the most cards.

The audit reports each deck's playable share and ranks the pieces of work by the cards they unlock across all of them. Re-run it after
each piece. Playable share of the first three (Atraxa, Krenko, Ur-Dragon): before #428 work 73, 64, 66 of 100 (68% together); after the
first round 79, 71, 68 (73%); after the second 79, 73, 71 (74%); on 2026-10-21, after the library search family (#495), 80, 75, 74 (76%).
