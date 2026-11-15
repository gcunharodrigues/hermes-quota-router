# Operação S2 — Observe com cotas reais

A S2 lê as cotas pelos leitores nativos do Hermes e mostra, por papel, a assinatura que o Auto escolheria; ela não grava nada fora do subtree do plugin.
O Auto continua recusado até a S3.
O contrato está na [emenda HQR-20](../decisions/hqr-20-amendment.md) e no [plano da S2](../decisions/s2-plan.md).

## Comandos

As respostas vêm em texto para leitura: conclusão primeiro, depois as cotas, o que mudaria, o que pede atenção e os próximos passos.
Acrescentar `--json` a qualquer comando devolve o mesmo resultado como JSON estrito, para scripts e testes.

- `/quota-router mode observe` liga o Observe; `/quota-router mode off` desliga e zera o contador de leituras do período.
- `/quota-router status` mostra modo, profile, inscrição, configurações efetivas e inválidas e, em Observe, as leituras de cada provedor (janela, uso, reset, idade e fonte), o resumo da decisão por papel com motivo, resets, mudança proposta ou aprovada e jobs de cron com pin parcial, as notas do mapa (por exemplo, a queda do Astra para a base), o instante da decisão e o que fica fora da cobertura.
- Um profile sem o plugin habilitado não está inscrito: nada nele muda e o comando não existe ali; `hermes -p <profile> plugins list` mostra o estado.
- `/quota-router explain` acrescenta o detalhe de cada decisão (elegibilidade, ritmo, motivo, mudança proposta ou aprovada) e o mapa proposto com as quatro variantes.
- `/quota-router config` mostra as configurações; `config set <chave> <valor>` valida antes de gravar; `config reset <chave>` volta ao padrão.
- `/quota-router config approve-map <variante>` grava o mapa proposto da variante (`base`, `fable`, `astra` ou `fable+astra`) em `roles`; é a aprovação de D5.

Sem mapa aprovado, cada decisão sai como `proposal_only`, com `proposal_change`; depois de `approve-map`, sai como `decided`, com `would_change`.
Nesta fatia nenhuma das duas é aplicada.
Aprovar uma variante não libera seus modelos: um alvo Fable ou Astra continua inelegível (`model_not_eligible:fable` ou `:astra`) enquanto a janela própria do Fable e o catálogo da conta para o Astra não chegam ao plugin.

As chaves, padrões e efeitos estão na seção 13 da emenda.
Em `roles`, cada modelo precisa ser do seu provedor (`gpt`, `codex` ou `o<n>` no Codex; `claude` na Anthropic); um mapa trocado fica inválido e é ignorado.
Um valor gravado por `hermes config set` ou à mão não passa pela validação do comando: o status o lista em `settings_invalid` só com o tipo e o motivo, sem repetir o valor; o plugin usa o padrão daquela chave e a decisão sai marcada como incompleta.
A preferência usada na histerese vale para uma revisão das configurações, do par candidato e da rota atual; qualquer mudança em um deles começa uma preferência nova.

## Leituras

O plugin chama só `agent.account_usage.fetch_account_usage(provider, read_only=True)` e não vê tokens.
Do corpo `raw` do Codex ele guarda apenas indicadores de créditos (há créditos, ilimitado, saldo positivo, limite de excedente, limite de gasto) e a disponibilidade do Astra; o valor do saldo e o resto do corpo não são guardados.
Para confirmar a duração de cada janela do Codex, o plugin lê também `rate_limit.<janela>.limit_window_seconds`, sem guardar: o host rotula pela posição uma janela de duração ausente ou desconhecida, e esse rótulo não vale como prova; cada janela emitida precisa corresponder, na mesma ordem, a uma janela publicada com 5 h ou 7 dias; janela sem essa duração, ou janela publicada que o host descartou, deixa a leitura desconhecida.
Janelas com folga e `rate_limit.allowed` falso ou `limit_reached` verdadeiro se contradizem: o Codex fica fora da franquia e dos créditos.
Codex pago com créditos exige `has_credits` verdadeiro, saldo finito e positivo e os dois limites lidos como falsos; um limite ausente ou malformado deixa os créditos não verificáveis, e `unlimited` sozinho não basta.
A Anthropic não expõe `raw` nesse leitor: estado de créditos e janela do Fable aparecem como não verificáveis (HQR-23).
Uma leitura ausente, vencida, futura, de outro provedor, com rótulo de janela desconhecido, escopo que não confere com o rótulo, janela repetida, formato inesperado, reset já passado ou sem janela semanal fica desconhecida e nunca conta como capacidade livre.
A idade é medida com o relógio lido depois de cada busca; uma leitura no cache é revalidada a cada uso e buscada de novo quando um reset passa.
O inventário é lido antes das cotas; depois de reunir as leituras, todas são julgadas de novo num único instante de decisão, que é o `decided_at`.
Uma janela inconsistente com sua duração, esgotada ou não, bloqueia o provedor e não o torna candidato pago.
Limiares, ritmo e histerese usam frações exatas dos percentuais informados, sem arredondamento.
Cada leitura vale por `limits.reading_max_age_s` segundos; `quota_queries` conta as leituras do período do modo atual e `quota_queries_total` as da instância.
O leitor nativo do Codex pode renovar a credencial quando ela está perto de expirar; isso é comportamento do host, não do plugin.

## Limites

- A decisão de Observe roda só quando `status` ou `explain` são chamados; não há hook nem tarefa em background.
- O mapa proposto é heurística da S2 até Guilherme aprovar uma variante.
- O inventário lê o documento do profile com `hermes_cli.config_backend.read_config_doc`, que só abre e interpreta o arquivo, e lê `cron/jobs.json` diretamente; não chama `read_raw_config`, `load_config_readonly` nem `load_jobs`, que podem criar pastas, gravar backup ou reparar arquivos.
- As configurações do próprio plugin são lidas com `ctx.get_config`, como manda a seção 13 da emenda; no host conferido essa leitura passa por `load_config_readonly`, que pode criar a pasta do Hermes ausente e gravar um backup do `config.yaml` quando o arquivo mudou desde a última leitura do processo; isso é do host, não muda chave alguma, e o ensaio instalado mede se acontece.
- Esforços seguem a escala do Hermes (`none` a `ultra`, em `agent/reasoning_effort.py`); um valor fora dela aparece como ausente.
- O inventário não devolve endpoints, chaves, nomes de jobs nem prompts; um job com pin parcial aparece pelo id e pelos campos que faltam; nomes, ids de job, provedores, modelos e esforços fora do formato esperado, com forma de URL, de chave ou com `@`, são trocados por marcadores.
- Astra fica fora em toda variante nesta fatia: o catálogo da conta, exigido pela seção 15 da emenda, só é consultável com o token, que o plugin não manipula; com `models.astra` ligado o status explica e a variante cai para a base.
