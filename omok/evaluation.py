# AI-written by OpenAI Codex, for issues #16–#20; issue #21 measurement additions.
"""Immutable material/line semantics and independently persisted coefficients."""
from collections.abc import Callable
from dataclasses import dataclass, fields
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, TypeVar

from omok.measurement import EvaluationProfile

T = TypeVar('T')

from omok.search import EVALUATION_LIMIT, SearchCancelled, material_evaluation
from omok.simulator import Coordinate, Position
from omok.captures import CAPTURE_FEATURES, capture_features
from omok.lines import LINE_FEATURES, POTENTIAL_FEATURES, line_features
from omok.threat_effects import EFFECT_FEATURES, MULTIPLICITY_FEATURES, capture_effects, multiplicity_features

FEATURE_VERSION = 'material-v1'
LINE_VERSION = 'lines-v1'
POTENTIAL_VERSION = 'potential-v1'
CAPTURE_VERSION = 'capture-v1'
EFFECT_VERSION = 'effects-v1'
VERSION_FAMILIES = {
    FEATURE_VERSION: ('material',),
    LINE_VERSION: ('material', 'lines'),
    POTENTIAL_VERSION: ('material', 'lines', 'potential'),
    CAPTURE_VERSION: ('material', 'lines', 'potential', 'captures'),
    EFFECT_VERSION: ('material', 'lines', 'potential', 'captures', 'effects', 'multiplicity'),
}
FAMILY_FEATURES = {'material': ('material',), 'lines': LINE_FEATURES,
                   'potential': POTENTIAL_FEATURES, 'captures': CAPTURE_FEATURES,
                   'effects': EFFECT_FEATURES, 'multiplicity': MULTIPLICITY_FEATURES}


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

    potential_enabled: bool = True
    open_three: int = 40
    broken_three: int = 25
    two_stone: int = 5

    captures_enabled: bool = True
    capture_move: int = 30
    capture_pair: int = 10
    multi_pair_move: int = 20
    vulnerable_pair: int = -40

    effects_enabled: bool = True
    capture_break_four: int = 120
    capture_break_potential: int = 20
    capture_create_four: int = 80
    capture_create_potential: int = 15
    capture_remove_blocker: int = 25
    capture_expose_five: int = -300

    multiplicity_enabled: bool = True
    geometric_multiple: int = 0
    verified_multiple: int = 50
    offensive_opportunity: int = 60
    defensive_urgency: int = 100

    def __post_init__(self) -> None:
        if type(self.feature_version) is not str or self.feature_version not in VERSION_FAMILIES:
            raise ValueError('Unsupported feature version.')
        supported = VERSION_FAMILIES[self.feature_version]
        defaults = {field.name: field.default for field in fields(self)}
        for family, names in FAMILY_FEATURES.items():
            enabled = getattr(self, family + '_enabled')
            if type(enabled) is not bool:
                raise ValueError('Family enablement must be boolean.')
            if family not in supported and not enabled:
                raise ValueError('Family enablement requires its feature version.')
            for name in names:
                value = getattr(self, name)
                if type(value) is not int or not -4000 <= value <= 4000:
                    raise ValueError('Coefficient must be an integer in [-4000, 4000].')
                if family not in supported and value != defaults[name]:
                    raise ValueError('Coefficient requires its feature version.')

    def coefficients(self) -> dict[str, int]:
        return {name: getattr(self, name)
                for family in VERSION_FAMILIES[self.feature_version]
                for name in FAMILY_FEATURES[family]}

    def enabled_families(self) -> list[str]:
        return [family for family in VERSION_FAMILIES[self.feature_version]
                if getattr(self, family + '_enabled')]

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
        if type(version) is not str or version not in VERSION_FAMILIES:
            raise ValueError('Unsupported feature version.')
        schema = cls(feature_version=version)
        names = set(schema.coefficients())
        allowed = schema.enabled_families()
        if type(coefficients) is not dict or set(coefficients) != names:
            raise ValueError('Unknown or missing coefficient.')
        if (type(families) is not list or any(type(f) is not str or f not in allowed for f in families)
                or len(set(families)) != len(families)):
            raise ValueError('Unsupported or duplicate enabled family.')
        return cls(**coefficients, feature_version=version,
                   **{family + '_enabled': family in families
                      for family in VERSION_FAMILIES[version]})

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
                  inspection: bool = False, profile: EvaluationProfile | None = None) -> tuple[dict[str, int], dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
        def scan(name: str, operation: Callable[[], T]) -> T:
            return operation() if profile is None else profile.measure(name, operation)
        check()
        features = {'material': scan('material', lambda: material_evaluation(position, check=check))
                    if inspection or self.config.material_enabled else 0}
        lines = None
        supported = VERSION_FAMILIES[self.config.feature_version]
        has_potential = 'potential' in supported
        has_multiplicity = 'multiplicity' in supported
        scan_multiplicity = has_multiplicity and (inspection or self.config.multiplicity_enabled)
        if self.config.feature_version != FEATURE_VERSION:
            scan_lines = inspection or self.config.lines_enabled or scan_multiplicity
            scan_potential = has_potential and (inspection or self.config.potential_enabled)
            if scan_lines or scan_potential:
                lines = scan('lines+potential' if scan_lines and scan_potential else
                             'lines' if scan_lines else 'potential',
                             lambda: line_features(position, check, fours=scan_lines, potential=scan_potential))
            features.update({name: lines['black'][name] - lines['white'][name] if lines else 0
                             for name in LINE_FEATURES})
            if has_potential:
                counts = lines['potential'] if lines and scan_potential else None
                features.update({name: counts['black'][name] - counts['white'][name] if counts else 0
                                 for name in POTENTIAL_FEATURES})
        check()
        captures = None
        if 'captures' in supported:
            if inspection or self.config.captures_enabled:
                captures = scan('captures', lambda: capture_features(
                    position, check, inspection=inspection or
                    ('effects' in supported and self.config.effects_enabled)))
            features.update({name: captures['black'][name] - captures['white'][name] if captures else 0
                             for name in CAPTURE_FEATURES})
        check()
        extra: dict[str, Any] = {}
        if 'effects' in supported:
            for family, names in (('effects', EFFECT_FEATURES), ('multiplicity', MULTIPLICITY_FEATURES)):
                values = None
                if inspection or getattr(self.config, family + '_enabled'):
                    if family == 'effects':
                        values = scan('effects', lambda: capture_effects(
                            position, check, inspection=inspection, captures=captures,
                            before=lines if scan_lines and scan_potential else None))
                    else:
                        assert lines is not None
                        values = scan('multiplicity', lambda: multiplicity_features(position, lines, check, inspection=inspection))
                    extra[family] = values
                features.update({name: values['black'][name] - values['white'][name] if values else 0
                                 for name in names})
        check()
        return features, lines, captures, extra

    def _contributions(self, features: dict[str, int]) -> dict[str, int]:
        enabled = self.config.enabled_families()
        return {name: features[name] * getattr(self.config, name) if family in enabled else 0
                for family in VERSION_FAMILIES[self.config.feature_version]
                for name in FAMILY_FEATURES[family]}

    def __call__(self, position: Position,
                 check: Callable[[], None] = lambda: None, *,
                 profile: EvaluationProfile | None = None) -> int:
        features, _, _, _ = self._features(position, check, profile=profile)
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
        if self.config.feature_version != FEATURE_VERSION:
            report['lines'] = None
        if 'potential' in VERSION_FAMILIES[self.config.feature_version]:
            report['potential'] = None
        if 'captures' in VERSION_FAMILIES[self.config.feature_version]:
            report['captures'] = None
        if self.config.feature_version == EFFECT_VERSION:
            report.update(effects=None, multiplicity=None)
        try:
            features, lines, captures, extra = self._features(position, check, inspection=True)
            contributions = self._contributions(features)
            raw = sum(contributions.values())
            check()
        except SearchCancelled as error:
            report['cancellation'] = str(error)
            return report
        report.update(features=features, contributions=contributions,
                      raw_total=raw, total=max(-EVALUATION_LIMIT, min(EVALUATION_LIMIT, raw)),
                      saturated=abs(raw) > EVALUATION_LIMIT, incomplete=False)
        report.update(extra)
        if captures is not None:
            report['captures'] = captures
        if lines is not None:
            report['lines'] = {name: lines[name] for name in ('black', 'white')}
            if 'potential' in lines:
                report['potential'] = lines['potential']
        return report

    def inspect_move(self, position: Position, move: Coordinate, *,
                     check: Callable[[], None] = lambda: None) -> dict[str, Any]:
        """Explain a legal placement's newly created endpoints on its actual board."""
        if self.config.feature_version != EFFECT_VERSION:
            raise ValueError('Move-effect inspection requires effects-v1.')
        report: dict[str, Any] = {'move': move, 'before': None, 'after': None,
                                  'created_verified_endpoints': None,
                                  'incomplete': True, 'cancellation': None}
        try:
            check()
            transition = position.play(move)
            check()
            before = self.inspect(position, check=check)
            after = self.inspect(transition.position, check=check)
            if before['incomplete'] or after['incomplete']:
                report['cancellation'] = before['cancellation'] or after['cancellation']
                return report
            created = {color: sorted(set(after['multiplicity'][color]['verified_endpoints'])
                                     - set(before['multiplicity'][color]['verified_endpoints']))
                       for color in ('black', 'white')}
            check()
        except SearchCancelled as error:
            report['cancellation'] = str(error)
            return report
        report.update(before=before, after=after, created_verified_endpoints=created,
                      removed=[item.cell for item in transition.captured],
                      outcome=transition.position.outcome, incomplete=False)
        return report
