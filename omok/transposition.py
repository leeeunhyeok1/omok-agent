# AI-written by OpenAI Codex, for issue #13.
"""Bounded completed-search values; full keys verify Python hash collisions."""
from collections import OrderedDict
from dataclasses import dataclass
from typing import Hashable, Literal

from omok.simulator import Coordinate, Position

Bound = Literal['exact', 'lower', 'upper']


@dataclass(frozen=True, slots=True)
class TableEntry:
    depth: int
    score: int
    bound: Bound
    best_move: Coordinate | None = None
    principal_variation: tuple[Coordinate, ...] = ()


class TranspositionTable:
    """FIFO replacement, exact-depth values and newest compatible move hints.

    Lines are limited to 64 plies so entry payloads, as well as entry count,
    remain bounded. Longer completed nodes simply aren't retained.
    """

    def __init__(self, capacity: int = 4096) -> None:
        if type(capacity) is not int or capacity < 0:
            raise ValueError('Table capacity must be a nonnegative integer.')
        self._capacity = capacity
        self._entries: OrderedDict[tuple[Position, Hashable, int], TableEntry] = OrderedDict()
        self._hints: dict[tuple[Position, Hashable], TableEntry] = {}
        self.hits = 0
        self.evictions = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        """Explicit new-game/configuration reset, including counters."""
        self._entries.clear()
        self._hints.clear()
        self.hits = self.evictions = 0

    def probe(self, position: Position, compatibility: Hashable, depth: int) -> TableEntry | None:
        entry = self._entries.get((position, compatibility, depth))
        if entry is not None:
            self.hits += 1
        return entry

    def store(self, position: Position, compatibility: Hashable, entry: TableEntry) -> None:
        if self.capacity == 0 or len(entry.principal_variation) > 64:
            return
        key = (position, compatibility, entry.depth)
        prior = self._entries.get(key)
        if prior is not None and prior.bound == 'exact' and entry.bound != 'exact':
            return
        hint_key = (position, compatibility)
        if prior is not None and self._hints.get(hint_key) is prior:
            del self._hints[hint_key]
        self._entries[key] = entry
        self._entries.move_to_end(key)
        if entry.best_move is not None:
            self._hints[hint_key] = entry
        if len(self._entries) > self.capacity:
            evicted_key, evicted = self._entries.popitem(last=False)
            hint_key = evicted_key[:2]
            if self._hints.get(hint_key) is evicted:
                del self._hints[hint_key]
            self.evictions += 1

    def hint(self, position: Position, compatibility: Hashable) -> Coordinate | None:
        entry = self._hints.get((position, compatibility))
        return None if entry is None else entry.best_move
