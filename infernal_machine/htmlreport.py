"""An analysis (`analyze.Analysis`) as one self-contained HTML page (issue #447).

    python -m infernal_machine.analyze DECKLIST [OPPONENT ...] --html report.html

The same numbers the markdown report prints, drawn: the mana base as bars, the goldfish's damage by turn as a chart, each card's
value with its error as a whisker (the table sorts by a click on a header), the matchups as win rates with their 95% intervals. A
section whose numbers were not kept (an older saved run) falls back to its text. No scripts load from anywhere: CSS and a few lines
of JS are inline, so the file can be mailed or opened offline. It follows the reader's light or dark setting.
"""

from __future__ import annotations

import re
from html import escape
from typing import TYPE_CHECKING, Any

from .coverage import FIXES_SHOWN, verdict
from .matchup import wilson

if TYPE_CHECKING:
    from .analyze import Analysis, Section

_CSS = """
:root{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#deded8;--good:#2a7d4f;--bad:#b3402a;--bar:#3b6ea8;--warn:#a8741a}
@media (prefers-color-scheme: dark){:root:not([data-theme=light]){--bg:#17171a;--fg:#e8e8e3;--muted:#9a9a93;--card:#202024;--line:#34343a;--good:#5ec08a;--bad:#e8806a;--bar:#6ea4e0;--warn:#d9a13d}}
:root[data-theme=dark]{--bg:#17171a;--fg:#e8e8e3;--muted:#9a9a93;--card:#202024;--line:#34343a;--good:#5ec08a;--bad:#e8806a;--bar:#6ea4e0;--warn:#d9a13d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 48px}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:0 0 12px}
.sub{color:var(--muted);margin:0 0 20px}section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.tile b{display:block;font-size:1.35rem}.tile span{color:var(--muted);font-size:.85rem}
table{border-collapse:collapse;width:100%}th,td{padding:5px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
th{color:var(--muted);font-weight:600;font-size:.85rem}th[data-sort]{cursor:pointer}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.barbox{position:relative;height:14px;background:color-mix(in srgb,var(--line) 55%,transparent);border-radius:7px;min-width:140px}
.bar{position:absolute;top:0;bottom:0;left:0;background:var(--bar);border-radius:7px}.whisker{position:absolute;top:6px;height:2px;background:var(--fg);opacity:.9}
.tick{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--fg);opacity:.35}
.good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;font-size:.82rem}
.verdict h2{font-size:1.6rem;margin:0}.verdict .sub{margin:2px 0 12px}.verdict h3{font-size:1rem;margin:18px 0 6px}.pbar{height:10px;border-radius:5px;background:color-mix(in srgb,var(--line) 55%,transparent);overflow:hidden}.pbar i{display:block;height:100%;background:var(--bar)}.pbar.full i{background:var(--good)}ol.fixes{padding-left:1.4rem;margin:0}ol.fixes li{padding:6px 0;border-bottom:1px solid var(--line)}code{display:block;overflow-x:auto;font:.82rem/1.4 ui-monospace,Menlo,Consolas,monospace}.chips{margin:4px 0 2px}.chips span{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:0 6px;margin:0 4px 4px 0;font-size:.85rem}.gain{color:var(--muted);font-size:.85rem}.verdict summary{cursor:pointer;min-height:44px;display:flex;align-items:center}.note{border-left:4px solid var(--warn);padding:8px 12px;background:var(--bg);margin:0 0 12px}.foot{color:var(--muted);font-size:.85rem;margin-top:24px}
svg text{fill:var(--muted);font-size:11px}svg .b{fill:var(--bar)}@media (max-width:600px){td,th{padding:4px 5px}.barbox{min-width:80px}}
"""

_JS = """
document.querySelectorAll('table.sortable').forEach(function(t){t.querySelectorAll('th[data-sort]').forEach(function(h,i){h.addEventListener('click',function(){
var b=t.tBodies[0],rows=Array.prototype.slice.call(b.rows),k=h.cellIndex,asc=h.dataset.dir!=='asc';h.dataset.dir=asc?'asc':'desc';
rows.sort(function(x,y){var a=x.cells[k].dataset.v||x.cells[k].textContent,c=y.cells[k].dataset.v||y.cells[k].textContent,n=parseFloat(a),m=parseFloat(c);
var r=isNaN(n)||isNaN(m)?a.localeCompare(c):n-m;return asc?r:-r});rows.forEach(function(r){b.appendChild(r)})})})});
"""


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _tile(value: str, label: str) -> str:
    return f'<div class="tile"><b>{escape(value)}</b><span>{escape(label)}</span></div>'


