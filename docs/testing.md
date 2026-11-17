# Testes sintéticos e prova instalada

## Runner observado

Biblioteca padrão `unittest`, sem dependência de teste adicional.
Executar na raiz da worktree, com ambiente de processo limpo e `HOME`, `TMPDIR` e `PYTHONPYCACHEPREFIX` apontando a diretórios descartáveis fora de qualquer repositório.
O Python deve ser escolhido explicitamente; o executor observou 3.13.16 no terminal e 3.14.9 no interpretador nativo identificado.
Não invocar o launcher do Hermes de trabalho: ele pode executar autorreparo antes do comando.
Não copiar dados, configurações ou autenticação do host para o harness.

```sh
python3 -m unittest discover -s tests/unit -p 'test_*.py' -v
python3 -m unittest discover -s tests/integration -p 'test_*.py' -v
python3 -m compileall -q __init__.py quota_router
```

O ambiente limpo é parte obrigatória da invocação; os comandos acima mostram apenas os argumentos do runner.
Desde a S2 o plugin usa o leitor nativo de cotas quando ele é importável; por isso `tests/unit/test_0_hermetic_environment.py` roda primeiro e encerra a suíte com código 2 se `agent.account_usage` estiver no caminho, antes que um teste leia cotas reais.
A entrada suportada é `python3 scripts/run_tests.py [unit|integration|harness|<módulo de teste>]`: ela roda cada suíte ou teste escolhido em ambiente limpo e recusa rodar, com código 2, se o leitor nativo for importável nesse ambiente.
`tests/integration/` tem o mesmo guard da unidade; rodar `python3 -m unittest` direto, fora do script, não é suportado.
Os testes que precisam de arquivos usam `TemporaryDirectory` e limpeza no fim; o processo chamador limpa seu HOME/cache externos após preservar os logs necessários.
O teste de integração exporta somente os caminhos versionados mais o manifesto para uma árvore temporária, confere hashes e carrega a entrada dessa cópia.
Ele usa um contexto sintético com persistência JSON criada pelo próprio teste; não é o PluginContext real ou uma instalação Hermes.
A execução com `PYTHONPYCACHEPREFIX` externo mantém a cópia inalterada após imports.
Não há requisição de rede, inferência, autenticação, fixture de produção ou quota real nesses ensaios.
A leitura operacional de Git e arquivos do projeto não comprova isolamento completo do host.
Discovery com zero casos não é aprovação; conferir contagens e exits reais.

## Gate de linhas

`quota_router.line_gate.check_lines(root, paths)` valida todos os caminhos explícitos e retorna local/linha/tamanho das violações.
O teste de integração aplica esse gate ao candidato versionado.
Os controles de unidade aceitam 2000 caracteres, rejeitam 2001, distinguem exceção exata de arquivo novo e falham quando o arquivo não pode ser lido.
`EXEMPTIONS` enumera somente a licença MIT, os três relatórios públicos congelados e os dois ledgers de dados preexistentes.
Não há exceção por diretório, código ou arquivo futuro.
A regra de uma frase por linha é verificada na revisão de texto, não inferida desse contador.

## Prova instalada

No run 1, `tests/installed/` ainda não era uma suíte exercitada ou materializada.
O run 2 acrescentou dois testes reais de runtime offline e correspondência do candidato instalado, ambos observados RED e GREEN.
O [recibo instalado](s1-installed-test.md) fixa alvo, comando, evidência e negativa de habilitação; dois testes verdes não qualificam OFF/Observe ativo ou o lifecycle completo.
Sem alvo admitido, não criar teste vazio, `skip` verde ou fixture rebatizada de instalação.
Após autorização, fixar caminhos reais, identidade de host/Python, allowlist e revisão e preparar o harness antes de qualquer execução instalada.
A regressão contra cópia exportada continua sendo sintética mesmo quando os hashes coincidem.
Esse parágrafo descreve o run 2; o run 5b exercitou OFF/Observe, desabilitação, remoção, reinstalação, rollback e controles de isolamento no alvo.

