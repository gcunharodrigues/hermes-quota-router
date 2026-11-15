# Hermes Quota Router

Plugin opcional de governança de franquias para Hermes Agent.
Leia a tarefa corrente indicada no README e a especificação/plano antes de editar.
Este bootstrap ainda não contém código de produto nem demonstra instalação, cobertura de chamadas ou cobrança incluída.
O avanço a BUILD depende do commit de execução confirmado pelo responsável.
Não inferir autorização de push, merge, release, instalação, credenciais, gastos ou produção a partir da existência deste repositório.

## Conhecimento OKF

- Perfil `per-repo`, bundle `decisions/`, índice `decisions/index.md`, histórico `decisions/log.md` e configuração `.okf/config.toml`.
- Staging `raw/` e arquivo `source-archive/`: criar apenas para ingestão autorizada.
- Semântica e navegação são editadas pelo agente; `okf apply` é reservado aos planos gerados e revisados.
- Resolver o binário pelo pacote físico da skill `$okf`, nunca escolher um binário arbitrário no PATH.
- Comandos genéricos: `okf --root . --json inspect`, `okf --root . --json plan-bootstrap --profile per-repo --output <plano-novo>` e `okf --root . --json validate --profile per-repo --gate both`.
- Continuar trabalho pelo link corrente no README, preservando os pins da tarefa.

## Código, dados e segurança

- Implementar em branches/worktrees de tarefa; não escrever código de produto na checkout principal.
- O host permanece dono da autenticação e da adaptação de transporte; o plugin não guarda prompts ou credenciais no estado compartilhado.
- Não contornar hooks fail-open com monkey-patch; AUTO exige as decisões D2 a D6 e os critérios AC-16 a AC-25 da emenda HQR-20 qualificados.
- Desconhecido não equivale a quota disponível; inferência aceita não comprova franquia incluída.
- Desenvolvimento, teste e produção isolam o Hermes inteiro, suas dependências, dados e credenciais; profiles ou worktrees não são sandbox.
- Estado/configuração/contexto de produção não são fixtures.
- Testes usam scratch/cache fora do repositório; rede e credenciais ficam limitadas ao ensaio autorizado.
- Preservar testes protegidos e os arquivos de suporte; mudanças exigem aprovação específica.
- Workers não editam arquivos de instruções protegidos; solicitar a alteração ao coordenador.
- Não copiar código de licença não esclarecida nem publicar histórico privado do estudo de origem.

## Texto e verificações

- Texto autoral com uma frase por linha; nenhuma linha autoral, inclusive código, pode exceder 2000 caracteres.
- Exceções identificadas: `evidence/*.txt` são relatórios públicos congelados; ledgers JSON são dados; `LICENSE` é o texto padrão de licença; lockfiles/gerados futuros devem ser enumerados com motivo antes de qualquer exceção nova.
- O bootstrap verifica diretamente o limite em seus documentos; S1 deve criar o gate executável do produto sem simular sua existência antes disso.
- Gate atual: validação OKF oficial/perfil, citações quando presentes e `git diff --check`/`git diff --cached --check`.
- Não anunciar testes/build de plugin enquanto seus arquivos não existirem; comandos planejados estão em `decisions/product-plan.md`.
- CodeGraph: índice privado `.codegraph/` por checkout, fora do Git; após mudar código, executar `codegraph sync .` com downloads/telemetria/update-check desabilitados e verificar a raiz física.
- Registrar pendências no `## Backlog` do README com ID, origem, trabalho e condição de conclusão; fechar com data/evidência, sem apagar.
