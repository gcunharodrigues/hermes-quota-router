# Operação HQR-38 — estados de franquia e rede de segurança

Esta é a implementação local da [especificação HQR-38](../decisions/hqr-38-spec.md), não uma instalação nem um aceite.
Ela complementa a [operação da S3](s3-operations.md); tudo o que não está aqui segue as regras da S3.
Publicação, ensaio instalado e piloto real exigem autorização própria.

## Estados por provedor

Cada decisão classifica cada provedor em um de quatro estados, mostrados no status em português e em `quota.states` no JSON.

- Livre (`free`): semana abaixo do limite semanal e janela de 5 h abaixo de `limits.session_block_pct` (95% por padrão), ou plano sem janela de 5 h.
- Pressionado (`pressured`): semana abaixo do limite e janela de 5 h entre `limits.session_block_pct` e 100%.
- Esgotado (`exhausted`): semana no limite semanal (100% por padrão) ou janela de 5 h em 100%.
- Desconhecido (`unknown`): leitura ausente, vencida, inconsistente ou em formato não qualificado.

A ordem da escolha é: Livres; depois Pressionados; depois créditos permitidos e verificáveis; sem candidato, nada muda.
Entre Livres, a conversa continua no principal enquanto ele estiver Livre (`principal_first`).
Entre Pressionados, todos os papéis, inclusive a conversa, seguem a maior folga semanal.
A histerese de `limits.hysteresis_pct` vale dentro de cada grupo; a passagem de um grupo para outro não espera a histerese.
A janela semanal por modelo (Opus, Sonnet) e os limites por modelo do Codex (`additional_rate_limits`) contam só para o modelo que nomeiam.
O JSON de cada decisão traz `states` por provedor; os motivos dos Pressionados começam com `pressured_`.

## Rede de segurança (`fallback_providers`)

Em Auto, o plugin grava a rede de segurança nativa do Hermes, que troca de provedor ao receber erro de cota e volta ao principal depois da espera.
Ela vale para chats fixados por seletor ou `/model`, CLI e chamadas já em andamento; chats do Desktop sem escolha manual já seguem o Auto no turno seguinte.

- Conversa: a chave raiz `fallback_providers` recebe todos os candidatos elegíveis do papel `conversation` no mapa aprovado.
- Rota de subagente: o campo `fallback_providers` da opção em `delegation.backends.model_map.options` recebe todos os candidatos elegíveis do mesmo papel.
- A lista inclui a escolha do Auto: um chat fixado no provedor oposto precisa dela como alternativa, e só o consumidor nativo conhece seu primário efetivo.
- O Hermes ignora a entrada que representa seu backend corrente; não há patch no core nem troca do pin manual pelo plugin.
- Cada entrada tem somente `provider` e `model`, o formato canônico nativo; o resolvedor nativo completa endpoint, modo de API e credenciais.
- O esforço não entra na entrada, porque o formato nativo não tem esse campo; na troca, o Hermes resolve o esforço por `agent.reasoning_overrides` do modelo e depois `agent.reasoning_effort`.
- Cada candidato entra quando está Livre, Pressionado, ou Esgotado com créditos permitidos e verificáveis; Livres precedem Pressionados, que precedem créditos, com a escolha do Auto primeiro em seu grupo.
- Esgotado sem créditos permitidos, Desconhecido ou modelo inelegível fica fora da lista; se só a escolha do Auto é elegível, a lista ainda pode servir ao chat fixado no lado oposto.
- Sem escolha elegível, não há nova escrita (D-30); isso não promete que uma cadeia retida esteja vazia ou segura.
- Uma cadeia vazia é gravada como `[]` só quando a linha de base tinha a chave; sem a chave na linha de base, ela continua ausente.
- Uma rota sem a chave herda `delegation.fallback_providers` pela regra nativa; `[]` explícito desliga essa herança.
- A cadeia efetiva é qualificada antes da aplicação: herança fora dos candidatos elegíveis exclui só o grupo de segurança, sem sobrescrever a configuração humana não inscrita.

## Grupos inscritos da rede de segurança

