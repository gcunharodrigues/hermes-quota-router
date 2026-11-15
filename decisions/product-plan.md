---
type: Product Delivery Plan
title: Hermes Quota Router — plano de entrega
description: Fatias utilizáveis, gates de publicação/instalação e prova de ambientes para o plugin de franquias.
status: draft
---

# Hermes Quota Router — plano de entrega

Estado: transposição pública do plano; bootstrap documental, sem código de produto.
Contrato funcional e AC-01–AC-15 em [product-spec.md](product-spec.md).
Este plano não é autorização de BUILD, publicação, instalação, credenciais, gastos ou ativação.

## 1. Destinos e separação de repositórios

- Código/distribuição propostos: repositório limpo `gcunharodrigues/hermes-quota-router`.
- Primeiro destino utilizável: Hermes de teste isolado, em versão conhecida, com o plugin efetivamente instalado a partir de revisão GitHub escolhida.
- Destino final: profiles de produção explicitamente escolhidos por o responsável, com recibo de código/canal/estado efetivos.
- Nenhum histórico de contas, inventário operacional ou evidência privada do estudo será usado como ancestral do repositório publicado.

## 2. Preparação e confirmação de execução

1. Conferir e confirmar o commit desta definição pública antes de criar BUILD.
2. Preservar repositório limpo, commit vazio inicial, branch/worktree de tarefa, OKF e índices CodeGraph independentes.
3. Manter fora da distribuição dados, histórico e recibos privados da origem.
4. Revisar e verificar a transposição pública e seus hashes; equivalência documental não é teste de produto.
5. Após confirmação da revisão, criar S1 BUILD e sua DEMO bloqueada no board do produto, com base no commit de execução confirmado.

O bootstrap não é uma fatia de produto concluída nem autoriza push, merge, release, gastos, credenciais ou instalação.
Mudanças no destino ou no escopo exigem reconciliar o contrato antes de criar os cards dependentes.

## 3. Sequência de fatias

```text
Definição revisada e aprovada
             │
   Bootstrap limpo e pin aprovado
             │
 S1 — instalar e gerir no Hermes de teste
             │ aceite da DEMO
 S2 — roteamento e matriz completa no teste
             │ aceite da DEMO
 S3 — piloto autorizado, promoção e produção
             │ aceite da DEMO
 Onboarding de outros usuários/profiles suportados
```

Cada BUILD tem um único escritor dos arquivos compartilhados, paralelismo somente entre frentes independentes e review critical com três perspectivas, por envolver fronteiras de acesso, controle de chamadas e distribuição.
O tier não autoriza acesso a credenciais ou alteração de profiles/runtime.
Cada DEMO nasce bloqueada e só é aceita por o responsável na conversa do default.
S2 depende do aceite de S1; S3 depende do aceite de S2 e dos gates operacionais específicos.
S1 foi aceita em 2026-11-15; a [emenda HQR-20](hqr-20-amendment.md) substitui S2 e S3 por Observe com cotas reais, Auto nas próximas tarefas e promoção; Guilherme a aprovou nesse dia.

## 4. S1 — ciclo de vida e canais no destino real

**Resultado utilizável:** o responsável consegue escolher o candidato de Teste, instalar o pacote no Hermes de teste isolado, verificar versão/canal/compatibilidade e operar OFF/Observe sem interferir na produção.
Não entregar apenas um ZIP, arquivo-fonte, plano ou execução em fixture como se fosse instalação real.

### Escopo

- Manifesto/estrutura de plugin e contrato de configuração versionados.
- Identidade visível de ambiente, canal, revisão resolvida e estado efetivo.
- Comandos de produto propostos na spec: status, modo e explicação, com avisos textuais de ambiente/compatibilidade.
- Diagnóstico de compatibilidade do Hermes e das superfícies pretendidas.
- Biblioteca e entrada nativa Python no host; nenhum daemon/CLI autônomo ou core Rust no primeiro release.
- Instalação desabilitada, habilitação controlada, OFF/Observe, remoção, reinstalação e retorno ao caminho nativo.
- Política/estado/logs isolados; status deve mostrar desconhecido/não configurado quando não houver fonte real admitida.
- Receita de instalação GitHub por revisão e rollback, conforme contrato nativo qualificado na pesquisa.
- Pacote sem credenciais e sem efeito global sobre dependências ou settings de produção.

