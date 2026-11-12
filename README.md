# Hermes Quota Router

Optional subscription-quota governance for Hermes Agent.

**Status: S1 implemented locally in part; installed qualification blocked.**
OFF/Observe management and synthetic verification exist on the S1 task branch.
No isolated Hermes test target has been admitted, and AUTO remains unavailable.
A public repository is not evidence of working installation, billing eligibility or complete request coverage.

- [Knowledge and decisions](decisions/index.md)
- [Tarefa atual: S1 e prova instalada pendente](decisions/s1-delivery.md)
- [Operação S1](docs/s1-operations.md)
- [Testes sintéticos](docs/testing.md)
- [Compatibilidade observada](docs/compatibility.md)
- [Product specification](decisions/product-spec.md)
- [Delivery plan](decisions/product-plan.md)

## Intended behavior

- Optional OFF, Observe and Auto modes.
- Deterministic decisions before managed execution, with per-attempt admission and native authentication.
- Current and future enrolled profiles, conversations, cron, subagents and auxiliary calls.
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
AUTO remains unavailable unless the host can enforce the complete admission contract.
Subscription eligibility and included billing require account/plan/transport/model qualification; quota visibility alone is insufficient.

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
| HQR-02 | S1 | Build the real optional lifecycle and verify installation in the chosen isolated test destination. | Applicable AC-01–03/10–12/14–15 exercised against installed files, not only source. |
| HQR-03 | Host contract | Qualify every managed surface/physical attempt and future-profile enforcement. | Matrix and negative tests prove the optional host contract; required core extensions separately approved. |
| HQR-04 | Subscription boundary | Qualify account/plan/transport/model/window and included billing. | Authorized real evidence; unknown or extra-usage candidates remain ineligible for AUTO. |
| HQR-05 | Isolation | Provision and verify full-host isolation for dev/test/prod. | Negative controls cover filesystem, credentials, dependencies, sockets and inherited environment. |
| HQR-06 | Distribution | Publish the exact admitted revision, preserve provenance and exercise promotion/rollback. | Explicit push/release/install permission and readback; commit alone is not deployment. |
| HQR-07 | Policy | Calibrate thresholds/freshness/hysteresis and approve per-role candidates. | Boundary tests plus separately authorized representative real evidence; no invented gains. |
| HQR-08 | S1 tooling | Implement the authored-line gate and discover non-empty test/build commands. | Closed locally 2026-11-12: `line_gate.py`, 2000/2001/missing-file controls and non-empty unit/integration suites; installed proof is not included. |
| HQR-09 | S1 installed gate | Admit a concrete whole-Hermes test target, provisioning, transport/install/restart scope and negative isolation controls; then exercise AC-01/10/12 against installed bytes. | Coordinator records explicit operational permission and installed lifecycle/isolation receipts for the reviewed SHA; no real inference by default. |
| HQR-10 | S1 review and readiness | Reconcile critical independent review and remaining applicable acceptance criteria before GO. | Three route-review perspectives reconciled, workspace guard stable and all required observations complete; local source/synthetic tests alone do not close S1. |
| HQR-11 | S1 test static diagnostics | Optional editor diagnostics flag nullable ModuleSpec in protected synthetic loaders; preserve tests unless a specific change is approved. | Native execution evidence remains green, or an authorized exact protected-test adjustment resolves static typing without weakening behavior. |
