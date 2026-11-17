---
type: Delivery Record
title: HQR-38 — entrega local da política de troca e da rede de segurança
description: Implementação HQR-38, demonstração offline e piloto real no Hermes de trabalho com Observe, Auto, sessão nova, subagente e cron em Opus e OFF com restauração; fallback aceito com prova de código e testes e fatia aceita por Guilherme em 2026-11-17; erro de cota real segue como observação natural.
status: stable
---

# HQR-38 — entrega local

Implementação da [especificação HQR-38](hqr-38-spec.md), aprovada por Guilherme em 2026-11-17 segundo o pedido de execução do coordenador.
O cabeçalho da especificação ainda diz "proposta"; esta entrega não alterou os bytes dela.
No registro inicial abaixo, nada havia sido publicado, instalado ou ativado; nenhum provedor havia sido consultado e nenhuma configuração real havia sido lida ou escrita.
O resultado posterior e o estado corrente estão nas seções de piloto real e de recuperação; os relatos das outras seções preservam o estado das versões e dos ensaios ali identificados.

## Piloto real no Hermes de trabalho, 2026-11-17

Guilherme pediu o piloto no próprio Hermes de trabalho e autorizou a substituição da versão instalada, depois de ser informado de que o retorno à versão antiga com estado migrado só tinha prova sintética.
A sequência autorizada foi backup, OFF com restauração, instalação da candidata, Observe com leitura de cotas e só então Auto.
Os backups privados de configuração, plugin e estado ficaram fora deste repositório.

### Saída da versão anterior

- A versão instalada antes do piloto era `233f4be`, em Auto, controlando a conversa e as dez rotas de subagentes.
- O OFF enviado pelo CLI respondeu `mode_effective = off` sem o bloco `applied`; a releitura do estado ainda mostrava Auto declarado e 11 grupos ativos, e a troca foi suspensa.
- O OFF enviado no Desktop respondeu com `applied`, Auto não declarado e grupos inativos; a releitura física da configuração e do estado confirmou a restauração, sem diário pendente.
- A causa da divergência entre as duas instâncias não foi comprovada; a fonte é compatível com uma instância sem engine associado ao estado, que responde OFF sem restaurar.

### Instalação e Observe

- A candidata `cc878bc` foi instalada pelo instalador nativo, com HEAD e arquivos rastreados conferidos, modo salvo `observe` e plugin habilitado.
- Um CLI novo carregou a candidata, mas a instância do Desktop continuou executando o código anterior: o status listava como bloqueio as 18 funções da rede de segurança e não trazia `quota.states`.
- Desabilitar e habilitar o plugin no gerenciador de plugins do próprio Desktop recarregou a instância; o status passou a trazer `source_qualified = true`, `quota.states`, `safety_net` e nenhum bloqueio de rota.
- A leitura real classificou Claude e Codex como Livres; créditos Anthropic desligados e créditos OpenAI permitidos.
- A política `pacing` propôs Claude para a conversa e para as dez rotas, com redes de segurança Claude → Codex.

### Auto, sessões e OFF

- Auto aplicou a conversa em Claude Opus com esforço high, as dez rotas pelo mapa aprovado e 11 cadeias `fallback_providers`, sem grupos excluídos; o ciclo seguinte manteve a escolha.
- A releitura da configuração em disco conferiu o modelo, o provedor, o esforço e a cadeia da conversa.
- Uma sessão nova do Desktop, aberta depois da decisão e sem escolha manual, abriu em Claude Opus pela Anthropic; o `model_config` da sessão no banco de sessões não tinha `composer_override_profile`, e Guilherme confirmou a tela.
- O mesmo `model_config` registrou esforço `low`, diferente do `high` aplicado pelo Auto à conversa; a origem desse esforço não foi investigada (HQR-42).
- As sessões em Sol vistas logo antes tinham sido criadas antes da aplicação do Auto.
- A sessão já aberta, com escolha manual de Sol registrada, permaneceu em Sol até `/model reset`, conforme D-28: sessão fixada só troca pela rede de segurança.
- O OFF no Desktop restaurou modelo, provedor, esforço, rotas de subagentes e a presença e o valor de `fallback_providers`, conferidos contra o backup anterior ao Auto; Auto não declarado, nenhum grupo ativo e nenhum diário pendente.
- Depois da prova de OFF, Guilherme religou o Auto, que permanece em uso no Hermes de trabalho.

### Limites do piloto

- Nenhum fallback por erro de cota real foi executado; o piloto de D-28 com sessão fixada recebendo erro do Codex continua pendente, sem esgotar franquia de propósito.
- Auditoria de código do Hermes instalado, sem rede e sem escrita no Hermes, rastreou o caminho erro de cota → classificação → pool de credenciais → `fallback_providers` para chat fixado, subagente por rota e cron sem pin.
- Os logs preservados registram 435 testes do Hermes aprovados offline numa cópia temporária da árvore, já apagada, selecionados por arquivo e por `-k` com `-m 'not integration and not live'`; incluem classificação de erros, pool de credenciais, restauração do primário e cadeias por superfície, não só fallback em sentido estrito.
- Uma seleção do agendador não coletou testes (código 5); outros 11 testes aprovados aparecem só na transcrição abreviada do auditor, fora dos logs de lote — 4 de poda da cadeia na troca de modelo, na cópia, e 7 do plugin advanced-delegation, no diretório instalado do plugin — e não entram na contagem.
- A auditoria concluiu, por leitura e testes, que 429 `usage_limit_reached` do Codex, 429 `rate_limit_error` da Anthropic com uma conta no pool, 402 e falha leve do Codex disparam a cadeia; sobrecarga, contexto longo e pool com outra conta disponível não disparam de imediato.
- Na troca, a cadeia pula a entrada que resolve ao mesmo backend ativo e entradas indisponíveis, como pool em espera longa; ela não remove o primário: Opus primário cai em Sol; Sol fixado cai em Opus e, se Opus também falhar no mesmo turno, Sol pode ser tentado de novo quando a conta não estiver em espera longa.
- A volta ao primário ocorre num turno seguinte depois da espera do provedor, no chat; subagentes e crons começam cada execução no primário.
- Lacunas da auditoria: nenhum teste existente leva um 429 real da Anthropic ou do Codex de ponta a ponta até o fallback, e a combinação de sessão fixada com `/model` e a volta após falha leve só foram vistas por leitura; o parecer completo do auditor não ficou preservado, apenas a transcrição abreviada e os logs.
- Com o Auto religado, um subagente na rota `general` respondeu numa chamada; o registro da sessão filha mostra Claude Opus pela Anthropic, a rota aplicada pelo Auto, sem conferência do esforço efetivo.
- Um cron de teste sem modelo fixado, criado para execução única, terminou com status `ok`; a sessão do cron registrou Claude Opus pela Anthropic, seguindo a conversa aplicada pelo Auto.
- `installed_verified` continua falso; o piloto não é aceite de produção, merge, push nem publicação.
- A recarga do Desktop após a instalação dependeu de ação manual no gerenciador de plugins (HQR-41).

### Decisão de Guilherme sobre o fallback, 2026-11-17

