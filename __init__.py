# Implements decisions/hqr-20-amendment.md, section 5 and AC-23; decisions/s3-plan.md, "Escopo".
"""Hermes native library entry; hooks register only with effective Auto."""
import os
from pathlib import Path

from .quota_router.apply import NativeBackend
from .quota_router.auxiliary import native_registry
from .quota_router.compat import native_auxiliary_compatibility, native_compatibility
from .quota_router.inventory import native_sources
from .quota_router.lifecycle import PLUGIN_DATA, Management


def _install_home():
    """D-37: the Hermes home that holds this copy (<home>/plugins/<slug>), or None outside a plugins directory.

    Revisão F1–F5, R4: absolute, never resolved; a symlinked slot must not name the profile its target lives in.
    """
    here = Path(os.path.abspath(__file__)).parent
    return here.parent.parent if here.parent.name == 'plugins' else None


def _registering_home():
    """The home Hermes binds around register() (`_plugin_home_scope`), or None outside a Hermes process."""
    try:
        from hermes_constants import get_hermes_home
        return Path(os.path.abspath(get_hermes_home()))
    except Exception:
        return None


def register(ctx):
    # D-37 and Revisão F1–F5, R4: the registering home is authoritative; the install path is only a cross-check, and a
    # disagreement refuses Auto, so one profile's copy never writes another profile's config or retained state.
    home, install = _registering_home(), _install_home()
    if home is None:
        manager = Management(ctx)
    else:
        config = home / 'config.yaml'
        manager = Management(ctx, backend=NativeBackend(config), data_dir=home / PLUGIN_DATA,
                             sources=lambda: native_sources(config), compatible=lambda: native_compatibility(home),
                             auxiliary_compatible=lambda: native_auxiliary_compatibility(home),
                             auxiliary_registry=lambda: native_registry(home),
                             refused='plugin_home_mismatch' if install is not None and install != home else None)
    ctx.on_unload(manager.close)
    ctx.register_command(
        "quota-router", manager.command,
        description="Quota Router: OFF/Observe/Auto for next tasks from native quota readings",
        args_hint="status | explain | apply | mode off|observe|auto | config [show|set <key> <value>|reset <key>|approve-map <variant>] [--json]",
    )
