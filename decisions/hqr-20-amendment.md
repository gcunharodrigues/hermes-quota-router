---
type: Product Specification
title: Emenda HQR-20 — roteamento das próximas tarefas
description: Proposta que simplifica o produto depois da S1 para escolher, a partir das leituras nativas de cota, o modelo das próximas tarefas, sem interceptar cada chamada.
status: draft
---

# Emenda HQR-20 — roteamento das próximas tarefas

Estado: aprovada por Guilherme em 2026-11-15, com as respostas às decisões D1 a D7 registradas na seção 8.
Guilherme decidiu em 2026-11-15 simplificar o produto depois da S1 para escolher o modelo das próximas tarefas, Observe antes de Auto, sem prometer interceptar cada chamada (README, HQR-20).
As seções 13 a 16 e o [mapa de cenários](hqr-20-scenarios.md) são o desdobramento das respostas dele, escrito pelo agente e sujeito a revisão.
Quando aprovada, esta emenda substitui as partes da [especificação](product-spec.md), do [plano](product-plan.md), do README e do `AGENTS.md` listadas na seção 9; o resto do contrato continua valendo.

## 1. Problema

A franquia de uma assinatura pode acabar antes do reset enquanto a outra ainda tem folga.
Hoje nada troca a rota sozinho: o trabalho segue para o provedor esgotado até alguém mudar a configuração.
A especificação aprovada exige uma decisão antes de cada tentativa física, inclusive retries e auxiliares (seção 4, AC-05 e AC-09).
A pesquisa e a S1 não acharam essa fronteira nas interfaces do Hermes: hooks são observadores e o middleware de requisição não troca de provider nem veta de forma confiável.[18]
Sem extensão do core, o Auto da especificação atual não pode ser ativado.

## 2. Resultado proposto

O plugin lê as cotas pelos leitores nativos do Hermes, calcula qual assinatura deve receber as próximas tarefas de cada papel e, em Auto, grava essa escolha na configuração nativa do profile.
A garantia muda de "cada chamada é admitida" para "cada tarefa nova que lê a configuração do profile depois de uma decisão aplicada começa no provedor escolhido".
O roteamento é de melhor esforço: não impede que uma tarefa comece num provedor esgotado e não é limite de gasto.
Status e explain mostram a decisão, a leitura que a sustenta, quando foi aplicada e o que ficou fora do controle.

## 3. Quem lê a decisão

Conferido no código do Hermes instalado localmente, que tem patches locais; a qualificação no host fixado é critério da S2.

Quem vê uma decisão depende do modo de execução de cada consumidor, não da superfície.
Na sessão comum, executada dentro do processo do gateway ou da CLI, o lançamento de cada subagente relê `delegation` da configuração do profile (`tools/delegate_tool.py`, `tools/delegate_tool_config.py`, `hermes_cli/config.py`).
Worker gerenciado só existe para sessões bypass, sessões Kanban ou com `gateway.managed_workers` ligado (`gateway/session_managed_worker.py`); cada worker novo recebe a configuração gravada com a sessão dona quando ela foi criada, não uma leitura nova do profile, e o leitor de `delegation` usa essa cópia (`gateway/session_policy.py`, `agent/safe_worker_policy.py`).
Sessões em modo `follow_profile_config` releem a cada turno as seções de `FOLLOW_SECTIONS` (`model`, providers, fallbacks, aliases e toolsets de plataforma) e as chaves de `FOLLOW_AGENT_KEYS` (`gateway/session_policy.py`).

| Consumidor | Lê a decisão | Fora da cobertura |
|---|---|---|
| Sessão comum em processo, nova ou já aberta | `delegation` a cada subagente lançado depois da decisão | O modelo da própria conversa, fixado quando a sessão foi criada |
| Sessão de conversa nova | O bloco `model`, ao ser criada | — |
| Sessão gerenciada (bypass, Kanban ou `gateway.managed_workers`) | Só se a sessão for criada depois da decisão; seus workers herdam a cópia dela | Sessão gerenciada criada antes da decisão, mesmo reaberta, e todo worker novo e subagente dela, que seguem a cópia antiga |
| Sessão aberta em `follow_profile_config` (Bot Chat) | O bloco `model` e as outras seções seguidas, no turno seguinte | — |
| Cron sem pin | A cada tick, `cron.model` e `cron.model_provider` (`cron/scheduler.py`) | Jobs com pin, tratados abaixo |
| Auxiliares, retries e fallbacks | Não governados | Seguem a rota da tarefa e o comportamento nativo |

