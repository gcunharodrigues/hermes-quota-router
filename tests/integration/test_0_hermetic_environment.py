"""Guard: integration tests never reach the native Hermes quota reader, its credentials or the network.

Discovery runs this module first; when the host reader is importable the suite stops before any plugin test.
Run the suite with a clean environment and `python3 -I` (docs/testing.md).
"""
import importlib.util
import os
import sys
import unittest


def native_reader_importable():
    try:
        return importlib.util.find_spec("agent.account_usage") is not None
    except (ImportError, ValueError):
        return False


class HermeticEnvironmentTests(unittest.TestCase):
    def test_native_reader_is_not_importable(self):
        if native_reader_importable():
            sys.stderr.write("Native Hermes reader importable: stopping before any test can read real quotas\n")
            sys.stderr.flush()
            os._exit(2)


if __name__ == "__main__":
    unittest.main()
