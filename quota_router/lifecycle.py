"""Management only; no quota source, routing or inference is connected in S1."""
import json

from . import VERSION


class Management:
    def __init__(self, ctx):
        self.ctx = ctx
        self.mode = "off"
        self.closed = False

    def close(self):
        self.closed = True
        self.mode = "off"

    def status(self):
        return {
            "version": VERSION,
            "mode_saved": self.ctx.get_config("mode", "off"),
            "mode_effective": self.mode,
            "auto_available": False,
            "auto_reason": "S1 has no qualified per-attempt admission or billing contract",
            "quota": {"state": "unknown", "source": None},
            "quota_queries": 0,
            "extra_inferences": 0,
        }

    def command(self, raw_args):
        return json.dumps(self.status(), ensure_ascii=False, sort_keys=True)