Consequência a aprovar: numa sessão comum, o próximo subagente já segue a decisão; numa sessão gerenciada, como as do Kanban, só a segue se a sessão for criada depois dela, mesmo que o worker seja iniciado depois.
Com a conversa no Auto (D2), uma sessão Bot Chat aberta troca de provider no turno seguinte a uma decisão; as outras sessões de conversa só mudam quando uma nova é criada (seção 16).
A S2 mede quais consumidores do host fixado congelam a configuração e quando; um consumidor não medido fica fora da cobertura declarada.

### Pins

Rota explícita significa provider, modelo, endpoint ou esforço fixados na chamada, no job ou na sessão; o nome de uma rota de `delegation.backends.model_map` é um papel e segue a decisão.
No cron, o Hermes considera fixado o job que tem provider, modelo ou endpoint próprio, mas resolve modelo e provider separadamente.
Um job com só um desses campos herdaria o outro do valor global e poderia formar um par incompatível depois de uma decisão.
Proposta: a S2 lista os jobs com pin parcial; enquanto existir algum, o Auto não muda as chaves globais do cron e o status explica o motivo.

## 4. Grupos de chaves, linha de base e restauração

O plugin escreve somente grupos de chaves inscritos, sempre o grupo inteiro e coerente: provider, modelo, endpoint, modo de API e esforço de uma mesma rota.
A conversa usa o pipeline nativo de troca de modelo (`hermes_cli/model_switch.py`), que monta o bloco completo; cron e rotas de subagente usam a escrita nativa de várias chaves.
No backend de arquivo, a escrita nativa aplica chave a chave e o lock nativo vale só dentro do processo (`hermes_cli/config_backend.py`, `hermes_cli/model_switch.py`).
Por isso o plugin usa um lock próprio entre processos, grava num diário a intenção da escrita, relê depois e, se encontrar uma escrita interrompida, completa ou desfaz o grupo antes de qualquer decisão nova.
O lock do plugin não coordena outros escritores: a escrita nativa de arquivo é incondicional (`hermes_cli/config_backend.py`), então uma edição humana que caia entre a comparação e a escrita do plugin é sobrescrita sem deixar sinal.
Proposta: enquanto um grupo está no Auto, o plugin é o único escritor dele; o status avisa isso, e a janela de corrida residual fica aceita como limite (D6).
A alternativa é uma escrita condicional (compare-and-set) no host, que exige extensão do core.

A linha de base é o valor de cada chave do grupo na inscrição, inclusive a ausência da chave.
Ela não muda com decisões posteriores: linha de base → A → B → OFF restaura a linha de base, não A.
Se o valor atual de qualquer chave do grupo diferir do último aplicado pelo plugin, alguém mudou a rota: o grupo inteiro sai do Auto, o plugin não escreve por cima e o status mostra a divergência.
Essa detecção só vale para edições feitas antes da comparação ou depois da escrita; a janela entre as duas é o limite de D6.
OFF restaura a linha de base só nos grupos que ainda têm, em todas as chaves, o valor aplicado pelo plugin; os outros ficam como estão e aparecem no relatório.
Remoção exige OFF efetivo antes.

## 5. Quando a decisão é tomada

Não há daemon, cron nem processo novo.
A decisão roda quando o Hermes já está ativo: abertura de sessão (`on_session_open`), tick do dispatcher Kanban (`on_kanban_dispatch_tick`) e `/quota-router status|explain|apply`.
A decisão vale para os consumidores que lerem a configuração depois dela; a tarefa que disparou a avaliação pode já ter lido a anterior.
Sem atividade, a configuração pode ficar defasada; o status mostra a idade da última decisão aplicada.
Nenhum desses pontos é veto: se o provedor escolhido esgotar durante uma tarefa, vale o comportamento nativo, e o diagnóstico registra o fato.
Se o plugin sumir ou falhar com Auto declarado, a configuração fica com a última decisão aplicada; o status e o diagnóstico na próxima carga mostram a ausência, mas nada bloqueia tarefas.

## 6. Política

