---
type: Delivery Record
title: S3 — implementação local de Auto e pendências
description: Registro da S3 com candidata D18 ensaiada e instalada em Observe, correção local de HQR-34 e limites de leitura; piloto Auto e aceite continuam pendentes.
status: draft
---

# S3 — implementação local de Auto e pendências

O relato inicial abaixo é histórico; o estado posterior está nas entradas datadas e no backlog do README, incluindo a correção local de HQR-34 ao fim deste registro.

Implementação iniciada por autorização de Guilherme, sobre o [plano aprovado](s3-plan.md), sem alterar seus bytes.
A S3 ainda não está concluída nem aceita: faltam provas do runner e do destino instalado.
A revisão independente de implementação não foi executada por este worker; nenhuma inferência foi chamada.

## Identidade e limites

- Worktree de tarefa: `.worktrees/hqr-s3`, relativa à raiz do projeto.
- Branch: `hermes/2026-11-16-hqr-s3`.
- Base conferida antes da primeira edição: `f7f3136c5d1c53947bce7a82d50beef89675c277`.
- Versão local: `0.3.0rc1`.
- Nenhum push, merge, instalação, Docker, restart, inferência ou acesso ao arquivo real de configuração, auth store ou tokens.
- Fontes do Hermes lidas somente no checkout autorizado; os ensaios usam dados e diretórios temporários sintéticos.

## Commits anteriores ao registro final

O histórico Git da branch identifica também o commit que acrescenta este registro, cujo próprio SHA não pode estar dentro dele.
As linhas `test(red):` são os commits RED preservados; os demais registram GREEN e correções incrementais.

- `a281318368fec94766809c4698eb60894e0ea73f` — test(red): require durable closed-projection Auto application
- `b0453de49ad03eb30bd602855ecbcbf09ebd213a` — feat: apply closed Auto groups with durable recovery and baseline restore
- `b3ececca0af5d36a23ca9cfa161d6abc003c8868` — test(red): require approved Auto lifecycle and provenance gates
- `ba5ae81aa25818abcb221bf3e515bf4d27aa47bc` — feat: enable qualified Auto lifecycle with approved map and closed hooks
- `8f3e2f79ec97d52d9ff375f0df72f25a3644f519` — test(red): require enrollment and group-local recovery isolation
- `296ee71e2f8d6430ca0e8954f2ae88bd423d1def` — fix: enroll enabled groups and isolate recovery exclusions
- `1b33da269c497f471a0364708c9cae678d36c389` — test(red): require safe installed S3 revision swap sequence
- `b9acf794a66a8e9b4ee81ba79c0609ed12550c9b` — test(red): require native catalog and cron effort edge semantics
- `a61aec58ec4c90b3314c32c14e8b3eed398af440` — fix: honor native catalog absence and cron effort origins
- `934f204d9ff7d07eb32c0abc7c8d2c10a5feb2b5` — feat: add installed Auto runner with guarded swaps and process recovery proofs
- `504a8be402c05fa757e66e81502bcccfc6172bc5` — test(red): require native hook shape and explicit re-enrollment
- `b910eeeacda8d2080943c3e2b0cf7e242b4e1a73` — fix: retain absence diagnostics and re-enroll after explicit OFF
- `c98b6f90eaf0dd749931da53c26d5334972519e2` — test(red): require durable generation for unchanged first decision
- `ab74c4fc5b2ba1a1a79fb851b62d0c09e0a09ee8` — fix: commit the first unchanged enrolled decision without rewriting config
- `747dc46b1db7eba8df735b4b7b11f7094867672e` — test(red): reject unavailable source on loaded native functions
- `c22233501248d9b73a77eb451adbea455c6201fb` — test(red): require file backend identity for qualified Auto writes
- `96ffcea0973e308426de343be2e574a91596dadf` — fix: fail closed on native source and backend drift
- `e0415d859c24da408baae044a8ad5f9d3384ac57` — test(red): require redaction and suspension on Auto storage failure
- `79ae239216a4826889b88d7f5bff6305a269721c` — fix: redact Auto storage failures and suspend subsequent writes
- `228cd6e008b023afe77b1e1cadf86240d7444589` — test(red): require applied values for every enrolled role
- `0bf42db2a37a02a0e5632e370f275d55c33d7700` — fix: expose closed last-applied values for every enrolled role

- `e4d318afbb0716f4717eb9f8d01cc2264728205d` — docs: record local S3 Auto delivery and explicit qualification gaps

## RED observado e proteção dos testes

Cada ciclo RED foi executado com `python3 scripts/run_tests.py tests.unit.<módulo>` ou `tests.harness.test_s3_auto_harness` antes da implementação correspondente.
O histórico RED permite repetir as falhas de requisito ausente sem editar testes; este registro distribui somente resultados resumidos.
As falhas de RED incluem ausência do motor, hooks/compatibilidade, inscrição sem candidato, isolamento da recuperação, semântica do catálogo/esforço, payload nativo, geração sem escrita e fonte carregada indisponível.
A regressão de processos e a matriz de cenários acrescentam provas à implementação já exercitada, sem serem apresentadas como novos ciclos RED.

`protected_test_approval`: D14, aprovação de Guilherme de 2026-11-16, somente `tests/integration/test_export.py:23`.
A mudança exige exatamente `on_session_open`, `on_kanban_dispatch_tick`, `subagent_start`, `on_session_start` e `api_request_error` nessa ordem.
`git diff f7f3136 -- <todos os testes preexistentes>` mostra apenas essa substituição; nenhum helper, guard, runner anterior ou teste RED foi enfraquecido.
As comparações por commit RED distinguem os arquivos acrescentados do único delta protegido autorizado.

## Provas executadas

Comando canônico: `python3 scripts/run_tests.py`.
A regressão completa final retornou `Ran 127 tests in 0.924s`, `Ran 9 tests in 1.562s` e `Ran 22 tests in 0.088s`, todas com `OK` e exit 0.
Os tempos resumidos são desta execução, não metas.
Não houve skip nem inferência nos testes.
A integração usa `Changes`/`write_changes` nativos com armazenamento inferior sintético; não é prova do preservador YAML ou do destino Docker.
Dois processos reais disputaram o lock e processos reais terminaram abruptamente em cada ponto testado de escrita.
As quatro situações de recuperação, aliases de credencial sintéticos, ausência de campo, OFF, consumidor desligado, fallbacks e divergência foram exercitados.
Os testes de geração cobrem A₁ → B → A₂ e a janela inclusiva de 60 s, com fonte não qualificada sem idade.

Os comandos finais requeridos são `compileall`, gate de linhas, OKF oficial/perfil, `git diff --check` e CodeGraph sem downloads/telemetria/update-check.
A compilação e o gate de linhas já executados retornaram exit 0 e `[]`; a validação OKF retornou `official: conformant`, `profile: pass`, `navigation: valid`, `coverage: complete`, sem diagnósticos.
Os checks de whitespace apontaram linha vazia adicional no fim de dois documentos e, no diff integral contra a base, de `quota_router/inventory.py`; foram removidas sem mudança funcional antes da repetição final obrigatória.
O primeiro CodeGraph selecionou um índice ancestral porque a worktree ainda não tinha o seu; esse resultado não foi usado como prova da worktree.
Foi criado o índice próprio por `CodeGraph.initSync` sem instalador, hooks ou mudança de instruções, e `codegraph sync .` retornou `Synced 62 changed files`; a última atualização retornou `Synced 3 changed files`.
O banco confirmado pertence a `.codegraph/codegraph.db` na raiz desta worktree, com downloads, telemetria e update-check desligados.
Os gates são repetidos após o stage dos documentos finais.
O scanner Gitleaks roda antes de cada commit; dois alertas foram identificados como SHA-256 de fonte em campos com a palavra `key`, sem credenciais, e os mesmos digests foram mantidos com formatação JSON em linha separada.
Nenhuma regra do scanner foi desabilitada ou colocada em allowlist.

## Contrato → implementação → limite

| Item | Estado local | Evidência e limite |
|---|---|---|
| 1 — mapa | Feito | Tabela aprovada de 12 papéis; cron segue conversa; esforços por provider, catálogo carregado e Fable/Astra inelegíveis. |
| 2 — grupos | Feito com restrição nativa | Projeções fechadas e lista RMW; credenciais/aliases/overrides bloqueiam; null explícito fica indisponível devido ao backend observado. |
| 3 — aplicação | Feito localmente | Baseline com presença, lock entre processos, diário durável, releitura, quatro recuperações, OFF e consumidor desligado. |
| 4 — compatibilidade | Parcial por destino | 71 funções e quatro constantes do Hermes de trabalho, incluindo advanced-delegation 1.1.0 e o leitor offline models.dev; fonte carregada/namespace ativo e backend conferidos; entrada Docker pendente. |
| 5 — lifecycle | Feito localmente | Auto condicionado a mapa/settings/compatibilidade, apply e status/explain; nenhuma afirmação de instalação. |
| 6 — hooks/AC-22 | Fallback implementado | Registro apenas em Auto, disposal e fila fechada; regra de geração testada; fonte nativa e cobertura instalada permanecem não qualificadas. |
| 7 — ausência | Feito localmente | Marca durável, último ciclo e diagnóstico na recarga, inclusive sem subtree; não distingue ausência de inatividade. |
| 8 — manifesto | Feito | `0.3.0rc1`, exatamente cinco hooks, descrição sem Auto indisponível globalmente. |
| 9 — protegidos | Feito | Somente a linha aprovada em D14 foi alterada; os demais arquivos preexistentes permanecem idênticos. |
| 10 — U/I | Parcial na fidelidade instalada | Matriz hermética, concorrência, crashes e segredos exercitados; a continuação acrescenta resolução nativa e escrita YAML em home descartável, não Auto instalado. |
| 11 — runner instalado | Todos os consumidores verdes localmente, aceite instalado incompleto | C1/C2/C3/C4/C5/C6/C7/C10 e fallback AC-22 exercitados após Auto em home descartável; dependência fixada e metadados locais; nenhuma execução Docker. |
| 12 — documentação | Feito localmente | Operação S3, testes, compatibilidade, README, índice, histórico e este registro; aceite e revisão de implementação pendentes. |

## Discrepâncias do host

O backend de arquivo não conserva null explícito em `Changes.set(None)`, apesar da documentação da classe; `utils.atomic_roundtrip_yaml_update` remove a chave.
A implementação bloqueia somente os grupos cuja presença não conseguiria restaurar exatamente e explica os nomes dos campos.
O leitor `get_session` chama `flush_for_read` e pode devolver campos privados; `get_session_model_config_value` usa o `model_config` atual e mutável.
Não foi qualificado um leitor nativo de criação/imutabilidade/tipo de mãe; usa-se o fallback expressamente permitido, sem ler o banco real.
O hook nativo de erro traz um dict `error={type, message}`; somente a classe entra no registro.
O Python limpo não tem `ruamel`; isso limita a prova de integração inferior e não justifica mudar o guard ou expor o leitor de contas.

## Pendências e próximo passo

As pendências estão preservadas no README como HQR-26, HQR-27 e HQR-28.
C4/C10 foram resolvidos localmente na segunda continuação; falta revisar independentemente o candidato e repetir a qualificação no alvo instalado.
O gate agora consulta o catálogo nativo models.dev, não o piso estático curado; a continuação abaixo registra o comportamento offline e os testes.
Conferir os IDs do mapa no alvo instalado continua necessário: os probes anteriores injetaram catálogo desconhecido e não qualificam elegibilidade de conta.
Qualificar uma entrada própria do host Docker e executar o runner somente com autorização.
Publicação de candidato limpo, instalação, rollout, rollback real e piloto no Hermes de trabalho continuam pendentes de autorização específica.
Não chamar esta entrega local de Auto instalado ou de aceite da S3.

## Continuação — probes nativos locais (2026-11-16)

A continuação conferiu a branch e o HEAD `59f796a7ffbd1d12e233646ee853197df58e019f` antes de editar.
Os RED desta continuação são `60ecdd4`, `4e291eb`, `9255692`, `d8beb11`, `922018d` e `964e6ae`; `ab0a975` e `c757ca8` registram os GREEN.
Os comandos focados foram `python3 scripts/run_tests.py tests.harness.test_s3_native_<probes|execution|absence|boundaries|memory|io>`, um módulo por ciclo.
Os arquivos anteriores e os novos testes de cada RED foram preservados depois de seus commits.

`tests/installed/s3_auto.py` embarca `s3_native_consumers.py` no processo do Python do alvo por `Run.json`, sem depender de o plugin instalado exportar um endpoint de teste.
Ele captura as políticas anteriores antes de `mode auto`, resolve depois da aplicação e conserva o gate final por cenário.
Os probes importam e chamam funções do host efetivamente carregado, guardam caminho relativo, linha e SHA-256 da fonte e recusam seam ausente ou fonte fora do host.
`stop_at_call` interrompe uma chamada nativa antes de identidade/publicação ou autenticação e não devolve resposta fabricada para o chamador.
O escopo provado é resolução de configuração/política, não publicação completa de sessão, inicialização de agente, transporte ou inferência.
O guard recusa rede, subprocessos que não sejam os workers exatos, credenciais, configuração/DB externos e mutações fora do home descartável.
Uma tentativa de abrir credencial ausente em raiz admitida recebe `FileNotFoundError` antes do open, depois de conferir a ausência; arquivo existente continua recusado.
`HERMES_DISABLE_LAZY_INSTALLS=1` desliga a preparação automática nativa de dependências somente no processo de prova.

| Cenário | Função/fronteira nativa | Resultado local |
|---|---|---|
| C1/C2 | `stage_local_session` até a política capturada, `LocalSessionPolicy.effective`, resolução nativa de modelo/provider/esforço | Política nova: Anthropic/Opus/high; anterior: Codex/Sol/low. |
| C3 | Política `follow_profile_config` criada antes e `effective` depois | Resolve Anthropic/Opus/high na próxima leitura. |
| C4 | `_load_config`, `_active_provider`, `_declared_parameters`, `_route_one`, `_child_reasoning` | Gate daquele home descartável: `model_map` indisponível sem carregar advanced-delegation; não se substitui por leitura manual das opções. |
| C5/C6 | `_worker_config`, `_bind_worker_config`, `load_config_readonly` e leitor de delegação, em processos reais | Worker já aberto e worker novo da política anterior conservam Codex/Sol/low e delegação congelada; política posterior resolve Anthropic/Opus/high; status marca sessões gerenciadas anteriores fora da cobertura. |
| C7 | `_load_cron_job_config`, `_resolve_job_runtime` até a chamada de runtime, `resolve_requested_provider`, `_resolve_job_reasoning_config` | Cinco controles: conversa, padrão completo, override low diferente da conversa high, só modelo e só provider; valores, origens e marca parcial conferem com o status. |
| C10 | Parser e `switch_model` antes de catálogo/credenciais; `_resolve_child_runtime` | Escolha explícita Terra/Codex chega à fronteira; construção explícita do filho resolve Terra/Codex/low; commit da escolha na sessão e chamada explícita no backend continuam sem prova e mantêm gate falhando. |
| AC-22 | `SessionDB` descartável, `create_session`, `get_session`, `update_session_model`, fonte de criação e entrega | Fonte não qualificada; fallback real do produto retorna somente `geração indeterminada`, sem idade. |

### Evidência do probe local, não instalada

O ensaio local executou o mesmo `NATIVE_BOOTSTRAP` que o runner envia ao alvo, com o Python nativo `3.14.9` e as fontes locais originais.
Ele preparou configuração sintética, conservou políticas/workers anteriores, mudou a configuração por `Changes` nativo e chamou `ConsumerProbe.after` com `Management.status` real em Observe e leitor de cota inerte.
Essa escrita de controle não foi uma aplicação do motor Auto, uma instalação ou uma qualificação do destino Docker.
A prova instalada permanece depois de uma aplicação real de Auto no runner, ainda não executado.

Comando executado, com variáveis que expandem os mesmos caminhos locais, a partir da raiz da worktree:

