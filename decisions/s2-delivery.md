---
type: Delivery Record
title: S2 — Observe com cotas reais
description: Registro da execução da S2 — RED, GREEN, revisão crítica, publicação, ensaio instalado e piloto no Hermes de trabalho.
status: draft
---

# S2 — Observe com cotas reais

Plano: [s2-plan.md](s2-plan.md), revisado com GO em `24e8ef6`.
Branch `hermes/2026-11-15-hqr-s2`.

## Estado corrente

- RED `5750b7e`: testes de configurações, leituras, política, inventário, mapa e comandos.
- GREEN: módulos `settings`, `readings`, `policy`, `inventory`, `mapping` e comandos `status`, `explain` e `config`; versão `0.2.0rc1`.
- Suítes em ambiente limpo: unidade 38, integração 1 e harness 7, todas passando; testes protegidos da S1 sem mudança.
- Revisão crítica, rodada 1 sobre `55dc5b7`: três NO-GO com 26 achados bloqueantes, entre eles leituras nativas que podiam gravar arquivos (`load_jobs`, `load_config_readonly`), nomes de jobs expondo trechos de prompt, valores inválidos repetidos na saída, cache sem revalidar reset, tolerância a leitura futura, arredondamento nos limiares, mapa sem aprovação e guard só na unidade.
- RED da rodada 1 `48e9bbf`; correções em seguida, com o runner `scripts/run_tests.py` e o guard também na integração.
- Revisão crítica, rodada 2 sobre `7a89e52`: três NO-GO; ficaram abertos leitura de configuração que grava backup com YAML malformado, validade das leituras no instante da decisão, escopo de janela, janela inconsistente já esgotada levando a créditos, evidência de créditos sem falha fechada, catálogo do Astra, superfície do status e preferência sem revisão do mapa; novos: mapa aprovado contornando Fable e Astra e textos com forma de URL ou chave no inventário.
- RED da rodada 2 `f2990ef`; correções em `02f1af7`.
- Revisão crítica, rodada 3 sobre `02f1af7`: três NO-GO, com a maior parte resolvida; ficaram status sem as notas do mapa e sem as mudanças por papel, mapa aprovado com modelo do provedor errado, ids de job e provedores com forma de segredo, negação explícita do Codex com janelas livres, leitura de inventário depois da checagem de idade e rótulo posicional do host para janela de duração desconhecida.
- RED da rodada 3 `9ed2706`; correções em `2600b58`.
- Revisão crítica, rodada 4 sobre `2600b58`: resolvidos status, papéis por provedor, segredos, contradição do Codex e ordem do inventário; abertos a duração usada de outra janela, esforços nativos `max` e `ultra` descartados e a falta de aprovação para ler `limit_window_seconds`.
- RED da rodada 4 `e69f7c2`; correções em `1c81903`; aprovação do campo registrada em `40e1741`.
- Revisão crítica, rodada 5 sobre `40e1741`: código sem achados nas três perspectivas; segurança e testes GO; a revisão geral mantém a S2 incompleta só pelo TE-10 (ensaio instalado, rollback e piloto).
- Regressão opcional da rodada 5: esforço `max` num modelo padrão gera par forte.
- Runner instalado `tests/installed/s2_observe.py`, com candidato e rollback por argumento; helpers puros testados em `tests/harness/test_s2_observe_harness.py`; os arquivos protegidos da S1 seguem iguais.
- Controle prévio no alvo, sem credenciais: o leitor nativo devolveu `None` para os dois provedores, sem evento de rede ou subprocesso.
- Pendente: histórico limpo publicado como candidato S2 (exige autorização de push), execução do runner, piloto no Hermes de trabalho (D1) e DEMO.
- Leitura de `rate_limit.<janela>.limit_window_seconds` para qualificar a duração das janelas do Codex: aprovada por Guilherme em 2026-11-15 e incluída na lista fechada da seção 14 da emenda; o valor não é guardado nem exibido.

## Achado durante a execução

Num ambiente em que o leitor nativo do Hermes era importável, um teste protegido em Observe chegou ao leitor real.
Correções: `quota_queries` passou a contar só o período do modo atual, com `quota_queries_total` para a instância; os guards de unidade e integração encerram a suíte antes de qualquer teste quando o leitor nativo está no caminho; e `scripts/run_tests.py` é a entrada suportada, em ambiente limpo.
