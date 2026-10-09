# AI-written by OpenAI Codex, for issue #21.
"""Portable identity and observed conditions for bounded local comparisons."""
from dataclasses import asdict
from time import get_clock_info
from hashlib import sha256
import os
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any

from omok.evaluation import EvaluationConfig
from omok.player import TimePolicy
from omok.search import FixedDepthSearch
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable


def evaluation_identity(config: EvaluationConfig) -> dict[str, Any]:
    return {'feature_version': config.feature_version, 'configuration_id': config.identity,
            'configuration': config.canonical_json()}


def conditions() -> dict[str, Any]:
    cpu = platform.processor()
    if sys.platform == 'darwin':
        try:
            cpu = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                          text=True, timeout=2).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
            'platform': platform.platform(), 'machine': platform.machine(),
            'cpu': cpu or None, 'cpu_count': os.cpu_count(),
            'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
            'load_average': list(os.getloadavg()) if hasattr(os, 'getloadavg') else None,
            'workers': 1, 'execution': 'sequential in-process; external contention uncontrolled',
            'clock': vars(get_clock_info('monotonic'))}


def engine_sources() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1] / 'omok'
    return {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(root.glob('*.py'))}


def search_settings(*, depth: int, nodes: int, radius: int, cap: int,
                    policy: TimePolicy) -> dict[str, Any]:
    return {'max_depth': depth, 'max_nodes': nodes, 'candidate_radius': radius,
            'candidate_cap': cap, 'full_width': False,
            'ordering': 'omok.tactics.static_rank', 'time_policy': asdict(policy),
            'table_capacity': 4096, 'extensions': 'none'}


def configured_search(config: EvaluationConfig | None, settings: dict[str, Any], *,
                      profile_every: int = 0) -> FixedDepthSearch:
    return FixedDepthSearch(evaluation_config=config, profile_every=profile_every,
                           tactics=TacticalPolicy(radius=settings['candidate_radius'],
                                                  cap=settings['candidate_cap']),
                           table=TranspositionTable(settings['table_capacity']))
