def patch(p, pairs):
    s = open(p, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    t = s.replace('\r\n', '\n')
    for a, b in pairs:
        assert t.count(a) == 1, (p, a[:90], t.count(a))
        t = t.replace(a, b)
    open(p, 'w', encoding='utf-8', newline='').write(t.replace('\n', nl))


patch('infernal_machine/effects/families/copying.py', [
('''def copy_card(card: Card, changes: CopyChanges | None = None) -> Card:
    """The card of a token that's a copy of `card`, with the changes of its except clause applied."""
    if not card.type_line.startswith("Token"):
        card = dataclasses.replace(card, type_line="Token " + card.type_line)
    return apply_copy_changes(card, changes)
''', '''def copy_of(card: Card, changes: CopyChanges | None = None, *, as_token: bool = False) -> Card:
    """The card that a copy of `card` is (CR 707.2): its copiable values with the changes of an "except" clause (CR 707.9). Every
    copy goes through here, so an except clause means the same thing everywhere. `as_token`: the copy is a token ("create a token
    that's a copy of ...", a copy of a permanent spell, CR 707.10f); otherwise it is not one, even if what it copies is (a clone
    entering as a copy of a token, a creature that becomes a copy of one)."""
    if as_token and not card.type_line.startswith("Token"):
        card = dataclasses.replace(card, type_line="Token " + card.type_line)
    elif not as_token:
        card = dataclasses.replace(card, type_line=card.type_line.removeprefix("Token "))
    return apply_copy_changes(card, changes)
'''),
('game.create_tokens(controller, copy_card((subject or source).card, self.changes), 1)', 'game.create_tokens(controller, copy_of((subject or source).card, self.changes, as_token=True), 1)'),
('game.create_tokens(controller, copy_card(target.attached_to.card, self.changes), 1)', 'game.create_tokens(controller, copy_of(target.attached_to.card, self.changes, as_token=True), 1)'),
('            card = copy_card(target.card, self.changes)', '            card = copy_of(target.card, self.changes, as_token=True)'),
('''        card = chosen.card if chosen.card.type_line.startswith("Token") else dataclasses.replace(chosen.card, type_line="Token " + chosen.card.type_line)
        game.create_tokens(controller, card, 1)''', '''        game.create_tokens(controller, copy_of(chosen.card, as_token=True), 1)'''),
('''            card = target.card if target.card.type_line.startswith("Token") else \\
                dataclasses.replace(target.card, type_line="Token " + target.card.type_line)
            if self.one_by_one:
                card = dataclasses.replace(card, power="1", toughness="1")
            game.create_tokens(controller, card, 1)''', '''            game.create_tokens(controller, copy_of(target.card, CopyChanges(power_toughness=("1", "1")) if self.one_by_one else None, as_token=True), 1)'''),
])

patch('infernal_machine/effects/families/exile_and_return.py', [
('''            card = target.card
            game.create_tokens(controller, card if card.type_line.startswith("Token") else
                               dataclasses.replace(card, type_line="Token " + card.type_line), 1)''', '''            game.create_tokens(controller, copy_of(target.card, as_token=True), 1)'''),
])

patch('infernal_machine/effects/outcomes.py', [('    copy_card,\n', '    copy_of,\n')])
patch('tests/test_copy_except.py', [
    ('from infernal_machine.effects.outcomes import CopyChanges, copy_card', 'from infernal_machine.effects.outcomes import CopyChanges, copy_of'),
])

patch('infernal_machine/game.py', [
('from .effects import (apply_copy_changes, EVENTS,', 'from .effects import (copy_of, CopyChanges, EVENTS,'),
('''            if item.is_copy:  # a copy of a permanent spell becomes a token (CR 707.10f)
                card = dataclasses.replace(card, type_line="Token " + card.type_line.removeprefix("Token "))''',
 '''            if item.is_copy:  # a copy of a permanent spell becomes a token (CR 707.10f)
                card = copy_of(card, as_token=True)'''),
('''        if item.is_copy:  # a copy of an Aura spell becomes a token Aura
            card = dataclasses.replace(card, type_line="Token " + card.type_line.removeprefix("Token "))''',
 '''        if item.is_copy:  # a copy of an Aura spell becomes a token Aura
            card = copy_of(card, as_token=True)'''),
('''        card = source.card if _is_token(source.card) else dataclasses.replace(source.card, type_line="Token " + source.card.type_line)
        for made in self.create_tokens(seat, card, 1):
            made.tapped = True''', '''        for made in self.create_tokens(seat, copy_of(source.card, as_token=True), 1):
            made.tapped = True'''),
('''        card = dead.card
        text = (card.oracle_text + "\\nWhen this token leaves the battlefield, return the exiled card to its owner's graveyard.").strip()
        head, dash, tail = card.type_line.partition("\\u2014")
        spirit = dataclasses.replace(card, type_line=f"Token {head.strip()} {dash} {tail.strip()} Spirit" if dash else f"Token {head.strip()}",
                                     oracle_text=text)
        for made in self.create_tokens(seat, spirit, 1):''', '''        card = dead.card
        spirit = copy_of(card, CopyChanges(add_types=("Spirit",), abilities=(
            "When this token leaves the battlefield, return the exiled card to its owner's graveyard.",)), as_token=True)
        for made in self.create_tokens(seat, spirit, 1):'''),
('''        self.attacking_tokens(seat, dataclasses.replace(card, type_line="Token " + card.type_line), 1, True, "sacrificed")''',
 '''        self.attacking_tokens(seat, copy_of(card, as_token=True), 1, True, "sacrificed")'''),
('''        card = copied.card
        text = (card.oracle_text + f"\\n{keyword}").strip()
        permanent.card = dataclasses.replace(card, type_line=card.type_line.removeprefix("Token "), oracle_text=text)''',
 '''        card = copied.card
        permanent.card = copy_of(card, CopyChanges(abilities=(keyword,)))'''),
('''            card = source.card if _is_token(source.card) else dataclasses.replace(source.card, type_line="Token " + source.card.type_line)
            if haste:
                card = dataclasses.replace(card, oracle_text=(card.oracle_text + "\\nHaste").strip())
            cards.append(card)''', '''            cards.append(copy_of(source.card, CopyChanges(keywords=("haste",)) if haste else None, as_token=True))'''),
('''        card = original.card if _is_token(original.card) else dataclasses.replace(original.card, type_line="Token " + original.card.type_line)
        card = dataclasses.replace(card, oracle_text=(card.oracle_text + "\\nHaste").strip())
        if not_legendary:
            card = dataclasses.replace(card, type_line=card.type_line.replace("Legendary ", ""))
        made = self.create_token_batch(seat, [card] * count)''', '''        card = copy_of(original.card, CopyChanges(keywords=("haste",), not_legendary=not_legendary), as_token=True)
        made = self.create_token_batch(seat, [card] * count)'''),
('''        card = original.card if _is_token(original.card) else dataclasses.replace(original.card, type_line="Token " + original.card.type_line)
        for opponent in self.opponents(seat):''', '''        card = copy_of(original.card, as_token=True)
        for opponent in self.opponents(seat):'''),
('''        permanent.card = apply_copy_changes(dataclasses.replace(copied, type_line=copied.type_line.removeprefix("Token ")), rule.changes)''',
 '''        permanent.card = copy_of(copied, rule.changes)'''),
])
print('ok')
