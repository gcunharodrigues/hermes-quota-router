#!/usr/bin/env bash
# Run from the prepared bundle. Check is read-only; only the host operator runs --provision.
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
mode=${1:---check}
case "$mode" in --check|--provision) ;; *) printf 'Use --check or --provision.\n' >&2; exit 2;; esac
[[ $# -le 1 ]]
[[ $(hostname) == hermes && ! -e /.dockerenv && ! -e /run/.containerenv ]]
sha256sum --check --strict SHA256SUMS
D() { docker --host unix:///var/run/docker.sock "$@"; }
existing=$(D ps -a --format '{{.Names}}' --filter 'name=hqr-s1-test')
if [[ -n $existing ]]; then
  printf 'Já há alvo HQR neste Docker; inspecione e reutilize, sem criar outro.\n' >&2
  exit 1
fi
printf 'Pacote íntegro; nenhum hqr-s1-test encontrado no Docker local.\n'
[[ $mode == --provision ]] || exit 0
image=hqr-s1-test-base:3b421578
recipe=$(sha256sum Dockerfile.hqr-base | cut -d ' ' -f1)
if ! D image inspect "$image" >/dev/null 2>&1; then
  D build --file Dockerfile.hqr-base --label "hqr.recipe=$recipe" --tag "$image" .
fi
image_id=$(D image inspect --format '{{.Id}}' "$image")
[[ $(D image inspect --format '{{index .Config.Labels "hqr.host"}}' "$image_id") == 3b421578588243f920886e6fe79a6faa87ea026e ]]
[[ $(D image inspect --format '{{index .Config.Labels "hqr.recipe"}}' "$image_id") == "$recipe" ]]
D create --name hqr-s1-test --network none --cap-drop ALL --security-opt no-new-privileges=true --user 10001:10001 "$image_id"
observed=$(D inspect --format '{{.HostConfig.NetworkMode}} {{.Config.User}} {{len .Mounts}} {{.HostConfig.Privileged}} {{json .HostConfig.CapDrop}} {{json .HostConfig.SecurityOpt}} {{len .HostConfig.PortBindings}} {{.Image}} {{.State.Status}}' hqr-s1-test)
[[ $observed == "none 10001:10001 0 false [\"ALL\"] [\"no-new-privileges=true\"] 0 $image_id created" ]]
printf 'Alvo criado e parado. Nenhum plugin foi instalado ou executado.\n'
