# Update Log

## 2026-11-17

- [Definições propostas da S4 e da fatia de auxiliares](s4-definition.md): rascunhos com decisões abertas D-S4-1 a D-S4-5 e [D-AUX-1 a D-AUX-4](aux-definition.md); backlog HQR-01, HQR-26, HQR-33, HQR-34 e HQR-35 fechado com evidência; nenhuma implementação.

- [Aceite da HQR-38](hqr-38-delivery.md#aceite-de-guilherme-2026-11-17): Guilherme aceitou a fatia, autorizou squash merge na `main` e push, e classificou HQR-42 como aceitável.

- [Decisão de Guilherme sobre o fallback](hqr-38-delivery.md#decisão-de-guilherme-sobre-o-fallback-2026-11-17): fallback por erro de cota aceito para a fatia com prova de código e testes offline; erro de cota real fica para observação natural; merge e push, previstos na mesma proposta, aguardam revisão, aceite e a pergunta própria.

- [Piloto real HQR-38](hqr-38-delivery.md#piloto-real-no-hermes-de-trabalho-2026-11-17): `cc878bc` instalada no Hermes de trabalho com autorização; Desktop recarregado pelo gerenciador de plugins, Observe com cotas reais, Auto aplicando conversa, dez rotas e 11 cadeias, sessão nova em Opus e OFF restaurando configuração; Auto religado por Guilherme; subagente `general` e cron de teste executados em Claude Opus; fallback auditado por código e 435 testes offline registrados do Hermes, sem erro de cota real; aceite da HQR-38 pendente.

- [Demonstração instalada offline HQR-38](hqr-38-delivery.md#resultado-observado-da-demonstração-offline): `cc878bc` instalada e conferida em 169 arquivos; uma tentativa Auto com troca de conversa e general em 95%, cadeia lida e OFF restaurado; cliente expirou em 120 s sem código de saída capturado, cinco registros e estado final conferidos depois, contêiner parado; sem piloto real ou alteração do Hermes de trabalho.

- [Recuperação do ensaio instalado HQR-38](hqr-38-delivery.md#recuperação-do-ensaio-instalado-2026-11-17): pacote autorizado após a revisão de preparação; fonte Docker medida diretamente, transição controlada dos dois testes de qualificação e correção do roteiro, sem mudar o algoritmo nem os guards; Auto ainda não repetido.

- [Suíte canônica completa HQR-38](hqr-38-delivery.md#suíte-canônica-completa-em-docker-sintético): commit `338bbfa` exercitado em Docker com 470 execuções verdes (353/19/98), exit 0 e nenhum skip; primeira tentativa com dois erros por falta da revisão Git antiga preservada, dependência suprida com objetos originais, sem alterar produto, testes ou guards; sem qualificação instalada, aceite, merge ou push.

- [Reconciliação crítica SOL-04](hqr-38-delivery.md#reconciliação-crítica-do-sol-04-sintético): general/security/tests aprovam a entrega sintética delimitada, com os cinco achados bloqueantes encerrados nesse escopo; candidata permanece WIP, sem GO global, suíte integral, instalação ou aceite humano.

- [SOL-04: publicação persistida e ida/volta sintéticas](hqr-38-delivery.md#publicação-e-idavolta-sintéticas-aguardando-rechecagem): REDs `39453fa` e `e6064ea`, comparação final corrigida, 27 IDs focados verdes e Engine legado exercitado com baseline corrente no retorno; rechecagem pendente, sem instalação, dados reais ou suíte integral.

- [Ajustes protegidos HQR-38 autorizados](hqr-38-delivery.md#ajustes-protegidos-autorizados-e-regressão-pura-2026-11-17): quatro diffs pontuais aprovados por Guilherme; regressão pura permitida com 114 IDs únicos e 114 passes, zero falhas/erros/skips, exit 0; integração editada não executada, persistência/rollback e instalação continuam bloqueados.

- [Correções SOL-01 a SOL-07](hqr-38-delivery.md#correção-dos-achados-sol-01-a-sol-07-2026-11-17): commits locais RED/correção, 114 IDs em regressão pura parcial com exit 1; testes protegidos preservados, migração e suites persistidas bloqueadas pela negativa de `auto.lock`; nenhum provedor, instalação ou publicação.

- [HQR-38 entrega local](hqr-38-delivery.md): 18 funções nativas da rede de segurança qualificadas (RED `64dbfb8`, GREEN `1c0d3b5`); entrada de trabalho requalificada, entrada Docker marcada para requalificação e recusada; runner instalado com a prova da rede de segurança, não executado.
- [HQR-38 entrega local](hqr-38-delivery.md): RED `61d5d79` e GREEN `07571e2`; 295 + 19 + 93 testes verdes; cenários A16–A39 e F1–F5 no [mapa](hqr-20-scenarios.md) e [operação](../docs/hqr-38-operations.md); nada publicado ou instalado.
- [HQR-38](hqr-38-spec.md): especificação proposta com as decisões D-28 a D-31 de Guilherme; aguarda aprovação.
- [Entrega S3](s3-delivery.md): ciclo OFF → restauração exata → Auto conferido; HQR-38 e HQR-39 registram a nova política pedida e os auxiliares por tipo de assinatura.
- [Entrega S3](s3-delivery.md): piloto Auto aplicado no Hermes de trabalho; 52 mudanças, todas nos grupos inscritos ou no modo, sem diário pendente.
- [Entrega S3](s3-delivery.md): Observe validado no Desktop de trabalho com as duas leituras e mapa aprovado; bloqueios de permissão do diretório de dados e de escopo de segredos do Hermes (HQR-37) resolvidos fora do código do plugin.

## 2026-11-16

- [HQR-35: backoff e motivos nativos opcionais](s3-delivery.md#hqr-35--backoff-e-motivos-nativos-opcionais): RED `6ae4d04` reproduz consultas repetidas, ausência de motivos e próxima tentativa; implementação local preserva desconhecido, compatibilidade com Hermes antigo e cache limpo na mudança de modo, sem consultar provedores ou instalar.

- [Correção local de HQR-34 e significado das leituras](s3-delivery.md#correção-local-de-hqr-34-e-significado-das-leituras): RED `e456205`, aviso corrigido sem mudar mapa/política, controles de cota esgotada versus desconhecida e 326 testes verdes; diagnóstico real delimitado permanece privado, sem reparar login ou atualizar a instalação.

- [Instalação D18 em Observe](s3-delivery.md#instalação-d18-em-observe-e-nova-prévia): candidata `0376def` instalada com arquivos exatos, settings e demais configurações preservados, aprendizagem automática restaurada e nova prévia por dispatcher nativo; sem Auto ou restart, com superfície Desktop ainda não exercitada e aviso genérico registrado em HQR-34.

- [Repetição D18 aprovada no Docker](s3-delivery.md#repetição-d18-aprovada-no-docker): recuperação autorizada comprovou OFF e baseline; `0376def` passou 16/16 passos, 323 testes locais e cinco checks posteriores, com alvo em Observe e sem mudar a instalação de trabalho.

- [Candidata D18 publicada e ensaio interrompido](s3-delivery.md#candidata-d18-publicada-e-ensaio-interrompido): `0376def` publicada; 13 passos PASS e novos cenários D18 passaram, mas timeout externo impediu o fechamento; alvo com candidata exata desabilitada e OFF salvo, sem comprovação final de OFF efetivo ou aceite.

- [Prova R3 encerrada](s3-delivery.md#fechamento-da-prova-r3-em-bc119a6): rechecagem focada aprovou a fixture e o controle mutante sobre `bc119a6`; sem bloqueantes locais, com publicação e repetição instalada de D18 ainda pendentes.

- [Ajuste autorizado da fixture R3](s3-delivery.md#ajuste-autorizado-da-fixture-r3): fonte isolada válida, ambiguidade carregada recusada e controle mutante detectado; 323 testes passaram, sem alterar o plugin, com rechecagem focada pendente.

- [Rechecagem de R1/R3](s3-delivery.md#resultado-da-rechecagem-de-3c377a2): geral e segurança aprovaram; falta corrigir a fixture de ambiguidade que não alcança o guard pretendido, com autorização para uma rechecagem focada após o limite de rodadas.

- [Segunda correção R1/R3](s3-delivery.md#segunda-correção-de-r1-lambda-inline-r3-e-aliases): lambda inline nativa aceita por inspeção do arquivo completo, aliases vinculados nas duas fontes e controles de drift sem escritas; 323 testes passaram, com rechecagem e execução instalada ainda pendentes.

- [Reconciliação R1/R2 de D18](s3-delivery.md#reconciliação-do-coordenador-após-a-retomada): contagens do teste criado nesta fatia e plano atualizados; 317 testes passaram na coordenação, com rechecagem independente pendente e runtime preservado.

- [Achados R1/R2 de D18](s3-delivery.md#correção-dos-achados-r1r2-de-d18-2026-11-16): caminho normal de resolução vinculado por 134 funções/18 constantes em cada host e overlay global recusado por nome; 12 métodos novos RED/GREEN, com runner completo bloqueado somente pelas contagens protegidas S3 de 73/12 ainda sem autorização de ajuste; sem publicação ou mutação do runtime.

- [Correção do preview S3](s3-delivery.md#correção-dos-três-defeitos-de-preview-s3-2026-11-16): D18 aceita defaults nativos qualificados, expõe bloqueios por papel e mostra mapa/qualificação reais; RED/GREEN e 305 testes locais, sem publicação ou mutação do runtime; HQR-33 mantém a revisão e a repetição instalada pendentes.
- [Ensaio instalado S3](s3-delivery.md#ensaio-instalado-no-alvo-docker-de-teste-2026-11-16): candidata `ba5d6f8` passou 16 de 16 passos no alvo Docker de teste; DEMO e piloto aguardam autorização.
- [Segundo ensaio S3 publicado](s3-delivery.md#segundo-ensaio-da-candidata-publicada-2026-11-16): candidata `161392a` instalada, fingerprints aprovados e Auto parcialmente exercitado; parada no diagnóstico Rich truncado e C5/C6 bloqueados por `posix_spawn`; seis testes novos, correções somente locais, regressão 177/13/90 verde e alvo preservado desabilitado com Auto salvo, sem rollback exercitado.

- [Correção dos achados HQR-32](s3-delivery.md#correção-dos-achados-do-runner-hqr-32-2026-11-16): SEC-01/SEC-02, TEST-01 e RUN-01 corrigidos com 17 testes novos RED/GREEN; 177/13/84 testes verdes, protegidos S1 preservados e rechecagem/publicação/ensaio instalado pendentes, sem mutação Docker.

- [Primeiro ensaio S3 publicado](s3-delivery.md#primeiro-ensaio-da-candidata-publicada-2026-11-16): admissão aprovada e parada no scanner de advanced-delegation antes da instalação de `db77b6e`; correção local do guard com três testes RED/GREEN, alvo S2 em OFF e revisão/republicação pendentes em HQR-32.

- [Hosts sem Git e higiene pública](s3-delivery.md#continuação--hosts-sem-git-e-higiene-pública-2026-11-16): correspondência completa com opt-in e revisão desconhecida explícita, fonte Docker conferida somente por leitura, comentários rastreáveis e resumos sanitizados; fechamento bloqueado por HQR-30/HQR-31, sem publicação ou instalação.

- [Preparação S3 para Docker](s3-delivery.md#preparação-para-publicação-e-ensaio-docker-2026-11-16): entrada de fonte com 71 funções/nove constantes, manifesto público de 23 arquivos e admissão somente de leitura aprovada; ausência de `.git/HEAD` no core impede a compatibilidade nativa, sem mutação do alvo ou publicação.
- [Entrega da S3](s3-delivery.md#revisão-independente-da-implementação): três revisores independentes aprovaram a implementação local em `f7c5a96`, depois de duas rodadas de correção; ensaio instalado e publicação aguardam autorização.
- [Revisão S3, rodada 2](s3-delivery.md#revisão-de-implementação-rodada-2-2026-11-16): G8 preserva a preferência Observe → Auto e TE-06 vincula C12 à emissão atual com hash salgado e watermark; oito testes novos, 166/13/58 verdes, sem ensaio instalado ou acesso ao Hermes real.

- [Revisão S3, rodada 1](s3-delivery.md#revisão-de-implementação-rodada-1-2026-11-16): G1–G7, SEC-S3-01–06 e TE-01–05 corrigidos localmente, 229 testes herméticos únicos, quatro testes nativos separados e 13 testes I repetidos com a camada original; sem instalação ou alteração do Hermes real.

- [Catálogo nativo models.dev na S3](s3-delivery.md#continuação--catálogo-nativo-modelsdev-2026-11-16): memória nativa antes do leitor offline, sem gate do piso curado, aviso de IDs não verificados e motivo para IDs ausentes; 142/9/44 testes verdes, 71 fingerprints e quatro constantes por leitura de fonte, sem instalação ou inferência.

- [C4/C10 locais resolvidos](s3-delivery.md#continuação--c4c10-fechados-localmente-2026-11-16): advanced-delegation 1.1.0 fixado, Auto/YAML nativo, persistência/retomada da escolha explícita e backend de subagentes com metadados somente em loopback; 187 testes herméticos, sem ensaio Docker, inferência ou alteração do Hermes real.

- [Continuação da S3](s3-delivery.md#continuação--probes-nativos-locais-2026-11-16): runner com resolução nativa de consumidores e qualificação negativa da fonte de sessão, 174 testes herméticos verdes e gates C4/C10 mantidos; sem instalação, Docker, inferência ou acesso à configuração real.

- [S3 — entrega local parcial](s3-delivery.md): implementação autorizada a partir de `f7f3136`, RED/GREEN para Auto, diário e projeções fechadas, com a única alteração protegida aprovada em D14; ensaio instalado, qualificação Docker, publicação e piloto continuam pendentes.

- [S2 aceita](s2-delivery.md) por Guilherme no candidato `ad113d9`, em Observe no Hermes de trabalho; `main` avançou para `ad113d9`.
- [Emenda HQR-20, seção 17](hqr-20-amendment.md#17-decisões-de-2026-11-16-para-a-s3): Bot Chat pode trocar de modelo (HQR-24 fechado), mapa `base` aprovado com esforço por provedor, histerese mantida e conversa por ritmo no Hermes de trabalho.
- [Plano da S3](s3-plan.md) aprovado pela revisão independente na sexta rodada (`0af5ec4`), com as decisões D8 a D17 de Guilherme na [seção 17 da emenda](hqr-20-amendment.md#17-decisões-de-2026-11-16-para-a-s3); execução aguarda pedido de Guilherme.

## 2026-11-15

- [S2](s2-delivery.md) implementada localmente (RED `5750b7e`, GREEN em seguida); um teste protegido fez duas leituras reais no ambiente do agente, corrigido com contador por período de modo e guard de ambiente hermético.
- [Plano da S2](s2-plan.md) e desdobramento das decisões D1 a D7 revisados: GO em `24e8ef6` depois de uma rodada de correções (créditos do Codex lidos de campos fechados de `raw`, conversa só com aceite de HQR-24, valores inválidos, runner instalado próprio, rollback e restart como gate).
- [Emenda HQR-20 aprovada](hqr-20-amendment.md#8-decisões) por Guilherme com D1 a D7: Observe no Hermes de trabalho, conversa nas sessões novas, créditos só da OpenAI por configuração, mapas com e sem Fable e Astra, escritor único e [mapa de cenários](hqr-20-scenarios.md); README e `AGENTS.md` atualizados conforme a seção 9.
- [Emenda HQR-20](hqr-20-amendment.md) proposta: rotear as próximas tarefas pela configuração nativa, S2 em Observe com cotas reais e S3 em Auto; decisões D1 a D5 abertas; a primeira revisão pediu cobertura por cópia congelada de configuração, pins parciais do cron, grupos de chaves com linha de base, custo residual de créditos e retirada de observações de conta, incorporados à proposta; depois de seis rodadas (R1 a R10 resolvidos), a revisão independente deu GO em `ae771d0`, e a emenda aguarda a aprovação de Guilherme.
- [S1 aceita](s1-delivery.md#aceite) por Guilherme em 2026-11-15 para `ad3e180` no alvo de teste; merge, push, produção e S2 seguem com gates próprios.
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
