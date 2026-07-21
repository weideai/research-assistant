#!/bin/sh
set -eu

mkdir -p backups
timestamp=$(date +%Y%m%d-%H%M%S)
docker compose --env-file .env.production exec -T db pg_dump -U research -d research | gzip > "backups/research-${timestamp}.sql.gz"
find backups -type f -name 'research-*.sql.gz' -mtime +30 -delete
echo "Backup created: backups/research-${timestamp}.sql.gz"
