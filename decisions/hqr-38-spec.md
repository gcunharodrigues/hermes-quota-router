---
type: Specification
title: HQR-38 — política de troca e tipos de assinatura
description: Proposta com as decisões D-28 a D-31 de 2026-11-17 — rede de segurança nativa, estados Livre, Pressionado, Esgotado e Desconhecido, e correções de leitura por tipo de plano.
status: stable
---

# HQR-38 — política de troca e tipos de assinatura (especificação proposta)

Estado: **aprovada por Guilherme em 2026-11-17**, a partir das decisões D-28 a D-31 abaixo.
Esta especificação não altera a S3 já instalada; ela define a próxima fatia.
Evidência da investigação: matriz de 13 tipos de plano e 24 cenários A16–A39, com leitores nativos reais e a política real do plugin executados sobre respostas sintéticas.

## Decisões de Guilherme (2026-11-17)

| ID | Decisão |
|---|---|
| D-28 | Troca dentro de uma conversa já aberta acontece pela rede de segurança nativa (`fallback_providers`), sem patch no core. Correção da mesma data, confirmada em teste real por Guilherme: o backend do Desktop adota o modelo do `config.yaml` a cada turno (`tui_gateway/prompt_turn.py:695-704`, `tui_gateway/model_switch.py:501-541`), então chats abertos sem escolha manual seguem o Auto proativamente; a rede de segurança vale para chats fixados por seletor ou `/model`, CLI e chamadas já em andamento. |
| D-29 | O plugin pode gravar `fallback_providers` na conversa e em cada rota de subagente; a perda de cache de prompt na troca e a volta automática ao provedor original depois da renovação são aceitas. |
| D-30 | O plugin não implementa trava própria quando tudo está esgotado; vale o comportamento nativo do Hermes e da conta no provedor. |
| D-31 | Janela de 5 h em 95% é gatilho de troca, não bloqueio absoluto: se as duas contas estiverem com a janela de 5 h em 95% ou mais, a escolha segue a folga semanal entre elas. Créditos só entram quando a semana chega a 100%, ou quando a janela de 5 h chega a 100% e os créditos daquele provedor estão permitidos. |

## Regras de decisão

Cada provedor tem, em cada decisão, um destes estados de franquia:

| Estado | Condição | Efeito |
|---|---|---|
| Livre | Semana abaixo de 100% e janela de 5 h abaixo de 95% (ou plano sem janela de 5 h) | Candidato normal, ordenado por folga semanal com histerese de 10% |
| Pressionado | Semana abaixo de 100% e janela de 5 h entre 95% e 100% | Candidato só se nenhum outro provedor estiver Livre; entre Pressionados, ordena por folga semanal com histerese |
| Esgotado | Semana em 100%, ou janela de 5 h em 100% | Fora da franquia; pode ir a créditos se `credits.<provedor>` estiver ligado e o saldo for verificável |
| Desconhecido | Leitura ausente, vencida ou inconsistente | Nunca é capacidade livre |

Ordem: Livres; depois Pressionados; depois créditos permitidos de provedores Esgotados; sem candidato, nada muda.
A janela semanal por modelo (Opus, Sonnet) conta como semana para o modelo correspondente.
A histerese continua valendo dentro de cada grupo; a passagem de um grupo para outro não espera a histerese.

## Rede de segurança (D-28, D-29)

- Em Auto, a conversa recebe `fallback_providers` com a rota do outro provedor para o papel `conversation` do mapa aprovado.
- Cada rota de subagente recebe o seu próprio `fallback_providers` com a rota do outro provedor para o mesmo papel.
- Os campos `fallback_providers` entram nos grupos inscritos: linha de base, diário, restauração em OFF e exclusão por edição externa seguem as regras da S3.
- Um provedor Esgotado sem créditos permitidos não entra na cadeia; uma cadeia vazia é gravada como lista vazia apenas se a linha de base tinha a chave.
- O Hermes troca no meio da resposta quando recebe erro de cota e volta ao primário quando a espera termina; o plugin não intercepta chamadas.
- Chats do Desktop sem escolha manual trocam no turno seguinte a cada decisão do Auto; chats fixados manualmente continuam no modelo escolhido e só trocam pela rede de segurança.

## Correções de leitura e tipos de plano

| Cenário | Defeito ou lacuna | Comportamento exigido |
|---|---|---|
| A22 | Janela Claude com `resets_at` nulo torna a leitura inteira desconhecida | Janela ociosa ou não iniciada é tratada como 0% usado, sem invalidar as demais |
| A23 | Diferença de relógio de 1 s em janela Codex não iniciada bloqueia o provedor e os créditos | Tolerância de relógio limitada; inconsistência nunca bloqueia créditos por si só |
| A29 | Reset passado com janela antiga no servidor bloqueia o provedor por 5 min | Motivos estruturais não usam o backoff de falha |
| A31 | `additional_rate_limits` por modelo são ignorados | Bloquear apenas o modelo afetado, quando a fonte nativa expuser o campo |
| A32 | Uso acima de 100% vira desconhecido | Limitar a 100% e tratar como Esgotado |
| A38 | Janela Codex sem uso numérico invalida a duração publicada | Contar apenas janelas com uso numérico |
| A26 | Plano mensal (ChatGPT Go) bloqueado sem motivo | Motivo explícito `monthly_plan_unsupported` no status |
| A27 | Plano só de créditos nunca é escolhido | Tratado como Esgotado com créditos, sujeito a `credits.<provedor>` |
| A34 | Formato novo anunciado para dezembro | Falha fechada com motivo de requalificação, sem capacidade inventada |

## Testes de aceitação

- Cenários A16–A39 acrescentados ao mapa de cenários, cada um com teste unitário e, quando houver escrita, teste de integração.
- Matriz de pares de plano: (5 h + semanal, só semanal) × (5 h + semanal, só semanal), com as transições Livre → Pressionado → Esgotado em cada lado.
- Ciclo de vida de `fallback_providers`: aplicação, releitura, OFF com restauração exata, edição externa excluindo o grupo.
- Piloto real autorizado: chat do Desktop fixado em Sol que, ao receber erro de cota do Codex, continua em Opus pela rede de segurança.
- Chat aberto sem escolha manual troca de provedor no turno seguinte a uma decisão do Auto, já confirmado por Guilherme em 2026-11-17.
- Bot Chat: escolha manual por `/model` é descartada na troca seguinte do profile; documentar como comportamento nativo.

## Fora do escopo

- Patch no core para conversas do Desktop seguirem o profile a cada turno: desnecessário, o backend já faz isso para chats sem escolha manual.
- Trava própria do plugin (descartada por D-30).
- Janela Fable e créditos Anthropic visíveis ao plugin (HQR-23).
- Auxiliares (HQR-29, HQR-39).