def _bar(low: float, high: float, scale_low: float, scale_high: float, mark: float | None = None, centre: float | None = None) -> str:
    """A horizontal bar from `scale_low` to `high`, with a whisker from `low` to `high` (a confidence interval), over a track that
    runs from `scale_low` to `scale_high`; `mark` draws a tick (the 50% line)."""
    span = (scale_high - scale_low) or 1.0

    def at(x: float) -> float:
        return max(0.0, min(100.0, (x - scale_low) / span * 100))

    point = centre if centre is not None else (low + high) / 2
    return ('<div class="barbox">' + (f'<i class="tick" style="left:{at(mark):.1f}%"></i>' if mark is not None else "")
            + f'<i class="bar" style="width:{at(point):.1f}%"></i>'
            + f'<i class="whisker" style="left:{at(low):.1f}%;width:{max(0.0, at(high) - at(low)):.1f}%"></i></div>')


def _signed_bar(delta: float, error: float, limit: float) -> str:
    """A bar for a change around zero, in the middle of the track, with a whisker for two standard errors."""
    half = limit or 1.0

    def at(x: float) -> float:
        return 50 + max(-half, min(half, x)) / half * 50

    left, right = sorted((at(0.0), at(delta)))
    colour = "var(--good)" if delta > 0 else "var(--bad)"
    return ('<div class="barbox"><i class="tick" style="left:50%"></i>'
            f'<i class="bar" style="left:{left:.1f}%;width:{right - left:.1f}%;background:{colour}"></i>'
            f'<i class="whisker" style="left:{at(delta - 2 * error):.1f}%;width:{at(delta + 2 * error) - at(delta - 2 * error):.1f}%"></i></div>')


def _fallback(section: "Section") -> str:
    body = escape(section.body)
    return f"<pre>{body}</pre>" if section.code else f"<p>{body}</p>"


