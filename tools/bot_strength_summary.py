"""Combine the shards of the weekly bot-strength run and decide whether the bot has regressed (#354).

    python tools/bot_strength_summary.py RESULT.json [RESULT.json ...]

Each file is what `tools/compare_bots.py --json` wrote for one shard: the default bot against the plain bot on the precon
decks. This adds the shards up, prints the win rate with its 95% interval (also to the GitHub job summary when there is
one), and exits 1 only if the whole interval is below 50%: the bot is then reliably worse than a bot with no judgments.
A run that finished no games also fails, since a pass would then mean nothing.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())

from infernal_machine.matchup import wilson  # noqa: E402


def main(paths: list[str]) -> int:
    if not paths:
        print("usage: python tools/bot_strength_summary.py RESULT.json [...]", file=sys.stderr)
        return 2
    results = [json.load(open(path, encoding="utf-8")) for path in paths]
    wins, games, errors = (sum(r[key] for r in results) for key in ("wins", "games", "errors"))
    if games == 0:
        print("No games finished.")
        return 1
    low, high = wilson(wins, games)
    text = (f"Default bot [{results[0]['features']}] against the plain bot: {wins}/{games} = {wins / games:.1%} "
            f"(95% interval {low:.1%}-{high:.1%}) over {len(results)} shards; {errors} games crashed or timed out and are not counted.")
    verdict = "REGRESSION: the bot loses to a bot with no judgments." if high < 0.5 else "No regression."
    print(text)
    print(verdict)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Bot strength\n\n{text}\n\n**{verdict}**\n")
    return 1 if high < 0.5 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
