#!/bin/sh
# Run a Python file with the working Hermes bootstrap (same interpreter and path setup as the launcher), no agent start.
# Operator-supplied paths (public-repository hygiene rule): HQR_HERMES_PYTHON (launcher interpreter) and HQR_HERMES_SOURCE (Hermes checkout).
: "${HQR_HERMES_PYTHON:?set HQR_HERMES_PYTHON to the working Hermes interpreter}"
: "${HQR_HERMES_SOURCE:?set HQR_HERMES_SOURCE to the working Hermes source directory}"
exec "$HQR_HERMES_PYTHON" -I -B -c 'import os, sys
os.environ.pop("PYTHONHOME", None); os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, os.environ["HQR_HERMES_SOURCE"])
sys._hermes_pin_default_home = True
import hermes_bootstrap
if not os.environ.get("HERMES_HOME"):
    from hermes_constants import get_default_hermes_root
    os.environ["HERMES_HOME"] = str(get_default_hermes_root())
import runpy
script = sys.argv[1]; sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")' "$@"
