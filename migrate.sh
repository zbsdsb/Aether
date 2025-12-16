#!/bin/bash
# 数据库迁移脚本 - 在 Docker 容器内执行 Alembic 迁移

set -e

CONTAINER_NAME="aether-app"

echo "Running database migrations in container: $CONTAINER_NAME"

docker exec $CONTAINER_NAME alembic upgrade head

echo "Database migration completed successfully"
