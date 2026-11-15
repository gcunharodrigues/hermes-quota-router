---
type: Product Specification
title: Hermes Quota Router — definição do produto
description: Plugin opcional de governança de franquias com distribuição GitHub, isolamento de ambientes e critérios explícitos de liberação.
status: draft
---

# Hermes Quota Router — definição do produto

Estado: transposição pública do contrato de produto; ainda sem implementação.
A revisão pública de execução precisa ser confirmada antes de BUILD; este documento não comprova prontidão operacional.

## 1. Autoridade, resultado e limites

Objetivo: distribuir um plugin opcional pelo GitHub, separando desenvolvimento, teste e produção e permitindo escolher a revisão instalada.
O resultado pretendido é instalar, inspecionar, ligar/desligar e remover um roteador opcional de franquias no Hermes, sem alterar silenciosamente modelos, permissões ou cobrança.
A cobertura inclui profiles atuais e futuros aderentes, conversa, cron, subagentes e auxiliares; habilitação por profile não prova cobertura global.[18]

O contrato define a implementação; a revisão de execução e as autorizações de publicação, instalação, credenciais, inferência e produção continuam separadas.
Nenhum comando de exemplo autoriza sua execução em um ambiente real.

Plano de execução em [product-plan.md](product-plan.md).

### Usuários, jornada e UX

Cada operador deve conseguir instalar a mesma revisão pelo GitHub e usar somente suas próprias contas/configurações, sem receber dados de outro usuário.
Jornada: escolher destino e canal, instalar desligado, verificar identidade/compatibilidade, observar recomendações reais admitidas e só então autorizar AUTO.
UX proposta, ainda inexistente: `/quota-router status`, `/quota-router mode off|observe|auto` e `/quota-router explain`.
Status mostra ambiente, revisão/canal resolvidos, modo salvo/efetivo, drenagem, cobertura e idade/fonte da quota; explain mostra candidatos, razão da escolha/recusa e reset, sem prompts ou credenciais.
Acessibilidade: saída textual legível, motivos não comunicados só por cor e contraste WCAG 2.2 AA em eventual componente visual.
Sucesso significa ciclo de instalação/retirada verificado, decisões explicáveis e ausência de cobrança/fallback implícitos; não há ganho de consumo, qualidade ou latência medido ainda.
Não objetivos do primeiro release: interface web própria, servidor central, proxy, cron novo, compras de créditos, mistura de contextos entre providers e coordenação de vários computadores.
Primeiro alvo proposto: Linux no runtime/arquitetura efetivamente qualificados em S1; outros sistemas só entram na matriz após ensaio próprio.

## 2. O que foi pesquisado e decisão de reaproveitamento

A pesquisa identificou cinco alternativas parciais, sem comprovar o conjunto integral dos requisitos: ds-router, Vibe Relay, OrqueHelx, Hermes Model Router e CLIProxyAPI/conector/cpa-status/Ebb.[19]
A recomendação é adaptar ideias de cadência e telemetria e usar o lifecycle nativo do Hermes, não instalar um desses projetos como solução integral.
Não copiar código de Vibe Relay enquanto a licença permanecer não esclarecida; separar licença de cada componente e preservar avisos quando houver reaproveitamento.[19]
Não introduzir proxy de prompts, serviço pago obrigatório ou daemon próprio apenas para acomodar um candidato parcial.
O formato de plugin é viável documentalmente; roteamento/veto universal antes de cada requisição não está demonstrado nas interfaces examinadas.[18]

## 3. Contrato de controle

Estados de produto propostos:

| Estado | Comportamento obrigatório |
|---|---|
| Ausente por escolha ou desabilitado efetivamente | Caminho nativo, sem roteamento ou novas consultas de cota do plugin. |
| OFF | Pacote disponível para gestão, política inativa; sem sondagens de cota ou alterações de rota. |
| Observe | Consulta apenas fontes admitidas e explica decisões simuladas; não troca modelos, bloqueia, reserva capacidade ou executa inferência extra. |
| Auto | Decide antes da admissão das unidades gerenciadas, somente entre candidatos autorizados e qualificados. |
| Mudança pendente | Distingue configuração salva de estado efetivo por processo/sessão; não anuncia OFF ou atualização aplicada antes da verificação. |

