# Operação S1 — gestão e receita

## Situação do run 4

O [run 4](s1-installed-test.md#run-4--ciclo-de-vida-completo-com-rede-2026-11-15) exercitou todo o roteiro abaixo no alvo de teste com o harness `tests/installed/lifecycle.py`.
`hermes plugins remove` apaga também a entrada `plugins.entries.hermes-quota-router` (modo e declaração); quem quiser preservá-las deve copiar a configuração antes.
O texto do run 2 abaixo é histórico.

## Situação do run 2

O [ensaio instalado](s1-installed-test.md) substitui as afirmações históricas abaixo de ausência de alvo/publicação por um recibo concreto.
O candidato `ad3e180f32adea3c25a2ef91280f1f6308729a47` foi instalado pelo GitHub desabilitado no Docker admitido.
A ativação foi recusada pelo PM e está bloqueada, sem repetir enable ou usar edição manual de seleção.
O roteiro abaixo continua contrato/proposta para os passos não exercitados, não evidência de conclusão.

## Limites e biblioteca

Este roteiro não autoriza instalação, provisionamento, acesso a contas, inferência, publicação ou produção.
O código S1 é gestão opcional, não um roteador de franquias qualificado.
O contrato permanece na [spec](../decisions/product-spec.md) e no [plano](../decisions/product-plan.md).

## Gestão disponível na biblioteca

A entrada nativa `register(ctx)` registra somente `/quota-router` e um callback de unload.
O manifesto `plugin.yaml` usa JSON, um subconjunto de YAML, sem dependências adicionais.
Não há provider, hook de inferência, ferramenta, socket, tarefa em background, daemon ou fonte de quota.
Os contadores `quota_queries` e `extra_inferences` representam exclusivamente operações desta implementação, não o tráfego do host.

- `/quota-router status`: versão, modo salvo/efetivo desta instância, revisão declarada, divergência e limites de compatibilidade.
- `/quota-router explain`: os mesmos diagnósticos; sem política S2 nem candidatos ou percentuais inventados.
- `/quota-router mode observe`: salva apenas `settings.mode` do próprio plugin pelo host; nenhuma troca de rota ou consulta de quota.
- `/quota-router mode off`: neutraliza a gestão desta instância; não confirma o estado de outros processos.
- `/quota-router mode auto`: recusa sem gravar; S1 não implementa admissão, enforcement global ou elegibilidade de cobrança.

OFF inicial não grava configuração.
Uma configuração anterior `observe` é preservada ao recarregar: reinstalar não significa desligar.
Modo salvo `auto` ou inválido gera `unavailable`, nunca confirmação de proteção ou OFF efetivo.
Falha de leitura gera diagnóstico indisponível; falha de gravação não altera o modo carregado e não expõe a exceção nativa.
Comandos concorrentes e unload são serializados nesta instância, não entre processos do host.
Uma edição externa de modo ou declaração permanece visível como divergência/restart, sem adoção silenciosa nesta instância.
Não existem admissões/pins em voo em S1; `draining` declara essa ausência de implementação, não uma drenagem universal comprovada.
Todos os processos precisam ser neutralizados/verificados antes de desativar, remover ou trocar código.

## Declaração de seleção

O operador configura a chave nativa relativa `deployment`, separadamente de `mode`, somente no alvo admitido.
Não há comando de instalação próprio ou alteração global de settings.
Exemplo de formato, com revisão sintética que NÃO deve ser instalada:

```json
{
  "schema": 1,
  "environment": "test",
  "channel": "candidate",
  "revision": "0000000000000000000000000000000000000000",
  "origin": "gcunharodrigues/hermes-quota-router"
}
```

A revisão exige SHA40 hexadecimal literal, sem converter branch/tag ou completar SHA curto.
S1 admite declarações `development`/`test` com `candidate`; `production`/`stable` são indisponíveis nesta fatia.
Ausência resulta em `unknown`; schema/campos inválidos em `invalid`.
A seleção carregada fica fixada até reload; status mostra também a seleção salva.
Uma declaração válida é `declared_not_verified`; `installed_verified` permanece falso.
Ela não autentica origem, bytes, isolamento, autorização de instalação nem promoção.
A verificação externa abaixo deve acompanhar o status e não é substituída por ele.

## Verificação de candidato e árvore instalada

A biblioteca `quota_router.verification` não executa Git, rede, instalação, código recebido nem operações do host.
`hash_tree(root, paths)` recebe uma allowlist explícita de caminhos relativos de uma revisão escolhida e só aceita conjunto exato.
`verify_tree(root, expected)` compara cada arquivo com o mapa SHA-256 externo confiável e relata `missing`, `extra` e `modified`.
Ambas rejeitam symlinks e entradas especiais; caminhos absolutos, traversal e nomes de credenciais são recusados na allowlist.
Somente metadados nativos `.git` na raiz ficam fora do payload.
Arquivos ignorados, caches, edições e sobras de reinstalação NÃO são dispensados do inventário.
Verificar árvore parada/quiescente, com pycache fora dela: o comparador não é sandbox nem proteção contra escritor concorrente.
Não ler arquivos adicionais de configuração/credenciais para satisfazer o inventário.
Derivar o mapa de uma exportação confiável da revisão e guardar esse mapa fora da árvore instalada.
Um mapa produzido da própria instalação não prova correspondência à revisão escolhida.
Vincular a revisão Git, sua árvore, os caminhos/modos e hashes, manifesto, licença, host/Python e resultados no recibo externo.
Inspecionar histórico público e executar Gitleaks no histórico e nos bytes exatos do candidato antes de qualquer envio autorizado.

## Proposta operacional para o coordenador

1. Admitir identidade e destino concretos para instalação integral de Hermes de teste e seu Python, separados de dev/produção.
2. Autorizar mecanismo de provisionamento e comandos, caminhos de escrita, rede de download público, dependências, backup e restart desse destino.
3. Provar identidade real, instalações e mounts efetivos e ausência de sockets/agentes/variáveis/credenciais produtivos com controles negativos sintéticos.
4. Escolher ambiente `test`, canal `candidate`, revisão final SHA40 e host/Python fixos; publicar/transportar esse conteúdo somente com autorização própria.
5. Conferir a sintaxe e efeitos da gestão nativa no host escolhido antes de operar; o host consultado em desenvolvimento não é um alvo admitido.
6. Fazer instalação nova desabilitada pela receita já aprovada no plano, substituindo seu placeholder somente pelo SHA escolhido.
7. Comparar árvore instalada, allowlist e hashes com a exportação revisada, incluindo arquivos ignorados e origem/pin nativos.
8. Registrar declaração `deployment` no namespace do plugin, conferir status nativo desabilitado e só então habilitar a gestão inicialmente OFF.
9. Em sessão fresca, exercer status/OFF/Observe/explain/recusa AUTO e repetir a integração sintética contra os módulos efetivamente instalados.
10. Exercer OFF em todos os consumidores, verificar neutralização e necessidade de restart, desativar e só então remover/reinstalar/rollback explicitamente.
11. Repetir a comparação de bytes e smoke após cada reinstalação/rollback; dados e configuração só são apagados por autorização separada.
12. Não concluir AC-01/10/12 nem S1 antes dessas observações no alvo e da revisão independente reconciliada.

`--no-enable` não é pedido de desativação prévia e `--force` não é limpeza de arquivos ou autorização para ultrapassar scanner.
Os comandos nativos de remoção/reload dependem da revisão efetiva; nenhum foi executado aqui.
O ramo/candidato local não está publicado, instalado ou promovido.
O [registro S1](../decisions/s1-delivery.md) e o [backlog](../README.md#backlog) distinguem fonte, testes sintéticos e provas pendentes.
