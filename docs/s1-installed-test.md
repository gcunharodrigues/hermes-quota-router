# S1 — ensaio instalado de 2026-11-12

## Resultado e limite

A emenda da tarefa de teste admitiu provisionamento Docker, instalação GitHub do candidato e lifecycle somente no alvo de teste.
A instalação desabilitada e a comparação externa dos bytes passaram.
A habilitação nativa foi recusada pelo PM; não houve gestão OFF/Observe instalada, restart funcional, remoção, reinstalação ou rollback exercitados.
S1 continua bloqueada, sem GO, aceite de DEMO ou avanço de S2.
O [registro corrente](../decisions/s1-delivery.md) conserva os resultados históricos; o [backlog](../README.md#backlog) registra o dependente HQR-16.

## Identidades medidas

- Candidato instalado: `ad3e180f32adea3c25a2ef91280f1f6308729a47`, origem pública `gcunharodrigues/hermes-quota-router`, versão `0.1.0rc1`.
- Escolha declarada no namespace nativo: schema `1`, ambiente `test`, canal `candidate`, revisão e origem acima.
- Host público: `3b421578588243f920886e6fe79a6faa87ea026e`, obtido por codeload, não da instalação do operador.
- Archive público do host: SHA-256 `2525046f165880c22f177f2214c8da3e26c58cb0aeab5bd09aad940556538897`; 24798 membros únicos, sem links, examinados antes da extração.
- Base pública: `python@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b`.
- Imagem própria instalada: `sha256:885256829d31bea659e46fcde238b8960eaf78dd79e67b61276db3090c7b8a43`.
- Container instalado `hqr-s1-test`: ID registrado no recibo privado.
- Python executado: `3.14.10`, prefixo `/opt/hermes-venv`, fonte importada `/opt/hermes/hermes_cli/plugins.py`.
- `pyproject.toml`: SHA-256 `ee825ad304ad685625c8878cd34b7923ec64579cdc08e646b84b76ba3d4c1cfc`.
- `uv.lock`: SHA-256 `d0ae8bfd20db7a8ca0e75418df718315c58088b120366227cc62ee8fe25d4274`.
- `pm/lock.json`: SHA-256 `0097f663ec1846751347c7bd7fa3f7d6f06b20c3061f1fe0cc18e1cf18d6932e`.

O PM nativo construiu as dependências com `python3 -m pm.build_env --source /opt/hermes --out /opt/hermes-venv --python /usr/local/bin/python3 --cache /opt/hqr-build-cache`, sem resolver outro lock.
Inventários de distribuições Python e pacotes Debian foram preservados com os recibos.
Isso fixa os bytes/versões observados; não equivale a auditoria atual de vulnerabilidades nem a qualificação de todas as funcionalidades do Hermes.
A CLI emite aviso `install out of sync` para ffmpeg/node/npm/pnpm/ripgrep ausentes e classifica a instalação como `unknown-managed`.
Esse aviso não foi ocultado nem corrigido alterando o host; a readiness completa do mecanismo de dependências permanece aberta.

## Preparação e isolamento

O cliente Docker usou HOME e DOCKER_CONFIG novos em scratch externo, ambiente reduzido a PATH/HOME/DOCKER_CONFIG/DOCKER_HOST e engine `unix:///var/run/docker.sock`.
A versão própria observada foi Docker `26.1.5+dfsg1`; nomes hqr-s1-test estavam livres antes da criação.
O contexto de build continha somente Dockerfile e archive público do host, sem a worktree, HOME ou estado do operador.
A [recipe](../tests/installed/Dockerfile) instala código/dependências públicos durante preparação da imagem.
A primeira instalação nativa bem-sucedida foi `hermes plugins install gcunharodrigues/hermes-quota-router --ref ad3e180f32adea3c25a2ef91280f1f6308729a47 --no-enable`.
Nenhum `--force`, dispensa do scanner, conta, login ou inferência foi usado.
Um mirror Git público foi baixado para o alvo durante preparação, mas não foi usado para reinstalação ou para substituir a origem verificada.

O alvo instalado foi criado com `--network none --cap-drop ALL --security-opt no-new-privileges=true`, usuário `10001:10001`, sem mounts de usuário, portas publicadas, privileged, namespaces host ou teto artificial de CPU/RAM.
`docker inspect` confirmou esses campos; o processo confirmou UID, CapEff zero e NoNewPrivs `1`.
No runtime anterior à instalação, controles sintéticos confirmaram arquivo/configuração de scratch do host invisível, módulo sentinela do host ausente, socket abstrato do host inacessível e conexão a endereço de documentação sem rota.
O socket foi conectado com sucesso no lado do host como controle positivo, e o arquivo sentinela permaneceu idêntico após o ensaio.
O guest escreveu/leu/removeu seu próprio arquivo sintético como controle positivo.
Não foram lidos segredos, conteúdo de produção ou credenciais como canários.
As configurações de segurança foram reconferidas no novo container instalado, mas os controles negativos completos não foram repetidos nele antes do bloqueio.
Portanto há evidência parcial de contenção, não fechamento de AC-10 para o lifecycle ativo ou prova contra escape do kernel/daemon.

## Falhas preservadas

1. O primeiro build falhou por `useradd: not found`: a recipe tinha PATH sem `/usr/sbin`.
A correção de PATH na recipe produziu o segundo build, sem mudar testes ou o host.
2. O primeiro controle de socket filesystem excedeu o limite de pathname AF_UNIX do scratch.
O ensaio foi refeito com socket abstrato sintético, ainda na mesma fronteira de namespaces, sem usar sockets reais.
3. `docker network connect bridge hqr-s1-test` falhou porque Docker não admite múltiplas redes quando uma é `none`.
Não era uma negativa de política/acesso; a rede do alvo não foi relaxada nem a operação repetida.
Um disconnect subsequente também falhou porque bridge nunca esteve conectada.
A preparação admitida passou a instalar pelo GitHub durante o build; o container pré-instalação foi parado e preservado com nome `hqr-s1-test-preinstall`, e o alvo instalado nasceu offline da nova imagem.
4. A habilitação posterior encontrou uma negativa efetiva de admissão nativa, detalhada abaixo.
Nenhum comando equivalente de habilitação ou reparo foi executado depois dessa negativa.

## Instalação desabilitada comprovada

Os testes novos consultam o container real e comparam todos os arquivos com hashes derivados de `git show` do candidato público escolhido.
Os 34 caminhos e bytes coincidiram, sem extras/faltantes/modificados; `.git` é o único metadado excluído do payload.
O HEAD instalado e `.install-metadata.json` confirmaram SHA40, pin e origem HTTPS exatos.
`plugins show` informou `Status: not enabled`.
O consumidor nativo `get_plugin_command_handler('quota-router')` retornou `None`, sem substituir PluginManager/PluginContext por fixture.
A declaração deployment foi gravada pela CLI nativa no namespace do plugin; ela é declaração, não prova de execução ativa.
A verificação não apresenta `installed_verified` do plugin como verdadeiro nem inventa quota real.

## Negativa efetiva de habilitação

Comando exato no alvo offline: `/opt/hermes-venv/bin/hermes plugins enable hermes-quota-router`.
Exit observado: `1`; exceção final `hermes_cli.plugins_admission.AdmissionRefused`.
O PM tentou uma nova geração e buscou `certifi==2026.10.19` em `files.pythonhosted.org`, falhando por DNS sem rede.
A mensagem nativa informa que config.yaml e ambiente ativo ficaram inalterados.
Readback próprio confirmou seleção enabled/disabled ausente, deployment preservado e handler `None`.
Não houve OFF/Observe ativo, AUTO salvo/habilitado, inferência, reparo do PM, conexão de rede ou nova tentativa após a negativa.
O resultado público desta tentativa é a negativa nativa resumida acima, sem stack trace nem caminhos operacionais.

O fato de o venv explícito já importar o host não prova que o PM consiga admitir sua própria geração offline.
Não se conclui uma causa-raiz apenas desse erro; layout/cache/seleção do PM precisam de disposição do coordenador antes da retomada.
Recomendação ao default: reconciliar a preparação nativa de dependências/cache e obter autorização explícita para uma nova tentativa limitada, mantendo o host/candidato fixos e os testes offline.
Alternativa: manter o candidato instalado desabilitado e S1 bloqueada.
Não usar edição manual de enabled, monkey-patch, host/profiles diferentes ou relaxamento de testes para substituir a admissão recusada.

## Evidência de testes e continuação

RED `01abcad`: um teste falhou por alvo inexistente; após provisionamento, passou.
RED `ac28c6c`: dois testes, com uma falha por candidato não instalado; após instalação real, ambos passaram.
Esses REDs provam a preparação/instalação requerida pelos testes, não implementação nova de OFF/Observe ou qualificação de todo o lifecycle.
Os testes de unidade/integração anteriores permanecem protegidos e separados dessas observações.
O discovery instalado é `python3 -m unittest discover -s tests/installed -p 'test_*.py' -v`, com HQR_DOCKER_CLIENT explícito e HOME/TMPDIR/pycache externos.
A suíte exige o alvo real admitido; não retorna skip/PASS por ausência do container.
Este documento resume os resultados medidos; registros brutos e arquivos gerados não integram a distribuição.
Não remover os recursos novos antes de preservar e reconciliar as evidências do bloqueio.

## Run 3 — habilitação nativa offline (2026-11-15)

Diagnóstico: a recipe aquecia `/opt/hqr-build-cache`, mas o PM do alvo usa o cache gravável `$HERMES_HOME/cache/uv` (`pm/packages.py:407-478`; `pm/environment.py:261-283`).
Correção autorizada por Guilherme: somente o argumento `--cache` da recipe passou a `/home/hqr/state/cache/uv`; testes, host, candidato e PM não mudaram.
A imagem `sha256:8a20fd5269398d4d97b546f63c351152fd82924637bb1bd61e8e75c9ee12e244` foi construída com downloads públicos apenas na preparação.
O container do run 2 foi parado e preservado como `hqr-s1-test-run2`; o novo `hqr-s1-test` nasceu com `--network none --cap-drop ALL --security-opt no-new-privileges=true`, usuário `10001:10001` e sem mounts.
Antes da tentativa, uma sonda stdlib confirmou o cache gravável com o arquivo `certifi-2026.10.19`, e os dois testes instalados passaram com `Status: not enabled`.
A única tentativa autorizada de `hermes plugins enable hermes-quota-router` terminou com exit `0` e `Plugin hermes-quota-router enabled`.
Readback: `Status: enabled`, `plugins.enabled` contém o plugin, o consumidor nativo `get_plugin_command_handler('quota-router')` resolve para `hermes_plugins.hermes_quota_router.quota_router.lifecycle`, os 34 arquivos continuam idênticos ao candidato e a rede continua `none`.
Correção posterior: esse sucesso não prova admissão offline estável; ver a seção do run 3b.
Continuam sem prova: OFF/Observe ativos nos consumidores instalados, controles negativos completos neste container, restart, disable, remoção, reinstalação, rollback e HQR-17.
Os resultados do run 3 estão resumidos nesta seção.

## Run 3 — ciclo de vida instalado (parcial)

O harness versionado [`tests/installed/lifecycle.py`](../tests/installed/lifecycle.py) dirige o alvo, grava um recibo por passo e para na primeira falha.
Os comandos do plugin passam pelo mesmo despacho nativo da CLI (`get_plugin_command_handler` e `invoke_plugin_command`) em processos novos, com audit hook para conexões, DNS e subprocessos.
A primeira execução parou no passo 5 porque o leitor de configuração do harness importava `yaml`, ausente no venv; o harness passou a usar `hermes_cli.config.load_config_readonly`, e os recibos dessa tentativa ficaram preservados.
Na segunda execução passaram os passos 1–10:

1. Estado do Hermes de produção registrado antes do ensaio (HEAD, `uv.lock`, `plugins.enabled` e diretório de plugins), sem leitura de credenciais.
2. Alvo offline, sem mounts, usuário 10001 e CapDrop ALL; 34 arquivos idênticos ao candidato; consumidor nativo carregando os módulos instalados.
3. Declaração `deployment` visível como `declared_not_verified`; modo inicial OFF; quota `unknown`; AUTO indisponível.
4. Declarações com branch, SHA curto e `production/stable` resultam em `invalid`.
5. `mode auto` é recusado sem alterar a configuração.
6. Observe muda somente `settings.mode` do plugin; o resto da configuração mantém o mesmo hash; consumidores novos veem Observe com zero eventos de rede/subprocesso e contadores zero.
7. Uma instância carregada em Observe mostra `restart_required` depois que outro processo grava OFF.
8. `docker restart` preserva rede `none` e recarrega Observe salvo.
9. OFF efetivo em consumidor novo e nenhum processo Hermes de longa duração no alvo.
10. `hermes plugins disable` retorna ao caminho nativo: handler ausente, settings preservados e bytes inalterados.

O passo 11 falhou: `hermes plugins remove` terminou com `[Errno 18] Invalid cross-device link` ao renomear a árvore do plugin para a área de exclusão.
Sondas descartáveis offline da mesma imagem mostraram a causa: no overlayfs do Docker (`redirect_dir=nofollow`), um diretório vindo de camada da imagem não pode ser renomeado, enquanto um diretório criado em runtime ou um volume novo semeado da imagem aceita o rename.
A árvore, os metadados e a configuração ficaram intactos; restou só um diretório vazio `.hermes-quota-router.remove-*`, deixado pelo Hermes.
É um limite do alvo de teste, que instala o plugin durante o build da imagem, e um defeito de robustez do host registrado em HQR-19; não é defeito do plugin.
Remoção, reinstalação, rollback, controles negativos no novo container e o estado final continuam sem prova.

## Run 3b — alvo com volume de estado (2026-11-15)

Guilherme autorizou trocar a asserção protegida de zero mounts por um único volume Docker da tarefa e criar um novo alvo com esse volume.
O teste protegido `test_runtime.py` agora exige exatamente o volume `hqr-s1-state` (driver `local`, sem opções, label da tarefa) em `/home/hqr/state` e nenhum caminho do host; RED `b8c6c0b` falhou contra o container sem volume.
O alvo anterior foi parado e preservado como `hqr-s1-test-run3a`; o novo `hqr-s1-test` usa a mesma imagem, rede `none`, CapDrop ALL, no-new-privileges e usuário 10001.
Os dois testes instalados passaram com o plugin instalado e desabilitado.

A habilitação nativa neste alvo foi recusada com exit `1`: ao reconstruir `hermes-agent`, o PM precisou resolver `setuptools==84.1.0` e `wheel` do `build-system.requires` em `https://pypi.org/simple/setuptools/`, sem rede.
A configuração e o ambiente ativo ficaram inalterados segundo a mensagem nativa; nenhuma nova tentativa foi feita.
Hipótese não comprovada: o sucesso do run 3 ocorreu poucos minutos depois do build, enquanto a resposta do índice no cache do uv ainda era considerada fresca; horas depois o uv precisou revalidá-la pela rede.
O PM não executa essa sincronização com `--offline` e remove `UV_*` do ambiente, exceto configurações de índice e transporte como `UV_NO_INDEX` e `UV_FIND_LINKS` (`pm/index_config.py`), que são o mecanismo nativo para redes air-gapped.
Portanto a habilitação offline continua sem prova estável, e o ciclo de vida completo depende da preparação air-gapped nativa (HQR-16).

## Run 4 — ciclo de vida completo com rede (2026-11-15)

Guilherme decidiu que o alvo de teste pode ter saída para a internet, mantendo volume próprio, nenhum caminho do host e nenhuma credencial; a spec exige separação de dados, configuração, credenciais e sockets de produção, não um alvo sem rede.
O teste protegido `test_runtime.py` passou a exigir rede `bridge` única, nenhuma porta publicada e somente o volume da tarefa `hqr-s1-state-net`; RED `63bfbed` falhou contra o alvo anterior.
O alvo do run 3b foi parado e preservado como `hqr-s1-test-run3b`; o novo `hqr-s1-test` usa a mesma imagem `sha256:8a20fd5269398d4d97b546f63c351152fd82924637bb1bd61e8e75c9ee12e244`.
Os dois testes instalados passaram com o plugin desabilitado, e a habilitação nativa passou com exit `0`.

A primeira execução do harness parou no passo 11 por uma checagem estrita demais: a remoção nativa funcionou, mas o Hermes também retira o nome do plugin de `plugins.disabled` (`_forget_plugin_config`), o que o harness contava como alteração alheia.
A checagem passou a ignorar só esse nome nas listas `enabled`/`disabled`; os recibos dessa tentativa ficaram preservados.
O estado anterior foi recomposto pelos comandos nativos `plugins install --ref ad3e180… --no-enable` e `plugins enable`, ambos com exit `0`, e o harness rodou de novo desde o passo 1.

Os 17 passos passaram:

1. Estado do Hermes de produção registrado: HEAD `3b42157`, `uv.lock`, plugins habilitados e diretório de plugins.
2. Precondições: rede `bridge` sem portas, só o volume da tarefa, usuário 10001, CapDrop ALL, 34 arquivos idênticos a `ad3e180` e consumidor nativo carregando os módulos instalados.
3. Declaração `deployment` visível como `declared_not_verified`, modo OFF, quota `unknown` e AUTO indisponível.
4. Branch, SHA curto e `production/stable` resultam em `invalid`.
5. `mode auto` recusado sem alterar a configuração.
6. Observe altera só `settings.mode`; consumidores novos veem Observe com zero eventos de rede/subprocesso e contadores zero.
7. Instância carregada em Observe mostra `restart_required` depois que outro processo grava OFF.
8. `docker restart` recarrega o Observe salvo.
9. OFF efetivo em consumidor novo; nenhum processo Hermes de longa duração.
10. `plugins disable` retorna ao caminho nativo, preservando settings e bytes.
11. `plugins remove` apaga árvore, metadados e a entrada de configuração do plugin, sem handler ou módulo importável e sem mudar o restante da configuração.
12. `plugins install --ref main` é recusado: `ref must be a full 40-character commit SHA`.
13. Reinstalação pelo GitHub de `ad3e180` volta desabilitada, com 34 arquivos idênticos, origem GitHub e pin; após habilitar, status OFF com a revisão declarada.
14. Rollback com `--force --ref` para a revisão pública anterior `a8ee907efa27420fdefb35be5bcb95df6502ba8c` (29 arquivos idênticos), após OFF e disable; smoke OFF com essa revisão.
15. Retorno ao candidato `ad3e180` pelo mesmo procedimento, com smoke OFF.
16. Controles de isolamento: usuário 10001, CapEff zero, NoNewPrivs; caminhos e módulo sentinela do host ausentes; socket abstrato do host recusado; 22 conexões aos 11 listeners TCP do host pelos seus dois endereços IPv4 não-loopback recusadas; sem socket Docker nem arquivos com nome de credencial; internet acessível como controle positivo; namespaces distintos do host.
17. Estado final no candidato em OFF, e o Hermes de produção igual ao do passo 1.

`a8ee907` é usado só como revisão anterior pública para exercitar a troca de código; ele não tem a serialização de comandos de `d7409c8` e não é candidato de produção.
A rede do alvo alcança a internet e a rede local do host; os testes mostram que os serviços do host não respondem, mas não provam a ausência de outros serviços na rede local.
Os resultados do run 4 estão resumidos nesta seção.

## Revisão crítica e run 5b (2026-11-15)

A primeira rodada de revisão independente sobre `d1bd80a` teve um GO (revisor geral) e dois NO-GO (segurança e testes), com quatro achados bloqueantes:

- TE-S1-008: o harness chamava o launcher do Hermes de trabalho, proibido em `docs/testing.md`, e comparava só a última linha de `plugins.enabled`.
  Por isso, no run 4, "Hermes de produção inalterado" vale só para HEAD, `uv.lock`, a última linha de `plugins.enabled` e o diretório de plugins.
- SEC-S1-01: as recusas TCP não distinguiam uma fronteira de rede de endpoints que só não escutavam naqueles endereços.
- SEC-S1-03: a checagem de `caution` depois do `--force` não garantia o veredito do scanner antes da troca.
- SEC-S1-04: o documento público citava endereços internos do host.

Correções, com RED `974e98a` para os testes novos do harness:

- O Hermes de trabalho é observado só por leitura de arquivos, com falha fechada; o caminho vem de `HQR_PRODUCTION_HERMES_HOME`, não do código.
- Antes de cada instalação, os bytes exatos da revisão saem do mirror público do alvo, conferem com os hashes do Git e passam pelo scanner nativo (`tools.plugin_guard.scan_plugin`); só `safe` permite instalar, inclusive com `--force`.
- O passo de isolamento falha se algum listener do host sair do loopback, exceto o cliente DHCP (UDP 68), e usa um listener sintético no loopback do host com controle positivo do lado do host.
- O documento passou a descrever endereços por papel; os valores concretos ficam só nos recibos privados.
- Recibos exigem diretório novo e exceções operacionais gravam falha; a remoção agora afirma módulo não importável e entrada de configuração apagada.

O teste de exceção do DHCP foi escrito junto com a função, depois que o run 5 parou no passo 16 com esse listener; os recibos do run 5 ficaram preservados.
O run 5b passou nos 17 passos: o scanner deu `safe` (um achado informativo `python_subprocess`) para `ad3e180` e `a8ee907`; o loopback sintético do host foi alcançado pelo host e recusado pelo alvo.
Medido também: um listener sintético no IP do gateway Docker foi alcançado pelo alvo; serviços do host fora do loopback e a rede local são alcançáveis por esse alvo com internet (HQR-22).

## Segunda rodada e run 6 (2026-11-15)

A rechecagem de testes deu GO; a de segurança manteve SEC-S1-01 porque a checagem dos listeners do host rodava só no passo de isolamento, depois das mutações, e o `docker inspect` do recibo saía truncado.
O harness ganhou o passo 3, `network-admission-before-mutation`, que grava de forma estruturada rede, portas, capacidades, opções de segurança, namespaces, usuário e mounts do alvo, e falha se algum listener do host sair do loopback antes de qualquer mudança; o passo de isolamento repete a checagem no fim.
A exceção do DHCP passou a aceitar só um socket UDP 68 IPv4 preso a uma interface; curinga ou endereço sem interface na porta 68 é rejeitado (RED `68b8b47`).
O run 6 passou nos 18 passos; no passo 3 não havia listener exposto.
SEC-S1-04 continua como gate de publicação: o commit local `d1bd80a`, não publicado, ainda tem os endereços no histórico e precisa ficar fora de qualquer push.