Instalar é separado de habilitar.
Após instalação sem habilitar, verificar origem/pin pela gestão nativa; habilitar o plugin carrega apenas sua gestão em modo OFF por padrão, e só depois seus comandos de produto ficam disponíveis.
Desligar afeta novas admissões; não cancela uma requisição já enviada nem muda o modelo de uma execução em andamento.
Unidades já admitidas drenam com seu pin e geração da política; novas unidades seguem o nativo quando OFF é solicitado.
Enquanto houver decisões/consultas da geração anterior necessárias à drenagem, o diagnóstico mostra mudança pendente, não OFF efetivo.
Desaparecimento inesperado do plugin com AUTO declarado é erro de integridade que bloqueia novas unidades gerenciadas, não OFF silencioso.
Callbacks ou providers já carregados podem exigir reconstrução/restart, e remoção não equivale automaticamente a disable/reload.[18]
O plugin não seleciona um backend exclusivo nem substitui permanentemente o provider configurado.
O procedimento de remoção exige OFF efetivo com drenagem ou restart autorizado, sem presumir que apagar arquivos restaure o nativo.
Restaurar somente configurações comprovadamente pertencentes ao plugin, sem sobrescrever alterações posteriores do usuário.
Dados locais de política/histórico só são apagados por escolha explícita, separada da remoção do código.

## 4. Fronteira técnica e identidade da execução

O plugin contém controle, política e observabilidade; a integração nativa precisa oferecer uma decisão anterior à resolução/envio para cada caminho gerenciado.
Um hook observador ou uma exceção de middleware fail-open não satisfaz essa fronteira.[18][6]
Contrato candidato: `decide(contexto) → allow | route | deny(motivo, retry_at)` antes de resolver client/transporte, `admit(pin, tentativa, destino_efetivo) → permit | deny` antes de cada envio físico e `settle(resultado)` ao terminar.
O host fornece em `destino_efetivo` a identidade opaca da conta, provider, transporte/modelo/esforço efetivamente resolvidos, sem expor segredos à política.
A permissão de envio fica vinculada a esse destino resolvido; uma alteração antes de enviar exige nova admissão correspondente, não reutilização da autorização anterior.
Rotação nativa de conta em retry do mesmo provider exige quota/elegibilidade da nova conta e novo vínculo de admissão; a leitura da conta anterior não a autoriza.
Isso não permite ao plugin trocar login, criar conta ou contrariar pins/provider/model/effort; se o host não fornecer essa fronteira por tentativa, AUTO permanece incompatível.
`retry_at` informa possibilidade de reenvio, não agenda sozinho; deferimento é um resultado tratado pelo caller.
O host deve aplicar negativas, timeout e falha da política fora dos caminhos fail-open, sem transformar recusa em fallback.
Esse contrato é proposta a qualificar, não API existente nem extensão autorizada.
Se a versão do Hermes não oferecer a cobertura exigida, Auto não pode ser habilitado como universal: o diagnóstico deve explicar a falta e o menor ajuste nativo necessário.
Não fazer monkey-patch silencioso, interceptar credenciais, reescrever histórico ou instalar um fork permanente como fallback implícito.
Qualquer extensão nativa deve ser desenvolvida em checkout separado do runtime e passar por autorização de escopo/instalação própria.

Cada unidade recebe ID, profile, ambiente, superfície, papel, origem da seleção, revisão de política e rota efetiva.
Fronteiras propostas: conversa = sessão com pin preservado nas retomadas; cron = execução nativa do job; subagente = execução lógica do filho; auxiliar = invocação lógica da tarefa auxiliar.
Tentativas/retries pertencem à mesma unidade, não criam nova oportunidade de balanceamento; uma retomada correlacionada reutiliza o pin persistido.
ID, origem ou vínculo ausentes no domínio governado geram incompatibilidade explícita; não inventar identidade a partir de prompts, nome de modelo ou posição no processo.
Uma seleção de role/default persistido não pode ser confundida com override explícito da invocação.
Overrides de usuário/chamada, pins de job e retomadas preservam provider/model/effort; não inferir essa origem pelo nome do modelo.
Uma rota explícita dentro do domínio governado mantém o destino e passa pela admissão; sem elegibilidade, recebe negativa sem troca automática.
Uma rota explícita fora do domínio Codex/Claude admitido segue o nativo e aparece como não gerenciada; não é fallback criado pelo plugin nem entra em uma alegação de proteção universal.
A rota automática é fixada pela duração da unidade; decisões posteriores não reformatam o contexto para outro provider.
Retries/fallbacks físicos precisam estar na matriz de cobertura e contabilização, sem garantia presumida a partir de uma chamada lógica.
Não reescrever histórico, prompt/toolsets ou mecanismos nativos de cache, permissões, approvals e isolamento de profiles.
Trocar provider no início de uma nova unidade não garante cache aquecido nem equivalência de qualidade/esforço; o mapa de candidatos exige validação por tarefa.