Decidido: o fallback por erro de cota fica aceito para esta fatia com a prova de leitura de código e dos testes offline do Hermes registrada acima.
O erro de cota real não será provocado; quando ocorrer naturalmente no uso, será observado e registrado.
A lacuna de ponta a ponta com erro real permanece declarada e não vira prova.
Origem: proposta do coordenador na conversa de 2026-11-17, em quatro passos: "Aceitar o fallback como comprovado por código e testes, deixando o erro de cota real como observação natural no uso"; "Fazer a revisão independente da fatia"; "Obter seu aceite"; "Sanear o repositório antes da publicação e depois fazer merge e push".
Guilherme respondeu "pode seguir com os passos".
Merge e push fazem parte da proposta, mas dependem dos passos de revisão e aceite, ainda não concluídos neste registro, e da pergunta antes de cada merge e push exigida pelo fluxo Git do responsável.

### Aceite de Guilherme, 2026-11-17

Decidido: Guilherme aceitou a fatia HQR-38 depois da revisão independente do registro do piloto, aprovada na segunda rodada de correção (`APPROVE_PILOT_RECORD`).
Na mesma resposta autorizou o merge por squash na `main` e o push ao repositório remoto, e classificou HQR-42 como aceitável.
Texto da resposta: "1. sim 2. sim 3. sim ; hqr-42 - não tem problema é aceitável", às perguntas sobre aceite da fatia, squash merge e push.
O aceite não converte em prova o erro de cota real nem `installed_verified`, que continuam como limites declarados.

## Recuperação do ensaio instalado, 2026-11-17

Guilherme autorizou prosseguir com o pacote de recuperação após a revisão independente que consolidou os erros de preparação, a transição do cadastro e dos testes protegidos e a nova tentativa de Auto no Docker.
A resposta correlacionada foi `0k, prossiga`; ela não autoriza produção, provedores reais, merge, push ou publicação.
A base desta recuperação é `9677d1c8f77c952cba5c86b017d0ee759575f79c`.
O incremento é crítico por alterar a qualificação que condiciona as escritas Auto; a revisão do delta deve cobrir geral, segurança e testes, sem reabrir automaticamente a implementação SOL-04 já revisada.

O primeiro ensaio parou na preparação de dependências públicas; a repetição expressamente autorizada habilitou advanced-delegation e o roteador, sem rede no alvo.
A tentativa seguinte de Auto foi recusada com `host_requalification_required`, permaneceu em OFF e não foi repetida.
A inspeção AST posterior mediu diretamente 152 funções e 19 constantes no alvo: os 134 hashes e as 19 constantes anteriores coincidiram, e as 18 novas funções foram encontradas.
O cadastro novo deve usar essas medições, não preencher lacunas copiando outro host.
A revisão Git do Hermes nesse alvo não foi identificada; a revisão declarada e a correspondência por fonte não são prova de uma revisão Git medida.

### Escopo controlado da correção

- Atualizar somente a entrada Docker em `quota_router/qualified_hosts.json`, preservando os hashes anteriores, as constantes e os limites de cobertura.
- Em `tests/unit/test_s3_docker_qualification.py`, substituir as expectativas de cadastro pendente/incompleto por cadastro medido completo e testar a entrada real, sem completá-la com outra entrada.
- Em `tests/unit/test_hqr38_safety_net_fingerprints.py`, conferir as funções Docker medidas e manter a recusa de uma cópia sintética explicitamente marcada como pendente, com revisão legível e sem revisão.
- Preservar os controles negativos de revisão, função ausente/adulterada, conjunto parcial e marca pendente; não alterar os guards nem o algoritmo de seleção.
- Corrigir o roteiro privado: imports existentes, backend `model_map`, endpoints/modos nativos, modelos derivados do mapa aprovado e cadeia compartilhada com todos os candidatos elegíveis.
- Conferir preparação e preflight antes de uma nova ativação Auto: identidade instalada, dependências/cache, dados sintéticos, cadastro, configuração, dispatcher, hook, baseline, recibos e recuperação.

O fluxo autorizado da demonstração é OFF, Auto com 94% na janela curta, hook nativo com 95%, troca conforme o mapa, leitura nativa da cadeia e OFF com restauração semântica exata, incluindo ausência de campos.
O transporte das leituras e o avanço do relógio são sintéticos; dispatcher, configuração, hooks e escritas devem ser os nativos do Hermes.
Leitura e normalização da cadeia não comprovam ativação de fallback com provedor, inferência, uma janela real do Desktop ou recuperação de chamada em andamento.
O piloto real do chat fixado e a instalação de produção continuam dependendo de autorização própria.

Estado inicial desta recuperação: medições preservadas, correção em preparação; nenhuma nova tentativa de Auto executada.
Os resultados posteriores devem ser acrescentados a esta seção, sem apagar as recusas anteriores.

### Resultado observado da demonstração offline

A candidata instalada foi `cc878bc0084c76e9fb7af56a3dd01ca1c583c1b4`, depois da revisão geral, de segurança e de testes do delta de qualificação, sem achado bloqueante.
O SDK nativo desabilitou o roteador anterior, instalou essa revisão por um transporte Git local raso de objetos originais, sem habilitar, e habilitou somente depois da conferência dos 169 arquivos e do HEAD instalado.
O namespace usou a imagem fixada, rede ausente, usuário 1001, raiz somente leitura e dados sintéticos próprios; não reutilizou configuração nem contas do Hermes de trabalho.
O aviso de ferramentas opcionais ausentes ou desatualizadas na imagem permaneceu registrado; essas ferramentas não foram instaladas para eliminar o aviso.

A primeira preparação desta rodada detectou labels sintéticos inválidos e parou com `unknown_window_label`, antes de tentar Auto.
O roteiro foi corrigido para os labels nativos e as durações publicadas nos slots Codex, sem alterar o parser, os fingerprints ou os guards do produto.
Dez verificações puras ou inertes conferiram o original recusado, 94/95 nos dois provedores, duração ausente recusada e quatro combinações de recuperação modelada.
A preparação nativa corrigida saiu com 0: OFF, backend `model_map` compatível, créditos desabilitados para os dois provedores, 94 Livre, 95 Pressionado e canário recebido pelo hook SDK.
A rechecagem independente limitada aprovou o roteiro corrigido para uma única tentativa offline; isso não aprovou produção.

| Etapa observada | Conversa | Rota `general` | Cadeia nativa lida |
| --- | --- | --- | --- |
| OFF inicial | Codex `gpt-6.1-sol`, esforço low | Codex `gpt-6.1-sol`, esforço low | Ausente |
| Auto com 94% na janela curta Codex | Codex `gpt-6.1-sol`, esforço xhigh | Codex `gpt-6.1-sol`, esforço medium | Codex, Claude |
| Hook SDK com 95%, após avanço sintético de 65 s | Claude `claude-opus-5-5`, esforço high | Claude `claude-opus-5-5`, esforço medium | Claude, Codex |
| Releitura do fallback | Primária Claude preservada | Primária Claude preservada | Mesma ordem pela leitura raiz e pela leitura de escopo |
| OFF final | Configuração inicial restaurada | Configuração inicial restaurada | Ausência original restaurada nos dois grupos |

