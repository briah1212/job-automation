#!/bin/bash
# Bring up the whole platform (Postgres, Redis, MinIO, API, job-worker,
# browser-worker, web, mock ATS) from a fresh `git clone`, with no manual
# setup steps and no external accounts/services required.
#
# Usage:
#   ./setup-portable.sh                          # deploy for localhost
#   ./setup-portable.sh hermes.example.com        # deploy for a remote server
#   PUBLIC_HOST=10.0.0.5 ./setup-portable.sh      # same, via env var
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo "Job Automation - Portable Setup"
echo "=========================================="

# --- Detect Docker Compose --------------------------------------------------
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v podman-compose &> /dev/null; then
    COMPOSE="podman-compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "Error: need 'docker compose', 'docker-compose', or 'podman-compose' installed."
    exit 1
fi
echo "Using: $COMPOSE"

random_hex() {
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    else
        python3 -c "import secrets; print(secrets.token_hex(32))"
    fi
}

# --- Create .env if missing, with real random secrets -----------------------
if [ ! -f .env ]; then
    echo "No .env found - creating one from .env.example with freshly generated secrets."
    cp .env.example .env

    sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=$(random_hex)/" .env
    sed -i.bak "s/^INTERNAL_API_KEY=.*/INTERNAL_API_KEY=$(random_hex)/" .env
    sed -i.bak "s/^NEXTAUTH_SECRET=.*/NEXTAUTH_SECRET=$(random_hex)/" .env
    sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(random_hex)/" .env
    sed -i.bak "s/^MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=$(random_hex)/" .env
    rm -f .env.bak

    echo "Generating CREDENTIAL_ENCRYPTION_KEY (needs the api image; building it now)..."
    $COMPOSE build api > /dev/null
    FERNET_KEY=$($COMPOSE run --rm --no-deps api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" | tr -d '\r')
    sed -i.bak "s#^CREDENTIAL_ENCRYPTION_KEY=.*#CREDENTIAL_ENCRYPTION_KEY=${FERNET_KEY}#" .env
    rm -f .env.bak

    echo "Generated .env with random secrets. Review it before exposing this server publicly."
else
    echo ".env already exists - leaving it as-is."
fi

# --- Set the public address this server will be reached at ------------------
PUBLIC_HOST="${1:-${PUBLIC_HOST:-}}"
if [ -n "$PUBLIC_HOST" ]; then
    # Pull the port values already in .env so we don't clobber a custom port.
    WEB_PORT=$(grep -E '^WEB_PORT=' .env | cut -d= -f2)
    API_PORT=$(grep -E '^API_PORT=' .env | cut -d= -f2)
    WEB_PORT=${WEB_PORT:-3002}
    API_PORT=${API_PORT:-8001}

    sed -i.bak "s#^PUBLIC_HOST=.*#PUBLIC_HOST=${PUBLIC_HOST}#" .env
    sed -i.bak "s#^NEXT_PUBLIC_API_URL=.*#NEXT_PUBLIC_API_URL=http://${PUBLIC_HOST}:${API_PORT}#" .env
    sed -i.bak "s#^NEXTAUTH_URL=.*#NEXTAUTH_URL=http://${PUBLIC_HOST}:${WEB_PORT}#" .env
    rm -f .env.bak
    echo "Configured for public host: ${PUBLIC_HOST}"
else
    echo "No PUBLIC_HOST given - deploying for localhost only."
    echo "  (Re-run as './setup-portable.sh your.server.address' to change this later - it requires rebuilding the web image.)"
fi

# --- Build and start everything ---------------------------------------------
echo ""
echo "Building images..."
$COMPOSE build

echo "Starting all services..."
$COMPOSE up -d

echo ""
echo "Waiting for the API to become healthy..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:$(grep -E '^API_PORT=' .env | cut -d= -f2 || echo 8001)/health" > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ""
echo "✓ Setup complete!"
WEB_PORT=$(grep -E '^WEB_PORT=' .env | cut -d= -f2)
API_PORT=$(grep -E '^API_PORT=' .env | cut -d= -f2)
MOCK_ATS_PORT=$(grep -E '^MOCK_ATS_PORT=' .env | cut -d= -f2)
HOST_FOR_URLS="${PUBLIC_HOST:-localhost}"
echo "  Web:       http://${HOST_FOR_URLS}:${WEB_PORT:-3002}"
echo "  API Docs:  http://${HOST_FOR_URLS}:${API_PORT:-8001}/docs"
echo "  Mock ATS:  http://${HOST_FOR_URLS}:${MOCK_ATS_PORT:-8080}"
echo ""
echo "Logs:   $COMPOSE logs -f"
echo "Stop:   $COMPOSE down"