### Stack proposta

Módulos de biblioteca Python carregados pelo host Hermes, com entrada nativa `register(ctx)`; sem CLI autônoma, serviço, proxy ou daemon novos.[5]
A escolha conserva a linguagem do host para biblioteca e integração, não propõe um novo executável Python genérico.
SQLite transacional é a opção inicial de estado local, sem prometer que uma base de dados execute trabalho agendado.
Não acrescentar Rust/FFI/IPC ao primeiro release sem parte executável durável ou benefício medido que compense build, distribuição e operação.
Se surgir essa necessidade, aplicar a ordem de linguagens e rever o contrato antes da implementação.

## 5. Política de franquias e falhas

Qualidade e compatibilidade por papel eliminam candidatos antes da comparação de disponibilidade.
Modelos/esforços vêm de um mapa explícito por provedor; benchmark de API não mede consumo de assinatura nem comprova equivalência de tarefas.
Não usar um LLM extra para decidir a rota.
A política precisa distinguir conta, modelo e superfície, unidades do fornecedor, janela, reset, duração conhecida, instante e proveniência da leitura.
Campos ausentes, leitura vencida, erro de autenticação, contrato desconhecido ou relógio inconsistente são desconhecidos, não capacidade livre.
Não somar barras de semana geral e Fable nem converter percentuais por magnitude.

Parâmetros iniciais propostos para ensaio: bloqueio de sessão em 95%, semanal/modelo em 100%, idade máxima de leitura em 60 segundos.
Esses parâmetros são hipóteses de produto configuráveis, não previsão de consumo ou calibração validada.
A escolha por ritmo semanal exige duração de janela respaldada pelo contrato; reset isolado não fornece duração.
Proposta determinística: para cada janela semanal aplicável, calcular `headroom = 1 - used_fraction`, `remaining_fraction = (reset_at - now) / duration` e `score = headroom / remaining_fraction`.
Somente contratos com `duration > 0` e `0 < remaining_fraction <= 1` podem entrar nesse ranking; inconsistência exige nova leitura e mantém a rota inelegível até esclarecimento.
O score do candidato é o menor score das janelas semanais aplicáveis; comparar scores é uma heurística de ritmo relativo, não equivalência de tokens, dinheiro ou quantidade de trabalho entre assinaturas/modelos.
Precedência: havendo preferência anterior elegível para o papel/revisão, conservá-la até um desafiante superar seu score em mais de 10%; empate ou vantagem exatamente de 10% mantêm a preferência anterior.
Somente na ausência de preferência anterior elegível escolher o maior score e, em empate, o principal configurado; sem principal entre os empatados, usar a ordem estável dos candidatos na política.
A margem de 10% é proposta não calibrada; a preferência anterior é guardada por papel e revisão de política, sem retomar um pin de execução como preferência global.
Leituras devem ser da identidade/conta/modelo/superfície e contrato qualificados; entre eventos comparáveis usar a coleta mais recente, e divergência no mesmo instante fica desconhecida.
Timestamps são UTC com timezone; duração/freshness usam relógio monotônico no processo quando possível, sem inferir continuidade após restart.
Idade entre zero e 60 segundos inclusive é aceita; data futura, idade maior, timestamp inválido ou reset igual/anterior ao instante exigem nova leitura, sem supor quota zerada.
Igualdade nos limiares de uso bloqueia; ausência de janela só dispensa o gate quando seu contrato confirma que não se aplica.
A concorrência usa coordenação local por conta e registro transacional de admissões; leases não são medidores de tokens ou garantia de franquia futura.
Clientes externos e outras máquinas podem consumir a mesma assinatura sem participar do estado local.
Expiração de lease não prova fim de requisição; recuperação distingue dono encerrado, chamada ainda ativa e resultado desconhecido, sem repetir envio/efeito ambíguo.

