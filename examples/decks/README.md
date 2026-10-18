# Real decklists for the coverage audit

Three Commander decks that people actually play, used to aim the card-coverage work (issue #428). They are the EDHREC "average deck"
for each commander (public pages, copied as plain card lists on 2026-10-18): the 99 cards most often played with it, so a typical
list, not any one player's. They are **not** in the gauntlet and are not meant as opponents.

| File | Commander | Style |
|---|---|---|
| `atraxa_edhrec_average.txt` | Atraxa, Praetors' Voice | proliferate and poison, four colors |
| `ur_dragon_edhrec_average.txt` | The Ur-Dragon | Dragon tribal, five colors |
| `krenko_edhrec_average.txt` | Krenko, Mob Boss | Goblin tribal, mono red |

```
python tools/coverage_audit.py --decks examples/decks/*.txt        # what blocks them, and what to build first
```

The audit reports each deck's playable share and ranks the pieces of work by the cards they unlock across all of them. Re-run it after
each piece. Playable share (cards the engine fully reads): before #428 work 73 / 300 cards of Atraxa, 64, 66 for Krenko and Ur-Dragon
(68% together); after this round 79, 71, 68 (73%). To add a list, export one from a deck site and run it through
`tools/import_deck.py`.
