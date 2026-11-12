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
