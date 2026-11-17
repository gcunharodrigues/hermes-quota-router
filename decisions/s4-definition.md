---
type: Product Definition
title: S4 — promoção, release e onboarding
description: Definição proposta da última fatia do plano HQR-20: release estável, instalação nos profiles escolhidos, onboarding de profiles novos, recarga do Desktop e rollback; decisões D-S4-1 a D-S4-5 abertas.
status: draft
---

# S4 — promoção, release e onboarding

Esta definição detalha a fatia S4 da [emenda HQR-20](hqr-20-amendment.md#10-fatias-propostas): "Release estável, instalação nos profiles escolhidos e onboarding de profiles novos".
Ela parte da HQR-38 aceita em 2026-11-17 e integrada na `main`.
Todos os itens marcados como proposta dependem das decisões D-S4-1 a D-S4-5 de Guilherme.

## Problema

O roteador funciona em um profile, instalado a partir de uma candidata identificada por SHA.
Não há versão publicada que outro desenvolvedor possa instalar e rastrear, nem procedimento repetível para levar o plugin a outros profiles ou a profiles novos.
O piloto mostrou que a instância do Desktop pode continuar com o código anterior depois de uma instalação (HQR-41).
O retorno à versão anterior com estado migrado só foi provado em ensaio sintético.

## Resultado utilizável

- Uma release versionada na `main`, com notas legíveis, SHA40 e receita de instalação com pin.
- O plugin instalado nos profiles escolhidos, começando em Observe, com leitura de cotas conferida em cada um.
- Um passo de onboarding que inclui o roteador na criação de um profile novo, começando em OFF ou Observe.
- Um procedimento de operação que confere a instância que responde no Desktop e orienta a recarga (HQR-41).
- Um procedimento de atualização e rollback exercitado no alvo de teste, incluindo estado migrado.

## Fatos observados

- Cada profile tem a própria configuração e o próprio estado do plugin; um profile sem o plugin habilitado não está inscrito.
- Profiles da mesma conta leem as mesmas cotas, mas cada instância do plugin decide sozinha a partir delas.
- O backend de subagentes exigido (`model_map` do plugin advanced-delegation) precisa estar habilitado em cada profile inscrito.
- O plano original pede isolamento de dev, teste e produção (HQR-05); o uso atual é um único host pessoal com alvo de teste em Docker.

## Decisões abertas

| ID | Pergunta | Opções | Proposta do agente |
|---|---|---|---|
| D-S4-1 | Em quais profiles instalar, além do principal | Nenhum; alguns; todos | Profiles que usam as mesmas assinaturas, começando em Observe |
| D-S4-2 | Formato da release | Só SHA com pin; tag Git; tag com GitHub Release | Tag `v0.3.0` com GitHub Release e notas, sem artefato binário |
| D-S4-3 | Onboarding de profiles novos | Manual pela operação; passo no procedimento de criação de profile | Passo no procedimento de criação, começando em OFF, Observe após conferência |
| D-S4-4 | Isolamento HQR-05 | Exigir isolamento completo; aceitar o host pessoal como limite declarado | Aceitar como limite declarado, mantendo o Docker para ensaios |
| D-S4-5 | Rollback com estado migrado | Exercitar no Docker antes da release; aceitar a prova sintética | Exercitar uma vez no Docker antes da release |

## Critérios de aceite propostos

1. A release aponta para um commit da `main`, e a instalação pela receita reproduz HEAD e arquivos rastreados conferidos.
2. Em cada profile escolhido, o status em Observe mostra leituras das duas contas, qualificação válida e nenhuma rota bloqueada.
3. Nenhum profile passa para Auto sem pedido explícito de Guilherme para aquele profile.
4. Um profile novo criado pelo procedimento sai com o plugin inscrito no modo combinado, verificado por leitura da configuração.
5. O procedimento HQR-41 é seguido numa instalação real e o status do Desktop traz os campos da versão instalada.
6. Atualização e rollback, inclusive com estado migrado, são exercitados no alvo de teste com OFF, restauração e leitura de volta.
7. O repositório publicado não contém caminhos, nomes ou identificadores da máquina do operador.

## Não objetivos

- Não governar `auxiliary.*` nesta fatia; isso é a fatia de auxiliares (HQR-29/HQR-39).
- Não prometer interceptação por chamada, teto de gastos ou recuperação de chamadas em andamento.
- Não alterar auto-update de outros plugins nem configurações de credenciais.

## Riscos

- Várias instâncias do plugin consultam as mesmas APIs de uso; a taxa de consultas pode subir (HQR-25).
- Um profile com mapa de subagentes diferente exige um mapa aprovado próprio antes de Auto.
- A recarga manual do Desktop pode ser esquecida; o procedimento precisa de uma conferência explícita.