Cada grupo da S3 tem um grupo próprio para a rede de segurança: `fallback:conversation` para a chave raiz e `fallback:<papel>` para cada rota.
Esses grupos seguem as regras da S3: linha de base com marca de ausência, diário, releitura, restauração exata em OFF e exclusão por edição externa.
Uma edição humana em `fallback_providers` tira do Auto só o grupo da rede de segurança; a rota ou a conversa continuam sendo aplicadas.
O consumidor desligado em `consumers.*` restaura a rota e a sua rede de segurança juntas.
O status mostra esses grupos em `applied.safety_net`, separados de `applied.groups`, e o texto os chama de "rede de segurança da conversa" ou "rede de segurança de <papel>".

A projeção é fechada: só aceita entradas com `provider` e `model` dos dois provedores governados, cada modelo do seu provedor, e no máximo `base_url` e `api_mode` iguais aos defaults nativos qualificados (D18).
Uma linha de base com credencial (`api_key`, `key_env`, `api_key_env`), outro provedor, outro campo ou valor fora desse contrato tira o grupo do Auto antes de qualquer escrita.
Nesse caso o status mostra só o nome do campo; o valor não entra em estado, diário, status ou diagnóstico.
Um `null` explícito em `fallback_providers` também fica fora, pela mesma razão de HQR-27.
O `fallback_model` legado não é escrito: o Hermes o acrescenta depois da cadeia raiz mesmo com `fallback_providers=[]`.
O plugin lê essa fonte apenas para qualificar o resultado efetivo; um legado fora dos candidatos elegíveis exclui o grupo de segurança e aparece somente pelo nome do campo.
Observe/explain aplica as mesmas precondições, restrição de null, divergência externa e exclusões finais aos grupos `fallback:*`.
Um grupo de segurança bloqueado tem `safety_net.state=group_blocked` e `chain=null`; isso não bloqueia a rota intacta e não expõe o valor recusado.

## Correções de leitura

- A22/SOL-06: reset nulo só qualifica ociosidade com uso 0% comprovado; uso positivo sem reset fica Desconhecido, com escopo por modelo quando o limite é desse modelo.
- A23/SOL-03: tolerância de relógio de 120 s em janela não iniciada; somente inconsistência temporal em formato qualificado admite avaliar créditos verificados e permitidos, nunca formato desconhecido ou reset vencido.
- SOL-03: resets por modelo vencem o cache e exigem nova leitura; na decisão final, um reset exclusivo de modelo bloqueia só esse modelo, sem reaproveitar sua janela antiga como créditos.
- A26: plano mensal do Codex (`plan_type` `go` ou janela de 28 dias ou mais) fica Desconhecido com motivo `monthly_plan_unsupported`.
- A27: Codex sem nenhuma janela e com créditos visíveis é plano só de créditos, Esgotado com créditos; sem prova de créditos, continua `no_week_window`.
- A29: `reset_passed`, `stale_reading` e `future_reading` tentam de novo depois de 30 s, sem o backoff de falha de 300 s.
- A31/SOL-02: cada item de `additional_rate_limits` vale para o modelo com o mesmo nome normalizado; duração ou valor não qualificados, `rate_limit:null` e slots novos deixam só esse modelo Desconhecido com `model_window_unqualified` e requalificação.
- A32: uso acima de 100% é limitado a 100% e conta como Esgotado.
- A34: um campo de janela novo em `rate_limit` dá o motivo `format_requalification_required`; rótulo ou duração não qualificados recebem `requalification_required`.
- A38: janela do Codex com uso nulo não entra na conferência de durações, como no leitor nativo.

## Limites

As correções locais SOL-01 a SOL-07 continuam sem aceite instalado; o [registro de entrega](../decisions/hqr-38-delivery.md) preserva as rodadas históricas e os resultados posteriores.
OFF seguido de reinstalação antiga não basta para downgrade depois da escrita de HQR-38; a operação explícita abaixo foi exercitada apenas em fixtures sintéticas.

