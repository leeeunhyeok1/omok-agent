# AI-written by OpenAI Codex, for issue #7.
"""Thin, offline-only loading of unchanged supplied sources."""
from dataclasses import dataclass
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from threading import RLock
from types import ModuleType
from typing import Any

from omok.player import DevelopmentPlayer, LegalBaseline

SOURCES = Path(__file__).resolve().parents[1] / 'players'
_LOAD_LOCK = RLock()


def _load(name: str, path: Path) -> ModuleType:
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load supplied source: {path}')
    module = module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


@dataclass(frozen=True)
class ProvidedPlayers:
    base: Any
    classes: dict[str, Any]

    def create(self, name: str, color: int) -> DevelopmentPlayer:
        if type(color) is not int or color not in (0, 1):
            raise ValueError('Color must be 0 or 1.')
        return self.classes[name](color)


@lru_cache(maxsize=1)
def load_players() -> ProvidedPlayers:
    # The original bots import "player". Restore any existing module afterwards;
    # retain uniquely named source modules for inspection and trace provenance.
    with _LOAD_LOCK:
        base = _load('offline._provided_player', SOURCES / 'player.py').Player
        previous = sys.modules.get('player')
        sys.modules['player'] = sys.modules['offline._provided_player']
        try:
            random = _load('offline._provided_random', SOURCES / 'randomplayer.py').RandomPlayer
            simple = _load('offline._provided_simple', SOURCES / 'simpleplayer.py').SimplePlayer
        finally:
            if previous is None:
                sys.modules.pop('player', None)
            else:
                sys.modules['player'] = previous

        def initialize(self: Any, color: int) -> None:
            base.__init__(self, color)
            LegalBaseline.__init__(self, color)

        baseline = type('ProvidedBaseline', (LegalBaseline, base),
                        {'__init__': initialize, '__module__': __name__})
        return ProvidedPlayers(base, {'random': random, 'simple': simple, 'baseline': baseline})
