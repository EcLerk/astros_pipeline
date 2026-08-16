#!/bin/sh

set -e

clickhouse-migrations \
    --db-host clickhouse \
    --db-port 9000 \
    --db-user "$CLICKHOUSE__USER" \
    --db-password "$CLICKHOUSE__PASSWORD" \
    --db-name "$CLICKHOUSE__DB" \
    --migrations-dir /app/clickhouse/migrations

exec python -m loader.main