## Harness do ciclo de vida

`tests/installed/lifecycle.py` dirige o alvo Docker admitido e grava um recibo JSON por passo em um diretório novo; um diretório já usado é recusado.
Falhas de asserção e exceções operacionais gravam recibo com `pass: false` antes de sair com código 1.
O Hermes de trabalho só é observado por leitura de arquivos (`HEAD`, `uv.lock`, `config.yaml`, plugins e gerações de dependências); o launcher dele nunca é iniciado.

```sh
HQR_DOCKER_CLIENT=<cliente docker em scratch> HQR_PRODUCTION_HERMES_HOME=<home do Hermes de trabalho> python3 -B tests/installed/lifecycle.py <diretório novo de recibos>
python3 -m unittest discover -s tests/harness -p 'test_*.py' -v
```

A admissão de rede do alvo e dos listeners do host roda antes da primeira mutação e é repetida no passo de isolamento.
Os testes de `tests/harness/` usam entradas sintéticas: observação sem processos, falha fechada, listeners fora do loopback, veredito do scanner e recibos de falha.
Consulte o [roteiro operacional](s1-operations.md) e o [registro S1](../decisions/s1-delivery.md).

## S3 — provas locais de Auto

O comando suportado permanece `python3 scripts/run_tests.py`, sem alteração do runner ou dos guards protegidos.
A regressão local da continuação executou `Ran 127 tests`, `Ran 9 tests` e `Ran 38 tests`, respectivamente para unidade, integração e harness, todas com `OK` e sem skips.
Os testes de harness imprimem diagnósticos de falha e argparse de propósito nos controles negativos; o resultado da suíte é o `OK` posterior.
Os números não incluem uma execução instalada.

| Contrato | Prova local |
|---|---|
| D2–D4, D6, D7; AC-18/19 | `test_s3_apply.py`, `test_s3_enrollment.py`, `test_s3_native_contracts.py`: projeção, inscrição, ausência, OFF, consumidor desligado, divergência e nova linha de base. |
| A1–A6, A9, A11, A13; B3/B4/B6 | Política S2 preservada e `test_s3_scenarios.py`: escrita ou nenhuma escrita pela camada de configuração. |
| D9 | `test_s3_processes.py`: dois processos reais, primeiro parado com lock adquirido e segundo aguardando; resultado final coerente. |
| D10 | Mesmo arquivo: morte abrupta com `os._exit(73)` depois do diário, de cada uma das cinco escritas de chave, da escrita completa, da releitura, da confirmação e da exclusão do diário. |
| Quatro recuperações | `test_s3_apply.py`: anterior, alvo, mistura e terceiro valor; inclui edição que volta ao anterior. |
| Credenciais R2/N2 | Unidade e integração: os quatro aliases presentes na inscrição e acrescentados depois, nenhuma alteração nativa e nenhum segredo sintético em estado, diário ou saída. |
| Rotas N3/O3 | Projeção fechada preserva outras opções e fallbacks; edição de fallback não é divergência. |
| E3 | `test_s3_compat.py`: alteração de corpo sem alteração de assinatura, constante alterada e fonte indisponível. |
| AC-22 | `test_s3_lifecycle.py`: A₁ → B → A₂, callback atrasado, janela inclusiva de 60 s, controle positivo, mutação, mãe desconhecida e fonte não qualificada. |
| E1 | `test_s3_native_contracts.py`: marca retida após unload e subtree ausente, com diagnóstico também em OFF. |
| Runner instalado | `test_s3_auto_harness.py` preservado e `test_s3_native_*.py`: argumentos, ordem, completude, parsing, fronteira sem retorno falso, guard de I/O, URI SQLite e fonte decorada. |