O roteiro conferiu a troca depois do hook e antes do comando `status` seguinte, para que esse comando não fosse confundido com o gatilho da troca.
Os quatro comandos SDK registrados retornaram `ok: true`; houve exatamente um `/quota-router mode auto` nesta rodada e nenhum replay.
O cliente `docker exec` atingiu o timeout de 120 s, portanto o código de saída do processo da demonstração não foi capturado e não é apresentado como 0.
Uma leitura posterior encontrou os cinco registros e o recibo completo; do marcador anterior ao Auto até esse recibo decorreram aproximadamente 119,58 s, sem contar a inicialização anterior ao marcador.
A coordenação releu a configuração integral e confirmou igualdade semântica fora das settings próprias do roteador, igualdade da projeção visível inicial/final e ausência das duas chaves de fallback.
Também confirmou `settings.mode = off`, `auto_declared = false`, quatro grupos inativos sem intenção pendente, ausência do processo de demonstração e parada do contêiner.
Esses readbacks comprovam o comportamento observado e a restauração, não um encerramento com código de saída conhecido.

O recibo observado tem SHA-256 `e98882515ada0a9894caa1b29b1f679fe5ad598d633a2295cf929f023d90825d`.
O roteiro corrigido tem SHA-256 `9ce0c0762f43283847ac8b402b3f4ee29c0dd3c5feb83500d7423fb7d74a16e9`.
Os recibos, os erros anteriores, os scripts privados e os hashes foram preservados em arquivo privado durável, fora da árvore pública.

A regressão do delta de qualificação passou com 16 métodos focais e 470 execuções canônicas, divididas em 353 de unidade, 19 de integração e 98 de harness, sem falhas ou skips e com exit 0 do runner.
Essas execuções cobrem os mesmos bytes de código, testes e cadastro da candidata instalada; os registros documentais posteriores não são apresentados como versões novamente executadas.
OKF, compilação, limite de linha, whitespace, scan staged e sincronização offline do CodeGraph passaram antes do commit da candidata.

### Limites e próximo gate

Foi demonstrada a integração instalada offline pelo dispatcher SDK, com escrita e releitura nativas, entrega de hook e restauração; não foi exercitada uma janela real do Desktop.
As cotas e o relógio eram sintéticos; os textos nativos que nomeiam APIs de uso descrevem a origem simulada e não comprovam consulta a essas APIs.
O catálogo models.dev estava indisponível ou vazio, e os IDs de modelo não foram verificados por inferência.
Nenhum fallback com provedor foi executado, nenhum subagente realizou inferência e nenhuma cobrança ou franquia real foi consultada.
A revisão Git do SDK continuou não identificada; a compatibilidade foi aceita pelo opt-in existente de correspondência de fonte, não por SHA Git medido.
Os checks inertes de recuperação não comprovam recuperação nativa sob qualquer falha; falha ao gravar o recibo ou em `close()` ainda pode substituir a exceção propagada.
O Hermes de trabalho não recebeu esta candidata, e o runner instalado legado com seus demais cenários não foi reexecutado por este roteiro.
O próximo gate é definir e autorizar o piloto real e seu destino; aceite, produção, merge, push e publicação continuam pendentes.

## Identidade

- Branch: `hermes/2026-11-17-hqr-38`, sobre a base `3922ddd`.
- RED: `61d5d79` (`wip: test:`); os cinco arquivos novos falharam antes da implementação por funções e campos ausentes e pelas decisões antigas, como A17 indo para créditos.
- GREEN: `07571e2`, com a implementação e os ajustes listados de testes anteriores.
- Documentação: commit seguinte a este registro.

## O que mudou

- Política (D-31): estados por provedor; Pressionado só é candidato sem Livre; entre Pressionados vale a folga semanal com histerese dentro do grupo; créditos só depois dos dois grupos.
- A17: com as duas janelas de 5 h entre 95% e 100%, a escolha fica na franquia pela folga semanal; antes ia para créditos do Codex.
- Rede de segurança (D-28, D-29): grupos `fallback:conversation` e `fallback:<papel>` com a mesma linha de base, diário, releitura, OFF exato e exclusão por edição externa da S3.
- Leituras: A22, A23, A26, A27, A29, A31, A32, A34 e A38, como descrito na [operação HQR-38](../docs/hqr-38-operations.md).
- Texto: estado por provedor e rede de segurança em português; o JSON traz `quota.states`, `states` e `safety_net` por decisão e `applied.safety_net`.
- Cenários A16–A39 e F1–F5 acrescentados ao [mapa de cenários](hqr-20-scenarios.md).

## Testes

- Antes: 240 unidade, 13 integração e 93 harness, todos verdes, sem skips.
- Depois: 295 unidade, 19 integração e 93 harness, todos verdes, sem skips, pelo runner `python3 scripts/run_tests.py`.
- Arquivos novos: `tests/unit/test_hqr38_policy.py`, `tests/unit/test_hqr38_readings.py`, `tests/unit/test_hqr38_fallback_groups.py`, `tests/unit/test_hqr38_render.py` e `tests/integration/test_hqr38_fallback.py`.
- A matriz de pares cobre Claude e Codex com 5 h + semanal e só semanal, cada lado passando por Livre, Pressionado e Esgotado.
- Depois do RED, os testes novos receberam dois ajustes: os grupos da rede de segurança passaram de `applied.groups` para `applied.safety_net`, e um caso de A23 no texto foi acrescentado ao arquivo de render.

## Testes anteriores alterados pela mudança aprovada

- `tests/unit/test_s2_policy.py`, `test_inconsistent_window_never_becomes_paid_capacity`: o motivo de crédito passa a ser `credits_limits_not_verifiable`, porque a inconsistência não bloqueia créditos por si só (A23); a escolha continua nenhuma.
- O mesmo arquivo, `test_exhausted_inconsistent_window_never_becomes_paid_capacity`: com créditos verificados e permitidos, a escolha passa a ser créditos do Codex (A23).
- `tests/unit/test_s2_readings.py`, `test_unknown_states`: o exemplo de `malformed_window` passa de 120% para -5%, porque 120% agora é Esgotado (A32).
- `tests/unit/test_s2_render.py`, `test_unusable_readings_never_advertise_credits`: o caso inconsistente sai deste teste (A23) e passa a `tests/unit/test_hqr38_render.py`.
- `tests/integration/test_s3_scenarios.py`, cenário A6: Claude com 5 h em 96% e Codex esgotado sem créditos passa a escolher Claude (D-31).

## Desvios e limites

- As entradas de `fallback_providers` têm só `provider` e `model`; o formato nativo não tem esforço, e o Hermes resolve o esforço na troca pela configuração global.
- Os grupos da rede de segurança são grupos próprios, não chaves acrescentadas aos grupos da S3, para não invalidar o estado S3 já instalado e para excluir só a rede quando ela é editada.
- A tolerância de relógio de A23 é de 120 s; a nova consulta de A29 usa o intervalo mínimo de 30 s.
- Em A31, um limite por modelo com nome que não corresponde a nenhum modelo do mapa é ignorado.
- Plano só de créditos da Anthropic continua Desconhecido, porque o leitor nativo não entrega o corpo bruto (HQR-23).
- A rede de segurança depende de 18 funções nativas agora qualificadas; o Docker continua sem essas medições (ver a seção seguinte).

## Impressões digitais da rede de segurança e runner instalado

