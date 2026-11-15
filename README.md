# Hermes Quota Router

Optional subscription-quota governance for Hermes Agent.

**Status: S1 accepted on 2026-11-15; the HQR-20 amendment (next-task routing) is approved; S2 (Observe with real quotas) is implemented locally and under review.**
The GitHub candidate `ad3e180` was installed, enabled and exercised through OFF, Observe, AUTO refusal, restart, disable, remove, reinstall, rollback and isolation controls (docs/s1-installed-test.md).
S1 is management only: it reads no quota and routes nothing.
AUTO remains unavailable.
A public repository is not evidence of working installation, billing eligibility or complete request coverage.

- [Knowledge and decisions](decisions/index.md)
- [S1 aceita](decisions/s1-delivery.md)
- [Emenda HQR-20 aprovada](decisions/hqr-20-amendment.md)
- [Plano da S2](decisions/s2-plan.md)
- [Tarefa atual: entrega da S2](decisions/s2-delivery.md)
- [Operação S1](docs/s1-operations.md)
- [Testes sintéticos](docs/testing.md)
- [Ensaio instalado e negativa nativa](docs/s1-installed-test.md)
- [Compatibilidade observada](docs/compatibility.md)
- [Product specification](decisions/product-spec.md)
- [Delivery plan](decisions/product-plan.md)

## Intended behavior

- Optional OFF, Observe and Auto modes.
- Deterministic choice of the model for the next tasks from native quota readings, written to the native profile configuration with native authentication.
- Enrolled profiles: new conversation sessions, subagents and cron without a pin; calls in flight, retries and auxiliary calls are not governed.
- Separate development, test and production runtimes, data and credentials.
- Explicit candidate/stable selection pinned to a complete commit; promotion and rollback with installed-file verification.
- No implicit paid fallback, credential copying, prompt proxy or custom daemon.

```text
one source repository
   └─ task branch + local worktree
        └─ development → candidate in isolated test
                            └─ same qualified revision → production
```

Worktrees separate source files, not runtime credentials or dependencies.
AUTO is best effort: it routes the next tasks and does not veto calls or cap spending (decisions/hqr-20-amendment.md).
Credit use is a per-provider setting; the plugin never turns credits on or off in a provider account.

## Development

Documentation is in Portuguese and retains the functional acceptance criteria of the design.
The public bootstrap excludes private account observations, profile inventories, execution receipts and source history.
Public research reports and ledgers live in `evidence/`; they are documentary evidence, not operational certification.
No environment provisioning, inference, CI workflow or production installation is performed by this bootstrap.

## License

MIT; see [LICENSE](LICENSE).
No third-party candidate code has been copied.

## Backlog

Add every deferral with ID, origin, work and completion evidence.
Close entries with a date and evidence; do not delete them or infer execution authority from them.

