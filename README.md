# Hermes Quota Router

Optional subscription-quota governance for Hermes Agent.

**Estado: S1 e S2 aceitas; o ensaio anterior da S3 passou no Docker, e três defeitos de preview estão corrigidos apenas localmente, com revisão e repetição instalada pendentes.**
The GitHub candidate `ad3e180` was installed, enabled and exercised through OFF, Observe, AUTO refusal, restart, disable, remove, reinstall, rollback and isolation controls (docs/s1-installed-test.md).
S1 is management only: it reads no quota and routes nothing.
A S3 oferece Auto condicionado ao mapa aprovado e ao host qualificado; o ensaio anterior não qualifica os bytes das correções locais nem substitui o aceite da fatia.
A public repository is not evidence of working installation, billing eligibility or complete request coverage.

- [Knowledge and decisions](decisions/index.md)
- [S1 aceita](decisions/s1-delivery.md)
- [Emenda HQR-20 aprovada](decisions/hqr-20-amendment.md)
- [Plano da S2](decisions/s2-plan.md)
- [Entrega da S2, aceita](decisions/s2-delivery.md)
- [HQR-38 aceita em 2026-11-17](decisions/hqr-38-delivery.md#aceite-de-guilherme-2026-11-17)
- [Tarefa atual: definição da S4](decisions/s4-definition.md) e [da fatia de auxiliares](decisions/aux-definition.md), aguardando decisões de Guilherme
- [Entrega local da S3 e pendências anteriores](decisions/s3-delivery.md)
- [Plano aprovado da S3](decisions/s3-plan.md)
- [Operação da S3](docs/s3-operations.md)
- [Entrega local de HQR-38](decisions/hqr-38-delivery.md) e [operação](docs/hqr-38-operations.md)
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

## Para agentes e desenvolvedores

Comece pelo [índice de decisões](decisions/index.md), que aponta a tarefa corrente e os documentos canônicos.
O contrato está na [emenda HQR-20](decisions/hqr-20-amendment.md), na [especificação](decisions/product-spec.md) e nos planos de [produto](decisions/product-plan.md), [S2](decisions/s2-plan.md) e [S3](decisions/s3-plan.md).
Os registros de entrega de [S1](decisions/s1-delivery.md), [S2](decisions/s2-delivery.md) e [S3](decisions/s3-delivery.md) separam implementação, testes, revisões e aceite.
Consulte `docs/` para [operação](docs/s3-operations.md), [compatibilidade](docs/compatibility.md) e [testes](docs/testing.md), e registre pendências no [backlog](#backlog).
Os gates locais são `python3 scripts/run_tests.py`, `python3 -m compileall -q __init__.py quota_router scripts tests`, o gate `quota_router.line_gate.check_lines` sobre `git ls-files`, `git diff --check` e `git diff --cached --check`.
Execute também Gitleaks antes de cada commit, `okf --root . --json validate --profile per-repo --gate both` com o binário fixado pela tarefa e `codegraph sync .` com downloads, telemetria e update-check desligados.
Os [comandos completos e os limites dos ensaios instalados](docs/testing.md) não concedem autorização de publicação, instalação ou acesso a dados reais.

## License

MIT; see [LICENSE](LICENSE).
No third-party candidate code has been copied.

## Backlog

Add every deferral with ID, origin, work and completion evidence.
Close entries with a date and evidence; do not delete them or infer execution authority from them.

| ID | Origin | Work | Done condition |
|---|---|---|---|
| HQR-42 | Piloto real HQR-38, 2026-11-17 | A sessão nova do Desktop aberta depois do Auto registrou esforço `low`, enquanto o Auto aplicou `high` à conversa; identificar se o esforço vem do seletor do Desktop, de padrão da sessão ou de outra origem | Origem do esforço identificada por código e por uma sessão nova conferida; correção ou limite registrado na operação; fechado em 2026-11-17: Guilherme classificou o comportamento como aceitável, sem investigação adicional |
| HQR-41 | Piloto real HQR-38, 2026-11-17 | Depois de instalar pelo CLI, a instância do Desktop continuou com o código anterior e só recarregou ao desabilitar e habilitar o plugin no gerenciador do Desktop; o procedimento de operação deve conferir a instância que responde e orientar essa recarga | Procedimento documentado e exercitado numa instalação seguinte, com o status do Desktop trazendo os campos da versão instalada |
| HQR-33 | Preview S3 e decisão D18, 2026-11-16 | Candidata `0376def` aprovada no Docker e instalada com autorização em 2026-11-16; arquivos exatos e nova prévia Observe pelo dispatcher nativo, sem bloqueio de endpoint padrão e com mapa aprovado | A janela Desktop já aberta não foi exercitada nem reiniciada; HQR-34 registra um aviso textual remanescente, e Auto, merge e aceite da S3 continuam separados conforme `decisions/s3-delivery.md`; fechado em 2026-11-17: a janela Desktop foi exercitada no piloto real da HQR-38, em Observe, Auto e OFF, e a S3 foi aceita com a HQR-38 |
| HQR-39 | Pergunta de Guilherme em 2026-11-17 sobre auxiliares por tipo de assinatura | Estender HQR-29: o mapa de `auxiliary.*` deve considerar o tipo de assinatura de cada provedor (janela de 5 h, só semanal, mensal, créditos), não apenas o par de modelos Terra → Sonnet e Luna → Haiku | Mapa de auxiliares por tipo de assinatura aprovado por Guilherme e coberto pela fatia de auxiliares; `image_gen` fica fixo no Codex, porque a Anthropic não tem modelo de geração de imagem (observação de Guilherme em 2026-11-17) |
| HQR-40 | Melhorias opcionais T-SOL04-03 a T-SOL04-05 da revisão de 2026-11-17 | Ampliar controles de falha na durabilidade do backup, snapshots/recibos adulterados e contexto na última verificação; tornar a injeção de erro de readback independente do ordinal de leitura | Novos controles sintéticos executados e revisados, sem mudança de teste protegido sem autorização específica; não substituem a suíte integral ou qualificação instalada da HQR-38 |
| HQR-38 | Política pedida por Guilherme em 2026-11-17 | Troca por janelas e histerese, rede de segurança para sessões fixadas e matriz de assinaturas; manter as decisões e os limites da especificação | Desenho aprovado e correções locais registradas em `decisions/hqr-38-delivery.md`; SOL-04 sintético com revisão crítica limitada aprovada; suíte canônica integral do commit `338bbfa` com 470 execuções verdes (353/19/98), sem alterar produto ou testes; permanecem qualificação nativa instalada, fallback e piloto reais, revisão final e aceite; os ensaios sintéticos não comprovam instalação ou migração real; atualização de 2026-11-17: piloto real executado e fallback aceito por Guilherme com prova de código e testes, conforme `decisions/hqr-38-delivery.md`; permanecem erro de cota real, `installed_verified`, revisão final e aceite da HQR-38; fechado em 2026-11-17: revisão do registro do piloto aprovada e fatia aceita por Guilherme, com erro de cota real e `installed_verified` como limites declarados |
| HQR-36 | Decisão do responsável em 2026-11-16, depois de escolher A + C para HQR-35 | Migrar a leitura de falhas para a opção B: o plugin chama o leitor interno da Anthropic e vê o erro HTTP real, sem depender do patch local `on_error`; exige ampliar os fingerprints de compatibilidade e revisar a regra de leitura apenas pelo leitor público | Opção B implementada com TDD, fingerprints do leitor interno qualificados, regra do projeto atualizada com aprovação, revisão independente e validação no Desktop; até lá, A + C continuam em uso |
| HQR-35 | Desktop ao vivo com `no_snapshot` repetido, 2026-11-16 | Backoff por provedor de 300 s após falha, motivado pelo `Retry-After: 300` observado; valor nativo limitado a 30–3600 s, consumo opcional de `on_error`, motivos HTTP/timeout/rede e próxima tentativa em texto/JSON, sem alterar a política | Qualificado localmente em 2026-11-16: RED `6ae4d04`, 20 testes novos e 346 execuções de regressão verdes; Hermes sem `on_error` conserva `no_snapshot`; revisão, publicação, instalação e validação Desktop permanecem separadas, sem acesso a provedores nesta tarefa; fechado em 2026-11-17: a correção (RED `6ae4d04`) faz parte da candidata `cc878bc`, instalada no piloto real, aceita e integrada na `main` com árvore idêntica ao commit aceito, conforme `decisions/hqr-38-delivery.md`; o backoff não foi observado ao vivo no Desktop, e HQR-36 segue aberta para a opção B |
| HQR-34 | Prévia Observe de D18, 2026-11-16 | Correção local autorizada: aviso de decisão incompleta não afirma uso global de padrões; campos inválidos continuam identificados separadamente; RED `e456205`, controles de desconhecido/esgotado e 326 execuções de regressão verdes | Publicação e instalação desta correção não estão autorizadas; o código instalado continua em `0376def`, Observe, com HQR-25 e validação Desktop ainda separados; fechado em 2026-11-17: a correção (RED `e456205`) faz parte da candidata `cc878bc`, instalada no piloto real, aceita e integrada na `main` com árvore idêntica ao commit aceito, conforme `decisions/hqr-38-delivery.md` |
| HQR-26 | S3 — entrega local | Ensaios de `ba5d6f8` e `0376def` passaram 16/16 no Docker; a candidata D18 foi instalada depois com autorização separada em Observe | HQR-33 mantém a validação da superfície Desktop e as autorizações de piloto e aceite da S3; HQR-34 registra o aviso textual remanescente; fechado em 2026-11-17: a entrega S3 foi integrada com a HQR-38, exercitada no piloto real e aceita por Guilherme, conforme `decisions/hqr-38-delivery.md` |
| HQR-32 | Ensaios S3 publicados e revisão do runner, 2026-11-16 | Fechado em 2026-11-16: correções revisadas/publicadas e candidata `ba5d6f8` aprovada em 16/16 passos no ensaio instalado registrado em `decisions/s3-delivery.md`. | Nenhuma para o runner anterior; D18 e a nova revisão instalada ficam em HQR-33. |
| HQR-27 | S3 — backend nativo | `Changes.set(None)` remove a chave no backend de arquivo; o grupo com null explícito fica indisponível para não prometer restauração de presença impossível. | Correção nativa qualificada com teste de presença/null ou manutenção explícita dessa restrição no status e na operação. |
| HQR-28 | S3 — integração | O runner hermético limpo não oferece `ruamel` e sua integração usa primitiva JSON sintética; a segunda continuação acrescentou prova YAML nativa em home descartável, sem alterar esse guard nem afirmar ensaio instalado. | Ensaio autorizado com a primitiva YAML real, sem tornar o leitor de conta importável na suíte hermética; sem inferir qualificação instalada de um fake. |
| HQR-29 | Decisão de Guilherme, 2026-11-16 | A S3 não governa `auxiliary.*`: tarefas auxiliares fixadas no Codex (Terra, Luna) continuam nele e usam créditos da OpenAI quando a franquia acaba; tarefas em `auto` seguem a escolha nativa, ainda não qualificada. | Fatia curta depois do aceite da S3: grupos auxiliares com Terra → Sonnet e Luna → Haiku no lado Claude, qualificação de `auto`, revisão e aceite. |
| HQR-30 | Higiene pública da S3, 2026-11-16 | Resolvido pelo coordenador: plano S3 sem referências de revisões privadas nem do estudo; runners do piloto S2 recebem caminhos por variáveis (`HQR_PILOT_HERMES_HOME`, `HQR_HERMES_PYTHON`, `HQR_HERMES_SOURCE`). | Nenhuma. |
| HQR-31 | Qualificação sem Git da S3, 2026-11-16 | Resolvido pelo coordenador: o teste Docker criado nesta fatia passa a exigir qualificação sem revisão quando a entrada é marcada para isso, e recusa quando não é. | Nenhuma. |
| HQR-01 | Bootstrap | Confirm the public execution commit and admit S1 BUILD/DEMO. | Owner confirmation bound to the actual reviewed commit; no inferred approval after migration; closed 2026-11-17: S1 was accepted by the owner on 2026-11-15 for the reviewed execution commit recorded in `decisions/s1-delivery.md` |
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
| HQR-25 | S2 DEMO 2026-11-16 | The native reader returns `None` without a reason, and the Anthropic usage API answered 429 with `Retry-After: 300` after five quick requests while Hermes also fetches usage after each turn; the host's cached usage slot cannot be bound to the selected account without credentials, so the plugin does not use it (revisão independente do cache, rodada 1). | A native core extension reports the failure reason and offers a token-free account binding for cached usage, scoped, approved and installed; until then the Anthropic reading may stay unknown for minutes and status names the possible cause. |
| HQR-24 | HQR-20 section 16 | Bot Chat sessions follow the profile model each turn, so a conversation decision changes an open Bot Chat at its next turn. | Before any conversation write in S3: owner accepts the limit, or a native option that keeps the Bot Chat model fixed is qualified. Closed 2026-11-16: Guilherme accepted the limit (HQR-20 section 17, D8). |