A política da seção 5 da especificação continua: leitura desconhecida, vencida ou inconsistente não é capacidade livre; percentuais não viram tokens; o ranking por ritmo semanal e a histerese de 10% permanecem.
Os limiares de bloqueio decidem a próxima tarefa, não uma tentativa.
Cada papel tem um mapa explícito de equivalência entre os dois provedores, com modelo e esforço; sem mapa aprovado, o papel não é roteado (D5).
Sem candidato elegível, nenhuma chave muda: a rota aplicada antes continua instalada, e o status mostra o motivo e o reset conhecido.
Fable continua fora como candidato automático.
O plugin não usa LLM para decidir e não faz inferência própria.

## 7. Custo residual

Excluir um provedor esgotado do ranking não impede o consumo de créditos ou de extra usage.
Uma tarefa pode começar nele por decisão defasada, por cópia congelada, por pin, ou porque nenhum candidato era elegível e a rota antiga ficou.
O plugin não controla cobrança; o único limite rígido é a configuração da própria conta em cada provedor.
Por isso o Auto exige uma decisão explícita de Guilherme sobre esse risco (D3), registrada na seção 14.

## 8. Decisões

Respostas de Guilherme em 2026-11-15, com a emenda aprovada.

| ID | Proposta do agente | Decisão de Guilherme |
|---|---|---|
| D1 | Observe com leituras reais no Hermes de trabalho, como piloto com backup, readback e rollback | Hermes de trabalho. |
| D2 | Subagentes e cron sem pin; conversa fora | Recomendação do agente e também a conversa da sessão principal, aplicada quando uma sessão nova começa. |
| D3 | Escolher entre melhor esforço sem garantia de zero crédito e exigir créditos desligados na conta | Verificar se os créditos estão ligados e se há saldo; créditos da OpenAI podem ser usados, os da Anthropic não; o plugin precisa de configuração para ligar e desligar cada função. |
| D4 | Declaração datada de Guilherme sobre extra usage da Anthropic | Seguir D3, com uma configuração que liga e desliga o uso de créditos. |
| D5 | Mapa gerado pela S2 e aprovado antes do Auto | De acordo, com variantes com e sem Fable e com e sem Astra. |
| D6 | Plugin como único escritor dos grupos inscritos, com a janela de corrida aceita | De acordo, verificando interferência com decisões anteriores dele (seção 16). |
| D7 | — | Fazer um mapa de cenários de uso que cubra as possibilidades ([mapa](hqr-20-scenarios.md)). |

S2 pode começar; a S3 (Auto) começa depois do aceite da S2 e da aprovação do mapa de D5.

## 9. O que esta emenda substitui

Na especificação:

- Seção 1, cobertura de conversa, cron, subagentes e auxiliares: passa a ser a cobertura por consumidor da seção 3; auxiliares, retries e fallbacks ficam fora e aparecem como não governados.
- Seção 3, linha 60 (ausência inesperada com Auto bloqueia unidades gerenciadas): passa a ser o diagnóstico da seção 5, sem bloqueio.
- Seção 3, linha 64 (não sobrescrever alterações posteriores do usuário): passa a valer só fora da janela de D6; dentro dela, a edição humana feita com Auto ligado pode ser perdida.
- Seção 4 inteira (`decide`/`admit`/`settle` por tentativa, destino efetivo e identidade por unidade): decisão por papel aplicada pela configuração nativa; a extensão do core vai para o backlog, sem fatia.
- Seção 5, leases e coordenação por conta (linhas 126 a 128) e recusa, deferimento ou pausa tipada (linhas 130 a 134): sem admissão não há lease; sem candidato vale a seção 6 desta emenda, e esgotamento durante uma tarefa segue o nativo.
- Seção 6, linhas 141 a 146 (prova de conta, plano, transporte, modelo e janela): substituída pela condição de D4 quando aprovada; sem D4, a rota Claude fica fora do Auto.
- Seção 8, linhas 199 a 201 (Auto global verificado e imposto pelo host em cada profile): onboarding de cada profile na S4, com o status mostrando profiles sem o plugin.
- AC-02, segunda parte (ausência inesperada falha explicitamente), AC-05, AC-07, AC-08, AC-09 e AC-13: substituídos por AC-16 a AC-25.

