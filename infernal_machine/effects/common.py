"""Shared by every part of the package: rules text as lines and sentences, and the regex pieces the others build on."""

from __future__ import annotations

import re
from functools import lru_cache

from ..cards import Card
from ..characteristics import Modifier


_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


_VOTE_PREFIX = r"(?:[A-Z][\w' -]* \u2014 )?"  # "Will of the council — ", "Council's dilemma — "


_N = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+|X)"
_N_FIXED = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"  # a number that is never X, for an effect that reads it as a plain int


_REMINDER = re.compile(r"\s*\([^)]*\)")


_SELF = (r"(?:CARDNAME|it|this (?:spell|creature|artifact|enchantment|land|planeswalker|permanent"
         r"|Aura|Equipment|Class|Vehicle|Saga|Room|token|emblem))")  # "this emblem": Chandra, Torch of Defiance's


Quantity = int | str  # a number, or the "X", "2X", "hX", "hX+" the game fills in when the spell resolves (Game.amount)


def _count(word: str) -> Quantity:
    """A number from rules text; "X" stays "X" ("twice X" is "2X") and the game fills it in (Game.amount)."""
    lowered = word.lower()  # some patterns see text that was lowercased first ("put X +1/+1 counters on it")
    if lowered == "x":
        return "X"
    if lowered == "twice x":
        return "2X"
    if lowered in ("half x", "half x down"):
        return "hX"
    if lowered == "half x up":
        return "hX+"
    return int(word) if word.isdigit() else _NUMBERS[lowered]


def _number(word: str) -> int:
    """A number from rules text for an effect that has no X: its template matches `_N_FIXED`, so the word is never "X"."""
    value = _count(word)
    assert isinstance(value, int), f"{word!r} is not a fixed number; the template should match _N_FIXED"
    return value


_WORDS = {1: "a", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
_KEYWORD_RULES = [  # a keyword line and the rules text it stands for (the reminder text, put to work)
    (re.compile(r"Outlast ((?:\{[^}]+\})+)"), lambda m: f"{m[1]}, {{T}}: Put a +1/+1 counter on this creature. Activate only as a sorcery."),
    (re.compile(r"Fabricate (\d+)"), lambda m: "When this creature enters, choose one \u2014\n"
        f"\u2022 Put {_WORDS[int(m[1])]} +1/+1 {'counter' if m[1] == '1' else 'counters'} on it.\n"
        f"\u2022 Create {_WORDS[int(m[1])]} 1/1 colorless Servo artifact creature {'token' if m[1] == '1' else 'tokens'}."),
    (re.compile(r"Soulshift (\d+)"), lambda m: f"When this creature dies, you may return target Spirit card with mana value {m[1]} or less from your graveyard to your hand."),
    (re.compile(r"Modular (\d+)"), lambda m: f"This creature enters with {_WORDS[int(m[1])]} +1/+1 {'counter' if m[1] == '1' else 'counters'} on it.\n"
        "When this creature dies, you may put a +1/+1 counter on target artifact creature for each +1/+1 counter on this creature."),
    (re.compile(r"Evolve"), lambda m: "Whenever a creature you control enters, if that creature has greater power or toughness than this creature, "
        "put a +1/+1 counter on this creature."),
    (re.compile(r"Mentor"), lambda m: "Whenever this creature attacks, put a +1/+1 counter on target attacking creature with lesser power."),
    (re.compile(r"Bargain"), lambda m: "Kicker\u2014Sacrifice an artifact, enchantment, or token."),  # CR 702.166: an optional additional cost, read as a kicker
    (re.compile(r"Bloodthirst (\d+)"), lambda m: f"If an opponent was dealt damage this turn, this creature enters with {_WORDS[int(m[1])]} +1/+1 "
        f"{'counter' if m[1] == '1' else 'counters'} on it."),
    (re.compile(r"Mobilize (\d+)"), lambda m: f"Whenever this creature attacks, create {_WORDS[int(m[1])]} tapped and attacking 1/1 red Warrior "
        f"creature {'token' if m[1] == '1' else 'tokens'}. Sacrifice them at the beginning of the next end step."),
    (re.compile(r"Transmute ((?:\{[^}]+\})+)"), lambda m: f"{m[1]}, Discard this card: Search your library for a card with the same mana value as "
        "this card, reveal it, put it into your hand, then shuffle. Activate only as a sorcery."),
    (re.compile(r"Renown (\d+)"), lambda m: "When this creature deals combat damage to a player, if it isn't renowned, put "
        f"{_WORDS[int(m[1])]} +1/+1 {'counter' if m[1] == '1' else 'counters'} on it and it becomes renowned."),
]


def _expand_keywords(text: str) -> str:
    lines = []
    for line in text.splitlines():
        for pattern, rules in _KEYWORD_RULES:
            if m := pattern.fullmatch(line.strip()):
                line = rules(m)
                break
        lines.append(line)
    return "\n".join(lines)


def _gift_wording(text: str) -> str:
    """A promised gift works like a free kicker: "if the gift was promised" reads as "if this spell was kicked", and a bargain
    (the sacrifice paid as the spell is cast) the same: "if this spell was bargained"."""
    text = text.replace("the gift was promised", "this spell was kicked").replace("the gift wasn't promised", "this spell wasn't kicked")
    return re.sub(r"\b(this spell|it) (was|wasn't) bargained\b", r"\1 \2 kicked", text)  # Bargain is an optional cost like a kicker


def _rules_text(card: Card) -> str:
    """Oracle text without reminder text, with the card's own name as CARDNAME.

    Legendary cards often call themselves by their short name ("Omnath" for
    "Omnath, Locus of Rage", "Kaalia" for "Kaalia of the Vast"), and double-faced cards by their front face's name.
    """
    text = _gift_wording(_expand_keywords(_REMINDER.sub("", card.oracle_text)))
    front = card.name.split(" // ")[0]
    short = front.split(",")[0]
    if "," not in front and "Legendary" in card.type_line and " " in front and front.split(" ")[0] not in ("The", "A", "An"):
        short = front.split(" ")[0]  # "Kaalia" for Kaalia of the Vast, "Edgar" for Edgar Markov
    for name in dict.fromkeys((card.name, front, front.split(",")[0], short)):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "CARDNAME", text)
    text = _INFINITY_LINE.sub(r"\1, if CARDNAME is harnessed, ", text)
    text = _POWER_UP_LINE.sub(r"\1 Power-up.", text)
    return _join_modes(_MAX_SPEED_LINE.sub(r"\1 Activate only if your speed is 4.", text))


