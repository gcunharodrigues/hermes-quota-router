# Update Log

## 2026-11-15

- [S2](s2-delivery.md) implementada localmente (RED `5750b7e`, GREEN em seguida); um teste protegido fez duas leituras reais no ambiente do agente, corrigido com contador por período de modo e guard de ambiente hermético.
- [Plano da S2](s2-plan.md) e desdobramento das decisões D1 a D7 revisados: GO em `24e8ef6` depois de uma rodada de correções (créditos do Codex lidos de campos fechados de `raw`, conversa só com aceite de HQR-24, valores inválidos, runner instalado próprio, rollback e restart como gate).
- [Emenda HQR-20 aprovada](hqr-20-amendment.md#8-decisões) por Guilherme com D1 a D7: Observe no Hermes de trabalho, conversa nas sessões novas, créditos só da OpenAI por configuração, mapas com e sem Fable e Astra, escritor único e [mapa de cenários](hqr-20-scenarios.md); README e `AGENTS.md` atualizados conforme a seção 9.
- [Emenda HQR-20](hqr-20-amendment.md) proposta: rotear as próximas tarefas pela configuração nativa, S2 em Observe com cotas reais e S3 em Auto; decisões D1 a D5 abertas; a primeira revisão pediu cobertura por cópia congelada de configuração, pins parciais do cron, grupos de chaves com linha de base, custo residual de créditos e retirada de observações de conta, incorporados à proposta; depois de seis rodadas (R1 a R10 resolvidos), a revisão independente deu GO em `ae771d0`, e a emenda aguarda a aprovação de Guilherme.
- [S1 aceita](s1-delivery.md#aceite) por Guilherme ("Sim", 2026-11-15 11:31 -0300) para `ad3e180` no alvo de teste; merge, push, produção e S2 seguem com gates próprios.
- [Run 4](../docs/s1-installed-test.md#run-4--ciclo-de-vida-completo-com-rede-2026-11-15): com alvo de teste com internet, por decisão de Guilherme, os 17 passos do ciclo de vida passaram contra o candidato instalado pelo GitHub; falta revisão independente e DEMO.
- [Revisão crítica](../docs/s1-installed-test.md#revisão-crítica-e-run-5b-2026-11-15): quatro bloqueantes corrigidos (observação de produção sem processos, scanner antes do `--force`, listeners do host e endereços no documento); run 5b com 17 passos aprovados.
- [Revisão crítica concluída](s1-delivery.md#revisão-independente-crítica): rechecagem final de segurança GO em `50e3135`, rodada no Claude depois de duas falhas HTTP 400 na rota Codex; publicação continua dependendo de excluir `d1bd80a` do histórico.
- [Segunda rodada](../docs/s1-installed-test.md#segunda-rodada-e-run-6-2026-11-15): admissão de rede antes das mutações e exceção DHCP restrita; run 6 com 18 passos aprovados.
- Guilherme decidiu simplificar o produto depois da S1 (HQR-20): rotear as próximas tarefas a partir das leituras nativas, sem interceptar cada chamada; a política de créditos (HQR-21) segue pendente.
- Decisão do responsável: a entrega deste produto passa ao fluxo conversacional direto do coordenador `default`, a partir da S1 em curso.
- Os cards S1/S2 do board `hermes-quota-router` ficam congelados como histórico; não são mais despachados ao `product-lead`, e a DEMO/aceite passam a ocorrer na conversa do responsável.
- Branch, worktree, candidato publicado `ad3e180`, negativa `AdmissionRefused` do run 2 e achados bloqueantes S1-REV-001, SEC-S1-01/02 e TE-S1-001/002/003 permanecem válidos e abertos.
- A migração não autoriza nova tentativa de `enable`, reconstrução do alvo de teste, push, merge, release ou produção.
- Autorizada a correção do cache na recipe, a reconstrução do alvo e uma única tentativa offline de `enable`; a [habilitação nativa](../docs/s1-installed-test.md#run-3--habilitação-nativa-offline-2026-11-15) passou e resolveu a negativa de admissão, sem qualificar ainda o lifecycle.
- [Ciclo de vida instalado](../docs/s1-installed-test.md#run-3--ciclo-de-vida-instalado-parcial): passos 1–10 aprovados; remoção nativa bloqueada por EXDEV do overlayfs na árvore embutida na imagem (HQR-19).
- [Run 3b](../docs/s1-installed-test.md#run-3b--alvo-com-volume-de-estado-2026-11-15): teste protegido ajustado com aprovação para o volume de estado; nova habilitação recusada ao resolver `setuptools` pelo índice, o que corrige a leitura anterior de que a admissão offline estava resolvida.

## 2026-11-12

- Complemento crítico S1: três pareceres `blocked`, guarda e 50 hashes estáveis, bloqueantes parcialmente supridos sem GO; novo opcional TE-S1-007 registrado em HQR-18, sem mudar testes protegidos.
- [Ensaio instalado S1](../docs/s1-installed-test.md): candidato GitHub exato instalado desabilitado no Docker admitido, com dois RED/GREEN operacionais e comparação de 34 arquivos.
- A habilitação foi recusada pelo PM em rede offline; S1 permanece bloqueada, com negativa/readback preservados e HQR-16/17 abertos, sem repetir enable ou avançar o lifecycle.
- [Estado S1](s1-delivery.md), README e navegação separam a prova parcial do run 2 dos pareceres históricos e dos passos não exercitados.

- [S1 corrente](s1-delivery.md) registra três pareceres independentes críticos bloqueados por provas operacionais ausentes, guarda estável e quatro recomendações opcionais no backlog, sem mudança posterior de código/testes.
- [S1 corrente](s1-delivery.md) implementa gestão OFF/Observe, identidade declarada, comparação de payload e gate de linhas com RED/GREEN sintéticos; instalação e isolamento do destino continuam pendentes.
- [Operação](../docs/s1-operations.md), [testes](../docs/testing.md) e [compatibilidade](../docs/compatibility.md) separam prova local de host real; AUTO, inferência, publicação e produção não foram ativados.

- Repositório limpo preparado com licença MIT, OKF `per-repo` e índices CodeGraph locais independentes.
- [Spec](product-spec.md) e [plano](product-plan.md) transpostos para publicação sem histórico, inventário ou dados privados da origem.
- [Bootstrap corrente](bootstrap.md) mantém revisão/confirmação de commit e permissões de publicação separados; nenhum código, inferência, instalação ou ativação executados.
