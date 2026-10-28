"""Playing lands and casting spells from a zone other than the hand (issue #435).

Each zone is one `ZonePlay`: the action prefixes it uses, what it offers a player now (`offers`), and what choosing one of its actions
does (`perform`). `Game.legal_actions` and `Game._perform` walk `ZONE_PLAYS`; the bot and the goldfish read the prefixes from here, so a
new zone is one new class and one entry in the list, not edits in four files. `Game` keeps the helpers they call (`_can_cast`, `_cast`,
`_enter`, `_paragon_options` ...) and reaches nothing else of them. Names defined in `game.py` are reached as `g.NAME`.
"""

from __future__ import annotations

from .analysis import is_land
from .effects import graveyard_casts, graveyard_permits, is_aftermath, plot_of
from .filters import parse_filter

# The action prefixes (re-exported by game.py, which the bot, the goldfish and the tests import them from).
CAST_GRAVEYARD = "Cast from graveyard: "  # flashback and escape
PLAY_GRAVEYARD = "Play land from the graveyard: "  # Crucible of Worlds: any number of lands, within the land drops
CAST_PARAGON = "Cast from graveyard (once a turn): "  # Serra Paragon
PLAY_PARAGON = "Play land from graveyard: "
CAST_EXILE = "Cast from exile: "  # a card exiled "you may play it this turn"
PLAY_EXILE = "Play land from exile: "
CAST_PERMIT = "Cast from graveyard (permission): "  # Gisa and Geralf, Lurrus: once each turn, a kind of spell, for its mana cost
PLAY_TOP = "Play land from the top of your library: "  # Courser of Kruphix, Future Sight
CAST_TOP = "Cast from the top of your library: "  # Future Sight, Mystic Forge, Realmwalker
PLOT = "Plot: "  # followed by the card's name: pay its plot cost and exile it from the hand, at sorcery speed
CAST_PLOTTED = "Cast plotted: "  # followed by the card's name: cast from exile as a sorcery on a later turn, without paying its mana cost


def _timely(game: g.Game, seat: g.Seat, card, sorcery_timing: bool) -> bool:
    """Whether `seat` may cast `card` at this moment as far as timing goes: a sorcery-speed moment, or the card (or a flash
    permission) allows an instant-speed cast."""
    return sorcery_timing or seat.flash_turn == game.turn or game._instant_speed(seat, card)


class ZonePlay:
    """One zone a player may play lands or cast spells from."""
    land_prefix: str
    cast_prefix: str
    extra_prefixes: tuple[str, ...] = ()  # other prefixes `perform` answers to

    def land_offers(self, game: g.Game, seat: g.Seat) -> list[str]:
        """Lands to offer with the lands in the hand (called only at a sorcery-speed moment with a land drop left)."""
        return []

    def offers(self, game: g.Game, seat: g.Seat, sorcery_timing: bool) -> list[str]:
        """The actions this zone gives `seat` now."""
        return []

    def perform(self, game: g.Game, seat: g.Seat, action: str) -> bool:
        """Carry out `action` if it is one of this zone's; whether it was."""
        return False


