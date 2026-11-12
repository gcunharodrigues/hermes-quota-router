# Testes sintéticos e prova instalada pendente

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

`tests/installed/` ainda não é uma suíte exercitada ou materializada.
Sem alvo admitido, não criar teste vazio, `skip` verde ou fixture rebatizada de instalação.
Após autorização, fixar caminhos reais, identidade de host/Python, allowlist e revisão e preparar o harness antes de qualquer execução instalada.
A regressão contra cópia exportada continua sendo sintética mesmo quando os hashes coincidem.
OFF/Observe no host real, ausência/desabilitação, reinstalação/rollback e controles negativos de isolamento permanecem pendentes.
Consulte o [roteiro operacional](s1-operations.md) e o [registro S1](../decisions/s1-delivery.md).