- RED `64dbfb8` (`wip: test:`): 39 falhas e erros em `tests.unit.test_hqr38_safety_net_fingerprints` e dois erros em `tests.unit.test_s3_docker_qualification`; no runner, dois dos cinco métodos falharam por ausência da prova embutida.
- Os três métodos negativos do runner já passavam no RED, porque a prova ausente também levanta `AssertionError`; depois do GREEN, cada um falha pela causa própria (leitor nativo divergente, OFF sem restauração e status sem os grupos).
- GREEN `1c0d3b5`: `compat.SAFETY_NET` acrescenta 18 funções a `compat.FUNCTIONS`; nenhuma constante nova foi necessária.
- Normalização e cadeia: `hermes_cli.fallback_config` `_normalized_base_url`, `_iter_fallback_entries`, `_entry_identity`, `get_fallback_chain` e `scoped_fallback_chain`.
- Releitura da raiz por turno: `gateway.run_config_loaders.GatewayConfigLoadersMixin._refresh_fallback_model` e `._apply_fallback_chain_to_agent`, `tui_gateway.agent_callbacks._sync_agent_fallback_with_config` e `hermes_cli.cli_chat_turn_mixin.CLIChatTurnMixin._sync_fallback_chain_with_config`.
- Cron, ativação e volta ao primário: `cron.scheduler._job_fallback_chain`, `agent.agent_init_fallback._fallback_entries` e `._init_fallback_chain`, `agent.chat_completion_helpers.try_activate_fallback` e `agent.agent_runtime_helpers.restore_primary_runtime`.
- Herança na delegação: `tools.delegate_tool_routes._with_inherited_fallback` e `._route_to_task_route`, `tools.delegate_tool_config._resolve_child_fallback_chain` e `._resolve_child_runtime`, onde fica a regra de rota fixada.
- A cópia de `fallback_providers` pela rota do model_map já estava coberta por `ModelMapDelegationProvider.route_task`.
- Entrada de trabalho: requalificada por `compat.collect_symbols` sobre a fonte instalada, em processo `python3 -I -B` com audit hook que recusava escrita, rede e subprocesso; nenhum bloqueio foi registrado.
- Os 134 hashes e as 19 constantes anteriores coincidiram; a entrada passou a 152 funções e 19 constantes, na revisão `3b421578588243f920886e6fe79a6faa87ea026e`.
- Os 18 arquivos novos não estão entre os três arquivos com patch local do Hermes de trabalho.
- Entrada Docker: os hashes dependem do alvo e não foram recalculados nem copiados da entrada de trabalho.
- A entrada recebeu `requalification_required`; `compat` recusa uma entrada marcada com o motivo `host_requalification_required`, mesmo com conjunto completo, com ou sem revisão Git legível.
- `tests/unit/test_s3_docker_qualification.py` passou a exigir a marca e o conjunto anterior sem as 18 funções; a seleção por revisão e por cada hash continua testada sobre uma cópia sem a marca, completada com os valores da entrada de trabalho.
- Runner: `tests/installed/s3_auto.py` ganhou `prove_safety_net_groups`, chamada depois da restauração das rotas nativas e antes da recusa de rota customizada.
- A prova cobre gravação na raiz e na rota `general`, projeção fechada, releitura pelos leitores nativos `get_fallback_chain` e `_with_inherited_fallback` com `scoped_fallback_chain`, OFF exato com a chave ausente e com a chave presente, e exclusão por edição externa sem sobrescrita.
- `tests/harness/test_hqr38_installed_runner.py` executa essa função contra o motor real com backend sintético e leitor substituto; o runner não foi executado em alvo instalado.
- Com a entrada Docker marcada, o passo `candidate-host-fingerprints` do runner para antes do Auto até a requalificação do alvo.
- Suíte depois: 300 unidade, 19 integração e 98 harness, todos verdes, sem skips.

## Pendências

- Requalificar a entrada Docker por inspeção somente de leitura do alvo e remover a marca, com autorização própria.
- Executar o runner instalado com os grupos da rede de segurança, com autorização própria.
- Revisão independente, publicação, ensaio instalado e o piloto real da especificação: chat do Desktop fixado em Sol que continua em Opus pela rede de segurança.

## Correção dos achados SOL-01 a SOL-07, 2026-11-17

Estado: WIP local, sem GO de entrega ou de instalação.
A base desta correção é `d1960da95f5da74e62da136e13528f182e3af257`, na mesma branch e worktree da HQR-38.
O pedido autoriza corrigir os sete achados e criar commits locais; não autoriza instalação, publicação, merge, push, consulta a provedores ou mudança do Hermes vivo.
O parecer independente completo foi lido, assim como `persistence-blocker.md`; o bloqueio de abertura relativa de `auto.lock` permanece intocado.
Não houve fetch: esta execução está sem rede e usa a base local explicitamente fixada pelo pedido.
Os pins OKF continuam os do bootstrap: pacote 0.3.0, `okf-runtime-v1`, router SHA-256 `e1f5be06b7f8a69fe7407aff97bde1cfd4d6767a65b974ff3bc1e958cb054b42`.

### Implementação e RED/GREEN por achado

| Achado | RED local | Correção local | Prova e limite |
|---|---|---|---|
| SOL-01 | `b6061ca`, quatro métodos com 14 falhas, incluindo subtests | `7e176f1` (WIP): a lista inclui todos os candidatos elegíveis e não exclui a escolha do Auto | Quatro métodos novos verdes; expectativas protegidas antigas ainda falham; refresh e exclusão de backend nativos provados separadamente em memória |
| SOL-02 | `e5dae6c`, três falhas em quatro métodos | `8c6477c`: null, slot novo e slot malformado geram marcador por modelo, com requalificação | Quatro métodos verdes; modelos não afetados continuam Livres |
| SOL-03 | `f273f8c`, cinco falhas em seis métodos | `1e82b27`: créditos só na inconsistência temporal qualificada; cache também expira nos resets por modelo | Seis métodos verdes; reset de modelo na decisão final não contamina o modelo alheio nem autoriza créditos |
| SOL-04 | `b2adbf0`, sete erros em cinco métodos por função ausente | `fe419c3` (WIP): `prepare_legacy_state` é uma preparação pura e não automática | Cinco métodos verdes contra os validadores reais atual e `233f4be`; migração persistida bloqueada, não concluída |
| SOL-05 | `cd5b210`, nove erros em sete métodos por guard ausente; `a7ff85b`, duas falhas de ligação estática | `d673439` (WIP): qualificação da herança e do legado, antes da escrita e na releitura | Sete métodos puros e um estático verdes; o estático não prova transação, restauração ou persistência |
| SOL-06 | `c7d5f98`, quatro falhas em quatro métodos, contando subtests | `a762c41` (WIP): null só com uso zero; limite usado sem reset bloqueia somente o modelo quando aplicável | Quatro métodos novos verdes; uma expectativa protegida antiga continua falhando |
| SOL-07 | `12100be`, seis falhas e um erro de fixture em cinco métodos | `02cfdeb` (WIP): gates compartilhados para fallback, comparação no relatório `safety_net` e reflexão de exclusões finais | Os quatro métodos funcionais passam; o quinto contém fixture incompleta congelada no RED e continua com erro, sem correção silenciosa |

O texto da cadeia compartilhada teve RED adicional `58da7ce`, com uma falha sob o contrato completo do renderizador; passou depois de `02cfdeb`.
A execução não alterou nenhum teste preexistente, runner, helper protegido ou guard.
Os nove arquivos novos `tests/unit/test_sol*.py` conservam seus bytes desde cada RED.
Um deles, `test_sol07_fallback_preview.py`, contém um erro meu de fixture: o último método omite `cron` no documento de decisão entregue ao renderizador.
A correção exata solicitada à coordenação é acrescentar `'cron': {'state': 'follows_conversation'}` a essa fixture, sem mudar as asserções; ainda não foi autorizada nem aplicada.
`test_sol01_shared_render.py` tem a fixture completa e prova o comportamento de texto, mas não substitui o método congelado com erro nem torna a suíte verde.