# "Max speed — {T}: Add {R}." is the ability only while your speed is 4 (CR 702.178): read as the ability with that condition.
_MAX_SPEED_LINE = re.compile(r"^Max speed \u2014 (\{.*\.)$", re.M)


# "Power-up \u2014 {5}{W}{W}: ..." is the ability with the marker sentence "Power-up." (ActivatedAbility.power_up): it can be activated
# only once, and costs its source's mana cost less if that entered this turn (the reminder text is gone by then).
_POWER_UP_LINE = re.compile(r"^Power-up \u2014 (\{.*\.)$", re.M)


# An Infinity Stone's "\u221e \u2014 At the beginning of your end step, ..." works only once it is harnessed: read as the trigger with
# that intervening "if" (The Mind Stone).
_INFINITY_LINE = re.compile(r"^\u221e \u2014 (At the beginning of [^,]+), ", re.M)


# "When this creature enters, choose one —" and "{T}: Choose one —" are followed by their modes on separate lines.
_MODAL_LEAD = re.compile(r".+[,:] choose (?:one or both|one or more|up to one|one(?: that hasn't been chosen this turn)?|two|three) \u2014"
                         r"|.+, choose one that hasn't been chosen this turn\."  # Lita, Little Orphan Amphibian: a period, not a dash
                         r"|.+, you may choose two\. Each mode must target a different player\.", re.I)


_TABLE_ROW = re.compile(r"\d+(?:\u2014\d+)? \| ")


_MODE_LABEL = re.compile(r"^\u2022 [A-Z][A-Za-z']*(?: (?:[A-Z][A-Za-z']*|a|an|the|of|to)){0,5} \u2014 ")


SIEGE_MODE = re.compile(r"^\u2022 (Khans|Dragons) \u2014 (.+)$")  # Fate Reforged's Sieges: only the chosen one is the permanent's (Game._enter)


def _join_modes(text: str) -> str:
    """Put the modes of a modal triggered or activated ability on its own line, so it is one ability like any other
    ("When ... enters, choose one — \u2022 Scry 2. \u2022 You gain 3 life."). A modal spell keeps its lines."""
    lines: list[str] = []
    joining = False
    for line in text.splitlines():
        if m := SIEGE_MODE.match(line.strip()):  # a Siege: "\u2022 Khans \u2014 At the beginning of ..." is an ability of its own
            lines.append(m[2])
            joining = False
            continue
        line = _MODE_LABEL.sub("\u2022 ", line.strip()) if line.strip().startswith("\u2022 ") else line  # "\u2022 Sell Contraband \u2014 Create ..."
        if joining and line.strip().startswith("\u2022 "):
            lines[-1] += " " + line.strip()
            continue
        if lines and _TABLE_ROW.match(line.strip()):  # "1\u20149 | Create a Treasure token.": a row of the die roll above (CR 706.2)
            lines[-1] += " " + line.strip()
            continue
        joining = _MODAL_LEAD.fullmatch(line.strip()) is not None
        lines.append(line)
    return "\n".join(lines)


def rules_lines(card: Card) -> list[str]:
    """The card's rules text, one ability per line, as the other functions here see it."""
    return list(_rules_lines(card))


@lru_cache(maxsize=None)
def _rules_lines(card: Card) -> tuple[str, ...]:
    return tuple(line.strip() for line in _rules_text(card).splitlines() if line.strip())