```sh
# PY, DRIVER, SRC e PROBE_HOME são entradas explícitas do ambiente de teste isolado.
env -i PATH=/usr/bin:/bin HOME="$PROBE_HOME" HERMES_HOME="$PROBE_HOME" TMPDIR="$PROBE_HOME" HERMES_DISABLE_LAZY_INSTALLS=1 "$PY" -I -B "$DRIVER" "$PWD" "$SRC" "$PROBE_HOME"
```

Saída observada: `C1=true, C2=true, C3=true, C4=false, C5=true, C6=true, C7=true, C10=false, AC-22=true`, `audit_denied=[]`, 31 fontes nativas identificadas e exit 1 do gate de aceite.
O stderr contém `EXPECTED LOCAL ACCEPTANCE GATE: C4: native model_map backend unavailable; no child route can be proved; C10: native /model requires metadata/auth before session commit; explicit subagent construction verified, not explicit backend call`.
SHA-256 do driver: `92c49183bb1a7000db4907c875cece89242158b77cbaad4a591fb7df9e9ef521`.
O resultado sanitizado desse ensaio está resumido acima; o registro bruto não integra a distribuição.
Homes e bancos sintéticos são removidos ao fim do ensaio; somente os resultados resumidos são distribuídos.
Tentativas preliminares registraram recusas do guard antes de bootstrap, dotenv/catálogo remoto e SQLite em memória; não foram contadas como sucesso.
Uma tentativa com cópia de fontes não qualificou as funções carregadas `FileBackend.write_path/read_path` e não foi usada como prova de Auto.
A execução final usou as fontes originais, não aquela cópia, e não abriu credenciais nem configuração/DB reais.

### Veredito AC-22 e limites restantes

`started_at` permaneceu igual após a troca nativa, mas `get_session().model_config` mudou; o leitor devolve a linha atual, não uma cópia imutável da criação.
A fonte mostra leitura da configuração → construção da política → relógio; `commit_local_session` não inclui `model_config` no INSERT local observado.
O resultado é `qualified=false`, com `model_config_mutable`, `creation_model_config_reader_not_qualified` e `local_creation_does_not_insert_model_config`.
O fallback foi exercitado para hook atrasado A₁ → B → A₂, captura dentro da janela, troca de modelo e mãe desconhecida; todos retornaram exatamente `{"state": "geração indeterminada"}`.
`AC-22=true` no recibo significa prova desse fallback aceito, nunca qualificação positiva da fonte nem prova de idade por tarefa.
Naquela execução, C4 e C10 continuavam em HQR-26 e o gate final falhava; a continuação abaixo registra a resolução local posterior, sem transformar esse recibo antigo em sucesso.
Nenhuma impressão digital nova do Docker, revisão independente, publicação, instalação, restart ou inferência foi executada.

### Gates da continuação

`python3 scripts/run_tests.py` retornou `Ran 127 tests in 0.926s`, `Ran 9 tests in 1.593s` e `Ran 38 tests in 0.123s`, todos `OK`, exit 0, sem skips.
São 174 testes herméticos, incluindo 16 novos testes do harness.
O diff `git diff --diff-filter=MDR f7f3136 -- tests` conserva somente a linha D14 de `tests/integration/test_export.py`; os testes preexistentes do runner permanecem intactos.
Os gates de compilação, linhas, OKF, whitespace, CodeGraph e Gitleaks são repetidos antes do commit documental final.
A execução de `compileall` retornou exit 0 e o gate de linhas retornou `[]`.
O OKF fixado retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete`, sem diagnósticos e com a raiz física desta worktree.
`git diff --check` retornou exit 0.
`codegraph sync .`, com `CODEGRAPH_NO_DOWNLOAD=1 CODEGRAPH_NO_UPDATE_CHECK=1 CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1`, retornou `Synced 8 changed files`; `codegraph status .` confirmou a raiz e `Index is up to date`.
O CodeGraph também avisou que o índice foi criado por uma versão anterior; não houve reconstrução completa ou download, e esse aviso não foi ocultado como prova de upgrade do índice.
Os scanners staged dos commits desta continuação retornaram exit 0, sem leaks; nenhuma regra foi desabilitada.

## Continuação — C4/C10 fechados localmente (2026-11-16)

Esta continuação conferiu branch `hermes/2026-11-16-hqr-s3`, árvore limpa e HEAD `e885f5fc1bfa0827097de2eafae8bc1b87b8c0e5` antes de editar.
A rede permaneceu limitada ao stub próprio em `127.0.0.1`; não houve Docker, publicação, push, merge, restart, launcher real ou inferência.
O remoto foi apenas identificado; não houve fetch, pois a autorização proíbe rede externa e fixa a base local.
A configuração real, o banco real de sessões e arquivos de credenciais não foram abertos ou copiados.

### Dependência e compatibilidade

O backend `model_map` não pertence ao core: vem do plugin oficial `advanced-delegation`, versão `1.1.0`.
Seu `plugin.yaml` e `.hermes-catalog.json`, lidos somente como fonte, fixam repositório `NousResearch/hermes-official-plugins`, subdiretório `advanced-delegation` e ref `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`.
O runner local copiou a árvore da dependência para `plugins/advanced-delegation` do home descartável, recusou symlinks e nomes de credenciais, conferiu hashes e tornou a cópia somente leitura antes de carregar.
A configuração sintética habilitou a dependência pela allowlist nativa `plugins.enabled`; `discover_plugins` e o registro nativo forneceram o provider, sem instanciá-lo manualmente nem interpretar opções para decidir a rota.
O runner Docker agora exige OFF efetivo antes da dependência, faz install com `--ref` completo e `--no-enable`, enable e readback nativo de versão, registro e `pinned_revision`, antes da qualificação do candidato.
Nenhuma dessas etapas Docker foi executada.

`qualified_hosts.json` conserva o mesmo host/revisão e passa de 44 para 61 funções, ainda com três constantes.
As 17 adições cobrem `_child_reasoning`, os cinco resolvers de `tools.delegate_tool_routes`, quatro funções do registro nativo, `DelegationProvider.settings` e seis funções do `model_map.py` externo.
Os hashes foram calculados por leitura dos arquivos originais de core e da dependência; fontes de outro home não recebem a prova do namespace bare.
Dois hashes anteriores, `FileBackend.read_path` e `FileBackend.write_path`, foram corrigidos para incluir o decorador `@staticmethod`, após RED demonstrar diferença entre inspeção inerte e objeto carregado.
Isso corrige a captura do fingerprint, não altera nem normaliza os bytes do host.
Ausência, disable ou indisponibilidade da dependência aparecem no status JSON e em texto; em Auto as rotas ficam `backend_unavailable`, sem escrita na aplicação, recuperação ou OFF.
Observe conserva propostas hipotéticas, sempre separadas da disponibilidade real.

### Prova nativa local

A preparação local usou o código versionado e o ambiente de teste isolado descritos abaixo.
O preparador chamou o Python nativo `3.14.9` diretamente, com `-I -B`, ambiente limpo, `HOME/HERMES_HOME/TMPDIR` descartáveis e lazy installs desligados.
O driver carregou o mesmo `NATIVE_BOOTSTRAP` embarcado no runner instalado.
O motor Auto e `Changes`/persistência YAML eram reais; contexto de gestão, cotas e catálogo desconhecido eram injeções declaradas, não uma instalação do quota-router.
O catálogo estático local rejeitou IDs do mapa aprovado antes da injeção; a elegibilidade real e a grafia/canonicalização desses IDs devem ser conferidas no alvo, sem interpretar esta prova como validação do catálogo ou da conta.

Resumo extraído programaticamente do recibo:

```text
C1=true, C2=true, C3=true, C4=true, C5=true, C6=true, C7=true, C10=true, AC-22=true
audit_denied=[]
sources=42
exit=0
throwaway_home_removed=True
```

C4 passou para a mãe comum anterior, ainda Codex/Sol/low, e para a nova, Anthropic/Opus/high: ambas as delegações por `option=general` resolveram Anthropic/Opus/medium pelo plugin e código nativo.
C5/C6 conservaram a prova de snapshot dos workers gerenciados.
C10 completou `switch_model` com provider custom sem credencial, persistiu hqr-explicit na sessão descartável por `_persist_model_switch_to_session` e releu por `stored_session_route`, apesar do padrão Anthropic/Opus do profile.
O backend de subagentes recebeu `option=explicit` por `resolve_task_routes`, retornando custom/hqr-explicit/low.
A chamada nativa `delegate_task(credentials_cfg=...)` também preservou o modelo explícito até a fronteira `_build_children`, interrompida antes de construir agente ou inferir.
`credentials_cfg` é de chamadores internos confiáveis; o tool model-facing oferece a rota nomeada `option`, não um parâmetro bruto `model`.
A seleção da sessão não mudou `model` no profile; o stub respondeu somente GET de `/models-dev.json` e `/v1/models`, com metadados sintéticos identificados.
A prova cobre resolução, persistência/retomada e despacho pré-construção, não uma interação integral com a interface ou uma chamada real a provedor.

Depois dos cenários, o controle nativo de dependência desabilitada retornou `subagents.ok=false`, `route_state=backend_unavailable` e `delegation_unchanged_on_apply_and_off=true`.
O OFF permaneceu efetivo e não tentou restaurar subagentes enquanto a dependência estava desabilitada.
O guard recusa qualquer outro destino, método ou caminho HTTP; o bind de capacidade IPv6 de urllib3 recebe `OSError` antes de ocorrer.
O único subprocesso extra é a leitura `git rev-parse HEAD` na raiz exata do core para a checagem de versão, sem fetch, locks opcionais ou prompts.

Recibos JSON, stderr e inventário da execução foram preservados privadamente, sem publicar sua localização.
Os ambientes e bancos sintéticos de todas as tentativas foram removidos depois da verificação dos resultados.
O roteiro reproduzível está em `tests/installed/s3_native_consumers.py`; um preparador operacional não integra a distribuição.
O resultado público desse ensaio é o resumo sanitizado desta seção.
As tentativas anteriores ficam como diagnóstico: bind IPv6 bloqueado, fingerprint de método estático incoerente, consulta Git de versão bloqueada e uso incorreto de tuple de resume no probe; não foram contadas como aceite.

### Testes e pendências

Os RED novos são `4658d6c` (dependência), `7a24a70` (probes/pin), `954d604` (staticmethod) e `5efcca5` (namespace/status), seguidos dos GREEN `45acf3c`, `4b4a300`, `a591cf5` e `7b87155`.
Os comandos focados foram `python3 scripts/run_tests.py tests.unit.test_s3_delegation_dependency`, `tests.harness.test_s3_advanced_proofs`, `tests.unit.test_s3_static_fingerprint` e `tests.unit.test_s3_delegation_runtime`, um módulo por ciclo.
Esses ciclos acrescentam testes, sem mudar os protegidos.
A regressão após o probe retornou `Ran 134 tests in 1.032s`, `Ran 9 tests in 1.629s` e `Ran 44 tests in 0.130s`, todos `OK`, exit 0 e sem skips: 187 testes.
Os resultados dos testes estão resumidos nesta seção.
O diff de testes preexistentes contra `f7f3136` continua contendo somente a substituição D14 de `tests/integration/test_export.py:23`.
Nenhum teste anterior desta continuação foi enfraquecido; o teste de status parcial observou também um `KeyError` no RED antes de a renderização aceitar um diagnóstico somente de dependência.
A repetição final de `python3 scripts/run_tests.py` retornou 134/9/44 testes, todos `OK`, exit 0, sem skips.
`compileall` retornou exit 0 e o gate de linhas retornou `[]`; `git diff --check` passou na árvore e contra `f7f3136`.
O OKF fixado retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]`, na raiz física correta.
CodeGraph 1.6.2 sincronizou 11 arquivos com downloads, telemetria e update-check desligados; raiz própria e 75 arquivos indexados conferiram exatamente com o conjunto versionado Python/YAML, sem faltantes ou extras.
O status ainda recomenda reindexação pelo formato anterior do índice; não houve rebuild nem download, e esse limite permanece explícito.
Os scans Gitleaks staged anteriores passaram sem leaks; o commit documental mantém o mesmo gate obrigatório e nenhuma regra foi desabilitada.
A revisão independente de implementação continua pendente e não foi substituída por auto-revisão; esta autorização não permite inferência para chamar um revisor.
HQR-26 permanece aberto para catálogo/mapa real, qualificação e ensaio Docker, revisão, publicação autorizada e aceite da S3.
C4/C10 estão fechados apenas no escopo local documentado; o fallback AC-22 continua sendo fonte não qualificada, nunca uma geração/idade nativa positiva.

## Continuação — catálogo nativo models.dev (2026-11-16)

A correção partiu de árvore limpa no HEAD `4bfb4d0e2f8cdd75ce18dd2f06980482744dd5e3`, na mesma branch/worktree autorizada.
O remoto foi identificado, sem fetch: esta continuação proíbe rede e preserva a base local fixada.
Não houve instalação, Docker, restart, inferência, publicação, leitura de configuração/auth/tokens ou acesso ao banco real de sessões.

`quota_router/mapping.py` deixou de usar o piso curado `_PROVIDER_MODELS` como gate.
O adaptador lê primeiro `_models_dev_cache` de `agent.models_dev` já carregado, sem I/O; sem memória utilizável lê o JSON do cache sem chamar os loaders mutantes.
O mapa de providers pertence ao host: `PROVIDER_TO_MODELS_DEV` liga `openai-codex` a `openai`, sem renomear IDs de modelo.
Catálogo/provider indisponível, vazio ou ilegível resulta em desconhecido e não bloqueia o papel; status/explain, em texto e JSON, informam `IDs não verificados`.
ID ausente de um catálogo legível e não vazio impede o papel inteiro, com `model_absent_from_catalog` e providers faltantes, sem substituição silenciosa.
O piso curado nunca bloqueia e não é usado como fallback.
O catálogo não comprova disponibilidade na conta nem billing.

A revisão identificou mutações no leitor offline nativo; esse caminho foi removido do plugin.
O plugin agora usa memória carregada ou leitura JSON direta, sem alterar cache ou ETag, e falhas tornam o catálogo desconhecido.
Nesta continuação somente as fontes originais do leitor foram inspecionadas: não se chamou o leitor real nem se modificou o cache do Hermes de trabalho.
`compat.py` e `qualified_hosts.json` acrescentam o leitor, nove helpers offline e o mapa de providers: 71 funções e quatro constantes, sem divergências na comparação por fonte.
O host Docker continua sem entrada qualificada.

### RED/GREEN e proteção

RED `e8d3fd8` mostrou duas falhas: IDs adicionais ausentes no resultado e papéis routine/triage/extract indevidamente bloqueados pelo piso curado.
GREEN `05cc83c` passou os cinco testes focados com memória models.dev.
RED `74f68cc` mostrou duas falhas de IDs não carregados sem memória; GREEN `85b1e07` passou os nove testes focados com o leitor offline.
RED `395ce6a` mostrou cinco falhas de asserção em 12 métodos, incluindo três subcasos de aviso desconhecido e a ausência do fingerprint; GREEN `a4a4e3d` passou os 12 métodos.
O comando em todos os ciclos foi `python3 scripts/run_tests.py tests.unit.test_s3_edges`.
As primeiras tentativas do segundo RED deram `KeyError` ao indexar o resultado vazio; antes do commit RED, o teste passou a consultar `.get(..., [])` e observou falhas de asserção dos mesmos IDs ausentes.

A clarificação do coordenador limita os protegidos aos arquivos S1 enumerados no mandato.
`tests/unit/test_s3_edges.py` é novo na S3, criado em `b9acf79` e ausente em `f7f3136`; seus dois testes de catálogo anteriores foram atualizados para a fonte e a semântica aprovadas, sem tocar nos protegidos.
A comparação com `f7f3136` conserva somente D14 em `tests/integration/test_export.py`; o diff dos protegidos entre o HEAD inicial desta continuação e o resultado é vazio.
`AGENTS.md` e `decisions/s3-plan.md` não foram editados.

### Prova e limites desta correção

