# Card effects

Every effect, trigger and keyword the engine understands, and what it cannot play yet. To support a card, add its line here (see `CLAUDE.md`).

## Card effects

The `effects` package reads an instant's or sorcery's rules text one sentence at a time. It understands:

| Rules text | Example |
|---|---|
| Draw N cards. | Divination |
| You gain N life. / Each opponent loses N life. | |
| (This spell) deals N damage to any target / target creature / target player / ... | Lightning Bolt |
| Destroy target creature / artifact / enchantment / nonland permanent / ... | Murder |
| Counter target (noncreature / creature / instant or sorcery / artifact / enchantment) spell. | Counterspell, Negate |
| Exile target creature / artifact / nonland permanent / ... | |
| Exile target creature. Its controller gains life equal to its power. | Swords to Plowshares |
| Exile target creature. Its controller may search their library for a basic land card, ... | Path to Exile |
| Exile target player's graveyard. | Tormod's Crypt |
| Exile (another) target nonland permanent ... until this enchantment leaves the battlefield. | Banishing Light |
| Exile another target ...; When this leaves the battlefield, return the exiled card to the battlefield under its owner's control. | Oblivion Ring, Fiend Hunter |
| Exile target creature (you control), then return it to the battlefield under its owner's (your) control. / ... Return it to the battlefield (or its owner's hand) at the beginning of the next end step. | Cloudshift, Flickerwisp |
| Exile target spell. / Counter target spell. If that spell is countered this way, exile it instead ... | Dissipate |
| Exile the top N cards of your library. You may play it (them) this turn. / Until the end of your next turn, you may play those cards. | Reckless Impulse |
| Choose one / two / three / one or both / one or more — • mode • mode ... (also in "When ..., choose one —" and "{T}: Choose one —") | charms and commands, Cleanup Crew |
| Entwine {cost} / Escalate {cost} (mana costs only) | Barbed Lightning (entwine), Blessed Alliance (escalate) |
| Tap all creatures your opponents control. | Cryptic Command |
| Target player (or opponent) draws N cards / gains N life / loses N life. | |
| Exile target card from a graveyard. | |
| Return (another) target permanent to its owner's hand. Return all creatures to their owners' hands. | Cyclonic Rift, Evacuation, Rushing River |
| Return target (creature) card from your graveyard to your hand / to the battlefield. | Raise Dead, Zombify |
| Return another target (artifact, creature, Elf) card from your graveyard to your hand. ("Another" leaves out the dying creature's own card, unless an identical card is also there.) | Myr Retriever, Dutiful Attendant |
| Put target creature card from a graveyard onto the battlefield under your control. | Reanimate |
| Search your library for a (creature / legendary creature / Aura / Equipment / nonbasic land) card (with mana value N or less), (reveal it,) put it into your hand, then shuffle. | Demonic Tutor, Stoneforge-style |
| Search your library for a nonbasic land card / up to two Forest cards, put it onto the battlefield (tapped), then shuffle. | Skyshroud Claim |
| Return target creature card from your graveyard to the battlefield tapped. | |
| Search your library for a card, then shuffle and put that card on top. | Vampiric Tutor |
| {T}: Add one mana of any color / two mana in any combination of colors / {C}{C} / {G}. Spend this mana only to cast KIND spell(s) (of the chosen type) (or activate abilities of ...) (, and that spell can't be countered). (Activate only if ...). Any kind the filters read; the "or activate" clause is read but the mana is not yet offered for abilities. | Cavern of Souls, Maelstrom of the Spirit Dragon, Eldrazi Temple, Shrine of the Forsaken Gods, Secluded Courtyard, Rivaz of the Claw |
| Whenever you / a player tap(s) a KIND for mana, add / that player adds one mana of any type that KIND produced / an additional {X}. If you tap a KIND for mana, it produces twice / three times as much of that mana instead. Any kind the filters read. The trigger's mana is its own, once per tap, and is not multiplied (CR 106.12a, 106.12b); "any type it produced" is any type the permanent can make in that tap. A storage land's mana is not multiplied. | Kinnan, Bonder Prodigy; Nyxbloom Ancient; Mana Reflection; Mana Flare; Crypt Ghast |
| {T}: For each color among permanents you control, add one mana of that color. (Vivid ability word read.) This creature gets +1/+1 for each color among permanents you control. | Bloom Tender, Faeburrow Elder |
| {COST}, {T}: Add X mana in any combination of colors, where X is AMOUNT. (Any amount the effects read; X is worked out when the mana is wanted.) | Selvala, Heart of the Wilds |
| {T}: Add MANA. This mana can't be spent to pay generic mana costs. (Only a colored symbol of a cost takes it.) | Jegantha, the Wellspring |
| Whenever another creature enters, its controller may draw a card if its power is greater than each other creature's power. (The entering creature's controller chooses; a tie is not greater.) | Selvala, Heart of the Wilds |
| {COST}: Untap enchanted creature. (beside the existing "Tap enchanted creature.") | Freed from the Real |
| Put a -1/-1 counter (or any counter) on this creature: EFFECT. The counter is a cost, always payable (CR 118.3); the bot doesn't activate it, having no reason to. | Devoted Druid |
| (You may) tap or untap target permanent / creature. With "When CARDNAME enters and whenever ...", two triggers. | Derevi, Empyrial Tactician |
| You may activate abilities of creatures you control as though those creatures had haste. (CR 302.6: a summoning-sick creature's {T} abilities, mana abilities and mana-costing ones included, work; attacking still needs haste. Only its controller's creatures.) | Tyvar, Jubilant Brawler; Thousand-Year Elixir; Shang-Chi |
| Mill N cards, then (you may) return a KIND card (with mana value N or less) from your graveyard to the battlefield / your hand. (Chosen as the ability resolves, from everything in the graveyard; with "you may" the player may take none.) | Tyvar, Jubilant Brawler |
| {COST}: Put CARDNAME onto the battlefield from the command zone. Offered only while the card is in the command zone, at any time its owner has priority; not a cast, so no commander tax. | Derevi, Empyrial Tactician |
| Whenever another creature you control enters, you may pay {COST}. If you do, put a +1/+1 counter on it. If it's a SUBTYPE, put two +1/+1 counters on it instead. (The creature that entered gets the counters; the payment is asked as the trigger resolves.) | Emiel the Blessed |
| Compleated: a Phyrexian mana symbol in the walker's cost paid with 2 life (the payment does that only when mana will not do) makes it enter with two fewer loyalty counters, per symbol. | Vraska, Betrayal's Sting; Nissa, Ascended Animist |
| Search your library for up to N / any number of (kind) cards (not named CARDNAME) (that each have different names), (reveal them,) put them into your hand / onto the battlefield / into your graveyard, then shuffle. / ... then shuffle and put those cards on top in any order (the searcher chooses the order). | Buried Alive, Tiamat, Goblin Recruiter |
| Search your library for a (legendary) permanent / creature card with mana value less than CARDNAME's power, put that card onto the battlefield / into your hand, then shuffle. (The power is read as the ability resolves.) | Sisay, Weatherlight Captain |
| Reveal the top N cards of your library. Put all (kind) cards (with mana value N or less) revealed this way / from among them into your hand / onto the battlefield and the rest on the bottom of your library in any / a random order. | Goblin Ringleader, Muxus, Goblin Grandee |
| Look at the top N cards of your library. You may put a (kind) card from among them onto the battlefield. Put the rest on the bottom of your library in a random order. | Ureni of the Unwritten |
| You get an emblem with "..." (a loyalty ability's ultimate, usually). The emblem goes to the command zone, is never a permanent, and its text works like a permanent's static or triggered abilities; an emblem whose text the engine cannot read, or that has an activated ability, leaves the loyalty ability unread. | Elspeth, Sun's Champion; Ajani, Adversary of Tyrants; Sorin, Lord of Innistrad |
| You lose N life. | |
| Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle. | Cultivate, Kodama's Reach |
| Search your library for a (Plains, Island, ...) card, put it onto the battlefield (tapped), then shuffle. | Farseek, Nature's Lore |
| Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle. | Explosive Vegetation |
| Scry N. / Surveil N. | |
| Look at the top N cards of your library. Put one of them into your hand and the rest on the bottom. / You may reveal a creature card from among them... | |
| Take an extra turn after this one. / Target player takes an extra turn after this one. | Time Walk, Time Warp |
| After this (main) phase, there is an additional combat phase (followed by an additional main phase). | Relentless Assault |
| Untap all creatures that attacked this turn. / Untap all creatures you control. | Aggravated Assault |
| Untap target land (permanent, creature, ...). / Untap another target creature. / Untap up to two target lands. | |
| Untap all lands (artifacts, permanents, enchantments) you control. | |
| Return all creature tokens / all nontoken creatures to their owners' hands. | Perplexing Test |
| Untap it. / Untap this creature. (in "Whenever this creature attacks, untap it", or "equipped creature ... untap it") | |
| You become the monarch. | Thorn of the Black Rose |
| You take the initiative. | Underdark Explorer |
| Goad target creature. / Goad all creatures you don't control. | Disrupt Decorum |
| Whenever an opponent casts a spell / draws a card, (you may) draw a card / create a Treasure token unless that player pays {N}. | Rhystic Study, Mystic Remora, Smothering Tithe |
| Whenever you become the monarch, ... / Whenever an opponent becomes the monarch, ... | |
| Starting with you, each player votes for X or Y. For each X vote, ... / If X gets more votes (or the vote is tied), ... | Tivit, Seller of Secrets; Plea for Power; Capital Punishment |
| Starting with you, each player votes for a nonland permanent you don't control. Exile each permanent with the most votes or tied for most votes. | Council's Judgment |
| Investigate. | |
| Mill N cards. / Target player (or opponent) mills N cards. / Each opponent (or player) mills N cards. | |
| Discard N cards (at random). / Discard your hand. / Target player (or opponent) discards N cards (at random). / Each opponent (or player) discards N cards or their hand. | Mind Rot, Hymn to Tourach |
| Draw N cards, then discard N cards. / Each player discards their hand, then draws N cards. / Each player draws N cards. | Faithless Looting, Wheel of Fortune |
| Target player reveals their hand. You choose a (nonland / noncreature, nonland / ... with mana value N or less) card from it. That player discards that card. | Thoughtseize, Duress |
| Equip {N} (Equipment) | Swiftfoot Boots, Lightning Greaves |
| Equip—Pay N life. / Sacrifice a creature. / Discard a card. | Blood-style equipment |
| Whenever equipped (enchanted) creature dies / deals combat damage to a player, ... | Sword of Feast and Famine-style |
| When this is put into a graveyard from the battlefield, return it to its owner's hand. | Rancor |
| Enchanted (equipped) creature (land) has "{T}: ..." | Enchanted land has "{T}: Add {G}{G}." |
| Equipped creature gets +N/+N and has keywords. / Enchanted creature gets +N/+N and has keywords. | |
| Enchant creature / land / ... (Auras) | |
| Enchanted creature can't attack or block. | Pacifism |
| Destroy all creatures / artifacts / lands / nonland permanents / ... (optionally "you don't control", "you control") | Wrath of God, Armageddon |
| Exile all creatures / ... | |
| Destroy / exile all creatures with flying / without flying / with power 4 or greater / with toughness 2 or less / nonblack / white | Hurricane-style wipes |
| This spell deals N (or X) damage to each creature / each creature you don't control / each opponent / each player | Pyroclasm |
| ... damage to each creature with flying (and each player) | Electrickery-style |
| Each opponent (or each player) sacrifices a creature / artifact / enchantment / land / permanent. Target player (or opponent) sacrifices one. | Diabolic Edict |
| Sacrifice a creature. | Smothering Abomination |
| Two things joined by "and": "... and you gain 1 life", "You gain 1 life and draw a card", "You draw two cards and lose 2 life" | Blood Artist, Night's Whisper |
| Create N P/T color Subtype (artifact) creature token(s) (with flying, vigilance, ...). | Raise the Alarm |
| Create a P/T ... creature token with (flying and) "<an ability we understand>" | Pest: "When this creature dies, you gain 1 life." |
| Create N Treasure / Clue / Food token(s). | Smothering Tithe |
| Exile target monocolored permanent. | Vanishing Verse |
| Look at the top three cards of your library. Put one of them into your hand, put one of them on the bottom of your library, and exile one of them. You may play the exiled card this turn. (with fewer cards, the hand and the bottom come first) | Expressive Iteration |
| Exile target creature. Its controller manifests the top card of their library. | Reality Shift |
| Shuffle your library. As many times as you choose, you may exile the top card of your library. If the total mana value of the cards exiled this way is 13 or less, you may cast any number of spells from among those cards without paying their mana costs. (you are asked after each card, shown the running total; bots stop at 4 cards or total 9) | Dance with Calamity |
| Create a token that's a copy of target creature (you control). / Populate. | Growing Ranks |
| Create a 3/3 ... token, then populate. (the new token may be the one copied; "token with trample, then populate" too) | Horncaller's Chant |
| Create a token that's a copy of another target creature you control(, except it isn't legendary). It gains haste. Sacrifice it at the beginning of the next end step. (also five tokens) | Orthion, Tempestra |
| Target player draws cards equal to half the number of cards in their library and loses half their life. Round up each time. | Peer into the Abyss |
| Whenever equipped creature deals combat damage to a player, that player loses half their life, rounded up. ("that player" is who was hit) | Quietus Spike |
| When this Aura enters, put a +1/+1 counter on enchanted creature. / Have the base power and toughness of other creatures you control become equal to CARDNAME's power and toughness until end of turn. | Seismic Tutelage, Tanazir Quandrix |
| When this creature dies, return it to the battlefield tapped under its owner's control at the beginning of their next upkeep. | Phytotitan |
| Draw a card (two, three cards) at the beginning of the next turn's upkeep. ("You draw ..." and the plain wording; an enters trigger too.) The cards come at the next upkeep, whoever's it is, and only the player who cast it draws them. | Portent, Clairvoyance, Flare, Balduvian Rage, Heal, Carrier Pigeons, Pyknite, Arcane Denial |
| You may put a creature card from your hand onto the battlefield. If you do, sacrifice it unless you pay its mana cost reduced by {2}. | Flash |
| Mill four cards, then return a creature card and a land card from your graveyard to your hand / a creature card to the battlefield (tapped). ("Exile this land" as a cost works) | Sudden Reclamation, Tomb Fortress, Port of Karfell |
| When this creature enters, if it's not a token, each opponent creates a token that's a copy of it. The tokens are goaded for the rest of the game. | Life of the Party |
| You lose all but 1 life. / When this creature leaves the battlefield, you gain life equal to the life you lost when it entered. | Soulgorger Orgg |
| Create a token that's a copy of another target creature you control. (not the source itself) | |
| Create a token that's a copy of it, tapped and attacking. (the copy attacks whom the source attacks; it is never declared, so attack triggers don't see it) | |
| Target player loses half their life, rounded up / rounded down. | |
| Double the number of +1/+1 counters on target creature. | |
| When this creature dies, return it to the battlefield (tapped). / ... under its owner's control. (a token is gone for good) | |
| You may put a creature card from your hand onto the battlefield. | |
| Mill three cards, then return a creature card from your graveyard to your hand. (any two effects that each work alone join with ", then") | |
| You gain life equal to the amount of life you lost this turn. | |
| Destroy target permanent. Its controller creates a 3/3 green Beast creature token. / That creature's controller creates ... | Beast Within, Rapid Hybridization, Resculpt |
| Draw two cards and create two Treasure tokens. | Big Score, Seize the Spoils |
| Create a token that's a copy of target creature. If this spell was kicked, create five of those tokens instead. | Rite of Replication |
| For each opponent, create two 3/3 ... tokens with flying that attack that opponent this turn if able. They gain haste until end of turn. Exile them at the beginning of the next end step. | Furygale Flocking |
| Prevent all combat damage that would be dealt to you this turn. For each 1 damage prevented this way, create a 2/1 ... token with flying. | Inkshield |
| CARDNAME deals 4 damage divided as you choose among any number of targets. (a point at a time: the first to a target, the rest to targets or nowhere) | Magma Opus |
| Tap two target permanents. | Magma Opus |
| Exile X target creatures. For each creature exiled this way, its controller creates a 2/2 ... token. | Curse of the Swine |
| Destroy up to X target artifacts and/or enchantments. Create twice X 1/1 ... tokens with "<an ability we understand>". | Pest Infestation |
| Choose any number of target creatures you control. For each of them, create a token that's a copy of that creature, except it has haste. Exile those tokens at the beginning of the next end step. | Twinflame |
| Create a token that's a copy of (target creature / it / that creature / equipped or enchanted creature), except (it isn't legendary / it's N/N / it's a Spirit in addition to its other types / it's a 2/2 black Zombie in addition to its other colors and types / it has flying and haste). *The except clause is a list of changes the engine applies to the copy (`CopyChanges`); any other clause leaves the line unsupported. "It" is the permanent that set off the trigger, still there or not, or the source for its own trigger.* | Helm of the Host, Miirym, Impostor Syndrome, Vaultborn Tyrant, Ratadrabik of Urborg, Irenicus's Vile Duplication |
| Whenever another nontoken Dragon (or: legendary creature) you control enters (dies) / a nontoken creature you control deals combat damage to a player, ... | Miirym, Ratadrabik of Urborg, Impostor Syndrome |
| Put N +1/+1 (or -1/-1) counters on target creature / on each creature you control / on it. | |
| Put N +1/+1 counters on up to one target creature. (a loyalty ability may choose no creature) | Ajani, Caller of the Pride's +1 |
| This creature enters with N +1/+1 counters on it. | Hydras |
| Target creature gets +N/+N (and gains keywords) / gains keywords until end of turn. | Giant Growth |
| Creatures you control (or your opponents control) get +N/+N (and gain keywords) until end of turn. | |
| Target creature gets +X/+X (-X/-X, +X/+0, ...) until end of turn, for each ... / where X is ... | |
| Double target creature's (this creature's, each creature you control's, each Dragon you control's) power (and toughness) until end of turn, once or X times: it gets +P/+T equal to its current size, the creatures of "each" together; "Then it fights up to one target creature" follows it. "At the beginning of each combat, ..." happens in every player's combat, and "Whenever this creature attacks alone" only when it is the sole attacker. | Unleash Fury, Unnatural Growth, Grunn, Thrakkus, Exponential Growth, Dragonclaw Strike |
| "Whenever you cast a creature spell this turn, draw a card." / "Until end of turn (until the end of your next turn), whenever ..., ...": a delayed triggered ability (CR 603.7). The spell or ability sets it up as it resolves, in the wording a permanent's trigger has; it works until the turn ends, or the end of its controller's next turn, and "If this spell was kicked, whenever ..." sets it up only then. | Glimpse of Nature, Death Frenzy, Gnawing Crescendo, Warhost's Frenzy, Vizkopa Guildmage, Mountain Titan, Season of the Bold, Showdown of the Skalds, Thunder of Unity |
| "Choose target creature you control. Whenever that creature deals combat damage to a player or planeswalker this turn, draw that many cards.": a delayed ability about the creature just targeted. It watches that creature only, for combat damage (to a player, a planeswalker, or any), any damage, or attacking one of your opponents or the monarch, with the damage as "that many" / "that much" / "that damage"; "if this spell was kicked" works in it. "Draw that many cards" also reads for the permanents whose trigger carries a number (combat damage, life lost). | Hunter's Insight, Vigorous Charge, Maeve, Insidious Singer, Okoye, Mighty and Adored, April, Reporter of the Weird, Cold-Eyed Selkie, Fear of Failed Tests, Glint-Eye Nephilim, Professor Hulk, Starwinder, Vilis, Broker of Blood |
| Target creature becomes a 4/4 Dragon until end of turn. / has base power and toughness 0/1 until end of turn. | |
| Put N <kind> counters on target <permanent>. / Remove N (all) <kind> counters from target <permanent>. / Remove all counters from target <permanent>. | |
| Double the number of +1/+1 counters on each creature you control. | |
| Move a (or all) +1/+1 counter(s) from target creature onto another target creature. | |
| Until end of turn, this land becomes a P/T (color) (Subtype) (artifact) creature (with keywords). It's still a land. / Target land you control becomes a ... | Mutavault, Treetop Village |
| Each opponent (or player) creates a token. / Target opponent creates a token. | |
| Creatures you control get +N/+N and gain trample until end of turn. | Overrun |
| This creature gets +1/+0 until end of turn. (as an activated ability) | Shivan Dragon |
| Search your library for a basic land card, put it onto the battlefield tapped, then shuffle. | Rampant Growth |