_WHOLE_LINE = re.compile(
    r'[Yy]ou get an emblem with "[^"]+"\.?'  # an emblem's text is sentences of its own, kept inside the quotes (Elspeth, Sun's Champion)
    r"|"
    r"[Rr]eveal the top (?:two|three|four|five|six|seven|eight|\d+) cards of your library\. Put all [A-Za-z]+(?: creature)? cards"
    r"(?: with mana value \d+ or less)? (?:revealed this way|from among them) (?:into your hand|onto the battlefield) and the rest on the "
    r"bottom of your library in (?:any|a random) order\."  # Goblin Ringleader, Muxus
    r"|You may discard a card or sacrifice a land\. If you do, draw (?:a card|two cards)\."  # Highway Robbery
    r"|[Yy]ou may discard a card\. (?:If|When) you do, (?!draw )[^\n]+"  # Party Thrasher, Inti: the rest of the line is what it does
    r"|Each player looks at the top \w+ cards of their library and may reveal a land card and/or an instant or sorcery card from "
    r"among them\. Each player puts the cards they revealed this way into their hand and the rest on the bottom of their library in a "
    r"random order\."  # Explore the Vastlands
    r"|Then that permanent's controller may sacrifice a land of their choice\. If the player does, they may copy this spell and may "
    r"choose a new target for that copy\."  # Chain of Vapor
    r"|(?:[Mm]ill \w+ cards, then )?[Ee]xile a nonland card at random from your graveyard\. Copy it\. You may cast the copy without "
    r"paying its mana cost\."  # Wondrous Crucible
    r"|[Ee]xile the top X cards of target opponent's library, where X is [^.]+\. Until end of turn, you may cast spells from among those "
    r"cards, and mana of any type can be spent to cast those spells\."  # Laughing Jasper Flint
    r'|CARDNAME becomes an? [^.]+\. If you do, it gains [^.]+ and loses all other abilities\.'  # The Irencrag
    r"|(?:You may )?behold an? [A-Z][a-z]+\. If you do, (?:untap that land|create an? [A-Z][a-z]+ token)\."  # Elven Passage; Sarkhan
    r"|Exile all attacking creatures target player controls\. That player may search their library for that many basic land cards, "
    r"put those cards onto the battlefield tapped, then shuffle\."  # Settle the Wreckage
    r"|[Cc]hoose target opponent\. If they lost life this turn, they reveal their hand, you choose a nonland card from it, and they "
    r"discard that card\. Otherwise, they discard a card\."  # Thought-Stalker Warlock
    r"|[Aa]ttach any number of target Equipment you control to target creature you control\. When one or more Equipment become "
    r"attached to that creature this way, that creature deals damage equal to its power to up to one target creature\."  # Thorin
    r"|You may reveal an artifact card you own from outside the game or choose a face-up artifact card you own in exile\. Put that card "
    r"into your hand\."  # Karn, the Great Creator
    r"|Choose creature or land\. Reveal the top (?:four|five|\d+) cards of your library\. Put all cards of the chosen type revealed this way "
    r"into your hand and the rest into your graveyard\."  # Winding Way
    r"|[Yy]ou may exile an? (?:black )?creature card(?: other than this card)? from your graveyard\. If you do, [^.]+\."
    # Masked Vandal, Ichorid
    r"|[Ll]ook at the top card of your library\. You may reveal that card\. If an instant or sorcery card is revealed this way, transform "
    r"this creature\."  # Delver of Secrets
    r"|Choose two target creature cards in your graveyard\. Sacrifice a creature\. If you do, return the chosen cards to the battlefield tapped\."  # Victimize
    r"|Search your library for up to X basic land cards, where X is the greatest power among creatures you control\. Put those cards "
    r"onto the battlefield tapped, then shuffle\."  # Traverse the Outlands
    r"|Exile the top four cards of your library in a face-down pile, then exile the top four cards of your library in a face-up pile\. An opponent chooses one of those piles\. Put that pile into your graveyard\. Look at the cards in the other pile\. You may cast a spell from among them without paying its mana cost\. Put the rest into your hand\."
    r"|Council's dilemma — Starting with you, each player votes for past or present\. You mill a card for each past vote, "
    r"then CARDNAME deals damage to each opponent equal to the total mana value of cards milled this way\. Exile the top card "
    r"of your library for each present vote\. Until the end of your next turn, you may play the exiled cards\."
    r"|Exile target instant or sorcery card from your graveyard\. Creatures you control get \+X/\+0 until end of turn, where X is "
    r"that card's mana value\. Whenever a creature you control deals combat damage to a player this turn, copy the exiled card\. "
    r"You may cast the copy without paying its mana cost\."
    r"|Each player puts a vow counter on a creature they control and sacrifices the rest\. Each of those creatures can't attack "
    r"you or planeswalkers you control for as long as it has a vow counter on it\."
    r"|Shuffle your library, then reveal cards from the top of it until you reveal a nonland card\. .*"
    r"|Exile the top (?:eight|seven|six|five) cards of your library\. You may cast an Aura spell from among them without paying its "
    r"mana cost\. Then put the rest on the bottom of your library in a random order\."
    r"|Look at the top (?:seven|six|five) cards of your library\. (?:You may put|Put) up to (?:two|three) (?:creature|permanent|noncreature, "
    r"nonland permanent) cards with mana value \d+ or less from among them onto the battlefield\. Put the rest on the bottom of your "
    r"library in (?:any|a random) order\."  # Collected Company, Storm the Festival, United Battlefront
    r"|Look at the top (?:seven|six|five) cards of your library\. Put any number of nonland permanent cards with total mana value "
    r"\d+ or less from among them onto the battlefield\. Put the rest on the bottom of your library in a random order\."
    r"|Each player exiles cards from the top of their library until they exile a nonland card\. An opponent chooses a nonland "
    r"card exiled this way\. You may cast up to (?:two|three) spells from among the other cards exiled this way without paying "
    r"their mana costs\."
    r"|Each player exiles cards from the top of their library until they exile a nonland card\. You may cast any number of spells "
    r"from among the nonland cards exiled this way without paying their mana costs\."
    r"|You may copy the exiled card\. If you do, you may cast the copy without paying its mana cost\."  # Isochron Scepter
    r"|Exile (?:target|each) card that's an instant or sorcery from your graveyard\. For each card exiled this way, copy it, and you "
    r"may cast the copy without paying its mana cost\."  # Mizzix's Mastery
    r"|Search your library for a card, exile it face down, then shuffle\. If this spell was kicked, you may cast the exiled card "
    r"without paying its mana cost if that spell's mana value is \d+ or less\. Put the exiled card into your hand if it wasn't cast "
    r"this way\."  # Beseech the Mirror
    r"|Choose an exiled card an opponent owns with a void counter on it\. You may play it this turn without paying its mana cost\."
    r"|That player exiles the top \w+ cards of their library\. Until end of turn, you may play those cards without paying their mana "
    r"costs\."  # Fallen Shinobi
    r"|That player exiles the top card of their library\. If it's a nonland card, you may cast it without paying its mana cost\."
    r"|Exile cards from the top of your library until you exile a legendary nonland card with lesser mana value\. You may cast that card "
    r"without paying its mana cost\. Put the rest on the bottom of your library in a random order\."  # Jodah, the Unifier
    r"|That player exiles cards from the top of their library until they exile an instant or sorcery card\. You may cast that card "
    r"without paying its mana cost\. Then that player puts the exiled cards that weren't cast this way on the bottom of their library in "
    r"a random order\."  # Gríma, Saruman's Footman
    r"|you may mill \w+ cards\. Then if there are \w+ or more cards in your graveyard, you may play the exiled card without paying its "
    r"mana cost\."  # Cemetery Tampering (the trigger's body begins in lower case)
    r"|Look at the top card of your library\. You may cast that card without paying its mana cost\. Do this only once each turn\."
    r"|choose target creature you control, then roll a d20\. 1\u201414 \| .+"  # Delina, Wild Mage: the whole table
    r"|create a token that's a copy of another target attacking creature and that's tapped and attacking\. Exile the token at end of "
    r"combat\."  # Flamerush Rider
    r"|[Rr]oll a d20\. \d+(?:\u2014\d+)? \| .+"  # a die roll and its table (CR 706.2)
    r"|exile this (?:enchantment|creature|artifact)\. If you do, return it to the battlefield under its owner's control\."  # Estrid's Invocation
    r"|Destroy target creature\. If that creature dies this way, its controller creates two tokens that are copies of that creature, "
    r"except their power is half that creature's power and their toughness is half that creature's toughness\. Round up each time\."
    r"|Exile target nonland permanent\. Each player other than its controller creates a token that's a copy of it\."  # Fractured Identity
    r"|exile (?:that card|it)\. If you do, return each other card exiled with this artifact to its owner's graveyard\."  # Mimic Vat
    r"|Look at the top \w+ cards of your library\. You may cast a spell from among them without paying its mana cost\. Put the rest on the "
    r"bottom of your library in a random order\."  # Aetherworks Marvel
    r"|[Ll]ook at the top X cards of your library, where X is your devotion to blue\. Put up to one of them on top of your library and the rest on the bottom of your library in a random order\. If X is greater than or equal to the number of cards in your library, you win the game\."  # Thassa's Oracle
    r"|Choose a card name\. Exile the top \w+ cards of your library, then reveal cards from the top of your library until you reveal a card with the chosen name\. Put that card into your hand and exile all other cards revealed this way\."  # Demonic Consultation
    r"|Exile the top card of your library\. You may put that card into your hand unless it has the same name as another card exiled this way\. Repeat this process until you put a card into your hand or you exile two cards with the same name, whichever comes first\."  # Tainted Pact
    r"|[Ee]xile the top card of each opponent's library\. Until end of turn, you may cast spells from among those exiled cards, and you may spend mana as though it were mana of any color to cast those spells\."  # Stolen Strategy
    r"|[Ee]xile the top card of each opponent's library\. You may play those cards for as long as they remain exiled\. If you cast a spell this way, you may spend mana as though it were mana of any color to cast it\."  # Brainstealer Dragon
    r"|[Ee]xile the top card of that player's library\. You may play that card for as long as it remains exiled, and you may spend mana as though it were mana of any color to cast it\."  # Cunning Rhetoric
    r"|[Ee]xile the top card of your library\. If it's an? \w+ creature card, you may cast that card until the end of your next turn\."  # Rundvelt Hordemaster
    r"|[Ee]xile the top card of that player's library\. Until end of turn, you may cast that card and you may spend mana as though it were mana of any color to cast that spell\."  # Grenzo, Havoc Raiser
    r"|[Ee]xile the top \w+ cards of target opponent's library\. Choose one of them\. Until the end of your next turn, you may play that card, and you may spend mana as though it were mana of any color to cast it\."  # You Find Some Prisoners
    r"|[Pp]ay X life, where X is the number of opponents that were dealt combat damage this turn\. If you do, draw X cards\."  # Tymna
    r"|Shuffle your library(?:\. Then|, then) exile the top card(?: of your library)?\. Until end of turn, you may play that card without paying "
    r"its mana "
    r"cost\."  # Mind's Desire
    r"|exile cards from the top of your library until you exile a nonland card\. You may cast it without paying its mana cost if that "
    r"spell's mana value is \d+ or less\. If you don't, put that card into your hand\."  # Breaching Dragonstorm
    r"|You may cast up to two instant and/or sorcery spells with total mana value \d+ or less from your graveyard and/or hand without "
    r"paying their mana costs\. If those spells would be put into your graveyard, exile them instead\."  # Invoke Calamity
    r"|Exile target instant or sorcery card from a graveyard\. Copy that card three times\. You may cast the copies without paying their "
    r"mana costs\."  # Mnemonic Deluge
    r"|Target opponent exiles cards from the top of their library until they exile an instant or sorcery card\. You may cast that card "
    r"without paying its mana cost\. Then put the exiled cards that weren't cast this way on the bottom of that library in a random "
    r"order\."  # Chaos Wand
    r"|exile a card at random from each opponent's graveyard\. You may cast any number of spells from among cards exiled this way without "
    r"paying their mana costs\. Then each player who owns a spell you cast this way loses life equal to its mana value\."  # Kefka
    r"|that player exiles it, then exiles cards from the top of their library until they exile a card that shares a card type with it\. "
    r"That player may cast that card without paying its mana cost\. Then they put all cards exiled with this enchantment on the bottom "
    r"of their library in a random order\."  # Possibility Storm
    r"|For each player, choose target nonenchantment, nonland permanent that player controls\. Those permanents' owners shuffle them into "
    r"their libraries\. Each player who controlled one of those permanents exiles cards from the top of their library until they exile a "
    r"nonland card, then puts the rest on the bottom of their library in a random order\. Each player may cast the nonland card they "
    r"exiled without paying its mana cost\."  # Guff Rewrites History
    r"|exile the top card of target opponent's library\. You may play that card for as long as it remains exiled, and mana of any type "
    r"can be spent to cast it\. If you're the monarch, until end of turn, you may cast a spell from among cards exiled with this "
    r"enchantment without paying its mana cost\."  # Court of Locthwain
    r"|Reveal the top card of your library\. If it's a creature card that shares a creature type with a creature you control, you may "
    r"cast it without paying its mana cost\. If you don't cast it, put it on the bottom of your library\."  # Descendants' Path
    r"|Exile an instant or sorcery card at random from your graveyard\. Then copy each card exiled with this enchantment\. You may cast "
    r"any number of the copies without paying their mana costs\."  # Arcane Bombardment
    r"|Exile cards from the top of your library until you exile cards with total mana value \d+ or greater\. You may cast any number of "
    r"spells from among them without paying their mana costs\."  # Improvisation Capstone
    r"|Exile the top \w+ cards of your library\. You may put a land card from among them onto the battlefield\. Until end of turn, for "
    r"each nonland card type, you may cast a spell of that type from among the exiled cards without paying its mana cost\."  # Aminatou's Augury
    r"|Draw a card, then discard a card\. If there are \w+ or more \w+ counters on CARDNAME, you may cast the discarded card without "
    r"paying its mana cost\."  # Malcolm, Alluring Scoundrel
    r"|Its controller may pay \w+ life\. If they do, they draw a card\."  # Gix, Yawgmoth Praetor
    r"|Look at that player's hand\. You may cast a spell from among those cards without paying its mana cost\."  # Silent-Blade Oni
    r"|Target opponent exiles the top X cards of their library\. You may cast any number of spells with mana value X or less from among "
    r"them without paying their mana costs\."  # Villainous Wealth
    r"|Exile the top X cards of target opponent's library\. You may play lands and cast spells from among cards exiled this way without "
    r"paying their mana costs\."  # Gix, Yawgmoth Praetor
    r"|Return up to one target artifact, creature, or non-Aura enchantment card with mana value (\d+) or less from your graveyard to "
    r"the battlefield with a finality counter on it\. It's a 1/1 Spirit creature with flying in addition to its other types\."
    r"|Choose target card exiled with (?:CARDNAME|this \w+)\. You may cast that card this turn without paying its mana cost\. If "
    r"that spell would be put into a graveyard, put it on the bottom of its owner's library instead\."
    r"|Exile up to one target instant or sorcery card from your graveyard and copy it\. You may cast the copy without paying its "
    r"mana cost\."
    r"|Each player exiles a card from their graveyard\. When one or more nonland cards are exiled this way, put that many \+1/\+1 "
    r"counters on target attacking creature\."
    r"|Each player sacrifices a creature or planeswalker of their choice\. If you sacrificed a permanent this way, you may return "
    r"another permanent card from your graveyard to your hand\."
    r"|Any number of target players each lose 2 life and sacrifice a creature of their choice\. You add \{B\}\{B\} and draw a card\."
    r"|For each player, you choose from among the permanents that player controls an artifact, a creature, an enchantment, and a "
    r"planeswalker\. Then each player sacrifices all other nonland permanents they control\."
    r"|Create a white Aura enchantment token named Contract attached to target creature an opponent controls\. The token has enchant "
    r"creature and \"Whenever enchanted creature attacks, it gets \+2/\+0 until end of turn if it's attacking one of your opponents\. "
    r"Otherwise, its controller loses 2 life\.\""
    r"|It gets \+2/\+0 until end of turn if it's attacking one of your opponents\. Otherwise, its controller loses 2 life\."
    r"|Copy that ability\. You may choose new targets for the copy\."
    r"|Put a card exiled with (?:this artifact|CARDNAME) into its owner's graveyard\. If it's a land card, create a Treasure token\. "
    r"If it's a nonland card, create an? .+ token\."
    r"|Reveal the top X cards of your library\. Put all land cards from among them onto the battlefield tapped and the rest on the "
    r"bottom of your library in a random order\."
    r"|Reveal cards from the top of your library until you reveal X land cards\. Put those land cards onto the battlefield tapped "
    r"and the rest on the bottom of your library in a random order\."
    r"|Reveal cards from the top of your library until you reveal an Aura card\. You may put that card onto the battlefield\. "
    r"If you don't, put it into your hand\. Put the rest on the bottom of your library in a random order\."
    r"|Look at the top (?:six|seven|eight) cards of your library\. You may put an Aura or Equipment card from among them onto "
    r"the battlefield\. If an Equipment is put onto the battlefield this way, you may attach it to a creature you control\. "
    r"Put the rest of those cards on the bottom of your library in a random order\."
    r"|Search your library for a [A-Z][a-z]+ card and put it onto the battlefield tapped\. Then if an opponent controls more "
    r"lands than you, repeat this process once\. If you search your library this way, shuffle\."
    r"|You and target opponent each reveal the top card of your library\. You each lose life equal to the mana value of the "
    r"card revealed by the other player\. You each put the card you revealed into your hand\."
    r"|Shuffle your library\. As many times as you choose, you may exile the top card of your library\. .*"
    r"|Remove all counters from target nonland permanent you control\. Draw a card for each counter removed this way\."
    r"|When you (?:next cast an|cast your next) instant or sorcery spell this turn, copy that spell\. You may choose new targets for the copy\."
    r"|When you next cast an instant or sorcery spell this turn, copy it for each time you've cast your commander from the command "
    r"zone this game\. You may choose new targets for the copies\."
    r"|You gain half X life and draw half X cards\. Round down each time\."
    r"|Mill a card, then exile a card from your graveyard at random\. You may play the exiled card this turn\."
    r"|Exile (?:that card|one of them) from your graveyard\. If you do, you may (?:play|cast) (?:that card|it) this turn\."
    r"|You may put a \+1/\+1 counter on a creature\. Then choose odd or even\. Return each creature with power of the chosen "
    r"quality to its owner's hand\."
    r"|You may put a creature card from your hand onto the battlefield\. If you do, sacrifice it unless you pay its mana cost "
    r"reduced by \{2\}\."
    r"|Each opponent creates a token that's a copy of it\. The tokens are goaded for the rest of the game\."
    r"|Create (?:a token that's a copy of|five tokens that are copies of) another target creature you control(?:, except it "
    r"isn't legendary)?\. (?:It gains|They gain) haste\. Sacrifice (?:it|them) at the beginning of the next end step\."
    r"|copy that spell for each other creature you control that the spell could target\. Each copy targets a different one of those "
    r"creatures\."  # Zada, Hedron Grinder
    r"|That player copies that spell for each other creature they control that the spell could target\. Each copy targets a "
    r"different one of those creatures\."
    r"|Exile (?:it|that creature)\. If you do, create a token that's a copy of (?:it|that creature|that card)(?:, except (?:\"[^\"]*\"|[^\".])*)?\.?\"?"  # Nightmare Shepherd, Hofri Ghostforge
    r"|For each creature token you control that entered this turn, create a tapped and attacking token that's a copy of that token\. "
    r"At the beginning of the next end step, sacrifice those tokens\."
    r"|Create X tokens that are copies of another target creature you control, where X is one plus the number of instant and "
    r"sorcery spells you've cast this turn\. They gain haste\. Exile them at the beginning of the next end step\."
    r"|Target player draws cards equal to half the number of cards in their library and loses half their life\. "
    r"Round up each time\."
    r"|Until end of turn, any time you could activate a mana ability, you may pay 1 life\. If you do, add \{C\}\."
    r"|Choose a color\. Add an amount of mana of that color equal to your devotion to that color\."
    r"|Create a \d+/\d+ \w+ \w+ creature token\. If you control (?:five|six|seven) or more lands, create a token that's a copy of this "
    r"creature instead\."
    r"|Each player sacrifices an? (?:creature or planeswalker|nontoken creature) of their choice\. Each player who can't discards a card\."
    r"|Look at the top card of your library\. If it's an? (?:creature )?card of the chosen type, you may reveal it and put it into "
    r"your hand\."
    r"|Tap enchanted creature\. It becomes unprepared\."
    r"|Then if you control [a-z]+ or more [A-Z][a-z]+s, sacrifice this Saga\. If you do, create [^.]+\."
    r"|Reveal the top card of your library\. If it's an? (?:permanent|creature|land|nonland) card, put it into your hand\."
    r"|(?:You may )?remove an? \S+ counter from this creature\. If you do, put [^.]+ on each other creature you control\."
    r'|At the beginning of the next end step, if any of those cards remain exiled, put them into your graveyard, then create [^.]+ this way\. '
    r'Those tokens have "[^"]+"\.?'  # Glimpse the Impossible
    r"|Draw a card\. If this spell wasn't cast from your hand, draw two cards instead\."  # Twinned Vision
    r"|Counter target spell if its mana value is \d+ or less\. If this spell was kicked, counter that spell if its mana value is \d+ or "
    r"less instead\."  # Prohibit
    r"|Each opponent sacrifices a creature of their choice\. If evidence was collected, instead [^.]+\."  # Extract a Confession
    r"|If evidence was collected, exile a card from an opponent's graveyard\. Then search its owner's graveyard, hand, and library for "
    r"any number of cards with that name and exile them\. That player shuffles, then draws a card for each card exiled from their hand "
    r"this way\."
    r"|Exile up to one target nonland card of each card type from your graveyard\. Copy those cards\. You may cast any number of spells "
    r"with total mana value \d+ or less from among the copies without paying their mana costs\."
    r"|Counter up to one target activated or triggered ability\. If an ability of an artifact, creature, or planeswalker is countered "
    r"this way, that permanent loses all abilities for as long as this creature remains on the battlefield\."
    r"|Counter target spell unless its controller pays (?:\{[^}]+\})+\. Counter that spell unless its controller pays (?:\{[^}]+\})+ "
    r"instead if this spell was cast using teamwork\."
    r"|Exile the top card of your library\. You may cast that card\. If you don't, CARDNAME deals \d+ damage to each opponent\."
    r"|Target instant or sorcery card in your graveyard gains flashback until end of turn\. The flashback cost is equal to its mana cost\.",
    re.I)