class Graveyard(ZonePlay):
    """Flashback and escape (and an Aftermath half) from the graveyard; Crucible of Worlds' lands."""
    land_prefix, cast_prefix = PLAY_GRAVEYARD, CAST_GRAVEYARD

    def land_offers(self, game, seat):
        return [PLAY_GRAVEYARD + c.name for c in g._unique(seat.graveyard) if is_land(c)] if game._graveyard_lands(seat) else []

    def offers(self, game, seat, sorcery_timing):
        actions = []
        for card in g._unique(seat.graveyard):
            for cast in graveyard_casts(card)[:1]:
                if not is_land(card) and _timely(game, seat, card, sorcery_timing) and game._can_cast(seat, card, graveyard=cast):
                    actions.append(CAST_GRAVEYARD + card.name)
            if (other := card.alternate) and is_aftermath(other) and _timely(game, seat, other, sorcery_timing) \
                    and game._can_cast(seat, other, graveyard=graveyard_casts(other)[0]):
                actions.append(CAST_GRAVEYARD + other.name)  # the Aftermath half
        return actions

    def perform(self, game, seat, action):
        if action.startswith(PLAY_GRAVEYARD):
            card = g._take(seat.graveyard, action.removeprefix(PLAY_GRAVEYARD))
            game._left_graveyard(seat, [card])
            game._enter(seat, g.Permanent(card, sick=True))
            seat.lands_played += 1
            game.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "graveyard"})
        elif action.startswith(CAST_GRAVEYARD):
            name = action.removeprefix(CAST_GRAVEYARD)
            card = next((c for c in seat.graveyard if c.name == name), None)
            if card is not None:
                game._cast(seat, card, seat.graveyard, graveyard=graveyard_casts(card)[0])
            else:  # the Aftermath half of a card in the graveyard
                whole = next(c for c in seat.graveyard if c.alternate and c.alternate.name == name)
                half = g._checked(whole.alternate)
                game._cast(seat, half, seat.graveyard, graveyard=graveyard_casts(half)[0], whole=whole)
        else:
            return False
        return True


class Paragon(ZonePlay):
    """Serra Paragon: once a turn, a land or a permanent spell of low mana value from the graveyard."""
    land_prefix, cast_prefix = PLAY_PARAGON, CAST_PARAGON

    def offers(self, game, seat, sorcery_timing):
        actions = []
        for card in game._paragon_options(seat):
            if is_land(card):
                if sorcery_timing and seat.lands_played < game._land_drops(seat):
                    actions.append(PLAY_PARAGON + card.name)
            elif _timely(game, seat, card, sorcery_timing) and game._can_cast(seat, card):
                actions.append(CAST_PARAGON + card.name)
        return actions

    def perform(self, game, seat, action):
        if action.startswith(PLAY_PARAGON):
            card = g._take(seat.graveyard, action.removeprefix(PLAY_PARAGON))
            game._used_paragon(seat, card)
            game._left_graveyard(seat, [card])
            game._enter(seat, g.Permanent(card, sick=True))
            seat.lands_played += 1
            game.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "graveyard"})
        elif action.startswith(CAST_PARAGON):
            card = next(c for c in seat.graveyard if c.name == action.removeprefix(CAST_PARAGON))
            game._used_paragon(seat, card)
            game._cast(seat, card, seat.graveyard)
        else:
            return False
        return True


class Permits(ZonePlay):
    """"Once during each of your turns, you may cast a Zombie creature spell from your graveyard." from a permanent you control."""
    land_prefix, cast_prefix = "", CAST_PERMIT  # (no lands: only spells)

    @staticmethod
    def _grants(game: g.Game, seat: g.Seat, card) -> list:
        """The unused (permanent, permit) pairs that let `seat` cast `card` from their graveyard now."""
        found = []
        for permanent in seat.battlefield:
            if game.loses_abilities(permanent):
                continue
            for permit in graveyard_permits(permanent.card):
                if permanent.activated_turn.get(permit.text) == game.turn:
                    continue
                if parse_filter(permit.kind).matches(card) and (permit.max_mv is None or card.cmc <= permit.max_mv):
                    found.append((permanent, permit))
        return found

    def offers(self, game, seat, sorcery_timing):
        return [CAST_PERMIT + card.name for card in g._unique(seat.graveyard)
                if self._grants(game, seat, card) and _timely(game, seat, card, sorcery_timing) and game._can_cast(seat, card, from_hand=False)]

    def perform(self, game, seat, action):
        if not action.startswith(CAST_PERMIT):
            return False
        card = next(c for c in seat.graveyard if c.name == action.removeprefix(CAST_PERMIT))
        permanent, permit = self._grants(game, seat, card)[0]
        permanent.activated_turn[permit.text] = game.turn  # (once each turn, however it ends up)
        game._cast(seat, card, seat.graveyard)
        return True


