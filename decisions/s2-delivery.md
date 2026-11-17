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
- Revisão do runner: NO-GO em `e33461c` (status de plugin desabilitado, OFF não conferido, volume não admitido, exceções amplas do host) e em `2132b87` (remoção de backup sem rotação); GO em `36eb409`.
- Publicação autorizada por Guilherme em 2026-11-15: candidato `214f0280705e97e42c2168dbee3654b52c617950`, histórico limpo sobre `ad3e180` com a árvore revisada, na branch remota `hermes/2026-11-15-hqr-s2`; a `main` não mudou e o histórico local com endereços internos e observações de conta não foi publicado.

## Ensaio instalado no alvo de teste

Alvo `hqr-s1-test` (rede bridge, volume próprio, sem credenciais), candidato `214f028`, rollback `ad3e180`; os resultados estão resumidos nesta seção, sem registros brutos distribuídos.

- Run 1: parou no passo 8 por erro do runner, que comparava as configurações do plugin pela chave de topo; o host guarda `credits.anthropic` como árvore aninhada. Corrigido em `0a72348`.
- Run 2: parou no passo 14, porque o `.env` de modelo do profile de teste criado no passo 10, só com comentários, caiu no controle de arquivos com nome de credencial. O runner passou a apagar o profile de teste em `2dcd489`; o controle não foi afrouxado.
- Run 3, runner `2dcd489`: 15 de 15 passos.
  - Instalação do candidato com scanner nativo `safe` e bytes iguais à revisão; OFF sem leitura de cotas.
  - AUTO recusado sem mudar arquivo algum.
  - Observe: os dois provedores desconhecidos (`no_snapshot`), fonte nativa, contadores 2, 4 e 6 por processo, zero inferência e nenhum evento de rede ou subprocesso nos comandos.
  - Gravações do Observe: só chaves do plugin (`mode`, `credits.anthropic`, `limits.hysteresis_pct`); o host gravou dois backups `good` do `config.yaml`, iguais à configuração sem as chaves do plugin, e apagou os dois mais antigos pela retenção de cinco.
  - Valor inválido gravado por fora aparece só com tipo e motivo; o comando recusa o mesmo valor; `config reset` limpa.
  - Profile novo sem o plugin e sem entrada na configuração (E4); o profile de teste é apagado no fim do passo.
  - Rollback para `ad3e180` (`0.1.0rc1`) e volta ao candidato (`0.2.0rc1`) com scanner `safe`; OFF confirmado antes de cada troca; remoção sem resto e reinstalação a partir dos padrões.
  - Controles de isolamento repetidos; o listener sintético no gateway da bridge continua alcançável, como registrado em HQR-22.
  - Estado final do candidato em OFF; Hermes de trabalho com o mesmo fingerprint de antes.
- O scanner nativo deu `safe` com 37 achados de padrão, os mesmos tipos que vêm dos testes e do harness (por exemplo, segredos e IPs sintéticos de fixture).
- O runner publicado em `214f028` é anterior a `0a72348` e `2dcd489`; o plugin instalado não muda, e a próxima publicação leva o runner corrigido.
- Revisão independente da evidência instalada: GO para o piloto D1, sem achados bloqueantes.

## Piloto no Hermes de trabalho (D1)

Driver `tests/installed/s2_pilot.py` (`f6abf89`), candidato `214f028`, profile `default`; recibos fora do Git, porque trazem leituras reais.

- 9 de 9 passos em 2026-11-15:
  - Pré-condições: plugin ausente e candidato igual à cabeça da branch publicada.
  - Backup datado de `config.yaml` e da pasta de plugins, com SHA256, em `backups/hqr-pilot-<data>`.
  - Scanner nativo `safe` sobre o arquivo do candidato.
  - Instalação desabilitada, com bytes, HEAD e metadados iguais ao candidato.
  - Habilitado em OFF, sem leitura de cotas.
  - Observe com as leituras reais dos dois provedores, ambas válidas, e decisões na ordem de D3: franquia antes de créditos, sem créditos da Anthropic; todas as decisões como `proposal_only`, porque nenhum mapa foi aprovado; zero inferência; só a chave `mode` gravada no plugin; resto da configuração com o mesmo hash.
  - Rollback local: OFF confirmado, desabilitar, remover, sem árvore nem metadados nem entrada, e o resto da configuração com o hash do backup.
  - Reinstalação da mesma revisão, de novo em Observe a partir dos padrões.
  - Checkout do Hermes e `uv.lock` sem mudança; só a pasta do plugin foi acrescentada.