def _split_sentences(text: str) -> list[str]:
    """The sentences of each line; a few effects (Creative Technique's) are one template across several sentences."""
    sentences: list[str] = []
    for line in text.splitlines():
        while line.strip():
            found = _WHOLE_LINE.search(line)  # a few effects span several sentences: keep each as one, wherever it sits
            before, whole, line = (line[:found.start()], found.group(0), line[found.end():]) if found else (line, "", "")
            sentences += [s.strip() for s in re.split(r'(?<=\.)\s+|(?<=\.")\s+(?=[A-Z])', before) if s.strip()]
            if whole.strip():
                sentences.append(whole.strip())
    return sentences


_COUNTER = r"([+\-\u2212]1/[+\-\u2212]1|[a-z]+) counters?"  # "+1/+1", or a named one ("charge")


def _counter_name(text: str) -> str:
    return text.replace("\u2212", "-")


_CANT_COUNTER = re.compile(r"This spell can't be countered\.")


@lru_cache(maxsize=None)
def cant_be_countered(card: Card) -> bool:
    return any(_CANT_COUNTER.fullmatch(line) for line in rules_lines(card))


def _signed(text: str) -> int:
    return int(text.replace("\u2212", "-"))


_COLOR_NAMES = "white|blue|black|red|green"


_COLOR_LETTER = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}


