#!/bin/sh
# Run a Python file with the working Hermes bootstrap (same interpreter and path setup as the launcher), no agent start.
PY=$(ls -d /home/hermes/.hermes/tools/python-3.14.9+*-linux-x64/bin/python3 | head -1)
exec "$PY" -I -B -c 'import os, sys
os.environ.pop("PYTHONHOME", None); os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, "/home/hermes/.hermes/hermes-agent")
sys._hermes_pin_default_home = True
import hermes_bootstrap
if not os.environ.get("HERMES_HOME"):
    from hermes_constants import get_default_hermes_root
    os.environ["HERMES_HOME"] = str(get_default_hermes_root())
import runpy
script = sys.argv[1]; sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")' "$@"