No plano, as seções 5 e 6 (S2 e S3) passam a ser as fatias da seção 10.
No README, passam a descrever o roteamento das próximas tarefas: a linha "per-attempt admission", a linha de cobertura que inclui auxiliares, a frase sobre Auto exigir o contrato de admissão completo e a frase sobre qualificação de conta, plano, transporte e modelo; HQR-03 é fechado como substituído, e HQR-04 passa a ser a condição de D4.
No `AGENTS.md`, a regra "AUTO exige capacidades qualificadas de admissão por tentativa" passa a "AUTO exige as decisões D2 a D6 e os critérios AC-16 a AC-25 qualificados"; o arquivo de instruções só muda depois da aprovação.

Continuam valendo: estados OFF/Observe/Auto, instalação separada de habilitação, isolamento de ambientes, distribuição por SHA completo, rollback, segurança e dados, AC-01, a primeira parte de AC-02, AC-03, AC-04, AC-06, AC-10, AC-11, AC-12, AC-14 e AC-15.

## 10. Fatias propostas

| Fatia | Resultado utilizável | Destino |
|---|---|---|
| S2 — Observe com cotas reais | `/quota-router status` e `explain` mostram, por papel, a assinatura recomendada, as leituras com idade e fonte, o que o Auto mudaria, os consumidores que congelam configuração e os jobs com pin parcial; nenhuma configuração fora do plugin é gravada. | Alvo de teste com leituras sintéticas e, com D1, o Hermes de trabalho em Observe. |
| S3 — Auto nas próximas tarefas | Com D2 a D6, o plugin aplica a decisão nos grupos inscritos, respeita pins e divergências e restaura a linha de base em OFF. | Alvo de teste primeiro; depois piloto autorizado no Hermes de trabalho. |
| S4 — Promoção e onboarding | Release estável, instalação nos profiles escolhidos e onboarding de profiles novos. | Produção autorizada. |

Cada fatia passa por revisão crítica com três perspectivas e pelo aceite de Guilherme antes da seguinte.

## 11. Critérios novos

| ID | Critério e evidência exigida |
|---|---|
| AC-16 | Leitura real pelos leitores nativos, sem o plugin ver tokens; janela, reset, idade e fonte aparecem no status; leitura ausente, vencida ou divergente fica desconhecida. |
| AC-17 | Observe calcula a mesma decisão que o Auto aplicaria e grava zero chaves fora do subtree do plugin. |
| AC-18 | Auto escreve só grupos inscritos e completos, pelo caminho nativo, com diário de intenção e releitura; pins de provider, modelo, endpoint e esforço preservam a rota efetiva, e jobs de cron com pin parcial impedem a mudança das chaves globais do cron. |
| AC-19 | Decisões repetidas mantêm a linha de base da inscrição, inclusive chave ausente; edição humana de uma só chave, feita antes da comparação ou depois da escrita, tira o grupo inteiro do Auto na aplicação, no OFF e na recuperação; OFF restaura a linha de base só nos grupos intactos; a janela residual de D6 é documentada, não testada como protegida. |
| AC-20 | Dois processos decidindo ao mesmo tempo, falha de escrita no meio de um grupo e restart depois dela não deixam grupo misturado: o próximo ciclo completa ou desfaz o grupo antes de decidir. |
| AC-21 | Depois de uma decisão aplicada, uma sessão de conversa nova, um subagente lançado por uma sessão comum já aberta, um subagente de uma sessão gerenciada criada depois e um tick de cron sem pin resolvem o provedor escolhido; numa sessão gerenciada criada antes, tanto um worker já em execução quanto um worker novo iniciado depois da decisão lançam subagentes com a rota de `delegation` da cópia da sessão, que o teste confere, e aparecem como fora da cobertura. |
| AC-22 | Sem candidato elegível, inclusive com os dois provedores esgotados, nenhuma chave muda e o status mostra motivo e reset; uma tarefa iniciada com decisão defasada é registrada com a idade da decisão. |
| AC-23 | Ausência ou falha do plugin com Auto declarado aparece no status e no diagnóstico; a configuração continua com a última decisão aplicada e nada é bloqueado. |
| AC-24 | Cada configuração da seção 13 muda o comportamento que descreve; `/quota-router config` recusa valor inválido sem gravar; valor inválido gravado por fora aparece no status e suspende as escritas do Auto; o status mostra o valor efetivo; com `credits.anthropic` desligado, Claude e Fable esgotados nunca são escolhidos. |
| AC-25 | Cada cenário do [mapa de cenários](hqr-20-scenarios.md) marcado para a fatia tem teste ou prova instalada com o resultado esperado. |