`python3 scripts/run_tests.py` retornou 142 testes unitários, nove de integração e 44 de harness, todos `OK`, exit 0, sem skips.
A repetição final conservou 195 IDs únicos quando qualificados por suíte; o log integral foi preservado privadamente.
O arquivo de bordas passou de quatro para 12 métodos; os cenários cobrem memória sem I/O, loader offline, mapa nativo, catálogo vazio/ilegível/indisponível, IDs presentes/ausentes e piso curado sem poder de bloqueio.
A regressão exercita aplicação real do motor contra armazenamento sintético, inclusive os modelos Sonnet/Haiku e o candidato Terra presente no lado Codex.
A qualificação de fonte conferiu todos os 71 hashes e quatro constantes do host de trabalho sem importar seus leitores mutantes.
Compilação retornou exit 0; gate de linhas retornou `[]`; whitespace passou na árvore e contra `f7f3136`.
O OKF fixado retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]` na raiz correta.
CodeGraph 1.6.2 sincronizou cinco arquivos com downloads, telemetria e update-check desligados, sem pendências de fonte e com índice próprio nesta worktree.
A recomendação preexistente de reindexação de formato permanece, sem rebuild ou download.
O scanner Gitleaks staged de cada commit retornou exit 0, sem leaks; o commit documental repete os gates finais.
A revisão independente segue pendente: a autorização proíbe inferência e não foi contornada para chamar um crítico.
HQR-26 continua aberto para qualificação/ensaio instalado do alvo, revisão, publicação autorizada e aceite, não para restabelecer o gate curado removido.

## Pins OKF

Pacote preservado: `/usr/local/lib/okf/0.3.0`.
Router físico: `/usr/local/lib/okf/0.3.0/skills/okf/SKILL.md`.
SHA-256 do router: `e1f5be06b7f8a69fe7407aff97bde1cfd4d6767a65b974ff3bc1e958cb054b42`.
`SHA256SUMS` do pacote conferiu e `runtime-capabilities` retornou `okf-runtime-v1`.
A validação é estrutural/documental e não atesta a semântica da implementação ou um destino instalado.

## Revisão de implementação, rodada 1 (2026-11-16)

A correção partiu da branch conferida, árvore limpa e HEAD `b403fd1307dcbbfa16ebb1ab71ddd7e8c3886579`.
A revisão independente pediu mudanças; esta rodada registra correções e provas do executor, não um novo parecer de aprovação.
Os três logs fornecidos foram lidos integralmente; eles abreviam partes dos retornos finais, então a lista de IDs e requisitos do mandato também foi usada, sem reconstruir pareceres como se fossem texto integral recuperado.
O remoto foi somente identificado: a base local permaneceu fixada e a restrição de rede impediu fetch externo.
Não houve publicação, push, merge, instalação, Docker, restart, inferência ou leitura de configuração, credenciais ou banco de sessões reais.

### Achado → correção → prova local

Todos os itens abaixo estão corrigidos no código ou na prova local; a execução T do runner continua pendente, conforme HQR-26.
Os nomes curtos de teste referem-se aos arquivos indicados na coluna de prova.

| Achado | Commit GREEN | Correção e teste |
|---|---|---|
| G1 | `2e4e54c`, `a885736` | OFF decide pela marca/grupos duráveis e exige restauração concluída; `test_s3_review.RestoreReviewTests.test_off_after_suspended_reload_requires_proven_restoration`, com host incompatível e settings inválidos; `test_off_refuses_unreadable_retained_directory_even_when_stat_hides_state` também recusa OFF quando o diretório não pode ser inspecionado. |
| G2 | `e9ba091`, `8bfd5c4` | Preserva preferência somente após escrita própria confirmada e remove chaves obsoletas; `HysteresisReviewTests.test_auto_keeps_preference_across_own_writes_and_repeated_small_inversions` e `test_auto_drops_preferences_for_removed_roles`. |
| G3 | `3efeb3a`, `59e60c7` | Qualifica `ROUTE_FIELDS`, `BACKEND`, `SETTINGS_PATH`, `PARAMETER` e `DAYBREAK_KEY` do namespace ativo; `test_s3_fingerprint_review.test_active_scoped_route_constant_drift_suspends_cycle_recovery_and_off`, sem escrita nos três caminhos. |
| G4 | `18a45c6`, `39e7578` | Worker usa cópia do contexto dono; `WorkerContextReviewTests.test_worker_uses_owner_context_not_process_default_home` e `NativeReviewTests.test_native_worker_keeps_default_home_when_process_has_another_home`. |
| G5 | `d12c2f2` | Parser/resolver nativos decidem precedência de aliases; `CronReviewTests.test_cron_uses_native_parser_and_ordered_alias_resolver` e `NativeReviewTests.test_native_parser_competing_alias_order_matches_status`, nas duas ordens. |
| G6 | `c6eaf94` | Memória nativa ou JSON aberto somente para leitura pelo caminho nativo; `CatalogReviewTests.test_corrupt_catalog_and_etag_are_untouched_and_mutating_loaders_never_called`; nenhum loader mutante é chamado. |
| G7 | `71eb57c` | Recusa aliases compartilhados antes de toda mutação; `AliasReviewTests.test_shared_nodes_across_group_boundary_refuse_all_write_paths` e `NativeYamlAliasTests.test_native_yaml_alias_refuses_without_changes_and_isolated_control_restores`, com YAML real. |
| G8 (rodada 2) | `7cbf8e9` | Migra a preferência de Observe para Auto somente com settings, par candidato e rota atual idênticos; `test_s3_mode_continuity.ModeContinuityTests` compara a decisão exibida com a projeção aplicada abaixo da histerese, preserva escritas próprias confirmadas e invalida após edição externa ou mudança de settings. |
| SEC-S3-01 | `6fe14d8`, `7566ca8` | Armazenamento por descritores, dono/permissões, `O_NOFOLLOW`, arquivos regulares e publicação atômica; os cinco métodos de `test_s3_storage_review.StorageReviewTests`. |
| SEC-S3-02 | `c6eaf94` | Mesmo tratamento de G6; snapshot sintético confirma cache corrupto e ETag intactos, sem rede nem reparo nativo. |
| SEC-S3-03 | `a1f6bd7`, `f385234` | Remove localizações privadas; host exige revisão Git e conjunto completo de fingerprints, sem subprocesso; `test_host_binding_uses_revision_and_fingerprints_not_private_location` e `test_host_revision_reads_git_metadata_without_spawning_a_process`, além do grep final. |
| SEC-S3-04 | `ae6138f` | Revalida identidade, labels, volume, opções, caps, privilégios e namespaces antes das mutações; `AdmissionReviewTests.test_negative_isolation_controls_stop_before_any_install`, nove controles herméticos. |
| SEC-S3-05 | `3efeb3a` | Extrai blocos por AST/linhas sem executar defaults/decoradores/anotações; `test_inert_inspection_never_executes_default_expression`, com sentinela. |
| SEC-S3-06 | `6b84860` | Exige manifesto revisado, bytes exatos, ausência de links/especiais e scanner seguro antes de enable; `test_dependency_rejected_before_enable_on_tree_or_scan_failure` e `test_dependency_inventory_checks_real_bytes_and_symlinks`. |
| TE-01 | `aa9f25b`, `440c697` | Gate inclui C8/C9/C12/E2; pins completos/parciais, créditos disponíveis mas desligados em A5, D3 exato, recuperação completa, ausência preservada e recusa de remoção; `test_review_gate_includes_jobs_error_and_removal_proofs`, `test_product_removal_refuses_declared_auto_without_native_remove_call`, `test_absence_projection_ignores_only_native_lifecycle_lists` e prova nativa de pins. |
| TE-02 | `7e6ccb4` | Apply/restore com esforço distinto e endpoint/modo vazios presentes, quedas por chave e edições pós-queda; `ProcessTests.test_apply_and_restore_crashes_check_full_projection_and_state` e `test_post_crash_prior_and_third_edits_are_preserved`. |
| TE-03 | `af8fe17` | Releitura divergente interrompe o ciclo antes de perder o primeiro diário; `JournalReviewTests.test_divergent_reread_stops_two_group_cycle_and_preserves_intention`, para aplicação e restauração com dois grupos. |
| TE-04 | `7e6ccb4` | Toggles por comandos de gestão em Auto, projeção completa por cenário e A13 abaixo/no/acima do limite; `ScenarioTests.test_management_consumer_toggles_restore_independently_and_reenroll` e `test_a13_returns_conversation_to_principal_and_cron_toggle_has_no_write_group`. |
| TE-05 | `7e6ccb4` | Relê a opção persistida, não uma referência antiga; `ScenarioTests.test_native_option_fallback_edits_survive_apply_and_off` e asserção reforçada em `test_s3_apply`. |
| TE-06 (rodada 2; complemento de TE-01) | `8b5fca8` | C12 exige sessão sintética única, hash salgado ausente no snapshot anterior, registro novo no watermark da emissão e campos fechados sem dados privados; `test_s3_c12_correlation.C12CorrelationTests` recusa histórico antigo com entrega inerte, correlação alheia e timestamp anterior, mas aceita a entrega nova mesmo com 128 registros retidos. |

Os commits RED estão preservados na branch, com os comandos focados executados antes das correções.
Para TE-02/04/05, o RED de `test_s3_coverage_review` mostra a ausência dos pontos de prova; os novos testes de integração depois executam os cenários, sem alegar um defeito antigo do motor que não foi observado.
Os extras TE usam sincronização explícita, encerramento dos managers novos, controle de corpo com mesmo nome/assinatura ligado ao contador de escritas e prova de latch mantido até reload.
A remoção nativa continua sem interceptação: E2 é imposto pelo fluxo `product_remove` e pelo procedimento do piloto, não por uma promessa de veto do core.
O runner agora exige `--advanced-manifest`; preparar esse manifesto a partir da revisão pública fixada é uma precondição do futuro ensaio, não um arquivo inventado nesta rodada.

### Provas e limites da rodada

`python3 scripts/run_tests.py` retornou 163 testes unitários, 13 de integração e 53 de harness, todos `OK`, exit 0, sem skips.
A contagem reconciliou 229 IDs únicos por suíte com os três resumos do runner, sem duplicatas.
A repetição separada dos 13 testes I com `HQR_NATIVE_SOURCE` usou `config_backend.py` original e primitiva JSON sintética, mantendo o leitor de contas não importável.
Os dois módulos nativos separados retornaram 1 e 3 testes verdes com Python 3.14.9 e ruamel já disponíveis, sem instalação; cada execução teve home próprio removido ao fim.
A inspeção inerte conferiu 71 funções e nove constantes contra as fontes fixadas; a revisão Git também conferiu, sem abrir arquivos de configuração ou dados reais.
A primeira tentativa separada de discovery I teve conflito entre dois módulos homônimos do guard no `PYTHONPATH`; corrigida somente a ordem dos caminhos na invocação, os 13 testes passaram.
Duas tentativas de localizar o Python por caminhos históricos inexistentes falharam; o interpretador efetivo foi descoberto pelo runtime, sem invocar launcher nem instalar nada.
Os gates executados retornaram: `compileall` exit 0, compilação dos cinco scripts embarcados válida, gate de linhas `[]`, OKF oficial `conformant`/perfil `pass`/navegação `valid`/cobertura `complete` e `diagnostics=[]`.
`git diff --check` e o check staged passaram após remover uma linha vazia adicional no fim deste registro.
O grep obrigatório retornou exit 1 sem ocorrências; o scan de todos os 44 arquivos acrescentados na S3 também ficou sem ocorrências novas.
O scan geral conservou 30 ocorrências antigas em oito arquivos S1/S2, sem alterar seus bytes.
CodeGraph 1.6.2 sincronizou a raiz própria, e os 83 caminhos Python/YAML indexados conferiram exatamente com o conjunto versionado, sem extras nem faltantes.
A recomendação preexistente de reindexar o formato permanece; não houve rebuild, download, telemetria ou update-check.
O pós-processamento inicial dessa comparação teve `NameError` por import ausente de JSON; corrigido somente o script de análise, a comparação exata passou.
O pin do router OKF permaneceu igual ao SHA-256 já registrado.
Gitleaks foi executado no stage antes de cada commit, sem desabilitar regras; o commit final repete esse gate.

Nenhum arquivo protegido desta rodada foi alterado; contra `f7f3136`, permanece somente a substituição D14 já aprovada em `tests/integration/test_export.py:23`.
`AGENTS.md`, `decisions/s3-plan.md` e a seção 17 da emenda foram preservados.
As ocorrências antigas de caminhos absolutos em arquivos S1/S2 foram reportadas, não reescritas; nenhuma ocorrência nova permanece nos arquivos S3.
HQR-26 continua aberto para rechecagem independente, manifesto da dependência, qualificação Docker, ensaio instalado e autorizações de publicação/piloto.
Não foi identificada necessidade de mudar o contrato aprovado; permissões inseguras ou fonte não qualificada usam recusa segura.

## Revisão de implementação, rodada 2 (2026-11-16)

G8 e TE-06 foram corrigidos e exercitados localmente; a rechecagem independente e o ensaio instalado continuam pendentes.
A rodada partiu de árvore limpa no HEAD `133bbadfe6ac69c06e3be76cbb5a9fa76d35b9da`, na mesma branch e worktree autorizadas.
Os finais dos logs fornecidos para G8 e TE-06 contêm trechos abreviados; os requisitos integrais do mandato orientaram as regressões, sem apresentar esses logs como pareceres completos.
O remoto foi apenas identificado, sem fetch, pois o mandato proíbe rede e fixa a base local.
Não houve publicação, push, merge, instalação, Docker, restart, inferência ou leitura de configuração, credenciais ou banco de sessões reais.

### RED/GREEN e escopo da prova

- G8: RED `2411b45c6fe5ab32bd496e004b08bcbd402d3864`, GREEN `7cbf8e9a5a11f9b918888a066ae284ecd12cae44`.
- TE-06: RED `dd254f2ecc83b4edea9d2aa778b65d36b159270a`, GREEN `8b5fca8ab76934379e3c5b52e4cae8597fba3e56`.
- Comandos RED: `python3 scripts/run_tests.py tests.unit.test_s3_mode_continuity` e `python3 scripts/run_tests.py tests.harness.test_s3_c12_correlation`.

G8 apresentou duas falhas de subcaso no primeiro método: Observe manteve Anthropic em 30/10 → 5/10, mas Auto escolheu Codex nas políticas `principal_first` e `pacing`.
Os três métodos novos agora passam e comparam a projeção fechada de conversa/general com a decisão anterior, inclusive esforço, ausência de escrita em Observe, aplicações repetidas e restauração por OFF.
Os controles mantêm a invalidação após mudança de settings ou rota externa e impedem sobrescrita do grupo divergente depois de escrita própria confirmada.
A migração conserva a identidade específica de rota de Observe e a identidade estável de Auto, sem mudar a semântica histórica da S2.

TE-06 apresentou oito falhas de asserção em cinco métodos: entrega inerte, registro alheio ou anterior ao watermark podiam satisfazer C12 pelo histórico, e as emissões reutilizavam a mesma sessão.
Os cinco métodos agora passam, executando por AST a função `quota_error` exata embarcada em `EXERCISE`, com `Engine`, `HookWorker` e armazenamento reais em diretório sintético.
Somente a entrega nativa é substituída por um emissor inerte ou pelo callback real do worker; nenhuma fonte, configuração ou sessão real do Hermes é carregada.
O controle positivo cobre histórico vazio, um registro e retenção cheia de 128 registros, além de duas emissões consecutivas com hashes distintos.
O recibo conserva somente hash salgado e timestamps da emissão e do registro; ID bruto e mensagem privada sintética não aparecem no histórico.
Essa prova qualifica a asserção de C12 no harness, não a entrega instalada do hook.

### Gates e proteção

`python3 scripts/run_tests.py` retornou 166 testes unitários, 13 de integração e 58 de harness, todos `OK`, exit 0 e sem skips.
O resultado da revisão independente, rodada 2, foi reconciliado com 237 IDs únicos por suíte, sem duplicatas; são oito métodos novos, três U e cinco de harness.
Os diagnósticos de argparse e `FAIL 01 broken` são saídas esperadas dos controles negativos preexistentes, não falhas das suítes.
A primeira execução RED de G8 importava também a classe de fixture e descobriu quatro métodos duplicados; a importação foi trocada por módulo antes do commit RED, cuja execução registrada contém somente os três métodos novos.
O primeiro controle de timestamp de TE-06 também disparava a guarda de mensagem privada; antes do commit RED foi corrigido para usar o callback real com relógio anterior, e a execução registrada mostrou a falha específica de watermark.

`compileall` de produto, scripts e testes retornou exit 0 com cache externo removido; os cinco scripts embarcados também compilaram.
O gate de linhas retornou `[]`, e `git diff --check` passou na árvore e contra `f7f3136`.
CodeGraph 1.6.2 sincronizou quatro arquivos e confirmou exatamente 85 caminhos Python/YAML versionados na raiz própria, sem extras, faltantes ou alterações pendentes, com downloads, telemetria e update-check desligados.
A recomendação preexistente de reindexar o formato permanece, sem rebuild ou download.
O pin do router OKF e `SHA256SUMS` do pacote permaneceram válidos; a validação retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]` na raiz física correta.
A primeira conferência de whitespace encontrou uma linha vazia extra no fim deste registro, removida antes da repetição final dos gates.
Gitleaks passou no stage antes de cada commit RED/GREEN, sem leaks nem regra desabilitada; o commit documental repete o scan.

