#!/bin/bash
# Kept for backwards compatibility - the real, up-to-date setup/start script
# is setup-portable.sh (starts every service: postgres, redis, minio, api,
# job-worker, browser-worker, web, mock-ats - this used to start only a
# subset via podman-compose specifically).
set -e
cd "$(dirname "$0")"
exec ./setup-portable.sh "$@"
