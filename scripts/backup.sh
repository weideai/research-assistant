#!/bin/sh
set -eu

mkdir -p backups
timestamp=$(date +%Y%m%d-%H%M%S)
docker compose --env-file .env.production exec -T db pg_dump -U research -d research | gzip > "backups/research-${timestamp}.sql.gz"
docker compose --env-file .env.production exec -T web tar -czf - -C /app/instance uploads > "backups/research-uploads-${timestamp}.tar.gz"
find backups -type f -name 'research-*.sql.gz' -mtime +30 -delete
find backups -type f -name 'research-uploads-*.tar.gz' -mtime +30 -delete
echo "Backups created: backups/research-${timestamp}.sql.gz and backups/research-uploads-${timestamp}.tar.gz"