Nenhum arquivo protegido foi alterado nesta rodada, inclusive `AGENTS.md` e `decisions/s3-plan.md`.
Contra `f7f3136`, o diff protegido conserva somente D14 em `tests/integration/test_export.py:23`, já aprovado e anterior a esta rodada.
Os novos testes permanecem idênticos aos respectivos commits RED.
HQR-26 conserva os próximos passos de rechecagem independente, qualificação Docker, ensaio instalado e autorizações de publicação/piloto; a correção local não fecha esses gates.

## Revisão independente da implementação

Três revisores independentes (geral, segurança e testes) revisaram `f7f3136..b403fd1` e pediram mudanças: G1 a G7, SEC-S3-01 a SEC-S3-06 e TE-01 a TE-05 (revisão independente, rodada 1).
A rodada de correção terminou em `133bbad`; a rechecagem aprovou segurança e encontrou G8 e TE-06 (revisão independente, rodada 2).
A segunda rodada terminou em `f7c5a96`; a rechecagem geral e a de testes aprovaram, sem bloqueantes (revisão independente, rodada 3).
Resultado: os três revisores aprovam `f7c5a96` como código local; a aprovação não prova entrega instalada, qualificação Docker, publicação ou piloto.
Próximo passo: com autorização de Guilherme, publicar candidato limpo e rodar o ensaio instalado no alvo Docker.

## Preparação para publicação e ensaio Docker (2026-11-16)

A preparação partiu da branch conferida `hermes/2026-11-16-hqr-s3`, árvore limpa e HEAD `cd42a762baaea87549e0f123bdd242117853e363`.
O fetch anônimo confirmou `origin/main=ad113d95604128fcdf9c446e2c5bd9c75bff0860`, ancestral do candidato, sem commits exclusivos do remoto.
Esta delegação executa somente a preparação: não houve push, publicação, merge, instalação, enable, configuração ou qualquer outra mutação no alvo.
O Hermes de trabalho não foi iniciado; apenas a árvore de fontes de advanced-delegation autorizada foi lida, sem configuração, auth ou sessões reais.

### Entrada Docker e bloqueio de proveniência

O alvo conferido é `hqr-s1-test`, imagem `hqr-s1-test:installed-ad3e180-run3`, label `hqr.host=3b421578588243f920886e6fe79a6faa87ea026e`.
O probe enviado por stdin ao `python3 -I -B`, com bytecode desligado e audit hook recusando escritas, rede e subprocessos, executou a inspeção inerte de `compat.py` sobre o core.
Foram obtidos 65 hashes de funções e quatro constantes do Docker; seis hashes de funções e cinco constantes da dependência vieram separadamente do checkout público fixado, por `plugin_root` explícito.
A nova entrada em `quota_router/qualified_hosts.json` contém os 71 hashes e nove constantes, revisão externa conferida e pin da dependência, sem caminhos privados.
O conjunto inteiro coincide com a entrada de trabalho já existente; entradas equivalentes não distinguem a localização do runtime.
Os testes conferem todos os símbolos exigidos, revisão exata, drift individual de cada símbolo e recusa quando faltam metadados Git.
`session_store_qualified=false` e `hooks_qualified=[]` permanecem sem promoção de cobertura instalada.

A inspeção revelou que o core empacotado não contém `.git/HEAD`: `native_revision()` falhou com `FileNotFoundError`.
O label Docker documenta a revisão externa, mas não está disponível como fonte confiável para o verificador dentro do plugin.
Portanto o alvo atual continua bloqueado por `native_source_unavailable`, mesmo depois de incluir a entrada de bytes e antes de considerar a dependência ainda ausente.
Não se criou fallback por label, variável de ambiente ou localização e não se inseriram metadados no alvo.
HQR-26 registra a preparação autorizada de proveniência necessária antes de executar o runner completo.

### Manifesto público e comparação real

O repositório público `NousResearch/hermes-official-plugins` foi obtido anonimamente em ambiente descartável e conferido no ref `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`.
`advanced-delegation/plugin.yaml` declara versão `1.1.0`; os 23 arquivos regulares foram conferidos também contra os blobs Git, todos de modo `100644`.
O manifesto `tests/installed/advanced-delegation-13b2c1c.json` usa exatamente `{"ref": SHA40, "files": {caminho_relativo: SHA256}}`, como `install_advanced()` espera.
`dependency_inventory()` sobre a árvore pública retornou `bytes_match=true`, `special=[]` e `files=23`.
Todos os 23 arquivos públicos coincidem byte a byte com a cópia de trabalho, sem ausentes ou modificados.
A árvore de trabalho inteira tem 30 arquivos e não é idêntica à pública: os sete extras são `.hermes-catalog.json` e seis `.pyc` em `__pycache__`.
Nenhum desses extras foi copiado, apagado ou admitido no manifesto; não houve links ou arquivos especiais.
O harness prova aceitação por atestação sintética válida e recusa de cópia com hash alterado antes de enable, não uma instalação real da dependência.

### RED/GREEN e admissão

- Entrada Docker: RED `d7592d2`, GREEN `22b83b4`; comando `python3 scripts/run_tests.py tests.unit.test_s3_docker_qualification`.
- Manifesto: RED `82a03df`, GREEN `94faccc`; comando `python3 scripts/run_tests.py tests.harness.test_s3_reviewed_manifest`.
- Modo somente de admissão: RED `d658598`, GREEN `b24cfc5`; comando `python3 scripts/run_tests.py tests.harness.test_s3_admission_only`.

O RED da entrada e do manifesto observou duas falhas cada por artefato ausente; o RED da flag observou três falhas porque `--admission-only` era rejeitado.
Todos passaram após os GREEN, sem editar os novos testes depois de seus commits RED.
A regressão completa retornou 168 testes unitários, 13 de integração e 63 de harness, todos `OK`, sem skips.

O runner com `--admission-only` retornou `PASS 01 admission-before-any-mutation`, exit 0, contra o container admitido.
O recibo contém `docker inspect hqr-s1-test`, `docker volume inspect hqr-s1-state-net` e `listeners.exposed=[]`, sem `exec`, probe ou comando Hermes.
Esse modo só confere política de container/volume e listeners; não qualifica revisão nativa, manifesto, publicação ou consumidores.
Os SHAs lexicais usados foram candidato `cd42a762baaea87549e0f123bdd242117853e363` e rollback `ad113d95604128fcdf9c446e2c5bd9c75bff0860`, sem consultar ou instalar essas revisões.
Os [comandos completos](../docs/testing.md#preparação-docker-e-admissão-somente-de-leitura) distinguem a admissão do ensaio instalado futuro, que ainda exige proveniência resolvida e os commits presentes no mirror público do alvo.

### Gates finais e preservação do alvo

`python3 scripts/run_tests.py` foi repetido e conciliado programaticamente: 168/13/63 testes, 244 IDs únicos por suíte, exit 0 e nenhum skip.
`compileall` de produto, scripts e testes retornou exit 0 com cache externo descartável, e o gate de linhas retornou `[]`.
O OKF fixado conservou seus pins e retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]` na raiz correta.
`git diff --check`, o check staged e o grep obrigatório de caminhos privados passaram, sem ocorrências novas.
O diff dos testes protegidos contra o HEAD inicial desta preparação é vazio; contra `f7f3136` conserva somente a linha D14 previamente aprovada de `tests/integration/test_export.py`.
`AGENTS.md`, `decisions/s3-plan.md` e os três arquivos novos de testes permanecem idênticos aos respectivos baselines protegidos/RED.
A releitura do alvo conservou exatamente o inventário de hashes do volume e os fingerprints do core; o conjunto ordenado de `docker diff` também permaneceu igual.
O check inicial de `docker diff` comparava a ordem incidental das linhas e foi corrigido no verificador do ensaio para ordenar as duas listas, sem mudar testes ou o alvo.
CodeGraph 1.6.2 sincronizou quatro arquivos com downloads, telemetria e update-check desligados; os 88 caminhos Python/YAML indexados conferiram com os versionados, sem extras, faltantes ou symlinks.
A recomendação preexistente de reindexar o formato permanece, sem rebuild ou download.
Gitleaks foi executado no stage antes de cada commit da preparação, sem leaks nem regra desabilitada; o commit documental mantém esse gate.
A preparação está registrada, mas não é aprovação de Auto instalado nem resolução do bloqueio de proveniência do core.

## Continuação — hosts sem Git e higiene pública (2026-11-16)

A qualificação de fonte agora aceita hosts sem revisão Git somente por uma entrada explicitamente marcada e pelo conjunto completo de fingerprints, incluindo advanced-delegation.
Uma revisão Git legível precisa coincidir também; nenhuma revisão legível divergente, entrada não marcada ou combinação parcial de entradas qualifica.
A entrada Docker conserva a revisão declarada, o label público de imagem e o hash do tarball da recipe, sem fabricar metadados Git no alvo.
O status separa `revision=null` de `qualified_revision` e exibe `revisão do Hermes não identificada; impressões conferem` quando a comparação completa passa.

### RED/GREEN e prova de fonte

- RED `f13f44a`: a correspondência completa sem Git era recusada por `native_source_unavailable`; GREEN `71db970` acrescentou a seleção opt-in por fingerprints completos.
- RED `a702fc3`: o status omitia a revisão desconhecida; GREEN `5d69a6d` acrescentou a informação em JSON e texto.
- RED `25be224`: faltava a marca explícita e a proveniência pública na entrada Docker; a continuação acrescentou esses dados sem mudar os hashes qualificados.

O comando focado é `python3 scripts/run_tests.py tests.unit.test_s3_revisionless`.
Seus nove métodos cobrem correspondência integral, hash alterado, drift individual em funções e constantes, revisão legível divergente, opt-in ausente/inválido, conjuntos incompletos/extras, mistura de entradas e status legível.
Os casos negativos que já passaram na primeira execução são cobertura adicional, não novos ciclos RED.

O probe de leitura carregou o código de compatibilidade em memória, inspecionou o core Docker sem importar leitores de configuração e forneceu ao verificador os fingerprints medidos mais os da dependência pública conferida separadamente.
Foram medidos 65 hashes e quatro constantes no core de `hqr-s1-test`, mais seis hashes e cinco constantes no ref público de advanced-delegation; os 23 arquivos desse ref coincidiram com o manifesto versionado.
O resultado do conjunto combinado foi `ok=true`, `reasons=[]`, `revision=null`, com a nota exigida; um hash alterado devolveu `ok=false` e nomeou a função divergente.
O audit hook recusava escrita, rede e subprocessos no alvo, não registrou tentativa proibida e o conjunto ordenado de `docker diff` permaneceu idêntico.
A dependência não está instalada no alvo: essa prova de fonte não é execução do plugin instalado, liberação de Auto nem ensaio dos consumidores.
Não houve publicação, push, merge, instalação, habilitação, mutação do alvo, acesso a configuração/auth/sessões reais ou inferência.

### Higiene, rastreabilidade e limites

Os documentos S1/S2/S3 editáveis agora usam resumos sanitizados de revisões e ensaios, sem IDs de delegação, caminhos de recibos locais, referências operacionais externas ou a leitura numérica de cota de uma conta real.
Os 17 módulos de produto receberam referências de origem no topo e junto às regras não óbvias, incluindo recuperação, janela de 60 s, catálogo, cron, precondições e qualificação.
A comparação de AST dos 17 módulos com `5d69a6d` foi idêntica: os comentários de rastreabilidade não mudam comportamento.
O README agora orienta agentes e desenvolvedores aos índices, contratos, planos, entregas, operação, backlog e gates.

O inventário contém 122 arquivos: 18 de código/dados de qualificação, 74 de testes/ferramentas de teste, 13 de documentação/pesquisa pública, 12 registros de decisão, quatro de empacotamento/licença/configuração documental e uma instrução para agentes.
Não há arquivo de recibo bruto ou transcrição a mover; os trechos operacionais dos registros editáveis foram reduzidos a resumos sanitizados.
Os dois runners de piloto S2 são ferramentas de teste, mas conservam caminhos de operador e precisam ser parametrizados antes da publicação; não foram executados nem alterados por serem arquivos de suporte protegidos.

O grep obrigatório caiu de 16 linhas com 18 IDs de delegação para quatro linhas com seis IDs, sem tratar os achados restantes como dados públicos aceitáveis.
Restam a linha de revisão do plano S3, reservada ao coordenador, e três linhas nos dois arquivos protegidos de piloto S2; o plano também conserva uma referência de método externo não distribuído.
Caminhos internos do container, como `/home/hqr` e `/opt/hermes`, e IPs sintéticos de testes são dados públicos de ensaio, não caminhos ou endereços do operador.
A baseline publicada já contém 11 linhas do grep obrigatório, com oito IDs; esta tarefa não reescreveu histórico nem publicou a branch local, e a publicação precisa usar uma árvore limpa e corrigir a baseline para frente.

### Gates e bloqueios de fechamento

`python3 scripts/run_tests.py` executou 177 testes unitários, 13 de integração e 63 de harness, 253 IDs únicos por suíte, sem skips, exit 1.
A única falha é `test_docker_selection_requires_exact_revision_and_every_fingerprint`, que ainda exige recusa sem Git no final de `tests/unit/test_s3_docker_qualification.py`.
Esse teste preexistente contradiz o contrato novo; a troca proposta é exigir `ok=true`, `revision=null` e a nota de correspondência completa depois da remoção de HEAD, sem tocar nos demais controles de revisão e drift.
O teste permanece intacto aguardando autorização específica, registrada em HQR-31; a higiene protegida e o plano ficam em HQR-30.

A compilação, o gate de linhas `[]`, o OKF oficial/perfil e `git diff --check` passaram.
O OKF manteve `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]` no pacote 0.3.0 já fixado.
CodeGraph 1.6.2 sincronizou os 89 arquivos Python/YAML da raiz correta, sem mudanças pendentes ou mismatch; a recomendação preexistente de reindexar o formato permanece, sem rebuild.
Os arquivos protegidos de S1/S2 são idênticos ao início desta continuação; contra `f7f3136`, o único delta continua sendo a linha D14 previamente autorizada de `tests/integration/test_export.py`.
O candidato ainda não está pronto para publicação: faltam as disposições de HQR-30/HQR-31, a regressão integral verde e a revisão independente do delta, sem inferir autorização de instalação ou aceite da S3.

## Disposição de HQR-30 e HQR-31 pelo coordenador

`tests/unit/test_s3_docker_qualification.py` foi criado nesta fatia (`d7592d2`) e não pertence aos testes protegidos da baseline `f7f3136`; o coordenador trocou a asserção final para a regra nova de qualificação sem revisão.
`tests/installed/s2_pilot.py` e `tests/installed/s2_pilot_runner.sh` também não estão na lista protegida; os caminhos do operador saíram do código.
O piloto usa um único home, `HERMES_HOME` ou o padrão `~/.hermes`, para conferências, backup e a CLI `hermes`, que herda a mesma variável.
O runner agora exige `HQR_HERMES_PYTHON` (interpretador do Hermes de trabalho) e `HQR_HERMES_SOURCE` (fonte do Hermes); a invocação anterior sem essas variáveis para com mensagem clara.
O plano S3 perdeu as referências de revisões privadas e a menção ao estudo privado, conforme a regra de higiene pública de Guilherme.
O label `hqr.task=t_1c0d7681` do alvo Docker continua nos testes e no Dockerfile: é um identificador opaco do fixture, sem dado pessoal, e os testes protegidos da S1 o exigem.
IDs de containers de execuções locais saíram de `docs/s1-installed-test.md` e ficam nos recibos privados.
Regressão completa: 177 unitários, 13 integração e 63 harness, todos verdes; a busca de higiene não encontra ocorrências.

## Primeiro ensaio da candidata publicada (2026-11-16)

O ensaio autorizado fixou a candidata pública `db77b6e55caa7d8bc123be9499a9187d33aef078`, na branch `hermes/2026-11-16-hqr-s3-candidate`, e rollback `ad113d95604128fcdf9c446e2c5bd9c75bff0860`.
As refs públicas foram relidas anonimamente; a árvore da candidata é idêntica ao runner local inicial `53800d253ac87652d38e5702d0dc80e30454e23a`.
`--admission-only` retornou PASS, exit 0, antes de qualquer comando no alvo.
A admissão adicional conferiu somente o alvo na bridge e nenhum listener exposto; o mirror público do alvo foi atualizado pela receita S2 e continha ambos os commits.

O runner completo retornou exit 1: PASS em `admission-before-any-mutation` e `dependency-requires-effective-off`; FAIL em `pinned-advanced-delegation`.
Os 13 passos posteriores não executaram: não houve swap da candidata, qualificação instalada, Auto, cenários nativos, ausência ou exercício de rollback.
A instalação nativa de advanced-delegation no pin aprovado com `--no-enable` terminou; a atestação falhou ao chamar o scanner, antes de enable.
O traceback liga `_tracked_bytecode` do scanner nativo a `subprocess.DEVNULL` e ao bloqueio de `os.open('/dev/null', O_RDWR)` pelo `ProbeGuard`; é defeito do runner, não recusa de segurança do scanner ou falha demonstrada do produto.

A correção local acrescenta um escopo exato para a consulta Git somente de leitura do scanner, com fsmonitor desligado e o dispositivo `/dev/null` conferido; `finally` revoga ambas as permissões.
O escopo não libera rede, credenciais, outra consulta/processo, outro cwd ou escrita externa ordinária, e não é usado pelos probes de consumidores.
RED `b0a0ce704f6a299f659ff29b4485529c5d84cdb1` observou três falhas; o GREEN correspondente está no histórico desta continuação.
O comando focado foi `python3 scripts/run_tests.py tests.harness.test_s3_scanner_guard`; depois da correção, os três testes passaram.
Os módulos nativos do novo harness são inertes, mas o `ADVANCED_CHECK`, o guard, o audit hook e a consulta Git são reais; isso reproduz a costura, não o scanner completo do Docker.
`python3 scripts/run_tests.py` retornou 177/13/67 testes, todos `OK`, exit 0 e sem skips, com contagem conciliada dos IDs por suíte.
Os testes protegidos da S1 continuam iguais à base, exceto D14 já aprovado; `AGENTS.md` e `decisions/s3-plan.md` não foram editados.

A releitura confirmou a árvore S2 exata em `ad113d9`, versão `0.2.0rc1`, habilitada com OFF salvo/efetivo, e a dependência não habilitada com pin exato e os 23 arquivos conferidos.
A admissão final conservou somente o alvo na bridge e `listeners.exposed=[]`; recibos brutos ficaram privados, fora do Git.
Um pós-processador local tentou a chave inexistente `plugin_version`; o recibo de releitura já estava PASS e foi interpretado pela chave real `version`, sem repetir o comando no alvo.
Não houve inferência, acesso ao Hermes real, push, merge ou nova instalação da correção local.
HQR-32 exige revisão independente, candidata republicada e repetição integral do ensaio antes de aceitar Auto instalado; esta execução parou para o coordenador cumprir esses gates.

## Correção dos achados do runner HQR-32 (2026-11-16)

A rodada começou em `bb3cf237bd2cc62908ccc6c71b8b9492a66a787a`, com árvore limpa e branch de tarefa confirmada.
As refs remotas relidas continuavam em `ad113d9` para main e `db77b6e` para a candidata; a correção ficou somente local, sem push, publicação ou merge.
A fonte do instalador e do scanner foi consultada no fixture Docker somente com leitura de arquivos por `docker exec`, sem importar o Hermes ou executar sua CLI.
Não houve mutação Docker, ensaio instalado, acesso ao Hermes real, leitura de credenciais ou inferência nesta rodada.

### Correções e prova por achado

| Achado | RED | GREEN | Prova acrescentada |
|---|---|---|---|
| TEST-01 | `2983430` | `01f31d5` | Um teste executa `Worker` e seu payload real em outro interpretador isolado, com módulos nativos inertes e árvore sintética sem arquivos extras após o encerramento. |
| RUN-01 | `5ea8ce5` | `1d22f0f` | Seis testes reproduzem a recusa nativa de destino existente e exigem reuso atestado; recusam habilitado, pin diferente, bytes/arquivos extras, links, especiais e scanner não safe. |
| SEC-01 | `4ea8ec6` | `1948564` | Quatro testes recusam executável alternativo, ambiente explícito diferente, deriva de PATH/ambiente herdado e cwd textual `None`. |
| SEC-02 | `f6b03d6` | `df04063` | Seis testes cobrem acesso entre threads, uso repetido, escopos aninhados, saídas intercaladas normais/com exceção e sobreposição válida de threads independentes. |

Os comandos RED foram `python3 scripts/run_tests.py tests.harness.test_s3_<worker_bootstrap|advanced_reuse|scanner_binding|scanner_lifetime>`, um módulo por ciclo.
TEST-01 observou uma falha; RUN-01 retornou `failures=10, errors=1` em seis métodos; SEC-01 retornou nove falhas de métodos/subtestes em quatro métodos; SEC-02 retornou dez falhas de métodos/subtestes em seis métodos.
Os quatro módulos passaram após os respectivos GREEN, sem alterar seus bytes depois dos commits RED.

SEC-01 qualifica o Git pela resolução canônica a partir de diretórios de sistema explícitos e fixa uma cópia completa do ambiente admitido.
A grafia `git` usada pelo scanner nativo só passa se continuar resolvendo para esse executável qualificado com o mesmo ambiente; executável alternativo e qualquer ambiente divergente são recusados.
O cwd é comparado por identidade com `None`, não pela sua representação textual.
SEC-02 guarda o ticket em estado local da thread, consome a admissão no primeiro `Popen` válido e revoga também o sink `/dev/null`; entrada substituta e qualquer saída do escopo não restauram tickets anteriores.
Os testes preexistentes do scanner continuam intactos, inclusive as provas reais de Git, bytecode rastreado e revogação após exceção.

O bootstrap TEST-01 inclui `contextmanager`, `stat`, `ProbeFailure` e `ensure`, além das classes copiadas, antes de instalar o audit hook do filho.
A prova usa o caminho real `Worker.read()`/`close()`, não apenas compilação ou inspeção da string.
RUN-01 não acrescenta `--force`: somente a mensagem específica da recusa nativa de destino existente abre o caminho de reuso.
Antes de habilitar, esse caminho exige diagnóstico nativo de não habilitado, pin exato, manifesto completo de bytes, ausência de links/especiais, política de scan ligada e veredito `safe`; qualquer outra falha original do instalador permanece uma falha.
O fixture executa `ADVANCED_CHECK` e o inventário real, mas modela o instalador, o scanner e a leitura de pin com módulos inertes; não é prova do instalador completo no Docker.

### Gates e preservação

`python3 scripts/run_tests.py` retornou 177 testes unitários, 13 de integração e 84 de harness, 274 IDs únicos conciliados com os resumos do runner, todos `OK`, exit 0 e sem skips.
A contagem inicial por linha terminou em 81 no harness por três diagnósticos esperados intercalados; a leitura dos blocos completos do mesmo log confirmou 84 IDs com resultado `ok`, sem repetir a suíte para corrigir o pós-processador.
`compileall` retornou exit 0, o gate de linhas retornou `[]`, e os checks de whitespace e a busca obrigatória de higiene não encontraram problemas.
O pacote OKF 0.3.0 fixado teve todos os hashes conferidos contra seu manifesto e retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete`, `diagnostics=[]`.
CodeGraph 1.6.2 sincronizou os seis arquivos de código alterados e confirmou os 94 caminhos Python/YAML rastreados, sem faltantes, extras, pendências ou mismatch da raiz; a recomendação preexistente de reindexação continua sem rebuild.
Gitleaks não encontrou vazamentos no stage antes de cada commit desta rodada.

