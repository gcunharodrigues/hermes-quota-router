# Implements decisions/hqr-20-amendment.md, sections 3/5/13 and AC-17/18/23/24; decisions/s3-plan.md, "Escopo";
# decisions/hqr-38-spec.md, D-28 to D-31 (states and safety net groups).
"""Optional OFF/Observe/Auto management for next-task routes; no request interception."""
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
from threading import RLock

from . import VERSION, storage, groups
from .identity import selection
from .inventory import cron_origins, native_profile, native_sources, read as read_inventory
from .mapping import approved_base, catalog_gate, effective_map, native_catalogs, propose
from .apply import Engine, NativeBackend
from .compat import native_compatibility
from .events import HOOKS, HookWorker
from .policy import decide, eligibility, fallback_chain
from .readings import collect, native_importer, revalidate
from .render import render
from .settings import DEFAULTS, PROVIDERS, load as load_settings, validate

USAGE = ("Usage: /quota-router status | explain | mode off|observe|auto | "
         "config [show | set <key> <value> | reset <key> | approve-map base|fable|astra|fable+astra] [--json]")
AUTO_REASON = "Auto requires an approved map, valid settings and qualified native source"


def _utcnow():
    return datetime.now(timezone.utc)


class Management:
    def __init__(self, ctx, importer=None, sources=None, clock=None, profile=None, backend=None, data_dir=None, compatible=None, catalogs=None):
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
        self.preference_routes = {}
        self.decision_now = None
        self.backend = backend
        self.data_dir = data_dir
        self.compatible = compatible or native_compatibility
        self.catalogs = catalogs or native_catalogs
        self.engine = None
        self.worker = None
        self.hook_registrations = []
        self.auto_failure = None
        saved = self.read("mode", "off")
        self.mode = saved if saved in ("off", "observe") else "unavailable"
        self.closed = False
        self.deployment, self.identity_evidence = selection(self.read("deployment"))
        self.load_retained_state()
        if saved == "auto" and self.auto_check()["ok"]:
            self.set_mode("auto")
            if self.start_auto():
                self.engine.loaded(self.clock().timestamp())

    def load_retained_state(self):
        try:
            if self.data_dir is None:
                constants = sys.modules.get('hermes_constants')
                if constants is None:
                    return
                home = constants.get_hermes_home()
                directory = home / 'plugin-data' / 'hermes-quota-router'
            else:
                directory = Path(self.data_dir)
            try:
                with storage.directory(directory) as fd:
                    handle = storage.open_record(fd, 'state.json')
                    os.close(handle)
            except FileNotFoundError:
                return
            if self.data_dir is None:
                self.data_dir = directory
                self.backend = NativeBackend(directory.parent.parent / 'config.yaml')
            self.engine = Engine(self.data_dir, self.backend, compatible=lambda: self.compatible())
            self.engine.loaded(self.clock().timestamp())
        except Exception:
            self.auto_failure = 'invalid_auto_state'

    # decisions/s3-plan.md, "Escopo": approved map, valid settings, enrolled default profile and qualified source are mandatory.
    def auto_check(self):
        settings, invalid = self.settings()
        if self.read_failed or invalid:
            return {"ok": False, "reasons": ["invalid_settings"]}
        if not settings["roles"]:
            return {"ok": False, "reasons": ["approved_map_required"]}
        if self.profile() != "default":
            return {"ok": False, "reasons": ["profile_not_enrolled_for_auto"]}
        if self.auto_failure:
            return {"ok": False, "reasons": [self.auto_failure]}
        try:
            return self.compatible()
        except Exception:
            return {"ok": False, "reasons": ["native_source_unavailable"]}

    def start_auto(self):
        if self.worker is not None:
            return True
        try:
            if self.engine is None:
                if self.backend is None:
                    from hermes_cli.config import get_config_path
                    self.backend = NativeBackend(get_config_path())
                if self.data_dir is None:
                    from hermes_constants import get_hermes_home
                    self.data_dir = get_hermes_home() / 'plugin-data' / 'hermes-quota-router'
                self.engine = Engine(self.data_dir, self.backend, compatible=lambda: self.compatible())
            if not self.engine.begin():
                return False
            self.worker = HookWorker(self.engine, self.hook_cycle, self.clock)
            for name in HOOKS:
                self.hook_registrations.append(self.ctx.register_hook(name, self.worker.callback(name)))
            return True
        except Exception:
            self.auto_failure = "hook_registration_or_storage_unavailable"
            self.dispose_hooks()
            self.set_mode("unavailable")
            return False

    def dispose_hooks(self):
        if self.worker is not None:
            self.worker.close()
            self.worker = None
        for registration in reversed(self.hook_registrations):
            try:
                registration.dispose()
            except Exception:
                pass
        self.hook_registrations.clear()

    def wait_hooks(self):
        if self.worker is not None:
            self.worker.wait()

    def hook_cycle(self):
        with self.lock:
            if self.mode == "auto" and not self.closed:
                self.status()

    def apply_decisions(self, settings, found, inventory):
        if not self.engine.recover():
            return
        # decisions/hqr-20-amendment.md, AC-20: recover first, then reread routes before calculating the next decision.
        document = self.backend.read()
        fresh = read_inventory(document, [])
        decisions = self.decisions(fresh, propose(fresh, found, settings), found, settings, document)
        enabled = set()
        selections = {}
        if settings["consumers.conversation"]:
            enabled.add("conversation")
        if settings["consumers.subagents"]:
            enabled.update(r["name"] for r in fresh.get("routes", []) if r["name"] in settings["roles"])
        # decisions/hqr-38-spec.md, D-29: each enrolled group carries its own safety net group, enabled and restored with it.
        enabled.update([groups.fallback_group(role) for role in enabled])
        items = dict(decisions.get("routes", {}), conversation=decisions.get("conversation", {}))
        for role, decision in items.items():
            if role in enabled and decision.get("state") == "decided" and role in settings["roles"] and decision.get("choice"):
                provider = decision["choice"]
                selections[role] = dict(settings["roles"][role][provider], provider=provider)
                if decision.get("safety_net") is not None:
                    net = decision['safety_net']
                    selections[groups.fallback_group(role)] = ({'blocked_fields': net['blocked_fields']}
                        if net.get('state') == 'group_blocked' else {"chain": net["chain"]})
        self.engine.cycle(selections, enabled=enabled, now=self.clock().timestamp())
        # Only a confirmed persisted target may advance the preference's expected route.
        document = self.backend.read()
        for role, entry in self.engine.state['groups'].items():
            if groups.is_fallback(role) or not entry.get('active') or groups.preconditions(document, role) or groups.project(document, role) != entry.get('last'):
                continue
            values = entry['last']
            keys = groups.CONVERSATION if role == 'conversation' else groups.FIELDS
            current = {name: values[key].get('value') for name, key in
                       zip(('provider', 'model', 'effort'), (keys[0], keys[1], keys[4]))}
            self.preference_routes[role] = self.route_revision(role, current, document)

    def read(self, key, default=None):
        try:
            return self.ctx.get_config(key, default)
        except Exception:
            self.read_failed = True
            return "unavailable"

    def close(self):
        with self.lock:
            self.closed = True
            self.dispose_hooks()
            self.set_mode("off")

    def settings(self):
        return load_settings(lambda key, default: self.read(key, default))

    def observing(self):
        return not self.closed and self.mode in ("observe", "auto")

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
        healthy = not self.read_failed and saved in ("off", "observe", "auto") and self.mode != "unavailable"
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
                "host": "unqualified",
                "source_qualified": False,
                "lifecycle": "requires_installed_smoke",
                "auto": "unavailable",
                "surfaces": "best_effort_next_tasks",
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
            document, jobs = self.sources()
            inventory = read_inventory(document, jobs)
            result["cron_origins"] = cron_origins(document, jobs)
            found = self.readings(settings)
            source = "native_account_usage" if self.importer is native_importer else "injected_reader"
            # decisions/hqr-38-spec.md, "Regras de decisão": account-level state per provider for status and render.
            states = {p: eligibility(r, settings, self.decision_now)["state"] for p, r in found.items()}
            result["quota"] = {"state": "observed", "source": source, "providers": found, "states": states}
            self.evaluate(result, settings, invalid, found, detail, inventory, document)
            if self.mode == "auto":
                ready = self.auto_check()
                if ready["ok"] and self.engine is not None:
                    self.apply_decisions(settings, found, inventory)
                else:
                    result["auto_suspended"] = ready["reasons"]
        ready = self.auto_check()
        result["subagents"] = self.subagents_status()
        result["auto_available"] = ready["ok"]
        result["auto_reason"] = None if ready["ok"] else ", ".join(ready["reasons"])
        result["compatibility"]["auto"] = "available" if ready["ok"] else "unavailable"
        # D18: source qualification is distinct from map approval, effective Auto and installed lifecycle evidence.
        try:
            native = self.compatible()
        except Exception:
            native = {'ok': False, 'reasons': ['native_source_unavailable']}
        if not native.get('ok'):
            ready = dict(ready, ok=False, reasons=sorted(set(ready.get('reasons', []) + native.get('reasons', ['native_source_unavailable']))))
            result.update(auto_available=False, auto_reason=', '.join(ready['reasons']))
            result['compatibility']['auto'] = 'unavailable'
            if self.mode == 'auto':
                result['auto_suspended'] = ready['reasons']
        result['compatibility'].update(source_qualified=native.get('ok') is True,
                                       host=native.get('host', 'qualified') if native.get('ok') else 'unqualified',
                                       reasons=native.get('reasons', []))
        for key in ('revision', 'qualified_revision', 'revision_note'):
            if key in native:
                result['compatibility'][key] = native[key]
        if native.get('ok'):
            result['draining'] = 'not_applicable_no_request_interception'
        if self.mode == 'auto' and healthy:
            result['integrity'] = 'auto_best_effort_native_config'
        if self.engine is not None:
            result["applied"] = self.engine.report(self.clock().timestamp())
            result["coverage"] = dict(result.get("coverage", {}), hooks="unqualified_until_installed_run",
                                      task_generation="native_session_store_unqualified")
        self.reflect_final_blocks(result, ready, settings)
        # Queries issued since the last effective mode change (zero in OFF); quota_queries_total covers this instance.
        result["quota_queries"] = self.queries
        result["quota_queries_total"] = self.queries_total
        return result

    # D18/AC-17: a late exclusion or suspension must override an earlier optimistic preview in the same response.
    def reflect_final_blocks(self, result, ready, settings):
        decisions = result.get('decisions') or {}
        if 'conversation' not in decisions:
            return
        blocks = result.setdefault('routing_blocks', {})
        applied = result.get('applied') or {}
        exclusions = applied.get('groups_out', {}) if applied.get('auto_declared') else {}
        items = dict(decisions.get('routes', {}), conversation=decisions['conversation'])
        for role, decision in items.items():
            if decision.get('state') == 'disabled_by_setting':
                continue
            excluded = exclusions.get(role, [])
            suspended = bool(settings['roles']) and not ready.get('ok')
            fallback_excluded = exclusions.get(groups.fallback_group(role), [])
            if decision.get('safety_net') is not None and (fallback_excluded or excluded or suspended):
                self.block_safety_net(decision, role, fallback_excluded or excluded,
                                      ready.get('reasons', []) if suspended else [], blocks)
            if not excluded and not suspended:
                continue
            backend_reason = 'advanced_delegation_unavailable'
            fields = sorted(set((blocks.get(role) or {}).get('fields', []) + [field for field in excluded if field != backend_reason]))
            reasons = (blocks.get(role) or {}).get('reasons', [])
            if backend_reason in excluded:
                reasons = sorted(set(reasons + [backend_reason]))
            if suspended:
                reasons = sorted(set(reasons + ready.get('reasons', ['host_not_qualified'])))
            if fields or reasons:
                blocks[role] = {'fields': fields, 'reasons': reasons}
                state = 'backend_unavailable' if not fields and reasons == [backend_reason] else 'group_blocked'
                decision.update(state=state, choice=None, tier=None, would_change=None, proposal_change=None,
                                blocked_fields=fields, block_reasons=reasons)

    def explain(self):
        result = self.status(detail=True)
        if not self.observing():
            result["decisions"] = {"state": "not_observing"}
        return result

    def evaluate(self, result, settings, invalid, found, detail, inventory, document=None):
        proposal = propose(inventory, found, settings)
        decisions = self.decisions(inventory, proposal, found, settings, document)
        result["routing_blocks"] = decisions.get("routing_blocks", {})
        result["decided_at"] = self.decision_now.astimezone(timezone.utc).isoformat()
        result["decision_incomplete"] = bool(invalid) or self.read_failed or any(r["state"] != "ok" for r in found.values())
        result["coverage"] = {"not_governed": inventory.get("not_governed", []), "inventory": inventory.get("state"),
                              "bot_chat": "follows_profile_model_each_turn_HQR-24",
                              "managed_sessions": "created_before_a_decision_keep_their_copy"}
        displayed_map = effective_map(proposal, settings)
        if detail:
            result["map"] = displayed_map
            result["decisions"] = decisions
            return
        def brief(decision):
            keys = ("choice", "tier", "state", "reason", "resets", "partial_pins", "would_change", "proposal_change",
                    "catalog_note", "catalog_unverified", "catalog_missing", "blocked_fields", "block_reasons", "states",
                    "safety_net")
            return {k: decision[k] for k in keys if decision.get(k) is not None}
        if decisions.get("state") == "inventory_unavailable":
            result["decisions"] = {"state": "inventory_unavailable", "provider_level": brief(decisions["provider_level"])}
            return
        result["decisions"] = {"variant": decisions["variant"], "map_status": displayed_map["status"], "map_notes": displayed_map["notes"],
                               "conversation": brief(decisions["conversation"]),
                               "routes": {name: brief(d) for name, d in decisions["routes"].items()},
                               "cron": brief(decisions["cron"])}

    # D18/AC-17 and G2/G8: route presence and both wire fields participate in preference identity.
    def route_revision(self, role, current, document):
        projection = groups.project(document, role) if not groups.preconditions(document, role) else None
        return dict(current, route=self.revision({}, projection))

    def decide_role(self, role, table, current, found, settings, enabled, document=None):
        if not enabled:
            return {"state": "disabled_by_setting", "choice": None, "tier": None}
        approved = settings["roles"].get(role)
        proposed = table.get(role) if table else None
        if approved == {"follows": "conversation"}:
            return {"state": "follows_conversation", "choice": None, "tier": None}
        pair = approved or proposed
        models = {p: pair[p]["model"] for p in pair} if pair else {}
        catalogs = self.catalogs()
        unverified = sorted(p for p in models if catalogs.get(p) is None)
        catalog_details = {"catalog_note": "IDs não verificados", "catalog_unverified": unverified} if unverified else {}
        blocked = {p: reason for p, model in models.items() if (reason := catalog_gate(p, model, catalogs))}
        # decisions/s3-plan.md, "Mapa aprovado": an absent approved ID blocks the role, not just one provider.
        if approved and "model_absent_from_catalog" in blocked.values():
            return dict(catalog_details, state="catalog_model_absent", choice=None, tier=None, reason="model_absent_from_catalog",
                        catalog_missing=sorted(p for p, reason in blocked.items() if reason == "model_absent_from_catalog"))
        now = {"provider": current.get("provider"), "model": current.get("model"), "effort": current.get("effort")}
        identity = self.route_revision(role, now, document) if document is not None else now
        key = (role, self.revision(settings, pair, identity))
        if self.mode == 'auto':
            observed = self.preferences.get(key)
            key = (role, self.revision(settings, pair))
            if self.preference_routes.get(role) != identity:
                self.preferences.pop(key, None)
            # decisions/hqr-20-amendment.md, D10; decisions/s3-delivery.md, G8: preserve only the exact Observe preference.
            if observed is not None:
                self.preferences[key] = observed
            self.preferences = {k: v for k, v in self.preferences.items() if k[0] != role or k == key}
            self.preference_routes[role] = identity
        decision = decide(role, found, settings, self.decision_now, previous=self.preferences.get(key), models=models,
                          blocked=blocked)
        if decision["tier"] == "subscription":
            self.preferences[key] = decision["choice"]

        def change(source):
            target = dict(source[decision["choice"]], provider=decision["choice"]) if source and decision["choice"] else None
            fields = []
            if target and approved and document is not None and not groups.preconditions(document, role):
                current_projection = groups.project(document, role)
                fields = [key for key, cell in groups.target(role, target).items() if cell != current_projection[key]]
            if not target or target == now and not fields:
                return None
            return dict({'from': now, 'to': target}, **({'fields': fields} if fields else {}))

        decision.update(catalog_details)
        # decisions/hqr-38-spec.md, D-28/D-29: the other provider's mapped model for the same role, when usable.
        if role != "cron" and pair and decision["choice"] is not None:
            decision["safety_net"] = fallback_chain(decision, pair)
        decision["would_change"] = change(approved) if approved else None
        decision["proposal_change"] = None if approved else change(proposed)
        if decision["choice"] is None:
            decision["state"] = "no_candidate"
        else:
            decision["state"] = "decided" if approved else "proposal_only"
        return decision

    def subagents_status(self):
        try:
            return self.compatible().get('subagents', {'ok': True, 'source': 'backend_contract'})
        except Exception:
            return {'ok': False, 'reason': 'advanced_delegation_unavailable'}

    def preview_fields(self, document, role, retained):
        """SOL-07: the same preconditions, null and external-edit gates for routes and their separate safety nets."""
        fields = groups.preconditions(document, role) + retained.get('groups_out', {}).get(role, [])
        if fields:
            return sorted(set(fields))
        projection = groups.project(document, role)
        if getattr(self.backend, 'can_store_null', False) is False:
            fields += [key for key, cell in projection.items() if cell.get('present') and cell.get('value') is None]
        section = 'safety_net' if groups.is_fallback(role) else 'groups'
        entry = retained.get(section, {}).get(role, {})
        if entry.get('active'):
            fields += [key for key, cell in projection.items() if cell != entry['values'].get(key)]
        return sorted(set(fields))

    @staticmethod
    def block_safety_net(decision, role, fields, reasons, blocks):
        group = groups.fallback_group(role)
        prior = blocks.get(group) or {}
        fields = sorted(set(fields + prior.get('fields', [])))
        reasons = sorted(set(reasons + prior.get('reasons', [])))
        blocks[group] = {'fields': fields, 'reasons': reasons}
        decision['safety_net'] = {'state': 'group_blocked', 'chain': None, 'blocked_fields': fields, 'block_reasons': reasons}

    def decisions(self, inventory, proposal, found, settings, document=None):
        if inventory.get("state") != "ok":
            return {"state": "inventory_unavailable", "provider_level": decide("general", found, settings, self.decision_now)}
        table = proposal["variants"].get(proposal["effective_variant"], {})
        if self.mode == 'auto':
            current_roles = {'conversation', 'cron'} | {route['name'] for route in inventory['routes']}
            self.preferences = {key: value for key, value in self.preferences.items() if key[0] in current_roles}
            self.preference_routes = {role: value for role, value in self.preference_routes.items() if role in current_roles}
        # D18/AC-17: preview uses the same enrollment gates as Auto, without capturing a baseline or writing.
        blocks = {}
        ready = self.auto_check() if settings['roles'] else {'ok': True}
        dependency = self.subagents_status()
        retained = self.engine.report(self.clock().timestamp()) if self.engine is not None else {}
        # D18/AC-17: explicit OFF ends enrollment; a later Auto begins with a new baseline.
        if not retained.get('auto_declared'):
            retained = {}
        def choose(role, current, enabled):
            fields, reasons = [], []
            if settings['roles'] and enabled:
                if role not in settings['roles']:
                    reasons.append('map_not_approved')
                if not ready.get('ok'):
                    reasons += ready.get('reasons', ['host_not_qualified'])
                if role != 'conversation' and not dependency.get('ok'):
                    reasons.append('advanced_delegation_unavailable')
                fields += self.preview_fields(document, role, retained)
                if fields or reasons:
                    self.preferences = {key: value for key, value in self.preferences.items() if key[0] != role}
                    self.preference_routes.pop(role, None)
                    blocks[role] = {'fields': sorted(set(fields)), 'reasons': sorted(set(reasons))}
                    state = 'backend_unavailable' if reasons == ['advanced_delegation_unavailable'] and not fields else 'group_blocked'
                    return dict(state=state, choice=None, tier=None, would_change=None, proposal_change=None,
                                blocked_fields=blocks[role]['fields'], block_reasons=blocks[role]['reasons'])
            decision = self.decide_role(role, table, current, found, settings, enabled, document)
            net = decision.get('safety_net')
            if net is not None and document is not None:
                group = groups.fallback_group(role)
                fields = self.preview_fields(document, group, retained)
                if not fields:
                    baseline = groups.project(document, group)
                    target = groups.target(group, {'chain': net['chain']}, baseline)
                    fields += groups.effective_fallback_errors(document, group, target, net['chain'])
                if fields:
                    self.block_safety_net(decision, role, fields, [], blocks)
            if decision.get('state') not in ('decided', 'proposal_only', 'follows_conversation'):
                blocks[role] = {'fields': [], 'reasons': [decision.get('reason') or decision['state']]}
            return decision
        routes = {route["name"]: choose(route["name"], route, settings["consumers.subagents"])
                  for route in inventory["routes"]}
        conversation_decision = choose('conversation', inventory['conversation'], settings['consumers.conversation'])
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
            "conversation": conversation_decision,
            "routes": routes,
            "cron": cron_decision,
            "routing_blocks": blocks,
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
            table = approved_base() if parts[2] == "base" else table
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
            try:
                output = self._command(remaining)
            except Exception:
                # Native parsers and storage exceptions may embed credentials; retain journals but never echo the exception.
                self.auto_failure = 'native_state_or_config_unavailable'
                output = self.dump({"ok": False, "mode_effective": "unloaded" if self.closed else self.mode,
                                    "auto_available": False, "auto_reason": self.auto_failure,
                                    "error": "Native state/config unavailable; further Auto writes suspended until reload"})
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
        elif parts == ["apply"]:
            result = self.status()
            if self.mode != "auto":
                error = "AUTO unavailable: apply requires effective Auto"
        elif parts == ["explain"]:
            result = self.explain()
        elif parts in (["status"], []):
            result = self.status()
        elif len(parts) == 2 and parts[0] == "mode" and parts[1] in ("off", "observe", "auto"):
            mode = parts[1]
            if self.closed:
                error = "Plugin instance unloaded; use native management and restart"
            elif mode == "auto" and not self.auto_check()["ok"]:
                error = "AUTO unavailable: " + ", ".join(self.auto_check()["reasons"])
            else:
                try:
                    if mode != 'auto' and self.auto_failure and self.engine is None:
                        raise ValueError('Retained Auto state unavailable')
                    if mode != "auto" and self.engine is not None and self.engine.needs_restoration():
                        ready = self.auto_check()
                        if not ready["ok"]:
                            raise ValueError("Auto restoration suspended")
                        if not self.engine.restore(now=self.clock().timestamp()):
                            raise ValueError("Auto restoration incomplete")
                        self.dispose_hooks()
                    self.ctx.set_config("mode", mode)
                except Exception:
                    error = "Native plugin settings write failed; effective mode unchanged"
                else:
                    self.set_mode(mode)
                    if mode == "auto" and not self.start_auto():
                        error = "AUTO unavailable: hook registration failed"
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
