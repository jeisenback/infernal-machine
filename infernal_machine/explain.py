"""How the engine read a card, and a check for misreadings (issue #478).

"Fully playable" (`report.unsupported_lines` is empty) means every line was parsed, not that it was parsed *correctly*. `explain` prints
each ability the way the engine holds it, beside the Oracle text, so a wrong reading can be seen; `audit` looks for one kind of wrong
reading by rule. Both are read-only: they run the same parsers the game does and change nothing.

The first rule, `subject-binding`: a triggered ability's effect was bound to *the permanent that set the trigger off* (`OnSubject`), but
the sentence says the card itself does it ("put a +1/+1 counter on this creature"). That is what happened to Skyclave Squid, whose "this
creature can attack this turn as though it didn't have defender" was applied to the land that entered, and to Fearless Fledgling and
Kappa Cannoneer, whose "It gains flying" after "put a counter on this creature" made the counter go on the entering land. Add a rule when a
bug of a new kind turns up, with the card that showed it, and run `tools/explain_card.py --audit` over the pool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .cards import Card
from .effects import activated_abilities, spell_effects, static_abilities, triggered_abilities
from .effects.families.spells_and_misc import OnSubject
from .effects.targets import binding, target_kind
from .report import unsupported_lines

_ITSELF = re.compile(r"\b(?:this (?:creature|artifact|enchantment|permanent|land|planeswalker|equipment|vehicle|aura|saga|battle|card)|CARDNAME)\b", re.I)
_LABEL = re.compile(r"^[A-Z][\w' -]* — ")  # an ability word: "Landfall — "


@dataclass(frozen=True)
class Finding:
    """One thing the audit thinks the engine read wrongly."""
    rule: str
    card: str
    text: str  # the ability, as the card prints it
    effect: str  # the effect as the engine holds it
    why: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.card}: {self.why}\n    {self.text}\n    -> {self.effect}"


def _effect(effect: object, indent: str = "      ") -> list[str]:
    """One line for an effect (and one for what it wraps): its class and fields, what it is bound to, what it targets."""
    bound = binding(effect)
    target = target_kind(effect)
    notes = ([f"binds {bound}"] if bound else []) + ([f"targets {target}"] if target else [])
    lines = [f"{indent}{effect}" + (f"   ({', '.join(notes)})" if notes else "")]
    inner = getattr(effect, "inner", None)
    if inner is not None:
        lines += _effect(inner, indent + "  ")
    return lines


def explain(card: Card) -> str:
    """The card as the engine reads it: its Oracle text, then every ability (triggered, activated, static, the spell's own effects) with
    its effects, what each is bound to, and the lines that were not understood."""
    head = f"{card.name}  {card.mana_cost}  {card.type_line}" + (f"  {card.power}/{card.toughness}" if card.power is not None else "")
    out = [head, ""]
    out += [f"  {line}" for line in card.oracle_text.splitlines()] or ["  (no rules text)"]
    for ability in triggered_abilities(card):
        watch = f"; watches {ability.watch.kind}" + (" you control" if ability.watch.yours else "") if ability.watch else ""
        out += ["", f"  triggered: {ability.text}", f"    event {ability.event}{watch}" + (", optional" if ability.optional else "")
                + (f", if {ability.condition}" if ability.condition else "")]
        out += [line for effect in ability.effects for line in _effect(effect)]
    for ability in activated_abilities(card):
        cost = " ".join(part for part in (ability.mana_cost, "{T}" if ability.tap else "", "sacrifice" if ability.sacrifice else "") if part)
        out += ["", f"  activated: {ability.text}", f"    cost {cost or 'none'}"]
        out += [line for effect in ability.effects for line in _effect(effect)]
    for buff in static_abilities(card):
        out += ["", f"  static: {buff}"]
    if "Instant" in card.type_line or "Sorcery" in card.type_line:
        effects = spell_effects(card)
        out += ["", "  spell: " + ("not understood as a whole" if effects is None else "resolves with")]
        if effects:
            out += [line for effect in effects for line in _effect(effect)]
    problems = unsupported_lines(card)
    out += ["", "  not understood: " + ("; ".join(problems) if problems else "nothing: every line is read")]
    return "\n".join(out)


def audit(card: Card) -> list[Finding]:
    """What the rules think the engine read wrongly about this card (see the module docstring); empty for a card that passes."""
    findings = []
    short = card.name.split(",")[0].split(" // ")[0]
    for ability in triggered_abilities(card):
        body = _LABEL.sub("", ability.text)
        body = body.split(", ", 1)[1] if ", " in body else body  # after the event
        names_itself = _ITSELF.search(body) is not None or (len(short) > 3 and re.search(rf"\b{re.escape(short)}\b", body) is not None)
        if not names_itself:
            continue
        for effect in ability.effects:
            if isinstance(effect, OnSubject) and binding(effect.inner) == "source":
                findings.append(Finding("subject-binding", card.name, ability.text, _effect(effect, "")[0],
                                        "the sentence says the card itself does this, but the effect was bound to the permanent that set the trigger off"))
    return findings
