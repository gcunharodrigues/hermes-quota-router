---
type: Product Specification
title: Mapa de cenários de uso — HQR-20
description: Cenários de cota, créditos, consumidores, configuração e falhas que o roteamento das próximas tarefas precisa cobrir, com o resultado esperado e a fatia que prova cada um.
status: draft
---

# Mapa de cenários de uso — HQR-20

Pedido de Guilherme em 2026-11-15 (D7 da [emenda](hqr-20-amendment.md)).
Cada cenário tem o resultado esperado com os padrões da seção 13 da emenda e a fatia que o prova: S2 (Observe) mostra a decisão sem gravar nada fora do plugin; S3 (Auto) aplica.
Um cenário marcado S2/S3 é provado nas duas: a decisão em Observe e a escrita em Auto.

## Fluxo da decisão

```text
leitura nativa das cotas ──► leitura válida? ──não──► desconhecida: candidato inelegível
          │sim
          ▼
  candidatos do papel no mapa (variante: base, +Fable, +Astra, +ambos)
          │
          ▼
  franquia elegível? ──sim──► ranking por ritmo + histerese
          │não                     (conversa: principal enquanto elegível)
          ▼
  créditos permitidos? (credits.<provedor>, credits.order)
          │sim ──► candidato pago com créditos
          │não ──► nenhum candidato: nada muda, status mostra motivo e reset
          ▼
  modo observe ──► só mostra          modo auto ──► grava o grupo inteiro
                                                    │
                     consumidores que leem depois ◄─┘
```

## A. Cotas e créditos

| ID | Situação | Resultado esperado | Fatia |
|---|---|---|---|
| A1 | Codex e Claude com folga | Ranking por ritmo; a conversa fica no principal (Codex) | S2/S3 |
| A2 | Codex esgotado, Claude com folga | Rotas e conversa vão para Claude, mesmo com `credits.openai-codex` ligado | S2/S3 |
| A3 | Claude esgotado, Codex com folga | Rotas e conversa ficam ou vão para Codex | S2/S3 |
| A4 | Os dois esgotados, `credits.openai-codex` ligado | Codex pago com créditos | S2/S3 |
| A5 | Os dois esgotados, `credits.openai-codex` desligado | Nenhum candidato; nada muda; status mostra motivo e os dois resets | S2/S3 |
| A6 | Claude com janela de sessão bloqueada e semana com folga | Claude inelegível até o reset da sessão | S2/S3 |
| A7 | Reset passou desde a última leitura | Nova leitura antes de decidir; sem ela, desconhecida | S2 |
| A8 | Leitura ausente, vencida, futura ou malformada | Desconhecida, nunca capacidade livre | S2 |
| A9 | Leitor nativo falha ou muda de formato | Desconhecida; status mostra o erro; Auto não escreve | S2/S3 |
| A10 | Vantagem do desafiante de exatamente 10% | Mantém a preferência anterior | S2 |
| A11 | Saldo de créditos do Codex acabou | Codex pago deixa de ser candidato; com os dois esgotados, nenhum candidato | S2/S3 |
| A12 | Duas máquinas ou clientes externos usam a mesma assinatura | A leitura seguinte reflete o consumo; não há coordenação | S2 |
| A13 | Reset do Codex com Claude como preferência | Conversa volta ao principal; rotas voltam só se o Codex superar a preferência em mais de 10% | S2/S3 |
| A14 | Desafiante com vantagem acima de 10% | Troca a preferência da rota | S2 |
| A15 | Estado de créditos da Anthropic | Mostrado como não verificável; `credits.anthropic` decide | S2 |

## B. Modelos e variantes do mapa

| ID | Situação | Resultado esperado | Fatia |
|---|---|---|---|
| B1 | `models.fable` desligado | Fable nunca é candidato | S2 |
| B2 | `models.fable` ligado e janela do Fable com folga | Fable é candidato do papel que o mapa indicar; hoje o leitor nativo não expõe essa janela, então Fable fica desconhecido (HQR-23) | Depois de HQR-23 |
| B3 | `models.fable` ligado e janela do Fable esgotada, ausente ou não exposta | Fable inelegível; `credits.anthropic` desligado impede uso pago | S2/S3 |
| B4 | `models.astra` ligado, Astra no catálogo da conta e `model_usage` do Codex com Astra disponível | Astra é candidato do papel que o mapa indicar | S2/S3 |
| B5 | `models.astra` ligado e Astra fora do catálogo ou indisponível em `model_usage` | Variante cai para a base; status explica | S2 |
| B6 | Papel sem entrada aprovada no mapa | Papel não roteado | S2/S3 |
| B7 | Qualquer variante, papel da conversa | Candidato Codex é `gpt-6.1-sol` xhigh | S2 |

