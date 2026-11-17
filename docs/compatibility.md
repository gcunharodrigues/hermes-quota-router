# Compatibilidade observada, não qualificada

A matriz separa leitura de fonte, teste sintético e ensaio instalado.
Não representa autorização de instalação nem certificação de todas as revisões Hermes.

| Dimensão | Observação | Limite |
|---|---|---|
| Fonte nativa lida | Hermes HEAD `3b421578588243f920886e6fe79a6faa87ea026e`, descrição `v0.23.1-dirty` | Não é um host de teste provisionado; o checkout completo tem alterações locais não inspecionadas. |
| Entrada | Loader lê `__init__.py` como pacote com submodule search locations | Apenas leitura de fonte e reprodução sintética da forma do import. |
| Configuração | `PluginContext.get_config`/`set_config` têm namespace relativo do próprio plugin | Persistência nativa não foi exercitada; teste usa JSON sintético. |
| Comando | `register_command(name, handler, description, args_hint)` recebe handler de argumentos textuais | CLI/gateway reais não foram abertos no alvo. |
| Unload | `on_unload(callback)` registra callback de gestão | Remoção/disable/restart reais não foram exercitados. |
| Python | 3.13.16 e 3.14.9 identificados operacionalmente | Execuções e contagens estão no registro da tarefa; não inferir outras versões/plataformas. |
| OFF/Observe | Sem hooks de inferência, provider ou fonte de quota na biblioteca S1 | Não certifica tráfego total, neutralização de outras instâncias ou isolamento de runtime. |
| AUTO | Indisponível em S1 | Sem política, admissão por tentativa, enforcement por profile/superfície ou billing qualificado. |
| SO | Ensaios locais sintéticos em Linux | Outros sistemas e destinos instalados não foram qualificados. |

## Ensaio instalado posterior — run 2

O [recibo instalado](s1-installed-test.md) fixa o host público admitido, Python 3.14.10, base por digest, imagem própria, locks e pacote GitHub instalado desabilitado.
O consumidor nativo retornou handler ausente; a habilitação recebeu `AdmissionRefused` por download do PM em alvo offline e não foi repetida.
Portanto a tabela acima é evidência histórica do run 1, não conclusão de ausência atual de um alvo admitido ou qualificação do ciclo ativo.
O aviso `unknown-managed`/ferramentas ausentes e os controles negativos apenas parciais permanecem explícitos em HQR-16/17.

## Ensaio instalado — run 4

