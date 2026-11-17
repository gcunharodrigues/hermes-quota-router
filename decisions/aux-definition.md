---
type: Product Definition
title: Fatia de auxiliares — roteamento de auxiliary.* por tipo de assinatura
description: Definição proposta para HQR-29 e HQR-39 — as tarefas auxiliares fixadas no Codex passam a seguir a decisão de cota, com mapa Terra → Sonnet e Luna → Haiku e exceções; decisões D-AUX-1 a D-AUX-4 abertas.
status: draft
---

# Fatia de auxiliares

Esta definição atende [HQR-29 e HQR-39](../README.md#backlog).
A S3 e a HQR-38 não governam `auxiliary.*`.
Todos os itens marcados como proposta dependem das decisões D-AUX-1 a D-AUX-4 de Guilherme.

## Problema

As tarefas auxiliares do Hermes — títulos, compressão de contexto, revisão de fundo, aprovação, juiz de metas, monitor, triagem, voz e outras — ficam fixadas no Codex com modelos menores.
Quando a franquia do Codex acaba, elas continuam no Codex e usam créditos da OpenAI, mesmo com a assinatura Claude livre.
Algumas são frequentes, como compressão e revisão de fundo, e consomem franquia sem passar pelo roteador.

## Fatos observados

- No Hermes de trabalho, onze tarefas auxiliares estão fixadas no Codex: quatro com Luna e esforço low e sete com Terra, esforço low ou medium.
- Tarefas sem modelo fixado usam `auto`, escolha nativa ainda não qualificada (HQR-29).
- A configuração de cada tarefa auxiliar é lida do `config.yaml` a cada uso, salvo quando a sessão tem um instantâneo próprio das auxiliares; o alcance desse instantâneo ainda precisa ser rastreado por superfície.
- A leitura atual do Codex traz só a janela semanal; a Anthropic traz janela de 5 h e semanal.
- `image_gen` fica fixo no Codex, porque a Anthropic não tem modelo de geração de imagem (observação de Guilherme em 2026-11-17).

## Resultado utilizável proposto

- As tarefas auxiliares fixadas passam a ser grupos do roteador, com a mesma linha de base, diário, releitura e OFF com restauração exata da S3.
- Quando o roteador escolhe Claude para o grupo, a tarefa vai para o equivalente Claude; quando escolhe Codex, volta ao modelo original.
- Mapa proposto (HQR-29): Terra → Sonnet e Luna → Haiku, mantendo o esforço de cada tarefa.
- Exceções fixas: `image_gen` e tarefas sem equivalente na Anthropic ficam no Codex.
- Tarefas em `auto` não são governadas nesta fatia.

## Decisões abertas

| ID | Pergunta | Opções | Proposta do agente |
|---|---|---|---|
| D-AUX-1 | Como as auxiliares escolhem o provedor | A: seguem a escolha da conversa; B: decisão própria pela mesma política; C: ficam no provedor oposto ao da conversa para dividir carga | A, por ser a mais simples e previsível |
| D-AUX-2 | Mapa de modelos | Terra → Sonnet e Luna → Haiku; outro mapa | Terra → Sonnet e Luna → Haiku, mantendo o esforço |
| D-AUX-3 | Tarefas incluídas | Todas as fixadas no Codex exceto `image_gen`; só as frequentes (compressão, revisão de fundo, títulos) | Todas as fixadas, exceto `image_gen` e voz em tempo real se exigir recurso só do Codex |
| D-AUX-4 | Ordem em relação à S4 | Auxiliares antes da S4; S4 antes das auxiliares | Auxiliares antes, para a release da S4 já incluir o recurso |

## Critérios de aceite propostos

1. Em Observe, o status mostra para cada tarefa auxiliar incluída o modelo atual, a escolha e o que mudaria.
2. Em Auto, as tarefas incluídas recebem o equivalente do provedor escolhido; a releitura da configuração confere modelo, provedor e esforço.
3. Uma tarefa auxiliar executada depois da decisão registra o modelo roteado, verificado no registro de sessões ou no log do Hermes.
4. OFF restaura cada tarefa à linha de base, inclusive campos ausentes.
5. Edição manual de uma tarefa auxiliar exclui o grupo do Auto, como nas rotas da S3.
6. `image_gen` e tarefas em `auto` permanecem inalterados.
7. A qualificação nativa cobre as funções do Hermes que leem `auxiliary.*`, com impressões digitais medidas.

## Não objetivos

- Não governar tarefas em `auto` nem alterar a escolha nativa.
- Não criar fallback por erro para auxiliares sem verificar que o Hermes o suporta nessa superfície.
- Não prometer economia de franquia sem medição.

## Riscos

- Um instantâneo de auxiliares por sessão pode atrasar a troca até a próxima sessão; precisa ser rastreado e declarado.
- Revisão de fundo e compressão em Claude consomem a janela de 5 h, que é a mais curta.
- Modelos equivalentes podem produzir resultados diferentes em tarefas sensíveis, como aprovação.