### Refinamento técnico de D-28/D-29

A especificação aprovada permanece byte a byte preservada.
A expressão "outro provedor" precisa ser aplicada ao primário efetivo do consumidor, não à escolha do Auto para o profile.
Quando Sol está fixado e o Auto escolhe Opus, excluir Opus da lista impede exatamente o piloto exigido na especificação.
Por isso a lista compartilhada inclui todos os candidatos que já passam pela mesma política; a exclusão do backend corrente continua nativa.
Isso não cria uma nova decisão de política, não muda o pin e não acrescenta patch no core.
As entradas continuam contendo apenas `provider` e `model` do mesmo papel.

### Matriz gerada e efetiva

Prova pura sobre fontes nativas selecionadas por AST: 14 observações, zero negativas do audit hook inalterado.
Ela executa o leitor de cadeia, `_with_inherited_fallback`, `_apply_fallback_chain_to_agent` e a identidade nativa de backend, com IDs canônicos e endpoints padrão vazios.
Não executa ativação de fallback, autenticação, transporte, inferência ou recuperação de filho em andamento.
Nos nove pares abaixo, os usos semanais sintéticos são 20% Codex e 40% Claude, e não há créditos verificáveis.
`S` significa Sol; `O`, Opus; `L`, Livre; `P`, Pressionado; `E`, Esgotado.
A cadeia efetiva mostrada é a sequência depois da releitura e da exclusão nativa do backend igual ao primário fixado.

| Codex | Claude | Auto | Cadeia gerada e relida | Efetiva com Sol fixado | Efetiva com Opus fixado |
|---|---|---|---|---|---|
| L | L | S | S → O | O | S |
| L | P | S | S → O | O | S |
| L | E | S | S | vazia | S |
| P | L | O | O → S | O | S |
| P | P | S | S → O | O | S |
| P | E | S | S | vazia | S |
| E | L | O | O | O | vazia |
| E | P | O | O | O | vazia |
| E | E | nenhum | nenhuma nova escrita | cadeia anterior não qualificada por este resultado | cadeia anterior não qualificada por este resultado |

Com Codex Esgotado e créditos verificáveis permitidos, Claude Livre gera O → S; com ambos Esgotados e só créditos Codex verificáveis, gera S.
Os controles de herança distinguem chave ausente, que herda O e bloqueia o grupo se O é inelegível, de `[]`, que resulta em cadeia efetiva vazia.
Na raiz, `fallback_model=O` ainda acrescenta O depois de `[]`; o plugin só qualifica essa fonte e nunca a apaga ou edita.

### Upgrade e downgrade: procedimento ainda bloqueado

OFF da HQR-38 sozinho não torna o estado legível por `233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a`.
Os grupos e o histórico `fallback:*` permanecem incompatíveis com o validador antigo mesmo com `schema:1` e Auto encerrado.
A função nova prepara uma representação compatível em memória: retira esses itens das coleções operacionais antigas e conserva o estado original completo em `hqr38_downgrade_archive.source_state`.
Esse arquivo lógico é histórico inerte: não restaura configuração, não reativa grupos e não apaga o histórico original.
A preparação recusa modo diferente de OFF, Auto declarado, grupo ativo, restauração incompleta sem exclusão, diário presente e arquivo histórico anterior que seria aninhado ou sobrescrito.
O validador antigo e o atual aceitam a representação preparada nos testes; isso não é prova de publicação persistida, atomicidade, recuperação ou readback.

1. Antes de upgrade autorizado, confirmar OFF na revisão que está realmente atendendo o consumidor e conferir baseline, grupos inativos, exclusões humanas e ausência de diário.
2. Preservar backup privado verificável da revisão e do estado, sem usar configuração, autenticação ou estado reais como fixture e sem restaurar snapshots de configuração cegamente.
3. Requalificar o alvo isolado e executar o ensaio completo de upgrade; esta rodada não instalou nada nem retirou o bloqueio Docker.
4. Para downgrade depois de HQR-38, confirmar OFF pela candidata ainda carregada e preparar a projeção pura apenas sobre um snapshot sintético admitido, conservando o arquivo histórico completo.
5. Parar aqui enquanto o gate de persistência não for resolvido: não existe nesta entrega comando de migração automática ou publicação de estado autorizado/qualificado.
6. Depois de autorização e resolução do gate, implementar e provar a publicação serializada, backup, comparação do snapshot no ponto de escrita, interrupções, readback do alvo e leitura pela revisão antiga.
7. Só então avaliar a troca de revisão; a configuração humana atual deve permanecer intacta, incluindo grupos excluídos, e qualquer retorno à candidata deve obter baseline nova, nunca reproduzir o arquivo histórico.

Não foram executados `Engine.locked`, `cycle`, `restore`, recuperação ou uma operação equivalente à abertura negada pela revisão.
As provas puras não substituem a migração bloqueada e não autorizam apagamento de estado real.
SOL-04 continua corrigido apenas na preparação pura, aguardando implementação/prova persistida; não está encerrado.

### Regressão parcial, testes protegidos e pendências

O runner canônico inalterado executou 14 módulos puros inspecionados: 114 métodos/IDs únicos, sem duplicatas e sem skips, exit 1.
Os resumos reais são: cinco falhas em `test_hqr38_policy` (incluindo subtests), uma falha em `test_hqr38_readings` e um erro em `test_sol07_fallback_preview`; os outros módulos terminaram `OK`.
A primeira execução do wrapper adicional teve um diretório novo de evidências com modo 0775, que fez o diagnóstico somente de leitura recusar seu ancestral; seu log foi preservado separadamente.
Somente a permissão desse diretório sintético novo passou a 0700 antes da segunda execução; o guard da revisão, a abertura negada e os testes congelados não foram alterados.
A regressão integral de 300 unitários, 19 integrações e 98 harness é a baseline histórica da revisão, não uma nova execução desta rodada.
Ela e os novos ensaios persistidos permanecem bloqueados, porque incluem a operação `auto.lock` proibida; não foram contornados por outro runtime ou ferramenta.

Mudanças protegidas que precisam de autorização específica antes de qualquer edição:

- `tests/unit/test_hqr38_policy.py:174,178,182,187,192`: esperar todos os candidatos elegíveis, incluindo a escolha do Auto, preservando as exclusões de Esgotado sem crédito e Desconhecido.
- `tests/integration/test_hqr38_fallback.py:61–64,79–81,89,93`: esperar S → O com ambos elegíveis e S quando só Codex é elegível, mantendo OFF e baseline exatos; nenhuma execução desta integração foi feita.
- `tests/unit/test_hqr38_readings.py:34–43`: Sonnet com uso 12,5% e reset null deve ser Desconhecido, com Opus ainda Livre; preservar os controles genuinamente ociosos.
- `tests/unit/test_sol07_fallback_preview.py:103`: completar somente a fixture `cron` descrita acima, preservando as demais asserções e a evidência RED original.