_PROTECTION_FROM = (_COLOR_NAMES + "|everything|all colors|monocolored|multicolored|creatures|artifacts|enchantments|instants"
                    "|sorceries|planeswalkers")


_PROT = (rf"protection from (?:{_PROTECTION_FROM})(?:(?:, and |, | and )(?:from )?(?:{_PROTECTION_FROM}))*")


_WARD_MANA = r"(?:\{\d+\}|\{[WUBRGC]\})+"


PROTECTION = re.compile(_PROT, re.I)  # "protection from red", "protection from red and from blue"


_KW = rf"(?:{_PROT}|ward {_WARD_MANA}|ward\u2014pay \d+ life|annihilator \d+|hexproof from (?:monocolored|white|blue|black|red|green)|[a-z]+(?: [a-z]+)?)"  # one keyword ("ward\u2014pay 2 life": Hexing Squelcher)


def _protection_keywords(text: str) -> frozenset[str]:
    """ "protection from red and from blue" -> {"protection from red", "protection from blue"}"""
    return frozenset(f"protection from {what.lower()}"
                     for m in PROTECTION.finditer(text) for what in re.findall(_PROTECTION_FROM, m[0], re.I))


# What a source can be protected against: its color letters, its card types, and whether it is mono- or multicolored.
_PROTECTION_TOKENS = {"everything": "everything", "monocolored": "monocolored", "multicolored": "multicolored",
                      "creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
                      "instants": "instant", "sorceries": "sorcery", "planeswalkers": "planeswalker"}


