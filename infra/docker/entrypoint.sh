#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Earlyread SaaS — Odoo container entrypoint
#
# 1. Wait for PostgreSQL to accept connections (the pod can start before PG is
#    reachable — first deploy, PG restart, transient network).
# 2. Render odoo.conf from the baked-in template, substituting ONLY the
#    explicitly-listed env vars (so the db_filter regex's trailing `$` and any
#    other literal `$` in the template are left untouched).
# 3. exec odoo with the rendered config (+ optional ODOO_EXTRA_ARGS — the M5
#    init Job uses this to pass `-d <db> -i <addons> --stop-after-init`).
#
# Env vars expected (set by the Helm chart pod spec — M4b):
#   DB_HOST DB_PORT DB_USER DB_PASSWORD   — PostgreSQL connection
#   ODOO_ADMIN_PASSWORD                   — Odoo master password (DB mgmt)
#   ODOO_WORKERS ODOO_MAX_CRON_THREADS    — per-role process tuning
#   ODOO_EXTRA_ARGS  (optional)           — extra odoo CLI flags
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Required env vars (fail fast with a clear message if missing) ────────────
: "${DB_HOST:?DB_HOST not set}"
: "${DB_PORT:?DB_PORT not set}"
: "${DB_USER:?DB_USER not set}"
: "${DB_PASSWORD:?DB_PASSWORD not set}"
: "${ODOO_ADMIN_PASSWORD:?ODOO_ADMIN_PASSWORD not set}"
: "${ODOO_WORKERS:?ODOO_WORKERS not set}"
: "${ODOO_MAX_CRON_THREADS:?ODOO_MAX_CRON_THREADS not set}"

CONF_TEMPLATE="/etc/odoo/odoo.conf.template"
CONF_RENDERED="/tmp/odoo.conf"

# ── 1. Wait for PostgreSQL ───────────────────────────────────────────────────
# pg_isready is a pre-auth connectivity probe — no password needed. It returns
# 0 once the server is accepting connections.
echo "entrypoint: waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} ..."
for i in $(seq 1 60); do
  if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; then
    echo "entrypoint: PostgreSQL is accepting connections."
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "entrypoint: ERROR — PostgreSQL not reachable after 60 tries (~5 min). Exiting." >&2
    exit 1
  fi
  sleep 5
done

# ── 2. Render odoo.conf ──────────────────────────────────────────────────────
# The SHELL-FORMAT argument restricts substitution to exactly these names.
# Anything else with a `$` (e.g. the db_filter regex end-anchor) is literal.
echo "entrypoint: rendering ${CONF_RENDERED} from ${CONF_TEMPLATE}"
envsubst '${DB_HOST} ${DB_PORT} ${DB_USER} ${DB_PASSWORD} ${ODOO_ADMIN_PASSWORD} ${ODOO_WORKERS} ${ODOO_MAX_CRON_THREADS}' \
  < "$CONF_TEMPLATE" > "$CONF_RENDERED"
chmod 600 "$CONF_RENDERED"

# ── 3. Hand off to Odoo ──────────────────────────────────────────────────────
echo "entrypoint: starting odoo (workers=${ODOO_WORKERS}, max_cron_threads=${ODOO_MAX_CRON_THREADS})"
# shellcheck disable=SC2086  # ODOO_EXTRA_ARGS is intentionally word-split
exec odoo -c "$CONF_RENDERED" ${ODOO_EXTRA_ARGS:-}