Os 13 caminhos protegidos da S1, inventariados pelo histórico S1 e comparados em `f7f3136`, mantêm somente a substituição de uma linha aprovada em D14 de `tests/integration/test_export.py`.
Para cada RED desta rodada, os diffs de modificações/remoções/renomes de S1 entre a base da rodada e RED, e entre RED e a entrega, são vazios; os próprios quatro testes RED também não mudaram depois de seus commits.
`AGENTS.md`, `decisions/s3-plan.md` e os arquivos preexistentes de testes unitários, integração e harness ficaram iguais a `bb3cf23`; somente os dois runners instalados autorizados mudaram, além dos quatro módulos novos de teste.
HQR-32 permanece aberto para rechecagem independente dos quatro achados, publicação autorizada da correção e ensaio instalado completo; esta rodada não afirma prontidão operacional, aceite da S3 ou atualização do alvo.

## Segundo ensaio da candidata publicada (2026-11-16)

O ensaio autorizado fixou a candidata pública `161392adcad5fc931d71f1f88564760c9e7e5203`, rollback `ad113d95604128fcdf9c446e2c5bd9c75bff0860` e runner inicial `0697c3e678291b0453f779d93deca9c60ceca948`.
As refs foram relidas anonimamente e as árvores da candidata e do runner coincidiram; o pai público da candidata é `db77b6e`.
A admissão `--admission-only` retornou PASS e exit 0 antes de qualquer comando no alvo.
A admissão adicional confirmou somente o alvo na bridge e nenhum listener exposto; a receita atualizou o mirror público e releu candidato e rollback como commits.

### Resultado instalado

O ensaio completo retornou exit 1, com oito passos PASS, um FAIL e sete não executados.
O runner interrompeu a execução no primeiro passo FAIL, sem tentativa de continuar ou repetir Docker depois das correções locais.

| Passo | Resultado |
|---|---|
| `admission-before-any-mutation` | PASS |
| `dependency-requires-effective-off` | PASS |
| `pinned-advanced-delegation` | PASS; reuso atestado antes de enable. |
| `candidate-swap` | PASS |
| `candidate-host-fingerprints` | PASS |
| `native-auto-scenarios` | PASS do script, não do conjunto de cenários. |
| `removal-refused-in-auto` | PASS; E2. |
| `absence-disable-with-auto` | PASS |
| `absence-config-and-native-diagnostic-while-disabled` | FAIL; `native disabled diagnostic missing`. |
| `absence-reenable` | Não executado. |
| `absence-readback` | Não executado. |
| `rollback-swap` | Não executado. |
| `rollback-observe-smoke` | Não executado. |
| `candidate-return` | Não executado. |
| `final-observe` | Não executado. |
| `acceptance-requires-all-native-consumers` | Não executado. |

Os cenários C1/C2/C3/C4/C7/C8/C9/C10/C12 e AC-22 passaram no recibo de consumidores, e E2 passou no passo seguinte.
C5/C6 falharam com `native probe refused forbidden operation: os.posix_spawn` e `audit_denied` contém essas duas recusas.
O passo `native-auto-scenarios` só prova que o script devolveu JSON; o gate final que exige todos os consumidores não foi alcançado.
As listas intermediárias de pendências precedem a inclusão de C12/E2 e não anulam os seus recibos individuais posteriores.
AC-22 significa somente o fallback aceito `geração indeterminada`, sem qualificar fonte nativa de criação, geração ou idade.
AC-17, A2/A3/A5/A13, histerese de rota, B3/B4, esforço C7, D7/OFF, recuperação nativa D10 e restauração D3 passaram com cotas sintéticas.
Isso não comprova cota real, elegibilidade de conta, transporte, inferência ou cobrança incluída.

### Defeitos do runner e correções locais

RUN-02: a tabela Rich de `plugins list` mostrou `hermes-quota-r…`, embora `plugins show` retornasse `Status: disabled` e a configuração estivesse preservada.
O diagnóstico falhou por procurar a chave inteira na tabela, não por ausência real do plugin ou mudança indevida da configuração.
A correção usa a forma nativa `plugins list --plain --no-bundled`, com correspondência exata da chave e o mesmo diagnóstico de `show`.
O teste novo executa a função `disabled_proof` real por AST com saídas modeladas e controles de chave parecida/ausente, status habilitado e configuração divergente.
RED `57c1fa8a50c5f4ecd30e1c61455b47e64c9f9074` observou dois FAIL em cinco testes; GREEN `132c8d09d5d99ae89d90d7bbfcf2ff391d33aefe` passou os cinco.
Comando: `python3 scripts/run_tests.py tests.harness.test_s3_disabled_listing`.

RUN-03: o Python 3.14.10 do alvo suporta CLOSEFROM em `posix_spawn`; o `Popen` do worker selecionou esse caminho e o audit hook o recusou.
O teste anterior de bootstrap não instalava o guard do pai, por isso não cobria essa fronteira.
A correção local acrescenta `start_new_session=True` ao Worker, mantendo a rota auditada de `Popen` e a recusa de todo `os.posix_spawn`, sem ampliar permissões do guard.
O novo teste instala o guard do pai, reproduz a seleção de spawn com CLOSEFROM, executa Worker/payload reais em outro processo com módulos nativos inertes e confere que spawn direto e outro Popen continuam bloqueados.
RED `a5c0d1263198425cc74f0d31d13811d02434e0ba` observou um FAIL; GREEN `8852cbcc48fb0236fbbc8f20ca84c2a4a19017d6` passou o teste novo e o bootstrap anterior intacto.
Comando: `python3 scripts/run_tests.py tests.harness.test_s3_guarded_worker_launch`.
Essas provas locais não repetem C5/C6 no Docker e não instalam os bytes corrigidos.

`python3 scripts/run_tests.py` retornou 177 testes unitários, 13 de integração e 90 de harness, todos `OK`, exit 0 e sem skips.
São 280 testes, seis novos; os diagnósticos negativos esperados continuam no log e não foram ocultados como falhas da suíte.
Gitleaks passou no stage antes de cada commit RED/GREEN, sem regra desabilitada.
A comparação com a base desta rodada conserva todos os testes preexistentes, exceto os dois runners S3 explicitamente autorizados; os novos testes permanecem iguais aos commits RED.
Os testes S1 comparados em `f7f3136` conservam somente D14 já aprovado, e `AGENTS.md` e `decisions/s3-plan.md` não foram editados.

