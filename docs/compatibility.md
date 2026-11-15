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
