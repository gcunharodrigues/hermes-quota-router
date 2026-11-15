# Public inputs only; no project checkout or operator home in this context.
FROM python@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
LABEL hqr.task="t_1c0d7681" hqr.host="3b421578588243f920886e6fe79a6faa87ea026e"
ENV HOME=/home/hqr HERMES_HOME=/home/hqr/state PYTHONPYCACHEPREFIX=/home/hqr/pycache
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates build-essential && rm -rf /var/lib/apt/lists/*
COPY host.tar.gz /opt/host.tar.gz
RUN echo '2525046f165880c22f177f2214c8da3e26c58cb0aeab5bd09aad940556538897  /opt/host.tar.gz' | sha256sum -c - && mkdir /opt/hermes && tar -xzf /opt/host.tar.gz --strip-components=1 -C /opt/hermes && rm /opt/host.tar.gz
WORKDIR /opt/hermes
RUN python3 -m pm.build_env --source /opt/hermes --out /opt/hermes-venv --python /usr/local/bin/python3 --cache /home/hqr/state/cache/uv
ENV PATH=/opt/hermes-venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
RUN mkdir -p /opt/hqr-receipts /home/hqr/state && python3 -c "import importlib.metadata,json,sys; from pathlib import Path; Path('/opt/hqr-receipts/python-packages.json').write_text(json.dumps({'python':sys.version,'prefix':sys.prefix,'packages':sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())},sort_keys=True,indent=2))" && sha256sum pyproject.toml uv.lock pm/lock.json > /opt/hqr-receipts/source-locks.sha256 && dpkg-query -W > /opt/hqr-receipts/os-packages.txt
RUN useradd --uid 10001 --create-home --home-dir /home/hqr hqr && chown -R hqr:hqr /home/hqr
USER 10001:10001
# Download/install during image preparation; runtime tests remain network=none.
RUN /opt/hermes-venv/bin/hermes plugins install gcunharodrigues/hermes-quota-router --ref ad3e180f32adea3c25a2ef91280f1f6308729a47 --no-enable && git clone --mirror https://github.com/gcunharodrigues/hermes-quota-router.git /home/hqr/public-mirror.git
CMD ["sleep", "infinity"]