A compilação de produto/scripts/testes e dos cinco scripts embarcados retornou exit 0; o gate de linhas retornou `[]` e os checks de whitespace passaram.
O pacote OKF fixado manteve seus hashes e retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]` na raiz correta.
CodeGraph sincronizou quatro arquivos e os 96 caminhos Python/YAML indexados coincidiram exatamente com os versionados, sem pendências; a recomendação preexistente de reindexação permanece sem rebuild ou download.
O primeiro pós-processador do inventário usou `filePath` em vez da chave real `path`; a comparação foi corrigida sobre o JSON preservado, sem tratar esse erro de análise como falha do sync.

### Estado final e pendências

A releitura separada dos efeitos confirmou a árvore exata da candidata `161392a`, versão `0.3.0rc1`, desabilitada e sem handler nativo; o modo salvo continua `auto`.
Esse estado não é OFF efetivo comprovado por um handler carregado e não está pronto para uma retomada automática do runner.
Advanced-delegation `1.1.0` permanece habilitado, no ref `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`, com os 23 arquivos e nenhum especial, todos exatos.
Rollback não foi instalado ou exercitado nesta execução, e não houve retorno ao candidato nem Observe final.
A admissão final confirmou somente o alvo na bridge e `listeners.exposed=[]`.
Os recibos e logs brutos ficaram privados, fora do Git.
Não houve push, merge, publicação das correções, inferência ou acesso ao Hermes real.
HQR-32 permanece aberto para revisão independente das duas correções, publicação autorizada, preparação aprovada do estado inicial OFF e repetição integral do ensaio.
A correção local e os cenários já verdes não fecham o aceite instalado da S3.

## Ensaio instalado no alvo Docker de teste, 2026-11-16

Candidata publicada `ba5d6f850d848d1f9793345f8b8a1ff9a833df4f` na branch `hermes/2026-11-16-hqr-s3-candidate`, árvore igual à do runner `3ec13eb`; rollback `ad113d9`; advanced-delegation 1.1.0 no pin `13b2c1c`.
Antes da execução, o alvo voltou ao estado de partida por comandos nativos: Quota Router habilitado e posto em OFF de imediato, baseline conferida por presença e valor, e só então advanced-delegation desabilitado.
Resultado: 16 de 16 passos PASS, exit 0; os 13 cenários nativos (C1 a C10, C12, E2 e AC-22) e AC-17, A2, A3, A5, A13, histerese, B3, B4, C7-effort, D7-OFF, D10 e D3 passaram, com cotas sintéticas e sem inferência.
AC-22 prova o fallback `geração indeterminada`, não uma fonte imutável qualificada.
Estado final do alvo: Quota Router 0.3.0rc1 em Observe, advanced-delegation 1.1.0 habilitado.
As duas tentativas anteriores pararam em defeitos do runner (HQR-32), corrigidos e revisados antes desta execução; os recibos brutos ficam privados.
Pendências abertas: o campo superior `pending_consumer_proofs` do recibo guarda um snapshot anterior ao gate, enquanto o gate valida a lista aninhada; e falta teste de encerramento de worker travado ou de cancelamento abrupto do pai (achado opcional da revisão).
Próximo gate: DEMO e piloto em Auto no Hermes de trabalho, com autorização específica de Guilherme, backup e rollback.

## Correção dos três defeitos de preview S3 (2026-11-16)

Os três defeitos estão corrigidos e testados localmente; os bytes corrigidos ainda não foram publicados ou instalados.
A autorização de Guilherme em 2026-11-16 está registrada como D18 na [emenda](hqr-20-amendment.md#18-correção-do-preview-s3-em-2026-11-16-d18).
A rodada partiu de árvore limpa, branch conferida e HEAD `92e7be1d586f1c4a45762a831d81967fb4dd4452`.
O fetch anônimo confirmou `origin/main=ad113d95604128fcdf9c446e2c5bd9c75bff0860`, ancestral da tarefa, e candidata pública `ba5d6f850d848d1f9793345f8b8a1ff9a833df4f`.
Não houve push, merge, publicação, instalação, restart, inferência ou acesso a configuração, credenciais e sessões reais.
O Docker foi consultado somente por `exec` de inspeção inerte dos fingerprints, com bytecode desligado e audit hook recusando escrita, rede e subprocessos.

### Causas, decisões e testes

| Defeito | Causa | Correção e prova |
|---|---|---|
| Defaults nativos recusados | A precondição tratava qualquer endpoint/modo não vazio como customizado; o alvo também apagava os dois campos. | `routes.py` espelha somente constantes públicas qualificadas; conversa e subagente aceitam os defaults do provider atual e gravam os defaults do destino; sete métodos novos cobrem ambos os providers, OFF/reload, projeção, recusa customizada e interrupções por campo. |
| Grupos bloqueados invisíveis | O motor verificava precondições depois de a decisão já ter sido anunciada; Observe não aplicava os gates do motor. | Decisão e `routing_blocks` por papel conferem os gates antes de anunciar mudança; cinco métodos novos cobrem campos, null, configuração, profile, catálogo, backend, divergência e continuidade da preferência. |
| Mapa e qualificação antigos | Explain renderizava `propose()` da S2 e o status conservava labels fixos de host não verificado. | Explain renderiza o `settings.roles` vigente e cron sem linha própria; quatro métodos novos cobrem cada célula aprovada, edição/recorte do mapa, Auto/Observe e qualificação com e sem revisão legível. |

Os três métodos adicionais de fronteira cobrem sincronização só de endpoint/modo, reingresso OFF → Observe → Auto e impossibilidade de qualificar um espelho obsoleto mudando apenas o ledger nativo.
Três métodos adicionais fazem uma edição externa ou perda de qualificação depois da prévia, inclusive no último veredito nativo; a resposta final suprime a mudança recusada e alinha a disponibilidade de Auto à fonte mais recente.
A identidade da preferência inclui a projeção fechada com presença; só uma escrita própria confirmada avança a rota esperada de G2/G8.
A recuperação conserva os quatro casos de D15 e admite mistura de rota somente pelas células anterior/alvo validadas do diário.
Endpoint customizado depois da publicação do diário não é completado nem restaurado; somente o nome do campo entra no diagnóstico.

### Fonte nativa e qualificação

O default Codex vem de `hermes_cli.auth_constants.DEFAULT_CODEX_BASE_URL`; o default Anthropic vem de `hermes_cli.runtime_provider._ANTHROPIC_DEFAULT_BASE_URL`.
`hermes_cli.providers.TRANSPORT_TO_API_MODE` fixa os modos, e os corpos de `_explicit_codex`/`_explicit_anthropic` confirmam os pares usados no runtime.
Essas fontes são inspecionadas, nunca chamadas para resolver credenciais.
O espelho escreve `base_url`/`api_mode` públicos do Codex com `codex_responses` e do Anthropic com `anthropic_messages`; valores ausentes na forma nativa seriam removidos, não herdados do provider anterior.
`model_selection_config_updates` continua qualificado e documenta a sincronização dos campos e a remoção por `None`.
O backend advanced-delegation copia os campos não vazios de `ROUTE_FIELDS`, portanto as opções recebem o mesmo par e conservam os campos fora da projeção.

O conjunto obrigatório passou de 71 funções/nove constantes para 73 funções/12 constantes por host.
As duas funções novas são `hermes_cli.runtime_provider._explicit_codex` e `hermes_cli.runtime_provider._explicit_anthropic`.
As três constantes novas são as duas URLs públicas de default e `TRANSPORT_TO_API_MODE`, identificadas acima.
As duas entradas foram rederivadas integralmente nas fontes da revisão `3b421578588243f920886e6fe79a6faa87ea026e`, inclusive a dependência no pin `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`.
Todos os fingerprints anteriores coincidiram; os dois conjuntos novos também são iguais, sem promover a fonte de sessões ou hooks.
A primeira tentativa de extração encontrou o reexport em `auth.py`, que não é um literal; a qualificação foi corrigida para a definição em `auth_constants.py`, sem executar nenhum módulo de autenticação.
O JSON qualifica a fonte medida e preserva separadamente `revision`, `qualified_revision`, `installed_verified=false` e `lifecycle=requires_installed_smoke`.

### RED/GREEN preservados

| Escopo | RED | GREEN | Comando focado após `python3 scripts/run_tests.py` |
|---|---|---|---|
| Defaults e recuperação | `81455ae` | `dbe2658` | `tests.unit.test_s3_native_defaults` |
| Bloqueios e preferência | `38c4ee5` | `6bdb2b8` | `tests.unit.test_s3_blocked_preview` |
| Mapa e qualificação | `85967da` | `55855e5` | `tests.unit.test_s3_effective_explain` |
| Runner com rota nativa | `97d1a4c` | `7869c54` | `tests.harness.test_s3_native_route_runner` |
| Fronteiras e reingresso | `b61bc0c`, `c36a247` | `a864676` | `tests.unit.test_s3_route_boundaries` |
| Gates tardios na resposta | `e969d0a`, `4e93473` | `7590102`, `fa95937` | `tests.unit.test_s3_final_gate_preview` |

Os RED observaram falhas de requisito ausente antes das correções correspondentes.
O primeiro RED de defaults teve três ajustes posteriores do fixture: definição real da constante em vez do reexport, mutação da opção real em vez da cópia de `option()`, e expectativa de descartar o diário quando a restauração interrompida ainda estava inteiramente no anterior (D15).
Não se apresenta esse ajuste de fixture como imutabilidade dos novos testes; os protegidos do mandato são os 13 caminhos S1.
Os controles S2 positivos agora declaram explicitamente profile/default e compatibilidade sintéticos; o caso de papel sem mapa exige bloqueio visível, em vez de anunciar a proposta como mudança de Auto.
As asserções S3 de ausência de endpoint e contagem de fingerprints foram alinhadas ao contrato D18; o controle de decisão inalterada começa na forma nativa completa.
Nenhum teste S1 foi alterado nesta rodada.

### Runner e limites da prova

`tests/installed/s3_auto.py` prepara conversa e opção general com os defaults nativos de endpoint/modo, sem removê-los para simplificar a prova.
A aprovação do mapa precede AC-17; a prévia é comparada ao alvo realmente persistido, inclusive modelo e esforço.
O runner exige `native-default-route-apply`, `native-default-route-restore` e `custom-route-refusal`, além dos cenários anteriores.
Três métodos novos de harness executam o setup e a função de recusa reais por AST, com `Management`/motor reais e armazenamento sintético; um controle de prévia otimista precisa falhar.
Essa execução não é um ensaio Docker da revisão corrigida, nem prova YAML nativa ou do transporte do provedor.
O Python da suíte hermética não tem `ruamel`; não se instalou dependência ou chamou launcher para ampliar a prova.

### Gates e proteção

`python3 scripts/run_tests.py` retornou 199 testes unitários, 13 de integração e 93 de harness, todos `OK`, exit 0, sem skips.
Os 305 IDs únicos foram conciliados por suíte com os três resumos do mesmo log; são 25 métodos novos nesta rodada.
`compileall` de produto/scripts/testes retornou exit 0 com cache descartável externo; os sete scripts Python embarcados também compilaram.
O gate de linhas retornou `[]`; os checks de whitespace passaram na árvore e contra a base da rodada, depois de remover uma linha vazia adicional no fim deste registro.
O pacote OKF 0.3.0 preservou o pin do router e seu manifesto; a validação oficial/perfil retornou `conformant`, `pass`, `valid`, `complete` e `diagnostics=[]` na raiz correta.
CodeGraph 1.6.2 sincronizou os arquivos alterados e os 103 caminhos Python/YAML indexados coincidiram exatamente com os versionados, sem faltantes, extras, pendências ou mismatch.
A recomendação preexistente de reindexar o formato permanece; não houve rebuild, download ou telemetria.
O grep obrigatório de higiene retornou zero ocorrências, e Gitleaks passou no stage antes de cada commit RED/GREEN, sem desabilitar regras.
Os gates são repetidos após o registro documental final.

O diff dos 13 caminhos protegidos S1 entre `92e7be1` e a entrega é vazio; contra `f7f3136` permanece somente a linha D14 já aprovada em `tests/integration/test_export.py`.
As comparações base → RED e RED → entrega dos mesmos 13 caminhos também são vazias para cada RED desta rodada.
`AGENTS.md` e `decisions/s3-plan.md` ficaram intactos.

### Próximo passo do coordenador

HQR-33 conserva a revisão independente do delta, a atualização do plano, a publicação autorizada e a repetição instalada antes de retomar o piloto.
A revisão independente não foi executada por este worker e nenhum estado de runtime foi atualizado.
O coordenador precisa substituir a frase do escopo da conversa que termina em "para provedores de registro, que não usam endpoint nem modo de API próprios" pela regra D18 de defaults nativos do destino, sem resolver credenciais.
A frase "Precondição da rota de subagente: sem endpoint próprio nem credencial na opção" precisa explicitar que o par ausente/vazio ou igual ao default do provider atual é aceito.
A enumeração dos fingerprints precisa acrescentar `_explicit_codex`, `_explicit_anthropic`, `DEFAULT_CODEX_BASE_URL`, `_ANTHROPIC_DEFAULT_BASE_URL` e `TRANSPORT_TO_API_MODE`, mantendo os itens anteriores.
Essas são mudanças propostas ao plano reservado, não alterações feitas pelo worker.

## Correção dos achados R1/R2 de D18 (2026-11-16)

R1 e R2 estão corrigidos nos testes focados; o gate completo permanece bloqueado por duas expectativas numéricas protegidas da S3 que ainda dizem 73/12 em vez de 134/18.
A rodada começou na branch conferida, árvore limpa e HEAD `8219eebbbb1fea344dba51123c380af2fa617631`.
O fetch confirmou `origin/main=ad113d95604128fcdf9c446e2c5bd9c75bff0860`, ancestral do candidato, sem delta remoto a integrar.
Não houve push, merge, publicação, inferência, alteração de Docker, configuração, sessões, credenciais ou plugins instalados.
O alvo Docker recebeu apenas comandos de identificação da fonte e inspeção inerte com bytecode desligado e audit hook de leitura.

### R1: caminho normal de resolução

O fingerprint anterior cobria os builders explícitos, mas a troca normal pode retornar de OAuth, pool ou `_anthropic_env_runtime` antes de usá-los.
A correção vincula a escada e seus builders de URL/modo, a seleção e formação final de `model_switch`, os guards canônicos e os reexports usados pelo módulo carregado.
As três tabelas de dispatch recebem hash da atribuição completa e projeção AST dos campos públicos relevantes; a inspeção não executa construtores, lambdas ou imports nativos.
As tabelas carregadas também são comparadas, e uma requalificação do modo OAuth/pool divergente do espelho continua recusada.
O leitor inerte segue reexports de função somente dentro da raiz de fonte e recusa ciclos/escapes.

As entradas de trabalho e Docker foram rederivadas integralmente: 134 funções e 18 constantes em cada uma, com conjuntos iguais e nenhum fingerprint anterior divergente.
A revisão conferida no checkout é `3b421578588243f920886e6fe79a6faa87ea026e`; o Docker continua sem Git legível e conserva essa revisão declarada, o opt-in e a proveniência anteriores.
A dependência de delegação conserva versão `1.1.0` e ref `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`.
A medição não promoveu sessão, hooks ou instalação à condição de qualificados.
Uma primeira tentativa de projeção encontrou o import preguiçoso do unparser do Python 3.14; a projeção usa agora campos AST normalizados e passou sob o mesmo guard, sem ampliar acesso.

### R2: overlay global

`groups.preconditions` recusa `model.openai_runtime` não vazio na conversa e nos subagentes, inclusive quando o provider atual é Anthropic e o destino seria Codex.
O mesmo guard atende Observe, inscrição, escrita tardia, recuperação e OFF; estado e diagnóstico conservam só o nome do campo.
Os testes aceitam ausência, null e strings vazias/espaços e recusam outros valores/tipos sem ecoá-los.
A inspeção também conferiu `model_derived_api_mode`, `_PROVIDER_API_MODE_OVERRIDES`, `_build_switch_result` e o guard final de chave ausente; não encontrou outra chave de configuração que reescreva o par desses dois providers depois da resolução nessa fonte.
`model.base_url`/`model.api_mode` já estão na projeção; aliases e blocos de provider atuam antes, e request overrides/service tier não mudam o par nesse trecho.
Essa análise não transforma overrides de ambiente ou endpoints customizados em defaults qualificados.

### RED/GREEN e proteção

| Achado | RED preservado | GREEN | Testes focados após `python3 scripts/run_tests.py` |
|---|---|---|---|
| R1 | `ce74a66`, `f890691`, `9f9182d` | `fcadea8` | `tests.unit.test_s3_default_resolution`, `tests.unit.test_s3_route_bindings`, `tests.unit.test_s3_default_guards` |
| R2 | `e1cf4dd` | `bebd5b7` | `tests.unit.test_s3_runtime_overlay` |

Os sete métodos novos de R1 e cinco de R2 passaram, sem skips.
R1 observou ausência de cobertura antes da correção e testa alteração de cada builder/seleção listado no seu fixture, inclusive modo OAuth e corpo Anthropic, com apply, recuperação e OFF sem escritas e com registros retidos idênticos.
Os controles adicionais conferem tabelas ativas, reexports sem import e desacordo entre tabela requalificada e espelho.
R2 observou decisão acionável indevida e escritas antes da correção; depois conferiu a recusa, a inserção tardia do overlay e ausência do seu valor em estado, JSON e texto.
Nenhum arquivo de teste ou suporte preexistente nesta rodada foi editado; os quatro arquivos novos foram preservados após seus RED.
As oito comparações base → RED e RED → entrega dos caminhos protegidos foram vazias.
Nos 13 caminhos S1, o delta da rodada é vazio e a comparação com `f7f3136` conserva somente D14 em `tests/integration/test_export.py`.

### Gates observados e bloqueio

O runner completo executou 211 métodos unitários, 13 de integração e 93 de harness, com 317 IDs únicos e nenhum skip.
Integração e harness passaram; unit teve exatamente uma falha, em `test_docker_entry_has_complete_fingerprints_without_locations`, por `134 != 73`.
A linha seguinte ainda espera 12 constantes; a medição agora contém 18.
O ajuste solicitado é somente 73 → 134 e 12 → 18 em `tests/unit/test_s3_docker_qualification.py:34–35`, sem mudar as asserções de conjunto completo, revisão, dependência, ausência de localizações ou digests.
A proteção dos testes impede fazê-lo sem autorização específica; HQR-33 registra essa dependência e não se declara regressão completa verde.
A primeira execução antes do stage do módulo novo também encontrou falha de exportação por usar `git ls-files`; a integração completa passou depois do stage explícito, sem editar esse teste.

`compileall` retornou exit 0 com cache externo descartável, e o gate de linhas retornou `[]`.
OKF 0.3.0 retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]` na raiz correta.
O router conserva SHA-256 `e1f5be06b7f8a69fe7407aff97bde1cfd4d6767a65b974ff3bc1e958cb054b42`, e as seis entradas do manifesto do pacote coincidiram.
`git diff --check` passou e o grep obrigatório de higiene não encontrou ocorrências.
CodeGraph 1.6.2 sincronizou oito arquivos; os 108 caminhos Python/YAML indexados coincidem exatamente com os versionados, sem pendências ou mismatch.
A recomendação de reindexação já existia e permanece; não houve rebuild, download, telemetria ou alteração de hooks.
Gitleaks passou no stage antes de cada commit RED/GREEN, sem exceção nova ou regra desligada.

