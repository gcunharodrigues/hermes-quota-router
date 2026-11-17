# Implements decisions/hqr-20-amendment.md, section 5 and AC-23; decisions/s3-plan.md, "Escopo".
"""Hermes native library entry; hooks register only with effective Auto."""
from .quota_router.lifecycle import Management


def register(ctx):
    manager = Management(ctx)
    ctx.on_unload(manager.close)
    ctx.register_command(
        "quota-router", manager.command,
        description="Quota Router: OFF/Observe/Auto for next tasks from native quota readings",
        args_hint="status | explain | apply | mode off|observe|auto | config [show|set <key> <value>|reset <key>|approve-map <variant>] [--json]",
    )
