---
type: Product Definition
title: S4 — promoção, release e onboarding
description: Definição proposta da última fatia do plano HQR-20 — release estável com proveniência, instalação nos profiles escolhidos, onboarding com status de profiles não inscritos, recarga do Desktop e rollback; decisões D-S4-1 a D-S4-6 abertas.
status: draft
---

# S4 — promoção, release e onboarding

Esta definição detalha a fatia S4 da [emenda HQR-20](hqr-20-amendment.md#10-fatias-propostas): "Release estável, instalação nos profiles escolhidos e onboarding de profiles novos".
Ela parte da HQR-38 aceita em 2026-11-17 e integrada na `main`.
Atende também HQR-06 (distribuição), HQR-41 (recarga do Desktop) e a substituição da seção 8 da especificação pela [seção 9 da emenda](hqr-20-amendment.md#9-o-que-esta-emenda-substitui): onboarding de cada profile com o status mostrando profiles sem o plugin.
Tudo o que não está em "Fatos observados" é proposta e depende das decisões D-S4-1 a D-S4-6 de Guilherme.

## Problema

O roteador funciona em um profile, instalado a partir de uma candidata identificada por SHA.
Não há versão estável publicada que outro desenvolvedor possa instalar e rastrear, nem procedimento repetível para levar o plugin a outros profiles ou a profiles novos.
O piloto mostrou que a instância do Desktop pode continuar com o código anterior depois de uma instalação (HQR-41).
O retorno à versão anterior com estado migrado só foi provado em ensaio sintético.

## Fatos observados

- O manifesto `plugin.yaml` está na versão `0.3.0rc1`.
- O status de cada instância declara `effective_scope = this_plugin_instance_only`: cada profile inscrito decide a partir das próprias leituras, sem coordenação entre instâncias.
- Um profile sem o plugin habilitado não está inscrito; o status do profile inscrito já aponta como conferir os outros (cenário E4 do [mapa de cenários](hqr-20-scenarios.md)).
- Subagentes dependem do backend `model_map` do plugin advanced-delegation habilitado no mesmo profile ([sondas da S3](s3-delivery.md), linha C4).
- No piloto da HQR-38, o OFF enviado pelo CLI e o enviado pelo Desktop divergiram, sem causa comprovada ([registro](hqr-38-delivery.md#saída-da-versão-anterior)).
- A emenda mantém valendo isolamento de ambientes, distribuição por SHA completo e rollback; o plano exige recibo com versão do host e do Python, schema do estado e comparação de arquivos ignorados com a allowlist ([plano, seções 6 e 7](product-plan.md#7-distribuição-instalação-e-atualização)).

## Resultado utilizável, condicionado às decisões

- Release identificada pelo SHA40 de um commit da `main`, com notas legíveis; o formato do rótulo segue D-S4-2, e o manifesto deixa de ser candidato de release.
- Receita de instalação sempre com `--ref <SHA40>`, nunca só por rótulo mutável, instalando sem habilitar e começando no modo definido em D-S4-3.
- Instalação nos profiles escolhidos em D-S4-1, cada um com autorização própria de instalação e de mudança de modo.
- Onboarding: o status mostra quais profiles não estão inscritos, e o procedimento de criação de profile inclui o roteador conforme D-S4-3.
- Procedimento de operação que confere a instância que responde no Desktop e orienta a recarga (HQR-41).
- Atualização e rollback com a prova escolhida em D-S4-5.

## Decisões abertas

| ID | Pergunta | Opções | Proposta do agente |
|---|---|---|---|
| D-S4-1 | Em quais profiles instalar, além do principal | Nenhum; alguns; todos | Os que usam as mesmas assinaturas, um de cada vez |
| D-S4-2 | Formato da release | Só SHA40 registrado; tag Git; tag com GitHub Release | Tag `v0.3.0` com GitHub Release e notas, sempre acompanhada do SHA40 |
| D-S4-3 | Modo inicial e configurações de um profile novo ou recém-instalado | OFF; Observe; e quais valores de `conversation.policy` e créditos | OFF na instalação, Observe após conferência; padrões do produto (`principal_first`, créditos OpenAI ligados, Anthropic desligados) salvo pedido do profile |
| D-S4-4 | Isolamento HQR-05 | Exigir isolamento completo de dev, teste e produção; aceitar o host pessoal como limite | Aceitar como limite declarado; isso exige emendar a regra de isolamento da emenda, do plano e do `AGENTS.md` e fechar HQR-05 como risco aceito |
| D-S4-5 | Prova de rollback com estado migrado | Exercitar no Docker antes da release; aceitar a prova sintética | Exercitar uma vez no Docker antes da release |
| D-S4-6 | Publicar a release no GitHub | Sim; não | Sim, depois do aceite da fatia e com a pergunta própria antes do push |

## Critérios de aceite

1. A instalação pela receita reproduz HEAD e arquivos rastreados do SHA40, sem arquivos ignorados fora da allowlist, e gera recibo com versão do host, Python e schema do estado.
2. Em cada profile autorizado para Observe, o status mostra `source_qualified = true`, `quota.states` para os dois provedores e `routing_blocks` vazio; leitura desconhecida aparece como desconhecida, e a conferência é repetida depois do intervalo de espera informado, sem consultas extras.
3. Nenhum profile passa para Auto sem pedido explícito de Guilherme para aquele profile.
4. O status de um profile inscrito mostra os profiles não inscritos, e um profile novo criado pelo procedimento sai com o plugin no modo e nas configurações de D-S4-3, conferidos por leitura da configuração.
5. O procedimento HQR-41 é seguido numa instalação real e o status do Desktop traz os campos da versão instalada.
6. A prova de rollback escolhida em D-S4-5 é executada e registrada; com prova no Docker, OFF, restauração e leitura de volta são conferidos com estado migrado.
7. As notas da release listam os limites abertos: erro de cota real não observado, HQR-23, HQR-25, HQR-27, HQR-28, HQR-36, HQR-40 e a divergência de OFF entre CLI e Desktop.
8. Árvore e histórico publicados não contêm caminhos, nomes ou identificadores da máquina do operador.
9. Proveniência e autorização (HQR-06): o SHA40 da release é a revisão revisada e aceita por Guilherme; push, publicação da release e instalação em cada profile têm autorização explícita registrada; a leitura de volta do remoto mostra o rótulo da release, quando houver, ou o próprio commit apontando para esse SHA40, e a leitura de volta de cada profile mostra esse HEAD instalado.

## Não objetivos

- Não governar `auxiliary.*` nesta fatia; isso é a [fatia de auxiliares](aux-definition.md).
- Não prometer interceptação por chamada, teto de gastos ou recuperação de chamadas em andamento.
- Não alterar auto-update de outros plugins nem configurações de credenciais.

## Riscos

- Várias instâncias consultam as mesmas APIs de uso, o que aumenta o risco de limite de taxa (HQR-25).
- Um profile com mapa de subagentes diferente exige mapa aprovado próprio antes de Auto.
- A recarga manual do Desktop pode ser esquecida; o procedimento precisa de conferência explícita.
- A divergência de OFF entre CLI e Desktop pode reaparecer em outros profiles; o OFF só vale com `applied` e leitura de volta.