O diff MDR dos testes preexistentes e o diff de cada teste novo desde seu RED estão vazios.
O refinamento de variável local de `apply.py` está em `b10d9af`, ainda WIP porque a execução persistida continua bloqueada.
Gates locais observados: linhas até 2000 em 166 caminhos rastreados, compilação de produto/scripts/testes com cache externo, whitespace e Gitleaks staged sem achados.
O OKF oficial e perfil passaram (`conformant`, `pass`, navegação válida e cobertura completa), sem certificar correção funcional ou aceite.
CodeGraph 1.6.2 recebeu índice próprio desta worktree, com sincronização manual escolhida sem hooks ou watcher; os 130 caminhos Python/YAML indexados coincidem com os 130 rastreados desse escopo, sem extras ou omissões.
A raiz física confere, `worktreeMismatch=null`, o índice está completo, sem pendências e sem recomendação de rebuild.
Persistência, suítes completas, downgrade operacional, rechecagem independente da candidata e aceite/piloto instalado continuam pendentes no HQR-38 do backlog.

### Ajustes protegidos autorizados e regressão pura, 2026-11-17

Guilherme autorizou explicitamente os quatro ajustes pontuais das linhas 175–180 no pedido desta rodada, repassado pelo coordenador.
Essa autorização substitui somente a pendência de edição dos quatro testes; não libera persistência, rollback, instalação ou outros testes/produto.
A base local conferida antes da primeira escrita foi `649a559b87dfee63982ba3fa8bdf52cc66bc5ca0`, com árvore e índice limpos, na branch e worktree já indicadas.
O remoto `origin` existe, mas não houve fetch nem outra rede por proibição expressa; não foi verificada sincronização remota nova.
Os pins OKF anteriores foram conferidos e preservados: pacote 0.3.0, `okf-runtime-v1` e router SHA-256 `e1f5be06b7f8a69fe7407aff97bde1cfd4d6767a65b974ff3bc1e958cb054b42`.

- `test_hqr38_policy.py`: cinco expectativas passam a incluir todos os candidatos elegíveis, inclusive a escolha Auto; exclusões de Esgotado sem crédito e Desconhecido permanecem exatas.
- `test_hqr38_fallback.py`: somente as expectativas autorizadas passam a S → O com ambos elegíveis e S com apenas Codex elegível; OFF, baseline, fixtures e demais asserções permanecem intactos.
- `test_hqr38_readings.py`: a fixture Sonnet de 12,5% sem reset agora exige Desconhecido, e Opus continua Livre; os controles genuinamente ociosos não mudaram.
- `test_sol07_fallback_preview.py`: somente a fixture recebeu `cron: {state: follows_conversation}`; as três asserções de texto permanecem intactas.

O RED original `12100bec9c9d5507859a9d9947c991a14c51fed6` e as evidências anteriores foram preservados; esta correção de fixture não transforma o erro original em RED funcional.
Nenhum código de produto, helper, runner, guard, instrução, instalação, configuração, autenticação ou estado vivo foi alterado.
O registro histórico acima sobre testes congelados descreve a rodada anterior; os quatro diffs autorizados desta rodada são a única exceção posterior.

Comando do runner inalterado, executado pelo wrapper de scratch com exatamente o isolamento permitido pelo handoff:

```sh
/usr/bin/python3 scripts/run_tests.py tests.unit.test_sol01_pinned_chain tests.unit.test_sol01_shared_render tests.unit.test_sol02_model_shapes tests.unit.test_sol03_credits_resets tests.unit.test_sol04_downgrade_pure tests.unit.test_sol05_effective_chain tests.unit.test_sol05_gate_wiring tests.unit.test_sol06_null_resets tests.unit.test_sol07_fallback_preview tests.unit.test_hqr38_policy tests.unit.test_hqr38_readings tests.unit.test_hqr38_render tests.unit.test_s2_policy tests.unit.test_s2_readings
```

Resultado final observado: 14 módulos, 114 métodos e 114 IDs únicos, 114 passes, zero falhas, zero erros, zero skips e zero duplicatas; exit 0.
O wrapper usa `/usr/bin/python3 -I -B`, home/TMPDIR descartáveis em scratch, PATH `/usr/bin:/bin` e cache Python externo, sem tornar o leitor nativo importável.
A primeira execução desta rodada encontrou o diretório novo de evidências em 0775: o diagnóstico somente de leitura recusou o ancestral e SOL-07 terminou com cinco falhas de asserção e um erro, contando subtests; 110 métodos passaram.
Esse log e seu resumo foram preservados como `initial-unsafe-ancestor.log` e `initial-unsafe-ancestor-summary.json`.
Somente esse diretório sintético novo passou a 0700, como na estratégia anterior do handoff; nenhuma política, runtime, profile, guard ou operação negada foi alterada ou repetida.
A fixture `cron` corrigida alcança apenas o renderizador puro, não persistência.
Evidências privadas desta rodada ficaram fora do repositório, com `run_pure_regression.py`, `pure-regression.log` e `pure-regression-summary.json`.

Compilação de produto/scripts/testes com cache externo, whitespace e limite de 2000 caracteres em 166 caminhos rastreados passaram.
Gitleaks staged passou sem achados, exit 0; OKF oficial/perfil passou com `conformant`, `pass`, navegação válida, cobertura completa e nenhum diagnóstico, exit 0.
A reconciliação dos logs confirmou os mesmos 114 IDs da rodada anterior, e o blob do RED original conservou SHA-256 `5ad254a0c60cfd38af6191f1adc370127e715994cbba1a160a8bfb68f516bec7`.
CodeGraph 1.6.2 sincronizou os quatro arquivos de teste na raiz física correta, com 130 arquivos, índice completo, nenhuma pendência, `worktreeMismatch=null` e sem recomendação de rebuild.
Os avisos opcionais do editor sobre `net` possivelmente nulo não motivaram mudanças fora do escopo; a execução real dos testes passou.

A integração persistida editada foi apenas inspecionada e compilada, não executada: sua fixture entra em Auto e depende das transações bloqueadas.
Não foram executados `Engine.locked`, `cycle`, `restore`, `auto.lock`, suíte integral, rollback/downgrade persistido ou runner instalado.
O gate de persistência e o parecer independente anterior permanecem preservados, sem nova aprovação independente ou GO de instalação.
As pendências operacionais e de revisão já registradas no HQR-38 do backlog continuam abertas; a pendência antiga de autorização de testes está resolvida somente pelos quatro ajustes acima.

## SOL-04 — publicação compatível autorizada, 2026-11-17

O responsável autorizou implementar e ensaiar a publicação persistida do downgrade em ambiente sintético, sem alterar o Hermes de trabalho.
O escopo não inclui instalação, migração de dados reais, provedores, publicação, merge, push ou suíte integral.
Base desta continuação: `4f304e3bd04ec82eca420f5ab532a2c8d87b4c38`, com árvore limpa.
O fetch confirmou `origin/main` em `ad113d95604128fcdf9c446e2c5bd9c75bff0860`, ancestral da candidata, sem commits remotos faltantes.
Os pins OKF 0.3.0 e do router registrados acima continuam iguais.
O ensaio sintético anterior executou os 12 cenários de persistência com exit 0, sem instalar o produto; o downgrade desse ensaio permaneceu puro.
As evidências privadas desse ensaio não fazem parte do produto publicável.

### Plano técnico em revisão