## 12. Não objetivos

- Interceptar, vetar ou repetir uma chamada já iniciada, retries, fallbacks ou auxiliares.
- Mudar a rota de sessões e workers já abertos ou reescrever contexto.
- Garantir que nenhuma tarefa comece num provedor esgotado ou que nenhum crédito seja consumido.
- Usar créditos, API paga ou Fable sem que a configuração correspondente da seção 13 esteja ligada.
- Coordenar várias máquinas ou clientes externos que usam a mesma assinatura.

## 13. Configurações do plugin

Guilherme pediu configurações que ele mesmo possa mudar e um jeito de ligar e desligar cada função.
Elas ficam no subtree nativo do plugin, `plugins.entries.hermes-quota-router.settings`, lido com `ctx.get_config` e gravado com `ctx.set_config`, sem tocar no resto da configuração.
Mudam por `/quota-router config` (mostrar, definir e voltar ao padrão) ou por `hermes config set`; o plugin não abre caixas de pergunta.
Uma mudança vale a partir da próxima decisão, e o status mostra o valor efetivo de cada configuração.
`/quota-router config` valida antes de gravar e recusa valor inválido sem mudar o anterior.
`hermes config set` e a edição manual gravam sem passar pelo plugin; o plugin valida cada valor ao usá-lo, mostra no status o valor inválido salvo e, enquanto houver um, não escreve nada em Auto e o Observe marca a decisão como incompleta.

| Configuração | Padrão | Efeito |
|---|---|---|
| `mode` | `off` | `off`, `observe` ou `auto`. |
| `consumers.subagents` | `true` | Auto grava as rotas de subagente. |
| `consumers.cron` | `true` | Auto grava as chaves globais do cron. |
| `consumers.conversation` | `true` | Auto grava o modelo da conversa, lido quando uma sessão nova começa. |
| `conversation.policy` | `principal_first` | Entre os candidatos com franquia, a conversa fica no principal enquanto ele for elegível; `pacing` usa o mesmo ritmo das outras rotas. |
| `principal` | `openai-codex` | Provedor preferido no desempate e na conversa. |
| `credits.openai-codex` | `true` | Codex com a franquia esgotada pode ser candidato pago com créditos. |
| `credits.anthropic` | `false` | Claude com a franquia esgotada nunca é candidato. |
| `credits.order` | `after_subscriptions` | Créditos só entram quando nenhuma franquia é elegível. |
| `models.fable` | `false` | Inclui Fable nos candidatos, só quando a janela própria dele está disponível. |
| `models.astra` | `false` | Inclui Astra nos candidatos, só quando o catálogo da conta o oferece. |
| `limits.session_block_pct`, `limits.week_block_pct` | `95`, `100` | Limiares de bloqueio da seção 5 da especificação. |
| `limits.reading_max_age_s` | `60` | Idade máxima de uma leitura. |
| `limits.hysteresis_pct` | `10` | Vantagem mínima para trocar a preferência. |
| `roles` | vazio | Mapa de D5, preenchido só depois da aprovação de Guilherme. |

## 14. Créditos

Decisão de Guilherme: créditos da OpenAI podem ser usados; os da Anthropic não.
Com os padrões da seção 13, a ordem é: franquias elegíveis, depois Codex pago com créditos, e nunca Claude além da franquia.
A preferência da conversa pelo principal só escolhe entre candidatos com franquia; Codex pago com créditos não vence Claude com franquia, nem na conversa.
O plugin não liga nem desliga créditos na conta do provedor; ele só decide se uma rota esgotada pode ser escolhida.

