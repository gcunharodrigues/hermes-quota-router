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