As funções nativas que leem e usam `fallback_providers` estão em `compat.SAFETY_NET`; uma mudança em qualquer uma suspende Auto e o status mostra o nome.
A entrada de trabalho foi requalificada com essas funções; a entrada Docker também recebeu as medições diretas durante a recuperação autorizada de 2026-11-17, sem copiar hashes de outro host.
Isso remove a pendência de inspeção de fonte, não comprova ensaio instalado, Desktop ou fallback com provedor.
Uma entrada novamente marcada com `requalification_required` continua recusada com `host_requalification_required`, mesmo quando os hashes coincidem.
O runner instalado `tests/installed/s3_auto.py` confere os grupos da rede de segurança, mas ainda não foi executado em alvo instalado.
Planos só de créditos da Anthropic não se distinguem de uma leitura sem janelas, porque o leitor nativo não entrega o corpo bruto; continuam Desconhecidos (HQR-23).

## SOL-04: publicação explícita para a revisão anterior

`quota_router.downgrade.publish_legacy_state(engine, expected, mode_reader=...)` recebe os bytes originais esperados e um leitor do modo atual.
É uma API administrativa explícita, não um comando de instalação, migração automática ou restauração da configuração.
O chamador deve fornecer o Engine e backend qualificados do alvo admitido, confirmar OFF e conservar os mesmos bytes esperados ao retomar.
O limite é de 1 MiB para cada registro lido e para o alvo preparado; um snapshot ou alvo maior é recusado.

| Fase | Comportamento |
|---|---|
| Admissão | Mesmo `auto.lock`; OFF e compatibilidade, estado esperado e ausência física de diário Auto, inclusive quando seu JSON é falsy. |
| Backup | `hqr38-rollback-<sha256>.json`, criação exclusiva, bytes originais exatos, arquivo privado e fsync do arquivo e diretório; backup incompleto não é sobrescrito. |
| Intenção | `hqr38-downgrade.json` em `pending`, com hashes do estado original, do alvo e das projeções de configuração; a referência não muda na retomada. |
| Publicação | Nova comparação de identidade/bytes, modo e configuração; publicação atômica pelo storage existente e readback do alvo exato. |
| Conclusão | Última comparação do estado/contexto e recibo `complete` publicado e sincronizado sob o mesmo lock; backup e recibo ficam retidos. |
| Retomada | Somente original ou alvo exato com backup íntegro; terceiro estado, leitura falha ou contexto divergente interrompem sem sobrescrita. |

Enquanto existir intenção pendente ou malformada, as operações comuns do Engine recusam continuar.
Um recibo concluído é validado com backup e arquivo histórico; o Engine sincroniza o diretório antes de liberar o acesso.
Se fsync ou readback falhar, o chamador não pode interpretar a tentativa como concluída: deve preservar os artefatos e reconciliar explicitamente.
A revisão antiga desconhece esse guard; nunca deve ser carregada só porque `state.json` parece compatível ou o recibo parece concluído.
Antes da troca, a operação explícita deve confirmar novamente a conclusão durável.
A repetição depois de sucesso verifica o mesmo alvo/backup/contexto sem republicar estado ou criar arquivo histórico aninhado.
Depois que o legado modificar legitimamente o estado, uma nova tentativa com o snapshot original será recusada; não se restaura esse backup cegamente.

O hash de configuração cobre a conversa e os grupos inscritos no snapshot original, não o documento completo.
Campos fora dessas projeções não são monitorados e nunca são escritos pela migração.
Mudanças relevantes ainda em OFF, falhas do leitor, links, backup divergente e diário presente bloqueiam a operação.
O arquivo `hqr38_downgrade_archive` continua histórico inerte e não serve como baseline no retorno à candidata.
Há uma janela residual para processos externos que ignoram o lock: comparação e rename não constituem CAS.

Os testes focados e a prova entre Engines estão no [registro SOL-04](../decisions/hqr-38-delivery.md#publicação-e-idavolta-sintéticas-aguardando-rechecagem).
Essa prova usa backend sintético em memória e arquivos sintéticos; não qualifica uma troca instalada no Hermes de trabalho.
Não foram provadas queda de energia ou interrupção de processo; os checkpoints usam exceções no mesmo processo.