Sem candidato elegível, conversa recebe motivo e reset conhecido.
Sessão já pinada não é rebalanceada em um turno posterior só porque a quota mudou.
Trabalho automático recebe recusa/deferimento explícito; o produto não pode prometer retomada por relógio se não tiver integração real com caller/scheduler nativo.
Não criar daemon, cron ou ciclo recursivo para encobrir ausência desse contrato.
Ao atingir limite durante uma execução, preservar a rota e devolver pausa/erro tipado com estado retomável quando suportado; não migrar silenciosamente para outro provider.

## 6. Cobrança e transporte Claude

OAuth, consulta de quota, aceitação de uma inferência e franquia debitada são evidências distintas.[12][15]
A documentação específica do Hermes para OAuth nativo e a documentação Anthropic de Claude Code/SDK têm escopos diferentes; esta definição não certifica a franquia Pro na rota nativa.[12][15]

Invariante proposto de produto: um candidato de assinatura só entra em Auto após comprovação da combinação conta + plano + transporte + modelo + janela aplicável.
Fonte de cobrança desconhecida ou dependente de extra usage fica inelegível para roteamento automático de franquias.
API paga não é fallback implícito.
Fable permanece desabilitado como candidato automático até qualificação específica e escolha explícita, sem adotar promoção temporária como capacidade permanente.

Gate de liberação: não declarar o balanceamento Codex↔Claude pronto enquanto a rota Claude exigida não estiver qualificada.
A definição pode avançar e o lifecycle ser construído sem esse gate resolvido; a ativação correspondente não pode.
Testes reais exigem autorização própria de alvo, conta, modelo, payload, chamadas/retries e risco de cobrança, sem presumir teto financeiro a partir de um timeout.
Não ativar créditos extras, trocar login ou copiar tokens para fazer um teste passar.

## 7. Desenvolvimento, teste e produção

| Ambiente | Identidade e dados | Permissão padrão |
|---|---|---|
| Desenvolvimento | Instalação/runtime/ambiente Python e home próprios; Hermes inteiro em sandbox separado, com dados sintéticos e nenhuma credencial de produção. | Editar e executar testes isolados após provisionamento autorizado. |
| Teste | Instalação e sandbox próprios, revisão candidata fixada, caches/SQLite/logs separados; sem login, sockets ou agentes externos herdados de produção. | Integração sintética e smoke do pacote instalado; chamadas reais somente com credenciais/contas de teste e autorização específica. |
| Produção | Instalação homologada e profiles explicitamente selecionados, com backups e estado próprios. | Uso real apenas após ativação autorizada. |

Profiles da mesma instalação compartilham seleção de dependências Python e não constituem sandbox de filesystem/credenciais; a pesquisa qualifica essa limitação, não o isolamento executado.[7]
Separar o Hermes inteiro em usuário/container/VM com instalações/ambientes Python próprios e sem mounts, sockets, agentes SSH ou variáveis produtivas; home diferente ou apenas terminal sandboxado não basta.[7]
O mecanismo concreto exige checagem de disponibilidade e autorização no provisionamento; ausência de contenção verificável bloqueia ensaios que poderiam alcançar produção.
`plugins.isolation: host` separa processos, não comprova isolamento de filesystem, credenciais ou dependências.[7]
Dev/teste não podem ler ou alterar credenciais, dados ou settings de produção.
Não copiar auth stores para testar; o harness carrega autenticação nativamente apenas quando um teste real estiver autorizado.
Se uma mesma assinatura for usada em mais de um ambiente sob exceção aprovada, o consumo externo continua compartilhado; isolamento de diretórios não cria outra franquia.
Instalar um RC no Hermes utilizado em trabalho real é um piloto de produção com versão candidata, não um teste isolado.
Esse piloto é opção separada e requer alvo, impacto, backup, critérios de parada e rollback explícitos.

## 8. GitHub, canais, instalação e rollback

Repositório de distribuição: `gcunharodrigues/hermes-quota-router`, público e com licença MIT.
Nenhum histórico privado, snapshot de conta, caminho local, inventário operacional ou recibo interno integra a distribuição.
CI com possível custo, publicação e instalação exigem suas autorizações específicas.