def _mana_base(section: "Section") -> str:
    colors = section.data.get("colors")
    if not colors:
        return _fallback(section)
    rows = []
    top = max([max(line["have"], line["needed"]) for line in colors.values()] + [1])  # one scale for every color, so the bars compare
    for color, line in colors.items():
        short = line.get("short", 0)
        rows.append(f'<tr><td>{escape(color)}</td><td class="n" data-v="{line["have"]}">{line["have"]}</td>'
                    f'<td class="n" data-v="{line["needed"]}">{line["needed"]}</td>'
                    f'<td>{_bar(line["have"], line["have"], 0, top, mark=line["needed"], centre=line["have"])}</td>'
                    f'<td class="{"bad" if short else "good"}">{f"short by {short}" if short else "enough"}</td></tr>')
    return (f'<p>{section.data.get("lands", "?")} lands. Sources of each color the deck has; the tick is the number it needs.</p>'
            '<table><thead><tr><th>Color</th><th class="n">Sources</th><th class="n">Needed</th><th></th><th></th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def _goldfish(section: "Section") -> str:
    data = section.data
    damage = data.get("damage")
    if not damage:
        return _fallback(section)
    turns = sorted(damage, key=int)
    top = max(damage.values()) or 1.0
    width, height, gap = 40, 110, 6
    bars = []
    for i, turn in enumerate(turns):
        h = damage[turn] / top * (height - 28)
        x = i * (width + gap) + 4
        bars.append(f'<rect class="b" x="{x}" y="{height - 16 - h:.1f}" width="{width}" height="{h:.1f}" rx="3"/>'
                    f'<text x="{x + width / 2}" y="{height - 4}" text-anchor="middle">T{escape(str(turn))}</text>'
                    f'<text x="{x + width / 2}" y="{height - 20 - h:.1f}" text-anchor="middle">{damage[turn]:.1f}</text>')
    chart = (f'<svg viewBox="0 0 {len(turns) * (width + gap) + 8} {height}" role="img" aria-label="Average combat damage dealt by turn" '
             f'style="max-width:{len(turns) * (width + gap) + 8}px;width:100%">' + "".join(bars) + "</svg>")
    drops = data.get("land_drops") or {}
    drop_row = "".join(f"<td class=\"n\">{_pct(drops[t])}</td>" for t in sorted(drops, key=int))
    return (f'<p>{data.get("games", "?")} games, {data.get("turns", "?")} turns. Average combat damage dealt so far, if nothing blocks it.</p>'
            + chart + ("<table><thead><tr><th>Land drop made by turn</th>" + "".join(f'<th class="n">T{t}</th>' for t in sorted(drops, key=int))
                       + f"</tr></thead><tbody><tr><td>share of games</td>{drop_row}</tr></tbody></table>" if drops else ""))


def _tuning(section: "Section") -> str:
    data = section.data
    cards = data.get("cards")
    if not cards:
        return _fallback(section)
    limit = max((abs(c["delta"]) + 2 * c["error"] for c in cards), default=1.0)
    rows = []
    for c in cards:
        clear = abs(c["delta"]) > 2 * c["error"]
        sign = "good" if c["delta"] > 0 else "bad"
        rows.append(f'<tr><td>{escape(c["name"])}</td><td class="n" data-v="{c["copies"]}">{c["copies"]}</td>'
                    f'<td class="n {sign if clear else ""}" data-v="{c["delta"]}">{c["delta"]:+.2f} &plusmn; {2 * c["error"]:.2f}</td>'
                    f'<td>{_signed_bar(c["delta"], c["error"], limit)}</td>'
                    f'<td class="n" data-v="{c["seen"]}">{_pct(c["seen"])}</td><td class="n" data-v="{c["cast_when_seen"]}">{_pct(c["cast_when_seen"])}</td>'
                    f'<td>{escape(c.get("note", ""))}</td></tr>')
    out = [f'<p>{data.get("games", "?")} games, {data.get("turns", "?")} turns. Average game value {data.get("baseline", "?")} '
           "(mana spent on spells + damage by the last turn). What each card adds per game, replayed with the card as a blank; the line "
           "is two standard errors, and a number that is not coloured is not clearly different from zero. Click a header to sort.</p>",
           '<table class="sortable"><thead><tr><th data-sort>Card</th><th class="n" data-sort>Copies</th><th class="n" data-sort>Adds per game</th>'
           '<th></th><th class="n" data-sort>Seen</th><th class="n" data-sort>Cast if seen</th><th>Note</th></tr></thead><tbody>'
           + "".join(rows) + "</tbody></table>"]
    lands = data.get("lands") or {}
    if lands:
        out.append("<h3>Land count</h3><table><thead><tr><th>Change</th><th class=\"n\">Effect on value</th></tr></thead><tbody>"
                   + "".join(f'<tr><td>{int(k):+d} lands</td><td class="n">{v["delta"]:+.2f} &plusmn; {2 * v["error"]:.2f}</td></tr>' for k, v in lands.items())
                   + "</tbody></table>")
    swaps = data.get("swaps") or []
    if swaps:
        out.append("<h3>Swaps, best first</h3><table><thead><tr><th>Card</th><th>Replaces</th><th class=\"n\">Effect</th><th>Note</th></tr></thead><tbody>"
                   + "".join(f'<tr><td>{escape(s["card"])}</td><td>{escape(s["replaces"])}</td><td class="n">{s["delta"]:+.2f} &plusmn; {2 * s["error"]:.2f}</td>'
                             f'<td>{escape(s.get("note", ""))}</td></tr>' for s in swaps) + "</tbody></table>")
    return "".join(out)


def _matchups(section: "Section") -> str:
    opponents = section.data.get("opponents")
    if not opponents:
        return _fallback(section)
    rows = []
    for name, record in sorted(opponents.items(), key=lambda kv: kv[1]["wins"] / (kv[1]["games"] or 1)):
        games, wins = record["games"], record["wins"]
        low, high = wilson(wins, games)
        rate = wins / games if games else 0.0
        clear = high < 0.5 or low > 0.5
        rows.append(f'<tr><td>{escape(name)}</td><td class="n" data-v="{rate}">{_pct(rate)}</td>'
                    f'<td>{_bar(low, high, 0.0, 1.0, mark=0.5, centre=rate)}</td>'
                    f'<td class="n">{_pct(low)}&ndash;{_pct(high)}</td><td class="n" data-v="{games}">{wins} of {games}</td>'
                    f'<td class="{("good" if rate > 0.5 else "bad") if clear else ""}">{("ahead" if rate > 0.5 else "behind") if clear else "too close to say"}</td></tr>')
    return (f'<p>Win rate against each opponent ({section.data.get("pod", 2)} players a game), with the 95% interval; the tick is 50%.</p>'
            '<table class="sortable"><thead><tr><th data-sort>Opponent</th><th class="n" data-sort>Win rate</th><th></th><th class="n">Interval</th>'
            '<th class="n" data-sort>Wins</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


def _bracket(section: "Section") -> str:
    return f"<p>{escape(section.body)}</p>"


def _combos(section: "Section") -> str:
    combos = section.data.get("combos")
    if combos is None:
        return _fallback(section)
    if not combos:
        return f"<p>{escape(section.body)}</p>"
    rows = []
    for combo in combos:
        cards = escape(" + ".join(combo["cards"])) + (f' <small>(needs {escape(", ".join(combo["requires"]))})</small>' if combo.get("requires") else "")
        blocked = combo.get("blocked", [])
        cannot = escape("can't play " + ", ".join(blocked))
        engine = '<td class="good">plays</td>' if not blocked else f'<td class="bad">{cannot}</td>'
        rows.append(f'<tr><td>{cards}</td><td>{escape(", ".join(combo["produces"]))}</td><td>{escape(combo.get("mana") or "-")}</td>'
                    f'<td>{escape(combo["tag"])}</td><td class="n" data-v="{combo["popularity"]}">{combo["popularity"]}</td>{engine}</tr>')
    return (f"<p>{len(combos)} combo{'s' if len(combos) != 1 else ''} the deck holds, from Commander Spellbook; the last column says whether "
            "the engine plays every piece.</p>"
            '<table class="sortable"><thead><tr><th data-sort>Cards</th><th data-sort>Produces</th><th>Mana</th><th data-sort>Tag</th>'
            '<th class="n" data-sort>Decks</th><th>Engine</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


def _fix_rows(fixes: list[dict]) -> str:
    rows = []
    for fix in fixes:
        more = fix["unlocks"] - len(fix["cards"])
        chips = "".join(f"<span>{escape(name)}</span>" for name in fix["cards"]) + (f"<span>+{more} more</span>" if more > 0 else "")
        rows.append(f'<li><code>{escape(fix["line"])}</code><div class="chips">{chips}</div>'
                    f'<span class="gain">+{fix["unlocks"]} card{"s" if fix["unlocks"] != 1 else ""}, {_pct(fix["playable_after"])} playable after</span></li>')
    return "".join(rows)


def _blocked_item(card: dict) -> str:
    copies = f' (x{card["copies"]})' if card["copies"] > 1 else ""
    more = f' <span class="gain">+{card["more"]} more line{"s" if card["more"] != 1 else ""}</span>' if card.get("more") else ""
    return f'<li><b>{escape(card["name"])}</b>{copies}: <code>{escape(card["line"])}</code>{more}</li>'


def _verdict(section: "Section") -> str:
    """The deck's verdict, first on the page (issue #477): what the engine can play, and the lines to build to play the rest."""
    data = section.data
    if "cards" not in data:  # a run saved before the verdict was kept: its text
        return f"<section><h2>{escape(section.title)}</h2><p>{escape(section.body)}</p></section>"
    cards, playable = data["cards"], data["playable"]
    if not cards:
        return '<section class="verdict"><h2>No cards</h2><p class="sub">The deck has no cards to check.</p></section>'
    blocked = cards - playable
    share = playable / cards
    headline = re.sub(r"\d+", lambda m: f'<span class="bad">{m[0]}</span>', escape(verdict(blocked)), count=1)
    label = f"{share:.0%} of cards fully playable"
    heading_class = "" if blocked else ' class="good"'
    out = [f'<section class="verdict"><h2{heading_class}>{headline}</h2>',
           f'<p class="sub">{playable} of {cards} cards fully playable</p>',
           f'<div class="pbar{"" if blocked else " full"}" role="img" aria-label="{escape(label)}"><i style="width:{share * 100:.1f}%"></i></div>']
    if not blocked:
        out.append("<p>Every card is one the engine understands.</p>")
    fixes = data.get("fixes", [])
    if fixes:
        out.append("<h3>Fix these lines to unlock this deck</h3>")
        out.append(f'<ol class="fixes">{_fix_rows(fixes[:FIXES_SHOWN])}</ol>')
        if len(fixes) > FIXES_SHOWN:
            out.append(f'<details><summary>Show {len(fixes) - FIXES_SHOWN} more</summary>'
                       f'<ol class="fixes" start="{FIXES_SHOWN + 1}">{_fix_rows(fixes[FIXES_SHOWN:])}</ol></details>')
    if data.get("unplayable"):
        items = "".join(_blocked_item(c) for c in data["unplayable"])
        out.append(f"<details><summary>All {len(data['unplayable'])} blocked cards</summary><ul>{items}</ul></details>")
    out.append("</section>")
    return "".join(out)


_RENDER = {"manabase": _mana_base, "goldfish": _goldfish, "tuning": _tuning, "matchups": _matchups, "bracket": _bracket, "combos": _combos}


def _tiles(analysis: "Analysis") -> str:
    by_part = {s.part: s.data for s in analysis.sections if s.part}
    tiles = [_tile(analysis.kind, "format")]
    if "floor" in by_part.get("bracket", {}):
        tiles.append(_tile(f'Bracket {by_part["bracket"]["floor"]}+', "at least, from its cards" + (" and combos" if by_part["bracket"].get("combos") else "")))
    if "combos" in by_part.get("combos", {}):
        tiles.append(_tile(str(len(by_part["combos"]["combos"])), "combos it holds"))
    if "lands" in by_part.get("manabase", {}):
        short = sum(c.get("short", 0) for c in by_part["manabase"].get("colors", {}).values())
        tiles.append(_tile(str(by_part["manabase"]["lands"]), "lands" + (f", {short} sources short" if short else "")))
    gold = by_part.get("goldfish", {})
    if "mulligan_rate" in gold:
        tiles.append(_tile(_pct(gold["mulligan_rate"]), "mulligans"))
        tiles.append(_tile(_pct(gold["on_curve"]), "of turns played on curve"))
    opponents = by_part.get("matchups", {}).get("opponents")
    if opponents:
        wins = sum(r["wins"] for r in opponents.values())
        games = sum(r["games"] for r in opponents.values())
        tiles.append(_tile(_pct(wins / games) if games else "-", f"won of {games} matchup games"))
    return '<div class="tiles">' + "".join(tiles) + "</div>"


def render_html(analysis: "Analysis", settings: str = "") -> str:
    """The analysis as an HTML document."""
    parts = []
    for section in analysis.sections:
        if section.part == "playability":  # first: it qualifies everything below
            parts.append(_verdict(section))
    parts.append(_tiles(analysis))
    if analysis.changes:
        parts.append(f"<section><h2>What changed</h2><pre>{escape(analysis.changes)}</pre></section>")
    for section in analysis.sections:
        if section.part and section.part != "playability":
            render: Any = _RENDER.get(section.part, _fallback)
            parts.append(f"<section><h2>{escape(section.title)}</h2>{render(section)}</section>")
    foot = []
    if analysis.skipped:
        foot.append("Left out: " + "; ".join(analysis.skipped) + ".")
    timings = ", ".join(f"{s.title.lower()} {s.seconds:.1f}s" for s in analysis.sections if s.seconds >= 0.05)
    foot.append(f"Took {analysis.seconds:.0f} seconds" + (f" ({timings})" if timings else "") + ".")
    title = f"Analysis of {analysis.name}"
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{_CSS}</style></head><body><main><h1>{escape(title)}</h1>"
            f'<p class="sub">{escape(analysis.kind)} deck.{(" " + escape(settings)) if settings else ""}</p>'
            + "".join(parts) + f'<p class="foot">{escape(" ".join(foot))}</p></main><script>{_JS}</script></body></html>\n')