## C. Consumidores

| ID | Situação | Resultado esperado | Fatia |
|---|---|---|---|
| C1 | Sessão de conversa nova depois de uma decisão | Começa no modelo decidido | S3 |
| C2 | Sessão de conversa já aberta | Mantém o modelo com que foi criada | S3 |
| C3 | Sessão Bot Chat aberta | Troca de modelo no turno seguinte, por desenho nativo; a S3 só escreve a conversa depois do aceite de HQR-24 | S3 |
| C4 | Subagente de sessão comum, nova ou aberta | Usa a rota decidida | S3 |
| C5 | Sessão gerenciada (Kanban, bypass) criada antes da decisão | Mantém a rota antiga, inclusive em workers novos; status mostra fora da cobertura | S3 |
| C6 | Sessão gerenciada criada depois da decisão | Usa a rota decidida | S3 |
| C7 | Cron sem pin | Usa a decisão no tick seguinte | S3 |
| C8 | Cron com provider, modelo e endpoint fixados | Não muda | S3 |
| C9 | Existe job de cron com pin parcial | Auto não muda as chaves globais do cron; status lista o job | S2/S3 |
| C10 | `/model` na sessão ou modelo explícito numa chamada de subagente | Respeitado; fora da decisão | S3 |
| C11 | Auxiliares, retries e fallbacks | Não governados; status mostra | S2 |
| C12 | Tarefa em andamento quando a franquia acaba | Comportamento nativo; o plugin registra | S3 |

## D. Configuração e operação

| ID | Situação | Resultado esperado | Fatia |
|---|---|---|---|
| D1 | `mode` muda de off para observe | Começa a ler cotas; não grava fora do plugin | S2 |
| D2 | `mode` muda para auto | Captura a linha de base de cada grupo e passa a aplicar | S3 |
| D3 | `mode` volta a off | Restaura a linha de base dos grupos intactos; relata os outros | S3 |
| D4 | Um consumidor desligado em `consumers.*` | Seu grupo volta à linha de base, se intacto, e deixa de ser escrito | S3 |
| D5 | Valor inválido em `/quota-router config` | Recusado; valor anterior mantido | S2 |
| D6 | Guilherme edita uma rota inscrita com Auto desligado | Nova linha de base na próxima inscrição | S3 |
| D7 | Guilherme edita uma rota inscrita com Auto ligado, fora da janela de escrita | O grupo sai do Auto; nada é sobrescrito | S3 |
| D8 | Edição dentro da janela de escrita | Pode ser perdida (D6 aceito) | — |
| D9 | Dois processos decidindo ao mesmo tempo | Um escreve; o outro relê e não mistura o grupo | S3 |
| D10 | Escrita interrompida no meio de um grupo | O próximo ciclo completa ou desfaz antes de decidir | S3 |
| D11 | Hermes sem atividade por horas | Configuração pode estar defasada; status mostra a idade | S2/S3 |
| D12 | Valor inválido gravado por `hermes config set` ou à mão | Status mostra o valor inválido; Auto não escreve; Observe marca a decisão como incompleta | S2/S3 |

## E. Ciclo de vida e ambiente

| ID | Situação | Resultado esperado | Fatia |
|---|---|---|---|
| E1 | Plugin desabilitado ou removido com Auto declarado | Configuração fica com a última decisão; ausência aparece no status e no diagnóstico | S3 |
| E2 | Remoção | Exige OFF efetivo antes | S2/S3 |
| E3 | `hermes update` muda as funções internas usadas | O plugin detecta ao carregar e suspende o Auto sem escrever | S3 |
| E4 | Profile não inscrito, inclusive um novo | Nada muda; status do profile mostra que não está inscrito | S2 |
| E5 | Rollback para a revisão anterior do plugin | Estado e configurações compatíveis; smoke no alvo antes de reativar | S2 |
| E6 | Instalação no Hermes de trabalho (D1) | Backup, readback, Observe e ensaio de retirada e reinstalação, que é o rollback ali; rollback de revisão ensaiado no alvo de teste | S2 |