### Critérios e prova

AC-01–AC-03, AC-10–AC-12 e AC-14–AC-15 aplicáveis ao ciclo de vida.
Provar instalação no alvo real, comparar arquivos instalados à revisão, conferir status antes/depois, contador de chamadas do plugin em OFF e controle negativo de cruzamento de ambientes.
A integração sintética deve rodar também contra os arquivos instalados; um teste da árvore fonte não comprova a instalação.
Fixtures continuam identificadas como sintéticas e não são apresentadas ao usuário como quota de sua assinatura.
Quotas reais não são requisito presumidamente autorizado desta fatia: precisam de conta/credencial de teste ou exceção explícita antes da prova.
Sem essa autorização, status real deve declarar ausência/desconhecido, não inventar percentuais.

### Caminhos e limites

No futuro repositório limpo: módulo do plugin, manifesto/lockfiles necessários, testes novos, docs/OKF e workflow de verificação/publicação autorizado.
Ainda não existem esses arquivos; os nomes e comandos executáveis serão conferidos ao criar a estrutura, não tratados como APIs já disponíveis.
Não escrever no Hermes de produção, em profiles existentes, no store de credenciais, em testes protegidos ou em outro projeto.
Criação de repo/push/prerelease e instalação no alvo dependem das permissões operacionais correspondentes.
Se faltar uma permissão requerida para o destino real, preservar o código/evidência e bloquear só o dependente; não marcar S1 concluída localmente.

## 5. S2 — política e cobertura no teste

**Resultado utilizável:** no Hermes de teste, o plugin admite ou recusa rotas gerenciadas com motivo e proveniência, exercitando conversa, cron, subagentes e auxiliares, inclusive retries e streaming, sem chamar modelos reais implicitamente.

### Escopo

- Adaptadores de janela com schema/unidade/proveniência explícitos, reset/freshness e leitura desconhecida segura.
- Política determinística por papel, seleção fixada por unidade e origem de pin/default identificada.
- Coordenação local por conta sem declarar que locks/leases reservam franquia no servidor.
- Integração com as quatro superfícies e ponto anterior a cada tentativa física gerenciada.
- Recusa/deferimento e comportamento durante limite, sem fallback pago ou migração de contexto.
- Visibilidade de chamadas/superfícies não cobertas e de profiles sem onboarding.
- Estado auditável mínimo, retenção/exportação/exclusão saneadas.

### Critérios e prova

AC-04–AC-09 e AC-13, mantendo as regressões de S1.
Testes devem distinguir unidade lógica de tentativa física; zero sondagens adicionais em OFF; pins/retomadas; snapshots faltantes/antigos; fração versus percentual; Fable versus semana geral; erro/timeout no middleware; store indisponível e concorrência.
Exercitar igualdade nos limiares, idade exatamente em 60 segundos, coleta futura, reset igual ao instante, duração desconhecida, conflito de leituras e histerese de 10%, sem transformar percentuais em tokens.
Caso HQR-DEF-001: principal Codex, preferência anterior Claude elegível e scores iguais deve manter Claude; vantagem exatamente de 10% também mantém Claude, e só vantagem superior permite a troca.
Sem preferência anterior elegível e com empate, esperar o principal; sem principal empatado, esperar a ordem estável dos candidatos da política.
Caso HQR-DEF-002: retry com provider/model/effort preservados, mas conta efetiva alterada de A para B, deve exigir nova admissão ligada a B; quota só de A ou identidade B desconhecida resulta em negativa, não reutilização da permissão.
Se B estiver previamente autorizada e qualificada, sua própria leitura precisa satisfazer os gates antes do envio; mudança de destino entre admissão e envio invalida a autorização anterior.
Exercitar drenagem com geração preservada, lease expirado com chamada viva e ausência inesperada do plugin em AUTO; nenhuma dessas condições equivale a capacidade liberada ou OFF intencional.
Usar ambiente isolado e dados/transportes sintéticos para regressão, explicitamente sem alegar validação de quota, cobrança ou qualidade real dos modelos.
A matriz de coverage deve apontar caller, resolver, adaptação de client/transporte, veto e observação da tentativa para cada superfície.