| ID | Origin | Work | Done condition |
|---|---|---|---|
| HQR-01 | Bootstrap | Confirm the public execution commit and admit S1 BUILD/DEMO. | Owner confirmation bound to the actual reviewed commit; no inferred approval after migration. |
| HQR-02 | S1 | Build the real optional lifecycle and verify installation in the chosen isolated test destination. | Applicable AC-01–03/10–12/14–15 exercised against installed files, not only source. Closed 2026-11-15: run 4 lifecycle harness, 17 steps passed against the GitHub-installed candidate (docs/s1-installed-test.md, Run 4). |
| HQR-03 | Host contract | Qualify every managed surface/physical attempt and future-profile enforcement. | Closed 2026-11-15: superseded by the approved HQR-20 amendment; a native per-attempt contract stays a possible core extension without a slice. |
| HQR-04 | Subscription boundary | Qualify account/plan/transport/model/window and included billing. | Replaced 2026-11-15 by the credit settings of HQR-20 (section 14): exhausted providers are chosen only when their credit setting allows it. |
| HQR-05 | Isolation | Provision and verify full-host isolation for dev/test/prod. | Negative controls cover filesystem, credentials, dependencies, sockets and inherited environment. |
| HQR-06 | Distribution | Publish the exact admitted revision, preserve provenance and exercise promotion/rollback. | Explicit push/release/install permission and readback; commit alone is not deployment. |
| HQR-07 | Policy | Calibrate thresholds/freshness/hysteresis and approve per-role candidates. | Boundary tests plus separately authorized representative real evidence; no invented gains. |
| HQR-08 | S1 tooling | Implement the authored-line gate and discover non-empty test/build commands. | Closed locally 2026-11-12: `line_gate.py`, 2000/2001/missing-file controls and non-empty unit/integration suites; installed proof is not included. |
| HQR-09 | S1 installed gate | Target admitted 2026-11-12; disabled GitHub installation and exact bytes verified, but active lifecycle remains blocked by HQR-16. | Complete AC-01/10/12 against the actual runtime after disposition of native admission; no real inference by default. Closed 2026-11-15: run 4 exercised AC-01/02/03/10/11/12 on the installed target; DEMO acceptance still pending. |
| HQR-10 | S1 review and readiness | Reconcile critical independent review and remaining applicable acceptance criteria before GO. | Three route-review perspectives reconciled, workspace guard stable and all required observations complete; local source/synthetic tests alone do not close S1. Closed 2026-11-15: three rounds; final security recheck GO on `50e3135` (decisions/s1-delivery.md). |
| HQR-11 | S1 test static diagnostics | Optional editor diagnostics flag nullable ModuleSpec in protected synthetic loaders; preserve tests unless a specific change is approved. | Native execution evidence remains green, or an authorized exact protected-test adjustment resolves static typing without weakening behavior. |
| HQR-12 | Review S1-REV-002 | Clarify transient settings-read recovery: the current failure latch lasts until reload and may coexist with restart_required=false. | New regression and explicit recovery/reload semantics, preserving protected tests; not a quota or AUTO safety bypass. |
| HQR-13 | Review TE-S1-004 | Add independent effect/sentinel assertions for repeated status/explain in OFF and Observe. | Tests catch settings or routing mutations even when reported counters remain zero; installed observations remain separate. |
| HQR-14 | Review TE-S1-005 | Strengthen the concurrent regression with an observable interleaving and unload overlap, not only a scheduling timeout. | Deterministic new coverage catches a serialization regression; existing protected test remains intact unless specifically approved. |
| HQR-15 | Review TE-S1-006 | Cover synthetic module reload and cleanup after failed assertions without assuming a cached submodule is fresh. | Fresh namespaces and guaranteed cleanup are exercised; any edit to protected helpers is separately approved. |
| HQR-16 | S1 run 2 native AdmissionRefused | Reconcile PM generation/cache readiness and authorize a bounded retry after offline enable attempted a dependency download; preserve disabled target and denial. | Coordinator disposition, native admission and complete offline management/lifecycle evidence, without manual enable or bypass. 2026-11-15: recipe cache fixed and run 3 enable passed minutes after the build, but run 3b enable was refused hours later resolving `setuptools` build requirements from the index; stable offline admission needs the native air-gapped settings (`UV_FIND_LINKS`/`UV_NO_INDEX`) and is still open. Closed 2026-11-15 by decision: Guilherme chose a test target with internet egress; native enable passed in run 4. Offline/air-gapped admission is not an S1 requirement. |
| HQR-17 | S1 run 2 runtime diagnostics | Qualify the native installation layout/tool readiness: CLI reports unknown-managed and missing ffmpeg/node/npm/pnpm/ripgrep. | Native readiness evidence appropriate to the supported S1 surface; no hidden warning or claim that plugin tests qualify all Hermes tools. |
| HQR-18 | Review TE-S1-007 | Strengthen the installed verifier against symlink roots/ancestors and special filesystem entries omitted by its independent inventory. | New negative controls reject those states; any edit to protected test_candidate.py needs explicit approval, with no claim of such a state observed in the target. |
| HQR-19 | S1 run 3 lifecycle step 11 | Host `plugins remove` (and the `--force` swap) renames the plugin tree with `os.rename`; on Docker overlayfs with `redirect_dir=nofollow` a tree baked in an image layer fails with EXDEV and leaves an empty `.<name>.remove-*` directory. | Test target keeps plugin state on a rename-capable filesystem, and an upstream issue or fix proposes a copy-and-delete fallback; no plugin change needed. 2026-11-15: run 3b/4 targets keep state in a task Docker volume and native remove passed; upstream fallback still to propose. |
| HQR-20 | Owner decision 2026-11-15 | Simplify the product after S1: route the next tasks from native quota/reset readings, Observe first then Auto, without promising per-call interception. | Closed 2026-11-15: amendment approved by Guilherme with decisions D1 to D7 (decisions/hqr-20-amendment.md). |
| HQR-22 | S1 security review round 1 | The networked test target reaches any host service bound beyond loopback and the local network; there is no firewall, only a harness precondition that fails when a host listener other than the DHCP client leaves loopback. | Accepted as a test-target limit by the internet decision, or a firewall/egress policy is authorized and proven; production never runs in this target. Review round 3 also noted: admission runs after the image build and the step 2 probes, and the default bridge allows container-to-container traffic (only the target was attached on 2026-11-15). |
| HQR-21 | Credit policy | Define whether and when subscription credits may be used. | Closed 2026-11-15: per-provider credit settings decided by Guilherme (HQR-20 amendment, sections 13 and 14). |
| HQR-23 | HQR-20 section 14 | The native Anthropic usage snapshot has no raw body, so disabled extra usage, credit state and the Fable window are not visible to the plugin; Fable stays unknown. | A native core extension exposing those fields is scoped, approved and installed, or the limit stays visible in status. |
| HQR-24 | HQR-20 section 16 | Bot Chat sessions follow the profile model each turn, so a conversation decision changes an open Bot Chat at its next turn. | Before any conversation write in S3: owner accepts the limit, or a native option that keeps the Bot Chat model fixed is qualified. |
