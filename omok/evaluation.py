# AI-written by OpenAI Codex, for issues #16 and #17.
"""Immutable material/line semantics and independently persisted coefficients."""
from collections.abc import Callable
from dataclasses import dataclass, fields
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from omok.search import EVALUATION_LIMIT, SearchCancelled, material_evaluation
from omok.simulator import Position
from omok.lines import LINE_FEATURES, line_features

FEATURE_VERSION = 'material-v1'
LINE_VERSION = 'lines-v1'


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    material: int = 1
    material_enabled: bool = True
    feature_version: str = FEATURE_VERSION

    lines_enabled: bool = True
    open_four: int = 300
    closed_four: int = 100
    broken_four: int = 150
    geometric_completion: int = 0
    verified_win: int = 300
    overline_trap: int = -20

    def __post_init__(self) -> None:
        if type(self.feature_version) is not str or self.feature_version not in (FEATURE_VERSION, LINE_VERSION):
            raise ValueError('Unsupported feature version.')
        if type(self.material) is not int or not -4000 <= self.material <= 4000:
            raise ValueError('Material coefficient must be an integer in [-4000, 4000].')
        for field in fields(self):
            if field.name not in LINE_FEATURES:
                continue
            value = getattr(self, field.name)
            if type(value) is not int or not -4000 <= value <= 4000:
                raise ValueError('Line coefficient must be an integer in [-4000, 4000].')
            if self.feature_version == FEATURE_VERSION and value != field.default:
                raise ValueError('Line coefficients require lines-v1.')
        if self.feature_version == FEATURE_VERSION and self.lines_enabled is not True:
            raise ValueError('Line enablement requires lines-v1.')
        if type(self.lines_enabled) is not bool or type(self.material_enabled) is not bool:
            raise ValueError('Family enablement must be boolean.')

    def coefficients(self) -> dict[str, int]:
        names = ('material', *LINE_FEATURES) if self.feature_version == LINE_VERSION else ('material',)
        return {name: getattr(self, name) for name in names}

    def enabled_families(self) -> list[str]:
        families = ['material'] if self.material_enabled else []
        if self.feature_version == LINE_VERSION and self.lines_enabled:
            families.append('lines')
        return families

    def canonical_json(self) -> str:
        return json.dumps({
            'feature_version': self.feature_version,
            'coefficients': self.coefficients(),
            'enabled_families': self.enabled_families(),
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
        version = data['feature_version']
        if type(version) is not str or version not in (FEATURE_VERSION, LINE_VERSION):
            raise ValueError('Unsupported feature version.')
        names = {'material', *LINE_FEATURES} if version == LINE_VERSION else {'material'}
        allowed = ['material', 'lines'] if version == LINE_VERSION else ['material']
        if type(coefficients) is not dict or set(coefficients) != names:
            raise ValueError('Unknown or missing coefficient.')
        if (type(families) is not list or any(type(f) is not str or f not in allowed for f in families)
                or len(set(families)) != len(families)):
            raise ValueError('Unsupported or duplicate enabled family.')
        return cls(**coefficients, material_enabled='material' in families,
                   lines_enabled='lines' in families if version == LINE_VERSION else True,
                   feature_version=version)

    @classmethod
    def load(cls, path: str | Path) -> 'EvaluationConfig':
        return cls.from_json(Path(path).read_text(encoding='utf-8'))


@dataclass(frozen=True, slots=True)
class ConfiguredEvaluator:
    config: EvaluationConfig

    def __post_init__(self) -> None:
        if type(self.config) is not EvaluationConfig:
            raise ValueError('Expected validated EvaluationConfig.')

    def _features(self, position: Position, check: Callable[[], None], *,
                  inspection: bool = False) -> tuple[dict[str, int], dict[str, Any] | None]:
        check()
        features = {'material': material_evaluation(position, check=check)
                    if inspection or self.config.material_enabled else 0}
        lines = None
        if self.config.feature_version == LINE_VERSION:
            if inspection or self.config.lines_enabled:
                lines = line_features(position, check)
            features.update({name: lines['black'][name] - lines['white'][name] if lines else 0
                             for name in LINE_FEATURES})
        check()
        return features, lines

    def _contributions(self, features: dict[str, int]) -> dict[str, int]:
        return {name: features[name] * weight
                if (self.config.material_enabled if name == 'material' else self.config.lines_enabled)
                else 0 for name, weight in self.config.coefficients().items()}

    def __call__(self, position: Position,
                 check: Callable[[], None] = lambda: None) -> int:
        features, _ = self._features(position, check)
        raw = sum(self._contributions(features).values())
        check()
        return max(-EVALUATION_LIMIT, min(EVALUATION_LIMIT, raw))

    def inspect(self, position: Position, *,
                check: Callable[[], None] = lambda: None) -> dict[str, Any]:
        report: dict[str, Any] = {
            'feature_version': self.config.feature_version,
            'configuration_id': self.config.identity,
            'context': {'side_to_move': position.side_to_move, 'outcome': position.outcome,
                        'perspective': 'black', 'kind': 'static_heuristic'},
            'coefficients': self.config.coefficients(),
            'enabled_families': self.config.enabled_families(),
            'features': None, 'contributions': None, 'raw_total': None,
            'total': None, 'saturated': None, 'incomplete': True, 'cancellation': None,
        }
        if self.config.feature_version == LINE_VERSION:
            report['lines'] = None
        try:
            features, lines = self._features(position, check, inspection=True)
            contributions = self._contributions(features)
            raw = sum(contributions.values())
            check()
        except SearchCancelled as error:
            report['cancellation'] = str(error)
            return report
        report.update(features=features, contributions=contributions,
                      raw_total=raw, total=max(-EVALUATION_LIMIT, min(EVALUATION_LIMIT, raw)),
                      saturated=abs(raw) > EVALUATION_LIMIT, incomplete=False)
        if lines is not None:
            report['lines'] = lines
        return report