O usuário escolhe ambiente de destino e canal, não apenas uma branch flutuante.
Teste corresponde a candidato/prerelease; produção a release estável homologada.
Todo install deve resolver e registrar revisão imutável, versão, canal, origem e compatibilidade; `main`/`latest` mutável não é pin de execução.
Promoção reutiliza o mesmo conteúdo homologado; não faz rebuild ou dependência nova sem novo teste.
No contrato público pesquisado, `--ref` aceita somente SHA completo de 40 hexadecimais, não branch/tag/SHA curto; a instalação registra origem e revisão resolvidas.[7]
Tags e releases nomeiam canais no processo do produto; antes da instalação, resolver a referência autorizada para seu commit completo e conferir a promoção registrada.
Receita futura de instalação nova, não executada: `hermes plugins install gcunharodrigues/hermes-quota-router --ref <SHA40_APROVADO> --no-enable`.[7]
`<SHA40_APROVADO>` é placeholder explícito: não existe revisão pública deste produto ainda, e nunca deve ser passado literalmente ao comando.
Para inspeção nova pode-se acrescentar `--no-deps`, mas isso não substitui plugin ativo nem prova prontidão do runtime.[7]
Reinstalar com `--no-enable` não desativa uma seleção já existente; primeiro drenar/desativar e verificar estado efetivo.[7]
Pin Git permanece fora do update normal; mudança/rollback de código usa explicitamente `--force --ref <SHA40_APROVADO>` na mesma origem, após scanner/review do candidato.[7]
`--force` também aceita cautela do scanner: não usá-lo para contornar negativa ou dispensar gate de segurança; findings materiais continuam bloqueando.[7]
Reinstalar preserva arquivos locais e não restaura config/banco; conferir árvore instalada, arquivos ignorados e hashes do payload, não apenas HEAD/metadados.[7]
SHA sozinho não congela dependências/runtime/configuração: o recibo da versão deve fixar também manifest/locks admitidos, Python/Hermes e schema de dados.[7]
GitHub Environments condicionam jobs de Actions e proteções dependem de plano/visibilidade; não são isolamento local nem pré-requisito pago obrigatório.[7]
Repo privado usa autenticação nativa já autorizada para aquele ambiente; não copiar/exibir tokens nem colocar credenciais na URL.[7]
Não depender de download automático de release assets/wheels ou build Rust/Cargo: esses caminhos não foram demonstrados.[7]

Instalação nova começa desligada; atualização só ocorre após desligamento efetivo explícito, pois o instalador não o garante por si.[7]
Atualização não faz promoção automática de Teste para Produção.
Rollback restaura código/revisão e configuração compatíveis após neutralização; migração irreversível de estado não é admitida no primeiro release.
Antes de reativar, conferir os arquivos efetivamente instalados e executar smoke naquele alvo, não só na árvore fonte.
A seleção de um pacote em um profile não atualiza os demais automaticamente.
Profiles futuros precisam de onboarding verificável para a versão/canal escolhidos; a ausência de onboarding é lacuna visível de cobertura, não um sucesso presumido.
A intenção AUTO global do ambiente precisa ser verificada pelo host ao iniciar cada profile, incluindo um recém-criado, sem copiar credenciais ou ampliar suas permissões.
Se faltar carregamento/enforcement nesse profile, falhar explicitamente no domínio gerenciado; não tratar falta de plugin como desinstalação intencional.
Essa exigência pode depender da extensão nativa já condicionada na seção 4; não presumir que a habilitação profile a profile atual a implemente.

## 9. Segurança, dados e atenção adicional

- Credenciais continuam no mecanismo nativo do Hermes; o plugin não possui cofre nem exporta tokens.
- Estado mínimo: identificador local opaco da conta, ambiente/profile, janela normalizada, revisão da política, decisão e timestamps.
- Não persistir prompts, respostas, headers, tokens, emails ou valores monetários no estado compartilhado ou em logs.
- Expor status/diagnóstico com fonte, idade da leitura, rota, razão, versão/canal e divergência de estado salvo/efetivo.
- Impedir cruzamento de caminhos/symlinks entre ambientes e validar schemas de política/metadados remotos.
- Releases devem conter apenas código, testes, docs públicos, licença autorizada e provenance, nunca material privado do estudo.
- Não prometer isolamento de segredo só por usar variável de ambiente, perfil ou criptografia em repouso.
- Retenção proposta para eventos locais de decisão: 7 dias, configurável; exportação saneada e exclusão sob demanda.
- Não reduzir gates, mudar testes protegidos ou ampliar capabilities para acomodar o roteador.
- A matriz de compatibilidade deve declarar os sistemas realmente exercitados; distribuição no GitHub não comprova operação em todo sistema.
- Registro de dados: identificadores opacos de conta/unidade, nome local do profile, janelas, decisões e timestamps, usados só para admissão/explicação no dispositivo e sujeitos à retenção/exportação/exclusão acima.
- O responsável pelo ambiente é o operador local; eventual uso com terceiros exige definir responsabilidade/controladoria no onboarding, sem presumir relação jurídica ou autorização de cliente.
- Cada provider permitido deve estar autorizado a receber o texto da unidade pela execução nativa; a allowlist de custo/modelo não substitui autorização de dados.