### Alterações reservadas ao coordenador

O plano S3 não foi editado nesta rodada.
Na frase das precondições da conversa, acrescentar a recusa global de `model.openai_runtime` não vazio também para os subagentes, com diagnóstico só pelo nome, em Observe, inscrição e antes de toda escrita.
Na frase que enumera funções qualificadas, acrescentar o caminho normal OAuth/pool/Anthropic, os builders Codex, os guards/reexports e a seleção/overlay final; a lista executável completa está em `compat.FUNCTIONS`.
Na frase das constantes, acrescentar as três tabelas de dispatch com atribuição/projeção inerte e as três tabelas auxiliares; os dois hosts agora exigem 134 funções e 18 constantes.
Depois do ajuste protegido autorizado, repetir o runner completo e revisar independentemente o delta antes de qualquer publicação ou repetição instalada.

### Reconciliação do coordenador após a retomada

A classificação anterior de `tests/unit/test_s3_docker_qualification.py` como teste protegido da baseline estava incorreta: o arquivo não existe em `f7f3136` e foi criado nesta fatia por `d7592d2`.
O coordenador atualizou somente as duas contagens, de 73/12 para 134/18, preservando as asserções de conjunto completo, revisão, hashes e recusa de divergências.
O plano passou a explicitar a recusa global de `model.openai_runtime`, os caminhos normais de resolução e a inspeção inerte das tabelas.
A nova execução integral do runner, pela coordenação, retornou exit 0: 211 unitários, 13 integração e 93 harness, sem skips.
R1/R2 permanecem corrigidos aguardando rechecagem independente; publicação, repetição instalada e retomada do piloto não foram executadas nesta reconciliação.

### Segunda correção de R1: lambda inline (R3) e aliases

A rechecagem de `8901a88` encerrou R2, mas manteve R1 aberto por duas causas: recusa da lambda inline válida e ausência da tabela `_PROVIDER_ALIASES` na qualificação.
R3 é o mesmo defeito apontado pelas perspectivas geral e de segurança, não dois defeitos diferentes.
A correção foi escrita diretamente pelo coordenador, sem delegar implementação.

- R3: `loaded_lambda` lê e analisa o arquivo completo da função ativa e seleciona a única lambda na sua primeira linha de código; não executa esse código, não depende de fragmentos de `inspect.getsource` e recusa posições ambíguas.
- O controle positivo reproduz a entrada multilinha nativa de dicionário; os negativos substituem o resolver ou põem duas lambdas na mesma linha.
- RED `5b12b70` reproduziu a recusa; GREEN `22c0956` passou os três controles e a regressão integral de 320 métodos.
- R1 residual: a constante integral `_PROVIDER_ALIASES` entra no conjunto obrigatório e o espelho recusa aliases que redirecionem um provider gerido, mesmo após requalificação do ledger.
- RED `8fd8f02` reproduziu drift aceito na fonte e na tabela ativa, além de espelho obsoleto; GREEN `e8116d7` passou os controles de suspensão em aplicação, recuperação e OFF, preservando escritas e registros.
- As duas fontes de `auth.py` foram lidas e a atribuição literal foi extraída por AST: os 78 aliases coincidem; ambas as entradas agora têm 134 funções e 19 constantes.
- Os valores anteriores de funções e constantes e os metadados de qualificação foram preservados; apenas a nova constante foi acrescentada.

A primeira preparação do teste de lambda também bloqueava imports internos de `linecache`, antes do defeito procurado; a fixture foi ajustada antes de congelar o RED para isolar a recusa da tabela nativa válida.
A suíte completa retornou exit 0: 217 testes unitários, 13 integração e 93 harness, sem skips.
Os arquivos RED novos ficaram intactos após os respectivos commits; a contagem Docker passou de 18 para 19 constantes sem alterar as demais asserções.
O plano e a emenda foram reconciliados; a próxima revisão se limita a R1/R3 e à cobertura afetada, conservando o fechamento de R2.
Nenhum runtime, configuração real, credencial ou sessão foi alterado, e nenhuma candidata foi publicada nesta correção.

### Resultado da rechecagem de `3c377a2`

As perspectivas geral e de segurança aprovaram o delta; testes encerraram R1-alias e preservaram o fechamento de R2, mas deixaram uma lacuna de prova em R3.
O teste de duas lambdas na mesma linha usa um argumento `IfExp`, recusado por `source_routes` antes de chegar ao seletor de `loaded_lambda`; por isso, não prova a rejeição de uma posição ambígua aceita pela gramática.
A coordenação confirmou a lacuna por leitura do teste e dos dois guards; não há defeito funcional novo demonstrado na implementação atual.
A correção proposta é apenas uma fixture com `resolve` sendo uma lambda direta e outra lambda na mesma linha, conferindo fonte isolada válida e tabela carregada recusada.
O snapshot de 143 arquivos e o estado Git permaneceram idênticos ao pin da revisão; os 323 testes anteriores continuam sendo evidência daquela versão, não prova dessa lacuna.
Como o limite de rodadas foi atingido, a correção e uma rechecagem focada aguardam autorização de Guilherme; nenhum teste foi alterado depois deste parecer.

### Ajuste autorizado da fixture R3

Guilherme autorizou em 2026-11-16 apenas o ajuste da fixture e uma rechecagem focada; não se infere autorização adicional de publicação, instalação ou ativação.
O argumento `resolve` agora é uma lambda direta em uma entrada válida de dispatch, com outra entrada e outra lambda na mesma linha física.
O teste exige que a inspeção da fonte isolada seja aceita antes de carregar a tabela; a recusa posterior precisa, portanto, alcançar a inspeção da função ativa.
Um controle temporário só em memória substituiu o seletor por outro que escolhe a primeira lambda: o teste falhou na asserção final, enquanto o seletor atual passou.
O resolver da fixture não foi chamado; nenhum código nativo foi executado e nenhum arquivo do plugin foi alterado.
A regressão completa retornou exit 0: 217 unitários, 13 integração e 93 harness, 323 IDs qualificados únicos, sem skips.
As aprovações geral e de segurança de `3c377a2` continuam vinculadas à implementação idêntica; a lacuna de prova aguarda a rechecagem específica do teste alterado.

### Fechamento da prova R3 em `bc119a6`

A rechecagem focada aprovou a fixture e encerrou R3-prova-ambiguidade em `bc119a6ab7f276558f553ff407b39cda027ce683`.
O revisor confirmou que as duas lambdas são diretas e estão na mesma linha, que o controle inerte passa antes da carga e que o mutante falha na asserção final; a prova usa os logs da coordenação, não uma execução do revisor.
O snapshot dos 143 arquivos e o estado Git foram reconferidos antes de registrar este fechamento, sem divergências.
R1/R2/R3 não conservam achados bloqueantes locais; as aprovações geral e de segurança permanecem vinculadas à implementação de `3c377a2`, inalterada em `bc119a6`.
O teste instalado completo precisa ser repetido na candidata D18 publicada; o PASS anterior de `ba5d6f8` não comprova esse delta.
Este registro muda somente documentação: não concede publicação, instalação ou ativação do Auto e não declara aceite de Guilherme.

### Candidata D18 publicada e ensaio interrompido

Guilherme autorizou em 2026-11-16 publicar a candidata corrigida e repetir o ensaio completo no Docker, sem merge nem mudança no Hermes de trabalho.
Publicada `0376def827fd6d26a2dcc13bc0f6d6e3400b0d75`, um commit limpo sobre `ba5d6f8`, com árvore idêntica à local `5c5bf38` e sem levar o histórico intermediário de desenvolvimento.
O readback do remoto confirmou a candidata e a `main` preservada em `ad113d9`.
Gitleaks passou no intervalo de saída; o grep restrito não encontrou referências privadas, e as 66 ocorrências do grep amplo foram classificadas como caminhos internos do fixture, IPs sintéticos/loopback ou instruções públicas de ensaio.

As admissões passaram; o reset inicial confirmou OFF, grupos inativos e configuração fora da entrada do plugin preservada, antes de desabilitar a dependência e atualizar o mirror público.
O ensaio registrou 13 passos completos PASS, zero FAIL registrados e três passos sem recibo completo: retorno à candidata, Observe final e gate de todos os consumidores.
Os cenários nativos registrados e as provas D18 de aplicação com defaults, restauração exata e recusa de rota customizada passaram, assim como o rollback instalado à S2 e seu smoke Observe.
O limite externo de 270 segundos, escolhido pela coordenação, matou o processo pai durante o retorno à candidata; isso é interrupção da infraestrutura do ensaio, não falha funcional demonstrada no plugin.
A etapa interrompida já tinha avançado além do último recibo: a leitura posterior confirmou os 143 arquivos exatos de `0376def` e metadados da instalação, mas o plugin desabilitado, modo OFF salvo e metadado de deployment da configuração ainda na S2.
A dependência permaneceu habilitada no alvo e não havia processo de teste nativo restante; OFF efetivo final não foi comprovado com um handler carregado.

Uma preparação de repetição fez admissão e leitura, mas parou no guard que esperava o Observe registrado anteriormente; não fez mutação nem iniciou outro ensaio completo.
Os recibos das tentativas foram preservados separadamente e não há aceite instalado de D18.
A recuperação proposta é reabilitar a candidata somente no alvo descartável, comprovar OFF e restauração antes de desligar a dependência, e repetir o roteiro integral com limite externo maior; qualquer falha mantém os dependentes parados.
HQR-33 conserva essa pendência; não houve mudança de código, inferência, acesso ao Hermes de trabalho, merge ou nova ativação no ambiente de trabalho.

### Repetição D18 aprovada no Docker

Guilherme autorizou em 2026-11-16 recuperar o estado interrompido somente no alvo Docker e repetir uma vez o ensaio completo, com limite externo de 20 minutos.
Esta execução não autoriza nem realiza nova publicação, merge, atualização da instalação de trabalho ou ativação de Auto nela.
A candidata pública permanece `0376def827fd6d26a2dcc13bc0f6d6e3400b0d75`, com `main` em `ad113d9`, conferidas no remoto antes da recuperação.

A admissão foi repetida antes da primeira mutação, e a recuperação exigiu o estado observado: plugin desabilitado, OFF salvo e arquivos/metadados exatos da candidata.
Com a dependência ainda habilitada, o plugin foi reabilitado e recebeu OFF imediatamente pelo dispatcher nativo.
Processo novo comprovou OFF efetivo, grupos inativos, nenhuma exclusão e preservação da configuração fora da entrada e das listas de ativação do plugin.
Provider, modelo, endpoint, modo de API e esforços de conversa/general foram comparados com presença e valores da baseline sintética; os getters nativos dos três objetos também executaram.
Somente depois dessas provas a dependência foi desabilitada; o readback confirmou router habilitado em OFF e dependência inativa.
O mirror continha a candidata e o rollback, e nova admissão precedeu o roteiro completo.

O runner e o manifesto usados eram byte a byte os publicados na candidata, sem alteração do produto, dos testes ou de seus guards.
A tentativa única gravou os logs em arquivo desde o início e um recibo exclusivo de lançamento; concluiu antes do limite de 1200 segundos, com exit 0.
Foram 16 passos completos PASS, sem FAIL: consumidores nativos, ausência/disable, reenable, rollback à S2 com Observe, retorno à candidata, Observe final e gate final.
As provas D18 de aplicação de defaults nativos, restauração exata e recusa de rota customizada passaram.
O gate final reuniu C1 a C10, C12, E2 e AC-22 com PASS; a lista final de provas pendentes em `consumers` estava vazia e não houve negativa registrada pelo audit hook.
O escopo continua sendo resolução nativa de configuração/policy, não inferência, autenticação nem publicação completa de sessão.
AC-22 conserva geração indeterminada nos casos não qualificáveis, Worker continua fora da troca de conversa e a CLI nativa não é interceptada para remoção.

Cinco checks posteriores, separados do roteiro, confirmaram admissão, os 143 arquivos exatos de `0376def`, Observe salvo e efetivo sem restart pendente, grupos inativos sem exclusões e a dependência no pin/manifesto exatos.
O status observado registrou zero inferências extras e leituras de quota desconhecidas no alvo sem credenciais; isso não comprova isolamento universal de rede ou comportamento de provedores reais.
A regressão local também foi reexecutada: 217 unitários, 13 integração e 93 harness, exit 0, 323 IDs únicos qualificados por suíte e nenhum skip.
Logs e recibos das duas tentativas foram arquivados fora do Git, com inventário SHA-256 conferido; a tentativa interrompida permanece registrada como incompleta, sem aceite retroativo.

HQR-33 encerra a pendência deste ensaio Docker, mas conserva a necessidade de autorização para atualizar em Observe e conferir nova prévia no Hermes de trabalho.
Qualquer piloto Auto e o aceite da S3 continuam dependendo de decisão específica de Guilherme após a prévia; estes testes não concedem merge ou push.

### Revisão do registro de resultado D18

A revisão independente aprovou o delta documental da repetição D18, sem bloqueantes, após conciliar os sete recibos de recuperação, os 16 passos completos, os cinco checks posteriores e os logs locais.
O parecer leu as evidências da coordenação e conferiu hashes, sem executar Docker, Hermes, inferência ou testes e sem conceder aceite ou implantação.
D18-DOC-01, opcional, foi acolhido: a contagem agora explicita 323 IDs únicos qualificados por suíte, pois são 322 IDs isolados e um deles aparece em duas suítes.
A coordenação reconferiu essas contagens e os hashes do snapshot no ponto de uso; a única mudança no texto revisado é essa qualificação, além deste registro do parecer.
Não houve mudança do produto, dos testes, dos guards nem do histórico anterior à repetição.

### Instalação D18 em Observe e nova prévia

