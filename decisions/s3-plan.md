---
type: Delivery Plan
title: S3 — Auto nas próximas tarefas
description: Plano da fatia S3 da emenda HQR-20 — mapa aprovado, escrita dos grupos inscritos pela configuração nativa, linha de base, OFF e recuperação, no alvo de teste e depois no Hermes de trabalho.
status: draft
---

# S3 — Auto nas próximas tarefas

Fatia S3 da [emenda HQR-20](hqr-20-amendment.md), com as decisões de Guilherme de 2026-11-16 registradas na [seção 17 da emenda](hqr-20-amendment.md#17-decisões-de-2026-11-16-para-a-s3).
A S2 foi aceita em 2026-11-16 no candidato `ad113d9` ([entrega](s2-delivery.md)).
Este plano é do agente e passa por revisão independente antes da execução.
As revisões independentes 1 a 5 pediram mudanças, incorporadas nesta versão; a revisão 6 aprovou o plano em `0af5ec4`, sem bloqueantes; o registro está no fim.

## Resultado utilizável

No Hermes de trabalho de Guilherme, com `mode auto`, o plugin aplica no profile `default` a escolha de cada papel: rotas de subagente e modelo da conversa; o cron sem modelo próprio segue a conversa (D12).
Cada tarefa nova que lê a configuração depois de uma decisão aplicada começa no provedor escolhido, com o modelo e o esforço do mapa aprovado.
`/quota-router status` mostra o que foi aplicado, quando, a leitura que sustentou a decisão, a idade dela e o que ficou fora da cobertura.
`mode off` restaura a linha de base dos grupos intactos e relata os outros.
O Auto é de melhor esforço: não veta chamadas, não limita gastos e não muda sessões gerenciadas já criadas.

## Mapa aprovado

O mapa `base` aprovado em 2026-11-16 entra no código como dado, com origem citada; a regra que o gerou (nota por benchmark e custo por tarefa da Artificial Analysis, com empate no benchmark do papel e no índice geral) não é reimplementada no plugin.

| Papel | Codex: modelo · esforço | Claude: modelo · esforço |
|---|---|---|
| conversation | `gpt-6.1-sol` · xhigh | `claude-opus-5-5` · high |
| general | `gpt-6.1-sol` · medium | `claude-opus-5-5` · medium |
| analysis | `gpt-6.1-sol` · high | `claude-opus-5-5` · high |
| strategy | `gpt-6.1-sol` · xhigh | `claude-opus-5-5` · high |
| research | `gpt-6.1-sol` · high | `claude-opus-5-5` · high |
| coding | `gpt-6.1-sol` · xhigh | `claude-opus-5-5` · high |
| review | `gpt-6.1-sol` · xhigh | `claude-opus-5-5` · high |
| deep | `gpt-6.1-sol` · max | `claude-opus-5-5` · xhigh |
| routine | `gpt-6.1-terra` · medium | `claude-sonnet-5-5` · high |
| triage | `gpt-6.1-terra` · low | `claude-sonnet-5-5` · medium |
| cron | segue a conversa (D12) | segue a conversa (D12) |
| extract | `gpt-6-luna` · high | `claude-haiku-5-5` · high |

- `/quota-router config approve-map base` passa a gravar esta tabela em `roles`, com esforço próprio por provedor; hoje o comando copia o esforço da rota atual para os dois lados e não expressa o mapa aprovado.
- Os identificadores de modelo são conferidos no catálogo nativo de cada provedor durante a execução; um identificador ausente no catálogo deixa o papel sem roteamento e o status explica, sem trocar por outro modelo.
- Um papel presente no profile e ausente da tabela continua não roteado (cenário B6).
- As variantes com Fable e Astra continuam propostas não aprovadas; na S3, Fable e Astra ficam inelegíveis mesmo quando disponíveis (cenários B3 e B4, seção 17 da emenda).
- Quando a rota de um papel no profile difere da célula escolhida do mapa aprovado, o Auto grava a célula; essa mudança faz parte do mapa aprovado.

### Cron (R1, D12 e D13)

No host, o cron não tem esforço global próprio: um job sem pin resolve o esforço por `resolve_reasoning_config`, que usa `agent.reasoning_overrides.<modelo>` e depois `agent.reasoning_effort`, o mesmo caminho da conversa (`cron/scheduler.py`, `_resolve_job_reasoning_config`; `hermes_constants.py`, `resolve_reasoning_config`).
Decisão de Guilherme em 2026-11-16 (D12): o cron sem modelo próprio usa a conversa.
Quando `cron.model` e `cron.model_provider` estão vazios, um job sem pin roda no modelo e no esforço da conversa; o Auto da conversa vale para ele.
O plugin não escreve chaves `cron.*`.
O host resolve modelo, provider e esforço do cron separadamente (`cron/scheduler.py`), e o status mostra cada campo com a origem:

| Estado | Modelo | Provider | Esforço |
|---|---|---|---|
| `cron.model` e `cron.model_provider` vazios | conversa | conversa | ver abaixo |
| Padrão completo: os dois preenchidos | padrão | padrão | ver abaixo |
| Padrão parcial: só um preenchido | padrão ou conversa | conversa ou padrão | ver abaixo |
| Job com pin completo de provider e modelo | job | job | ver abaixo |
| Job com pin parcial | job ou herdado | herdado ou job | ver abaixo |

O esforço segue a precedência do host: esforço válido fixado no job; senão `agent.reasoning_overrides` do modelo efetivo do cron; senão `agent.reasoning_effort`, o mesmo valor global que o Auto grava para a conversa.
Por isso o cron usa o mesmo mecanismo da conversa, mas só tem o mesmo esforço efetivo quando não há pin de esforço nem override para o modelo dele; o status mostra o valor e a origem.

O status marca como "parcial" o padrão e o job em que um campo fixo convive com um campo herdado da conversa, porque o par pode ficar incompatível depois de uma decisão (C9); nada disso bloqueia o Auto da conversa.
`consumers.cron` fica sem efeito desde D12: o valor continua aceito para não invalidar configurações salvas, e o status explica que o cron segue a conversa e como fixá-lo; a seção 17 da emenda registra a troca de AC-24 e D4 para esse campo.
Decisão D13: o agente que cria um job de cron analisa a tarefa e escolhe o modelo; sem escolha própria, o job fica sem pin e segue a conversa.
A escolha do agente é um pin completo, com provider, modelo e esforço (`hermes cron create|edit --provider --model --reasoning-effort`), nunca parcial nem só de esforço; um job fixado fica fora do Auto (C8) e não troca de provedor quando a cota aperta.
A regra para os agentes fica na skill compartilhada `cron-model-choice`, fora do código do plugin.

## Escopo

- `quota_router/mapping.py`: tabela aprovada como variante `base`, validação de papéis e identificadores, e `approve-map base` gravando a tabela.
- `quota_router/groups.py` (novo): projeção fechada de cada grupo; só as chaves listadas são lidas para linha de base, diário e comparação.
  - Rota de subagente: na opção de `delegation.backends.model_map` com o nome do papel, `provider`, `model`, `base_url`, `api_mode` e `reasoning_effort`; nome, descrição, fallbacks e opções próprias não são escritos, comparados nem restaurados, e a seção 17 da emenda substitui a linha da seção 16 que os incluía no grupo.
  - Como `model_map.options` é uma lista, a escrita é leitura–modificação–escrita da lista inteira pela camada nativa, sob o lock e com releitura, alterando só os cinco campos da opção do papel; o diário guarda só esses campos; uma edição humana em outra opção feita entre a leitura e a escrita é perdida, dentro da janela de D6.
  - Cron: sem grupo próprio (D12); o status mostra se o cron segue a conversa, se `cron.model` tem padrão próprio e quais jobs têm pin completo ou parcial (C8, C9).
  - Conversa: `model.default`, `model.provider`, `model.base_url`, `model.api_mode` e `agent.reasoning_effort`, escritos com `write_changes` da camada nativa (`hermes_cli/config_backend.py`) na forma de `model_selection_config_updates` (`hermes_cli/model_switch.py`) para provedores de registro.
  - Por D18 (2026-11-16), `model.base_url` e `model.api_mode` são aceitos quando ausentes, vazios ou iguais aos defaults nativos qualificados do provider atual; a aplicação grava os defaults nativos do provider de destino, sem resolver credenciais, e o OFF devolve presença e valor originais.
  - O plugin não chama `switch_model` nem guarda um `ModelSwitchResult`, porque a resolução nativa devolve credenciais (R2).
  - Precondições do grupo da conversa: `model` é um bloco, não a forma curta em texto; sem `model.model` nem `model.name`; sem `api_key`, `api`, `key_env`, `api_key_env` nem `context_length`; sem entrada em `agent.reasoning_overrides` para um modelo do mapa da conversa.
  - Precondição da rota de subagente: sem credencial na opção; endpoint e modo de API ausentes, vazios ou iguais aos defaults nativos do provider atual (D18); endpoint ou modo personalizado tira o grupo do Auto.
  - `model.openai_runtime` não vazio bloqueia conversa e subagentes, inclusive quando o provider atual é Anthropic; esse overlay fica fora do contrato D18.
  - As precondições são conferidas em Observe, na inscrição e de novo, sob o lock, antes de toda escrita, inclusive recuperação e restauração; se uma falhar, o grupo sai do Auto sem escrita, e o status mostra só o nome do campo, nunca o valor.
- `quota_router/apply.py` (novo): inscrição, linha de base, diário, lock, escrita, releitura, divergência, OFF e recuperação (seção 4 da emenda).
  - Linha de base: valor de cada chave da projeção na inscrição, com marca de ausência.
  - Lock: arquivo próprio no diretório de dados do plugin, com `fcntl.flock`, válido entre processos da mesma máquina; não coordena outros escritores (D6).
  - Diário: antes de escrever, grava de forma durável (arquivo temporário, `fsync`, `rename`) o grupo, o estado anterior e o estado alvo de cada chave, com presença; depois da escrita e da releitura iguais ao alvo, grava o novo "último aplicado" e só então apaga o diário.
  - Recuperação, sob o lock, antes de qualquer decisão, com diário pendente:
    - todas as chaves com o valor anterior: a escrita não chegou a valer; o diário é descartado sem escrita, e o último aplicado continua o anterior;
    - todas as chaves com o alvo: a escrita terminou; o alvo passa a ser o último aplicado;
    - mistura de valores anteriores e alvos: escrita interrompida; o ciclo completa para o alvo;
    - alguma chave com um terceiro valor: edição externa; o grupo sai do Auto sem escrita e o status mostra as chaves.
  - Limite: uma edição humana que deixe exatamente uma mistura de valores anteriores e alvos não se distingue de uma escrita interrompida e é completada; uma que volte todas as chaves ao anterior é preservada pela recuperação, mas a decisão seguinte pode escrever o alvo de novo, como em qualquer decisão; o limite fica no status e foi aceito por Guilherme (D15, seção 17 da emenda).
  - Divergência sem diário: qualquer chave diferente do último aplicado tira o grupo inteiro do Auto, sem escrita, na aplicação e no OFF (AC-19).
  - OFF: restaura a linha de base só nos grupos que ainda têm, em todas as chaves, o último aplicado; consumidor desligado em `consumers.*` faz o mesmo com o seu grupo (D4).
  - Estado do plugin (linha de base, último aplicado, diário, marca de Auto, histórico curto) fica no diretório de dados do plugin, fora do `config.yaml` e da pasta do código, com só valores da projeção fechada; nenhum prompt, credencial ou payload de hook.
- `quota_router/compat.py` (novo): o plugin traz uma lista de impressões digitais qualificadas, o SHA-256 do código-fonte de cada função nativa usada (`inspect.getsource`), por host qualificado.
  - A lista cobre cada função chamada e as dependências diretas que mudam o efeito: `config_backend.write_changes`, `write_config_keys`, `read_config_doc`, o backend de arquivo e seu `write_path`, `model_switch.model_selection_config_updates`, `cron/scheduler._resolve_job_reasoning_config`, `hermes_constants.resolve_reasoning_config`, `_explicit_codex` e `_explicit_anthropic` do runtime de providers (D18) e os leitores de `delegation` e de sessão usados no inventário.
  - D18 também vincula o caminho normal OAuth/pool/Anthropic, builders Codex, guards e reexports ativos e a seleção/overlay final; a enumeração executável está em `compat.FUNCTIONS`, com 134 funções por host qualificado.
  - A qualificação também guarda as constantes que mudam o que um consumidor lê, como `FOLLOW_SECTIONS` e `FOLLOW_AGENT_KEYS` de `gateway/session_policy.py`, os defaults de rota e as tabelas OAuth/pool, aliases, modos de provider e hosts nativos; `compat.CONSTANTS` enumera as 19 entradas por host, incluindo `hermes_cli.auth._PROVIDER_ALIASES`.
  - As tabelas de dispatch são inspecionadas por AST, com a atribuição e os campos públicos vinculados sem executar imports, lambdas ou construtores nativos.
  - Ao carregar e antes de cada escrita, compara as impressões; diferença ou fonte indisponível suspende o Auto com zero escritas e aparece no status com o nome da função ou constante (E3).
  - O host do alvo de teste e o Hermes de trabalho, que tem patches locais, são qualificados separadamente; um `hermes update` no Hermes de trabalho suspende o Auto até nova qualificação.
- `quota_router/lifecycle.py`: `mode auto` aceito só com mapa aprovado, configurações válidas e compatibilidade conferida; `/quota-router apply` roda um ciclo; `status` e `explain` mostram aplicado, idade, grupos fora do Auto e cobertura.
- Hooks (seção 5 da emenda): `on_session_open` e `on_kanban_dispatch_tick` disparam um ciclo; `subagent_start` e `on_session_start` registram a decisão usada pela tarefa (AC-22); `api_request_error` registra esgotamento durante uma tarefa (C12).
  - Cada decisão aplicada recebe uma geração crescente, com horário e os valores escritos, no histórico curto.
  - Vínculo comprovado, não observado: o hook só aponta a sessão; a geração usada é determinada pela evidência que o host gravou para ela, nunca pela geração vigente no callback, porque `on_session_open` é entregue depois de a sessão capturar a configuração (`gateway/session_local.py`, `gateway/session_open.py`).
  - Evidência aceita, qualificada no host fixado antes de contar: o horário de criação e a configuração de modelo que o banco de sessões nativo grava para a sessão (módulos `hermes_state_sessions*`), lidos por função nativa de leitura.
  - Regra: a geração usada é a última aplicada estritamente antes do horário de criação, desde que os valores dela batam com a configuração gravada para a sessão e nenhuma geração tenha sido aplicada nos 60 segundos anteriores ao horário de criação (janela de segurança, D17); em qualquer outro caso, "geração indeterminada" (D16).
  - A qualificação da fonte confere, no host fixado, que `started_at` e `model_config` são gravados na criação da sessão e mostra o caminho entre a leitura da configuração e a gravação do horário; `model_config` alterado depois da criação (troca de modelo na sessão) torna o registro "geração indeterminada".
  - Limite aceito por Guilherme (D17): se o host levar mais de 60 segundos entre ler a configuração e gravar o horário de criação, e houver duas aplicações nesse intervalo com valores iguais, o registro pode apontar a geração posterior.
  - Subagente: `subagent_start` traz os ids da sessão-mãe e do filho; o tipo da sessão-mãe (comum ou gerenciada) só é usado se uma fonte nativa qualificada o informar; sem ela, "geração indeterminada"; com ela, a regra acima vale para a sessão do filho (comum) ou para a sessão-mãe (gerenciada, cópia congelada).
  - Cron: a regra acima vale para a sessão da execução de cron.
  - Sessão Bot Chat em `follow_profile_config` segue a geração vigente a cada turno; o registro diz isso, sem idade de geração única.
  - Os identificadores de sessão entram no estado só como SHA-256 com sal local.
  - De cada payload só entram no estado campos fechados: horário, provedor, modelo, papel, tipo de evento e classe de erro; nunca mensagens, prompts, headers ou corpo.
  - Cada hook é qualificado no host fixado antes de contar como cobertura; um hook não qualificado vira limite visível no status, não cobertura presumida.
  - O callback nunca levanta exceção para o host, aceita `**kwargs` e não bloqueia a sessão.
- Ausência do plugin (AC-23, E1): a marca de Auto e o horário do último ciclo ficam no diretório de dados.
  - Ao carregar de novo, o status mostra "Auto declarado; plugin ausente ou sem ciclo de X a Y" e a última decisão aplicada.
  - Enquanto o plugin está desabilitado ou falhou ao carregar, o diagnóstico é o nativo: `hermes plugins list` mostra o estado, e `mode: auto` continua no subtree do plugin.
  - A remoção exige OFF efetivo (E2); remover sem OFF apaga o subtree pela via nativa, a configuração fica com a última decisão aplicada e o diretório de dados guarda a marca; esse limite fica documentado.
- `plugin.yaml`: `provides_hooks` com os hooks acima e descrições sem "AUTO unavailable"; versão `0.3.0rc1`.
- Documentação: `docs/s3-operations.md`, `docs/testing.md`, `docs/compatibility.md`, README e registro de entrega `decisions/s3-delivery.md`.

## Testes protegidos

A S3 muda uma asserção da S1 em `tests/integration/test_export.py`, linha 23: `self.assertEqual(manifest["provides_hooks"], [])`.
Mudança aprovada por Guilherme em 2026-11-16 (D14): a linha passa a exigir exatamente a lista de hooks declarada pela S3; o resto do arquivo fica igual.
Como os hooks só são registrados com o Auto efetivo, os contextos falsos de `tests/integration/test_export.py` (linhas 50 a 60) e de `tests/unit/test_default.py` (linhas 11 a 34), reaproveitado por `test_modes.py`, `test_failures.py`, `test_identity.py` e `test_concurrent.py`, nunca recebem `register_hook`: em todos eles não há mapa aprovado e o Auto não fica efetivo.
Se o host recusar registro de hook depois da carga, a execução para e pede aprovação específica para mudar esses contextos, com o trecho exato.
Nos mesmos testes, `auto_available` fica falso, `mode auto` é recusado sem gravar e o `auto` salvo continua erro de integridade.
`tests/installed/lifecycle.py` continua como prova da S1 e roda contra a revisão da S1.

## Cenários e provas

Critérios: AC-18 a AC-25, com AC-16 e AC-17 preservados da S2.
U = teste de unidade com relógio, leituras, configuração e diretório de dados sintéticos; I = integração com a camada nativa de configuração sobre um `HERMES_HOME` temporário; T = ensaio instalado no alvo de teste com o Hermes fixado e sem inferência.

| Cenário | Prova |
|---|---|
| A1–A13, B1–B6 (S2/S3) | U: decisão por cenário; I: a escrita correspondente ou nenhuma escrita; T: A2, A3, A5 e A13 |
| B3, B4 | U e T: Fable e Astra inelegíveis mesmo disponíveis |
| C1 | T: resolução nativa de sessão nova dá o provedor, modelo e esforço escolhidos |
| C2 | T: sessão de conversa aberta antes mantém o modelo |
| C3 | T: sessão em `follow_profile_config` resolve o modelo novo no turno seguinte |
| C4 | T: subagente lançado por sessão comum nova e aberta resolve a rota decidida |
| C5 | T: sessão gerenciada criada antes; workers antigo e novo resolvem a cópia; status mostra fora da cobertura |
| C6 | T: sessão gerenciada criada depois resolve a rota decidida |
| C7 | T: com `cron.*` vazio, tick sem pin resolve modelo, provider e esforço da conversa decidida; com padrão completo, modelo e provider do padrão e o esforço pela precedência do host, inclusive o controle com override para o modelo do cron diferente do esforço da conversa; com padrão parcial, o status marca "parcial"; `consumers.cron` desligado não muda nada e o status explica |
| C8 | U e T: job com provider, modelo e endpoint fixados não muda |
| C9 | U e T: job com pin parcial aparece no status com o par que formaria com a conversa decidida |
| C10 | T: modelo explícito em `/model` e em chamada de subagente prevalece |
| C12 | T: erro de cota sintético no hook `api_request_error` é registrado; sem hook qualificado, limite no status |
| D2–D4, D6, D7 | U e I: inscrição, OFF, consumidor desligado, nova linha de base, edição humana |
| D9 | I: dois processos reais disputando o lock; nenhum grupo misturado |
| D10 | I: processo morto em cada ponto da escrita; os quatro casos da recuperação, inclusive queda seguida de edição que volta tudo ao anterior (preservada) e de edição com terceiro valor (grupo fora do Auto) |
| D11, D12 | U: idade mostrada; valor inválido suspende escritas |
| E1 | T: desabilitar com Auto; configuração fica; ao reabilitar, status mostra a ausência |
| E2 | T: remoção sem OFF recusada pelo fluxo do produto; limite nativo documentado |
| E3 | U: controles negativos com função alterada sem mudar assinatura e com uma constante alterada suspendem o Auto com zero escritas; T: impressões do host fixado conferem |
| AC-22 | U e T: sessão criada em A₁, com B e depois A₂ aplicados antes da entrega do hook, registra A₁ ou "geração indeterminada", nunca A₂; captura em A₁ seguida de B e A₂ antes do horário de criação, dentro da janela, dá "geração indeterminada"; sem aplicação na janela, registra A₁ com a idade dela (controle positivo); A → B → A distingue as gerações pelo horário; troca de modelo na sessão depois da criação dá "geração indeterminada"; filho com sessão-mãe de tipo desconhecido e fonte não qualificada dão "geração indeterminada" |
| Credenciais (R2, N2) | U e I: com segredo sintético em `api_key`, `api`, `key_env` e `api_key_env`, um de cada vez, presente na inscrição ou acrescentado depois, nenhuma escrita acontece e o segredo não aparece em estado, diário, status ou diagnóstico |
| Rotas (N3, O3) | I: escrita da opção do papel preserva as outras opções e os campos fora da projeção; edição humana em fallback não tira o grupo do Auto |

```sh
python3 -m unittest discover -s tests/unit -p 'test_*.py' -v
python3 -m unittest discover -s tests/integration -p 'test_*.py' -v
python3 -m unittest discover -s tests/harness -p 'test_*.py' -v
python3 -m compileall -q __init__.py quota_router
okf --root . --json validate --profile per-repo --gate both
```

Seguir RED/GREEN com testes novos.
As leituras de cota no alvo de teste são substituídas dentro do processo do runner por snapshots sintéticos no formato do host; o plugin não ganha porta de teste.

## Ensaio instalado no alvo de teste

Runner novo `tests/installed/s3_auto.py`, com candidato e revisão de rollback como argumentos, no alvo Docker já admitido.
Toda troca de revisão segue a sequência do produto: OFF conferido, desabilitar, instalar com `--force --ref <SHA40>`, scanner `safe`, arquivos iguais à revisão, habilitar e smoke.

1. Instalar o candidato e conferir as impressões digitais do host do alvo.
2. Observe: decisão igual à que o Auto aplicaria e zero chaves fora do subtree (AC-17).
3. `approve-map base` e `mode auto`: linha de base capturada, grupos escritos, releitura igual; esforço resolvido conferido na conversa e num job de cron sem pin.
4. Cenários C da tabela pela resolução nativa.
5. Cenários A2, A3, A5 e A13 por snapshots sintéticos.
6. Edição humana de uma chave: grupo fora do Auto, sem sobrescrita.
7. Escrita interrompida e restart: recuperação.
8. `mode off`: linha de base restaurada nos grupos intactos, inclusive chave ausente.
9. E1: desabilitar com Auto declarado e reabilitar.
10. Rollback para `ad113d9` pela sequência acima, smoke em Observe, e volta ao candidato.

## Publicação

A instalação nativa precisa da revisão no GitHub.
O candidato é montado como árvore limpa sobre `main` (`ad113d9`), sem histórico privado, depois da revisão aprovada.
Push da branch do candidato, merge e release dependem de pedido específico a Guilherme.

## Piloto no Hermes de trabalho

O piloto em Auto grava a configuração real do profile `default` e depende de autorização específica de Guilherme, pedida depois do ensaio instalado.

1. Backup datado de `config.yaml`, da pasta do plugin e do diretório de dados do plugin, com hash.
2. Qualificar as impressões digitais do Hermes de trabalho, que tem patches locais, e a resolução da conversa e de um job de cron sem pin, só com leitura.
3. Troca de revisão: S2 em OFF conferido, desabilitar, restart autorizado dos processos que carregam o plugin, instalar o candidato com `--force --ref`, scanner `safe`, arquivos iguais, habilitar, restart autorizado e smoke em Observe.
4. `approve-map base`; conferir no status a tabela aprovada e a decisão.
5. `mode auto` e `apply`; conferir por releitura que só os grupos inscritos mudaram e que o resto da configuração tem o hash do backup.
6. Ciclo `off` → linha de base restaurada → `auto` de novo.
7. Rollback ensaiado pela mesma sequência do passo 3 até `ad113d9` em Observe, e volta ao candidato em Observe.
8. `mode auto` de novo, conferência do mapa, da inscrição e do estado efetivo por releitura, e manter em Auto para a DEMO.

Parar se o scanner não der `safe`, se algum arquivo divergir, se uma chave fora dos grupos mudar, se as impressões não conferirem ou se o Hermes não carregar; nesse caso, OFF, restaurar a linha de base e voltar à revisão `ad113d9` em Observe.
Restart de gateway, dashboard ou backend do app desktop exige autorização e ausência de tarefa em andamento.

## Caminhos e limites

Caminhos permitidos: `__init__.py`, `plugin.yaml`, `quota_router/`, testes novos em `tests/unit/`, `tests/integration/` e `tests/harness/`, `tests/installed/s3_auto.py`, a mudança aprovada em `tests/integration/test_export.py`, `docs/`, `decisions/` e README.
Não objetivos: interceptar chamadas, retries, fallbacks ou auxiliares; mudar sessões e workers já abertos; Fable e Astra como candidatos; extensão do core (HQR-23, HQR-25); outros profiles (S4).
Proibido: monkey-patch no plugin, chamada a funções nativas que devolvem credenciais, leitura de tokens ou auth stores pelo plugin, inferência própria, escrita fora dos grupos inscritos, do subtree e do diretório de dados do plugin, mudança em testes protegidos sem aprovação.

## Revisão

| ID | Achado da revisão 1 | Tratamento nesta versão |
|---|---|---|
| R1 | Cron sem esforço global próprio | D12 e D13: cron sem pin segue a conversa; plugin não escreve `cron.*`; prova do esforço resolvido |
| R2 | `switch_model` devolve credenciais | Escrita por `write_changes` com projeção fechada; inscrição recusada com credencial inline; prova com segredo sintético |
| R3 | Recuperação contra divergência | Diário com anterior e alvo; terceiro valor é edição externa; ordem durável |
| R4 | Assinatura não detecta mudança | Impressão digital do código-fonte por host qualificado; controle negativo |
| R5 | B4 contra Astra inelegível | Seção 17 da emenda e cenário B4 reconciliados |
| R6 | Defasagem e C12 sem prova | Hooks de registro com campos fechados, gate de qualificação e matriz cenário → prova |
| R7 | Status ausente sem plugin | Marca durável, relato ao recarregar, diagnóstico nativo e limite da remoção |
| R8 | `register_hook` nos contextos protegidos | Registro só com Auto efetivo; parada com pedido de aprovação se o host recusar |
| R9 | Atualização sem desabilitar | Sequência OFF, desabilitar, restart, instalar, habilitar em toda troca de revisão |

| ID | Achado da revisão 2 | Tratamento nesta versão |
|---|---|---|
| R3 | Recuperação sobrescrevia edição que voltava ao anterior | Quatro casos de recuperação; todas no anterior descarta o diário; limite residual aceito por Guilherme (D15) |
| R6 | Idade global não prova a decisão usada | Gerações; registro antes do ciclo; correlação pelo modelo do payload; subagente por horário com limite documentado; prova com decisão defasada |
| N1 | `consumers.cron` e padrões parciais | Tabela de origem por campo; `consumers.cron` sem efeito e explicado; seção 17 |
| N2 | Alias `api` e precondições só na inscrição | Recusa de `api`, formas curtas e aliases do nome; precondições antes de toda escrita; provas por alias |
| N3 | Fallbacks e opções no grupo contratado | Seção 17 substitui a linha da seção 16; prova de que fallback editado não tira o grupo |
| N4 | Skill com pin só de esforço | Skill alinhada a D13: pin completo ou nenhum |
| O1 | Cobertura das impressões | Lista com dependências diretas; fonte indisponível suspende; constantes na revisão 3 |
| O2 | Auto depois do rollback | Passo 8 do piloto |
| O3 | Escrita de lista | Leitura–modificação–escrita da lista sob lock; limite de D6 |

| ID | Achado da revisão 3 | Tratamento nesta versão |
|---|---|---|
| R6 | Correlação por modelo ambígua; filho de sessão gerenciada antiga | Vínculo por sessão com id opaco; filho pela sessão-mãe; "geração indeterminada" sem vínculo; provas A → B → A e sessão gerenciada antiga; aceito por Guilherme (D16) |
| N5 | Esforço do cron com override do modelo próprio | Precedência real do host na tabela e no status; controle com override diferente |
| O1 | Constantes fora das impressões | `FOLLOW_SECTIONS` e `FOLLOW_AGENT_KEYS` qualificados; controle negativo |

| ID | Achado da revisão 4 | Tratamento nesta versão |
|---|---|---|
| R6 | Vínculo nascia com a geração vigente no callback | Geração determinada pelo horário de criação e pela configuração gravados pelo host; tipo da sessão-mãe só por fonte qualificada; tudo o mais é "geração indeterminada" (D16); prova A₁ → B → A₂ |

| ID | Achado da revisão 5 | Tratamento nesta versão |
|---|---|---|
| R6 | Janela entre leitura da configuração e gravação do horário de criação; `model_config` mutável | Janela de segurança de 60 s e limite aceito por Guilherme (D17); mutação depois da criação dá "geração indeterminada"; controles negativo e positivo |
