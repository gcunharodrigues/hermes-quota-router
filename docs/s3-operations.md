# Operação S3 — Auto nas próximas tarefas

Esta é a implementação local `0.3.0rc1`, não uma instalação nem o aceite da S3.
O contrato combina o [plano aprovado](../decisions/s3-plan.md), a [seção 17 da emenda](../decisions/hqr-20-amendment.md#17-decisões-de-2026-11-16-para-a-s3) e a correção D18 da seção 18.
Publicação, qualificação Docker, ensaio instalado e piloto real exigem autorização própria.

## Ativação em ambiente autorizado

1. Conferir `mode off`, a revisão instalada, o scanner nativo `safe` e os arquivos contra o SHA completo.
2. Conferir as impressões digitais do host específico em `quota_router/qualified_hosts.json`.
3. Executar `/quota-router mode observe` e `/quota-router explain` para examinar as leituras e a recomendação.
4. Executar `/quota-router config approve-map base` para gravar os 12 papéis, com modelo e esforço próprios por provedor.
5. Executar `/quota-router mode auto` e `/quota-router apply` somente depois dos gates do destino.
6. Conferir `/quota-router status`, os grupos inscritos, a geração aplicada, a idade e a releitura nativa.
7. Executar `/quota-router mode off` para restaurar apenas os grupos intactos antes de desabilitar, substituir ou remover.

Todos os comandos mantêm saída legível por padrão e aceitam `--json` para o mesmo resultado estruturado.
`apply` executa um ciclo quando Auto está efetivo.
`status` e `explain` também podem executar um ciclo em Auto.
OFF não lê cotas e Observe não altera rotas.
A ausência de mapa, um profile diferente de `default`, uma configuração inválida ou uma impressão incompatível impedem Auto.
Fable e Astra continuam inelegíveis, mesmo quando oferecidos.
Um identificador ausente de um catálogo nativo já carregado deixa o papel inteiro sem roteamento, sem substituição silenciosa.
O catálogo curado não prova disponibilidade na conta; o plugin não chama a descoberta que exige tokens.

## Grupos inscritos

A conversa contém exclusivamente `model.provider`, `model.default`, `model.base_url`, `model.api_mode` e `agent.reasoning_effort`.
A rota contém exclusivamente `provider`, `model`, `base_url`, `api_mode` e `reasoning_effort` da opção com o nome do papel em `delegation.backends.model_map.options`.
A lista é escrita inteira pela camada nativa, mas somente os cinco campos da opção são alterados.
Descrição, nome, fallbacks e opções próprias não são comparados nem restaurados.
O cron não tem grupo e nenhuma chave `cron.*` é gravada.
`consumers.cron` permanece aceito, sem efeito sobre a escrita, e o status mostra a origem de modelo, provider e esforço por padrão e job.
Esforço válido do job prevalece sobre o override do modelo efetivo e sobre `agent.reasoning_effort`.
Pins parciais aparecem como parciais e não impedem Auto na conversa.
Desde HQR-38, cada grupo tem também um grupo próprio de rede de segurança em `fallback_providers`, descrito na [operação HQR-38](hqr-38-operations.md).

O plugin recusa a conversa em forma curta, aliases `model.model`/`model.name`, campos `api_key`, `api`, `key_env`, `api_key_env`, `context_length`, endpoint/modo próprios ou override para um modelo da conversa.
Rotas com endpoint, modo ou credencial próprios também ficam fora.
D18 aceita endpoint/modo ausentes ou vazios, ou exatamente os defaults nativos qualificados do provedor atual, tanto na conversa como nas opções de subagente.
A aplicação sincroniza os dois campos com os defaults do provedor escolhido; OFF conserva presença e valor originais.
O espelho público em `quota_router/routes.py` é vinculado às constantes nativas qualificadas, sem chamar um resolver que retorne credenciais.
Essas verificações ocorrem na inscrição e novamente sob lock antes de escrever, recuperar ou restaurar.
A saída informa somente os nomes dos campos, nunca os valores recusados.
Status e explain publicam os bloqueios de cada papel em `routing_blocks`, inclusive em Observe, sem anunciar uma mudança que Auto recusaria.
Uma sincronização apenas de endpoint/modo aparece como `sincroniza` seguida dos nomes dos campos.
Explain renderiza `settings.roles`, sem linha própria de cron; qualificação da fonte não implica prova instalada.
O backend nativo observado remove a chave quando recebe `None`, mesmo em `Changes.set`; por isso um grupo nativo com `null` explícito na projeção fica fora, pois sua presença original não poderia ser restaurada exatamente.
Essa restrição conserva o estado em vez de improvisar uma escrita de documento inteiro.

## Diário e recuperação

Os arquivos ficam em `<HERMES_HOME>/plugin-data/hermes-quota-router/`, nunca no código ou no documento de configuração.
`state.json` guarda linha de base, último aplicado, presença por chave, gerações e a marca de Auto.
`journal.json` guarda um único grupo, anterior, alvo, horário e intenção de restauração.
`salt.json` guarda o sal local e `events.json` conserva no máximo 128 fatos fechados.
O histórico também conserva no máximo 128 gerações; evidência anterior ao histórico disponível não recebe idade inventada.
A remoção autorizada desses arquivos após OFF elimina o histórico local e o sal; uma exportação deve limitar-se a esses arquivos, sem copiar configuração ou sessões.

Cada ciclo adquire `auto.lock` com `fcntl.flock`, relê o estado e resolve o diário antes de outra decisão.
A publicação durável usa arquivo temporário, `fsync`, `rename` e sincronização do diretório.
Depois da escrita nativa, a projeção é relida; somente a igualdade com o alvo permite confirmar o último aplicado e apagar o diário.
Uma releitura divergente interrompe o ciclo antes de qualquer outro grupo, sem substituir o diário pendente.

| Releitura | Ação |
|---|---|
| Todas as chaves no anterior | Descartar o diário, sem escrever configuração. |
| Todas no alvo | Confirmar o alvo sem repetir a geração já confirmada. |
| Mistura exata de anterior e alvo | Completar o alvo. |
| Algum terceiro valor | Excluir o grupo, preservar a edição e continuar os demais. |

Sem diário, uma única divergência em relação ao último aplicado exclui o grupo inteiro.
OFF e consumidor desligado restauram a linha de base apenas dos grupos intactos, inclusive a ausência de uma chave.
Um ciclo explícito OFF → Auto inicia outra inscrição e captura uma nova linha de base, inclusive para um grupo anteriormente divergente.
Se a compatibilidade ou as configurações estiverem inválidas, a restauração fica suspensa e o comando não anuncia OFF efetivo.
Isso também vale depois de recarregar: grupos ativos e a marca durável, não o modo em memória, determinam a restauração necessária.

O lock coordena somente processos do plugin na mesma máquina.
Uma edição humana entre a comparação e a escrita pode ser perdida, inclusive em outra opção da lista escrita inteira.
Uma edição que produza exatamente uma mistura anterior/alvo depois de uma queda será completada.
Esses limites são os aceitos em D6 e D15, não uma proteção contra todos os escritores.

## Armazenamento privado e aliases YAML

O motor cria seu próprio diretório com modo `0700` e arquivos com modo `0600`, sem chamar o helper nativo que cria pastas permissivas.
Valida dono e permissões dos ancestrais, recusa links e arquivos especiais e usa descritores com `O_NOFOLLOW`, operações relativas ao diretório e publicação atômica.
Diretório existente permissivo, arquivo de outro dono ou link de lock suspende a operação; o plugin não altera silenciosamente o alvo do link nem corrige permissões preexistentes.
O operador precisa examinar a causa e corrigir o ambiente autorizado antes de recarregar.
Aliases YAML que compartilham nós no caminho de mutação do grupo com outra região são recusados antes de aplicação, recuperação e OFF.
O grupo excluído mostra `yaml_alias_crosses_group`; a configuração fica intacta.

## Hooks, cobertura e idade

Os cinco hooks do manifesto só são registrados com Auto efetivo e são descartados em OFF e unload.
O worker conserva o contexto do profile dono, mesmo quando o processo foi iniciado com outro `HERMES_HOME`.
`on_session_open` e `on_kanban_dispatch_tick` colocam um ciclo na fila limitada.
`subagent_start`, `on_session_start` e `api_request_error` registram somente horário, provider, modelo, papel, tipo de evento e classe de erro.
Os identificadores de sessão entram em disco apenas como SHA-256 com sal local.
Prompts, `child_goal`, mensagens, headers, request e texto de erro não entram no estado.
Os callbacks aceitam `**kwargs`, não propagam exceções e não aguardam lock, rede ou escrita em disco.
A fila tem 64 posições; um evento excedente pode ser descartado, pois o mecanismo é observador de melhor esforço.

Uma idade por tarefa exige fonte nativa qualificada, horário de criação, configuração gravada imutável e tipo conhecido da sessão-mãe.
A geração candidata é a última do grupo estritamente anterior à criação, com os mesmos valores e nenhuma aplicação nos 60 s anteriores, inclusive o limite de 60 s.
Uma sequência A₁ → B → A₂ não pode atribuir A₂ a uma sessão criada em A₁ apenas porque os modelos são iguais.
Mudança posterior do modelo, fonte não qualificada ou tipo da sessão-mãe desconhecido produzem `geração indeterminada`, sem idade.
Uma sessão em `follow_profile_config` segue a geração por turno, sem idade única.

A fonte de sessões deste host continua não qualificada: `get_session` chama `flush_for_read` e `model_config` é mutável.
A implementação usa o fallback explícito, sem abrir o banco nem consultar prompts de sessões reais.
Os hooks também continuam sem qualificação instalada; o status não os anuncia como cobertura demonstrada.
Sessões gerenciadas anteriores, pins, auxiliares, retries, fallbacks e chamadas em andamento continuam fora do alcance.

## Ausência, atualização e rollback

Unload não restaura rotas nem muda o modo salvo, porque desabilitar inesperadamente deve preservar a última decisão e a marca durável.
Na próxima carga, inclusive sem o subtree após uma remoção nativa, o status informa o intervalo `plugin ausente ou sem ciclo` e a última decisão retida.
Esse intervalo não distingue ausência de simples inatividade.
Enquanto o plugin está ausente, o diagnóstico disponível é `hermes plugins list`; o comando do plugin pode não existir.
A remoção do produto exige OFF efetivo, mas o comando nativo de remoção não é interceptado pelo plugin.
Remover sem OFF pode deixar a última rota instalada e apagar o subtree, conservando a marca no diretório de dados.

Toda troca de revisão segue OFF conferido → desabilitar → scanner `safe` → instalar com `--force --ref <SHA40> --no-enable` → conferir arquivos → habilitar → smoke.
Antes disso, conferir compatibilidade do estado com a revisão de destino: HQR-38 deixa grupos e histórico `fallback:*` que `233f4be` não aceita mesmo depois de OFF.
Para esse downgrade, o fluxo de troca de arquivos não basta; a preparação pura e a migração persistida ainda bloqueada estão no [registro HQR-38](../decisions/hqr-38-delivery.md#upgrade-e-downgrade-procedimento-ainda-bloqueado).
Não apagar estado nem restaurar configuração antiga cegamente para fazer o downgrade passar.
O scanner anterior à instalação evita substituir o candidato por bytes ainda não admitidos; a instalação nativa também mantém seu scanner.
O runner `tests/installed/s3_auto.py` implementa esse fluxo, cenários sintéticos no processo instalado, rollback e ausência.
O gate final exige C1–C10 aplicáveis, C12, E2 e o fallback AC-22; ausência de prova ou tentativa proibida impede aceite.
O ensaio instalado anterior passou na candidata `ba5d6f8`, mas não cobre os bytes da correção D18.
O runner atualizado começa com defaults nativos de endpoint/modo e exige aplicação, OFF exato e recusa de endpoint customizado; essa versão ainda não foi executada no Docker.
O argumento obrigatório `--advanced-manifest <arquivo>` contém `ref` igual ao pin completo e `files`, mapa de todos os caminhos relativos esperados para seus SHA-256.
Esse manifesto deve vir dos bytes públicos fixados e revisados pelo operador, não de uma releitura oportunista da instalação que será validada.
Sem ele o runner para; esta revisão não buscou a árvore pública nem qualificou um manifesto para Docker.
O fluxo `product_remove` recusa remover quando o modo salvo é Auto, a marca durável continua declarada ou algum grupo segue ativo.
Essa recusa pertence ao procedimento do produto, não impede alguém de invocar diretamente a remoção nativa.
Veja as pendências no [registro de entrega](../decisions/s3-delivery.md).
