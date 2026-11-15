---
type: Delivery Plan
title: S2 — Observe com cotas reais
description: Plano da fatia S2 da emenda HQR-20 — leituras nativas, política, configurações e Observe no alvo de teste e no Hermes de trabalho, sem gravar fora do plugin.
status: draft
---

# S2 — Observe com cotas reais

Fatia S2 da [emenda HQR-20](hqr-20-amendment.md), aprovada por Guilherme em 2026-11-15.
Este plano é do agente e passa por revisão independente antes da execução.

## Resultado utilizável

No Hermes de trabalho de Guilherme, `/quota-router status` e `/quota-router explain` mostram, por papel, a assinatura que o Auto escolheria, as leituras de cota com idade e fonte, o motivo da escolha, as variantes do mapa e o que ficaria fora da cobertura.
`/quota-router config` mostra e muda as configurações da seção 13 da emenda.
Nada é gravado fora do subtree do plugin; `mode auto` continua recusado até a S3.

## Escopo

- `quota_router/settings.py`: esquema, padrões e validação das configurações da seção 13, lidas e gravadas só por `ctx.get_config` e `ctx.set_config`.
- `quota_router/readings.py`: adaptador do leitor nativo `agent.account_usage.fetch_account_usage(provider, read_only=True)` para Codex e Claude, com janela, percentual, reset, escopo, idade e fonte; ausente, vencida, futura, malformada ou com erro vira desconhecida.
- `quota_router/policy.py`: decisão determinística da seção 5 da especificação e das seções 6, 13 e 14 da emenda: limiares, ritmo semanal, histerese, principal na conversa, créditos por provedor e ordem, variantes de Fable e Astra.
- `quota_router/inventory.py`: leitura, sem escrita, das rotas de subagente, do bloco de modelo da conversa e dos jobs de cron do profile, para mostrar o que o Auto mudaria, os pins e os jobs com pin parcial.
- `quota_router/catalog.py`: disponibilidade de Astra pela descoberta nativa de modelos da conta, sem tokens no plugin.
  Na execução, o catálogo nativo só oferece Astra com o token da conta; sem descoberta qualificada, a S2 mantém a variante base, como manda a seção 15 da emenda, e o status explica.
- Comandos `status`, `explain` e `config` em `quota_router/lifecycle.py` e o `config_schema` de `plugin.yaml`.
- A decisão de Observe roda só nos comandos `status` e `explain`, com cache das leituras pelo tempo de `limits.reading_max_age_s`; a S2 não registra hooks, que entram na S3.
- O plugin usa do `ctx` só `get_config`, `set_config`, `register_command` e `on_unload`; leituras de cota e da configuração do profile usam funções nativas de leitura, sem gravação.
- Documentação: `docs/s2-operations.md`, `docs/testing.md`, `docs/compatibility.md`, README e registro de entrega `decisions/s2-delivery.md`.

## Cenários e critérios

Critérios: AC-01, AC-03, AC-06, AC-10 a AC-12, AC-14 a AC-17, AC-24 e AC-25 nos cenários marcados S2 ou S2/S3 do [mapa](hqr-20-scenarios.md).
Os cenários A, B e D viram testes de unidade da política e das configurações, um caso por linha, com relógio e leituras sintéticos.
O mapa de D5 sai como saída de `explain` com as quatro variantes; Guilherme o aprova depois da S2, antes da S3.
Fixtures ficam identificadas como sintéticas e nunca aparecem no status como cota real.

## Testes e verificações

```sh
python3 -m unittest discover -s tests/unit -p 'test_*.py' -v
python3 -m unittest discover -s tests/integration -p 'test_*.py' -v
python3 -m unittest discover -s tests/harness -p 'test_*.py' -v
python3 -m compileall -q __init__.py quota_router
okf --root . --json validate --profile per-repo --gate both
```

Seguir RED/GREEN com testes novos e preservar os testes protegidos da S1.
A integração usa um `ctx` falso e um leitor nativo falso que devolve snapshots no formato do host.
Um teste confere que, depois de `status`, `explain` e `config`, a configuração do profile fora do subtree do plugin tem o mesmo hash.
Os testes protegidos da S1 continuam sem mudança e precisam passar:

- `tests/integration/test_export.py` exige manifesto sem hooks e nenhuma capacidade além das quatro acima; no Observe sem leitor nativo disponível, nenhuma leitura é emitida e `quota_queries` fica em zero.
- `tests/unit/test_default.py` e `tests/unit/test_modes.py` exigem zero leituras em OFF, que continua valendo.
- Se a implementação mostrar que algum deles precisa mudar, a execução para e pede aprovação específica de Guilherme com o trecho exato.

O ensaio instalado usa um runner novo, `tests/installed/s2_observe.py`, com candidato e revisão de rollback passados como argumentos; `tests/installed/lifecycle.py` fica como prova da S1.
No alvo de teste, sem credenciais, o leitor nativo devolve indisponível: o status precisa mostrar cota desconhecida com a fonte, contar a tentativa de leitura e não gravar fora do subtree.
O runner também ensaia o rollback de revisão: OFF, `--force --ref` para a revisão anterior com scanner `safe`, arquivos iguais, smoke em OFF e volta ao candidato.

## Publicação

A instalação nativa precisa da revisão no GitHub.
O commit local `d1bd80a` tem endereços internos (SEC-S1-04) e está no histórico da S1, base desta branch.
Antes do push, montar um histórico limpo a partir de `ad3e180` com a árvore revisada, conferir que nenhum commit publicado contém os endereços e só então publicar, depois da revisão aprovada.

## Piloto no Hermes de trabalho (D1)

1. Backup datado de `config.yaml` e da pasta de plugins do profile `default`, com hash.
2. `hermes plugins install gcunharodrigues/hermes-quota-router --ref <SHA40 revisado> --no-enable`, scanner nativo `safe` e arquivos instalados iguais à revisão.
3. Habilitar, conferir OFF, mudar para Observe e rodar `status`, `explain` e `config`.
4. Conferir que a configuração fora do subtree do plugin não mudou e que nenhuma inferência extra foi feita.
5. Ensaiar o rollback local, que no Hermes de trabalho é voltar ao estado sem o plugin: OFF, desabilitar, remover, conferir que não sobrou arquivo nem entrada do plugin e que o resto da configuração tem o hash do backup, e reinstalar a mesma revisão até Observe.
6. Manter o piloto em Observe para Guilherme usar.

Parar se o scanner não der `safe`, se algum arquivo divergir, se a configuração fora do subtree mudar ou se o Hermes não carregar; nesse caso, desabilitar e remover o plugin e restaurar do backup só a entrada `plugins.entries.hermes-quota-router` e a pasta do plugin, sem tocar no resto.
Se o host exigir restart do gateway, a execução para e pede autorização de Guilherme; o restart só acontece sem tarefa em andamento.

## Caminhos e limites

Caminhos permitidos: `__init__.py`, `plugin.yaml`, `quota_router/`, testes novos em `tests/unit/`, `tests/integration/` e `tests/harness/`, `tests/installed/s2_observe.py`, `docs/`, `decisions/` e README.
Não objetivos: escrita de rotas, cron ou modelo (S3), extensão do core (HQR-23), Fable como candidato, outros profiles.
Proibido: monkey-patch, leitura de tokens ou auth stores pelo plugin, inferência própria, mudança em testes protegidos, e qualquer escrita no Hermes de trabalho além da instalação do plugin e do seu subtree.
