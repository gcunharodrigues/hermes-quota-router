"""Plugin management: OFF/Observe, settings and Observe decisions (S2); AUTO stays refused until S3."""
from datetime import datetime, timezone
import hashlib
import json
import platform
from threading import RLock

from . import VERSION
from .identity import selection
from .inventory import native_profile, native_sources, read as read_inventory
from .mapping import model_gate, propose
from .policy import decide
from .readings import collect, native_importer, revalidate
from .render import render
from .settings import DEFAULTS, PROVIDERS, load as load_settings, validate

USAGE = ("Usage: /quota-router status | explain | mode off|observe|auto | "
         "config [show | set <key> <value> | reset <key> | approve-map base|fable|astra|fable+astra] [--json]")
AUTO_REASON = "S2 is Observe only; Auto arrives in S3 after the map approval"


def _utcnow():
    return datetime.now(timezone.utc)


class Management:
    def __init__(self, ctx, importer=None, sources=None, clock=None, profile=None):
        self.ctx = ctx
        self.profile = profile or native_profile
        self.lock = RLock()
        self.read_failed = False
        self.importer = importer or native_importer
        self.sources = sources or native_sources
        self.clock = clock or _utcnow
        self.cache = {}
        self.queries = 0
        self.queries_total = 0
        self.preferences = {}
        self.decision_now = None
        saved = self.read("mode", "off")
        self.mode = saved if saved in ("off", "observe") else "unavailable"
        self.closed = False
        self.deployment, self.identity_evidence = selection(self.read("deployment"))

    def read(self, key, default=None):
        try:
            return self.ctx.get_config(key, default)
        except Exception:
            self.read_failed = True
            return "unavailable"

    def close(self):
        with self.lock:
            self.closed = True
            self.set_mode("off")

    def settings(self):
        return load_settings(lambda key, default: self.read(key, default))

    def observing(self):
        return not self.closed and self.mode == "observe"

    def readings(self, settings):
        found, issued = collect(PROVIDERS, self.clock(), settings["limits.reading_max_age_s"], cache=self.cache,
                                importer=self.importer, clock=self.clock)
        self.queries += issued
        self.queries_total += issued
        # One decision time for every candidate: a reading that expired or crossed a reset meanwhile is unknown.
        self.decision_now = self.clock()
        return revalidate(found, self.decision_now, settings["limits.reading_max_age_s"])

    def set_mode(self, mode):
        if mode != self.mode:
            self.queries = 0
            self.cache.clear()
        self.mode = mode

    def revision(self, settings, *parts):
        """Preference revision: any change of settings, candidate pair or current route starts a new preference history."""
        relevant = {k: v for k, v in settings.items() if k != "mode"}
        return hashlib.sha256(json.dumps([relevant, *parts], sort_keys=True).encode()).hexdigest()[:16]

    def status(self, detail=False):
        saved = self.read("mode", "off")
        deployment_saved, saved_evidence = selection(self.read("deployment"))
        identity_changed = (deployment_saved, saved_evidence) != (self.deployment, self.identity_evidence)
        settings, invalid = self.settings()
        healthy = not self.read_failed and saved in ("off", "observe") and self.mode != "unavailable"
        result = {
            "ok": healthy,
            "integrity": "observe_only_no_route_writes" if healthy else "settings_or_mode_unavailable",
            "version": VERSION,
            "deployment": self.deployment,
            "deployment_saved": deployment_saved,
            "identity_evidence": self.identity_evidence,
            "identity_saved_evidence": saved_evidence,
            "installed_verified": False,
            "compatibility": {
                "python": platform.python_version(),
                "host": "not_verified_in_this_runtime",
                "lifecycle": "requires_installed_smoke",
                "auto": "unavailable",
                "surfaces": "observe_only_in_S2",
            },
            "mode_saved": saved if saved in ("off", "observe", "auto") else "invalid",
            "mode_effective": "unloaded" if self.closed else self.mode,
            "effective_scope": "this_plugin_instance_only",
            "restart_required": not self.closed and (saved != self.mode or identity_changed),
            "draining": "not_applicable_no_admission_in_S1",
            "auto_available": False,
            "auto_reason": AUTO_REASON,
            "settings": settings,
            "settings_invalid": invalid,
            "profile": self.profile(),
            "enrollment": {"state": "enrolled", "scope": "this_profile",
                           "other_profiles": "a profile without this plugin enabled is not enrolled; see `hermes -p <profile> plugins list`"},
            "quota": {"state": "unknown", "source": None},
            "extra_inferences": 0,
        }
        if self.observing():
            # Inventory first: its I/O must not age the readings after their decision-time check.
            inventory = read_inventory(*self.sources())
            found = self.readings(settings)
            source = "native_account_usage" if self.importer is native_importer else "injected_reader"
            result["quota"] = {"state": "observed", "source": source, "providers": found}
            self.evaluate(result, settings, invalid, found, detail, inventory)
        # Queries issued since the last effective mode change (zero in OFF); quota_queries_total covers this instance.
        result["quota_queries"] = self.queries
        result["quota_queries_total"] = self.queries_total
        return result

    def explain(self):
        result = self.status(detail=True)
        if not self.observing():
            result["decisions"] = {"state": "not_observing"}
        return result

    def evaluate(self, result, settings, invalid, found, detail, inventory):
        proposal = propose(inventory, found, settings)
        decisions = self.decisions(inventory, proposal, found, settings)
        result["decided_at"] = self.decision_now.astimezone(timezone.utc).isoformat()
        result["decision_incomplete"] = bool(invalid) or self.read_failed or any(r["state"] != "ok" for r in found.values())
        result["coverage"] = {"not_governed": inventory.get("not_governed", []), "inventory": inventory.get("state"),
                              "bot_chat": "follows_profile_model_each_turn_HQR-24",
                              "managed_sessions": "created_before_a_decision_keep_their_copy"}
        if detail:
            result["map"] = proposal
            result["decisions"] = decisions
            return
        def brief(decision):
            keys = ("choice", "tier", "state", "reason", "resets", "partial_pins", "would_change", "proposal_change")
            return {k: decision[k] for k in keys if decision.get(k) is not None}
        if decisions.get("state") == "inventory_unavailable":
            result["decisions"] = {"state": "inventory_unavailable", "provider_level": brief(decisions["provider_level"])}
            return
        result["decisions"] = {"variant": decisions["variant"], "map_status": proposal["status"], "map_notes": proposal["notes"],
                               "conversation": brief(decisions["conversation"]),
                               "routes": {name: brief(d) for name, d in decisions["routes"].items()},
                               "cron": brief(decisions["cron"])}

    def decide_role(self, role, table, current, found, settings, enabled):
        if not enabled:
            return {"state": "disabled_by_setting", "choice": None, "tier": None}
        approved = settings["roles"].get(role)
        proposed = table.get(role) if table else None
        pair = approved or proposed
        models = {p: pair[p]["model"] for p in pair} if pair else {}
        blocked = {p: reason for p, model in models.items() if (reason := model_gate(model))}
        now = {"provider": current.get("provider"), "model": current.get("model"), "effort": current.get("effort")}
        key = (role, self.revision(settings, pair, now))
        decision = decide(role, found, settings, self.decision_now, previous=self.preferences.get(key), models=models,
                          blocked=blocked)
        if decision["tier"] == "subscription":
            self.preferences[key] = decision["choice"]

        def change(source):
            target = dict(source[decision["choice"]], provider=decision["choice"]) if source and decision["choice"] else None
            return {"from": now, "to": target} if target and target != now else None

        decision["would_change"] = change(approved) if approved else None
        decision["proposal_change"] = None if approved else change(proposed)
        if decision["choice"] is None:
            decision["state"] = "no_candidate"
        else:
            decision["state"] = "decided" if approved else "proposal_only"
        return decision

    def decisions(self, inventory, proposal, found, settings):
        if inventory.get("state") != "ok":
            return {"state": "inventory_unavailable", "provider_level": decide("general", found, settings, self.decision_now)}
        table = proposal["variants"].get(proposal["effective_variant"], {})
        routes = {route["name"]: self.decide_role(route["name"], table, route, found, settings, settings["consumers.subagents"])
                  for route in inventory["routes"]}
        cron = inventory["cron"]
        if not settings["consumers.cron"]:
            cron_decision = {"state": "disabled_by_setting", "choice": None, "tier": None}
        elif not cron["globals_writable"]:
            cron_decision = {"state": "blocked_partial_pins" if cron["partial_pins"] else "jobs_unavailable",
                             "partial_pins": cron["partial_pins"], "choice": None, "tier": None}
        else:
            conversation = inventory["conversation"]
            current = {"provider": cron["provider"] or conversation["provider"], "model": cron["model"] or conversation["model"],
                       "effort": conversation["effort"]}
            cron_decision = self.decide_role("cron", table, current, found, settings, True)
        return {
            "variant": proposal["effective_variant"],
            "conversation": self.decide_role("conversation", table, inventory["conversation"], found, settings,
                                             settings["consumers.conversation"]),
            "routes": routes,
            "cron": cron_decision,
        }

    def configure(self, parts):
        settings, invalid = self.settings()
        if parts in (["config"], ["config", "show"]):
            return {"ok": True, "settings": settings, "settings_invalid": invalid, "defaults": DEFAULTS}, None
        if len(parts) == 4 and parts[1] == "set":
            key, value = parts[2], parts[3]
            if key == "mode":
                return None, "Use /quota-router mode to change the mode"
            ok, normalized = validate(key, value)
            if not ok:
                return None, f"Invalid value for {key}: {normalized}; nothing was written"
        elif len(parts) == 3 and parts[1] == "reset" and parts[2] in DEFAULTS and parts[2] != "mode":
            key, normalized = parts[2], DEFAULTS[parts[2]]
        elif len(parts) == 3 and parts[1] == "approve-map":
            proposal = propose(read_inventory(*self.sources()), {}, settings)
            table = proposal["variants"].get(parts[2])
            if not table:
                return None, "Unknown map variant or inventory unavailable; nothing was written"
            ok, normalized = validate("roles", table)
            if not ok:
                return None, f"Proposed map is invalid ({normalized}); nothing was written"
            key = "roles"
        else:
            return None, USAGE
        try:
            self.ctx.set_config(key, normalized)
        except Exception:
            return None, "Native plugin settings write failed; nothing changed"
        settings, invalid = self.settings()
        return {"ok": True, "settings": settings, "settings_invalid": invalid, "changed": {key: normalized}}, None

    def command(self, raw_args):
        """Readable chat text by default; the same result as strict JSON when the arguments include `--json`."""
        parts = raw_args.split() if isinstance(raw_args, str) else []
        as_json = "--json" in parts
        remaining = " ".join(p for p in parts if p != "--json")
        with self.lock:
            output = self._command(remaining)
        if as_json:
            return output
        payload = json.loads(output)
        name = parts[0] if parts and parts[0] in ("status", "explain", "config", "mode") else "status"
        try:
            return render(name, payload)
        except Exception:
            return "Não foi possível montar o texto do resultado. Use `/quota-router status --json` para ver os dados."

    def _command(self, raw_args):
        parts = raw_args.split() if isinstance(raw_args, str) else []
        error = None
        if parts and parts[0] == "config":
            payload, error = self.configure(parts)
            if payload is not None:
                return self.dump(payload)
            result = self.status()
        elif parts == ["explain"]:
            result = self.explain()
        elif parts in (["status"], []):
            result = self.status()
        elif len(parts) == 2 and parts[0] == "mode" and parts[1] in ("off", "observe", "auto"):
            mode = parts[1]
            if self.closed:
                error = "Plugin instance unloaded; use native management and restart"
            elif mode == "auto":
                error = "AUTO unavailable: " + AUTO_REASON
            else:
                try:
                    self.ctx.set_config("mode", mode)
                except Exception:
                    error = "Native plugin settings write failed; effective mode unchanged"
                else:
                    self.set_mode(mode)
            result = self.status()
        else:
            error = USAGE
            result = self.status()
        if error:
            result.update(ok=False, error=error)
        return self.dump(result)

    @staticmethod
    def dump(payload):
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        except ValueError:
            return json.dumps({"ok": False, "error": "Result contained a non-finite number and was withheld"})