- **Wording:** "of their choice" and a leading "You draw" / "You create" are read the same as without them.
- **Amounts that depend on the game:** "..., where X is ...", "... equal to ..." and "... for each ..." are worked out
  when the effect resolves. Supported: its (or this creature's) power, using its last known power if it has left the
  battlefield; counters of any kind on it ("charge counters on this artifact"); cards (or <type> cards) in your graveyard; the number of <type> you control; creatures on the battlefield; the amount of life
  you gained this turn; half your life total, rounded down or up; spells you've cast this turn; the greatest mana value among instant and sorcery spells you've
  cast this turn; opponents. "For each" multiplies drawing, life, tokens, +1/+1 counters and a pump ("+2/+2 until end of turn for each creature you control") ("create a 1/1 Saproling
  token for each +1/+1 counter on this creature"). A sentence a template already understands is never rewritten.
  "An X/X ... token" gets its size when it's created (Rootha, Mastering the Moment).
- **Target restrictions:** destroy and exile targets can say "an opponent controls",
  "you don't control" or "you control".
- **Counters:** +1/+1 and -1/-1 counters change power and toughness. Matching +1/+1 and -1/-1
  counters cancel out. Other kinds ("charge", "time") are only counted. "Put N <kind> counters on target <permanent>",
  "Remove N <kind> counters from target ...", "Remove all (<kind>) counters from target ..." and "Double the number of
  +1/+1 counters on each creature you control" work. "Move a (or all) <kind> counter(s) from target creature onto
  another target creature" moves up to that many; moved counters aren't "put", so Doubling Season doesn't double them.
  "Move any number of" isn't built.
- **Setting power and toughness:** "Target creature becomes a 4/4 (color) (Subtype) (creature) (with flying) until end of
  turn" and "has base power and toughness 0/1 until end of turn" set the base; counters and bonuses still add to it,
  whatever order they came in. Its types, subtypes and colors don't change.
- **Animating lands:** "Until end of turn, this land becomes a 3/3 green Ape creature with trample. It's still a land."
  (Mutavault, Blinkmoth Nexus, Treetop Village, Celestial Colonnade) and "Target land you control becomes a 3/3
  Elemental creature with haste until end of turn. It's still a land." The permanent keeps its types and gains
  Creature (and Artifact), the stated subtypes, colors, power and toughness, and keywords; "with all creature types"
  adds no subtype. It goes back to a plain card at end of turn. A land is summoning sick the turn it comes in, so it
  can't attack or use {T} abilities if animated that turn. Bots never activate these abilities.
- **Targets in a list:** "X target creatures" (Curse of the Swine) has exactly X targets, so X is limited to how many
  legal targets there are; "up to X target artifacts and/or enchantments" (Pest Infestation) and "any number of target
  creatures" (Twinflame) may have fewer, or none. Each is one list, and a list whose targets are all gone by the time the
  spell resolves makes it fizzle (a list that never had any still resolves, so "twice X tokens" still happens with no
  targets). "Create twice X ..." is twice the spell's X. A copy "except it has haste" has haste for good, and copies made
  together count as one "one or more creature tokens" event.
- **Tokens for other players:** "Each opponent (or player) creates ..." and "Target opponent creates ...". A token
  with "This creature can't block / attack / attack or block." gets that restriction.
- **Static abilities:** "(Other) (Elf) creatures you control get +1/+1 (and have flying)",
  "Creatures you control have haste" and "Creature tokens you control have haste" (Brudiclad). These apply only
  while their source is on the battlefield.
  - Either can be conditional, written "As long as X, ..." or "... as long as X.", and a creature can buff
    itself ("As long as you control an artifact, this creature gets +1/+1 and has flying."). The buff is checked
    every time power, toughness or keywords are looked at, so it switches on and off as the game changes.
    Conditions: you control a/N or more <type>, you control no <type>, it's your turn, you're the monarch,
    you have no cards in hand, you have N or more cards in hand, plus the graveyard, life, lands and cast
    conditions listed under triggers. A line with any other condition is ignored.
  - Who it affects can be a color ("Other red creatures you control"), a tribe in the plural ("Spirits you control"),
    or attackers only ("Attacking Pests you control"). Bonuses can scale: "This creature gets +1/+0 for each artifact
    you control", "... for each creature card in your graveyard", "+2/+2 for each Aura attached to it", and on an Aura
    "Enchanted creature gets +1/+1 for each Aura you control that's attached to a creature". "Enchanted creature gets
    +1/+1 and is goaded" goads it for as long as the Aura stays (the Aura's controller is the goader).
    "White creatures get +1/+1" (Crusade) affects every player's creatures. An Aura can give keywords, including
    "annihilator 2" (Eldrazi Conscription: when it attacks, the defending player sacrifices two permanents), a quoted
    ability (Fallen Ideal) and an extra creature type (Angelic Destiny: "is an Angel in addition"; lords see it).
    "As this enters, choose a creature type" (Patchwork Banner) names the most common type in your cards unless you
    choose; "Creatures you control of the chosen type get +1/+1" follows. "... for each time you've cast your
    commander from the command zone" scales a tribe (Vanguard of the Restless, which also returns from the
    graveyard when a Spirit enters if you pay {2}{W}). Veyran makes your instant and sorcery triggers happen twice.
  - Counters: "that many plus one +1/+1 counters" replacements can cover other creatures (Benevolent Hydra), any permanent
    (Kami of Whispered Hopes) or artifacts and creatures (Ozolith). "Enters with twice X" (Primo), "escapes with two
    +1/+1 counters" (Woe Strider), a copy "except it enters with X additional counters" (Altered Ego) and "enters with an
    additional counter for each creature that died this turn" (Gorma) are supported, as are "as long as it has ten or more
    counters" (Primordial Hydra) and "creatures you control with counters on them" (Nev). A creature that taps for as
    much mana as its power (Kami), a mana ability that removes a counter once each turn (Mana Bloom), "double the
    counters on this creature" and a spell that costs {1} less for each counter on a permanent (Zimone) work too.
  - Counters on cards: "Move all counters" and "Remove all counters ... draw a card for each" (Nexus Mentality, whose
    "choose both" needs a commander), "Put a +1/+1 counter on each of up to X target creatures" (Silkguard, which asks
    for X before the targets), a counter for each player's creature (Nils, whose attack tax makes each counter cost {1}),
    vow counters that keep a creature from attacking the caster (Promise of Loyalty), "each opponent loses all counters"
    (Final Act), and Zimone's Hypothesis (odd or even).
  - Shadrix Silverquill chooses two modes for two different players, or none. Rousing Refrain adds {R} for each card in an
    opponent's hand, keeps the mana until end of turn and suspends itself; Suspend N—{cost} exiles a card from your hand
    with time counters, one comes off each upkeep, and the last one casts it for free.
- **Current power, toughness and keywords:** printed values plus counters, static abilities and
  "until end of turn" effects. They count everywhere: combat, damage, targeting (granted hexproof),
  destroy (granted indestructible), state checks, and the labels players see ("Bear 4/4").
  "Until end of turn" effects wear off in the cleanup step. An effect on "creatures you control"
  affects only the creatures there when it resolves. `Game.power`, `Game.toughness` and
  `Game.has_keyword` are the way to read them.
- **Tokens:** they enter with summoning sickness, and "dies" triggers still happen when they leave.
  After leaving the battlefield they stop existing, so they never reach the graveyard or exile.
  Treasure is a mana source that's sacrificed when used, and it's spent after lands and other sources.
  "Create a 0/0 Fractal token. Put X +1/+1 counters on it." (or ", then put three ... on it") gives the new token the
  counters. Clue and Food work through their activated abilities. A token with a quoted ability
  ("When this token dies, you gain 1 life.") works when that ability is understood; otherwise the card isn't.
  "Put X +1/+1 counters on it, where X is the amount of mana spent to cast that spell." (Deekah) reads the mana paid
  for the spell that set off the magecraft trigger; a copy of a spell was never cast, so its Fractal gets none.
  Brudiclad's "Then you may choose a token you control. If you do, each other token you control becomes a copy of
  that token until end of turn." asks which token (or none); the others keep their counters and damage and get
  their own card back at cleanup.
- **Lands:**
  - Entering tapped: "This land enters tapped" (taplands, gain-lands, temples, triomes), and the conditional
    kinds: checklands ("unless you control an Island or a Swamp"; any land with that land type counts),
    fastlands ("two or fewer other lands"), slowlands ("two or more other lands"), and bond lands
    ("unless you have two or more opponents", so untapped in a 3+ player game), plus "unless you control two or more
    basic lands", "unless you control three or more other Islands", "unless your opponents control eight or more lands"
    (their lands added together), and the Snarls ("you may reveal a Mountain or Plains card from your hand"; you are
    asked, and it enters tapped if you decline or have no such card). Fetched and reanimated lands follow the same rules.
    More conditions: "unless you control a planeswalker / a basic land / a legendary creature / a Mount or Vehicle / a
    Mountain" (one type of land works for any of the five), "unless a player has 13 or less life" (any player, you
    included), "If you control two or more other lands, this land enters tapped", "If you were the starting player, this
    land enters tapped" (the game remembers who started), and a reveal of any one creature type ("you may reveal an
    Elemental card from your hand", with the Snarl wording kept for two land types).
  - "This land enters tapped with two charge (depletion, ...) counters on it": tapped, with the counters. The Vivid lands
    ("{T}, Remove a charge counter: Add one mana of any color") make their own color for free and any color for a counter,
    and only a mana of another color uses one (generic mana and the land's own color do not). The depletion lands ("{T},
    Remove a depletion counter: Add {G}{G}. If there are no depletion counters, sacrifice it") make two mana per tap and
    are sacrificed when the last counter goes; a land with none left makes no mana.
  - "This land enters tapped. As it enters, choose a color.": you choose one of the five as it enters and the land
    remembers it, and "{T}: Add one mana of the chosen color" makes only that color (Room of Refuge, not the five colors
    Scryfall lists for it). The Thriving lands and Gates, "choose a color other than red" and "{T}: Add {R} or one mana of
    the chosen color", leave their own color out of the choice and make it besides the chosen one. A land with no choice
    (it was never asked) makes nothing, or only its own color.
  - Storage lands (Hollow Trees, Fountain of Cho and the rest of their two cycles): "{T}, Remove any number of storage
    counters from this land: Add {G} for each storage counter removed this way" makes one mana for each counter and takes
    off as many counters as the mana you use (a land with none makes no mana). "You may choose not to untap this land during
    your untap step" asks you at your untap step, only while the land is tapped, whether to untap it or leave it tapped to
    collect a counter at upkeep ("if this land is tapped, put a storage counter on it"); the bot always untaps.
  - "When this land enters, sacrifice it unless you pay {1}" (Gateway Plaza and the other Guildgate-style lands): you are asked
    whether to pay (the land enters tapped, so it cannot pay for itself); with nothing to pay with, or if you decline, it is
    sacrificed. Tri-lands ("{T}: Add {W}, {U}, or {B}") make one mana of one of the three colors.
  - Station lands (Adagia, Evendo, Kavaron, Susur Secundi, Uthros): "Station" taps another untapped creature you control
    (you choose which) and puts charge counters equal to its power on the land, only as a sorcery. An ability written
    "12+ |" works only with that many charge counters on the land: Evendo's and Uthros's mana (a mana for each creature or
    artifact you control, besides the land's own {T} mana), Adagia's token copy of an artifact or enchantment (legendary),
    Kavaron's Robot and attack bonus, Susur Secundi's draw. The counters do not come off.
  - Hideaway N (the five Hideaway lands: Howltooth Hollow, Mosswort Bridge, Shelldock Isle, Spinerock Knoll, Windbrisk
  - **Exploit** (CR 702.110): when the creature enters you may sacrifice a creature (one of yours, itself included; the bots only give up one that is hardly worth keeping), and "When this creature exploits a creature, ..." then goes on the stack. Fell Stinger, Qarsi Sadist, Rakshasa Gravecaller, Sidisi, Undead Vizier and ten others work; the ones that need to know what was exploited (Profaner of the Dead, Silumgar Scavenger, Skull Skaab) or that give exploit to others (Colonel Autumn) wait.
    Heights): as the land enters you look at the top N cards, choose one to exile face down (the others go to the bottom in
    a random order; the other players are not told which). The land's ability plays that card for free, but only if its
    condition holds as the ability resolves: every hand empty, creatures you control with total power 10 or more, any
    library with 20 or fewer cards, one opponent dealt 7 or more damage this turn, or three or more creatures attacked this
    turn. A spell is cast without paying its mana cost; a land is played only if you still have a land drop (otherwise it
    stays hidden); you may decline. If the condition fails the cost is still paid and the card stays.
  - Karoos: "When this land enters, sacrifice it unless you return an untapped Mountain you control to its owner's
    hand." You are asked which land to return (or to sacrifice it); with no untapped land of the type it is sacrificed.
  - "At the beginning of your upkeep, if this land is tapped, put a storage counter on it" (the condition "if this
    land is tapped" works on any trigger).
  - Shocklands: you may pay 2 life or the land enters tapped. Life you can't spare (2 or less) isn't offered.
  - Painlands and Talismans: 1 damage when tapped for a colored mana. Colorless mana from them is free, and
    the payer picks painless sources first. Talismans make their colors now (they used to make colorless only).
  - Command Tower: only makes your commander's colors, whatever the card data lists.
  - Study Hall and Path of Ancestry: mana abilities with a "When that mana is spent to cast ..., scry" rider. The
    rider triggers when the auto-payer tapped the land for that ability while paying for the right spell: your
    commander (Study Hall scries the number of times it has been cast from the command zone, counting this cast) or
    a creature spell sharing a creature type with your commander (Path of Ancestry scries 1). The trigger goes on
    the stack above the spell. Study Hall tapped for its plain {C} spends no such mana, so it doesn't trigger then.
  - Mana with strings attached: "Spend this mana only to cast spells with mana value 5 or greater or spells with {X}" (Troyan)
    and "only on costs that contain {X}" (Elementalist's Palette) are only used for what they may pay for; "{T}, Sacrifice a
    Food: Add one mana of any color" (Gilded Goose, one Food per Goose) and "{T}, Mill a card: Add {C}" (Millikin, needs a
    library) pay their extra cost when the mana is spent; "Add one mana ... for each charge counter" (Astral Cornucopia,
    Palette) makes one mana per counter (the mana of one tap may be spent as different colors).
  - Every copy is made by `copy_of(card, changes, as_token=...)` (`effects/families/copying.py`): a token copy ("create a token that's a
    copy of ...", a copy of a permanent spell, Myriad, Encore's attackers, Twinflame, Rionya), a clone entering as a copy, a creature
    that becomes a copy until end of turn (Muddle), Hofri Ghostforge's Spirit copy. The "except ..." (`CopyChanges`) means the same
    thing in all of them, and a copy of a token is a token only if it is made as one. Nothing else builds a "Token ..." type line from
    a card (a test looks).
  - Creature types and counts (found by auditing real decks, #428): "Goblin spells you cast cost {1} less to cast." and "Red creature
    spells ..." (a creature type or a color and a type is a filter; Goblin Warchief, Dragonspeaker Shaman, Hazoret's Monument);
    "As an additional cost to cast this spell, sacrifice a Goblin." (Goblin Grenade); "X deals damage to any target (or target
    player or planeswalker) equal to the number of creatures (Goblins) you control" (Massive Raid, Goblin War Strike); "Add {R} for
    each creature you control / each Goblin on the battlefield." (Battle Hymn, Brightstone Ritual); "the number of Goblins on the
    battlefield" is an amount (Elves, Wolves, Dwarves and Werewolves read as Elf, Wolf, Dwarf and Werewolf).
  - Round two of the deck audit: a lord that affects every player's creatures of a type, "Other Goblins get +1/+1 and have
    mountainwalk." (Goblin King; the form with "you control" was there); "Whenever a Dragon you control attacks, ..." (Utvara
    Hellkite, Atarka; one attacking creature of the type, not "one or more"); a library search by creature type ("a Dragon creature
    card", "an Elf card"); "Reveal the top four cards of your library. Put all Goblin cards revealed this way into your hand and
    the rest on the bottom of your library in any order." (Goblin Ringleader); and Corrupted: "an opponent has three or more poison
    counters" as a condition, on a mana ability too (Glistening Sphere's activation). Not done: "Other Merfolk" (a type that is its
    own plural), defending-player effects (Silumgar), "one or more Goblins attack" (General Kreat), Blood Moon.
  - Poison counters from spells (Atraxa's deck): "Each opponent (each player) gets a poison counter." (Prologue to Phyresis, Ichor Rats),
    "... sacrifices a creature or planeswalker of their choice and gets a poison counter." (Vraska's Fall), and "Then each creature
    your opponents control gets -1/-1 until end of turn for each poison counter its controller has." (Phyresis Outbreak). Infect,
    toxic and losing at ten counters were already there.
  - Casting from your own graveyard on a permission: "You may cast this card from your graveyard." and "... as long as you
    control a Zombie." (Gravecrawler): the card's own mana cost, then back to the graveyard if it dies (the `Cast from graveyard:`
    action, with `GraveyardCast.requires`). "Once during each of your turns, you may cast a Zombie creature spell (a permanent
    spell with mana value 2 or less, an Aura or Equipment spell) from your graveyard." (Gisa and Geralf, Lurrus, Danitha): the
    `Cast from graveyard (permission):` action, one use a turn for each permanent that has the line (recorded in its
    `activated_turn`), not while it has lost its abilities. The ten known "Companion — ..." conditions are understood lines.
  - Playing from the top of the library: "You may play lands (and cast spells) from the top of your library." (Courser of
    Kruphix, Oracle of Mul Daya, Future Sight), with the spells limited to a kind or several ("artifact spells and colorless
    spells" Mystic Forge, "creature spells of the chosen type" Realmwalker, "Goblin spells", "instant and sorcery spells",
    "spells with flash or flying", "spells with mana value 4 or greater", "snow lands and snow spells") and, for an Equipment,
    only "as long as it is attached to a creature" (The Reality Chip). The game offers `Play land from the top of your library:`
    and `Cast from the top of your library:` for the top card when the permission allows it (a land uses the land drop; a
    spell is cast at its usual timing for its mana cost). "Play with the top card revealed" and "You may look at the top card"
    are accepted and change nothing: the engine does not hide a library. Wordings with a condition or a cost
    ("if you control", "by sacrificing", "once each turn") are not understood.
  - Exile and graveyard effects: Serra Paragon (once each turn, play a land or cast a permanent spell of mana value 3 or
    less from your graveyard; that permanent is exiled, and you gain 2 life, if it goes to the graveyard). Surge to
    Victory (exile an instant or sorcery from your graveyard, creatures get +X/+0, and each creature that connects this
    turn lets you cast a free copy of it). Fateful Tempest (a past-or-present vote: mill and damage, or exile cards you
    may play until your next turn ends). Abstract Performance (two piles of four; an opponent sends one to your
    graveyard, you may cast a spell from the other for free and take the rest).
  - Ancient Tomb ("{T}: Add {C}{C}. ... deals 2 damage to you."): two mana from one tap, and the damage is dealt
    once per tap however much of the mana is used. Bouncelands ("{T}: Add {B}{G}.") make both colors the same way.
  - City of Brass ("Whenever this land becomes tapped, it deals 1 damage to you."): hurts every time it's tapped
    for mana. Mana Confluence ("{T}, Pay 1 life: Add one mana of any color."): pays life (not damage), and is not
    used when you can't afford it. The payer picks painless sources first.
  - Bouncelands: "enters tapped" plus "When this land enters, return a land you control to its owner's hand."
    You choose the land and it can be itself; bots return the newest land.
  - **Prepare cards** (Secrets of Strixhaven, e.g. Eiganjo Dynastorian // Replenish): a creature whose card also has a spell half. "This creature enters prepared" and "... becomes prepared" (from any trigger the engine fires) make it prepared; while it is, you get a "Cast prepared: <spell>" action (with the spell's own timing and cost). It casts a copy of the spell, which ends instead of going to a graveyard, and the creature stops being prepared. The report checks both halves. "Target creature becomes prepared / unprepared" (Skycoach Waypoint, Hexhaven Dueling Arena's "creature that attacked this turn"), "each creature you control becomes prepared" (Codie) and the conditions "if this creature isn't prepared", "three or more artifact and/or creature cards in your graveyard", "a player has one or fewer cards in hand" and "an opponent has more cards in hand than you" work. Also: "choose up to one" modes (Biblioplex Tomekeeper), "Then if <condition>, <effect>" sentences, exiling cards from your graveyard ("you may exile eight cards ... If you do, this creature becomes prepared", and "Exile a creature card from your graveyard" as a cost), "Tap two untapped creatures you control" as a cost, "When X and whenever Y" as two triggers, and "Whenever one or more tokens you control enter". The spell halves of Carnivorous Cultivator, Eccentric Pestfinder, Eiganjo Dynastorian, Inspired Skypainter, Lorehold Archivist, Pigment Wrangler, Skycoach Conductor, Striding Shotcaller, Ursine Guide and Vastlands Scavenger work. The three cards whose text the issue cut off work, from their full Oracle text: Emeritus of Truce ("Then if an opponent controls more creatures than you, this creature becomes prepared", counted after the token it just made), Stensian Sanguinist ("Whenever you attack" is the same trigger as "whenever one or more creatures you control attack"; "Whenever that creature deals combat damage to a player this combat" is kept on the combat, so it ends with it) and Yavimaya Bloomsage ("if that creature has power 7 or greater" looks at the creature that just got the counter). Static lines with a condition also work for the rest of the report: Threshold ("Threshold — This creature gets +1/+1 as long as there are seven or more cards in your graveyard", Theorix Metamage and Void Extrapolator; an ability word in front of a static line is ignored, as it already was for triggers) and "As long as an opponent was dealt noncombat damage this turn" (Whiplash Wordsmith; combat damage and life loss do not count, and it ends with the turn). Alchemy "conjure" works for "Conjure a card named X onto the battlefield" (Galathul Galecaller, Ursine Guide, Crescendo Conductor): `load_deck` finds the names in the deck's text, looks them up in the same card source and keeps them in `Deck.conjured`, so nothing is fetched during a game; a name the source does not know is left out and conjuring it does nothing. A conjured card is marked `conjured`, which is all "a spell that isn't from your starting deck" checks, and "Whenever you conjure one or more cards" fires once per conjure. Conjuring into a hand or a graveyard is not built. "Each creature you control with a +1/+1 counter on it has vigilance" (Vigorbloom Vanguard; only that counter counts, and only your own creatures) and the mana restriction "This mana can't be spent to cast spells from your hand" (Heartwood Crafter; the mana still pays for abilities and for spells cast from the command zone or elsewhere) work. A spell counts as cast from hand when that exact card object is in the hand as it is paid for, so a second identical card in hand can make a flashback cast count as from hand. The two mana effects that last for a turn work too. Pyre Rhymer's Molten Tide makes each Mountain (any land with the Mountain subtype) you tap this turn add an additional {R}. Yavimaya Bloomsage's Channel lets you pay 1 life for {C} any time this turn; since mana is paid automatically, it is used only when your other mana cannot cover the cost, it can never pay you down to 0 life, and at most 10 life-paid {C} are offered for one payment. With these, all 70 prepare cards are fully playable in the report. Infinite Coursework works too: "tap enchanted creature" (with "It becomes unprepared") when the Aura enters, "doesn't untap during its controller's untap step", and "loses all abilities". A creature that loses all abilities has no keywords of its own, no triggered abilities (its own or ones that watch), no activated or mana abilities (a creature land can't tap for mana) and its static abilities stop; its size is kept, and abilities that another Aura or effect gives it still work, since the order effects were made in is not tracked.
  - Abilities from the hand: "{U/R}{U/R}, Discard this card: Create a Treasure token." (Magma Opus) is offered as
    "Activate from hand: <card>" at instant speed; the card is discarded as the cost and the effect goes on the stack.
  - More activated abilities (#73): costs that exile this permanent ("Exile this artifact", Perpetual Timepiece) or return it
    to its owner's hand (Rootha) are paid before the ability goes on the stack, so it outlives the source. An ability that
    says "Return this card from your graveyard to the battlefield tapped" (Teacher's Pest) is offered as "Activate from
    graveyard: <card>", and so is one whose cost is "Exile this card from your graveyard" (the Souls, Renew, Bonebind Orator): its
    targets are chosen while the card is still there, so "Return another target creature card" leaves it out, the card is exiled as the
    cost is paid, and an ability that says "Activate only as a sorcery" is only offered then. "Pay life equal to the number of colors in
    your commanders' color identity" (War Room) works.
    Alchemist's Refuge lets you cast every spell this turn at instant speed, Arcane Lighthouse takes hexproof and shroud
    off your opponents' creatures until end of turn, and Restless Spire's creature has first strike only during your turn.
    Also: "noncreature artifact or noncreature enchantment" and "noncreature, nonland permanent" as target kinds, "creatures
    named CARDNAME can't be blocked", "Spirits you control gain ... until end of turn", "Exile enchanted creature", a
    counter on each green creature that entered this turn (Oran-Rief), a land fetched untapped when you control four lands
    (Fabled Passage), a token if the exiled card is a creature (Feral Appetite), "draw two cards instead" with a condition
    (Zimone) and Quintorius's "draw two cards, then mill a card". The rest of #73's lines (mana abilities that spend
    other resources or restrict what the mana buys, Class levels, Priest of Forgotten Gods, Currency Converter, Opal Palace,
    Thunderclap Drake and Quintorius's Spirit sacrifice) were built with #80.
  - Rules text of #81: "Counter target spell unless its controller pays {N}" (the controller is asked), "Destroy target artifact,
    enchantment, or planeswalker", "Return six target nonland permanents ...", "target creature with mana value X",
    "gets +X/+X and gains hexproof and indestructible", "Then it fights up to one target creature", "Proliferate X times",
    Dig Through Time's look-seven-take-two, Commander's Insight, Culling Ritual (mana for each permanent destroyed), Mana Geyser,
    Biomass Mutation, Wave of Reckoning, Winds of Rath ("that aren't enchanted"), Volcanic Torrent (creatures and planeswalkers),
    damage to "each of one or two targets", draw-then-discard, mill-then-return, "You may sacrifice a permanent. If you do, draw two
    cards", "sacrifice X creatures" as an additional cost (Immoral Bargain, whose X is chosen at casting although its mana cost has no {X}), X limited by the number of players (Open the Way),
    "Arcane Denial"'s draws at the next upkeep, Flashback with a life payment, casting from the graveyard "by paying {2}{W}",
    cost reductions ("costs {2} less if you gained life this turn", "{X} less where X is the total power of your creatures",
    Aura spells, spells that target a creature, affinity for Auras), Pest Rescuer's extra life, haste while an opponent is at 10 or
    less life, and combat limits: Ghostly Prison's tax per attacker, and the same tax worded "for each of those creatures" with {1} (Baird, Steward of Argive), {W/P} (Archon of Absolution, Norn's Annex) or {X} (Sphere of Safety: the enchantments you control) (the taxes of all your attackers are added up and paid once, after they are chosen and tapped, as CR 508.1h-i says; a creature that taps to attack can't help pay it, and you are only offered an attacker if the new total is still affordable), "Inklings can't attack you", creatures enchanted by your Auras
    can't attack you, "can block only creatures with flying" and "creatures with power less than this creature's power can't block it".
    The rest of #81's lines (the Class levels, Anger, Cursed Mirror, Galazeth Prismari, Goldspan Dragon, Harmonic Prodigy,
    Flickering Ward, spell mastery and Quandrix Command) were built with #80. Guardian Augmenter's "Commander creatures you control
    get +2/+2" and "Commanders you control have hexproof" apply to your commander (a role, not a creature type; a token copy
    doesn't count), Bloodghast's landfall brings it back from the graveyard, and a flashback that pays 3 life is legal at 3 life.
    `tests/test_rules_text_81.py` plays the real Oracle text of the cards in #81 that no earlier test named.
  - Precon behavior sweep (#151 and the issues after it): `tests/test_prepare_sweep_151.py` plays the nine prepare creatures and
    their spell halves from real Oracle text, through real upkeeps, combats and draws. It found that "Put two +1/+1 counters on
    target creature. It gains trample until end of turn." (Pack a Punch) gave the trample to nothing; "it" now means the creature
    that got the counters, and still means the source when no creature was targeted before it.
    A copy of a permanent spell (Owlin Spiralmancer copying an X creature) now enters as a token, so it leaves no card in the
    graveyard when it dies; before, it entered as the real card.
    Fellwar Stone makes the colors the opponents' lands could produce (before, only Exotic Orchard did, so the artifact made no
    mana), and an Eldrazi Spawn's "Sacrifice this token: Add {C}." is a mana ability that works the turn the token arrives (it
    needs no {T}), where before the Spawn made no mana at all. A payment spends a Treasure or a Spawn only when nothing else will
    pay (before, a Spawn was taken first for generic mana and lands stayed untapped).
  - Trigger effects of #80: "sacrifice two lands", a search whose "it" is the card found (Bitterthorn), "Whenever one or more
    creatures die / enter" (once for everything that happens together, with "with mana value 3 or less" and "only once each turn"),
    "its controller loses 2 life and you gain 2 life" (Parasitic Impetus), "you may attach this Aura to that creature" and
    "if that enchantment is an Aura, you may attach it to the token", "tap up to one target creature and goad it", "return target
    nonland permanent card with mana value 3 or less", "exile target noncreature, nonland card", "exile up to one target nonland,
    nontoken permanent you don't control", a token copy of this creature, "create half X Food tokens, rounded up", "When you cast
    this spell, you gain half X life and draw half X cards", tapped Treasures equal to its power, "gets +X/+0 where X is that spell's
    mana value", "creatures you control gain flying and get +X/+X", "You may pay {2}. If you do, ..." (including a target), "pay {1}
    and discard a card", "remove a counter from it. If you do, draw a card", "It has "Sacrifice this token: Add {C}."", populate with
    a hasty token that is sacrificed at the end step, "put into a graveyard from the battlefield" (a token that dies counts, as the rules say; "nontoken" watchers ignore it), "becomes the target of a spell",
    decayed, "return this card from your graveyard to your hand" at upkeep (Squee), "exile that card from your graveyard" after a
    discard, and "mill a card, then exile a card from your graveyard at random. You may play the exiled card this turn".
    Built for #80 so far: Tomik, Nether Traitor, Prismari Pianist, Manaform Hellkite, Killian's "enchanted creatures attack" line,
    Hateful Eidolon, Pearl-Ear (a spell that targets a modified permanent), and Venerable Warsinger (the combat damage dealt is
    passed to the trigger as X, so "mana value X or less" resolves against it), Skyclave Apparition (the exiled card's owner gets a
    token when it leaves), Keen Duelist, Conspiracy Theorist (once per discard, not per card), and Laelia (cards exiled from your
    library and/or graveyard; cascade does not count yet), Spirit of Resilience, Zimone (a prime number of lands), Firemane
    Commando, Breena and Combat Calligrapher (another player's attack; the trigger carries the seat attacked), Claim Jumper and
    Archaeomancer's Map (land counts), and Goldspan Dragon and Galazeth Prismari (mana abilities given to your Treasures or
    artifacts; Goldspan's two mana need not be the same color),
    Armored Skyhunter, Songbirds' Blessing, Herald of Amity, Forum Filibuster, Ao the Dawn Sky and Plargg and Nassari (look at,
    reveal or exile cards from the top of the library, then put or cast from among them; an Aura enters on a host you choose,
    an Equipment may be attached; Forum Filibuster's graveyard return is chosen on resolution, not targeted).
    The copy family: Brudiclad (the other tokens become copies for good in the current wording; the older "until end of turn"
    wording still works), Rionya, Redoubled Stormsinger, Muddle (and the myriad keyword), Cursed Mirror, Thunderclap Drake,
    Hofri Ghostforge and Mirrorwing Dragon.
    The X family: a permanent that enters carries the X it was cast with, so Fractal Harness and Kinetic Ooze read it (Kinetic
    Ooze's "mana value X or less", "if X is 5 or more" and "if X is 10 or more"); Lattice Library, Brass Infiniscope (its mana
    sets up "when you next cast a spell with {X} this turn", for a spell that uses its mana too), Open the Way and Animist's
    Awakening (with Spell mastery), Unbound Flourishing (doubles X of a permanent spell; copies an instant or sorcery, or an
    activated ability, with {X} in its cost; a copied ability keeps its targets), and Oversimplify's current wording.
    Graveyard exile, return and cast: a card exiled by a permanent's ability is "exiled with" it (Currency Converter puts one into
    the graveyard for a Treasure or Rogue; Quintorius casts one free, and a spell that would go to a graveyard goes to the bottom of
    its owner's library; both are chosen as the ability resolves, not targeted), Excava (a finality counter: a creature with one is
    exiled instead of dying, and it leaves as the real card), Augusta, Renegade Bull (cast a copy of the exiled card for free) and
    Sevinne's Reclamation (a spell cast from a graveyard may copy itself as it resolves).
    Class enchantments (Intermediate Chirography, Advanced Reconstruction): a Class enters at level 1 and reads as the abilities of its
    level, so gaining a level (at sorcery speed, the next level only) swaps in the next level's text; it goes to the graveyard as the
    whole card. "Spells you cast from anywhere other than your hand cost {2} less" counts a card as cast from the hand if it is in it.
    The one-offs: Blossoming Bogbeast (a sentence may begin with "Then"), Anger (a static ability that works from the graveyard), Quandrix
    Command (its shuffle mode always shuffles your own graveyard), Opal Palace, Harmonic Prodigy, Forgotten Ancient, Deadly Brew, Priest of
    Forgotten Gods, Plumb the Forbidden (the number to sacrifice is asked as it is cast), Flickering Ward, Darksteel Mutation (its size,
    indestructible and lost abilities; it does not replace card types or creature types), Tragic Arrogance, Scriv (the Contract token and
    its trigger, which is told which seat is attacked) and Guardian of Faith (phasing: a phased-out creature, and what is attached to it,
    is out of the battlefield list until its controller's next untap step, with nothing leaving or entering).
    With these every unique card of the five precon decks is fully playable (the report on each deck in `examples/precons` lists no unsupported line).
  - Manifest (Reality Shift): the top card of the library enters face down as a 2/2 creature with no abilities. A creature
    card can be turned face up at any time you have priority for its mana cost ("Turn face up: ..."; not a stack
    action). It goes to the graveyard as the real card, and only its controller is shown what it is
    (`face_down_as` in the board).
  - Cycling {N}: an ability you can use from your hand at instant speed. Pay, discard the card, draw.
    Basic landcycling {N} and Plainscycling / Islandcycling / Swampcycling / Mountaincycling / Forestcycling {N}
    fetch a land to your hand instead (basic land, or any land with that type). The cost can be mana or "Pay N life"
    (offered only if it leaves you above 0 life).
  - Mana abilities that end with "Activate only if <condition>." (Temple of the False God, Mox Jasper) make mana only
    while the condition holds, checked each time you pay. "{1}, {T}: Add one mana of any color." (Hall of Oracles) works
    like a Signet. A filter or Signet can no longer tap for mana to pay for its own cost (a land with a plain
    {T}: Add {C} could before).
  - **Mana a payment doesn't use stays in the pool** (CR 106.4): Sol Ring tapped for a {1} spell made {C}{C}, and the other {C} pays for
    the next spell or ability that step, as the mana of a ritual does; the pool empties at the end of the step. Mana with a restriction
    (Jegantha's, which can't pay generic costs), mana that cost life or damage to make, and mana that took a counter off its permanent
    are not kept.
  - "{T}: Add {G} for each creature you control" (Gaea's Cradle, Elvish Archdruid) and "{2}, {T}: Add {B} for each Swamp
    you control" (Cabal Coffers): the amount is worked out each time you pay. Coffers' {2} is paid first, so it is only
    worth it with enough Swamps (the payment picks the first mana that fits).
  - Filter lands ("{W/B}, {T}: Add {W}{W}, {W}{B}, or {B}{B}."): paid like a Signet, so one Swamp becomes two white,
    two black or one of each. A filter land can't pay for its own ability.
  - Exotic Orchard ("any color that a land an opponent controls could produce") and Reflecting Pool ("any type that
    a land you control could produce", colorless included): they read the other lands' mana, and a land of this
    kind adds nothing to another's, so two never feed each other. With nothing to read they make no mana.
  - Pathways (modal double-faced lands): the card shows both faces' names, and "Play land" is offered once for
    each face. The face you play is the permanent and makes only its own color. This applies to a land back face
    of any modal double-faced card; other double-faced cards use their front face only.
- **Equipment and Auras:** "Equip {N}" is an activated ability at sorcery speed that targets a creature you
  control (re-equipping moves the Equipment). An Aura chooses what it enchants when cast, and goes to the
  graveyard instead of entering if that target is gone when it resolves. Attached permanents change the
  creature's power, toughness and keywords, so granted haste, hexproof or shroud work as usual (shroud stops
  even the controller's equip). Equipment stays on the battlefield, unattached, when its creature leaves;
  an Aura goes to the graveyard. Labels show attachments ("Sword attached to Bear (seat 0, #1)").
  "Can't attack or block" is supported through Auras.
  - **Other equip costs:** "Equip—Pay 3 life.", "Equip—Sacrifice a creature.", "Equip—Discard a card." are paid like any
    ability cost. "Equip legendary creature {3}" (a restriction on what it can equip) isn't supported.
  - **Triggers on what is attached:** "Whenever equipped (or enchanted) creature dies / deals combat damage to a
    player, ..." (the Equipment's or Aura's controller gets the trigger). "Whenever enchanted creature deals damage to
    an opponent, you may draw a card" (Curiosity, Keen Sense, Ophidian Eye; any damage, combat or not) and its combat
    form (Sleeper's Robe): the opponent is an opponent of the Aura's controller, and damage to a creature or of 0 does not count. The damage an ability deals ("Niv-Mizzet deals 1 damage to any target") is dealt by the permanent, so it sets these off, and a spell's damage, which no permanent deals, does not; with Niv-Mizzet, Parun it closes the draw loop. "When this Aura is put into a graveyard
    from the battlefield, return it to its owner's hand" (Rancor) works for any permanent, and so does "When
    enchanted creature dies, return this Aura to its owner's hand": it comes back from the graveyard it is in.
    Exiled, it isn't returned. Other Aura returns on "When enchanted creature dies" work too: "return it to the
    battlefield under your control" (Changing Loyalty), "return this card from your graveyard to the battlefield"
    (Screams from Within) and "... at the beginning of the next end step" (Ghoulish Impetus) with you choosing what
    it enchants (it stays in the graveyard if nothing is legal), and Gift of Immortality's creature-then-Aura pair.
  - **Granting abilities:** "Enchanted (or equipped) creature has "{T}: Draw a card."" lets that creature activate it
    (a summoning-sick one can't use {T}). "Enchanted land has "{T}: Add {G}{G}."" makes the land tap for that mana
    instead of its own single mana. A quoted ability that isn't understood leaves the card unsupported.
  - **Reconfigure {N}:** an Equipment creature has two abilities at sorcery speed: attach to another creature you
    control (offered only if you have one), and "(unattach)" (offered only while attached). While attached it is
    not a creature; when unattached, when its creature leaves, or when it leaves the battlefield it is its real
    card again.
  - **"It" on the host:** "Whenever equipped (enchanted) creature attacks (deals combat damage to a player), put a
    +1/+1 counter on it" means the equipped creature. In "Whenever equipped creature dies, ... it" the creature is
    gone, so that line isn't understood.
  - **Not built:** Fortify and Fortifications, "Whenever this Equipment becomes attached", Wild
    Growth-style "whenever enchanted land is tapped for mana", and an equip bonus that scales ("+1/+1 for each").
- **Replacement effects:** statics that change what would happen, read from a permanent on the battlefield.
  - Rest in Peace: "If a card or token would be put into a graveyard from anywhere, exile it instead." (Leyline of the
    Void: only an opponent's cards.) Every route to a graveyard is covered: spells, dying, discarding, milling, cycling.
    Things still die, so dies triggers happen; a commander can still choose the command zone. Rest in Peace's "exile
    all cards from all graveyards" is supported.
  - Damage doubling: "If a source (you control) would deal damage to a permanent or player, it deals double (triple) that damage
    instead" (Furnace of Rath, Dictate of the Twin Gods, Angrath's Marauders, City on Fire, Fiery Emancipation, Gratuitous
    Violence for a creature you control, Charging Tuskodon for itself), the same to an opponent or an opponent's permanents
    (Twinflame Tyrant) or an opponent only (Fiendish Duo), noncombat only (Solphim), and "that much damage plus N" (Tomik).
    Spells count as sources you control. Doubling, "plus N" and prevention shields are all replacement effects, so the player being dealt the
    damage (the controller, for a permanent) chooses the order (CR 616.1) and is asked only when the order changes the result (3 damage with a
    shield of 2 and a doubler: 2 if the shield goes first, 4 if the doubling does); the least damage is listed first. Several stack (two doublers:
    four times).
    The source can be named: "a red source you control" (Torbran), "another red source" or "another source you control" (Embermaw
    Hellion, Thor), "a red or artifact source" (Mechanized Warfare), a creature type ("a Giant source", "a Lizard, Mouse, Otter, or
    Raccoon you control"), "an instant or sorcery source" (Pyromancer's Swath) and a spell ("a red instant or sorcery spell you
    control", "a red spell" whoever controls it). A spell counts as a source of the color and types of its card. "With an odd mana
    value", "that entered this turn", "plus X" and "prevent half" are not read.
  - Blightsteel Colossus, Darksteel Colossus, Legacy Weapon, Progenitus and Nexus of Fate: "If CARDNAME would be put into a
    graveyard from anywhere, reveal CARDNAME and shuffle it into its owner's library instead." It works from every zone
    (dying, discarding, milling, a resolved spell); a creature that is shuffled in never dies, and a commander can still
    choose the command zone.
  - Draw doubling: "If you would draw a card, draw two cards instead." (Thought Reflection) and the form that skips the first
    card of your draw step (Alhammarret's Archive, Teferi's Ageless Insight, Bard, King of Dale). Each one applies once to a draw,
    so two of them make four.
    Phial of Galadriel's "while you have no cards in hand" form looks at the hand before each card, and its "gain twice that much life while
    you have 5 or less life" looks at your life before the gain; both stack with the other doublers.
  - Doubling Season and Parallel Lives: tokens an effect creates under your control, and counters an effect puts on your
    permanents (including the counters a permanent enters with), are doubled. Several stack (two doublers: four times).
    Hardened Scales adds one to +1/+1 counters on your creatures first, then doubling applies.
  - Also in the current wording: Mondrak ("If one or more tokens would be created under your control, twice that many ..."),
    Branching Evolution (twice that many +1/+1 counters on a creature you control, after Hardened Scales' extra ones),
    The Wind Crystal (you gain twice that much life, after Pest Rescuer's extra one), and Academy Manufactor (a Clue, Food or
    Treasure token you would create becomes one of each, before any token doubling). All stack, and only the effect's
    controller's own events count.
  - Chatterfang, Squirrel General: "If one or more tokens would be created under your control, those tokens plus that many 1/1 green
    Squirrel creature tokens are created instead." Every batch of tokens its controller creates comes with as many 1/1 green Squirrels, applied
    after Academy Manufactor and before token doubling (so Doubling Season doubles the Squirrels too); two Chatterfangs each add that many
    Squirrels to what the other left, and the Squirrels it makes do not make more. His "{B}, Sacrifice X Squirrels: Target creature gets
    +X/-X until end of turn." asks for X (up to the Squirrels you control, himself included), sacrifices that many as a cost, and pumps by X.
  - Vorinclex, Monstrous Raider and Innkeeper's Talent at level 3: "If you would put one or more counters on a permanent or player,
    put twice that many ... instead" doubles every counter their controller puts, on any permanent or player (the counters a
    permanent enters with are put by its controller; poison from infect or toxic by the source's controller); Vorinclex's "If an
    opponent would put one or more counters ..." halves what each opponent puts, rounded down, after any doubling. Tekuthal,
    Inquiry Dominus: "If you would proliferate, proliferate twice instead." (each time sets off "Whenever you proliferate").
    "Proliferate twice." (Contagion Engine, Ezuri) and Deepglow Skate's "double the number of each kind of counter on any number of
    target permanents" are read too. Not read: Vorinclex's effect on loyalty abilities' costs.
  - Exiled instead of dying: "If a creature an opponent controls would die, exile it instead" (Liesa, Gisa), "If this creature
    would die, exile it instead", and the spells that say "If that creature would die this turn, exile it instead" (Lava
    Coil) or "If a creature dealt damage this way would die this turn" (Anger of the Gods). The creature is exiled, so it
    does not die and dies triggers do not happen. Not read: Frostwielder's "dealt damage by this creature this turn", damage
    prevention (Fog, "prevent the next N damage"), and "twice as much mana" (Mana Reflection).
  - Damage prevention (#235, first batch): "Prevent the next N damage that would be dealt to any target / target creature / you /
    this creature this turn" (an ability, a spell or a mode) is a shield that absorbs up to N from any sources and is then used
    up; "Prevent all damage that would be dealt to target creature this turn" is one that is never used up. Shields last the
    turn they were made. "Prevent all combat damage that would be dealt this turn" (Fog) stops combat damage to players and
    creatures until the turn ends. A permanent can prevent all damage dealt to itself, only combat damage to itself, only damage
    from creatures, or all damage to its controller. "Damage can't be prevented" (and "damage dealt by this creature can't be
    prevented") beats all of these. Prevented damage is not dealt, so there is no lifelink, poison, commander damage or combat
    damage trigger for it. Not read: sources of your choice (Circles of Protection), enchanted creature, divided and X shields,
    redirection; the full list is in issue #235.
  - Top-300 unplayable cards (#200, first batch): "search your library for a basic land card, put it onto the battlefield, then
    shuffle" (untapped, Prismatic Vista), Crop Rotation and Harrow; "lose life equal to its / that card's / that permanent's
    mana value" (Feed the Swarm, Withering Torment) with "creature or enchantment" targets; "return all attacking creatures to
    their owner's hand" (Aetherize); "untap up to N lands" (Frantic Search, Snap), asked one land at a time with a Done choice;
    Gamble (search for any card, then discard at random); the conditions "you control a creature with power N or greater"
    (Garruk's Uprising) and "you created a token this turn" (Mox Opal's Metalcraft-style mana, with the Metalcraft, Threshold,
    Hellbent, Delirium and Revolt word prefixes stripped); and "your devotion to <color>" as an amount (Gray Merchant of
    Asphodel). The rest of the list is in issue #200.
  - Popularity pass 1 (#200, #201, #202), the gaps shared by the most played cards: "You may play an additional land on each of
    your turns" (one more land drop for each, Exploration, Gitrog Monster); "You may play lands from your graveyard" (Crucible of
    Worlds), which uses a land drop; "Whenever you gain life, target opponent loses that much life" (Sanguine Bond, Vito) and
    its mirrors, where "that much" is the life actually gained or lost after doublers; "This artifact doesn't untap during your
    untap step" (Basalt Monolith, Mana Vault, with its upkeep payment and draw-step damage; a permanent that has lost its
    abilities untaps normally); the Enduring cycle (it returns when it dies as an enchantment that is not a creature, so it
    cannot die that way twice); "Creatures you control have {T}: Add one mana of any color" (Enduring Vitality; a summoning-sick
    creature still can't use it); "Equip legendary creature {N}" alongside a plain Equip line; Extort (a {W/B} payment per
    extort permanent on each spell you cast); and "You may look at the top card of your library any time", which is understood
    but changes nothing, since no player here uses the information. Not read: playing lands or casting spells from the top of
    the library (Oracle of Mul Daya), the Class level that adds a land drop (Druid Class), "chosen type in addition to its other
    types" (Roaming Throne).
  - Channel lands (#200): "Channel — {cost}, Discard this card: ..." is an ability used from the hand at any time, and
    "This ability costs {1} less to activate for each legendary creature you control" lowers only the generic part of the cost
    (Boseiju, Eiganjo, Otawara, Sokenzan, Takenuma). Their effects needed targets "attacking or blocking creature", "artifact,
    enchantment, or nonbasic land an opponent controls" and "artifact, creature, enchantment, or planeswalker"; "that player may
    search their library for a land card with a basic land type" (a dual land counts); "They gain haste until end of turn" after
    "Create two ... tokens"; and "return a creature or planeswalker card from your graveyard to your hand".
  - Chosen type and color (#200): Cavern of Souls, Unclaimed Territory and Pillar of Origins make one mana of any color
    only for a creature spell of the type named as they entered, and Delighted Halfling only for a legendary spell; the
    colorless mana of the land still pays for anything. Mana from Cavern of Souls or the Halfling that is spent on such a spell
    makes it uncounterable (a Cavern tapped for such a spell is treated as having made its colored mana). Kinnan's extra mana ("add one mana of any type that permanent produced") is not restricted, and it can be of the type the restricted mana would have been: the Halfling and Kinnan pay Freed from the Real's {U}, which repeats. "This creature is
    the chosen type in addition to its other types" adds the type to the permanent's type line (it goes to the graveyard as the
    card it was); "Other creatures you control of the chosen type get +1/+1" (Adaptive Automaton), "Creatures you control of the
    chosen color get +N/+N" (Heraldic Banner, Hall of Triumph), Metallic Mimic's extra +1/+1 counter for each other creature
    of its type that enters, and Roaming Throne's extra trigger for another creature of its type. Not read: Secluded
    Courtyard (mana for abilities too), cost reductions and "whenever you cast a spell of the chosen type" (Herald's Horn, Door
    of Destinies, Chronicle of Victory), "of the chosen color" for every player (Gauntlet of Power), and Caged Sun's extra mana.
  - Mana artifacts (#200): Chromatic Lantern ("Lands you control have {T}: Add one mana of any color"); Chrome Mox (you may exile a
    nonartifact, nonland card from your hand as it enters; its mana is any color of that card, none if it has none); Mox Amber (any
    color among your legendary creatures and planeswalkers); Mox Diamond (it enters only if you discard a land, otherwise it goes
    to the graveyard); Relic of Sauron (two mana, each one of its colors); Nyx Lotus (choose a color, mana equal to your
    devotion to it); The Great Henge (costs less by your greatest power; a counter and a card for each nontoken creature that
    enters). Mana that costs a creature or a card is used as an activated ability that puts the mana in your pool, which waits
    for the end of the step: Phyrexian Altar (sacrifice a creature), Springleaf Drum and Relic of Legends (tap an untapped
    creature, a legendary one for the Relic), Lion's Eye Diamond (discard your hand, sacrifice it). The three mana of "any one
    color" from Lion's Eye Diamond are chosen independently, as with Gilded Lotus. Not read: Throne of Eldraine, Herd Heirloom
    and Power Depot (restricted mana with other abilities), Forsaken Monument, Caged Sun.
    of its type that enters, and Roaming Throne's extra trigger for another creature of its type. Also read, for a
    permanent that named a creature type: "[Creature] spells [you cast] of the chosen type cost {N} less" (Herald's Horn, Urza's
    Incubator, which helps every player, and Gathering Stone's discount); Herald's Horn's upkeep look at the top card; watching
    triggers "of the chosen type" for casts, a creature entering, attacking or dying (Chronicle of Victory, Vanquisher's Banner,
    Kindred Discovery, Bloodline Pretender, Species Specialist, Reflections of Littjara); Door of Destinies, which pumps for each
    charge counter on it; and "Creatures of the chosen type have fear" for every player's creatures (Cover of Darkness). Not
    read: Secluded Courtyard (mana for abilities too), Gathering Stone's second ability, Morophon's reduction, "of the chosen
    color" for every player (Gauntlet of Power), and Caged Sun's extra mana.
  - Popular creatures (#200): "You may play two additional lands" (Azusa); "Untap all permanents you control during each other
    player's untap step" (Seedborn Muse); "{T}: Untap target Forest" (Arbor Elf, and the other basic land types); "Each spell you cast
    that's red or green costs {1} less" (once, even for a red-green spell); landfall "put a +1/+1 counter on each Plant creature you
    control" (Avenger of Zendikar), "create a Food token or a Treasure token" (you choose) and "create a 1/1 Insect token, or a copy
    of this creature with six or more lands" (Scute Swarm); "whenever one or more other creatures with power 2 or less enter"
    (Welcoming Vampire, once each turn); "whenever you create or sacrifice a token" (Mirkwood Bats) and "whenever you sacrifice a
    Clue / Food / Treasure / token / artifact / land" (Tireless Tracker); Orcish Bowmasters (the damage and "amass Orcs 1" when it
    enters and for each draw by an opponent except the one in their draw step; amass puts counters on your Army, or makes a 0/0
    Army token first); "each player sacrifices a creature or planeswalker / nontoken creature of their choice" and "each player
    who can't discards a card" (Plaguecrafter, Accursed Marauder); "that player sacrifices a creature" at an opponent's upkeep
    (Sheoldred, Whispering One); Laboratory Maniac (drawing from an empty library wins the game instead); and "you lose 1 life and
    create a Treasure token" on a second spell each turn (Lotho). Not read: Hullbreaker Horror, Imperial Recruiter, Terror of the
    Peaks, Disciple of Freyalise.
  - Popular creatures, second batch (#200): "Creatures your opponents control get -2/-2" (Elesh Norn); "Other permanents you control
    have indestructible" (Avacyn; a creature-only ability still never reaches a land or an artifact); "If an opponent would lose
    life during your turn, they lose twice that much" (Bloodletter of Aclazotz); "{T}: Put a +1/+1 counter on each artifact creature
    you control" (Steel Overseer); "Aura and Equipment spells you cast cost {1} less" (Danitha); a black-creature watch and
    "Sacrifice another black creature" (Ayara); "Whenever another creature enters, you may gain 1 life" (Soul's Attendant);
    Ragavan (a Treasure, and the top card of the damaged player's library, which you may cast until end of turn) with Dash (the
    alternative cost gives haste and returns the creature to its owner's hand at the next end step); Etali, Primal Storm (the top
    card of every library, cast for free in any number); a card cast from another player's library or exile (Plargg and Nassari,
    Etali, Ragavan) is its owner's: it goes to the owner's graveyard, hand or exile, not the caster's;
    Esper Sentinel ("draw a card unless that player pays {X}", X being its
    power, for the first noncreature spell an opponent casts each turn); Ledger Shredder (connive: draw, discard, and a counter if
    the discard wasn't a land); Phyrexian Metamorph (a copy of an artifact or creature, and an artifact too); and Imperial
    Recruiter ("a creature card with power 2 or less"). The Ferocious ability word is read like Metalcraft. Not read: Eternalize,
    Priest of Titania, Sanctum Weaver, Hullbreaker Horror, Syr Konrad, Braids.
  - Second popularity pass (the most played cards still missing one rules line): the Verge lands (a second color only with the right
    land), Spire of Industry, the Urza lands, the Spirit Guides (exile from hand for mana, no stack), opponents' creatures and
    artifacts entering tapped (Authority of the Consuls), untapping artifacts in other players' untap steps (Unwinding Clock),
    Explore, Silence and Ranger-Captain (opponents can't cast), Mental Misstep, Reprieve, Swan Song, the Elemental Blasts, Nature's
    Claim, Bedevil, Entomb and Buried Alive, Cabal Ritual and Rite of Flame, Gitaxian Probe, Greater Good and Altar of Dementia, Grave
    Pact, Bitterblossom, Command Beacon, Whispersilk Cloak and the other "can't be blocked" Auras and Equipment, "for each land" bonuses,
    tapping a target creature, and the keywords split second and rebound (Ephemerate). A Horizon land can now also tap for {C}.
  - The other half of a card (`Card.alternate`): an Adventure, a split card's second half and a modal card's back spell are
    cast from the hand under their own name, cost, color and mana value. A resolved Adventure goes to exile and the creature can
    be cast from there for as long as it stays; a countered or fizzled one goes to the graveyard. A split card has the first
    half's cost and mana value, not the sum. An Aftermath half is cast only from the graveyard (`CAST_GRAVEYARD`, like Flashback)
    and is exiled whether it resolves, is countered or fizzles. Still not played (listed as "Second face or half"): the Fuse
    option, a modal back that is a permanent, and melds.
  - Manifest dread (`Game.manifest_dread`, effect `ManifestDread`): look at the top two cards, one enters face down as a 2/2 (as
    for manifest; a creature card can be turned up for its mana cost) and the other goes to the graveyard. "Twice", "then put N
    +1/+1 counters on that creature" and "then attach this Equipment to that creature" are understood. "Whenever you manifest
    dread" and "when it dies this turn, manifest dread" are not.
  - Stun counters (`Game.untap`): a tapped permanent with a stun counter loses one instead of untapping, in the untap step and when an
    effect untaps it; an untapped one keeps its counters. "Tap target creature and put a stun counter on it" (and N counters), the
    "up to one/two/three" and "one or two" forms with "put a stun counter on each of them", and the same inside triggers are
    understood; "creatures your opponents control" is now a kind the plural patterns accept. Not understood: conditional
    counters ("if it's your turn"), counters on the source itself, "twice X", and the Siege/Battle cards.
  - "Change the target of target spell (or ability, or activated ability) with a single target" (`ChangeTarget`, `Game.change_target`):
    only a spell or ability with exactly one target (not a list of targets) can be aimed at; you pick another legal target for it, from
    the point of view of the spell's controller, and "unless that spell's controller pays {2}" (Divert) is asked of that player. Also
    "that targets only a player / a single creature / this creature" (Rebound, Muck Drubb, Silver Wyvern), "The new target must be a
    player / a creature" (folded into the effect), "to this creature" with an optional "you may" (Hydroelectric Specimen), "you may
    change the targets of target instant or sorcery spell" (Goblin Flectomancer, each target may stay) and Spellskite's "Change a target
    of target spell or ability to this creature" (you pick which target when it has several). "This creature" is the permanent whose ability
    is being aimed or is resolving (`Game.targeting_source`). Not understood: Willbender (morph), Reflecting Mirror's X, Torchling's
    forced block and Return the Favor's Spree.
  - Third popularity pass (`tests/test_popular_pass3.py`), the most played cards still missing a line: the Landscape fetch lands
    ("a basic Swamp, Forest, or Island card", Myriad Landscape's two lands that share a type); "Target creature you control deals
    damage equal to its power to ..." to a creature or planeswalker, any target, or each other creature and each opponent;
    "the greatest power among (other) creatures you control" as an amount; "this or that" additional costs made only of a
    sacrifice, a discard or life (`AdditionalCost.options`; a mana option such as Redirect Lightning's is not); search for a creature
    "with mana value X or less" onto the battlefield and "Shuffle CARDNAME into its owner's library"; Deflecting Swat's "choose new
    targets" (each target may stay); and a few single lines (Mithril Coat, Untimely Malfunction, Rakdos Charm, Damn).
  - Leftovers of the third popularity pass: an additional cost may offer several ways to pay, including mana ("pay 5 life or pay {2}",
    "sacrifice a creature or pay {3}{B}", three-way costs); the choice is made before targets (CR 601.2b) and a way counts as
    affordable only if the mana it adds can be paid. "You may cast a spell with mana value N or less from your hand without paying its
    mana cost" (Rishkar's Expertise); "Non-Human creatures you control get +3/+3"; "Until end of turn, creatures you control gain
    trample and get +X/+X"; "Return target spell or nonland permanent an opponent controls to its owner's hand"; and a mode named
    in front of its text ("\u2022 Sell Contraband \u2014 Create a Treasure token") reads as the mode itself.
  - Three single cards from the popularity passes (`tests/test_remaining_cards.py`): Victimize (choose two creature cards in your graveyard,
    sacrifice a creature, and if you do they return tapped), Malakir Rebirth ("that creature gains 'When this creature dies, return it to the
    battlefield tapped' until end of turn": `Permanent.returns_when_dies` holds the turn, and the game puts the trigger on the stack when
    it dies that turn) and Traverse the Outlands ("up to X basic land cards, where X is the greatest power among creatures you control").
  - Creatures that have to block (`tests/test_small_leftovers.py`): "All creatures able to block target creature this turn do so" (`Permanent.lured_turn`),
    the same on an Aura or Equipment ("... enchanted/equipped creature ...": Lure, Nemesis Mask, checked in `Combat._lured`), and "Target creature
    blocks this turn if able" / "... blocks this creature this turn if able" (`must_block_turn`, `must_block_what`: Torchling's ability). A creature that
    cannot block the attacker is not forced. "Put a stun counter on it" with nothing earlier to follow is the creature itself
    (`PutStunOnSource`); before, such a trigger was accepted and did nothing.
  - Morph, Megamorph and Disguise (`tests/test_morph.py`): a card with `Morph {cost}` can be cast face down for {3} (`Cast face down: <name>`,
    sorcery speed, as a colorless nameless 2/2 creature spell; a countered or dying one is the real card in the graveyard) and enters
    face down like a manifested card, keeping the real card and the cost to turn it up (`Permanent.turn_up_cost`). `Turn face up: ...`
    pays that cost, not the mana cost, at any time; Megamorph then adds a +1/+1 counter and "When/As this creature is turned face up"
    triggers (event `turned_face_up`); a Disguise creature has ward {2} while face down. Turning up is not entering, so "when it
    enters" does not happen. A morph cost may also be a sacrifice ("another creature", "two Mountains"), a card of a color to reveal, a
    card to discard, a return to hand, or life (`MorphCost`; it is offered only when it can be paid). Not read:
    "Whenever you turn a permanent face up".
  - Fourth popularity pass (`tests/test_popular_pass4.py`): keyword abilities are read from the rules text they stand for
    (`_KEYWORD_RULES` in `effects/common.py`, reminder text stripped first): Outlast, Fabricate, Soulshift, Modular, Evolve, Mentor,
    Mobilize, Bloodthirst, Renown and Transmute. Evolve's "greater power or toughness" is the condition `subject_greater`
    (`condition_holds` now takes the permanent the trigger is about); Mentor's target is "attacking creature with lesser power"
    (`target_options`); Mobilize makes tapped and attacking Warriors (`Game.tokens_join_attack`) that are sacrificed at the end step;
    Bloodthirst counts only if an opponent took damage this turn; Renown sets `Permanent.renowned`; Transmute searches for
    "mv=self", the discarded card's mana value, and is offered only at sorcery timing. Dredge (`dredge_of`) offers to mill N
    instead of each draw (`Game._dredge`); Umbra armor (`rules_statics` key `umbra_armor`) saves what its Aura enchants from
    destruction (`Game._saved_from_destruction`). An Aura may enchant a Forest, a Mountain, an Equipment, "artifact or creature you control"
    and the like (`_ENCHANT_HEAD`); Utopia Sprawl adds mana of the color chosen as it entered. Not understood: Mobilize X, "red or green
    creature" Auras, Dog Umbra and Umbra Mystic, Gift, Spree, Ninjutsu, Foretell.
  - Transforming double-faced cards and day/night (`tests/test_transform.py`): a `transform` card keeps its back face as `Card.flip`
    (mana value that of the front face); `Game.transform` swaps `Permanent.card` for it and keeps the front in
    `Permanent.transformed_from`, so counters, damage and Auras stay and the card leaves as its front face. A card is fully playable
    only if its back face is too (`unsupported_lines`). "Transform this creature", "When it transforms into CARDNAME", "Exile this Saga,
    then return it to the battlefield transformed" and "When it dies, return it ... transformed" are understood. Daybound and
    nightbound follow the day/night rule (`Game.day_night`, `_update_day_night` at each untap step: the previous turn's player cast no
    spells or two or more), and only that rule turns them over; the older "if no spells were cast last turn" werewolves use the
    upkeep conditions `no_spells_last_turn` and `two_spells_last_turn`. Not understood: Disturb, Craft, Living metal, More Than Meets the
    Eye, Meld, and transform costs or conditions that no template reads yet.
  - Distribute counters (`tests/test_distribute_counters.py`): "Distribute four +1/+1 counters among any number of target creatures you
    control" (Verdurous Gearhulk, The Earth Crystal, Elven Rite, Grove's Bounty with X) is `DistributeCounters`: the counters are
    given out one at a time as it resolves, so any split works, and nothing is targeted; a creature with hexproof or protection from the
    source is left out. Not understood: -2/-1 counters, "Vehicles and/or creatures", a "where X is" clause, and a second sentence
    on the same line (Glint Weaver, Undercity Upheaval).
  - Ninjutsu and Commander ninjutsu (`tests/test_ninjutsu.py`): `Ninjutsu {cost}` is the action `Ninjutsu: <card>`, offered to the
    active player once blockers are declared (`declare_blockers`) when they have an unblocked attacker (one that is neither blocked nor
    stays blocked) and the mana; Commander ninjutsu also from the command zone. Paying returns the attacker to its owner's hand and puts
    the ability on the stack (`Game._ninjutsu`); when it resolves the card, if it is still there, enters tapped and attacking the same
    player or planeswalker (`Game.ninjutsu_enter`) without being declared as an attacker. Not understood: Silver-Fur Master's discount
    and the many ninjas' own combat-damage triggers that no template reads yet ("that player discards", "target creature that player
    controls", "a Ninja you control deals combat damage").
  - Ninja combat-damage triggers (`tests/test_ninja_triggers.py`): a self trigger of "deals combat damage to a player" may speak of
    "that player" (`Event.maybe_player`: "that player discards two cards", "look at that player's hand"), and a target may be
    "creature that player controls" (`Game.targeting_player` while the trigger's targets are chosen, the resolving item's `player`
    after: Throat Slitter, Mistblade Shinobi). "Whenever a Ninja you control deals combat damage to a player" and "one or more Ninja or
    Rogue creatures you control deal ..." are watches on the new occurrence `combat_damage_dealt` (the second once per combat, via
    the batch Combat.deal_damage opens). Yuriko's reveal-and-drain is `RevealTopToHandDrain`; "Activate only during your turn." and a
    bare creature type as a target ("target Ninja you control") are read. Not understood: Skullsnatcher, Silent-Blade Oni, Coiling
    Stalker, Moon-Circuit Hacker, the counter-removing ninjas, Orochi Soul-Reaver (manifest), Silver-Fur Master.
  - Foretell (`tests/test_foretell.py`): `Foretell {cost}` is two actions. `Foretell: <card>` is offered on your own turn whenever you
    have priority and {2}: the card goes from the hand to exile and is recorded in `Seat.foretold` as (turn, card). From a later turn
    `Cast foretold: <card>` casts it from exile for the foretell cost at the card's usual timing, as a cast with a `GraveyardCast("Foretell",
    cost)` way (so X in the foretell cost works) whose `StackItem.foretold` makes "If this spell was foretold, ..." true (Poison the
    Cup, Starnheim Unleashed). Not understood: cards that grant foretell (Dream Devourer, Bohn), reduce its cost (Cosmos Charger, Ranar),
    count foretold cards (Niko Defies Destiny, Alrund), or foretell from elsewhere (Ethereal Valkyrie, The Foretold Soldier).
  - Disturb (`tests/test_disturb.py`): `Disturb {cost}` on the front of a transforming card is the action `Cast with disturb: <card>`,
    offered for a card in your graveyard at the back face's usual timing. The back face is cast (`whole` is the card, as with
    Aftermath) for the disturb cost as a `GraveyardCast("Disturb", cost, exile_after=True)`, so a countered or fizzled spell is exiled; a
    permanent enters as the back face (`transformed_from` the card) and "If CARDNAME would be put into a graveyard from anywhere, exile
    it instead" (`Replacements.graveyard_self`) exiles it when it leaves. Not understood: the back faces whose own abilities have no
    template yet (Dennick, Mirrorhall Mimic, Brine Comber, and others).
  - Warp (`tests/test_warp.py`): `Warp {cost}` is an alternative cost (`AlternativeCost.warp`), offered only when casting from the
    hand. A creature cast for it is exiled as the next end step begins (`Game._warp_exile`) and its owner may then cast it from exile
    (`exile_play`) from a later turn, for its full mana cost. "Creature or artifact" is a watch kind for entering and dying (a non-creature
    artifact that goes to a graveyard is announced as dying), and "..., if you've gained N or more life this turn" is read after the effect.
    Not understood: Warp costs that are not mana (Timeline Culler), Warp-Strike, and the other abilities of the Warp cards that have no
    template yet (Memorial Team Leader, Starwinder, Quantum Riddler, ...).
  - Gift (`tests/test_gift.py`): "Gift a card / a Treasure / a Food / a tapped Fish / an Octopus / an extra turn" asks as the spell is
    cast whether to promise it (`Game._choose_gift`: the first option is no gift, then one per opponent; only offered when what a
    promised gift adds can be done). A promised gift is a kick that costs nothing (`kicked` is 1), so the card's text is read
    with "the gift was promised" as "this spell was kicked": `IfKicked` adds an effect (with its targets), `KickedReplaces` stands in for
    the effect before it ("instead ..."), `IfNotKicked` is "if the gift wasn't promised". The opponent gets the gift before the spell's
    other effects, or as a permanent enters (`Game._give_gift`). Not understood: "that creature's controller", a promised gift inside a
    sentence ("... if the gift was promised."), "instead" with two cards from a graveyard, Kitnap, Octomancer, Starforged Sword.
  - Leftover templates (`tests/test_leftovers_4.py`): delirium (four card types in your graveyard, as a static and as an activation
    condition), "is equipped", "each player has N or less life", "you didn't cast a spell this turn", lords for two tribes ("Wolves and
    Werewolves"), tapping an untapped creature of a given type as a cost, "you attack with three or more creatures", "the end step" and
    "When ... dies" wordings, a sacrifice of the creature with the greatest power, "return two target ... cards", the Gift damage to
    that creature's controller, and a dead creature coming back transformed at the next end step.
  - `effects.py` is now the `infernal_machine/effects/` package, one module per purpose (`common`, `targets`, `outcomes`,
    `statics`, `costs`, `triggers`, `activated`, `mana`, `spells`), each importing only from the ones before it; `from
    infernal_machine.effects import ...` still works, so the game and the tests did not change. Every reader gives the same
    answer for all 32,115 cards as before the split.
  - Mana payment left `game.py` for `infernal_machine/payment.py` (#284), the way combat did: `ManaPayer` holds which permanents can
    make which mana, what pays a cost, and tapping them (with `ManaSource` and `Payment`). `Game` keeps thin methods that call it
    (`_pay_cost`, `_mana_sources`, `_spend_mana`), so the effects and the tests did not change. Casting followed in
    `infernal_machine/casting.py`: `Caster` holds the ways to cast a spell, its costs and options (kicker, buyback, gift, modes,
    X), its targets and putting it on the stack; names that stay in `game.py` (the prompts, `StackItem`, the card helpers) are
    reached as `g.NAME`, so either module can be imported first.
  - Events are a registry (`effects/events.py`): each "Whenever ..." an ability can wait for is declared once, with its rules
    text and, for the ones the game announces to a player's permanents, the occurrence that sets it off and who hears it
    (the player or each opponent). The game says what happened (`Game.happened("discarded", seat)`) and every event declared
    for it fires, so a new event for an occurrence the game already announces needs only a declaration. An event the game
    does not declare is an error, not a trigger that silently never fires; `tests/test_events.py` checks that every declared
    event is announced somewhere and every announcement names a declared event.
  - Rooms: one card with two doors. Either door is cast from the hand (the card itself is the front door, `alternate` the back); the Room
    enters as one permanent that reads as only its unlocked doors (`room_view`; the whole card waits in `real_card` and goes to the
    graveyard whole). "When you unlock this door, ..." triggers for that door only, as it enters and when a locked door is unlocked by
    paying its mana cost (`Unlock: ...`, a sorcery-speed special action). Eight of the 28 Rooms play so far; the others wait on manifest
    dread, stun counters and the like. Also read now: "deals N damage to target creature an opponent controls", enchantment creature tokens,
    and "a +1/+1 counter on each of up to two target creatures".
  - Hullbreaker Horror: "return target spell you don't control to its owner's hand" (a spell kind that names whose it is, like the rest of the
    spell targets), so its "choose up to one" mode trigger reads; a mode with nothing to aim at is not offered.
  - Sylvan Library: each seat remembers the cards it drew this turn (`drawn_cards`); at the draw step the player may draw two more, then
    chooses two of the cards drawn this turn (the draw step's own card too) and for each pays 4 life (not at 4 or less) or puts it on top
    of the library.
  - Urza's Saga: a chapter that says 'This Saga gains "..."' (`GainsAbility`) adds the line to the permanent's text for as long as it stays
    (the card goes back to the graveyard as printed; a gained "{T}: Add {C}." also tells a land what it makes), and "search for an
    artifact card with mana cost {0} or {1}, put it onto the battlefield" (read as mana value 1 or less). A land with no mana of
    its own is no longer a mana source.
  - Teferi's Protection: on top of the Ring's player protection, "your life total can't change" until your next turn
    (`Seat.life_locked`; `change_life` does nothing while it holds), "all permanents you control phase out" (the existing phasing,
    with what is attached), and a spell's own "Exile CARDNAME." sentence (it is exiled instead of going to the graveyard).
  - The One Ring: "you gain protection from everything until your next turn" (`Seat.protected`: nothing can target the player, damage
    to them is prevented, and it ends when their next turn begins), only "if you cast it" (`Permanent.cast`; a copy of the spell is not
    a cast). A "for each" amount in a later clause is now worked out when that clause is done, so "put a burden counter on it, then
    draw a card for each burden counter on it" draws for the counter just put there.
  - One filter grammar (`filters.py`): targets, mass effects, searches, graveyard returns, watching triggers and cost
    reductions all name a kind of card ("black creature", "nonland, nontoken permanent an opponent controls", "creature card with
    mana value 3 or less", "R|G"), and they all read it with `parse_filter` instead of four separate matchers. A "permanent" is
    now a card with a permanent type, so an instant no longer counts as one.
  - Rules-changing statics (#204), read from the permanent's own text:
    - "Creature spells you control can't be countered" / "Spells you control can't be countered": a counterspell does nothing
      to them.
    - "You may cast spells / creature spells / sorcery spells / Spirit spells as though they had flash": castable at instant
      speed by its controller.
    - "Your opponents can't cast spells during your turn" / "... during combat"; "Each player can't cast more than one spell each
      turn" / "You can't cast more than one spell each turn"; "You can't cast creature spells" / "noncreature spells".
    - "Activated abilities of artifacts can't be activated" (Stony Silence), including their mana abilities; Grand Abolisher
      ("During your turn, your opponents can't cast spells or activate abilities of artifacts, creatures, or enchantments"),
      where a land's mana ability is not stopped.
    - "Each land is a Swamp / Forest in addition to its other land types" (Urborg, Yavimaya, for every player's lands) and "Lands
      you control are every basic land type" (Dryad of the Ilysian Grove): the land can also tap for that color. Only plain
      basic-style lands get the extra mana; a land that is already special (a painland's pain, a filter land, a bounce land) and
      conditions that look for a Swamp are not changed. Not read: "Enchanted land is a Swamp", "pay {2} more to cast it with
      flash", "each opponent can cast spells only at sorcery speed" (Teferi, Time Raveler).
  - Panharmonicon and Yarok: a triggered ability of a permanent you control that triggers because an artifact or creature
    (or any permanent) entered triggers an additional time; each such permanent adds one. Both the entering
    permanent's own "When this enters" and watching "Whenever another creature enters" abilities count.
    "This ability triggers only once each turn" still holds.
- **Copying:**
  - Clone: "You may have this creature enter the battlefield as a copy of any creature on the battlefield." (also
    "a creature you control", and artifacts, enchantments or lands). It is decided as it enters, with a "Don't copy
    anything" choice, so the copy's enters abilities trigger. A copy has the other card's printed characteristics,
    not its counters or damage; a copy of a token isn't a token. It goes to the graveyard as the Clone card.
    Bots copy the biggest creature. What it may copy is a kind ("any creature", "any nonland permanent", "any artifact or
    enchantment", "a creature you control", "a creature an opponent controls", "a creature you control with power 4 or
    greater", "enter tapped as a copy of any land": tapped when it is a copy). The "except ..." clause is a list of changes
    (`CopyChanges`, shared with token copies): it isn't legendary, N/N, a type or a color in addition to its other types,
    keywords, a quoted ability (only one the engine understands), "an additional +1/+1 counter if it's a creature",
    "an additional loyalty counter if it's a planeswalker", X additional counters. Any other clause (a new name, "loses all
    other card types", "doesn't copy its color", conditional abilities) leaves the line unsupported. Phantasmal Image,
    Spark Double, Vesuva, Glasspool Mimic, Malleable Impostor, Phyrexian Metamorph, Altered Ego.
  - "Copy target instant or sorcery spell (you control). You may choose new targets for the copy." The copy goes on
    the stack above the spell and resolves first. It isn't cast (no cast triggers) and isn't a card, so it vanishes
    instead of going to the graveyard, even if countered. With the second sentence its controller picks targets
    again (the old ones are still choices); without it the copy keeps them.
    "..., then return it to its owner's hand." (Narset's Reversal) copies first, then the spell leaves the stack for its
    owner's hand without resolving. "Whenever you cast a Faerie or Wizard permanent spell, copy it." (Archmage of Echoes):
    a watch for either of two types and a permanent; the copy of a permanent spell becomes a token.
  - Abilities: "Whenever you activate an ability, if it isn't a mana ability, you may pay {2}. If you do, copy that ability.
    You may choose new targets for the copy." (Rings of Brighthearth; also "of an artifact" for Kurkesh, and Illusionist's and
    Battlemage's Bracers for the equipped creature's). The game raises "activated" for every activated ability that uses the
    stack (loyalty abilities included; mana abilities are paid with, not activated). "{2}, {T}: Copy target triggered ability
    you control. You may choose new targets for the copy." (Strionic Resonator; "twice ... the copies" for Mister Fantastic)
    targets a triggered ability of yours on the stack. A copy of an ability keeps its X and (unless new targets are chosen) its targets.
  - "Create a token that's a copy of target creature" and populate were added earlier.
- **Control change:** "Gain control of target creature." (permanent), "Gain control of target creature until end of turn.
  Untap that creature. It gains haste until end of turn." (Threaten), and Control Magic ("Enchant creature. You
  control enchanted creature."). The permanent moves to the new controller's battlefield, is summoning sick for
  them (haste fixes that), and leaves combat. Its owner doesn't change, so it goes to its owner's graveyard if it
  dies. Threaten's effect ends in the cleanup step; Control Magic's ends as soon as the Aura stops being
  attached or leaves, and the creature goes back to whoever controlled it before. A lone "Untap that creature."
  isn't understood. Bots aim Control Magic at an opponent's creature.
- **Vehicles:** "Crew N" is an ability at instant speed: tap untapped creatures you control, one at a time, until their
  total power is N or more (summoning-sick creatures can crew, the Vehicle can't crew itself). Until end of turn the
  Vehicle is an artifact creature, with its printed power and toughness, so it can attack (not the turn it arrived)
  and block, and it dies like a creature. It goes back to being a plain card at end of turn or when it leaves. It
  can't be crewed twice in a turn, and bots crew whenever they can.
- **Sagas:** "I — ...", "II — ..." and "I, II — ..." chapters. A Saga enters with a lore counter and its
  chapter I triggers; each of its controller's turns, after the draw step, it gets another and the matching chapter
  triggers. Once the last chapter's ability has resolved it is put into the graveyard. A Saga is all or nothing: if
  any chapter isn't understood it has none, and the report lists its lines.
- **Protection:** "Protection from red" (and "from red and from blue"), printed or given by Equipment, an Aura, a
  static ability, or "gains protection from red until end of turn". The protected permanent can't be targeted,
  damaged, blocked, enchanted or equipped by the source. What counts about the source is its colors, its card types
  and whether it is monocolored, multicolored or colorless, so these work too: "protection from everything", "from
  all colors", "from monocolored" / "multicolored", "from creatures" / "artifacts" / "enchantments" / "instants" /
  "sorceries" / "planeswalkers". Protection from creatures stops creatures blocking it and creature damage and
  abilities, but not a Bolt. An Aura or Equipment of a type it is protected from falls off. A spell that targeted it
  before it gained protection fizzles.
  - **"Protection from the color of your choice"** (Mother of Runes, Gods Willing), as "Target creature (you
    control) gains protection from the color of your choice until end of turn" or "This creature gains ...": the
    controller picks one of the five colors as it resolves. Bots take the first (white).
- **Ward:** when an opponent's spell or ability targets a warded permanent, a ward trigger goes on the stack and the
  spell or ability is countered unless its controller pays. The cost can be mana ("Ward {2}"), life ("Ward—Pay 3
  life."), discarding ("Ward—Discard a card.") or a mix ("Ward—{1}, Pay 2 life."); if they can't pay they aren't
  asked, and bots always pay when they can. Ward can also be given: "Other creatures you control have ward {1}",
  "Equipped creature has ward {2}". You can't ward yourself. Not supported: tapping or sacrificing as a ward cost.
- **Exile until it leaves:** Oblivion Ring, Banishing Light and Fiend Hunter exile a permanent, and when the source
  leaves the battlefield for any reason the exiled card comes back under its owner's control as a new permanent
  (summoning sick, without counters or attachments, and its "enters" abilities happen again). Tokens exiled this way
  are gone for good, and a commander that went to the command zone instead isn't returned. If the source has left
  by the time the exile ability resolves, nothing is exiled. "Another target" can't be the source itself.
- **Flicker and delayed returns:** "Exile target creature you control, then return it to the battlefield under its
  owner's (or your) control" (Cloudshift, Ephemerate) brings it back at once; "Exile target creature. Return it to the
  battlefield under its owner's control at the beginning of the next end step" (Flickerwisp's "another target
  permanent" too) or "...to its owner's hand at the beginning of the next end step" waits. It comes back as a new
  object with no counters, summoning sick, and its enters triggers happen again. A token is gone for good. Cast
  during the end step itself, the card waits for the next turn's end step.
- **Exiling a spell:** "Exile target (kind of) spell." and "Counter target spell. If that spell is countered this way,
  exile it instead of putting it into its owner's graveyard." The spell goes to its owner's exile, not the graveyard.
- **Exile, then play it:** "Exile the top card (or N cards) of your library. You may play it this turn" and
  "...Until the end of your next turn, you may play those cards." The cards sit in exile and show up as "Cast from
  exile: ..." and "Play land from exile: ..." until the permission ends (a land uses your land drop; each card can
  be played once). "Your next turn" is the next turn that comes round to you in normal order. Without "you may play",
  "Exile the top N cards" just exiles them. Bots play exiled cards like cards in hand.
- **Modal spells:** you choose the modes as you cast. Only modes that have a legal target are offered, a mode can't
  be chosen twice, and "one or both" / "one or more" let you stop with "Done choosing modes" once you have enough.
  Chosen modes happen in the order printed. If any mode isn't supported, the whole card is unsupported, and the
  report lists the mode.
  - **Confluence** ("Choose three. You may choose the same mode more than once."; "Choose up to four" for Moment of
    Reckoning): you make that many picks, and a mode may be picked again. A mode with no legal target is not offered,
    but one possible mode is enough to fill all the picks; each pick chooses its own targets. "Choose X" and the
    pawprint Seasons ("worth of modes") are not read.
  - **Pawprint modes** ("Choose up to five {P} worth of modes. You may choose the same mode more than once.", a Season): each
    mode costs the pawprints written before it; you keep picking until the five are spent or you say "Done choosing modes", and a
    mode that no longer fits is not offered. Season of Gathering, Season of Loss and Season of Weaving work ("Choose artifact or
    enchantment. Destroy all permanents of the chosen type.", "Choose an artifact or creature you control. Create a token that's a
    copy of it.", "Draw a card for each creature that died under your control this turn.", "Exile target nonland permanent. Its
    controller draws a card.", "Return target permanent card with mana value 3 or less from your graveyard to the battlefield with an
    indestructible counter on it." for Season of the Burrow); Season of the Bold (a delayed trigger) is not read, and neither is
    "Choose X". A creature with a keyword counter (flying, indestructible, lifelink ...) has that keyword (CR 122.1b).
  - **Spree** ("+ {1}{U} — Counter target spell."): you choose one or more modes, each once, and pay the mana cost plus the cost of every mode you chose; a mode you could not pay for on top of the ones already chosen is not offered, and the modes happen in printed order (CR 702.172). It works for a card whose every mode is read: Three Steps Ahead, Insatiable Avarice, Explosive Derailment, Phantom Interference and Unfortunate Accident. The others wait on one mode each (Return the Favor copies an ability, Requisition Raid puts a counter on each creature "target player controls", Shifting Grift exchanges control ...).
  - **Entwine {cost}:** offered (yes or no) when every mode has a target and the extra cost can be paid; paying it
    does all the modes. **Escalate {cost}:** each mode beyond the first adds the cost, and a mode that would cost
    more than the caster has isn't offered. Only mana costs are understood ("Escalate\u2014Discard a card" leaves
    the card unsupported). Bots always entwine when they can, and keep adding modes while they can pay.
  - **Modal triggers and abilities** ("When this creature enters, choose one \u2014", "{T}: Choose one \u2014"): the
    modes are chosen when the ability goes on the stack, before its targets. It isn't put on the stack if no
    mode has a legal target (and can't be activated at all). One mode that isn't understood leaves the whole
    ability unsupported.
- **Zones:** bounced permanents go to their owner's hand, and tokens stop existing. A commander headed for the
  hand can go to the command zone instead. Cards keep their owner: a creature you reanimate from an opponent's
  graveyard enters under your control, but goes back to their graveyard when it dies. Graveyard targets are
  checked again on resolution, and a spell with no legal graveyard target can't be cast.
- **Land ramp:** the player picks each land from the matching cards in their library ("basic land", or lands
  with the listed land types, which includes non-basic lands like Steam Vents for "Island or Mountain"),
  then the library is shuffled. Lands put onto the battlefield trigger landfall. A land put into the hand is
  revealed when the card says so.
- **Extra turns, monarch and goad:**
  - Extra turns go to the player who asked, right after the current turn; the latest one asked for goes first,
    and regular turn order then carries on from where it was.
  - The monarch draws a card at their end step. Combat damage dealt to the monarch by a creature makes that
    creature's controller the monarch. If the monarch loses, the active player becomes monarch.
  - **The initiative:** "You take the initiative" makes you venture into the Undercity (`undercity.py` has the
    rooms: Secret Entrance, Forge, Lost Well, Trap!, Arena, Stash, Archives, Catacombs, Throne of the Dead
    Three). You also venture at your upkeep while you hold it, and combat damage to the holder from a creature
    takes it (each hit is checked on its own, so two players' creatures hitting at once give it to the first
    one resolved). If the holder loses, the active player takes it. Each room's ability goes on the stack and
    uses the normal targeting, so the player chooses targets and the next room (when there are two exits);
    leaving the last room completes the dungeon and the next venture starts over. The Throne's creature enters
    with three +1/+1 counters and hexproof until its controller's next turn begins. Bots take the first exit and
    put the Forge's counters on their own creature. "Whenever you take the initiative" and "if you have the
    initiative" aren't understood.
  - **Voting:** "Starting with you, each player votes for X or Y" (and, for Council's Judgment, for a nonland
    permanent you don't control), with the card's own outcome: "For each X vote, ..." (Tivit),
    "If X gets more votes [or the vote is tied], ..." (Plea for Power), or "Exile each permanent with the most votes
    or tied for most votes". The vote goes round in turn order starting with the caster, and every vote is public.
    Only outcomes that need no target are understood, and a vote with no outcome is ignored with its card. Bots
    vote against an opponent's permanent, and for the first word otherwise. Capital Punishment's two-part
    outcome ("Each opponent sacrifices a creature for each death vote and discards a card for each taxes vote") is
    two per-vote outcomes; the second part takes the first's subject if it has none.
  - An additional combat phase goes right after the current phase (after combat ends, if it comes from inside
    combat), with an additional main phase after it if the card says so. Cast before combat, it simply gives
    you two combats, and creatures tapped in the first can't attack in the second.
  - A goaded creature must attack each combat if able, and not the goader if another opponent can be attacked.
    It lasts until the goader's next untap step. "Goad all creatures you don't control" goads every creature
    each opponent controls.
  - "Whenever you become the monarch" and "Whenever an opponent becomes the monarch" trigger only when the
    monarch actually changes.
  - "... unless that player pays {N}": the player who cast the spell or drew the card is asked whether to pay
    when the trigger resolves, and is only asked if they can. Understood only for effects that need no target
    (draw, create a token, gain or lose life).
- **Scry, surveil and mill:** scrying and surveilling look at the top cards one at a time and choose to keep
  each on top or put it on the bottom (scry) or into the graveyard (surveil). When two or more stay on top the
  player is asked which goes on top next (bots keep the order). Only the scrying player sees the cards. Surveil's graveyard cards are public. Milling
  more cards than the library holds just mills what's there, and the player loses on their next draw.
- **Discard:** the player discards the cards they choose, unless it says "at random" (then nobody is asked) or
  "their hand" (all of it goes, in order, and nobody is asked). Discarding more cards than the hand holds just
  empties it, and every discard is public. Thoughtseize-style effects reveal the hand to everyone, then the
  caster picks from the cards that fit ("nonland", "noncreature, nonland", "mana value 3 or less"); if none fit,
  the hand is only revealed. The three sentences are understood only together. Bots discard their worst card
  (a land if more than half the hand is lands, otherwise the most expensive spell), and take the most expensive
  card they can see; cards from an opponent's hand they don't know count as worth nothing. Not understood: "Discard
  a card, then ..." followed by anything but a draw, "whenever you discard", madness, and discarding "that many".
- **Library and mana tricks:** Chaos Warp ("The owner of target permanent shuffles it into their library, then reveals the top
  card. If it's a permanent card, they put it onto the battlefield": the owner shuffles and reveals, a token just
  vanishes, an Aura stays on top), Sensei's Divining Top ("{T}: Draw a card, then put this artifact on top of its
  owner's library"), and Mana Drain (the {C} equal to the countered spell's mana value, X included, arrives at the
  beginning of your next main phase and is lost at the end of it).
- **Keywords:**
  - **Prowess:** whenever you cast a noncreature spell, +1/+1 until end of turn.
  - **Shadow:** it can block or be blocked only by creatures with shadow. **Skulk:** it can't be blocked by creatures
    with greater power. **Devoid** is accepted: the card data already has no color.
  - **Changeling** (and the older "this card is every creature type"): the card's type line lists every creature type
    (`infernal_machine/creature_types.py`, from Scryfall's catalog), so a Goblin lord, a trigger that watches Goblins and a
    tribal attack restriction all see it. Players are shown "every creature type". A type added by a later set is missing
    until it is added to that list. Not read: giving or taking away creature types (Maskwood Nexus, Amoeboid Changeling).
  - **Fear:** only artifact and black creatures can block it. **Intimidate:** only artifact creatures and creatures that share a
    color with it. **Horsemanship:** only creatures with horsemanship. **Islandwalk, Swampwalk, Mountainwalk, Forestwalk and
    Plainswalk:** it can't be blocked while the defending player controls a land of that type (snow and nonbasic landwalk are
    not read). A printed "This creature can't be blocked." works like the granted one.
  - **Blocking limits** read from the creature's own text: "can't be blocked by creatures with power N or less / greater" (by
    the blocker's current power), "by artifact creatures", "by Walls", "by blue creatures" (any color), "by creatures with
    flying"; "can't be blocked except by black creatures" / "by creatures with flying"; "can't be blocked by more than one
    creature" (further blockers are not offered the block); "can't be blocked except by three or more creatures" (fewer
    blockers than that and it is unblocked instead, as with menace); "can't block creatures with power N or greater"; and
    "can't block and can't be blocked". The group forms ("each creature you control can't be blocked by more than one
    creature") and the activated "{1}{G}: can't be blocked this turn" forms are not read.
  - **Flanking:** when it is blocked, each blocker without flanking gets -1/-1 until end of turn (done as the blockers are
    set, not from a trigger on the stack). **"All creatures able to block this creature do so."** forces every untapped
    creature that can block it to, and they are not asked about other attackers. **"{2}{U}: This creature can't be blocked
    this turn."** and **"Target creature can't block this turn."** (as an ability, a spell or an enters trigger) last until end
    of turn. Not read: "can't block this creature" (only one attacker), "up to two target creatures can't block", and "target
    creature with power N or less can't be blocked".
  - **Being blocked:** "Whenever this creature becomes blocked, ..." goes on the stack once the blockers are set, with the
    player attacked as "defending player" and the number of blockers past the first. **Bushido N** (+N/+N when it blocks or
    becomes blocked), **Afflict N** (the defending player loses N life) and **Rampage N** (+N/+N for each blocker past the
    first) use it, and so does "blocks or becomes blocked, ..." in the card's own words. **"This creature must be blocked if
    able."**: its defender picks one untapped creature that can block it (no question if only one can), and a creature
    blocks only one attacker. Not read: "becomes blocked by a creature" and "blocks a creature" (they need to know which
    creature), and "defending player discards a card".
  - **"This creature attacks each combat if able.":** the creature is never offered "Don't attack"; its controller still
    picks whom it attacks. A creature that can't attack (tapped, summoning sick, defender) is not asked.
  - **Infect:** its damage to a player is that many poison counters instead of life loss, and its damage to a creature is
    that many -1/-1 counters instead of marked damage. **Wither:** the creature part only. **Toxic N:** combat damage to a
    player also gives N poison counters (several Toxic keywords add up). A player with ten or more poison counters loses the
    game. Poison shows in the board view and the text client. Toxic granted by another card is not read.
  - **Living weapon:** a 0/0 black Phyrexian Germ token is created and the Equipment attached to it when it enters.
  - **Echo {cost}:** at your next upkeep after it enters you pay once (you are asked, if you can) or sacrifice it.
  - **Delve:** exiling cards from your graveyard pays for generic mana. The engine exiles as few as will do, and you
    choose which. **Cascade:** a trigger above the spell exiles cards from your library until a nonland card that costs
    less; you may cast it for free, and the rest go to the bottom in a random order (a cascade spell's X counts as 0 on
    the card but its chosen X counts for the comparison).
  - **Convoke:** while the spell is paid for, each untapped creature you control (summoning sick ones too) can be tapped for
    {1} or for one mana of its color; a colorless creature pays only generic mana. **Improvise:** the same with artifacts,
    for generic mana only. They count as extra mana sources after your lands and mana creatures, so creatures are tapped
    only for what the lands can't cover (a creature that makes mana is used for its mana, once), and they come out of the
    castability check like any other source. "Each creature that convoked this spell ..." lines are not read.
  - **Devour N:** as it enters you may sacrifice any number of other creatures (asked one at a time, then Done); it
    gets N +1/+1 counters for each. The bot never devours.
  - **Replicate {cost}:** you choose how many times to pay when you cast (any affordable number); a trigger above the
    spell makes that many copies, each with new targets. A copy of an Aura spell becomes a token Aura. **Storm** (a copy
    for each spell cast before it this turn, by anyone) and **Gravestorm** (a copy for each permanent put into a
    graveyard this turn) use the same trigger.
  - **Ascend:** with ten or more permanents you get the city's blessing for the rest of the game, if you control a
    permanent with Ascend ("as long as you have the city's blessing" works in static abilities).
  - **Affinity for <type>s:** costs {1} less for each of that type you control.
- **Reanimation Auras** (Animate Dead): "Enchant creature card in a graveyard" is cast on a creature card in any
  graveyard; when it resolves the creature comes back under your control and the Aura is attached to it, and if the
  Aura leaves the battlefield the creature is sacrificed. The tapped version (Dance of the Dead) is understood
  too, but its other lines are not. Necromancy (it becomes an Aura as it enters) is not built.
- **Kaalia of the Vast:** "Whenever this creature attacks an opponent, you may put an Angel, Demon, or Dragon creature
  card from your hand onto the battlefield tapped and attacking that opponent." It attacks the same player and
  triggers nothing for attacking. A legendary card's short name ("Kaalia", "Edgar") is read as the card itself.
- **Cumulative upkeep {1}** (Mystic Remora): at your upkeep it gets an age counter and you pay the cost once for each
  counter, or sacrifice it. You are asked if you can pay. Mana costs only; "Cumulative upkeep—Pay 1 life" is not built.
- **Reordering the library:** "Look at the top three cards of your library, then put them back in any order. You may
  shuffle." (Ponder, Sensei's Divining Top's first ability) and "Draw three cards, then put two cards from your hand on
  top of your library in any order." (Brainstorm). You choose the order; the first card you pick goes on top.
- **Look at the top N (impulse effects):** "Look at the top four cards of your library. Put one of them into
  your hand and the rest on the bottom of your library in any order." and "Look at the top five cards... You may
  reveal a creature card from among them and put it into your hand. Put the rest on the bottom..." are understood
  only as a whole. The rest go to the bottom in a random order (the engine picks the order for "any order").
  The optional reveal shows everyone the card; the plain version keeps it private. Bots take the highest
  mana value card.
- **Tutors:** the searcher picks from the matching cards in their library, which is then shuffled. Other players
  only learn which card unless it says "reveal it". If nothing matches, the library is just shuffled.
  "With mana value 3 or less / 3 or greater / 3" works for searches and for graveyard targets
  ("Return target creature card with mana value 2 or less from your graveyard to your hand"); only the cards that
  match are offered. "A land card" can go onto the battlefield (any land, not just a basic). Reanimate's "You lose
  life equal to its mana value" follows the card it put onto the battlefield.
  The kind can also be "legendary" or "legendary creature", "nonbasic land", or a subtype: "Aura", "Equipment",
  "Vehicle", "Saga" ("an Equipment card with mana value 2 or less"). The same kinds work for cards in a
  graveyard ("Return target legendary creature card from your graveyard to your hand"). "Return ... to the
  battlefield tapped" is supported. Land searches also cover "a nonbasic land card" and "up to two Forest (or
  Mountain or Forest) cards" onto the battlefield, tapped or not. "Your opponents control" works in "Return all
  creatures your opponents control to their owners' hands" and in destroy and exile all. Tribal cards work too: a
  capitalized subtype before "card" ("an Elf card", "target Goblin card from your graveyard"), but only a single
  word (not "Time Lord"). Cards in a graveyard are offered by name, so two copies of a card are one choice.
- **Targets:** "another target ..." (bounce, destroy, exile) can't be the source itself, and "up to one target ..."
  (bounce, destroy, exile) adds a "No target" choice at the end of the list; the spell can be cast even when there
  is nothing to target. Bots take a real target when there is one.
  - **"Up to two (three, four) target creatures"** (also artifacts, enchantments, permanents, nonland permanents,
    lands, creature tokens, and creature cards in your graveyard) for bounce, destroy and exile: one target prompt
    per target, each with "No target", and a target already chosen can't be chosen again by the same effect.
  - **More kinds of target:** "creature token", "nontoken creature", "tapped / untapped / attacking creature" and
    "land", each also with "you control" / "an opponent controls".
- **Mass effects:** nothing is targeted, so hexproof doesn't help. A restriction ("with flying", "with power 4 or
  greater", "nonblack") is checked when the effect resolves, using the permanent's current keywords and stats, so
  a creature that was given flying until end of turn counts. Only the keywords the engine knows are accepted; "with a
  +1/+1 counter on it" and similar aren't supported. Indestructible permanents survive
  "destroy all" but not exile or sacrifice. Everything leaves the battlefield at the same moment, so a
  creature watching for deaths triggers for every other creature that died with it, and a creature with
  "Whenever this creature or another creature dies" sees itself go too. The same is true when several
  creatures die to damage at once. A player chooses their own creature to sacrifice, in turn order.
  - **More restrictions:** "with mana value N or less / greater" (any permanent, not just creatures), "nontoken",
    "creature tokens", "legendary", "tapped" / "untapped", "nonbasic" (lands), plus the existing keywords, power,
    toughness and color. **"Except":** "except (for) artifact (enchantment, legendary, white, ...) creatures",
    "except (for) creatures with flying" and "except for tokens" leave those alone. "Your opponents control" works
    in all of them.
  - **Wipes that give something back:** "Destroy all creatures. For each creature destroyed this way, its controller
    creates a 1/1 white Spirit creature token." (also for exile): a token per creature that really left, to its
    last controller; an indestructible survivor gives nothing. "Then create a 3/2 ... token for each nontoken creature
    you controlled that was destroyed this way." (Ceaseless Conflict) pays only the caster, and "Each player creates a
    0/0 ... Fractal creature token and puts a number of +1/+1 counters on it equal to the total power of the creatures
    they controlled that were exiled this way." (Oversimplify) gives everyone one token, as big as what they lost (as
    it last was); with no counters it dies at once.
  - **Sacrifice:** "Each player (opponent) sacrifices two lands", "...a nonland permanent", "...an artifact or
    enchantment", "...all creatures they control", "...a creature with the greatest power among creatures they
    control" (they choose among the tied greatest), and "Sacrifice all creatures you control." With fewer
    than asked, they sacrifice what they have.
  - **Also:** "deals N damage to each creature your opponents control" and "All creatures get -2/-2 until end of turn."
    Farewell works as a plain modal spell ("Choose one or more" with "Exile all graveyards"). "That are one or more colors / colorless / multicolored / monocolored" works in destroy and exile all ("Exile all
    nonland permanents that are one or more colors"), and so do "an attacking / tapped / untapped creature" in the
    sacrifice effects. Not built: other "that are ..." conditions.
- **Regeneration:** "Regenerate target creature.", "{B}: Regenerate this creature." and "Regenerate each creature you
  control." give a shield that lasts until end of turn (several stack). The next time the creature would be
  destroyed, by a destroy effect or by lethal damage or deathtouch, it is tapped, loses all its damage and leaves
  combat instead (a blocked attacker stays blocked). "It can't be regenerated" and "They can't be regenerated" after
  a destroy effect make that effect skip shields. Exile, sacrifice and zero toughness aren't destruction, so shields
  don't help. Activating in response works like any ability, but bots don't regenerate on their own.
  "Sacrifices the creature with the greatest power" isn't supported yet.
- **Fight, proliferate, persist and undying:**
  - "Target creature you control fights target creature you don't control." (also "fights another target creature")
  - "It fights target creature you don't control." / "Then that creature fights up to one target creature an opponent controls.": the creature the sentence before it gave a pump or counters to is the one that fights; with no sentence before it, the source creature fights ("When this creature enters, it fights up to one target creature you don't control."). "Then it fights" after nothing is not read. Epic Confrontation, Hunt the Weak, Chelonian Tackle, Swift Kick, Savage Smash and the like work; the ones with a condition on the counters (Ancient Animus), another sentence ("exile it instead", excess damage) or a color in the target (Hunt the Hunter) do not.
    and "Target creature you control deals damage equal to its power to target creature you don't control." (a bite,
    one-sided). It takes two targets; each deals damage equal to its power to the other at the same time, with its
    deathtouch and lifelink. If either target is gone or they are the same creature, nothing happens.
  - "Proliferate." lets you pick any permanents (yours or an opponent's) that have counters, or planeswalkers; each gets
    one more of every kind it has. You choose one at a time and finish with "Done". Bots pick only their own.
  - Persist and undying: when the creature dies with no -1/-1 (persist) or +1/+1 (undying) counter on it, it comes
    back from the graveyard under its owner's control with one. It is a dies trigger, so it uses the stack and
    can be answered; a token or a card that went somewhere else instead (a commander in the command zone) doesn't return.
- **Exile:** each player has an exile zone. Exiled creatures don't "die", so dies triggers don't fire.
  A commander heading to exile or the graveyard can go to the command zone instead.
- **Targets:** chosen when the spell is cast. If every target is gone when it resolves, the spell
  does nothing ("fizzles"). Hexproof and shroud are respected, and a spell with no legal target can't be cast.
- **Partial text:** if any sentence isn't understood, the spell still resolves but does nothing,
  and the `resolve` event is marked `"unsupported": true`. The engine never does half of what a card says.
- **Triggered abilities on permanents:** these use the same effect list as spells.

  | Trigger | Example |
  |---|---|
  | When this creature enters, ... | Mulldrifter: "When Mulldrifter enters, draw two cards." |
  | When this creature dies, ... | |
  | Whenever this creature attacks, ... | |
  | Whenever this creature blocks, ... | |
  | When this creature enters or dies, ... (also "attacks or blocks"; one ability per event) | |
  | Whenever a creature you control attacks, ... (once per attacker) | |
  | Whenever you draw a card, ... (once per card; the opening hand doesn't count) | |
  | Whenever an opponent draws a card / gains life / loses life, ... | Sheoldred, the Apocalypse |
  | Whenever you draw your second card each turn, ... | |
  | Whenever an opponent sacrifices a creature, ... | |
  | Whenever you discard a card / an opponent discards a card, ... | Megrim |
  | Whenever an opponent searches their library, ... | Ob Nixilis, Unshackled (the event; its effect is not built yet) |
  | Whenever a Pest (Elf, token, creature token) you control dies / another Elf you control enters, ... | |
  | Whenever (another) creature (permanent) you control leaves the battlefield, ... | |
  | Whenever a creature enters / dies, ... its controller ... | |
  | Whenever this creature deals combat damage to a player, ... | |
  | At the beginning of your upkeep / end step, ... | |
  | At the beginning of each upkeep / each end step, ... (every player's turn) | Tendershoot Dryad |
  | At the beginning of combat on your turn, ... | |
  | Whenever you gain life / lose life, ... (once per event, not per point) | Dina, Soul Steeper |
  | Whenever you sacrifice a creature, ... | Smothering Abomination |
  | Whenever another creature / a nontoken creature you control / an artifact ... enters, ... | Soul Warden |
  | Whenever a land you control enters, ... (Landfall) | |
  | Whenever (this creature or) another creature (you control) dies, ... | Zulaport Cutthroat |
  | Whenever a creature an opponent controls dies, ... | Yahenni, Undying Partisan |
  | When enchanted creature dies, ... | |
  | Whenever one or more cards leave your graveyard, ... (once per event) | Quintorius, History Chaser |
  | Whenever a player sacrifices a permanent / another permanent, ... | Merchant of Venom |
  | Whenever you lose life for the first time each turn, ... | |
  | Whenever a creature (a permanent) you control becomes tapped, ... (attacking, tapping for mana or as a cost, or a tap effect; not entering tapped) | Quest for Renewal (whose creatures also untap in each other player's untap step while it has four quest counters) |
  | Whenever you cycle a card (another card), ... / Whenever you cycle or discard a card, ... | Drannith Healer, Pitiless Vizier |
  | Whenever you scry, ... / Whenever you surveil, ... / Whenever you scry or surveil, ... (scry 0 and surveil 0 are no event) | Denzilore Fatehold, Nimrodel Watcher |
  | Whenever you attack with a creature alone, ... (also "a creature you control attacks alone"; "it" is the attacker; the Exalted keyword) | Black Panther, Aven Squire |
  | Whenever one or more creatures you control attack, ... (once) | |
  | Whenever an opponent attacks with creatures, if two or more of those creatures are attacking you and/or planeswalkers you control, ... | Mangara |
  | Whenever a creature enters under an opponent's control, ... (or "a creature an opponent controls enters"; "you may have that player lose 1 life") | Blood Seeker |
  | Whenever a creature (with power 4 or greater / toughness 4 or greater / power 2 or less / with flying / with a +1/+1 counter on it) you control enters, dies or attacks, ... | Kiora, Kheru Bloodsucker, Raid Bombardment ("the player or planeswalker that creature is attacking"), Skyclave Shadowcat |
  | Whenever you cast a spell from your graveyard / from anywhere other than your hand, ... (and "a player casts a spell from their graveyard") | |
  | Whenever you cast a multicolored spell, ... ("the number of colors that spell is" is an amount) | Tome of the Guildpact, Mana Cannons |
  | Whenever a player casts a spell, that player gains X life, where X is the number of cards in all graveyards with the same name as that spell. | Aven Shrine |
  | Whenever a creature card is put into your graveyard from anywhere, ... (dying, discarding, milling, cycling and spells all count; tokens are not cards) | |
  | Whenever you expend 4, ... (as the mana you have spent on spells this turn reaches 4) | |
  | At the beginning of your draw step, ... ("draw an additional card", "two additional cards", and "remove two hour counters" work) | Well of Ideas, Midnight Oil |
  | At the beginning of each other player's draw step, that player draws an additional card. | Well of Ideas |
  | At the beginning of each opponent's upkeep / each opponent's end step / an opponent's end step, ... ("that player" is whose turn it is; "if that player didn't cast a creature spell this turn"; damage equal to the cards in their hand, or minus 4) | Predatory Advantage, Price of Knowledge, Viseling |
  | "Power and toughness are each equal to the number of cards in your hand" is a base size; "Players have no maximum hand size" and "Your maximum hand size is equal to the number of hour counters on this enchantment" decide who discards at cleanup. | Overbeing of Myth, Price of Knowledge, Midnight Oil |
  | Whenever you cast or copy an instant or sorcery spell, ... (Magecraft) | Archmage Emeritus |
  | Whenever you cast an instant or sorcery spell with mana value 5 or greater (from your hand), ... | Dirgur Focusmage |
  | Whenever one or more creatures (creature tokens) you control deal combat damage to a player, ... (once per player hit) | Striding Shotcaller |
  | Whenever you gain life for the first time each turn, ... | Leech Collector |
  | Whenever an opponent draws their second card each turn, ... | Faerie Mastermind |
  | Whenever you cast your first / second / third spell each turn, ... (and an opponent's "their second spell") | Monologue Tax |
  | At the beginning of your first / second main phase, ... | Scathing Shadelock |
  | Whenever you cast a (creature / noncreature / instant or sorcery) spell, ... | |
  | Whenever you cast a red (or other color) / Aura / "Aura, Equipment, or Vehicle" / historic spell, ... | Sram, Senior Edificer |
  | Whenever a player / an opponent casts a spell, ... | |
  | Whenever you cast your first spell with {X} in its mana cost each turn, ... (X is that spell's X) | Zimone, Infinite Analyst |
  | Whenever a creature (token) you control deals combat damage to a player, ... (once per creature) | Ohran Frostfang |
  | Whenever equipped / enchanted creature attacks, ... | |
  | Whenever you attack with two or more creatures, ... | Firemane Commando |
  | Whenever a creature attacks you (or a planeswalker you control), ... (once per attacker) | |

  - Triggers go on the stack the next time a player would get priority. The active player's go
    first, so they resolve last, and players can respond to them.
  - Targets are chosen when a trigger goes on the stack. A trigger with no legal target is removed.
  - "You may" abilities ask their controller when they resolve.
  - A card can call itself by its full name, its short legendary name ("Omnath"),
    "this creature" (or "this Aura", "this Equipment", "this Class", ...), or "it".
  - "This ability triggers only once each turn." is respected.
  - Intervening "if" clauses are checked when the ability triggers and again when it resolves (CR 603.4).
    Supported: "if a card left your graveyard this turn", "if you gained life this turn", "if an opponent
    controls more lands than you", "if you've cast an instant or sorcery spell this turn", "if you control
    seven or more Plains", "if you control no Snakes", "if you control an artifact", "if it's your turn", "if you're
    the monarch", "if you have no cards in hand", "if you gained 2 or more life this turn", "if two or more creatures
    died this turn" (any player's), "if there are three or more creature cards in your graveyard", "if a player has one
    or fewer cards in hand", "if an opponent has more cards in hand than you", "if this creature isn't prepared", "if
    this land is tapped", "if you control no other creatures" (the source doesn't count itself), "if a modified
    creature died under your control this turn" (a creature with counters, or with Equipment or an Aura of yours on it),
    and "if two or more of those creatures are attacking you and/or planeswalkers you control". A trigger with any
    other "if" clause is ignored. Not built: "a spell with the same name as ..." and the wording of Tomik's trigger.
  - Paying life counts as losing it. A creature that's sacrificed sees itself go
    ("Whenever you sacrifice a creature" on the creature itself triggers).
  - A trigger whose effect isn't understood is ignored.
  - In triggers about another creature (enters, dies, attacks, attacks you, deals combat damage), "it" and
    "that creature" mean that creature ("put a +1/+1 counter on it"), but only when every effect is about "it".
  - In triggers about another player (an opponent draws, gains or loses life, discards, searches their library, or casts a spell), "that player"
    and "they" mean that player ("they lose 2 life", "deals 2 damage to that player"), but only for effects that
    target a player. Anywhere else a line that says "it", "they" or "that player" is ignored.
  - Ability words like "Landfall —" are ignored when reading the trigger. A creature that dies still sees
    its own death ("Whenever this creature or another creature dies").
- **Activated abilities on permanents:** these also use the same effect list.

  | Cost | Example |
  |---|---|
  | Mana, {T}, sacrifice this, pay N life | Mind Stone: "{1}, {T}, Sacrifice this artifact: Draw a card." |
  | Planeswalker loyalty (+1, −3, 0) | "−3: Destroy target creature." |
  | Sacrifice a creature / another creature / an artifact (land, enchantment, permanent) | "Sacrifice a creature: Draw a card." |
  | Discard a card | "{1}, Discard a card: Draw a card." |
  | Exile a card from your graveyard | "{1}, Exile a card from your graveyard: You gain 1 life." |
  | Remove a counter, or two to five, from this (+1/+1 or a named one) | "{2}{G}, Remove a +1/+1 counter from this creature: Destroy target artifact or enchantment." / "Remove three spore counters from this creature: Create a 1/1 green Saproling creature token." (the Thallids) |
  | Sacrifice a Food / Treasure / Clue | "{1}, Sacrifice a Food: Target creature gains indestructible until end of turn. Tap it." |
  | Sacrifice X creatures (of a type) | Chatterfang: "{B}, Sacrifice X Squirrels: Target creature gets +X/-X until end of turn." (X is asked, then that many are sacrificed; plurals like "two Squirrels" read too) |

  - They can be activated whenever you have priority, unless they say "Activate only as a sorcery".
    "Activate only once each turn" is respected.
    "Activate only if <condition>" (and "... as a sorcery and only if ...") uses the same conditions as triggers,
    plus "you control two or more white permanents". "Target creature can't be blocked this turn" is understood.
  - Loyalty abilities: one per planeswalker per turn, at sorcery speed, and loyalty can't go below 0.
  - Creatures can't use {T} abilities the turn they arrive (unless they have haste).
  - A permanent can't tap itself for mana to pay for its own {T} or sacrifice ability.
  - Abilities go on the stack, so players can respond, and counterspells can't target them.
  - Card costs ("Sacrifice a creature", "Discard a card", "Exile a card from your graveyard") are paid when you
    activate, and the ability isn't offered unless you can pay. You can sacrifice only your own permanents; the
    source itself counts unless it says "another". Bots don't use abilities that cost their own cards. Costs
    can name two to four cards ("Sacrifice two creatures", "Discard two cards", "Exile three cards from your
    graveyard"); ward costs still pay one card.
  - "Scry N, then reveal the top card of your library. If it's a land card, put it onto the battlefield
    (tapped). Otherwise, draw a card." (Thrasios, Triton Hero) is understood as a whole or not at all.
  - **Ability words that are a condition (#427):** Raid reads "if you attacked this turn" (the condition `attacked_this_turn`: you declared an attack
    with at least one creature this turn, CR 508.1) in a trigger's "if" clause (Storm Fleet Spy, Mardu Skullhunter) and in "This creature enters with a
    +1/+1 counter on it if you attacked this turn" (War-Name Aspirant, applied as it enters). Lieutenant reads "if you control your commander"
    (`control_commander`: a commander of yours is on the battlefield, not in the command zone; Loyal Subordinate, Loyal Apprentice). Enrage is a trigger
    on the new event `damaged`, "Whenever this creature is dealt damage" (Imperial Ceratops): it fires for any damage above 0, even a lethal blow.

- **Hidden cards:** a drawn card's name goes only to the player who drew it.
- **Replays:** the same `seed` gives the same shuffles.
- **Landfall wordings (#427):** "you may have <it> deal / lose / become / gain / get ..." in a trigger is read as the optional effect itself ("you may have
  this creature deal 1 damage to target player or planeswalker", Cosi's Ravager; "you may have target land you control become a 3/3 Elemental creature with
  haste until end of turn. It's still a land.", Embodiment of Fury). "This creature can attack this turn as though it didn't have defender" (Skyclave Squid,
  Krotiq Nestguard, any trigger or activated ability) sets `Permanent.defender_ok_turn`, which `Combat._can_attack` checks; the "it" in that sentence and in
  "It's still a land." is the creature itself, not the permanent that set the trigger off.

## What the engine can't play yet

```
python -m infernal_machine.report deck.txt
```

The report looks the deck up in Scryfall's bulk data (downloaded to `.cache/oracle_bulk.json` on first use) and prints:
- how many cards are fully playable,
- the missing pieces grouped by kind, such as activated abilities, tokens or exile, with the most-affected kind first,
- every rules-text line the engine doesn't understand yet.

Use it to decide which effects to add next. In code: `deck_report(deck)` and `unsupported_lines(card)` in `report.py`.

**Checked against real cards (#25).** The five Secrets of Strixhaven precon decks in `examples/precons` were loaded from Scryfall and run through the report, and bot games were played with them. Of their 391 distinct cards, 326 are fully playable; the 65 that are not need triggers (42 cards), other rules text (15), activated abilities (8) or tokens (1), one card needing two kinds. Wording gaps found that way were fixed (Land Tax, Assassin's Trophy, Pawn of Ulamog, Ribtruss Roaster, Pest Rescuer, Springbloom Druid, Witch of the Moors, Drumbellower, Quandrix Apprentice). Playing bots against each other also found a crash: a spell that targets "a creature with mana value X" (Entrancing Melody) let the player pick an X that no creature had; it is now only offered for X values that have a target. To repeat it, load the decks with `CachedSource(ScryfallSource(), path)` (or `BulkSource`) and give each seat a `BotPlayer`.