## 10. Critérios de aceitação

| ID | Critério e evidência exigida |
|---|---|
| AC-01 | Pacote instalado no alvo de teste real escolhido; versão/canal/ref e hashes correspondem ao candidato. |
| AC-02 | OFF/ausência intencional/desabilitado mantém o nativo e inicia zero consultas/inferências extras do plugin após desligamento efetivo; ausência inesperada com AUTO declarado falha explicitamente. |
| AC-03 | Observe mostra decisões com proveniência sem alterar rota ou settings; fixtures não são apresentadas como quota real. |
| AC-04 | Auto usa só candidatos autorizados/qualificados, respeitando papel, origem da seleção, pins e retomadas; preferência anterior elegível tem precedência sobre desempate pelo principal. |
| AC-05 | Matriz cobre conversa/cron/filhos/auxiliares, sync/async/streaming e cada tentativa física, inclusive retries de SDK/fallback; erro/timeout/ausência inesperada da política não contornam a negativa. |
| AC-06 | Testes de unidade contratual distinguem percentuais/frações, conta/modelo/superfície, zeros, valores fracionários, 1 e 100, ausência e reset inválido. |
| AC-07 | Concorrência, queda de processo, lease expirado com chamada ativa, store indisponível e cache inválido não geram dupla decisão/envio silencioso ou quota fictícia. |
| AC-08 | Sem candidato e limite durante execução produzem resultado tipado; nenhuma troca de transporte ou retomada autônoma não demonstrada. |
| AC-09 | Plano/conta/transporte/modelo desconhecidos ou sem franquia comprovada não entram em Auto; admissão vinculada ao destino efetivo por tentativa, inclusive após rotação nativa de conta, sem cobrança extra implícita. |
| AC-10 | Hermes inteiro em dev/teste não acessa dados/config/credenciais/sockets de produção nem altera seu ambiente de dependências; controles negativos comprovam a separação, não só homes distintos. |
| AC-11 | Instalação de Teste, instalação de Produção e promoção têm escolhas e recibos distintos; revisão mutável ou artefato divergente é recusado. |
| AC-12 | Desativar, remover, reinstalar e rollback exercitados no alvo; estado em voo e necessidade de reload/restart são visíveis e não deixam backend órfão. |
| AC-13 | Criar profile de teste após instalar o plugin e verificar onboarding/enforcement global autorizado; ausência inesperada bloqueia o domínio gerenciado e aparece no diagnóstico. |
| AC-14 | Pacote/provenance públicos não contêm dados do estudo; scan, allowlist e inspeção do histórico/conteúdo publicado vinculados à revisão exata. |
| AC-15 | Testes reais e ativação de produção têm autorizações e limites próprios; resultado sintético ou código commitado não substitui prova instalada. |

## 11. Estado documental

Este é o contrato público, não uma implementação nem uma aprovação de implantação.
A [emenda HQR-20](hqr-20-amendment.md) substitui as partes listadas na seção 9 dela; Guilherme a aprovou em 2026-11-15.
O [registro de bootstrap](bootstrap.md) informa a fase corrente e a confirmação de revisão necessária antes de S1.

## Reference definitions

[12]: https://hermes-agent.nousresearch.com/docs/integrations/providers
[15]: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
[18]: ../evidence/plugin-native-research.txt
[19]: ../evidence/plugin-existing-research.txt
[5]: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
[6]: https://hermes-agent.nousresearch.com/docs/developer-guide/middleware
[7]: ../evidence/product-delivery-research.txt

## Sources

[5] https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
[6] https://hermes-agent.nousresearch.com/docs/developer-guide/middleware
[7] /evidence/product-delivery-research.txt — Pesquisa pública de distribuição e isolamento
[12] https://hermes-agent.nousresearch.com/docs/integrations/providers — Hermes — provedores, OAuth e extra usage
[15] https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan — Anthropic — CLI/Agent SDK usam limites da assinatura
[18] /evidence/plugin-native-research.txt — Pesquisa pública: viabilidade e limites do plugin
[19] /evidence/plugin-existing-research.txt — Pesquisa pública: cinco soluções parciais