class Exile(ZonePlay):
    """A card exiled with "you may play it this turn" (or until the end of the next turn)."""
    land_prefix, cast_prefix = PLAY_EXILE, CAST_EXILE

    def offers(self, game, seat, sorcery_timing):
        actions = []
        for card in g._unique([c for c, until in seat.exile_play if game.turn <= until and c in seat.exile]):
            if is_land(card):
                if sorcery_timing and seat.lands_played < game._land_drops(seat):
                    actions.append(PLAY_EXILE + card.name)
            elif _timely(game, seat, card, sorcery_timing) and game._can_cast(seat, card, from_hand=False):
                actions.append(CAST_EXILE + card.name)
        return actions

    def perform(self, game, seat, action):
        if action.startswith(PLAY_EXILE):
            card = g._take(seat.exile, action.removeprefix(PLAY_EXILE))
            game._used_exile_permission(seat, card)
            game._enter(seat, g.Permanent(card, sick=True))
            seat.lands_played += 1
            game.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "exile"})
        elif action.startswith(CAST_EXILE):
            card = next(c for c in seat.exile if c.name == action.removeprefix(CAST_EXILE))
            game._used_exile_permission(seat, card)
            game._cast(seat, card, seat.exile)
        else:
            return False
        return True


class Library(ZonePlay):
    """The top card of the library: Courser of Kruphix, Future Sight, Mystic Forge, Realmwalker ..."""
    land_prefix, cast_prefix = PLAY_TOP, CAST_TOP

    def offers(self, game, seat, sorcery_timing):
        if not (seat.library and (top := seat.library[0]) and game._plays_from_top(seat, top)):
            return []
        if is_land(top):
            return [PLAY_TOP + top.name] if sorcery_timing and seat.lands_played < game._land_drops(seat) else []
        if _timely(game, seat, top, sorcery_timing) and game._can_cast(seat, top, from_hand=False):
            return [CAST_TOP + top.name]
        return []

    def perform(self, game, seat, action):
        if action.startswith(PLAY_TOP):
            card = seat.library.pop(0)
            game._enter(seat, g.Permanent(card, sick=True))
            seat.lands_played += 1
            game.broadcast({"event": "play_land", "seat": seat.index, "card": card.name, "from": "library"})
        elif action.startswith(CAST_TOP):
            game._cast(seat, seat.library[0], seat.library)
        else:
            return False
        return True


class Plotted(ZonePlay):
    """Plot (CR 702.170): from the hand, a special action at sorcery speed puts the card into exile for its plot cost; on a later turn it is
    cast from exile as a sorcery without paying its mana cost, whatever its type."""
    land_prefix, cast_prefix = "", CAST_PLOTTED
    extra_prefixes = (PLOT,)

    def offers(self, game, seat, sorcery_timing):
        if not sorcery_timing:
            return []
        actions = [PLOT + c.name for c in g._unique(seat.hand)
                   if (cost := plot_of(c)) and game._payment(seat, g.dataclasses.replace(c, mana_cost=cost)) is not None]
        for turn, card in seat.plotted:
            if turn < game.turn and card in seat.exile and CAST_PLOTTED + card.name not in actions \
                    and game._can_cast(seat, card, graveyard=g.GraveyardCast("Plot", "{0}")):
                actions.append(CAST_PLOTTED + card.name)
        return actions

    def perform(self, game, seat, action):
        if action.startswith(PLOT):
            game._plot(seat, action.removeprefix(PLOT))
        elif action.startswith(CAST_PLOTTED):
            game._cast_plotted(seat, action.removeprefix(CAST_PLOTTED))
        else:
            return False
        return True


GRAVEYARD, PARAGON, PERMITS, EXILE, LIBRARY, PLOTTED = Graveyard(), Paragon(), Permits(), Exile(), Library(), Plotted()
ZONE_PLAYS: tuple[ZonePlay, ...] = (GRAVEYARD, PARAGON, PERMITS, EXILE, LIBRARY, PLOTTED)
LAND_PREFIXES = tuple(z.land_prefix for z in ZONE_PLAYS if z.land_prefix)
CAST_PREFIXES = tuple(z.cast_prefix for z in ZONE_PLAYS)


from . import game as g  # noqa: E402  (last: game.py imports the names above from this module while it is itself being imported)
