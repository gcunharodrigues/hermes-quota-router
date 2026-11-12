"""Hermes native library entry; no provider, inference hook or background task."""
from .quota_router.lifecycle import Management


def register(ctx):
    manager = Management(ctx)
    ctx.on_unload(manager.close)
    ctx.register_command(
        "quota-router", manager.command,
        description="Quota Router: OFF/Observe management; AUTO unavailable",
        args_hint="status | explain | mode off|observe|auto",
    )
