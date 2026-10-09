# AI-written by OpenAI Codex, for issue #25.
"""JSON-configured factory for existing local and supplied player implementations."""
from typing import Any

from offline.measurement import configured_search
from offline.opponents import SeededSmokePlayer
from omok.evaluation import EvaluationConfig
from omok.player import IterativePlayer, LegalBaseline, TimePolicy


def create(color: int, *, name: str, seed: int = 0, supplied: bool = False,
           settings: dict[str, Any] | None = None, evaluation: str | None = None,
           profile_every: int = 0) -> Any:
    options: dict[str, Any] = {}
    if name == 'search':
        if settings is None:
            raise ValueError('Search requires resolved settings.')
        options = {'max_depth': settings['max_depth'], 'max_nodes': settings['max_nodes'],
            'policy': TimePolicy(**settings['time_policy']),
            'search': configured_search(EvaluationConfig.from_json(evaluation) if evaluation else None,
                                       settings, profile_every=profile_every)}
    if supplied:
        from offline.provided import load_players
        return load_players().create(name, color, **options)
    if name == 'smoke':
        return SeededSmokePlayer(color, seed)
    if name == 'baseline':
        return LegalBaseline(color)
    if name == 'search':
        return IterativePlayer(color, **options)
    raise ValueError('Unknown local player: ' + name)
