---
type: Delivery Record
title: S1 — gestão local e gate do destino instalado
description: Implementação parcial verificável de OFF/Observe, identidade declarada e validação de payload, com instalação real ainda não admitida.
status: draft
---

# S1 — execução parcial

## Autoridade e estado

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

## Próximo gate

Default precisa obter um alvo e permissões concretos de provisionamento/instalação/restart/transporte, sem acesso a contas ou inferência por padrão.
O roteiro propõe instalar desabilitado, verificar origem/ref/hashes e isolamento completo, habilitar somente gestão OFF e exercitar ciclo/removal/reinstalação/rollback no alvo real.
Autorizar envio/publicação da revisão é decisão separada; o ramo local não está disponível no GitHub como candidato instalável.
Achados da revisão e gates não exercitados devem ser reconciliados no registro nativo antes de qualquer GO.
Pendências canônicas: HQR-02/05/06/09/10 no [backlog](../README.md#backlog).