Se a interface nativa não permitir o contrato, o BUILD deve mostrar o gap e o ajuste mínimo proposto antes de qualquer mudança em outro checkout.
Não contornar com monkey-patch, proxy oculto ou observer fail-open.
Uma extensão do core, se necessária, requer escopo aprovado, checkout de desenvolvimento separado, preservação dos patches locais conhecidos e revisão/instalação próprias.
Sem extensão qualificada, a capacidade correspondente fica inelegível e não se pode anunciar Auto universal.
Sem integração real com scheduler/caller, `defer` não é promessa de despertar sozinho no reset.[18]

### Caminhos e não objetivos

S2 usa os módulos/biblioteca/testes/docs de S1 no novo repositório; não altera auth stores, profiles produtivos ou o Hermes instalado.
O checkout de core eventualmente necessário não faz parte dessa allowlist até aprovação específica e reconciliação do plano/card.
Sem extensão de host qualificada, preservar o trabalho independente e bloquear o dependente; não aceitar uma demonstração parcial como cobertura universal.

## 6. S3 — piloto autorizado e produção

**Resultado utilizável:** o responsável escolhe a revisão homologada e os profiles de produção, instala/atualiza pelo GitHub, habilita o comportamento qualificado e consegue desligar/remover/reverter sem perder contexto ou estado indevidamente.

### Gates prévios

- S2 aceita, pacote e matriz de compatibilidade fechados.
- Cobrança por conta/plano/transporte/modelo comprovada para cada candidato de assinatura.
- Mapa de modelos/esforços por papel aprovado; Fable não habilitado por promoção temporária ou escolha do agente.
- Plano exato de piloto com alvo, conta, payload, contagem de operações/tentativas/retries, logs saneados e condição de parada.
- Autorização específica de publicação/push, instalação/restart, uso de dados reais e inferência potencialmente faturável quando aplicável.
- Backup/readback e rollback ensaiados nos arquivos efetivamente instalados.

### Prova

AC-01–AC-15 na versão selecionada, distinguindo o que foi provado sinteticamente do que foi observado no runtime real.
Testar o candidato em alvo admitido, promover o mesmo conteúdo e verificar novamente a identidade instalada; não confiar em tag flutuante ou apenas sucesso do instalador.
Se for usado RC no Hermes de trabalho real, registrar como piloto de produção, não como isolamento de teste.
Falha ou efeito externo ambíguo exige reconciliação antes de repetir instalação/envio/chamada.
Compatibilidade de schemas deve permitir rollback para a revisão anterior; desativar antes de restaurar e reativar só após smoke no alvo.

### Critério de conclusão

Não concluir o produto Codex↔Claude sem a rota Claude qualificada.
Não declarar produção ativa por existir release, código commitado, credencial aceita, snapshot de quota ou demonstração sintética.
Aceite humano, versão/canal/alvo efetivos e limites remanescentes devem constar do handoff.

### Caminhos e não objetivos

S3 pode preparar código/docs/recibos e workflow de release autorizado no novo repo; publicação e instalação seguem os alvos/caminhos expressamente aprovados na autorização operacional.
Product-lead não recebe acesso produtivo implícito: default coordena a aplicação admitida e a verificação no destino com o responsável.
Não criar repositório/CI pago, publicar release, copiar credenciais, mudar profiles ou reiniciar produção por mera aprovação do BUILD.

## 7. Distribuição, instalação e atualização