def protection_tokens(keyword: str) -> frozenset[str]:
    """ "protection from red" -> {"R"}, "protection from creatures" -> {"creature"}, "protection from all colors" -> WUBRG"""
    what = keyword.removeprefix("protection from ").lower()
    if what == "all colors":
        return frozenset(_COLOR_LETTER.values())
    return frozenset({_COLOR_LETTER.get(what) or _PROTECTION_TOKENS[what]})


def _keyword_list(text: str) -> frozenset[str]:
    """ "flying", "flying and vigilance", "flying, vigilance, and trample" -> {"flying", ...}; a protection
    clause becomes one keyword per color ("protection from red")."""
    rest = PROTECTION.sub("", text)
    return _protection_keywords(text) | frozenset(w.strip().lower() for w in re.split(r",? and |, ", rest) if w.strip())


_NUM = r"(\d+|one|two|three|four|five)"


_PT = r"([+\-\u2212]\d+)/([+\-\u2212]\d+)"


_PT_X = r"([+\-\u2212])(\d*X|0)/([+\-\u2212])(\d*X|0)"  # multiples of X: "+X/+X", "+2X/+2X", "-X/-0", "+0/+X"


_KEYWORDS = rf"({_KW}(?:(?:,? and |, ){_KW})*)"


_KEYWORDS_BARE = rf"{_KW}(?:(?:,? and |, ){_KW})*"