Workflow W07, tier critical: o novo código será capaz de migrar estado persistido quando futuramente instalado, embora esta execução use somente dados sintéticos.
O plano acrescenta uma operação explícita ao módulo `quota_router/downgrade.py`, sem descoberta de configurações ou migração automática.
O chamador fornece o snapshot esperado em bytes e um leitor do modo atual; a operação exige OFF, ausência física de diário Auto e estado sem grupos ativos.
A operação usa o mesmo `auto.lock` do Engine e descritores de diretório protegidos por `storage`, sem alterar autenticação, configuração ou o guard histórico.
Ela preserva backup byte a byte e privado, criado exclusivamente, antes de publicar uma intenção de migração durável.
A intenção vincula os hashes do snapshot original e da representação preparada pela função pura existente.
A configuração é observada pelo backend do Engine, sem escrever nela; a representação comparada contém apenas as projeções dos grupos do snapshot e da conversa, em ordem estável.
Somente o hash dessa representação entra na intenção, nunca o documento bruto, prompts ou credenciais.
Esse hash fica fixado na primeira intenção durável e deve ser reutilizado na retomada, sem adotar silenciosamente uma configuração posterior.
Alterações fora dessas projeções não são monitoradas nem sobrescritas; erro de leitura ou divergência no escopo comparado bloqueia publicação e conclusão.
Enquanto a intenção estiver pendente ou malformada, operações comuns do Engine recusam execução; somente a operação explícita de migração pode reconciliá-la.
A publicação usa a primitiva atômica existente, com nova comparação do snapshot, identidade do alvo, modo e configuração antes da escrita, seguida de readback e sincronização.
Depois do readback exato e da nova checagem de modo/configuração, a mesma intenção é publicada atomicamente como recibo `complete`, com fsync do arquivo e do diretório, sob o mesmo lock.
O recibo concluído e o backup são retidos; sucesso só é retornado depois dessa sincronização.
O Engine comum valida o recibo concluído e sincroniza o diretório antes de liberar o acesso; se a conclusão falhar após rename e antes de fsync, nenhum chamador pode usar só o retorno anterior como prova de liberação durável.
Antes de carregar a revisão antiga, é obrigatório reconciliar pela operação explícita e obter sucesso durável, pois a revisão antiga desconhece o novo guard.
Uma repetição após sucesso apenas confirma recibo, backup, alvo exato, modo e hash de configuração; não cria backup novo, não aninha arquivo histórico e não republica o estado.
Se a revisão antiga já modificou legitimamente o estado, esse snapshot não é reutilizado para outra migração: uma divergência é preservada, não desfeita.
O limite de escritor cooperativo permanece: comparação e rename não são CAS contra processos externos que ignoram o lock.
A retomada aceita somente o snapshot original ou o alvo preparado exato, com backup íntegro; um terceiro valor, modo diferente, diário ou backup divergente bloqueia sem sobrescrita.
A identidade original do arquivo é exigida somente durante uma tentativa que publica; o rename legítimo muda o inode, e uma retomada já no alvo exige os bytes exatos do alvo, não o inode anterior.
Backups incompletos são preservados e recusados, não apagados ou tratados como completos.
O arquivo histórico continua inerte e nunca restaura configuração nem é reproduzido como baseline.
A revisão antiga deve ler o estado publicado e exercitar seu Engine com configuração sintética, preservando o arquivo histórico e as edições externas.
O retorno à candidata deve obter baseline da configuração corrente, sem reproduzir o histórico arquivado.

### Provas e limites previstos

Adicionar testes novos em RED, sem alterar testes ou helpers protegidos, e preservar o commit e o log completo antes do GREEN.
Executar transações e a abertura de `auto.lock` somente no contêiner isolado, com as restrições de imagem, rede, binds e dispositivos já qualificadas.
Cobrir publicação/readback, backup exato, OFF e recusas, conflito de snapshot/configuração, interrupções e retomada idempotente.
Incluir modo ainda OFF com configuração alterada entre tentativas, falha do leitor, diário fisicamente presente com JSON falsy, falhas de readback/fsync e repetição após conclusão sem novas escritas de estado.
Exercitar também os limites reais de publicação e recuperação com dados sintéticos; distinguir exceções no mesmo processo de interrupção de subprocesso quando esta não for executada.
O ensaio usa fontes legadas fixadas em `233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a`, sem importar autenticação ou backend nativo.
Antes da entrega, exigir revisão independente general/security/test da candidata exata, sem confundir aprovação técnica com instalação ou aceite.
SOL-04 permanece aberto até a implementação, o ensaio autorizado e a reconciliação da revisão; a qualificação instalada continua separada.

### Primeiro RED da publicação persistida

O plano ajustado recebeu `APPROVE_PLAN` em rechecagem dos achados SOL04-PLAN-01 e SOL04-PLAN-02, resolvidos somente no nível do plano.
O novo arquivo `tests/unit/test_sol04_persist_publish.py` exige backup byte a byte, alvo preparado exato, recibo concluído, configuração intacta e repetição sem republicação.
Um contêiner novo executou esse único método com dados sintéticos: zero falhas de asserção, um erro pela ausência de `publish_legacy_state`, zero skips, exit 1.
O erro alcançou o ponto pretendido depois de aplicação e OFF reais da fixture; não foi falha de import ou de bootstrap.
O driver focado do ensaio usou o preflight previamente qualificado e a biblioteca padrão `unittest`; não executou nem substitui a regressão integral pelo runner canônico.
Logs, snapshot de fontes e recibo de Docker foram preservados fora do Git, com hashes intactos e sem alteração do guard histórico.
Base do primeiro RED: `4f304e3bd04ec82eca420f5ab532a2c8d87b4c38`; a nova fixture e esse teste ficam protegidos após o commit RED.
Nenhum teste ou helper preexistente foi alterado.

### GREEN inicial e RED de recuperação

O primeiro RED foi preservado em `39453fa913093f4b275373aae7502f102e69489b`, após revisão pré-commit específica dos testes.
A implementação inicial não commitada passou no mesmo método em contêiner novo, exit 0, sem alterar o teste protegido.
O novo arquivo `tests/unit/test_sol04_persist_recovery.py` acrescentou verificações de checkpoints, conflitos, leitores indisponíveis, diários falsy, backups incompletos, links e falhas de readback/fsync.
A execução conjunta observou 16 IDs únicos, uma falha de asserção, zero erros e zero skips, exit 1.
A falha nova mostrou que uma mudança do estado depois do primeiro readback e antes da conclusão ainda podia receber recibo `complete`.
Essa é uma falha da implementação inicial, não um erro de fixture; a correção precisa repetir a comparação final do estado antes de concluir.
O snapshot privado preserva os bytes da implementação não commitada que produziu esse RED, separadamente de HEAD e do próximo commit somente de testes.
O primeiro teste protegido permanece idêntico a `39453fa`; os novos testes de recuperação ficam congelados em seu commit RED, antes de corrigir o defeito.

### Publicação e ida/volta sintéticas, aguardando rechecagem

O segundo RED está em `e6064ea45ac318599b5112fb02f83ae6181a79d2`, somente testes e registro; os bytes WIP executados estão preservados separadamente.
General, security e tests confirmaram o mesmo defeito de conclusão e aprovaram somente esse commit RED.
A correção acrescenta uma nova leitura pelo descritor protegido depois do último checkpoint e da checagem de contexto, exigindo o alvo exato antes de publicar `complete`.
G-SOL04-01, S-SOL04-01 e T-SOL04-01 ficam corrigidos aguardando rechecagem independente, sem alterar as asserções congeladas.
Uma execução focada posterior passou os 16 IDs, sem falhas, erros ou skips, exit 0.
A regressão focada acrescentou `test_s3_apply` e `test_s3_enrollment`: 27 IDs únicos, 27 passes, zero falhas, erros ou skips, exit 0.
Os dois testes novos permanecem byte a byte iguais aos respectivos commits RED, assim como todos os testes e helpers preexistentes.