No host conferido, o snapshot nativo do Codex traz o corpo da resposta em `raw`, sem headers nem credenciais, além de uma linha com o saldo (`agent/account_usage.py`).
A S2 lê de `raw` só campos de uma lista fechada: `credits.has_credits`, `credits.unlimited`, `credits.balance`, `credits.overage_limit_reached`, `spend_control.reached`, `rate_limit.allowed`, `rate_limit.limit_reached`, `rate_limit.<janela>.limit_window_seconds` e `model_usage.<modelo>.available`; nunca registra o corpo inteiro.
Decisão de Guilherme em 2026-11-15, na revisão da S2: `rate_limit.<janela>.limit_window_seconds` entra na lista só para confirmar que cada janela do Codex dura 5 h ou 7 dias; o valor não é guardado nem exibido.
O snapshot da Anthropic não traz `raw`, e a linha de extra usage só aparece quando ele está ligado; o estado de créditos da Anthropic e a janela própria do Fable ficam "não verificáveis pelo plugin".
Expor esses campos da Anthropic no leitor nativo vai para o backlog como extensão do core (HQR-23).
A verificação pedida por Guilherme foi feita pelo agente e fica registrada fora deste repositório público.

Consequência para Fable: fora de uma oferta da Anthropic, Fable no plano Pro consome créditos; com `credits.anthropic` desligado, ele só é candidato enquanto sua janela própria mostrar franquia disponível.
Como a janela própria do Fable não chega ao plugin, Fable fica desconhecido, portanto inelegível, até a extensão do backlog.
A disponibilidade de Astra vem de `model_usage` no `raw` do Codex e da descoberta nativa de modelos da conta.

## 15. Mapas de equivalência

O mapa de D5 tem quatro variantes, escolhidas por `models.fable` e `models.astra`: base, com Fable, com Astra e com os dois.
Para cada papel das rotas atuais, a S2 propõe o candidato Codex e o Claude de cada variante, com modelo e esforço, a partir do catálogo nativo da conta.
O candidato Codex da conversa é `gpt-6.1-sol` com esforço xhigh em todas as variantes, salvo mudança explícita de Guilherme no mapa.
Astra depende da descoberta de modelos da conta e do campo de disponibilidade do Codex; sem ela, a variante com Astra cai para a base e o status explica.
O Observe mostra as quatro variantes lado a lado; Guilherme aprova o mapa e escolhe a variante antes do Auto.

## 16. Interferência com decisões anteriores

| Decisão anterior de Guilherme | Interferência | Tratamento |
|---|---|---|
| Preferência por `gpt-6.1-sol` com esforço xhigh para conversar e orquestrar | Auto na conversa poderia trocar o modelo mesmo com Codex disponível | `conversation.policy=principal_first` mantém sol xhigh enquanto o Codex for elegível; o esforço vem do mapa. |
| Rotas de subagente já configuradas por ele, com nome, descrição, esforço, fallbacks e opções próprias | Auto reescreve provider, modelo, endpoint e esforço | O grupo inclui fallbacks e opções da rota; nome e descrição não mudam; OFF restaura a linha de base inteira. |
| Não usar caixas de perguntas | Um plugin pode pedir escolha ao usuário | O plugin não usa perguntas interativas; tudo passa por comandos e configuração. |
| Merge e push após revisão aprovada; produção com gates próprios | A instalação da S2 no Hermes de trabalho depende de uma revisão publicada | Instalar só a revisão revisada e publicada, com backup, readback e rollback; o piloto em Observe vale por D1. |
| Patches locais do Hermes e procedimento de conferência a cada `hermes update` | O plugin usa funções internas de configuração e troca de modelo | O plugin confere essas funções ao carregar e suspende o Auto, sem escrever, se alguma mudar. |
| Profiles de outras sessões, como os da WRXN | Auto por profile poderia alcançar profiles alheios | Só o profile `default` é inscrito; outros dependem de pedido próprio na S4. |
| Fable só por escolha explícita | Mapa com Fable | `models.fable` desligado por padrão; ligar é a escolha explícita. |
| S1: instalação separada de habilitação e OFF por padrão | Nenhuma | Mantidas. |

Limite que contraria parte de D2: sessões "Bot Chat" seguem o modelo do profile a cada turno por desenho nativo (`follow_profile_config`), então mudariam de modelo no turno seguinte a uma decisão, não só numa sessão nova.
As demais sessões de conversa fixam o modelo ao serem criadas (`tui_gateway/methods_session.py`), como Guilherme pediu.
Por isso a S3 só escreve o modelo da conversa depois que Guilherme aceitar essa exceção ou de uma correção nativa qualificada (HQR-24); sem isso, `consumers.conversation` fica sem efeito e o status explica.

## Reference definitions

[18]: ../evidence/plugin-native-research.txt

## Sources

[18] /evidence/plugin-native-research.txt — Pesquisa pública: viabilidade e limites do plugin
