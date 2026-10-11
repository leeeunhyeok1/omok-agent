# AI-written by OpenAI Codex, for issue #26.
"""Worker-only verified loading; external imports/global RNGs live in one process."""
from importlib import import_module
import io
import json
import os
import shutil
from pathlib import Path
import sys
import sysconfig
import tarfile
from tempfile import TemporaryDirectory
from typing import Any

from offline.registry import Entry, RegistryError, ROOT, checkpoint_archive, source_snapshot
from hashlib import sha256

# A restored tree must live until worker exit, including lazy imports/config reads.
_RESTORED: list[TemporaryDirectory[str]] = []


def create(color: int, *, entry: dict[str, Any], seed: int) -> Any:
    registered = Entry.from_record(entry)
    data = registered.data
    if data['runtime'] != sys.version:
        raise RegistryError('Registered Python runtime changed; register a new version.')
    if source_snapshot(ROOT, ('offline',)) != data['adapter_sources']:
        raise RegistryError('Registry adapter changed; register a new version.')
    loader = data['loader']
    if loader['kind'] == 'checkpoint':
        archive = checkpoint_archive(loader['commit'], tuple(loader['paths']))
        directory = TemporaryDirectory(prefix='omok-player-', dir=os.environ['OMOK_WORKER_SNAPSHOTS'])
        _RESTORED.append(directory)
        root = Path(directory.name)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(root, filter='data')
        # The protocol/rules supervisor retains its own live references. The player
        # imports only the restored engine inside this dedicated subprocess.
        for name in list(sys.modules):
            if name == 'omok' or name.startswith('omok.'):
                del sys.modules[name]
    elif loader['kind'] == 'local':
        root = ROOT if loader['root'] == '.' else Path(loader['root'])
    else:
        raise RegistryError('Unknown loader kind.')
    actual = source_snapshot(root, tuple(data['source_paths']))
    for name, expected in data['sources'].items():
        if actual.get(name) != expected:
            raise RegistryError('Source/dependency changed or missing: ' + name)
    if actual != data['sources']:
        raise RegistryError('Source bundle changed; register a new version.')
    if loader['kind'] == 'local':
        directory = TemporaryDirectory(prefix='omok-player-', dir=os.environ['OMOK_WORKER_SNAPSHOTS'])
        _RESTORED.append(directory)
        frozen_root = Path(directory.name)
        for name, expected in data['sources'].items():
            target = frozen_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
            if sha256(target.read_bytes()).hexdigest() != expected:
                raise RegistryError('Source changed while taking the worker snapshot: ' + name)
        root = frozen_root
        # Repository player factories use the copied offline package. Current
        # protocol modules retain their references; all new player imports use the snapshot.
        if loader['root'] == '.' and (root / 'offline').is_dir():
            sys.modules['offline'].__path__ = [str(root / 'offline')]
        if (root / 'omok').is_dir():
            for name in list(sys.modules):
                if name == 'omok' or name.startswith('omok.'):
                    del sys.modules[name]
    return construct_player(root, registered, color, seed)


def construct_player(root: Path, registered: Entry, color: int, seed: int) -> Any:
    """Construct only after a caller has verified and isolated the source tree."""
    data = registered.data
    loader = data['loader']
    sys.path.insert(0, str(root))
    for dependency in data['dependencies']:
        module = import_module(dependency)
        file = getattr(module, '__file__', None)
        if file:
            path = Path(file).resolve()
            if path.is_relative_to(root.resolve()):
                if path.relative_to(root.resolve()).as_posix() not in data['sources']:
                    raise RegistryError('Dependency is outside the registered snapshot: ' + dependency)
            elif (not path.is_relative_to(Path(sysconfig.get_path('stdlib')).resolve())
                  or path.is_relative_to(Path(sysconfig.get_path('purelib')).resolve())
                  or path.is_relative_to(Path(sysconfig.get_path('platlib')).resolve())):
                raise RegistryError('Vendor dependency sources into the registered bundle: ' + dependency)
    factory: Any = import_module(loader['module'])
    file = getattr(factory, '__file__', None)
    if not file or not Path(file).resolve().is_relative_to(root.resolve()):
        raise RegistryError('Loader imported outside the registered source root.')
    if Path(file).resolve().relative_to(root.resolve()).as_posix() not in data['sources']:
        raise RegistryError('Loader source is absent from the snapshot.')
    for part in loader['factory'].split('.'):
        factory = getattr(factory, part)
    options = dict(data['options'])
    if 'candidate_configuration' in options:
        # Construct with the verified/restored engine modules, never live engine classes.
        # Entry already validated the serialized configuration before any scheduling.
        configuration = options.pop('candidate_configuration')
        settings = configuration['settings']
        evaluation_module = import_module('omok.evaluation')
        search_module = import_module('omok.search')
        tactics_module = import_module('omok.tactics')
        table_module = import_module('omok.transposition')
        player_module = import_module('omok.player')
        config = evaluation_module.EvaluationConfig.from_json(
            json.dumps(configuration['evaluation'], allow_nan=False))
        options = {'max_depth': settings['max_depth'], 'max_nodes': settings['max_nodes'],
            'policy': player_module.TimePolicy(**settings['time_policy']),
            'search': search_module.FixedDepthSearch(evaluation_config=config,
                tactics=tactics_module.TacticalPolicy(radius=settings['candidate_radius'], cap=settings['candidate_cap']),
                table=table_module.TranspositionTable(settings['table_capacity']))}
    if 'evaluation_path' in options:
        from omok.evaluation import EvaluationConfig
        path = (root / options.pop('evaluation_path')).resolve()
        if not path.is_relative_to(root.resolve()) or path.relative_to(root.resolve()).as_posix() not in data['sources']:
            raise RegistryError('Evaluator path is outside the verified worker snapshot.')
        options['evaluation_config'] = EvaluationConfig.load(path)
    if data['seed_support'] == 'constructor':
        options['seed'] = seed
    return factory(color, **options)
