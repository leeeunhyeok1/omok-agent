# AI-written by OpenAI Codex, for issue #43.
"""Worker-only reload of a self-contained champion export, with fresh caches."""
import base64
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

from offline.champions import load_export
from offline.registry import Entry, digest, source_snapshot
from offline.registry_worker import construct_player

_RESTORED: list[TemporaryDirectory[str]] = []


def create(color: int, *, artifact: str, identity: str, seed: int = 0) -> Any:
    data = load_export(Path(artifact))
    if digest(data) != identity:
        raise ValueError('Export changed after scheduling.')
    bundle = data['version']['bundle']
    entry = Entry.from_record(bundle['entry'])
    if entry.data['runtime'] != sys.version:
        raise ValueError('Champion runtime changed; revalidate a new compatible version.')
    directory = TemporaryDirectory(prefix='omok-champion-', dir=os.environ['OMOK_WORKER_SNAPSHOTS'])
    _RESTORED.append(directory)
    root = Path(directory.name)
    for name, content in bundle['sources'].items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('Archived source path escapes its snapshot.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(content, validate=True))
    if source_snapshot(root, tuple(entry.data['source_paths'])) != entry.data['sources']:
        raise ValueError('Restored champion differs from the promoted snapshot.')
    # Keep supervisor references intact; future player imports use the archive.
    if (root / 'offline').is_dir():
        sys.modules['offline'].__path__ = [str(root / 'offline')]
        for name in list(sys.modules):
            if name.startswith('offline.'):
                del sys.modules[name]
    for name in list(sys.modules):
        if name == 'omok' or name.startswith('omok.'):
            del sys.modules[name]
    return construct_player(root, entry, color, seed)
