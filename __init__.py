"""Hermes native library entry; no provider, hook, inference or background task."""
from .quota_router.lifecycle import Management


def register(ctx):
    manager = Management(ctx)
    ctx.on_unload(manager.close)
    ctx.register_command(
        "quota-router", manager.command,
        description="Quota Router: OFF/Observe with native quota readings; AUTO unavailable until S3",
        args_hint="status | explain | mode off|observe|auto | config [show|set <key> <value>|reset <key>|approve-map <variant>] [--json]",
    )
