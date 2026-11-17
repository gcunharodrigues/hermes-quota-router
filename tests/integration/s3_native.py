"""Hermetic native config seam over JSON storage; no host configuration loader or account import.

When the authorized local source is present its unmodified config_backend module is executed under an inert package.
The low-level JSON primitive is synthetic: this is not a qualification of native YAML/comment persistence.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

from quota_router.apply import durable

SOURCE = Path(os.environ['HQR_NATIVE_SOURCE']) / 'hermes_cli/config_backend.py' if os.environ.get('HQR_NATIVE_SOURCE') else None


def install_layer(checkpoint=None):
    import dataclasses
    package = types.ModuleType('hermes_cli')
    package.__path__ = []
    sys.modules['hermes_cli'] = package
    utils = types.ModuleType('utils')
    def update(path, key, value):
        path = Path(path)
        document = json.loads(path.read_text())
        parts = key.split('.')
        node = document
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if value is None:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = copy.deepcopy(value)
        import os
        import tempfile
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        with os.fdopen(fd, 'w') as handle:
            json.dump(document, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if checkpoint:
            checkpoint(key)
    utils.fast_safe_load = lambda handle: json.load(handle)
    utils.atomic_roundtrip_yaml_update = update
    def forbidden(*_args, **_kwargs):
        raise AssertionError('Whole-document write is outside S3')
    utils.atomic_roundtrip_yaml_save = forbidden
    sys.modules['utils'] = utils
    if SOURCE is not None and SOURCE.is_file():
        spec = importlib.util.spec_from_file_location('hermes_cli.config_backend', SOURCE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return 'native_config_layer_with_synthetic_storage'
    # The supported runner also works where the read-only native source is unavailable.
    module = types.ModuleType('hermes_cli.config_backend')
    @dataclasses.dataclass
    class Changes:
        document: object = None
        set: object = None
        unset: tuple = ()
        extra_content_on_create: object = None
    def write_changes(path, changes):
        assert changes.document is None
        for key, value in (changes.set or {}).items():
            update(path, key, value)
        for key in changes.unset:
            update(path, key, None)
    module.Changes = Changes
    module.write_changes = write_changes
    module.read_config_doc = lambda path: json.loads(Path(path).read_text())
    sys.modules['hermes_cli.config_backend'] = module
    return 'synthetic_config_layer'
