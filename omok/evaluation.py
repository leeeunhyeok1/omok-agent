# AI-written by OpenAI Codex, for issue #16.
"""Immutable material semantics and independently persisted agent coefficients."""
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from omok.search import EVALUATION_LIMIT, SearchCancelled, material_evaluation
from omok.simulator import Position

FEATURE_VERSION = 'material-v1'


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    material: int = 1
    material_enabled: bool = True
    feature_version: str = FEATURE_VERSION

    def __post_init__(self) -> None:
        if type(self.feature_version) is not str or self.feature_version != FEATURE_VERSION:
            raise ValueError('Unsupported feature version.')
        if type(self.material) is not int or not -4000 <= self.material <= 4000:
            raise ValueError('Material coefficient must be an integer in [-4000, 4000].')
        if type(self.material_enabled) is not bool:
            raise ValueError('Family enablement must be boolean.')

    def canonical_json(self) -> str:
        return json.dumps({
            'feature_version': self.feature_version,
            'coefficients': {'material': self.material},
            'enabled_families': ['material'] if self.material_enabled else [],
        }, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)

    @property
    def identity(self) -> str:
        return sha256(self.canonical_json().encode('ascii')).hexdigest()

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.canonical_json() + '\n', encoding='utf-8')

    @classmethod
    def from_json(cls, source: str) -> 'EvaluationConfig':
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for name, value in pairs:
                if name in result:
                    raise ValueError('Duplicate configuration name: ' + name)
                result[name] = value
            return result
        data = json.loads(source, object_pairs_hook=unique_object)
        if type(data) is not dict or set(data) != {
                'feature_version', 'coefficients', 'enabled_families'}:
            raise ValueError('Configuration requires exactly version, coefficients and families.')
        coefficients = data['coefficients']
        families = data['enabled_families']
        if type(coefficients) is not dict or set(coefficients) != {'material'}:
            raise ValueError('Unknown or missing coefficient.')
        if type(families) is not list or families not in ([], ['material']):
            raise ValueError('Unsupported or duplicate enabled family.')
        return cls(coefficients['material'], families == ['material'], data['feature_version'])

    @classmethod
    def load(cls, path: str | Path) -> 'EvaluationConfig':
        return cls.from_json(Path(path).read_text(encoding='utf-8'))


@dataclass(frozen=True, slots=True)
class ConfiguredEvaluator:
    config: EvaluationConfig

    def __post_init__(self) -> None:
        if type(self.config) is not EvaluationConfig:
            raise ValueError('Expected validated EvaluationConfig.')

    def __call__(self, position: Position,
                 check: Callable[[], None] = lambda: None) -> int:
        check()
        raw = (material_evaluation(position, check=check) * self.config.material
               if self.config.material_enabled else 0)
        check()
        return max(-EVALUATION_LIMIT, min(EVALUATION_LIMIT, raw))

    def inspect(self, position: Position, *,
                check: Callable[[], None] = lambda: None) -> dict[str, Any]:
        report: dict[str, Any] = {
            'feature_version': self.config.feature_version,
            'configuration_id': self.config.identity,
            'context': {'side_to_move': position.side_to_move, 'outcome': position.outcome,
                        'perspective': 'black', 'kind': 'static_heuristic'},
            'coefficients': {'material': self.config.material},
            'enabled_families': ['material'] if self.config.material_enabled else [],
            'features': None, 'contributions': None, 'raw_total': None,
            'total': None, 'saturated': None, 'incomplete': True, 'cancellation': None,
        }
        try:
            check()
            feature = material_evaluation(position, check=check)
            raw = feature * self.config.material if self.config.material_enabled else 0
            check()
        except SearchCancelled as error:
            report['cancellation'] = str(error)
            return report
        report.update(features={'material': feature}, contributions={'material': raw},
                      raw_total=raw, total=max(-EVALUATION_LIMIT, min(EVALUATION_LIMIT, raw)),
                      saturated=abs(raw) > EVALUATION_LIMIT, incomplete=False)
        return report
