#!/bin/sh
set -e

# Make sure the mounted writable folders exist and belong to the runtime user.
mkdir -p /app/logs /app/instance /app/uploads
chown -R appuser:appuser /app/logs /app/instance /app/uploads 2>/dev/null || true

exec su appuser -s /bin/sh -c "$*"