`tests/installed/sol04_rollback.py` executou também a ida/volta entre o Engine atual e o Engine legado de `233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a` sobre estado realmente publicado nas fixtures.
As 19 fontes do pacote legado foram fixadas, conferidas e montadas somente para leitura; o backend de configuração continuou sintético e em memória.
A reconciliação terminou antes de carregar o legado; leitura, recuperação, OFF, Auto/OFF legado e retorno à candidata passaram.
Edições humanas sintéticas de esforço e fallback permaneceram; o retorno capturou baseline da configuração corrente, não do histórico arquivado.
A tentativa de reutilizar o snapshot original depois da escrita legítima do legado foi recusada, sem alterar arquivos ou configuração.
Backup byte a byte e arquivo histórico inerte foram preservados nos dois Engines.
Essas observações fornecem a prova antes ausente em G-SOL04-02 e T-SOL04-02, ainda sujeita à rechecagem.
O nome `tests/installed` indica o local do complemento no projeto, não uma instalação de Hermes comprovada por esse ensaio.

O recibo de execução confere 195 arquivos de entrada intactos e logs de attach idênticos aos do Docker, com contêiner parado e sem OOM ou estouro de orçamento.
Os recibos e fontes privadas do sandbox permanecem fora do produto publicável.
O wrapper executou testes focados próprios, não a suíte integral do runner canônico.
As interrupções foram exceções no mesmo processo; não se qualifica queda de energia ou morte abrupta de processo.
A migração continua explícita, limitada a escritores cooperativos, sem alteração de configuração, autenticação, provedores ou Hermes de trabalho.
A suíte integral, validação nativa instalada, fallback real e instalação continuam separados e não executados nesta continuação.
Os complementos opcionais T-SOL04-03 a T-SOL04-05 ficam registrados em HQR-40, sem enfraquecer os testes protegidos para tratá-los.
Gates desta candidata: 132 fontes Python compiladas com cache externo, limite de linhas sem violações em 169 caminhos, whitespace e Gitleaks staged sem achados.
OKF oficial/perfil passou, com navegação válida e cobertura completa; CodeGraph sincronizou e conferiu 133 caminhos Python/YAML exatos, sem extras, omissões, pendências ou recomendação de rebuild.
Esses gates não substituem a suíte integral, a rechecagem crítica ou a prova instalada.

### Reconciliação crítica do SOL-04 sintético

General, security e tests concluíram a rechecagem 1/2 com `APPROVE_SCOPED_SYNTHETIC`, sem bloqueantes abertos nesse escopo.
G-SOL04-01, S-SOL04-01 e T-SOL04-01 foram encerrados pela comparação final corrigida e pelo teste RED congelado agora verde.
G-SOL04-02 e T-SOL04-02 foram encerrados pela execução entre os Engines pinados, com recusa após alteração legítima do legado e baseline corrente no retorno.
Os pareceres conferiram os mesmos fontes executados, os 27 IDs únicos verdes e os limites dos ensaios, sem executar novamente o produto.
Os opcionais T-SOL04-03 a T-SOL04-05 continuam em HQR-40; nenhuma alteração dos testes protegidos foi usada para encerrá-los.
O fechamento posterior à revisão altera apenas o registro factual; código, testes e condições operacionais aprovadas permanecem idênticos.
SOL-04 está implementado e qualificado no ambiente sintético autorizado; a candidata HQR-38 permanece WIP, sem GO global, aceite humano ou instalação.
A suíte integral, a qualificação nativa instalada, fallback e piloto reais seguem pendentes e requerem os respectivos escopos e autorizações.
O prefixo histórico e os REDs ficam preservados; a revisão técnica limitada não autoriza migração de estado real, merge, push ou publicação.

### Suíte canônica completa em Docker sintético

O responsável autorizou em 2026-11-17 a suíte integral em Docker, somente com dados sintéticos e sem alterar a instalação de trabalho.
O alvo exercitado foi o commit `338bbfa2349cbd7464add2c24a53fa1a73928385`, com os 169 arquivos versionados conferidos antes e depois da execução.
O comando foi `/usr/local/bin/python3 -B /code/scripts/run_tests.py`, sem seleção parcial nem alteração do runner.

FS-GIT-01: a primeira preparação tinha índice Git descartável, mas não os objetos da revisão antiga exigidos por `tests/unit/test_sol04_downgrade_pure.py`.
A execução terminou com exit 1: 353 testes de unidade, dos quais dois retornaram erro ao chamar `git show`; integração e harness terminaram com 19 e 98 testes verdes.
Os dois erros ocorreram antes de carregar o validador legado e não foram usados como prova de defeito na publicação persistida.
A revisão `233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a` e os dois caminhos necessários foram conferidos no repositório de origem.

A segunda preparação preservou a primeira e acrescentou somente os cinco objetos Git originais necessários: commit, árvore raiz, árvore `quota_router` e os dois blobs.
Cada identidade de objeto foi conferida pelo hash Git; nenhuma ref artificial substituiu a revisão antiga.
A `.git` própria recebeu índice sintético e essa dependência histórica mínima, sem copiar configurações de usuário ou remotos.
Código do produto, testes, helpers, runner, guard de importação nativa e preflight de runtime permaneceram idênticos.

O novo contêiner retornou exit 0 e `OK` nas três suítes: 353 de unidade, 19 de integração e 98 de harness, total de 470 execuções.
Os IDs são únicos dentro de cada suíte; há 470 pares suíte/ID e 469 strings de ID globais, pois o guard hermético tem o mesmo nome nas duas primeiras suítes.
Não houve falhas, erros, skips, avisos, timeout ou OOM na segunda execução; a lista de IDs permaneceu igual à primeira.
FS-GIT-01 fica encerrado com essa prova, sem alterar testes protegidos ou reduzir a seleção para obter verde.

O recibo confere 353 entradas intactas da segunda preparação e logs de attach iguais aos do Docker; o contêiner terminou parado.
A imagem, rede `none`, raiz somente leitura, mounts, UID/GID `1001:1001`, capacidades removidas e `no-new-privileges` conservaram os limites do ensaio cooperativo anterior.
A admissão dos dispositivos e o guard histórico permaneceram com os hashes anteriores.
Essa configuração não comprova sandbox contra código hostil nem ausência universal de segredos preexistentes na imagem.
As duas execuções e os diagnósticos originais foram preservados fora do produto publicável.

Esta continuação altera somente registros e documentação de testes; a revisão independente da evidência/documentação usa uma perspectiva, preservando a cobertura crítica válida do código inalterado.
A suíte integral canônica deixa de ser pendência para os fontes exercitados; isso não é aceite humano ou GO global da HQR-38.
Continuam pendentes qualificação nativa instalada, fallback e piloto reais; não houve instalação, migração de estado real, alteração de provedores, merge ou push.
O próximo passo proposto é qualificar a candidata e seu rollback em Hermes isolado, mediante autorização separada.

A revisão independente do registro concluiu `APPROVE_PROOF_RECORD`, sem achados bloqueantes ou opcionais, após conferir os cinco documentos e as evidências persistidas.
O revisor leu os resultados e conferiu hashes, objetos Git e contagens; não executou novamente testes, produto, Docker ou scanners.
Este fechamento acrescenta somente o resultado do parecer, sem mudar os fontes exercitados, os critérios ou os limites da qualificação sintética.