A integração carrega `hermes_cli/config_backend.py` somente quando `HQR_NATIVE_SOURCE` aponta explicitamente à fonte autorizada, sob um pacote inerte e sem importar o leitor de cotas.
O runner canônico não herda essa variável: sua integração usa o armazenamento sintético fechado e a prova nativa separada fica registrada com essa distinção.
A configuração usa um `HERMES_HOME` temporário e um arquivo explícito `synthetic.json`, para não inicializar o bootstrap de configuração do host.
A primitiva de persistência inferior é JSON sintético, pois o Python limpo não oferece `ruamel`; a prova cobre `Changes`, `write_changes`, `_ExplicitFile` e `FileBackend.write_path`, não o preservador YAML de comentários.
Na ausência da fonte, a mesma costura usa o fake fechado, seguindo o padrão da S2.
Isso mantém a garantia do runner limpo e não é uma instalação, um ensaio nativo integral ou prova de resolução de consumidores.

As fontes nativas de sessão não foram qualificadas e o produto conserva `geração indeterminada` sem idade por tarefa.
O runner instalado S3 foi escrito, mas não executado; ele embarca `s3_native_consumers.py` no processo Python do alvo e o gate final verifica cada cenário, não apenas uma lista declarada de pendências.
O único teste preexistente alterado é `tests/integration/test_export.py:23`, com a lista exata de hooks aprovada em D14.
Nenhum outro teste protegido, helper S2, runner anterior ou mecanismo de discovery foi modificado.

### Probes nativos de consumidores, sem inferência

O runner prepara políticas antigas antes do Auto e chama `ConsumerProbe.after` depois da primeira decisão aplicada que muda a rota.
C1/C2/C3 usam a criação nativa até a captura da política e a resolução do próximo turno; isso não publica uma sessão completa nem constrói um agente.
C5/C6 usam `_worker_config` e processos novos do mesmo Python do host, com `_bind_worker_config` antes de importar os leitores de configuração e delegação.
O worker antigo é lido antes e depois da decisão; outro worker iniciado depois recebe a política antiga; o controle posterior usa política nova.
C7 executa a resolução nativa do tick até a chamada de runtime, interrompida antes de autenticação sem resposta falsa; provider e esforço também passam pelos resolvers nativos.
A matriz inclui cron vazio, padrão completo, override de esforço para o modelo do cron e padrões parciais nos dois sentidos, com comparação dos valores, origens e marca parcial do status.
C4 usa o backend nativo `model_map`; ausência ou schema incompatível mantém falha explícita, sem reimplementar a escolha a partir da lista de opções.
C10 confere parsing/fronteira de `/model` e precedência na construção nativa do filho, mas mantém gate para o commit na sessão e a chamada explícita no backend que não foram provados sem credenciais.
As fontes carregadas são identificadas por caminho relativo, linha e digest; funções ausentes, fonte indisponível, erro nativo e tentativa proibida não viram skip ou sucesso.

A qualificação AC-22 cria seu próprio `SessionDB` descartável dentro do home de prova e lê a sessão por função nativa antes/depois de uma troca de modelo.
No host local, o modelo gravado é mutável e o commit local observado não insere `model_config`; o resultado é fonte não qualificada.
O fallback do produto é então exercitado e deve retornar exatamente `geração indeterminada`, sem geração nem idade.
Uma fonte desconhecida ou uma prova nativa que não conseguiu executar continua sendo falha de cenário, não qualificação negativa automática.

