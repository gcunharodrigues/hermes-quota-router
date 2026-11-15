---
type: Delivery Record
title: S1 — gestão local e gate do destino instalado
description: Candidato GitHub ad3e180 instalado, exercitado em todo o ciclo de vida no alvo Docker de teste, aprovado na revisão crítica e aceito por Guilherme.
status: draft
---

# S1 — entrega aceita

## Estado corrente — run 4, 2026-11-15

A entrega passou ao fluxo conversacional do `default`; os cards S1/S2 ficaram como histórico.
O [ensaio instalado](../docs/s1-installed-test.md#run-4--ciclo-de-vida-completo-com-rede-2026-11-15) exercitou os 17 passos do ciclo de vida contra o candidato `ad3e180` instalado pelo GitHub: OFF, Observe, recusa de AUTO, divergência entre processos, restart, disable, remove, reinstalação, rollback, retorno e controles de isolamento.
O alvo tem saída para a internet por decisão de Guilherme, volume de estado próprio, nenhum caminho do host e nenhuma credencial; o Hermes de produção ficou inalterado.
A primeira revisão crítica teve quatro bloqueantes, corrigidos no harness e na documentação; o run 5b passou de novo nos 17 passos ([detalhes](../docs/s1-installed-test.md#revisão-crítica-e-run-5b-2026-11-15)).
A segunda rodada exigiu a admissão de rede antes das mutações; o run 6 passou nos 18 passos ([detalhes](../docs/s1-installed-test.md#segunda-rodada-e-run-6-2026-11-15)).

### Revisão independente crítica

| Rodada | Snapshot | Geral | Segurança | Testes |
|---|---|---|---|---|
| 1 | `d1bd80a` | GO (3 opcionais) | NO-GO: SEC-S1-01, 03, 04 | NO-GO: TE-S1-008 |
| 2 | `a349492` | — | NO-GO: SEC-S1-01 parcial; 03 resolvido; 04 parcial | GO: 008, 009, 010 resolvidos |
| 3 | `50e3135` | — | GO: SEC-S1-01 resolvido | — |

As rodadas 1 e 2 usaram a rota `review` (`openai-codex`, `gpt-6.1-sol`, esforço xhigh).
Na rodada 3, duas tentativas nessa rota falharam com HTTP 400 do provedor, sem parecer; com autorização de Guilherme, a rechecagem rodou uma vez em sessão one-shot nova no Claude (`anthropic`, `claude-opus-5-5`), sem mudar configuração.
O workspace ficou idêntico antes e depois de cada rodada.
Os pareceres e logs ficam em `.runtime/s1-review/`.
O run 6 executou a mesma versão de `tests/installed/lifecycle.py` depois commitada em `50e3135`; entre o run e o commit só mudaram documentos.

Disposição dos achados:

- SEC-S1-01, SEC-S1-03 e TE-S1-008 a 010: resolvidos e rechecados.
- SEC-S1-04: o documento atual não tem endereços internos, mas o commit local `d1bd80a`, não publicado, ainda os tem; é gate de publicação, não de aceite da S1.
- Opcionais registrados em HQR-22: a admissão de rede roda depois do build da imagem e das sondas do passo 2; a bridge padrão permite tráfego entre containers (hoje só o alvo está nela).
- Opcional TE-S1-004 segue em HQR-13; os achados opcionais da rodada 1 do revisor geral foram atendidos pelas mesmas correções.

### Aceite

DEMO apresentada na conversa de Guilherme em 2026-11-15, com status, Observe, recusa de AUTO e OFF rodados ao vivo no alvo de teste (recibo privado `.runtime/s1-demo/demo.json`, fora do Git).
Guilherme respondeu "Sim" à pergunta "Você aceita a S1 como demonstrada?" em 2026-11-15 11:31 -0300.
O aceite vale para o plugin `ad3e180f32adea3c25a2ef91280f1f6308729a47` no alvo de teste, com a evidência e a revisão registradas até `28115a957d77ea86b71bf44964127aed4e3472ec`.
Ele não autoriza merge, push, release, instalação no Hermes de produção, uso de créditos nem o início da S2 sem a emenda de spec e plano de HQR-20.

## Histórico — run 2, 2026-11-12

A emenda operacional do card admitiu o alvo Docker de teste e o candidato publicado `ad3e180f32adea3c25a2ef91280f1f6308729a47`, sem autorizar publicação de revisões futuras.
O [ensaio instalado](../docs/s1-installed-test.md) registra instalação GitHub desabilitada, comparação dos 34 arquivos, host/Python/locks/imagem e limites dos controles negativos.
A habilitação nativa recebeu `AdmissionRefused`, exit 1, ao tentar baixar dependência com o alvo offline; nenhum retry, reparo ou contorno foi executado.
Readback confirmou handler ausente e deployment preservado; OFF/Observe ativos, restart, remoção, reinstalação e rollback ainda não foram exercitados.
S1 permanece bloqueada, sem GO, DEMO ou S2; default precisa dispor HQR-16/17 e a retomada precisa preservar os pins e a negativa.
Os REDs novos `01abcad` e `ac28c6c` são de preparação/instalação, sem alteração do candidato instalado ou dos testes antigos.
O repositório contém recipe e dois testes instalados adicionais; a revisão local futura não está publicada ou instalada como se fosse outro candidato.
Os recibos do run 2 estão preservados em `.runtime/s1-installed-run2/` da worktree da tarefa, não em scratch como única cópia nem anunciados como anexos.

## Complemento de revisão independente — run 2

Uma chamada com três perspectivas `review` examinou o delta instalado/documental até `7b9d2280737e127425e799c7c56ccff93b369241`; os três retornos foram `blocked`, sem GO.
O executor reconferiu a guarda antes/depois idêntica `90ed1d6158a4b1a786550dd45d6dae100334eb91663ca43697da8eb923b82c7b` e todos os 50 hashes de evidência.
Os seis bloqueantes anteriores permanecem pelo mesmo ID, agora parcialmente supridos pela instalação desabilitada; não se repete a alegação antiga de ausência de alvo/instalação.
Gestão instalada, controles negativos completos no novo container e lifecycle continuam abertos após a negativa nativa.
Os quatro opcionais históricos permanecem HQR-12..15; `TE-S1-007`, novo opcional válido de inventário, ficou em HQR-18 sem editar o teste protegido.
Os três revisores leram evidência; não executaram testes, Docker, scan, build ou instalação.
Reviewer/test-engineer recalcularam os hashes dos artefatos; security-reviewer conferiu o pin do manifesto e explicitou que não recalculou todos os membros.
O retorno nativo completo de `deleg_ef1155df` foi preservado da própria sessão, SHA-256 `8759490f9dc67c882282c8bb41173e5d228aa59b21d1e46b76c95f61e3bf344f`, com os três pareceres separados.
A alteração documental posterior registra reconciliação/backlog somente, não representa nova execução/revisão de código nem resolve a negativa.

## Histórico preservado — run 1

### Autoridade e estado

Contrato e base aprovados: `812d1fc9b4a4d0812295266e331e406b2f43bee4`, [spec](product-spec.md) e [plano](product-plan.md), preservados sem alterações.
O sistema nativo de tarefas conserva a autorização de BUILD; o texto histórico dos snapshots continua sendo o da definição.
A fonte S1 foi construída localmente na branch da fatia, sem merge, push, publicação, instalação ou inferência.
S1 NÃO está concluída: destino Hermes de teste/provisionamento não foi admitido e AC-01/10/12 continuam sem prova instalada.
O [bootstrap](bootstrap.md) permanece como registro histórico, não o estado atual de execução.

## Incremento implementado

- Entrada nativa e manifesto standalone sem dependência adicional.
- Gestão OFF/Observe com persistência delegada ao namespace nativo do próprio plugin e recusa explícita de AUTO.
- Modo salvo versus efetivo por instância, unload e divergência/restart visíveis; sem promessa global.
- Identidade declarada validada para candidato dev/teste, versão e diagnóstico de compatibilidade não qualificada.
- Inventário de bytes por allowlist explícita, SHA-256, rejeição de arquivos extras/faltantes/modificados, symlinks e paths inseguros.
- Gate executável de 2000 caracteres por linha com exceções exatas e controles negativos/operacionais.
- [Roteiro operacional](../docs/s1-operations.md), [testes](../docs/testing.md) e [matriz de compatibilidade](../docs/compatibility.md).

Não há fonte de quota, contabilidade de franquia, roteamento/admissão S2, inferência extra, daemon ou backend.
`installed_verified: false` e quota `unknown` são intencionais: dados declarados/testes sintéticos não viram prova real.
O produto não protege AUTO declarado em profiles sem plugin: esse enforcement continua dependente do host/S2 e é indisponível aqui.

## Evidência RED/GREEN

Cada RED foi observado antes da implementação correspondente e commitado apenas com testes novos.
Os comandos foram executados em ambiente limpo, com HOME/TMPDIR/pycache externos; os logs e códigos reais ficam no registro nativo da tarefa.

| RED | Runner | Falha observada |
|---|---|---|
| `5c6695dc3f97d642ec2946698f6cbd718a81f2ba` | unit | Entrada do plugin ausente. |
| `55b3502d99fe005da62e2fd5c92f2ecaef322028` | unit | Observe retornava OFF. |
| `b90ea396e8f5689b7ea792c7e632ba9ce96aa0c4` | unit | Identidade declarada ausente. |
| `640e3e97bee126e4f487cbb67b257feeb8e42552` | unit | AUTO salvo retornava sucesso e erro de leitura escapava. |
| `7718fd0081f82810150766378211b3d35da3b582` | unit | Verificador de payload ausente. |
| `24286e64da597045e1f25920092cb0bb95b92f7f` | unit | Gate de linhas ausente. |
| `0e6d9cef6e17800484a3b716c27911a6faf27012` | integration | Manifesto nativo ausente. |
| `46cc1bc5b64a08c8afc8c1662a9fbed0139b8613` | unit | Observe anterior sobrescrevia o OFF efetivo concorrente. |

O teste adicional de erro de gravação já passou na primeira observação; é cobertura de comportamento existente, não evidência de um novo ciclo RED.
Após o último incremento de código: 9 testes de unidade e 1 integração sintética, exits 0 em Python 3.13.16.
A regressão final, compilação, validação documental, scan de candidato e revisão independente são registrados por versão na tarefa nativa, não presumidos por essa contagem intermediária.
Testes e seus arquivos de suporte são protegidos a partir de cada RED; nenhum teste preexistia na base documental.
Nenhuma alteração de teste protegido foi autorizada ou feita; diffs MDR devem continuar vazios.

## Ferramentas e limites

OKF 0.3.0, contrato `okf-runtime-v1`, router SHA-256 `e1f5be06b7f8a69fe7407aff97bde1cfd4d6767a65b974ff3bc1e958cb054b42`, pacote físico da instalação 0.3.0.
CodeGraph 1.6.2 tem índice independente desta worktree; sync e rebuild após verificar ausência de daemons resultaram em 15 arquivos, 124 nós e 184 arestas, mismatch null, estado complete e reindexRecommended false.
A lista indexada foi comparada ao conjunto de 14 arquivos Python e ao manifesto YAML desta fatia; query `Management` encontrou o símbolo em `quota_router/lifecycle.py`.
Isso não configura watcher/MCP nem prova isolamento de Hermes.
Os pins de fonte host e limites do checkout consultado estão na [matriz](../docs/compatibility.md).
Os testes sintéticos não utilizam nem qualificam o PluginManager real.
Não há suíte instalada com execução admitida; não executar discovery vazio nem chamar cópia exportada de instalação.
Diagnósticos estáticos opcionais do editor sobre nullabilidade de `ModuleSpec` nos testes não são falhas observadas de execução; não foi alterado teste protegido para silenciá-los.

## Revisão independente e reconciliação

Uma única chamada crítica, com reviewer, security-reviewer e test-engineer na rota `review`, examinou base até `60c0ad23f0b329dd5334978d0c937911fd034bc4`.
Os três retornos nativos completos são `blocked`; nenhum é GO.
A guarda SHA-256 de status completo, HEAD e refs permaneceu idêntica antes/depois: `49cf89a00ea2ec54242c2208c2e2aedbceb90e6c789ced164954bd63ea301880`.
O executor reconferiu a guarda, não apenas adotou o relato dos revisores.
Os revisores leram os logs do autor; não executaram testes, build, scan, instalação ou operações reais.
Reviewer e test-engineer também conferiram por leitura/hashing os bytes do pacote e dos arquivos; security-reviewer não recalculou os hashes e explicitou esse limite.

- `S1-REV-001`, `SEC-S1-01/02` e `TE-S1-001/002/003`: bloqueantes válidos de prova instalada, isolamento e lifecycle ausentes, reunidos nos gates HQR-02/05/06/09/10.
- `S1-REV-002`: opcional válido de diagnóstico; o latch de leitura só recupera com nova instância e pode não sinalizar restart, sem permitir AUTO; acompanhamento HQR-12.
- `TE-S1-004`: opcional válido de evidência; contadores literais não substituem asserções independentes de ausência de efeitos em explain; HQR-13.
- `TE-S1-005`: opcional válido de determinismo; o RED observou uma corrida real, mas a espera de escalonamento não garante o mesmo interleaving sempre; HQR-14.
- `TE-S1-006`: opcional válido de harness; namespace unitário reutiliza submódulos e unload sintético de integração não está em finally; impacto presente limitado, HQR-15.

Nenhum revisor identificou defeito bloqueante adicional no código local; isso não aprova a fatia incompleta nem elimina as lacunas opcionais de regressão.
Não houve correção de código ou teste após a revisão, nem nova rodada: o bloqueio operacional não pode ser resolvido sem admissão humana.
A alteração posterior a esse commit registra somente esta reconciliação e o backlog; não é apresentada como nova revisão técnica ou aceite.
Os pareceres nativos completos foram preservados no registro gerado da tarefa; os live transcripts são abreviados e não são apresentados como parecer integral.

## Próximo gate

Default precisa obter um alvo e permissões concretos de provisionamento/instalação/restart/transporte, sem acesso a contas ou inferência por padrão.
O roteiro propõe instalar desabilitado, verificar origem/ref/hashes e isolamento completo, habilitar somente gestão OFF e exercitar ciclo/removal/reinstalação/rollback no alvo real.
Autorizar envio/publicação da revisão é decisão separada; o ramo local não está disponível no GitHub como candidato instalável.
Achados da revisão e gates não exercitados devem ser reconciliados no registro nativo antes de qualquer GO.
Pendências canônicas: HQR-02/05/06/09/10 no [backlog](../README.md#backlog).