O [run 4](s1-installed-test.md#run-4--ciclo-de-vida-completo-com-rede-2026-11-15) exercitou o candidato no host `3b42157`, Python 3.14.10, em Linux/Docker com rede `bridge` e volume próprio.
Isso qualifica o ciclo de vida da gestão S1 nesse alvo, não outros sistemas, outros hosts ou as superfícies de roteamento da S2.
O aviso `unknown-managed`/ferramentas ausentes continua registrado em HQR-17; o plugin não depende dessas ferramentas.

## Pins das fontes operacionais

Os hashes fixam os arquivos efetivamente consultados, não a instalação integral ou o conteúdo de dependências.
Não foram lidas configurações, dados ou credenciais de profiles.

- `hermes_cli/plugins_context.py`: SHA-256 `d75a6fef102140431f68bc1a402d58977b5024ad21d5b1df284a9dad41250df4`.
- `hermes_cli/plugins_loader.py`: SHA-256 `3400cc514c8a0f0749e02b309020cc48794eae530adc26c0ad3f2381ba6935fc`.
- `hermes_cli/plugins_manifest.py`: SHA-256 `89b30e679247a628c7dad93c573afa9f3f22529015b26397de24f5067ff7fc06`.
- `hermes_cli/plugins_dispatch.py`: SHA-256 `33d01cbb167c1a08fcca9dba0d867f92062bc790b7a0b7957fa9f03dafcd091e`.

No alvo futuro, repetir a qualificação no host/Python realmente escolhidos e vincular os novos hashes ao recibo daquela execução.
O status mantém `host: not_verified_in_this_runtime`, `lifecycle: requires_installed_smoke` e `installed_verified: false`.
O [roteiro](s1-operations.md) não substitui essa prova.
Essa descrição é histórica da S1; na S3/D18 o campo `source_qualified` e o label do host refletem a comparação efetiva, sem promover `installed_verified` ou a prova de lifecycle.

## S2 — leituras nativas

Conferido no Hermes local (com patches locais), sem prova instalada ainda:

| Dimensão | Observação | Limite |
|---|---|---|
| Leitor de cotas | `agent.account_usage.fetch_account_usage(provider, read_only=True)` devolve janelas com rótulo, uso, reset e escopo; o Codex traz `raw` | A Anthropic não traz `raw`; créditos e janela do Fable não chegam ao plugin. |
| Duração das janelas Codex | `_codex_window_labels` rotula pela posição quando `limit_window_seconds` falta ou é desconhecido | O plugin confere `limit_window_seconds` no `raw` e trata janela sem duração publicada como desconhecida. |
| Rótulos e escopos de janela | `Session`, `Weekly`, `Current session`, `Current week` com escopo `account`; `Opus week`, `Sonnet week` com escopo `model` | Rótulo novo, escopo divergente ou janela repetida deixam a leitura desconhecida; sem janela semanal também. |
| Configuração do profile | `hermes_cli.config_backend.read_config_doc` sobre `get_config_path()`, sem expansão de variáveis | `read_raw_config` não é usado porque grava backup quando o YAML está malformado; `load_config_readonly` também não, porque cria pastas e grava backup. |
| Configurações do plugin | `ctx.get_config`, exigido pela seção 13 da emenda | No host conferido passa por `load_config_readonly`; o efeito de backup é do host e será medido no ensaio instalado. |
| Catálogo de modelos Codex | `hermes_cli.codex_models.get_codex_model_ids` só oferece Astra com o token da conta | O plugin não manipula tokens; Astra fica inelegível na S2. |
| Jobs de cron | Leitura direta de `cron/jobs.json` ao lado do `config.yaml` | `cron.jobs.load_jobs` não é usado porque cria pastas e repara o arquivo; pin parcial bloqueia a decisão do cron. |
| Prova | Testes sintéticos | Ensaio instalado e piloto ainda não feitos. |

## S3 — impressão digital por host

`quota_router/qualified_hosts.json` contém entradas de fonte do Hermes de trabalho e do Docker `hqr-s1-test`, vinculadas ao conjunto completo de fingerprints; a revisão `3b421578588243f920886e6fe79a6faa87ea026e` também deve coincidir quando legível.
Cada entrada atual contém 134 SHA-256 de funções e 19 valores de constantes, incluindo hashes/projeções das tabelas de resolução e os aliases de provider (D18/R1).
A conferência desta rodada leu somente fontes e metadados Git, sem abrir configuração, sessões ou credenciais reais.
A continuação acrescentou 17 funções de delegação e corrigiu os hashes inertes de `FileBackend.read_path/write_path` para incluir `@staticmethod`, como faz a inspeção do objeto carregado.
As definições não carregadas são inspecionadas de forma inerte no arquivo original; seus corpos não são executados.
Objetos nativos já carregados têm preferência na comparação, e fonte indisponível suspende Auto.
A lista inclui a camada de configuração e seus escritores inferiores, a forma nativa de seleção de modelo, a resolução de esforço do cron, os leitores de delegation/sessão e models.dev e as constantes `FOLLOW_SECTIONS`, `FOLLOW_AGENT_KEYS`, `VALID_REASONING_EFFORTS` e `PROVIDER_TO_MODELS_DEV`.
A entrada qualifica os bytes inspecionados, não uma instalação S3, a biblioteca YAML inteira ou cobertura de consumidores.
Qualquer mudança em um item suspende as escritas, inclusive recuperação e OFF, e o status informa o nome afetado.

A preparação de 2026-11-16 acrescentou a entrada Docker por inspeção somente de leitura: 65 funções e quatro constantes vieram do core do alvo, e seis funções e cinco constantes vieram da árvore pública fixada de advanced-delegation.
Os dois conjuntos completos são iguais aos da entrada de trabalho; não se usa caminho ou nome do container para desempatar a compatibilidade.
A revisão externa foi conferida no label `hqr.host` da imagem `hqr-s1-test:installed-ad3e180-run3`, mas a fonte do alvo não contém `.git/HEAD`.
A preparação anterior resultava em `native_source_unavailable` pela ausência desses metadados; a continuação HQR-26 resolve esse caso sem alterar o alvo.
Uma entrada com `allow_revisionless_match=true` permite qualificação sem revisão legível somente quando o conjunto inteiro de funções e constantes coincide exatamente, incluindo a dependência.
Uma revisão legível diferente sempre suspende Auto, mesmo com fingerprints iguais; entradas não marcadas e conjuntos parciais nunca qualificam.
O campo `source_provenance` da entrada Docker cita o label de imagem `hqr.host`, a recipe `tests/installed/Dockerfile` e o SHA-256 do tarball `2525046f165880c22f177f2214c8da3e26c58cb0aeab5bd09aad940556538897`; esses dados documentam a origem, não substituem a comparação de bytes.
O status usa `revision=null`, conserva a revisão declarada em `qualified_revision` e mostra `revisão do Hermes não identificada; impressões conferem` quando a qualificação completa passa.
A conferência somente de leitura desta continuação encontrou 65 funções e quatro constantes no Docker e combinou esse conjunto com seis funções e cinco constantes da dependência pública fixada, cujos 23 arquivos conferiram com o manifesto.
O conjunto combinado qualificou e um hash divergente suspendeu a qualificação; a dependência continua ausente no alvo, portanto isso não é qualificação de uma instalação S3 nem liberação de Auto antes da instalação autorizada.
A dependência ainda não está instalada no Docker; seus fingerprints foram calculados com `collect_symbols(..., plugin_root=...)` sobre o ref público `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`, independentemente da localização futura.
Não alterar fingerprints ou revisão para contornar esse gate; a localização do checkout não concede compatibilidade.
`hermes update` ou alterações locais exigem nova qualificação vinculada aos bytes efetivamente revisados.

### HQR-38: rede de segurança

`compat.SAFETY_NET` acrescenta 18 funções nativas que normalizam, releem, ativam, restauram e herdam `fallback_providers`; a lista e os motivos estão na [entrega HQR-38](../decisions/hqr-38-delivery.md).
A entrada de trabalho passou a 152 funções e 19 constantes, medidas por `collect_symbols` na fonte instalada; os 134 hashes anteriores coincidiram.
Inicialmente, a entrada Docker não foi medida de novo e recebeu `requalification_required`.
Na recuperação autorizada de 2026-11-17, a inspeção AST direta do alvo encontrou as 152 funções e 19 constantes exigidas, preservando todos os hashes anteriores.
A entrada Docker passou a registrar essas medições próprias; a revisão Git continuou não identificada e a qualificação instalada não é inferida dessa leitura.
Uma entrada com essa marca nunca é escolhida, com ou sem revisão Git legível, e o motivo é `host_requalification_required`; não se copiam hashes de outra entrada.

### D18: resolução padrão e overlays

R1 corrigiu a cobertura incompleta dos dois resolvers explícitos: a resolução normal passa por OAuth, pool ou `_anthropic_env_runtime`, não necessariamente por `_explicit_codex`/`_explicit_anthropic`.
O conjunto atual inclui os builders de URL de `auth_codex`, a ordem de seleção/overlay em `runtime_provider`, guards e reexports que preservam os providers canônicos e a formação final da seleção em `model_switch`.
As tabelas `_OAUTH_RUNTIME_PROVIDERS`, `_POOL_ENTRY_SIMPLE_MODES` e `_PROVIDER_API_MODE_OVERRIDES` recebem hash da atribuição completa e projeção AST dos campos de rota relevantes.
`compat_tables.py` não executa seus construtores ou lambdas e compara também as células públicas das tabelas já carregadas.
Lambdas inline são localizadas no AST do arquivo completo pelo filename e linha da função ativa; posições ambíguas são recusadas.
`_PROVIDER_ALIASES` é comparada como constante integral, em disco ou carregada; uma tabela requalificada não pode redirecionar os providers do espelho.
Um modo OAuth/pool requalificado que diverge do espelho público continua recusado.
As tabelas auxiliares `_HOST_MANDATED_API_MODES`, `_DIRECT_API_BASE_URLS` e `_RESPONSES_NATIVE_HOSTS` também fazem parte do conjunto obrigatório.

As duas árvores foram medidas novamente na revisão fixada, com bytecode desligado e audit hook recusando escrita, rede, subprocesso e leitura fora das fontes admitidas.
As duas entradas produziram o mesmo conjunto de 134 funções e 18 constantes; todos os fingerprints anteriores coincidiram.
A medição Docker continuou sem revisão Git legível e preservou o opt-in e a proveniência existentes, sem mudar a instalação.
Uma tentativa inicial esbarrou no import preguiçoso do unparser AST do Python 3.14; a projeção passou a usar campos AST normalizados, sem esse import e sem alterar o guard.
Isso é qualificação de fonte, não execução dos resolvers, credenciais ou ensaio instalado.

R2 recusa `model.openai_runtime` não vazio antes da prévia e de cada inscrição/escrita, inclusive recuperação e OFF.
O guard vale para conversa e subagentes porque o overlay global pode alterar o modo Codex de ambos; só o nome do campo entra em status, explain e estado.
Ausente, null e string vazia ou só com espaços são controles aceitos; outros tipos são recusados.
A inspeção conferiu o overlay final de `resolve_runtime_provider`, `model_derived_api_mode`, `_PROVIDER_API_MODE_OVERRIDES`, a formação da seleção e `raise_if_declared_key_missing`.
Não foi encontrada outra chave de configuração que reescreva endpoint/modo desses dois providers depois da resolução nessa fonte.
`model.base_url`/`model.api_mode` já pertencem à projeção; aliases e blocos `providers`/`custom_providers` atuam na seleção anterior, enquanto `request_overrides` e service tier não reescrevem o par de rota nesse trecho.
Overrides de ambiente e rotas explicitamente customizadas não passam a ser defaults qualificados por essa inspeção.

### Discrepâncias e fontes não qualificadas

- `Changes.set` documenta que `None` conserva um null explícito, mas `FileBackend.write_path` o passa para `utils.atomic_roundtrip_yaml_update`, que remove a chave em `utils.py:577–578`.
O produto não tenta corrigir o host; um null explícito na projeção impede o grupo nativo e aparece pelo nome do campo.
- `hermes_state_sessions.SessionSessionsMixin.get_session` chama `flush_for_read`, além de devolver campos como prompts que não pertencem ao estado do plugin.
O código do plugin não chama esse leitor enquanto a fonte não for qualificada.
- `get_session_model_config_value` usa o mesmo leitor e o `model_config` atual, que pode ter mudado desde a criação.
A fonte não comprova uma revisão imutável do modelo na criação nem o tipo da sessão-mãe no contrato testado; usa-se o fallback autorizado `geração indeterminada`, sem idade.
- O payload nativo de `api_request_error` usa `error={type, message}`; o adaptador conserva somente `type`, nunca `message` ou `request`.
- O Python do runner limpo não oferece `ruamel`, embora a fonte da camada de configuração esteja acessível.
Os ensaios locais usam a camada nativa com primitiva sintética e não qualificam persistência YAML ou resolução nativa de sessões.

Os hooks têm registro/disposal e redação exercitados em contextos sintéticos, mas continuam explicitamente não qualificados como cobertura instalada.
Os testes protegidos de S1/S2 preservam a recusa de Auto quando não há mapa e host qualificados.
O [registro S3](../decisions/s3-delivery.md) separa a implementação local das pendências do runner e do ensaio instalado.


### Dependência de delegação na S3

`model_map` não pertence ao core: o core oferece somente `delegation/default`, enquanto o plugin oficial `advanced-delegation` fornece `model_map` e `profile_routes`.
O pin lido em `plugin.yaml` e `.hermes-catalog.json` do plugin de trabalho é versão `1.1.0`, repositório `NousResearch/hermes-official-plugins`, subdiretório `advanced-delegation`, ref `13b2c1c9c8204bf333df240b2aacf98c3e6250b7`.
As funções acrescentadas ao fingerprint incluem resolução do registro/backend, `_route_one`, schema/parâmetros, esforço do filho, `DelegationProvider.settings` e seis funções de `model_map.py`, incluindo `task_parameters` e `route_task`.
A comparação usa o módulo da instância registrada no escopo atual, inclusive namespaces com sufixo de home, em vez de emprestar o módulo sem sufixo de outro profile.
Arquivo ausente, fonte carregada indisponível ou drift mantém o gate de compatibilidade fechado.

O status JSON publica `subagents.ok=false` e o texto informa rotas indisponíveis se advanced-delegation não estiver habilitado/carregado ou se o backend selecionado não for `model_map`.
O registro é consultado sem disparar discovery, loaders mutantes, autenticação ou inferência.
Em Auto, essas rotas recebem `backend_unavailable`; inscrição, aplicação, recuperação e restauração por OFF não escrevem nelas enquanto a dependência está indisponível.
A conversa pode continuar se os demais fingerprints qualificarem; grupos excluídos precisam do reingresso explícito já previsto para OFF/Auto.
Com um mapa aprovado, Observe usa os mesmos gates de Auto e suprime a mudança do grupo indisponível; propostas sem aprovação continuam identificadas como hipotéticas.

O [probe local da segunda continuação](../decisions/s3-delivery.md#continuação--c4c10-fechados-localmente-2026-11-16) usou cópia conferida e somente leitura da dependência, carregada por `discover_plugins` no home descartável.
Ele também exercitou escrita e leitura YAML nativas, que não devem ser confundidas com a integração hermética de primitiva JSON nem com instalação S3.
Naquele probe, o catálogo estático não aceitou todos os IDs do mapa aprovado; o probe injetou catálogo desconhecido e cotas sintéticas, de forma explícita.
O gate estático foi substituído pelo catálogo nativo models.dev, conforme a seção abaixo; aquele recibo não foi reexecutado nem promovido a uma validação real de catálogo.
A disponibilidade na conta, a instalação da dependência e a prova instalada continuam pendentes em HQR-26; a comparação de fontes sem Git foi resolvida nesta continuação.
O manifesto `tests/installed/advanced-delegation-13b2c1c.json` contém os 23 arquivos públicos do ref fixado, conferidos contra os blobs Git.
Os 23 arquivos também coincidem byte a byte com a cópia de trabalho; a árvore de trabalho inteira difere por `.hermes-catalog.json` e seis arquivos de `__pycache__`, não incluídos no manifesto público.

### Catálogo nativo models.dev na S3

`native_catalogs()` usa primeiro `_models_dev_cache` do módulo `agent.models_dev` já carregado, sem I/O nem refresh.
Sem cache em memória, importa o módulo se necessário, resolve `_get_cache_path()` e abre o JSON somente para leitura.
O mapa nativo `PROVIDER_TO_MODELS_DEV` resolve os providers, inclusive `openai-codex` → `openai`; os IDs são comparados exatamente, sem corrigir grafia ou canonicalizar.
O piso curado `hermes_cli.models_catalog_static._PROVIDER_MODELS` não é consultado e nunca bloqueia um papel.

Catálogo indisponível, vazio ou com entrada de provider ilegível significa desconhecido, não uma lista de modelos proibidos.
A decisão continua sujeita aos demais gates e informa `catalog_note="IDs não verificados"` e `catalog_unverified` no JSON; status e explain também exibem o aviso em texto.
Se um catálogo models.dev legível e não vazio não contiver um ID do mapa aprovado, o papel inteiro fica sem rota com `reason=model_absent_from_catalog`, os providers faltantes em `catalog_missing` e motivo legível no texto.
Não se troca para o outro provider para esconder esse erro de mapa.
Esses metadados públicos não comprovam acesso da conta, créditos, franquia incluída ou disponibilidade de transporte.

O plugin não chama os loaders offline nativos porque eles podem alterar cache e ETag.
Sem memória carregada, abre somente para leitura o caminho devolvido pelo helper nativo, interpreta JSON e trata qualquer falha como catálogo desconhecido.
O fingerprint acrescenta o leitor e nove helpers offline, incluindo a quarentena, e o valor de `PROVIDER_TO_MODELS_DEV`.
A revisão conferiu os 71 fingerprints e as nove constantes por inspeção inerte de fontes, sem executar o leitor no home real.
Os testes usam módulos/cache sintéticos; esta correção não reexecutou o probe nativo instalado nem abriu o cache real para afirmar presença dos IDs.
