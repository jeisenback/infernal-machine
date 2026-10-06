---
name: add-mechanic
description: Use when adding or extending a rules mechanic or card-text template in Infernal Machine (effects.py, game.py, bot.py). Covers tests first, the all-or-nothing parse rule, bot behaviour, mutation checks, the bot-game run and the README.
---

# Add a mechanic

Follow in order. Each step has an exit check.

1. **Heartbeat.** Read `.claude/heartbeat.json` and follow CLAUDE.md. Stop if another session is live on this branch.
2. **Scope.** State in two lines what texts the mechanic will read and what it will not. The second line becomes "Not done" in the PR.
3. **Tests first.** Write tests in `tests/test_<mechanic>.py` and watch them fail. Cover the plain case, each rule edge (ties, empty zones, dead players, already-holding guards) and the unsupported cases below.
4. **All or nothing.** The template must understand the whole text. A lone sentence that needs its neighbours (a "take" with no "look", an "Untap that creature." with no target) must leave the card unsupported. Add a test that proves it, and check the card shows in `python -m infernal_machine.report`.
5. **Implement.** Add the template or effect. Reuse existing templates for sub-effects instead of new parsing. Add the bot's choice in `bot.py` if the mechanic asks the player anything; the simplest sensible choice is enough.
6. **Card text.** Texts written from memory (no Scryfall) are a risk. Name each such card in the PR and say it needs checking against real text. Do not guess at wording you cannot state.
7. **Mutation checks.** Break the code on purpose 3 to 6 times, once per rule the tests claim to guard (a tie rule, an order, a guard, a cap, a cleanup). Each break must fail a test. If one passes, tighten the assertion, not the break. Restore the code after each. Record what you broke.
8. **Full suite.** `python -m unittest discover -s tests -t .` passes. Note the total.
9. **Bot games.** If the change touches turn flow, combat, the stack or bot decisions, or adds cards the bots will draw: `python tools/bot_games.py DECKLIST --games 100` with a deck that holds the new cards. All games must finish. Note the average turns.
10. **README.** Add the mechanic to the supported list in the right place, with the exact wordings read and what is not supported. Remove any line that said it was not built.
11. **Heartbeat and commit.** Update the heartbeat after tests pass and after push. Then use the `pr-body` skill if a PR is wanted.

Do not add effects the issue did not ask for.
