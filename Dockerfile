# ─────────────────────────────────────────────────────────────────────────────
# Earlyread SaaS — Odoo 19 application image
#
# Layers on the official odoo:19.0 base:
#   • clickhouse-connect + anthropic — external_dependencies the addon
#     manifests declare (PyPI names use hyphens; Python imports use underscores)
#   • snowflake-connector-python (pinned) — the Snowflake PHI connector. NOT a
#     declared manifest external_dependency (declaring it would block module
#     load on any host without it); the executor imports it lazily. Pinned here
#     so production pods always have it. Pulls in cryptography for key-pair auth.
#   • gettext-base (envsubst) + postgresql-client (pg_isready) for the entrypoint
#   • posterra_portal + dashboard_builder addons → /mnt/extra-addons
#   • odoo.conf.template baked in; entrypoint renders it from env at start
#
# hha_crm_integration is intentionally NOT included — it was removed from
# posterra_portal's manifest `depends` list and has zero runtime references.
#
# Build (server-side; no local Docker needed):
#   az acr build --registry earlyreadsaasacreread \
#     --image odoo:<git-short-sha> --file Dockerfile .
#
# The build context is the repo root; .dockerignore keeps .git, .claude
# worktrees, node_modules, terraform state, etc. out of the upload.
# ─────────────────────────────────────────────────────────────────────────────

FROM odoo:19.0

LABEL org.opencontainers.image.title="earlyread-saas-odoo"
LABEL org.opencontainers.image.description="Odoo 19 + posterra_portal + dashboard_builder"
LABEL org.opencontainers.image.source="https://github.com/nshntkmr/earlyread-saas-odoo"

# Root for package installs + addon copy; drop back to odoo user at the end.
USER root

# Python deps declared as external_dependencies in the addon manifests.
# --break-system-packages: the odoo:19.0 base is Debian-based; recent Debian
# marks system Python externally-managed (PEP 668). The flag is a harmless
# no-op if the environment isn't externally-managed.
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
        typing-extensions \
    && pip3 install --no-cache-dir --break-system-packages --ignore-installed \
        clickhouse-connect \
        anthropic \
        snowflake-connector-python==4.6.0 \
    && rm -rf /root/.cache
# --ignore-installed on BOTH pip steps: snowflake-connector-python depends
# on a newer `idna` than the Debian-installed one, and pip fails to
# uninstall the Debian package ("RECORD file not found"). --ignore-installed
# tells pip to side-install the new version without touching the old one.

# gettext-base → envsubst (entrypoint renders odoo.conf)
# postgresql-client → pg_isready (entrypoint waits for PG)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gettext-base \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Addons → where odoo.conf's addons_path points. Owned by the odoo user.
COPY --chown=odoo:odoo posterra_portal    /mnt/extra-addons/posterra_portal
COPY --chown=odoo:odoo dashboard_builder  /mnt/extra-addons/dashboard_builder

# odoo.conf template — rendered at startup by the entrypoint via envsubst.
COPY infra/docker/odoo.conf.template  /etc/odoo/odoo.conf.template

# Custom entrypoint: waits for PG, renders odoo.conf, exec's odoo.
COPY infra/docker/entrypoint.sh  /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Drop privileges — runtime as the unprivileged odoo user.
USER odoo

# Odoo HTTP (8069) and longpolling/websocket (8072). The NGINX sidecar (M4b)
# listens on 8080 and proxies to these.
EXPOSE 8069 8072

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