A execução local do código embarcado retornou C1/C2/C3/C5/C6/C7 e fallback AC-22 aprovados, C4/C10 falhando e nenhuma tentativa proibida no recibo final.
Ela usou escrita nativa de configuração sintética em home descartável, não Auto instalado; o gate de aceite retornou exit 1.
O [registro da continuação](../decisions/s3-delivery.md#continuação--probes-nativos-locais-2026-11-16) contém comando, digests, saída e limites.
O alvo Docker e sua qualificação separada não foram executados ou alterados nesta continuação.


### Segunda continuação: C4/C10 fechados localmente

O ensaio local resumido no registro S3 retornou todos os nove cenários verdes, `audit_denied=[]` e exit 0, com 42 fontes nativas identificadas.
A regressão posterior executou 134 testes de unidade, nove de integração e 44 de harness, todos `OK`, sem skips: 187 no total.
As novas unidades cobrem dependência ausente/desabilitada/não carregada/indisponível, ausência de escrita na aplicação e OFF, namespace ativo, status legível e igualdade dos fingerprints de métodos estáticos carregados/inertes.
O novo harness cobre pin/enable/readback, confinamento de fonte externa e rede estrita: somente o socket exato em `127.0.0.1`, GET de metadados e nenhuma rota de inferência.
Um teste de capacidade IPv6 de urllib3 é recusado com `OSError` antes do bind; não há conexão IPv6.
O único subprocesso adicional admitido é `git rev-parse HEAD` na raiz exata da fonte, para a checagem nativa de versão; downloads Git e prompts ficam desligados.

C4 resolve `option=general` por `_load_config`, `_active_provider`, `_declared_parameters`, `_route_one`, `ModelMapDelegationProvider.route_task` e `_child_reasoning`, para políticas comuns anteriores e posteriores ao Auto.
As duas resolvem Anthropic/Opus/medium, mesmo quando a mãe anterior conserva Codex/Sol/low.
C5/C6 continuam verdes com a cópia congelada dos workers gerenciados.
C10 completa `switch_model` com um provider custom local sem credencial e usa `_persist_model_switch_to_session` sobre um `SessionDB` descartável, seguido de `stored_session_route` com padrão do profile diferente.
O backend nativo recebe `option=explicit` e resolve custom/hqr-explicit/low; uma chamada real a `delegate_task(credentials_cfg=...)` chega com o pin explícito até `_build_children`, cuja execução é interrompida antes de criar filhos.
Essa última forma é de chamadores nativos confiáveis: o tool model-facing oferece a seleção nomeada `option`, não um argumento bruto `model`.
O stub registrou somente GET de `/models-dev.json` e `/v1/models`; não implementa chat, completions, responses ou messages.
A prova alcança resolução, persistência/retomada da seleção e despacho pré-construção, não uma interação completa com a interface, agente ou inferência.

O controle posterior desabilitou a dependência apenas no home descartável: status ficou indisponível e a delegação permaneceu idêntica em valores e presença tanto no apply quanto no OFF.
O motor Auto e o escritor/leitor YAML eram reais; o contexto de gestão, as cotas e a disponibilidade desconhecida de catálogo foram injetados e estão declarados no recibo.
Isso fecha os gates locais de resolução, não a elegibilidade real dos modelos ou a qualificação instalada.

Antes de qualificar um alvo Docker autorizado, `s3_auto.py` exige OFF efetivo, um manifesto de bytes revisado da dependência e a admissão completa do container/volume.
Depois de instalar com `--no-enable`, compara a árvore inteira, recusa symlinks/especiais e exige scanner `safe` antes de habilitar e reler versão, registro e pin.
O comando que o runner acrescenta é `hermes plugins install https://github.com/NousResearch/hermes-official-plugins#advanced-delegation --ref 13b2c1c9c8204bf333df240b2aacf98c3e6250b7 --no-enable`, seguido de `hermes plugins enable advanced-delegation`.
Depois disso vêm o swap protegido do candidato e a qualificação própria do host, antes de Auto.
Essas etapas Docker foram escritas e testadas hermeticamente, não executadas.
Os resultados, comandos reproduzíveis e limites estão no [registro atualizado](../decisions/s3-delivery.md#continuação--c4c10-fechados-localmente-2026-11-16).

### HQR-35 — backoff de leituras indisponíveis

`python3 scripts/run_tests.py tests.unit.test_s3_reading_backoff` exercita falhas sintéticas com relógio fixo e módulos nativos inertes.
O teste cobre backoff por provedor, expiração exata, início depois da consulta, limites de 30–3600 s, recuperação, limpeza na mudança de modo e ausência de nova consulta durante a espera.
O importador só inspeciona a assinatura para detectar o argumento explícito `on_error`; não faz consulta de capacidade, não usa `**kwargs` como prova de suporte e mantém `read_only=True` em ambos os contratos.
Os diagnósticos retêm apenas `kind`, `status` inteiro HTTP válido e `retry_after_s` numérico finito; campos privados, tipos inválidos e valores não finitos são descartados antes da normalização.
A prova percorre normalização, cache, status/explain JSON e texto em português, sem transformar desconhecido em franquia ou crédito disponível.
A regressão completa usa o mesmo runner canônico; nenhuma consulta real, instalação ou mudança nos guards e testes protegidos faz parte desta prova.

## Rodada 1 da revisão S3

`test_s3_storage_review.py` prova diretório/lock com symlink, arquivo especial, permissões inseguras e criação privada do caminho padrão.
`test_s3_review.py` cobre recarga suspensa/OFF, histerese entre escritas próprias, remoção de preferências obsoletas, contexto do worker e latch até reload.
`test_s3_fingerprint_review.py` cobre constantes do namespace ativo, corpo com mesmo nome/assinatura, inspeção sem executar defaults e identidade Git sem subprocesso.
A matriz de processos compara todos os cinco campos, presença, baseline, último aplicado e geração em quedas de apply e restore, inclusive edições pós-queda para anterior e terceiro valor.
A matriz de cenários relê a opção persistida, exercita toggles por `Management` e confere A13 abaixo, exatamente no limite e acima da histerese.
Os testes de cobertura que ficaram RED por métodos ausentes são controles da existência da prova; não são apresentados como falhas antigas do motor.

### Integração nativa separada

O Python limpo continua sem `ruamel`; não se instalou dependência nem se mudou o guard.
Os módulos `tests/native_yaml/test_s3_aliases.py` e `test_s3_review_native.py` rodam separadamente com o Python/dependências já disponíveis do host, `HOME/HERMES_HOME/TMPDIR` descartáveis e `ProbeGuard` antes de importar os consumidores nativos.
Eles provam aliases YAML com controle válido de restauração, pins completos/parciais por resolução nativa, precedência real de aliases e `ContextVar` real do home no worker.
O script de teste não invoca o launcher, não instala o plugin e não abre configuração, credenciais ou banco de sessões reais.

```sh
# PY, DEPS e SRC identificam somente o interpretador, dependências e fontes autorizadas.
# PROBE_HOME é um diretório novo em scratch, fora dos repositórios.
env -i PATH=/usr/bin:/bin HOME="$PROBE_HOME" HERMES_HOME="$PROBE_HOME" TMPDIR="$PROBE_HOME" PYTHONDONTWRITEBYTECODE=1 HERMES_DISABLE_LAZY_INSTALLS=1 HERMES_CONFIG_BACKEND=file PYTHONPATH="$DEPS:$SRC:$PWD" "$PY" -B tests/native_yaml/test_s3_aliases.py -v
env -i PATH=/usr/bin:/bin HOME="$PROBE_HOME" HERMES_HOME="$PROBE_HOME" TMPDIR="$PROBE_HOME" PYTHONDONTWRITEBYTECODE=1 HERMES_DISABLE_LAZY_INSTALLS=1 HERMES_CONFIG_BACKEND=file PYTHONPATH="$DEPS:$SRC:$PWD" "$PY" -B tests/native_yaml/test_s3_review_native.py -v
```

Na execução desta rodada cada módulo recebeu seu próprio home descartável e o preparador o removeu ao fim.
A prova adicional de `config_backend.py` usou `HQR_NATIVE_SOURCE`, pacote inerte e primitiva JSON, mantendo o leitor de contas não importável.
Essas provas não substituem o runner instalado nem o aceite no alvo Docker.

## Rodada 2 da revisão S3

`tests/unit/test_s3_mode_continuity.py` compara Observe → Auto com a projeção realmente aplicada abaixo da histerese, nas políticas de conversa principal e por ritmo.
Os controles verificam mudanças de settings e rota externa, preservação após escrita própria, grupo divergente sem sobrescrita e OFF exato.
`tests/harness/test_s3_c12_correlation.py` executa somente a função C12 embarcada, por AST, com armazenamento e worker reais em scratch e entrega sintética.
Histórico antigo com entrega atual inerte, correlação alheia ou timestamp anterior à emissão deve falhar; registro novo passa com histórico vazio, parcial ou cheio, sem reter ID bruto ou mensagem privada.
Os comandos focados são `python3 scripts/run_tests.py tests.unit.test_s3_mode_continuity` e `python3 scripts/run_tests.py tests.harness.test_s3_c12_correlation`.
A regressão completa desta rodada retornou 166/13/58 testes, todos `OK`, sem skips, conciliados com 237 IDs únicos por suíte.
Essa execução não prova entrega instalada do hook nem substitui a rechecagem independente do candidato.

## Preparação Docker e admissão somente de leitura

`tests/installed/advanced-delegation-13b2c1c.json` fixa os 23 arquivos de advanced-delegation 1.1.0 no ref `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`.
O harness aceita esse manifesto com atestação sintética válida e recusa uma cópia com o hash de `model_map.py` alterado antes de enable.
A comparação real com os blobs públicos é uma inspeção separada, não uma instalação simulada pelo harness.

`--admission-only` executa apenas `docker inspect`, `docker volume inspect` e a admissão dos listeners do host, grava o recibo local e retorna antes de qualquer `exec`, probe ou comando Hermes no alvo.
Os argumentos de revisão continuam exigindo SHAs completos e distintos, mas esse modo não verifica publicação, manifesto, fingerprint em runtime ou disponibilidade do backend.
Não definir `HQR_PRODUCTION_HERMES_HOME`: o runner S3 não precisa ler o Hermes de trabalho.
Escolher diretórios novos em scratch para o cliente Docker e os recibos.

```sh
CANDIDATE=$(git rev-parse HEAD)
ROLLBACK=ad113d95604128fcdf9c446e2c5bd9c75bff0860
HQR_DOCKER_CLIENT="$DOCKER_CLIENT" PYTHONDONTWRITEBYTECODE=1 python3 -B tests/installed/s3_auto.py "$ADMISSION_RECEIPTS" --candidate "$CANDIDATE" --rollback "$ROLLBACK" --advanced-manifest tests/installed/advanced-delegation-13b2c1c.json --admission-only
```

A execução de preparação retornou `PASS 01 admission-before-any-mutation`, exit 0, com `listeners.exposed=[]` e somente os dois comandos Docker de inspeção no recibo.
A preparação anterior não liberava o ensaio completo porque o core do alvo não contém `.git/HEAD`.
A continuação HQR-26 permite uma entrada explicitamente marcada para tarball somente pelo conjunto completo de funções e constantes, sem fabricar uma revisão de runtime.
A entrada Docker guarda a proveniência pública e a comparação de fontes somente de leitura qualificou o conjunto completo com a dependência pública conferida separadamente; isso não instala a dependência nem prova Auto instalado.
Antes do ensaio completo, publicar o candidato exato, garantir que o mirror público do alvo contém candidato e rollback e instalar a dependência pelo fluxo nativo autorizado.
Nenhuma dessas mutações foi executada nesta tarefa.

Após essas condições, o comando do ensaio instalado completo é:

```sh
HQR_DOCKER_CLIENT="$DOCKER_CLIENT" PYTHONDONTWRITEBYTECODE=1 python3 -B tests/installed/s3_auto.py "$INSTALLED_RECEIPTS" --candidate "$CANDIDATE" --rollback ad113d95604128fcdf9c446e2c5bd9c75bff0860 --advanced-manifest tests/installed/advanced-delegation-13b2c1c.json
```

Não reutilizar o diretório de recibos da admissão nem acrescentar `--admission-only` ao ensaio completo.
A preparação acrescenta dois testes unitários e cinco de harness: a regressão completa retornou 168/13/63 testes verdes, sem skips.

## Primeiro ensaio S3 publicado e scanner

`HQR_DOCKER_CLIENT` é um diretório privado novo, não o caminho do binário Docker: o helper usa seus subdiretórios `home/` e `docker/` como `HOME` e `DOCKER_CONFIG` do cliente, com socket local explícito.
O executável `docker` é resolvido em `/usr/bin:/bin`; criar os dois subdiretórios em scratch com `umask 077`, sem copiar configuração ou credenciais do operador.
Usar o SHA40 publicado explicitamente, não o HEAD local depois de correções: o primeiro ensaio fixou `db77b6e55caa7d8bc123be9499a9187d33aef078` e rollback `ad113d95604128fcdf9c446e2c5bd9c75bff0860`.
Após a admissão, o mirror público do alvo recebeu `git -C /home/hqr/public-mirror.git fetch --prune origin`, conforme a receita S2; ambos os commits foram relidos como objetos `commit` antes do runner completo.

O primeiro ensaio retornou dois passos PASS e FAIL em `pinned-advanced-delegation`; os 13 passos restantes e todos os cenários de Auto ficaram não executados.
A instalação da dependência com `--no-enable` terminou, mas o guard de `ADVANCED_CHECK` bloqueou o `os.open('/dev/null', O_RDWR)` usado pelo scanner em `subprocess.DEVNULL`.
A costura inspecionada do scanner é somente `git -c core.fsmonitor=false -C <dependência> ls-files -z -- '*.pyc' '*.pyo'`.
A correção local admite esse argv com cwd ausente e o dispositivo `/dev/null` verificado apenas durante `scan_plugin`, revogando as permissões inclusive em erro; os probes de consumidores continuam sem essa permissão.

`python3 scripts/run_tests.py tests.harness.test_s3_scanner_guard` observou três falhas RED e três testes GREEN.
O novo teste executa o `ADVANCED_CHECK` real com módulos nativos inertes e a consulta Git real, cobrindo resultado seguro, bytecode rastreado e revogação/controles negativos; não é uma repetição do scanner instalado.
A regressão completa retornou 177 unitários, 13 de integração e 67 de harness, todos `OK`, sem skips.
O alvo foi relido em S2 `0.2.0rc1`, no rollback e com OFF salvo/efetivo; advanced-delegation permaneceu não habilitado, com pin e os 23 arquivos exatos.
A correção exige revisão e nova publicação antes de outro ensaio Docker completo; esse resultado não prova Auto instalado nem exercício de rollback.

## Segundo ensaio S3 publicado

A execução de `161392adcad5fc931d71f1f88564760c9e7e5203`, com runner inicial `0697c3e678291b0453f779d93deca9c60ceca948` e árvores iguais, instalou o candidato e qualificou os fingerprints do alvo.
A admissão somente de leitura passou; o ensaio completo retornou exit 1, com oito passos PASS, um FAIL e sete não executados.
`native-auto-scenarios` terminou como passo PASS porque o script devolveu JSON, mas C5/C6 falharam individualmente e o gate final de consumidores não executou.
Os demais onze cenários exigidos, incluindo E2 pelo passo de recusa de remoção, passaram; AC-22 prova somente o fallback `geração indeterminada`.
O passo de diagnóstico durante disable falhou porque a tabela Rich encurta o identificador; `--plain --no-bundled` preserva a chave inteira.
C5/C6 foram recusados pelo audit hook quando o Python 3.14.10 selecionou `os.posix_spawn` com suporte a CLOSEFROM; a correção local usa `start_new_session=True`, sem liberar spawn no guard.
Os comandos focados são `python3 scripts/run_tests.py tests.harness.test_s3_disabled_listing` e `python3 scripts/run_tests.py tests.harness.test_s3_guarded_worker_launch`.
Eles observaram dois e um FAIL no RED, respectivamente, e cinco e um testes GREEN; a regressão canônica retornou 177/13/90 testes, todos `OK`, exit 0 e sem skips.
O primeiro módulo executa a função instalada de diagnóstico por AST com saídas nativas modeladas; o segundo executa Worker e payload reais com fontes inertes e seleção de spawn reproduzida localmente.
Nenhuma dessas provas instala a correção ou repete o ensaio Docker.
A releitura deixou a candidata `0.3.0rc1` desabilitada, sem handler nativo e com Auto salvo; advanced-delegation `1.1.0` permaneceu habilitado no pin e nos 23 arquivos aprovados.
Rollback, retorno ao candidato, Observe final e aceite integral não executaram.
A retomada exige revisão independente, nova candidata publicada e preparação aprovada do estado inicial OFF; não tratar a candidata desabilitada como um alvo já pronto para o runner.
O [registro do ensaio](../decisions/s3-delivery.md#segundo-ensaio-da-candidata-publicada-2026-11-16) conserva resultados por passo, cenários e commits locais.

## HQR-38 — estados e rede de segurança

A regressão local de HQR-38 executou `Ran 295 tests`, `Ran 19 tests` e `Ran 93 tests` pelo mesmo runner, todas com `OK` e sem skips.
Os arquivos `tests/unit/test_hqr38_*.py` cobrem a matriz de pares, A16–A39 e os grupos `fallback_providers` com backend sintético.
`tests/integration/test_hqr38_fallback.py` cobre aplicação, releitura, OFF exato com chave ausente, edição externa e credencial pela camada de configuração sintética.
Os números não incluem execução instalada; veja a [entrega](../decisions/hqr-38-delivery.md).

## Regressão canônica HQR-38 após SOL-04

O commit `338bbfa2349cbd7464add2c24a53fa1a73928385` passou no runner canônico completo em Docker sintético: 353 testes de unidade, 19 de integração e 98 de harness, com exit 0, sem falhas, erros, skips ou avisos.
São 470 execuções com IDs únicos por suíte; o guard hermético repete o mesmo nome entre unidade e integração, resultando em 469 strings de ID globais.
Os ensaios focados e a prova entre Engines não foram somados novamente a esse total.
O [registro da execução](../decisions/hqr-38-delivery.md#suíte-canônica-completa-em-docker-sintético) preserva a preparação que falhou e a correção da dependência histórica FS-GIT-01.

Os testes de downgrade puro consultam `quota_router/groups.py` e `quota_router/apply.py` na revisão `233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a` por `git show`.
Um índice Git novo satisfaz `git ls-files`, mas não fornece essa revisão histórica.
Uma exportação de teste precisa dos objetos originais necessários, com identidade verificada; não deve fabricar uma ref com o nome do commit nem substituir o validador antigo.
Na cópia descartável, foram admitidos apenas o commit, as duas árvores do caminho e os dois blobs exigidos, sem configurações de usuário, remotos ou estado do Hermes de trabalho.
Dentro do ambiente já isolado e admitido, as conferências de dependência são:

```sh
git cat-file -e 233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a:quota_router/groups.py
git cat-file -e 233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a:quota_router/apply.py
python3 -B scripts/run_tests.py
```

Esses comandos não admitem o ambiente por si só; continuam obrigatórios o isolamento, dados sintéticos e os guards descritos acima.
O runner, seus argumentos de seleção e todos os testes protegidos permaneceram inalterados.
A regressão não executou `tests/native_yaml/`, o lifecycle instalado, provedores reais ou o Hermes de trabalho; esses são gates separados.
