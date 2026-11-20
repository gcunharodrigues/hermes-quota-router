"""D-37: each profile's copy uses its own config and retained state, and Auto is not limited to default."""
import importlib.util, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_entry():
    spec = importlib.util.spec_from_file_location('hqr_f5_entry', ROOT / '__init__.py',
                                                  submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules['hqr_f5_entry'] = module
    spec.loader.exec_module(module)
    return module


class ProfileHomeTests(unittest.TestCase):
    def test_install_home_is_the_profile_that_holds_the_copy(self):
        entry = load_entry()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'profiles' / 'secondary-test-profile'
            (home / 'plugins' / 'hermes-quota-router').mkdir(parents=True)
            fake = home / 'plugins' / 'hermes-quota-router' / '__init__.py'
            fake.write_text('')
            entry.__file__ = str(fake)
            self.assertEqual(entry._install_home(), home)

    def test_auto_check_has_no_default_profile_gate(self):
        source = (ROOT / 'quota_router' / 'lifecycle.py').read_text()
        self.assertNotIn('profile_not_enrolled_for_auto', source)


if __name__ == '__main__':
    unittest.main()