O responsável autorizou em 2026-11-16 instalar a candidata corrigida, manter Observe e mostrar nova prévia, sem ligar Auto.
A instalação recebeu `0376def827fd6d26a2dcc13bc0f6d6e3400b0d75` pelo gerenciador nativo, com ref imutável e origem pública já conferida, sem nova publicação ou merge.
Backup datado do plugin, configuração, metadado próprio e estado existente foi conferido antes da troca e permanece privado, com os recibos e inventários SHA-256 fora do Git.
A revisão automática de aprendizagem foi pausada pelo controle nativo e depois restaurada ao valor anterior; o controle de atualização automática de plugins manteve seu estado anterior.
Um lançamento inicial do auxiliar como nome de módulo falhou antes de executar o arquivo; o bootstrap de arquivo já revisado foi usado com o mesmo interpretador nativo resolvido pelo launcher.
As verificações auxiliares também precisaram distinguir um default não persistido de um valor explícito e a ausência de estado Auto do estado sintético exercitado no Docker; não houve negativa do gerenciador nativo nem relaxamento de guard do produto.

OFF salvo e efetivo foi comprovado antes de desabilitar a revisão anterior, sem estado Auto retido para restaurar e sem alterar rotas.
O scanner nativo classificou a candidata como segura; a instalação ocorreu desabilitada, com 143 arquivos exatos, ref/pin/origem conferidos e settings do plugin preservados.
Somente depois o plugin foi habilitado sem permissão para sobrescrever ferramentas internas e recebeu Observe pelo dispatcher nativo em processo novo.
`status`, `explain` e `config` foram exercitados em JSON e em texto humano padrão; os módulos carregados pertenciam à árvore instalada conferida.
A nova prévia não tinha bloqueios de rota por endpoint/modo padrão, usava o mapa aprovado de `settings.roles` e mostrava as diferenças propostas, sem gravá-las.
Observe salvo e efetivo, ausência de restart pendente e zero inferências extras declaradas pelo plugin foram conferidos; os eventos monitorados não incluíram subprocessos.
O mapa, limites, política e controles de crédito foram preservados, assim como o hash semântico da configuração alheia ao plugin e os fingerprints observados do core/lockfile e dos arquivos preexistentes preservados.
O arquivo de configuração não ficou byte a byte igual ao backup após as escritas nativas; as comparações foram de presença/valores dos settings e do conteúdo semântico restante, não uma alegação de identidade física.
A restauração da aprendizagem foi relida e `hermes config check` retornou exit 0; não há pausa deixada por esta instalação.

As leituras reais de quota, valores do perfil, caminhos e recibos privados não são versionados.
Uma leitura desconhecida manteve a decisão incompleta e não recebeu causa presumida; a observação real não qualifica cobrança nem disponibilidade universal de provedores.
Não foi feito piloto Auto, inferência deliberada, reinício de gateway/Desktop ou mudança no Hermes instalado além do plugin e dos controles nativos temporários descritos.
O ensaio usa o dispatcher que executa o comando, não a janela Desktop; essa superfície não foi exercitada.
Uma sessão/processo já aberto pode conservar módulos anteriores; nenhuma validação end-to-end dessa janela é reivindicada e eventual restart precisa de autorização própria.

HQR-34 registra um achado apenas textual, não corrigido: `quota_router/render.py:575` associa qualquer `decision_incomplete` ao aviso de uso de padrões, mesmo com settings válidos e mapa efetivo vindo de `settings.roles`.
A evidência mantém as duas coisas separadas: o mapa efetivo foi conferido, mas esse aviso não é fiel quando a incompletude vem somente de uma leitura indisponível.
Corrigir o texto, validar a janela Desktop e iniciar Auto são próximos escopos distintos; esta autorização de instalação não os concede nem constitui aceite da S3.

A revisão independente do registro aprovou o delta factual e confirmou HQR-34, sem bloqueantes documentais.
O revisor conferiu o snapshot e os recibos delimitados, sem repetir operações ou testes; seu parecer não qualifica a janela Desktop nem concede correção, restart ou Auto.
A coordenação reconferiu os hashes antes deste registro de fechamento, sem mudar o texto revisado, o produto ou os testes.

No readback final, caches Python surgidos após a conferência inicial fizeram a igualdade do inventário inteiro falhar por arquivos extras; nenhum arquivo publicado estava ausente ou modificado.
Os caches foram preservados e conferidos por cabeçalho e comparação inerte com o código compilado da fonte instalada, sem importar, executar ou remover seu payload.
Todos corresponderam à fonte; a prova distingue os arquivos publicados exatos dos artefatos gerados em runtime e não reivindica uma árvore sem extras depois do uso.

### Correção local de HQR-34 e significado das leituras

O responsável autorizou corrigir o aviso do explain e investigar a leitura Anthropic, sem instalar outra candidata, ativar Auto ou reparar login implicitamente.
A base desta tarefa é `053f9c7e175e130f7c8b45705cba7c20f79df2df`, na mesma branch e worktree de tarefa.
O novo teste isolado reproduziu a afirmação falsa de uso de padrões mesmo com mapa válido, personalização preservada, leitura desconhecida e nenhum bloqueio de rota.
A fixture inicial continha restrições sintéticas adicionais; antes do RED definitivo ela foi reduzida até as pré-condições passarem e a falha ocorrer somente na asserção da mensagem enganosa.
A revisão independente aprovou esse teste e seu snapshot; o RED foi preservado em `e4562053da8de1f7bff349d07cad1f55b1e9bbc6`.

A correção em `quota_router/render.py` troca somente o aviso genérico de incompletude e acrescenta referência a HQR-34.
O diagnóstico dos campos inválidos permanece em `attention()`, que já identifica cada campo e seu fallback individual; não houve alteração de mapa, defaults, política de escolha, créditos, leitores ou guards.
O mesmo teste RED passou e alcançou as asserções finais de ausência de escrita; seus bytes permaneceram idênticos ao commit RED.
Dois controles adicionais caracterizam comportamentos que já passavam na base sem a correção: percentual de esgotamento informado é exibido, ausência de leitura não vira percentual, e fallback de um campo inválido não substitui um mapa válido.
Esses controles também foram executados na base exportada em scratch e não são apresentados como novos REDs.
A regressão completa retornou 220 unitários, 13 integração e 93 harness, exit 0, com 326 IDs únicos qualificados por suíte e nenhum skip.
Não houve alteração de testes protegidos ou de seus suportes: os diffs MDR de testes contra a base e contra o RED estão vazios, além dos novos arquivos identificados.

A investigação operacional foi separada dos testes e limitada a uma consulta pelo leitor nativo read-only, sem inferência nem acesso manual a credenciais.
O observador reteve somente campos permitidos de transporte e quota, recusou mutações fora dos recibos e não permitiu renovação ou outras requisições; os resultados reais e as negativas ficam privados, fora do Git.
Não houve repetição por outra rota após essas negativas; a correção do renderer continuou por ser independente da operação afetada.
Os fingerprints observados da configuração, metadados e revisões instaladas permaneceram iguais antes e depois do diagnóstico.
Essa observação delimitada não comprova a causa histórica de toda leitura indisponível nem a identidade da conta esperada; também não comprova qual janela de franquia está esgotada.

A fonte nativa inspecionada reduz exceções de consulta a `None`, e o plugin recebe apenas a ausência de snapshot, não o motivo HTTP.
Um percentual só pode ser mostrado quando vem de uma leitura válida da janela correspondente; falha de consulta, falta de autenticação e limite de consultas não equivalem a esgotamento numérico.
O contrato atual não permite ao plugin exibir um motivo descartado pelo host; HQR-25 mantém a extensão nativa e o vínculo seguro à conta como escopo próprio, sem inventar percentual ou usar cache sem identidade qualificada.
Reautenticação, mudança no Hermes instalado, publicação, instalação da correção, restart e Auto continuam fora desta autorização.

A revisão independente GREEN aprovou a correção local e as provas, sem achados; conferiu os seis arquivos e os recibos sem executar testes ou repetir o diagnóstico.
A coordenação reconferiu o snapshot no ponto de uso; somente este fechamento documental foi acrescentado depois do parecer, sem mudar os bytes do renderer ou dos testes revisados.

### HQR-35 — backoff e motivos nativos opcionais

Origem: `/quota-router status` no Desktop de trabalho repetia `no_snapshot`, conforme HQR-35 no README, em 2026-11-16.
A autorização desta continuação cobre somente o plugin, seus testes e registros locais, sem publicação, merge, instalação, restart ou consulta a provedores.
A base foi `40fe36769b694326ae6aa64d9b92cf6ea9a96ade`, com worktree limpa; o fetch de `origin` confirmou `main` em `ad113d95604128fcdf9c446e2c5bd9c75bff0860`, ancestral da tarefa e sem commits exclusivos em relação a ela.
A regressão anterior à mudança retornou 220 unitários, 13 integração e 93 harness, todos `OK`, sem skips.

`quota_router/readings.py` agora guarda falhas no mesmo cache por provedor, com `failed_at` e `retry_at` em UTC.
O padrão de 300 s vem do `Retry-After: 300` observado em HQR-25; um `retry_after_s` numérico finito conhecido é limitado a 30–3600 s.
A espera começa depois da tentativa, não em seu início, e não reinicia nem conta nova consulta nos cache hits.
Uma leitura bem-sucedida substitui todos os metadados da falha e volta à regra de frescor normal; `lifecycle.set_mode` continua limpando o cache na troca de modo.
Somente estados desconhecidos produzidos por uma tentativa recebem backoff; leitor ausente, sem tentativa, não cria entrada negativa.

O importador detecta o parâmetro explícito `on_error` por `inspect.signature`, sem chamar o leitor para detectar capacidade.
Sem suporte ou com assinatura não inspecionável, conserva a chamada anterior com `read_only=True` e o motivo `no_snapshot` quando o retorno é `None`.
Com suporte, um callback local a cada tentativa copia apenas `kind` permitido, `status` HTTP inteiro de 100 a 599 e `retry_after_s` numérico finito; nenhum corpo, header, token ou mensagem de exceção é retido.
A normalização distingue `http_429`, `http_401`, HTTP genérico, `timeout`, `network_error` e erro genérico do leitor.
O renderer mostra o motivo conhecido em português e `nova tentativa às HH:MM` no horário local, mantendo o texto genérico anterior quando o host não entrega motivo.
O status e o explain em JSON incluem `reason` e `retry_at`; nenhuma política de elegibilidade ou créditos foi alterada, e desconhecido continua sem capacidade.
Isso não implementa a extensão nativa de HQR-25, nem usa cache nativo sem vínculo seguro à conta.

`red_commits`: `6ae4d048ba42d38c9854dc8c413bdc28c7bee763`.
`protected_test_paths`: `tests/**` e `scripts/run_tests.py`, incluindo os suportes preexistentes e o novo teste após o RED.
`protected_test_approval`: nenhuma alteração solicitada ou aplicada.
Comando RED: `python3 -B scripts/run_tests.py tests.unit.test_s3_reading_backoff`.
O RED executou 20 métodos e retornou `FAILED (failures=42)`, incluindo subtestes, exit 1, sem erros de importação ou sintaxe; as asserções mostram consultas repetidas, prazos ausentes e motivos descartados.
O mesmo arquivo protegido passou 20/20 depois da implementação, com módulos Hermes inertes, relógio fixo e sem consulta real.
O runner completo `python3 scripts/run_tests.py` retornou 240 unitários, 13 integração e 93 harness, todos `OK`, exit 0, sem skips ou warnings: 346 IDs únicos qualificados por suíte.
`compileall` sobre entrada, produto, scripts e testes passou com cache externo descartável; o gate `quota_router.line_gate.check_lines` retornou `[]` nos 146 caminhos versionados.
Gitleaks não encontrou segredos nos oito arquivos da tarefa, e os checks de whitespace passaram.
O OKF fixado manteve o SHA-256 anterior e as seis entradas do manifesto; sua validação retornou `official=conformant`, `profile=pass`, `navigation=valid`, `coverage=complete` e `diagnostics=[]`.
Um aviso inicial de referência Markdown foi corrigido retirando os colchetes ao redor do SHA do RED, sem alterar o pin.
`codegraph sync .` sincronizou os três arquivos de código, na raiz e índice próprios da worktree, com downloads, telemetria e update-check desligados.
Os 113 caminhos Python/YAML do índice coincidiram com os 113 versionados, sem caminhos extras ou ausentes; `pendingChanges` e `pendingRefs` ficaram vazios e `worktreeMismatch=null`.
O índice já recomendava reconstrução por metadados legados antes desta tarefa e continua recomendando; nenhuma reconstrução ou alteração de hooks foi feita.
O backoff é local à instância do plugin e não impede as consultas próprias do Hermes a cada turno.
`protected_test_diff`: vazios em `git diff -M --diff-filter=MDR 40fe367 6ae4d04 -- tests scripts/run_tests.py` e `git diff -M --diff-filter=MDR 6ae4d04 -- tests scripts/run_tests.py`.
O único teste acrescentado contra a base é `tests/unit/test_s3_reading_backoff.py`.
Não houve mudança de testes protegidos, helpers, fixtures, guards ou runner.

A revisão independente desta continuação fica com a coordenação; este worker fez implementação e autochecks, não um parecer independente.
A validação Desktop, a qualificação do futuro callback no host e qualquer publicação ou instalação continuam fora do resultado local e exigem seus próprios gates.

### Validação Observe no Desktop de trabalho, 2026-11-17

Esta seção registra a validação na superfície real autorizada por Guilherme; publicação, merge e aceite da S3 continuam separados.
O plugin instalado está em `233f4be`, com HQR-34 e HQR-35, por checkout local autorizado; essa revisão não foi publicada nem passou pelo instalador nativo.
O Desktop mostrou primeiro `invalid_auto_state` em todos os grupos, porque `<HERMES_HOME>/plugin-data` tinha modo `0775` e o armazenamento privado recusa ancestral gravável pelo grupo.
Com autorização, o ambiente passou a `0755`, sem mudar o guard; depois do restart do Desktop, `auto_available` ficou verdadeiro e `routing_blocks` vazio.
A leitura Anthropic continuou `no_snapshot` porque o backend Desktop hospeda três profiles e executava comandos de plugin sem o escopo de segredos do profile; `get_secret` lançava `UnscopedSecretError`, e o leitor nativo o convertia em ausência.
Esse defeito é do Hermes, foi corrigido por patch local revisado (HQR-37, fora deste repositório) e não exigiu mudança no plugin.
Em 2026-11-17 às 07:58 UTC−03, `/quota-router status` no Desktop leu as duas contas, sem bloqueios, e recomendou Claude pela franquia por ritmo: semana Claude 32% usada com renovação no mesmo dia, Codex 12% usada com renovação em 23/11.
A prévia propôs o mapa aprovado para a conversa e as dez rotas, sem escrita em Observe.
O piloto Auto foi autorizado depois dessa validação; seu resultado fica registrado separadamente.

### Piloto Auto no Hermes de trabalho, 2026-11-17

Guilherme autorizou o piloto e executou `/quota-router mode auto` e `/quota-router apply` no Desktop às 08:01 UTC−03.
O backup anterior está em `<HERMES_HOME>/backups/hqr-s3-auto-pilot-20261117T105930Z/`, com configuração, pasta do plugin e hashes; o diretório de dados ainda não existia.
O plugin aplicou onze grupos, gerações 1 a 11, todos para Anthropic pela franquia, conforme o mapa aprovado e o ritmo da semana Claude que renovava no mesmo dia.
A comparação folha a folha entre a configuração gravada e o backup encontrou 52 mudanças, todas permitidas: os campos dos grupos inscritos e `settings.mode`.
Nenhuma chave fora dos grupos mudou, `groups_out` ficou vazio e não restou diário pendente.
O cron sem pin passou a resolver a conversa, como prevê D12, sem escrita em `cron.*`.
Hooks e idade por tarefa continuam não qualificados; ciclo OFF → restauração → Auto, volta ao Codex depois da renovação Claude, troca de revisão nativa e rollback continuam pendentes.

### Ciclo OFF → restauração → Auto, 2026-11-17

Guilherme executou `/quota-router mode off`; a comparação folha a folha com o backup do piloto encontrou uma única diferença, `settings.mode`, e a conversa voltou a Codex Sol high.
Depois, `mode auto` reaplicou os onze grupos; a nova comparação voltou a 52 mudanças, todas permitidas, sem diário pendente.
A política pedida em seguida, inclusive troca dentro de sessão aberta e trava geral, fica registrada em HQR-38 e não altera o comportamento desta entrega.