Repositório proposto, canais e receitas futuras estão na especificação; SHA40, pin, reinstalação e limites de isolamento constam da pesquisa preservada.[7]
Receita de instalação nova: `hermes plugins install gcunharodrigues/hermes-quota-router --ref <SHA40_APROVADO> --no-enable`, somente no alvo autorizado e com o SHA real substituído.[7]
Para mudar revisão/rollback, desativar efetivamente e drenar antes de `--force --ref`; `--no-enable` não desativa plugin já selecionado e reinstalação não limpa banco/config/arquivos locais.[7]
Comparar também arquivos ignorados e edição local com a allowlist do pacote; metadados corretos com código antigo/modificado não satisfazem AC-01.
Congelar versão do host/Python, declarações/locks de dependências admitidos e schema do store no recibo, não apenas commit do plugin.
Não depender de recurso pago ou proteção de GitHub Environments sem qualificação do plano/visibilidade e autorização de custo.
Instalações/ambientes Python e Hermes inteiro de dev/test/prod ficam separados por usuário/container/VM admitidos, sem credenciais ou mounts/sockets produtivos.[7]
O provisionamento deve demonstrar identidade real, caminhos e controles negativos; não basta sandboxar o terminal enquanto o plugin roda no host produtivo.
A instalação deve oferecer escolha explícita de ambiente e revisão, com origem e hashes verificáveis, começando OFF.
Atualizações de canal e produção não seguem automaticamente o último prerelease.
Nenhuma alteração global de auto-update dos outros plugins é autorizada para obter esse resultado.

## 8. Comandos e verificações

Gates documentais deste bootstrap:

- `$okf --root . --json validate --profile per-repo --gate both`, resolvido pelo router fixado, não pelo PATH.
- Helper de citações com ledger explícito e `verify --strict` para os documentos que usam fontes.
- `git diff --check` e `git diff --cached --check` para o escopo preparado.
- Gitleaks instalado, com saída redigida e escopo exato do candidato; não prova ausência universal de segredo.

Contrato futuro de arquivos: `plugin.yaml`, `__init__.py`, biblioteca `quota_router/`, testes `tests/unit/`, `tests/integration/`, `tests/installed/`, `docs/` e bundle `decisions/`.[7]
Esses caminhos são propostas para o novo repositório, ainda inexistentes, não arquivos descobertos neste estudo.
S1 fixa versão do host/Python e confirma essas fronteiras antes do primeiro RED; não há dependência adicional planejada além da biblioteca padrão/nativa.
Comandos planejados de S1 e regressão de S2/S3, nunca executados aqui porque ainda não existe código do produto:

```sh
python3 -m unittest discover -s tests/unit -p 'test_*.py' -v
python3 -m unittest discover -s tests/integration -p 'test_*.py' -v
python3 -m unittest discover -s tests/installed -p 'test_*.py' -v
python3 -m compileall -q __init__.py quota_router
git diff --check
```

Rodar esses comandos só no sandbox admitido com scratch/cache/pycache fora do repo e rede/credenciais delimitadas; inspecionar o harness antes da execução.
Discovery com zero casos não passa o gate: verificar contagem e cobertura de AC, não apenas exit code.
S1 não tem build binário; o pacote é a árvore Git qualificada com manifesto, biblioteca e recibo de arquivos/hashes.
S2 acrescenta a matriz de superfícies ao mesmo runner; S3 reexecuta regressão contra as cópias instaladas e o piloto real separadamente autorizado.
Não instalar runner/dependência, enfraquecer testes ou apresentar compilação do inventário como verificação do roteador.
Seguir RED/GREEN com testes novos, registrar REDs e preservar todos os testes protegidos, inclusive fixtures/helpers/config que os suportam.
Revisão critical de cada BUILD: reviewer, security-reviewer e test-engineer, com snapshots e limites reais.

## 9. Handoff e gates humanos

Default conserva definição, conversa, aprovações e bootstrap documental.
Product-lead constrói cada fatia aprovada e executa sua revisão independente; não ganha permissão de publicar/instalar/alterar perfis por receber o card.
Research fica com pesquisas públicas delimitadas; resultados não são prova operacional.

Nenhum BUILD/DEMO será criado nesta fase de definição.
A aprovação será pedida com commit exato; a publicação/visibilidade, git init do repo limpo, push, instalação e ativação terão perguntas próprias quando necessários.
Cada pendência, achado opcional ou gate não executado permanece no backlog canônico com ID, origem, trabalho e condição de conclusão.

## Reference definitions

[18]: ../evidence/plugin-native-research.txt
[7]: ../evidence/product-delivery-research.txt

## Sources

[7] /evidence/product-delivery-research.txt — Pesquisa pública de distribuição e isolamento
[18] /evidence/plugin-native-research.txt — Pesquisa pública: viabilidade e limites do plugin
