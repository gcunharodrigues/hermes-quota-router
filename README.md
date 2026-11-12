# Hermes Quota Router

Optional subscription-quota governance for Hermes Agent.

**Status: documentation/bootstrap only.**
There is no installable plugin or qualified AUTO routing yet.
A public repository is not evidence of working installation, billing eligibility or complete request coverage.

- [Knowledge and decisions](decisions/index.md)
- [Tarefa atual: bootstrap e confirmação da revisão](decisions/bootstrap.md)
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
| HQR-08 | S1 tooling | Implement the authored-line gate and discover non-empty test/build commands. | New tests/gate enforce the 2000-character rule with path-specific exemptions and real RED/GREEN. |
