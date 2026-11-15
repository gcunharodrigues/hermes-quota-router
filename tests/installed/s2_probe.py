"""Command probe for S2 runners: JSON from every revision the runners install or roll back to.

Revisions with `quota_router/render.py` answer in readable text and need `--json`; older revisions (S1 `ad3e180`,
S2 `214f028`) already answer JSON and reject the extra argument, so it must not be sent to them.
The capability is read from the modules the handler lookup loaded, before any command runs: no extra command,
reading or write.
`tests/installed/lifecycle.py` keeps the S1 probe unchanged.
"""
from lifecycle import PROBE as S1_PROBE

CALL = 'invoke_plugin_command(handler, raw, source=None'
assert S1_PROBE.count(CALL) == 1, "S1 probe changed; review this derivation"
HANDLER = 'handler = get_plugin_command_handler("quota-router")\n'
assert S1_PROBE.count(HANDLER) == 1, "S1 probe changed; review this derivation"

CAPABILITY = (HANDLER + 'readable = any(name.startswith("hermes_plugins.hermes_quota_router") and name.endswith(".render") '
              'for name in sys.modules)\n')
PROBE = (S1_PROBE.replace(HANDLER, CAPABILITY)
         .replace(CALL, 'invoke_plugin_command(handler, raw + (" --json" if readable else ""), source=None')
         .replace('"handler": handler is not None,', '"handler": handler is not None, "readable": readable,'))
assert PROBE != S1_PROBE and "readable" in PROBE
