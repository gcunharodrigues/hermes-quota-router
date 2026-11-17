---
type: Product Definition
title: Fatia de auxiliares — roteamento de auxiliary.* por tipo de assinatura
description: Definição proposta para HQR-29 e HQR-39 — emenda a HQR-20 para que tarefas auxiliares fixadas no Codex possam seguir a decisão de cota, com mapa Claude por tarefa, matriz de estados da HQR-38 e liga/desliga próprio; decisões D-AUX-1 a D-AUX-6 abertas.
status: draft
---

# Fatia de auxiliares

Esta definição atende HQR-29 e HQR-39 do backlog do [README](../README.md).
É uma proposta de emenda: a [seção 9](hqr-20-amendment.md#9-o-que-esta-emenda-substitui) e a [seção 12](hqr-20-amendment.md#12-não-objetivos) da emenda HQR-20 deixam auxiliares fora e não governados, e a S3 e a HQR-38 seguiram essa regra.
Aceitar esta fatia muda essa regra para as tarefas auxiliares incluídas, preservando o não objetivo de interceptar chamadas já iniciadas.
Tudo o que não está em "Fatos observados" é proposta e depende das decisões D-AUX-1 a D-AUX-6 de Guilherme.

## Problema

As tarefas auxiliares do Hermes — títulos, compressão de contexto, revisão de fundo, aprovação, juiz de metas, monitor, triagem, voz e outras — podem ficar fixadas no Codex com modelos menores.
Quando a franquia do Codex acaba, elas continuam no Codex e usam créditos da OpenAI, mesmo com a assinatura Claude livre.
O volume de chamadas de cada tarefa não foi medido.

## Fatos observados

- Leitura somente leitura da configuração do Hermes de trabalho, em 2026-11-17 às 19:36 (−03): onze tarefas em `auxiliary.*` fixadas no Codex, três com Luna (`title_generation`, `profile_describer`, `tts_audio_tags`) e oito com Terra.
- Tarefas sem modelo fixado usam `auto`, escolha nativa ainda não qualificada (condição de HQR-29).
- A configuração de cada tarefa auxiliar é lida da configuração do profile a cada uso, por leitor com cache invalidado pela assinatura do arquivo; a exceção são sessões em modo de bypass da configuração do usuário, que usam só os padrões do código e ficam fora do alcance do roteador.
- Uma tarefa registrada com `inherit_from` segue a configuração efetiva da tarefa base até ter rota própria.
- `image_gen` é chave de topo da configuração, fora de `auxiliary.*`, e fica fixa no Codex porque a Anthropic não tem modelo de geração de imagem (observação de Guilherme em 2026-11-17).
- A matriz de estados por provedor da HQR-38 (Livre, Pressionada, Esgotada, Desconhecida, créditos por provedor) já decide conversa e rotas de subagentes.

## Resultado utilizável proposto

- As tarefas incluídas em D-AUX-3 passam a ser grupos do roteador, com a mesma linha de base, diário, releitura, exclusão por edição manual e OFF com restauração exata da S3.
- A escolha de provedor segue D-AUX-1 e usa a matriz de estados da HQR-38, o que cobre os tipos de assinatura pedidos em HQR-39: janela de 5 h e semanal da Anthropic, janela semanal do Codex, estados desconhecidos e créditos.
- Com Claude esgotado e `credits.anthropic` desligado, nenhuma auxiliar vai para Claude; com os dois esgotados, nenhuma chave muda, como em AC-22.
- Modelo e esforço do lado Claude seguem o mapa de D-AUX-2, com esforço próprio por provedor como no precedente D9.
- Nova configuração `consumers.auxiliary`, desligada por padrão, liga e desliga a função como as demais da seção 13 da emenda.
- AC-18, AC-19, AC-20, AC-22, AC-23 e AC-24 passam a valer para os grupos auxiliares; AC-21 ganha o caso de uma tarefa auxiliar executada depois da decisão.

## Decisões abertas

| ID | Pergunta | Opções | Proposta do agente |
|---|---|---|---|
| D-AUX-1 | Como as auxiliares escolhem o provedor | A: seguem a decisão do papel conversa gravada pelo Auto, não o modelo da sessão aberta; B: decisão própria por grupo pela mesma política; C: provedor oposto ao da conversa para dividir carga | A; com `consumers.conversation` desligado, as auxiliares usam a decisão calculada para a conversa mesmo sem aplicá-la |
| D-AUX-2 | Mapa de modelos e esforço no lado Claude | Terra → Sonnet e Luna → Haiku com o mesmo esforço; esforço próprio por tarefa; outro mapa | Terra → Sonnet e Luna → Haiku, com esforço por tarefa conferido contra os níveis aceitos pelos modelos Claude |
| D-AUX-3 | Tarefas incluídas | Todas as fixadas no Codex; uma lista menor | Todas as fixadas no Codex, salvo uma tarefa que exija recurso exclusivo do Codex, a confirmar na qualificação |
| D-AUX-4 | Ordem em relação à S4 | Auxiliares antes da S4; S4 antes | Auxiliares antes, para a release da S4 já incluir o recurso |
| D-AUX-5 | Tarefas em `auto` | Qualificar nesta fatia; manter fora e abrir item próprio no backlog | Manter fora e abrir item próprio, porque a escolha nativa não é controlada pelo plugin |
| D-AUX-6 | Aprovar a emenda da regra "auxiliares fora" | Sim; não | Sim, restrita às tarefas incluídas e sem interceptar chamadas iniciadas |

## Critérios de aceite

1. Em Observe, o status mostra para cada tarefa incluída o modelo atual, a escolha, o estado dos provedores e o que mudaria, e grava zero chaves fora do subtree do plugin.
2. Em Auto, com `consumers.auxiliary` ligado, as tarefas incluídas recebem o modelo e o esforço do mapa para o provedor escolhido; a releitura da configuração confere modelo, provedor e esforço.
3. Com `consumers.auxiliary` desligado, nenhuma chave auxiliar muda.
4. Com Claude esgotado e `credits.anthropic` desligado, nenhuma tarefa auxiliar é movida para Claude; com os dois esgotados, nenhuma chave muda e o status mostra motivo e reset.
5. Uma tarefa auxiliar executada depois da decisão usa o modelo roteado, comprovado por um registro do Hermes cuja existência é verificada antes da fatia; sem esse registro, o critério fica como limite declarado.
6. OFF restaura cada tarefa à linha de base, inclusive campos ausentes; edição manual exclui o grupo do Auto.
7. Tarefas fora de D-AUX-3, tarefas em `auto` e `image_gen` permanecem inalteradas.
8. A qualificação nativa cobre as funções do Hermes que leem `auxiliary.*`, com impressões digitais medidas.

## Não objetivos

- Interceptar, repetir ou trocar uma chamada auxiliar já iniciada.
- Governar tarefas em `auto` sem a decisão D-AUX-5.
- Prometer economia de franquia sem medição.

## Riscos

- Revisão de fundo e compressão em Claude consomem a janela de 5 h, a mais curta; o volume não foi medido.
- Modelos equivalentes podem produzir resultados diferentes em tarefas sensíveis, como aprovação.
- A seleção de uma tarefa auxiliar pode não deixar registro de modelo por chamada, limitando a prova do critério 5.
