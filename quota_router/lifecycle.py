"""Management only; no quota source, routing or inference is connected in S1."""
import json

from . import VERSION


class Management:
    def __init__(self, ctx):
        self.ctx = ctx
        saved = ctx.get_config("mode", "off")
        self.mode = saved if saved in ("off", "observe") else "unavailable"
        self.closed = False

    def close(self):
        self.closed = True
        self.mode = "off"

    def status(self):
        saved = self.ctx.get_config("mode", "off")
        return {
            "ok": True,
            "version": VERSION,
            "mode_saved": saved if saved in ("off", "observe", "auto") else "invalid",
            "mode_effective": "unloaded" if self.closed else self.mode,
            "effective_scope": "this_plugin_instance_only",
            "restart_required": not self.closed and saved != self.mode,
            "draining": "not_applicable_no_admission_in_S1",
            "auto_available": False,
            "auto_reason": "S1 has no qualified per-attempt admission or billing contract",
            "quota": {"state": "unknown", "source": None},
            "quota_queries": 0,
            "extra_inferences": 0,
        }

    def command(self, raw_args):
        parts = raw_args.split() if isinstance(raw_args, str) else []
        error = None
        if parts in (["status"], ["explain"], []):
            pass
        elif len(parts) == 2 and parts[0] == "mode" and parts[1] in ("off", "observe", "auto"):
            mode = parts[1]
            if self.closed:
                error = "Plugin instance unloaded; use native management and restart"
            elif mode == "auto":
                error = "AUTO unavailable: admission, surfaces and billing are unqualified"
            else:
                try:
                    self.ctx.set_config("mode", mode)
                except Exception:
                    error = "Native plugin settings write failed; effective mode unchanged"
                else:
                    self.mode = mode
        else:
            error = "Usage: /quota-router status | explain | mode off|observe|auto"
        result = self.status()
        if error:
            result.update(ok=False, error=error)
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
