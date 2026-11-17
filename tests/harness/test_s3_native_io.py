"""Mutation admission keeps native source and all non-target paths read-only."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class MutationAdmissionTests(unittest.TestCase):
    def test_native_mutations_are_confined_to_the_disposable_home(self):
        module = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as directory:
            guard = module.ProbeGuard(directory)
            own = directory + '/fixture'
            for event, foreign, admitted in [
                ('os.remove', ('/foreign/fixture', -1), (own, -1)),
                ('os.mkdir', ('/foreign/fixture', 448, -1), (own, 448, -1)),
                ('os.rename', (own, '/foreign/fixture', -1, -1), (own, own + '-new', -1, -1)),
                ('os.rename', ('/foreign/fixture', own, -1, -1), (own, own + '-new', -1, -1)),
                ('os.chmod', ('/foreign/fixture', 384, -1), (own, 384, -1)),
                ('os.rmdir', ('/foreign/fixture', -1), (own, -1)),
            ]:
                with self.subTest(event=event, arguments=foreign), self.assertRaises(module.UnsafeProbe):
                    guard.audit(event, foreign)
                guard.audit(event, admitted)
            self.assertEqual(len(guard.denied), 6)

    def test_descriptor_open_guard_resolves_exact_directory_without_broad_relative_admission(self):
        import os
        module = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            guard = module.ProbeGuard(directory)
            self.assertTrue(hasattr(guard, 'wrap_open'))
            wrapped = guard.wrap_open(os.open)
            for parent, allowed in ((directory, True), (outside, False)):
                fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    if allowed:
                        target = wrapped('state.json', os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=fd)
                        os.close(target)
                    else:
                        with self.assertRaises(module.UnsafeProbe):
                            wrapped('state.json', os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=fd)
                        self.assertFalse((Path(outside) / 'state.json').exists())
                finally:
                    os.close(fd)

    def test_partial_native_observations_are_retained_but_never_pass(self):
        module = importlib.import_module('s3_native_consumers')
        def partial():
            raise module.IncompleteProof('session commit not proved', {'subagent': 'native'})
        self.assertEqual(module.case(partial), {'pass': False, 'reason': 'session commit not proved',
                                               'observed': {'subagent': 'native'}})


if __name__ == '__main__':
    unittest.main()