# "gets +3/+3", "gets +2/+0 and gains trample", "gains flying" (one or both parts), then "until end of turn."
_CHANGE = rf"(?:gets? {_PT}(?: and gains? {_KEYWORDS})?|gains? {_KEYWORDS}) until end of turn\."


def _modifier(m: re.Match, first: int) -> Modifier:
    p, t, keywords_with_pt, keywords_only = m.group(first, first + 1, first + 2, first + 3)
    keywords = keywords_with_pt or keywords_only
    return Modifier(_signed(p) if p else 0, _signed(t) if t else 0, _keyword_list(keywords) if keywords else frozenset())


CANT_ATTACK, CANT_BLOCK = "can't attack", "can't block"  # pseudo-keywords, so combat can ask has_keyword


PROTECTION_CHOSEN = "protection from the chosen color"  # Flickering Ward: Game.modifiers turns it into the Aura's color


CANT_BE_BLOCKED = "can't be blocked"
ONLY_BLOCKED_BY = "only blocked by "  # + a blocker test ("keyword:haste", "type:Wall"): "can't be blocked this turn except by ..."


MUST_ATTACK = "attacks each combat if able"


_LAND_TYPE = r"(?:Plains|Island|Swamp|Mountain|Forest)"


_MANA_SYMBOLS = r"(?:\{\d+\}|\{[WUBRGC]\})+"


_THRESHOLD = re.compile(r"(\d+)\+ \| (.+)")


_ANY_N = {"two": 2, "three": 3, "four": 4, "five": 5}


def colors_spent(spent: tuple[frozenset[str], ...]) -> int:
    """Converge: how many colors of mana were spent, each mana counted as one color it could be (CR 702.110: the most that its types
    allow, a matching of mana to colors)."""
    owner: dict[str, int] = {}  # color -> the mana counted as it

    def place(i: int, seen: set[str]) -> bool:
        for color in spent[i] & set("WUBRG"):
            if color not in seen:
                seen.add(color)
                if color not in owner or place(owner[color], seen):
                    owner[color] = i
                    return True
        return False
    return sum(place(i, set()) for i in range(len(spent)))


FROM_LIBRARY = re.compile(r"When (?:CARDNAME|this card) is put into your graveyard from your library, (.+)", re.I)  # Narcomoeba, Creeping Chill