- Restart do gateway autorizado por Guilherme em 2026-11-15 e feito com drenagem nativa (`hermes gateway restart`, sem `--interrupt`); serviço ativo de novo, sem erro do plugin no log.
- Depois do restart, um consumidor novo carrega o plugin da pasta instalada, em Observe, versão `0.2.0rc1`, sem restart pendente; as leituras reais seguem válidas e a recomendação é a mesma, só como proposta.
- DEMO, primeira tentativa: Guilherme rodou `/quota-router status` no app e recebeu JSON, difícil de ler; pediu saída para humanos para tornar a conclusão e os limites legíveis sem interpretar JSON.
- Saída legível em `quota_router/render.py`, com JSON só por `--json`; prévia com as leituras reais aprovada para seguir.
- Aprovação de Guilherme em 2026-11-15 para mudar os testes protegidos da S1 só no pedido de JSON: `tests/unit/test_modes.py`, `tests/unit/test_failures.py` e `tests/integration/test_export.py` passam a chamar o comando com ` --json`, e o probe de `tests/installed/lifecycle.py` acrescenta ` --json`; nenhuma asserção muda. Aprovou também publicar a nova versão e reinstalar no Hermes de trabalho com novo restart do gateway.
- `tests/unit/test_default.py`, `tests/unit/test_concurrent.py` e `tests/unit/test_identity.py`, também da S1, liam o JSON e tinham ficado fora da lista; Guilherme aprovou a mesma mudança para eles (seis chamadas, sem mudar asserção).
- Revisão independente, rodada 1 de `545fcd0`: NO-GO com oito achados.
O probe instalado da S1 enviava `--json` também ao rollback S1, que recusa o argumento; o texto declarava créditos disponíveis com limite de gastos atingido ou não verificável; `explain` escondia configuração inválida e decisão incompleta; janelas por modelo e limites configurados abaixo de 100% ficavam sem nome; a histerese aparecia fixa em 10%; mapa parcial aparecia inteiro como aprovado; faltavam idade da leitura, mapas por papel e a recomendação geral sem inventário; pins só de endpoint eram descritos errado.
- Correções: `tests/installed/lifecycle.py` voltou aos bytes de `82e888d`; os runners S2 usam `tests/installed/s2_probe.py`, derivado do probe S1, que só pede `--json` quando o plugin carregado tem `render.py`, sem comando extra; o texto segue a política de créditos, nomeia janela e limite, usa a histerese efetiva, separa aprovado de proposto e mostra os campos que faltavam.
Testes novos em `tests/unit/test_s2_render.py` e `tests/harness/test_s2_probe_harness.py`.
- Re-revisão independente, rodada 2 de `7c7f3b5`: NO-GO com três achados médios: créditos apareciam disponíveis quando a política rejeitava a leitura por datas inconsistentes ou negação contraditória do provedor; faltava a fonte da leitura; `explain` atribuía à cota semanal geral um bloqueio da cota semanal do Opus.
- Correções: o texto usa o veredito de conta da própria política (`policy.eligibility`) e diz que nem a franquia nem os créditos serão usados; mostra a fonte geral e a de cada leitura; a política registra `blocked_window` (tipo e família da janela que bloqueou), campo aditivo usado só no texto.
- Re-revisão independente, rodada 3 de `22295ef`: GO, sem achados bloqueantes; 109 testes.
- Publicação (aprovada por Guilherme): candidato `6abf28f04d53cba1eb7a520ef494e4cd3867363d`, árvore de `22295ef` sobre `214f028`, na branch remota nova `hermes/2026-11-15-hqr-s2-readable`; `main` sem mudança; histórico local não publicado.
- Ensaio instalado run 4 (`hqr-s1-test`, candidato `6abf28f`, rollback `ad3e180`): 15 de 15 passos; os recibos mostram `--json` só nas revisões com `render.py`.
- Troca no Hermes de trabalho: backup datado com SHA256; `214f028` desligado (OFF), desabilitado e removido sem mudar chaves fora do plugin; piloto `s2_pilot.py --branch hermes/2026-11-15-hqr-s2-readable` com `6abf28f`: 9 de 9 passos; plugin em Observe.
O piloto ganhou `--branch`, com a branch anterior como padrão.
- Gateway reiniciado sem `--interrupt`, com a autorização de Guilherme; consumidor novo devolve o `status` em texto.
- DEMO, segunda tentativa: o texto foi aprovado, mas o status dizia que o plugin não lia a Anthropic, o que contradizia a leitura esperada.
Verificação: a leitura nativa pode trazer somente a semana geral, sem janela de 5 h nem semana própria do Opus; o plugin não infere uma janela ausente nem recebe a semana do Fable ou os créditos da Anthropic (HQR-23).
O modelo da conversa mostrado é o padrão do profile, não o da sessão aberta.
- Texto corrigido: a linha do Claude explica a falta das janelas e quem não informa os créditos; a conversa aparece como modelo padrão do profile para sessões novas; `str.capitalize` deixava de minúscula "Hermes" e "Claude" e foi trocado.
- Revisão independente do piloto, rodada 1 de `34f505d`: NO-GO num achado médio: `--branch` aceitava padrões, que `git ls-remote` expande, e a checagem olhava só o primeiro SHA.
Correção: o nome da branch precisa ser literal, e a checagem exige exatamente uma linha com o SHA e o ref completo; harness `tests/harness/test_s2_pilot_harness.py`.
- Re-revisão independente do piloto, rodada 2 de `8809e3f`: GO; 113 testes.
- Com o sim de Guilherme: candidato `2a94c81604fb202d43fe610f4507d2e96f4310a6` (árvore de `8809e3f` sobre `6abf28f`) publicado em `hermes/2026-11-15-hqr-s2-readable`; ensaio instalado run 5: 15 de 15; troca no Hermes de trabalho com backup datado, remoção de `6abf28f` e piloto `s2_pilot.py`: 9 de 9; plugin em Observe; consumidor novo devolve `status`, `explain` e `config` em texto.
- Processos que guardam o plugin antigo na memória: gateway, backend do app desktop e serviço do dashboard reiniciados depois da troca.
- DEMO, terceira tentativa, no app desktop: o Claude apareceu como "leitura indisponível" e a recomendação foi Codex com créditos.
Causa medida: a API de uso da Anthropic responde 429 com `retry-after: 300` depois de cinco consultas seguidas; o Hermes a consulta depois de cada turno, e o leitor nativo devolve `None` sem dizer o motivo.
O teste de rajada que confirmou o limite também gastou a cota de consultas por cinco minutos.
- Primeira correção (`f625623`): usar a última leitura guardada pelo Hermes (`cached_account_usage`) quando a busca falha.
Revisão independente do cache, rodada 1: NO-GO (HQR-CACHE-01, alto): a vaga legada do cache não está ligada à conta selecionada agora; depois de troca de conta ou logout, a leitura de outra conta passaria como válida, e só lendo credenciais o plugin provaria a ligação.
Também (HQR-CACHE-02, baixo): o texto e a documentação apresentavam o limite de cinco minutos como contrato, e `None` não identifica o motivo.
- Correção final: o fallback saiu; o texto da leitura sem resposta da Anthropic cita o limite de consultas como causa possível e o 300 s como resposta observada; a ligação conta–leitura sem token vai ao backlog do core (HQR-25).
- Re-revisão independente do cache, rodada 2 de `341e3ce`: GO; 114 testes; o item HQR-25 entrou no backlog.
- Com o sim de Guilherme: candidato `ad113d95604128fcdf9c446e2c5bd9c75bff0860` (árvore de `1264aaa` sobre `2a94c81`) publicado em `hermes/2026-11-15-hqr-s2-readable`; ensaio instalado run 6: 15 de 15; troca no Hermes de trabalho com backup datado e piloto: 9 de 9.
- Decisão de Guilherme em 2026-11-16: `limits.reading_max_age_s` = 300 no Hermes de trabalho, gravado pelo comando do plugin.
- Restarts: gateway, dashboard e backend do app desktop.
- DEMO e aceite: Guilherme aceitou a S2 em 2026-11-16, no candidato `ad113d9` instalado em Observe no Hermes de trabalho.
O aceite não autoriza merge na `main`, release nem a S3.
- Leitura de `rate_limit.<janela>.limit_window_seconds` para qualificar a duração das janelas do Codex: aprovada por Guilherme em 2026-11-15 e incluída na lista fechada da seção 14 da emenda; o valor não é guardado nem exibido.

## Achado durante a execução

Num ambiente em que o leitor nativo do Hermes era importável, um teste protegido em Observe chegou ao leitor real.
Correções: `quota_queries` passou a contar só o período do modo atual, com `quota_queries_total` para a instância; os guards de unidade e integração encerram a suíte antes de qualquer teste quando o leitor nativo está no caminho; e `scripts/run_tests.py` é a entrada suportada, em ambiente limpo.
