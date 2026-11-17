# SOL-04: decisions/hqr-38-delivery.md, explicit publication and legacy readback.
"""Synthetic two-version Engine proof, not native Hermes installation or account testing."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types

from quota_router import downgrade, groups
from quota_router.apply import Engine
from s3_fakes import TARGET, qualified
from test_sol04_persist_publish import fixture


def prove_rollback(legacy_root):
    """Load pinned legacy modules from the operator's read-only snapshot, never Git or live config."""
    package = types.ModuleType('sol04_legacy_product')
    package.__path__ = [str(Path(legacy_root) / 'quota_router')]
    sys.modules[package.__name__] = package
    legacy_engine = importlib.import_module(package.__name__ + '.apply').Engine
    with tempfile.TemporaryDirectory(prefix='sol04-two-versions-') as root:
        engine, backend, expected = fixture(root)
        original = json.loads(expected)
        human_chain = [{'provider': 'openai-codex', 'model': 'gpt-6.1-terra'}]
        backend.document['agent']['reasoning_effort'] = 'low'
        backend.document['fallback_providers'] = copy.deepcopy(human_chain)
        human = backend.read()
        result = downgrade.publish_legacy_state(engine, expected, mode_reader=lambda: 'off')
        assert result['status'] == 'complete', 'Migration reconciliation did not complete'
        assert backend.read() == human, 'Migration changed human configuration'
        # The old revision does not enforce the new guard: it is loaded only after explicit reconciliation.
        old = legacy_engine(engine.directory, backend, qualified)
        assert old.recover() is True, 'Legacy Engine could not read/recover the published record'
        assert old.restore(30) is True, 'Legacy OFF failed'
        assert backend.read() == human, 'Legacy OFF replayed an old baseline'
        assert old.begin() is True, 'Legacy enrollment failed'
        old.cycle({'conversation': TARGET}, 40)
        assert old.restore(50) is True, 'Legacy Auto/OFF failed'
        assert backend.read() == human, 'Legacy Auto/OFF lost human edits'
        preserved = {p.name: p.read_bytes() for p in engine.directory.iterdir() if p.is_file()}
        try:
            downgrade.publish_legacy_state(engine, expected, mode_reader=lambda: 'off')
        except ValueError:
            pass
        else:
            raise AssertionError('Original migration snapshot reused after legacy changes')
        assert {p.name: p.read_bytes() for p in engine.directory.iterdir() if p.is_file()} == preserved, 'Rejected republication changed records'
        assert backend.read() == human, 'Rejected republication changed human configuration'
        saved = engine.read_record('state.json')
        assert saved[downgrade.ARCHIVE]['source_state'] == original, 'Legacy save lost the inert archive'
        new = Engine(engine.directory, backend, qualified)
        assert new.begin() is True, 'Candidate could not restart after the legacy save'
        chain = [{'provider': TARGET['provider'], 'model': TARGET['model']}]
        new.cycle({'conversation': TARGET, 'fallback:conversation': {'chain': chain}}, 60)
        # Only provider/model belong to a fallback entry; use the actual closed projection as the acceptance proof.
        state = new.read_record('state.json')
        baseline = groups.project(human, 'fallback:conversation')
        assert state['groups']['fallback:conversation']['baseline'] == baseline, 'Candidate replayed archived fallback baseline'
        assert new.restore(70) is True, 'Candidate OFF after return failed'
        assert backend.read() == human, 'Candidate return lost current human configuration'
        assert new.read_record('state.json')[downgrade.ARCHIVE]['source_state'] == original, 'Candidate altered the archive'
        assert (engine.directory / result['backup']).read_bytes() == expected, 'Backup bytes changed across versions'
        return {'legacy_readback': True, 'legacy_auto_off': True, 'candidate_fresh_baseline': True,
                'republish_after_legacy_change_refused': True,
                'human_edits_preserved': True, 'archive_inert_and_preserved': True,
                'native_hermes_installation': 'NOT_TESTED', 'configuration_backend': 'synthetic_memory'}
